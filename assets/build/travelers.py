"""
Traveler-dot morph engine: samples ~900 points from the portrait silhouette and
from each logo silhouette, then solves an optimal-transport assignment between
consecutive phases (portrait -> logo1 -> logo2 -> logo3 -> portrait) so each
traveler dot takes the shortest path when it moves.

Run inside conda env `project_env`. Depends on pipeline.py having already been
run (uses assets/build/intermediates/dark_ink.npy for the portrait shape).
"""
import numpy as np
import subprocess
from scipy.optimize import linear_sum_assignment
from PIL import Image

SCALE = 1.6
N_TRAVELERS = 900
LOGO_DIR = "assets/build/logos"
INTER = "assets/build/intermediates"
OUT = "assets/build/intermediates"

LOGOS = ["python", "opencv", "ultralytics"]


def sample_grid_points(mask, n_target, seed=0):
    """Grid-sample points inside a boolean mask, evenly spaced, then trim/pad to n_target."""
    ys, xs = np.where(mask)
    if len(xs) == 0:
        raise ValueError("empty mask")
    area = len(xs)
    # estimate grid step to land near n_target points
    step = max(1, int(np.sqrt(area / n_target)))
    h, w = mask.shape
    pts = []
    for y in range(0, h, step):
        for x in range(0, w, step):
            if mask[y, x]:
                pts.append((x, y))
    pts = np.array(pts, dtype=np.float64)
    rng = np.random.default_rng(seed)
    if len(pts) > n_target:
        idx = rng.choice(len(pts), n_target, replace=False)
        pts = pts[idx]
    elif len(pts) < n_target:
        # pad by resampling random points from the mask directly
        extra_idx = rng.choice(len(xs), n_target - len(pts), replace=True)
        extra = np.stack([xs[extra_idx], ys[extra_idx]], axis=1).astype(np.float64)
        pts = np.concatenate([pts, extra], axis=0)
    return pts  # (n_target, 2) in grid units


def rasterize_logo_mask(svg_path, res=200):
    """Render a logo SVG and return (boolean fill mask, RGB array) at res x res,
    so dots can later be colored with the logo's own original brand colors."""
    png_path = svg_path.replace(".svg", "_mask.png")
    subprocess.run(["rsvg-convert", "-w", str(res), "-h", str(res),
                     svg_path, "-o", png_path], check=True)
    im = Image.open(png_path).convert("RGBA")
    arr = np.array(im)
    alpha = arr[:, :, 3]
    return alpha > 40, arr[:, :, :3]


def sample_colors_at(rgb, points_grid_units):
    """Look up the original logo RGB color at each sampled point (grid-unit coords,
    same space as the mask points were sampled in, i.e. pre-fit-to-frame)."""
    h, w = rgb.shape[:2]
    xs = np.clip(points_grid_units[:, 0].astype(int), 0, w - 1)
    ys = np.clip(points_grid_units[:, 1].astype(int), 0, h - 1)
    px = rgb[ys, xs]
    return [f"#{r:02x}{g:02x}{b:02x}" for r, g, b in px]


def fit_points_to_frame(pts, target_w, target_h, margin=0.12):
    """Rescale/center a point cloud (grid coords) to fit within target_w x target_h,
    preserving aspect ratio, with a margin fraction on each side."""
    x0, y0 = pts[:, 0].min(), pts[:, 1].min()
    x1, y1 = pts[:, 0].max(), pts[:, 1].max()
    w, h = x1 - x0, y1 - y0
    avail_w = target_w * (1 - 2 * margin)
    avail_h = target_h * (1 - 2 * margin)
    s = min(avail_w / w, avail_h / h)
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    tx, ty = target_w / 2, target_h / 2
    out = pts.copy()
    out[:, 0] = (pts[:, 0] - cx) * s + tx
    out[:, 1] = (pts[:, 1] - cy) * s + ty
    return out


def main():
    dark_ink = np.load(f"{INTER}/dark_ink.npy")
    h, w = dark_ink.shape
    frame_w, frame_h = w * SCALE, h * SCALE

    portrait_pts = sample_grid_points(dark_ink, N_TRAVELERS, seed=1)
    portrait_px = portrait_pts * SCALE  # already in the right frame, native scale

    NEUTRAL_COLOR = "#22D3EE"  # fallback fill for portrait/transition segments

    phase_points = {"portrait": portrait_px}
    phase_colors_raw = {"portrait": [NEUTRAL_COLOR] * N_TRAVELERS}
    for logo in LOGOS:
        mask, rgb = rasterize_logo_mask(f"{LOGO_DIR}/{logo}.svg")
        pts = sample_grid_points(mask, N_TRAVELERS, seed=hash(logo) % 1000)
        colors = sample_colors_at(rgb, pts)  # sample BEFORE re-fitting to frame
        pts_fit = fit_points_to_frame(pts, frame_w, frame_h, margin=0.22)
        phase_points[logo] = pts_fit
        phase_colors_raw[logo] = colors

    order = ["portrait"] + LOGOS + ["portrait"]
    # solve assignment for each consecutive pair, chaining traveler identity
    sequences = [phase_points[order[0]]]
    color_sequences = [phase_colors_raw[order[0]]]

    total_costs = []
    for i in range(len(order) - 1):
        a_name, b_name = order[i], order[i + 1]
        a_pts = sequences[-1]
        b_pts_all = phase_points[b_name]
        cost = np.linalg.norm(a_pts[:, None, :] - b_pts_all[None, :, :], axis=2)
        row_ind, col_ind = linear_sum_assignment(cost)
        b_pts_matched = b_pts_all[col_ind]
        b_colors_all = np.array(phase_colors_raw[b_name])
        b_colors_matched = b_colors_all[col_ind]
        total_costs.append(cost[row_ind, col_ind].sum())
        sequences.append(b_pts_matched)
        color_sequences.append(list(b_colors_matched))

    print("phase order:", order)
    print("total assignment cost per transition:", [f"{c:.0f}" for c in total_costs])
    print("avg per-dot travel distance per transition:",
          [f"{c/N_TRAVELERS:.1f}px" for c in total_costs])

    seq_arr = np.stack(sequences, axis=0)  # (n_phases, N_TRAVELERS, 2)
    np.save(f"{OUT}/traveler_sequence.npy", seq_arr)
    with open(f"{OUT}/traveler_phase_order.txt", "w") as f:
        f.write(",".join(order))

    color_arr = np.array(color_sequences)  # (n_phases, N_TRAVELERS) of hex strings
    np.save(f"{OUT}/traveler_colors.npy", color_arr)

    # quick static previews of each phase's point cloud, to verify shapes before animating
    for i, name in enumerate(order):
        pts = seq_arr[i]
        circles = "".join(f'<circle cx="{x:.0f}" cy="{y:.0f}" r="2"/>' for x, y in pts)
        svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{frame_w:.0f}" height="{frame_h:.0f}">'
               f'<rect width="100%" height="100%" fill="#0A101F"/>'
               f'<g fill="#A78BFA">{circles}</g></svg>')
        with open(f"{OUT}/traveler_phase_{i}_{name}.svg", "w") as f:
            f.write(svg)
        subprocess.run(["rsvg-convert", f"{OUT}/traveler_phase_{i}_{name}.svg",
                         "-o", f"{OUT}/traveler_phase_{i}_{name}.png"], check=True)

    print("done")


if __name__ == "__main__":
    main()

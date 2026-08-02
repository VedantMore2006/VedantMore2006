"""
Assembles the animated portrait using CSS @keyframes (shared timing, per-element
custom properties) instead of inline SMIL, to keep file size sane.

Key size decisions vs the literal two-layer spec:
- No separate duplicate intro layer. The same 94 drift bands double as the intro
  shimmer unit: each band gets a one-shot CSS fade-in (introFade, staggered via
  animation-delay) nested inside its infinite loop-drift animation. Since bands
  are spatially organic clusters covering the whole portrait (not raster order),
  staggering their fade-in still reads as scattered shimmer, not a wipe, without
  paying for ~460KB of duplicate dot markup.
- Traveler positions (900 dots x 9 keyframes x 2 axes) are stored as CSS custom
  properties and animated via ONE shared @keyframes rule, instead of two
  <animate> elements per dot. Cuts per-dot fixed overhead substantially.

Run inside conda env `project_env`, after pipeline.py and travelers.py.
Outputs: assets/build/svg/portrait_animated_dark.svg
         assets/build/svg/portrait_animated_light.svg
"""
import numpy as np
import subprocess
from sklearn.cluster import KMeans

SCALE = 1.6
N_BANDS = 94
DRIFT_FRACTION = 0.42
NOISE_SIGMA = 4.0
INTER = "assets/build/intermediates"
SVG_DIR = "assets/build/svg"

T_PORTRAIT = 3.0
T_TRANS = 1.3
T_LOGO = 2.0
LOOP_DUR = T_PORTRAIT + 4 * T_TRANS + 3 * T_LOGO  # 14.2s
INTRO_DUR = 3.2

MODES = {
    "dark": dict(bg="#0A101F", portrait_color="#A78BFA", traveler_color="#22D3EE",
                 ink_file=f"{INTER}/dark_ink.npy"),
    "light": dict(bg="#FFFFFF", portrait_color="#000000", traveler_color="#7C3AED",
                  ink_file=f"{INTER}/light_ink.npy"),
}


def pct(*times):
    return [t / LOOP_DUR * 100 for t in times]


def build_drift_bands(ink, logo1_centroid, seed=0):
    ys, xs = np.where(ink)
    pts = np.stack([xs, ys], axis=1).astype(np.float64) * SCALE
    rng = np.random.default_rng(seed)
    ideal_drift = DRIFT_FRACTION * (logo1_centroid[None, :] - pts)
    noisy_drift = ideal_drift + rng.normal(0, NOISE_SIGMA, size=ideal_drift.shape)
    features = np.concatenate([pts, noisy_drift * 0.15], axis=1)
    km = KMeans(n_clusters=N_BANDS, n_init=3, random_state=seed).fit(features)
    labels = km.labels_
    bands = []
    for b in range(N_BANDS):
        mask = labels == b
        if not mask.any():
            continue
        band_pts = pts[mask]
        band_drift = noisy_drift[mask].mean(axis=0)
        bands.append(dict(points=band_pts, drift=band_drift,
                           centroid=band_pts.mean(axis=0)))
    return bands


def render_dots(points):
    return "".join(f'<circle cx="{x:.0f}" cy="{y:.0f}"/>' for x, y in points)


def main():
    seq = np.load(f"{INTER}/traveler_sequence.npy")  # (5, 900, 2)
    colors = np.load(f"{INTER}/traveler_colors.npy")  # (5, 900) hex strings
    logo1_centroid = seq[1].mean(axis=0)

    for mode_name, cfg in MODES.items():
        ink = np.load(cfg["ink_file"])
        h, w = ink.shape
        frame_w, frame_h = w * SCALE, h * SCALE

        bands = build_drift_bands(ink, logo1_centroid, seed=3)
        rng = np.random.default_rng(7)

        # p0: loop start / p1: portrait hold ends, transition-out begins
        # p2: arrival at logo1, fully hidden begins / p3: departure from logo3,
        # return-transition begins (fades back in smoothly through p5)
        # p5: loop end, back to full portrait
        p0, p1, p2, p3, p5 = pct(
            0, T_PORTRAIT, T_PORTRAIT + T_TRANS,
            T_PORTRAIT + T_TRANS + 3 * T_LOGO + 2 * T_TRANS,
            LOOP_DUR,
        )

        band_svgs = []
        for b in bands:
            dx, dy = b["drift"]
            # spread fade-in delay across the intro window based on band centroid
            # (position-derived, not raster order -> scattered, not a wipe)
            delay = float(rng.uniform(0, INTRO_DUR - 1.2))
            dots = render_dots(b["points"])
            inner = (
                f'<g class="band" style="--dx:{dx:.1f}px;--dy:{dy:.1f}px">'
                f'{dots}</g>'
            )
            outer = (
                f'<g class="bandIntro" style="opacity:0;animation-delay:{delay:.2f}s">'
                f'{inner}</g>'
            )
            band_svgs.append(outer)
        base_layer = f'<g fill="{cfg["portrait_color"]}">{"".join(band_svgs)}</g>'

        # travelers: shared keyframes, per-dot custom properties (position + the
        # dot's own original brand color for each logo it visits)
        n_dots = seq.shape[1]
        trav_svgs = []
        for i in range(n_dots):
            xs = [seq[p, i, 0] for p in range(5)]
            ys = [seq[p, i, 1] for p in range(5)]
            xvals = [xs[0], xs[0], xs[1], xs[1], xs[2], xs[2], xs[3], xs[3], xs[4]]
            yvals = [ys[0], ys[0], ys[1], ys[1], ys[2], ys[2], ys[3], ys[3], ys[4]]
            x0v, y0v = xvals[0], yvals[0]
            # store as deltas from the base cx/cy and animate transform (compositor-
            # only) instead of cx/cy (layout-triggering) -- the single biggest FPS
            # cost across 900 simultaneously-animating dots
            props = ";".join(
                f"--dx{k}:{v - x0v:.0f}px" for k, v in enumerate(xvals) if k > 0
            )
            props += ";" + ";".join(
                f"--dy{k}:{v - y0v:.0f}px" for k, v in enumerate(yvals) if k > 0
            )
            props += (f";--c1:{colors[1, i]};--c2:{colors[2, i]};--c3:{colors[3, i]}")
            trav_svgs.append(
                f'<circle class="trav" cx="{x0v:.0f}" cy="{y0v:.0f}" style="{props}"/>'
            )
        traveler_layer = f'<g id="travelers">{"".join(trav_svgs)}</g>'

        t0, t1, t2, t3, t4, t5, t6, t7, t8 = pct(
            0, T_PORTRAIT, T_PORTRAIT + T_TRANS,
            T_PORTRAIT + T_TRANS + T_LOGO,
            T_PORTRAIT + 2 * T_TRANS + T_LOGO,
            T_PORTRAIT + 2 * T_TRANS + 2 * T_LOGO,
            T_PORTRAIT + 3 * T_TRANS + 2 * T_LOGO,
            T_PORTRAIT + 3 * T_TRANS + 3 * T_LOGO,
            LOOP_DUR,
        )
        trav_opacity_pct = pct(0, T_PORTRAIT, T_PORTRAIT + T_TRANS * 0.5,
                                LOOP_DUR - T_TRANS * 0.5, LOOP_DUR)

        style = f'''<style>
.band circle, .bandIntro .band circle {{ r: 0.62; }}
.bandIntro {{
  animation: introFade 1.2s ease-out 1 forwards;
}}
.band {{
  animation: loopDrift {LOOP_DUR}s linear infinite;
}}
@keyframes introFade {{
  0% {{ opacity: 0; }}
  100% {{ opacity: 1; }}
}}
@keyframes loopDrift {{
  {p0:.3f}%, {p1:.3f}% {{ transform: translate(0,0); opacity: 1; }}
  {p2:.3f}% {{ transform: translate(var(--dx),var(--dy)); opacity: 0; }}
  {p3:.3f}% {{ transform: translate(var(--dx),var(--dy)); opacity: 0; }}
  {p5:.3f}% {{ transform: translate(0,0); opacity: 1; }}
}}
.trav {{
  r: 0.9;
  fill: {cfg["traveler_color"]};
  animation: travelPos {LOOP_DUR}s linear infinite,
             travelFill {LOOP_DUR}s linear infinite;
}}
#travelers {{
  animation: travelOpacity {LOOP_DUR}s linear infinite;
}}
@keyframes travelFill {{
  {t1:.3f}% {{ fill: {cfg["traveler_color"]}; }}
  {t2:.3f}% {{ fill: var(--c1); }}
  {t3:.3f}% {{ fill: var(--c1); }}
  {t4:.3f}% {{ fill: var(--c2); }}
  {t5:.3f}% {{ fill: var(--c2); }}
  {t6:.3f}% {{ fill: var(--c3); }}
  {t7:.3f}% {{ fill: var(--c3); }}
  {t8:.3f}% {{ fill: {cfg["traveler_color"]}; }}
}}
@keyframes travelPos {{
  {t0:.3f}% {{ transform: translate(0,0); }}
  {t1:.3f}% {{ transform: translate(var(--dx1),var(--dy1)); }}
  {t2:.3f}% {{ transform: translate(var(--dx2),var(--dy2)); }}
  {t3:.3f}% {{ transform: translate(var(--dx3),var(--dy3)); }}
  {t4:.3f}% {{ transform: translate(var(--dx4),var(--dy4)); }}
  {t5:.3f}% {{ transform: translate(var(--dx5),var(--dy5)); }}
  {t6:.3f}% {{ transform: translate(var(--dx6),var(--dy6)); }}
  {t7:.3f}% {{ transform: translate(var(--dx7),var(--dy7)); }}
  {t8:.3f}%, 100% {{ transform: translate(var(--dx8),var(--dy8)); }}
}}
@keyframes travelOpacity {{
  {trav_opacity_pct[0]:.3f}% {{ opacity: 0; }}
  {trav_opacity_pct[1]:.3f}% {{ opacity: 0; }}
  {trav_opacity_pct[2]:.3f}% {{ opacity: 1; }}
  {trav_opacity_pct[3]:.3f}% {{ opacity: 1; }}
  {trav_opacity_pct[4]:.3f}% {{ opacity: 0; }}
}}
</style>'''
        svg = (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{frame_w:.0f}" height="{frame_h:.0f}" '
            f'viewBox="0 0 {frame_w:.0f} {frame_h:.0f}">\n'
            f'{style}\n'
            f'<rect width="100%" height="100%" fill="{cfg["bg"]}"/>\n'
            f'{base_layer}\n{traveler_layer}\n'
            f'</svg>'
        )
        out_path = f"{SVG_DIR}/portrait_animated_{mode_name}.svg"
        with open(out_path, "w") as f:
            f.write(svg)
        print(f"[{mode_name}] wrote {out_path}, {len(svg)} bytes ({len(svg)/1024:.0f}KB)")

        subprocess.run(["rsvg-convert", "-b", cfg["bg"], out_path,
                         "-o", f"{INTER}/animated_{mode_name}_t0.png"], check=True)


if __name__ == "__main__":
    main()

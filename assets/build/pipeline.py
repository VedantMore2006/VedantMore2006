"""
Portrait -> dot-matrix SVG pipeline for the GitHub profile banner.
Run inside conda env `project_env`.

Source: assets/source/background removed.png (has real alpha transparency)
Outputs: assets/build/svg/portrait_light.svg, portrait_dark.svg
         assets/build/preview/portrait_light.png, portrait_dark.png
"""
import numpy as np
from PIL import Image, ImageOps, ImageFilter
import subprocess

SRC = "assets/source/background removed.png"
INTER = "assets/build/intermediates"
SVG_DIR = "assets/build/svg"
PREVIEW_DIR = "assets/build/preview"

GRID_W, GRID_H = 260, 295  # trimmed from the doc's 300x340 to cap circle-dot file size
SCALE = 1.6
DOT_RADIUS = 0.62
SHADOW_CLAMP = 210.0    # dark-mode floor so shadow regions never go fully blank
HIGHLIGHT_CLAMP = 222.0  # light-mode ceiling so blown highlights (cheek, shirt) keep dots
LIGHT_GAMMA = 1.18       # >1 darkens midtones, raising overall dot density

LIGHT_COLOR, LIGHT_BG = "#000000", "#FFFFFF"
DARK_COLOR, DARK_BG = "#A78BFA", "#0A101F"


def crop_head_shoulders(im):
    """Crop to 300:340 aspect ratio using the alpha channel to center the subject."""
    arr = np.array(im)
    alpha = arr[:, :, 3]
    ys, xs = np.where(alpha > 10)
    top, bottom = ys.min(), ys.max()
    left, right = xs.min(), xs.max()

    target_aspect = GRID_W / GRID_H
    subj_w = right - left
    subj_h = bottom - top

    # pad around the subject bounding box, keep some headroom above hair
    pad_x = int(subj_w * 0.18)
    pad_top = int(subj_h * 0.12)
    crop_left = max(0, left - pad_x)
    crop_right = min(im.width, right + pad_x)
    crop_top = max(0, top - pad_top)

    crop_w = crop_right - crop_left
    crop_h = int(crop_w / target_aspect)
    crop_bottom = crop_top + crop_h
    if crop_bottom > im.height:
        crop_bottom = im.height
        crop_h = crop_bottom - crop_top
        crop_w = int(crop_h * target_aspect)
        crop_left = max(0, crop_left)
        crop_right = crop_left + crop_w

    return im.crop((crop_left, crop_top, crop_right, crop_bottom))


def fs_dither_serpentine(gray):
    """Floyd-Steinberg dithering, serpentine order. Returns bool ink grid (True=dot)."""
    arr = gray.astype(np.float64).copy()
    h, w = arr.shape
    ink = np.zeros((h, w), dtype=bool)
    for y in range(h):
        ltr = (y % 2 == 0)
        xs = range(w) if ltr else range(w - 1, -1, -1)
        for x in xs:
            old = arr[y, x]
            new = 0.0 if old < 128 else 255.0
            ink[y, x] = (new == 0.0)
            err = old - new
            if ltr:
                if x + 1 < w: arr[y, x + 1] += err * 7 / 16
                if y + 1 < h:
                    if x - 1 >= 0: arr[y + 1, x - 1] += err * 3 / 16
                    arr[y + 1, x] += err * 5 / 16
                    if x + 1 < w: arr[y + 1, x + 1] += err * 1 / 16
            else:
                if x - 1 >= 0: arr[y, x - 1] += err * 7 / 16
                if y + 1 < h:
                    if x + 1 < w: arr[y + 1, x + 1] += err * 3 / 16
                    arr[y + 1, x] += err * 5 / 16
                    if x - 1 >= 0: arr[y + 1, x - 1] += err * 1 / 16
    return ink


def ink_to_circle_centers(ink, scale=SCALE):
    """Flat list of (cx, cy) dot centers, 1 decimal precision to keep file size down."""
    h, w = ink.shape
    ys, xs = np.where(ink)
    cx = xs * scale + scale / 2
    cy = ys * scale + scale / 2
    return cx, cy


def build_svg(ink, color, bg, out_path, radius=DOT_RADIUS):
    h, w = ink.shape
    cx, cy = ink_to_circle_centers(ink)
    W, H = w * SCALE, h * SCALE
    # shared r/fill via CSS so each dot only costs its two coordinates
    # integer-rounded coords: at this scale sub-pixel precision is imperceptible
    # and costs real bytes across tens of thousands of dots
    circles = "".join(f'<circle cx="{x:.0f}" cy="{y:.0f}"/>' for x, y in zip(cx, cy))
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W:.0f}" height="{H:.0f}" '
        f'viewBox="0 0 {W:.0f} {H:.0f}">\n'
        f'<style>circle{{r:{radius};fill:{color}}}</style>\n'
        f'<rect width="{W:.0f}" height="{H:.0f}" fill="{bg}"/>\n'
        f'<g>{circles}</g>\n'
        f"</svg>"
    )
    with open(out_path, "w") as f:
        f.write(svg)
    return len(svg)


def main():
    im = Image.open(SRC).convert("RGBA")
    cropped = crop_head_shoulders(im)
    cropped.save(f"{INTER}/crop.png")

    resized = cropped.resize((GRID_W, GRID_H), Image.LANCZOS)
    resized.save(f"{INTER}/resized_300x340.png")

    arr = np.array(resized)
    alpha = arr[:, :, 3]
    subject_mask = alpha > 128
    np.save(f"{INTER}/subject_mask.npy", subject_mask)

    rgb = Image.fromarray(arr[:, :, :3], "RGB")
    gray = rgb.convert("L")
    gray = ImageOps.autocontrast(gray, cutoff=1)
    gray = gray.filter(ImageFilter.UnsharpMask(radius=3, percent=140))
    gray_arr = np.array(gray).astype(np.float32)
    gray_arr = np.clip((gray_arr - 127.5) * 1.3 + 127.5, 0, 255)
    Image.fromarray(gray_arr.astype(np.uint8)).save(f"{INTER}/gray_contrast.png")

    # LIGHT MODE: keep background, dots = dark parts of photo.
    # Outside the subject (fully transparent originally) is uniform white -> autocontrast
    # already pushes it near 255, so it naturally dithers to near-empty. Force it explicitly.
    light_input = gray_arr.copy()
    # gamma darken midtones to raise overall density, then clamp highlights (bright
    # cheek/shirt) so they never dither to fully empty patches
    light_input = 255.0 * (light_input / 255.0) ** LIGHT_GAMMA
    subj_vals = light_input[subject_mask]
    light_input[subject_mask] = np.minimum(subj_vals, HIGHLIGHT_CLAMP)
    light_input[~subject_mask] = 255.0
    light_ink = fs_dither_serpentine(light_input)
    np.save(f"{INTER}/light_ink.npy", light_ink)

    # DARK MODE: dots draw the lit subject; background fully cleared; shadow floor
    # clamp avoids voids in darker subject regions (neck/collar shadow, beard).
    inverted = 255.0 - gray_arr
    inverted[~subject_mask] = 255.0
    region = inverted[subject_mask]
    inverted[subject_mask] = np.minimum(region, SHADOW_CLAMP)
    dark_ink = fs_dither_serpentine(inverted)
    dark_ink[~subject_mask] = False
    np.save(f"{INTER}/dark_ink.npy", dark_ink)

    print("light density:", light_ink.mean(), "dark density:", dark_ink.mean())

    light_bytes = build_svg(light_ink, LIGHT_COLOR, LIGHT_BG, f"{SVG_DIR}/portrait_light.svg")
    dark_bytes = build_svg(dark_ink, DARK_COLOR, DARK_BG, f"{SVG_DIR}/portrait_dark.svg")
    print("light svg bytes:", light_bytes, "dark svg bytes:", dark_bytes)

    subprocess.run(["rsvg-convert", f"{SVG_DIR}/portrait_light.svg",
                     "-o", f"{PREVIEW_DIR}/portrait_light.png"], check=True)
    subprocess.run(["rsvg-convert", "-b", DARK_BG, f"{SVG_DIR}/portrait_dark.svg",
                     "-o", f"{PREVIEW_DIR}/portrait_dark.png"], check=True)
    print("done")


if __name__ == "__main__":
    main()

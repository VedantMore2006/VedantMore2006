"""
Assembles the final banner: terminal window chrome + VISUAL.MAP portrait panel
(embeds the animated portrait SVG as a nested <svg>) + SYSTEM.INFO readout panel
with dotted leaders, LIVE badge, and handle pill.

Run inside conda env `project_env`, after animate.py.
Outputs: assets/build/svg/dark.svg
         assets/build/svg/light.svg
"""
import re

SVG_DIR = "assets/build/svg"

W, H = 1180, 610
PAD = 28
TITLE_BAR_H = 34
LEFT_FRAC = 0.38

FONT = "ui-monospace, SFMono-Regular, 'Cascadia Code', Menlo, Consolas, monospace"
ROW_FONT_SIZE = 14
HEADER_FONT_SIZE = 13
LIVE_FONT_SIZE = 12
PILL_FONT_SIZE = 14
ROW_SPACING = 23

# rough monospace advance width as a fraction of font-size (typical ~0.6)
CHAR_W = 0.6

ROWS = [
    ("Subject", "Vedant More"),
    ("Role", "Computer Vision Engineer"),
    ("Origin", "Shegaon, Maharashtra, IN"),
    ("Education", "BCA (AI Focus)"),
    ("Status", "Learning . Training . Shipping"),
    ("ToolChain", "VSCode, Neovim, Git, Docker"),
    ("Core.Lang", "Python, JavaScript, Bash"),
    ("Core.Frontend", "HTML5, WebRTC"),
    ("Core.Backend", "FastAPI, Uvicorn"),
    ("Core.Database", "SQLite"),
    ("Core.Infra", "Docker, GCP, Linux"),
    ("Grid.Mail", "vedantmoremain@gmail.com"),
    ("Grid.Portfolio", "MyResume.pdf"),
    ("Grid.LinkedIn", "vedant-more-5796a1326"),
    ("Grid.GitHub", "VedantMore2006"),
    ("Grid.Instagram", "vedantvasantmore88"),
]

MODES = {
    "dark": dict(
        bg="#0A101F", panel_bg="#0f1729", border="#22D3EE33",
        title_text="#64748B", label_color="#64748B", value_color="#E2E8F0",
        leader_color="#334155", header_color="#22D3EE", accent="#10B981",
        pill_bg="#7C3AED", pill_text="#F8FAFC", portrait_svg="portrait_animated_dark.svg",
        live_color="#F87171",
    ),
    "light": dict(
        bg="#FFFFFF", panel_bg="#F8FAFC", border="#0891B233",
        title_text="#64748B", label_color="#64748B", value_color="#0F172A",
        leader_color="#CBD5E1", header_color="#0891B2", accent="#10B981",
        pill_bg="#7C3AED", pill_text="#F8FAFC", portrait_svg="portrait_animated_light.svg",
        live_color="#DC2626",
    ),
}


def esc(s):
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def text_w(s, font_size):
    return len(s) * font_size * CHAR_W


def build_row(label, value, x0, x1, y, cfg):
    label_fs = ROW_FONT_SIZE
    label_w = text_w(label, label_fs)
    value_w = text_w(value, label_fs)
    value_x = x1 - value_w

    leader_start = x0 + label_w + 6
    leader_end = value_x - 6
    leader_len = max(0, leader_end - leader_start)
    dot_gap = 5
    n_dots = max(0, int(leader_len // dot_gap))
    dots = "".join(
        f'<circle cx="{leader_start + i*dot_gap:.1f}" cy="{y-4:.1f}" r="0.9" '
        f'fill="{cfg["leader_color"]}"/>'
        for i in range(n_dots)
    )

    return (
        f'<text x="{x0}" y="{y}" font-family="{FONT}" font-size="{label_fs}" '
        f'fill="{cfg["label_color"]}" textLength="{label_w:.1f}" '
        f'lengthAdjust="spacingAndGlyphs">{esc(label)}</text>'
        f'{dots}'
        f'<text x="{value_x:.1f}" y="{y}" font-family="{FONT}" font-size="{label_fs}" '
        f'fill="{cfg["value_color"]}" textLength="{value_w:.1f}" '
        f'lengthAdjust="spacingAndGlyphs">{esc(value)}</text>'
    )


def load_portrait_inner(path):
    """Extract the inner content + viewBox dims of the animated portrait SVG so it
    can be embedded as a nested <svg> (self-contained style/animation scope)."""
    with open(path) as f:
        content = f.read()
    m = re.search(r'width="(\d+)" height="(\d+)"', content)
    w, h = int(m.group(1)), int(m.group(2))
    inner = re.search(r'viewBox="[^"]*">(.*)</svg>', content, re.S).group(1)
    return inner, w, h


def build_mode(mode_name, cfg):
    portrait_inner, pw, ph = load_portrait_inner(f"{SVG_DIR}/{cfg['portrait_svg']}")

    left_w = int(W * LEFT_FRAC)
    frame_x, frame_y = PAD, TITLE_BAR_H + PAD
    frame_w = left_w - PAD - 14
    frame_h = H - TITLE_BAR_H - PAD * 2

    # fit portrait (pw x ph) into frame, preserving aspect, centered
    scale = min(frame_w / pw, frame_h / ph)
    pfw, pfh = pw * scale, ph * scale
    px = frame_x + (frame_w - pfw) / 2
    py = frame_y + (frame_h - pfh) / 2

    right_x0 = left_w + 26
    right_x1 = W - PAD - 4

    header_y = TITLE_BAR_H + PAD + 14
    pill_text = "@VedantMore2006"
    pill_w = text_w(pill_text, PILL_FONT_SIZE) + 24
    pill_x = right_x1 - pill_w
    pill_y = header_y + 10

    rows_y0 = pill_y + 34
    rows_svg = "".join(
        build_row(label, value, right_x0, right_x1, rows_y0 + i * ROW_SPACING, cfg)
        for i, (label, value) in enumerate(ROWS)
    )

    live_x = right_x0
    live_dot_r = 4

    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">
<defs>
<style>
@keyframes livePulse {{ 0%,100% {{ opacity: 1; }} 50% {{ opacity: 0.35; }} }}
.liveDot {{ animation: livePulse 1.6s ease-in-out infinite; }}
</style>
<clipPath id="frameClip-{mode_name}">
  <rect x="{frame_x}" y="{frame_y}" width="{frame_w}" height="{frame_h}" rx="8"/>
</clipPath>
</defs>
<rect width="{W}" height="{H}" rx="14" fill="{cfg['bg']}"/>
<rect x="0.5" y="0.5" width="{W-1}" height="{H-1}" rx="14" fill="none" stroke="{cfg['border']}"/>

<rect x="0" y="0" width="{W}" height="{TITLE_BAR_H}" rx="14" fill="{cfg['panel_bg']}"/>
<rect x="0" y="{TITLE_BAR_H-14}" width="{W}" height="14" fill="{cfg['panel_bg']}"/>
<circle cx="22" cy="{TITLE_BAR_H/2}" r="5" fill="#FF5F56"/>
<circle cx="40" cy="{TITLE_BAR_H/2}" r="5" fill="#FFBD2E"/>
<circle cx="58" cy="{TITLE_BAR_H/2}" r="5" fill="#27C93F"/>
<text x="{W/2}" y="{TITLE_BAR_H/2+4}" text-anchor="middle" font-family="{FONT}" \
font-size="12" fill="{cfg['title_text']}">profile.sh --live</text>

<rect x="{frame_x}" y="{frame_y}" width="{frame_w}" height="{frame_h}" rx="8" \
fill="none" stroke="{cfg['border']}"/>
<text x="{frame_x+10}" y="{frame_y+18}" font-family="{FONT}" font-size="11" \
fill="{cfg['label_color']}" letter-spacing="1.5">VISUAL.MAP</text>
<g clip-path="url(#frameClip-{mode_name})">
  <svg x="{px:.1f}" y="{py+10:.1f}" width="{pfw:.1f}" height="{pfh:.1f}" \
viewBox="0 0 {pw} {ph}">{portrait_inner}</svg>
</g>

<text x="{right_x0}" y="{header_y}" font-family="{FONT}" font-size="{HEADER_FONT_SIZE}" \
fill="{cfg['header_color']}" letter-spacing="1.5">SYSTEM.INFO</text>
<circle class="liveDot" cx="{live_x+118}" cy="{header_y-4}" r="{live_dot_r}" fill="{cfg['live_color']}"/>
<text x="{live_x+128}" y="{header_y}" font-family="{FONT}" font-size="{LIVE_FONT_SIZE}" \
fill="{cfg['live_color']}" letter-spacing="1">LIVE</text>

<rect x="{pill_x:.1f}" y="{pill_y-16:.1f}" width="{pill_w:.1f}" height="24" rx="12" fill="{cfg['pill_bg']}"/>
<text x="{pill_x+12:.1f}" y="{pill_y:.1f}" font-family="{FONT}" font-size="{PILL_FONT_SIZE}" \
fill="{cfg['pill_text']}">{pill_text}</text>

{rows_svg}
</svg>'''
    return svg


def main():
    for mode_name, cfg in MODES.items():
        svg = build_mode(mode_name, cfg)
        out_path = f"{SVG_DIR}/{mode_name}.svg"
        with open(out_path, "w") as f:
            f.write(svg)
        print(f"[{mode_name}] wrote {out_path}, {len(svg)} bytes ({len(svg)/1024:.0f}KB)")


if __name__ == "__main__":
    main()

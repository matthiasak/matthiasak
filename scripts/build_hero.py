#!/usr/bin/env python3
"""Render assets/hero.svg: art/keas.gif as a pixel sprite sheet on a game "character select" screen.

Needs ffmpeg + ffprobe on PATH and network access (Google Fonts subset of Press Start 2P, OFL).
Run from anywhere: python3 scripts/build_hero.py
"""
import base64, json, random, re, struct, subprocess, urllib.parse, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GIF, JPEG, OUT = ROOT / "art/keas.gif", ROOT / "art/keas.jpeg", ROOT / "assets/hero.svg"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
BG, PANEL, FG, DIM, AMBER = "#0B0F2E", "#141A45", "#F4F4F4", "#9AA0D0", "#F2B84B"

# (text, x, y, font-size, fill, blinks). Press Start 2P advance = 1em, so width = len(text) * size.
HUD = [
    ("PLAYER 1", 896, 84, 12, AMBER, True),
    ("MATT KEAS", 896, 124, 24, FG, False),
    ("AI/ML SWE @GOOGLE", 896, 156, 12, DIM, False),
    ("HOUSTON, TX", 896, 180, 12, DIM, False),
    ("NOW PLAYING: GIBBS + KEA", 744, 352, 10, FG, False),
    ("\u25b6 PRESS START", 744, 380, 12, AMBER, True),
]
# (label, bar fill 0..1, colour)
STATS = [("\u03bb FP", 1.00, AMBER), ("AIR BISON", 0.94, "#E5352B"), ("NODE HERD", 0.88, "#5FD068"), ("ALGOTRADE", 0.81, "#57A6FF")]


def png(src, pre, colors):
    """ffmpeg `pre` filters -> palette-quantized (no dither) single PNG, returned as bytes."""
    graph = f"{pre},split[a][b];[a]palettegen=max_colors={colors}:stats_mode=full:reserve_transparent=0[p];[b][p]paletteuse=dither=none"
    cmd = ["ffmpeg", "-v", "error", "-i", str(src), "-filter_complex", graph, "-frames:v", "1", "-f", "image2pipe", "-vcodec", "png", "-"]
    return subprocess.run(cmd, check=True, capture_output=True).stdout


def gif_frames():
    cmd = ["ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0",
           "-show_entries", "stream=nb_read_frames,r_frame_rate", "-of", "json", str(GIF)]
    s = json.loads(subprocess.run(cmd, check=True, capture_output=True).stdout)["streams"][0]
    num, den = map(int, s["r_frame_rate"].split("/"))
    return int(s["nb_read_frames"]), num / den


def font(text):
    """Press Start 2P subset to exactly `text` as woff2 (Google Fonts serves woff2 only to modern UAs)."""
    get = lambda u: urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": UA}), timeout=30).read()
    css = get("https://fonts.googleapis.com/css2?family=Press+Start+2P&text=" + urllib.parse.quote(text)).decode()
    m = re.search(r"url\((https://[^)]+)\) format\('woff2'\)", css)
    if not m:
        raise SystemExit(f"no woff2 url in Google Fonts css:\n{css}")
    return get(m.group(1))


def build():
    n, fps = gif_frames()
    # GIF native pixel is ~4.75px, so a 160x90 grid keeps the face detail; drawn at 4x = 640x360 stage.
    sheet = png(GIF, f"scale=160:90:flags=area,tile=1x{n}", 48)
    if struct.unpack(">II", sheet[16:24]) != (160, 90 * n):
        raise SystemExit("sprite sheet is not 160 x 90*frames")
    icon = png(JPEG, "scale=64:64:flags=area", 32)
    glyphs = "".join(sorted(set("".join(t for t, *_ in HUD) + "".join(l for l, *_ in STATS))))
    woff2 = font(glyphs)
    b64 = lambda b: base64.b64encode(b).decode()

    rng = random.Random(1337)  # fixed seed: rebuilds are byte-identical unless inputs change
    flakes = []
    for _ in range(40):
        size = 4 if rng.random() < 0.8 else 8
        x = 40 + 4 * rng.randrange(160)
        dur = round(rng.uniform(5, 11), 1)
        delay = round(rng.uniform(0, dur), 1)
        flakes.append(f'<rect class="flake anim" x="{x}" y="-8" width="{size}" height="{size}" style="animation-duration:{dur}s;animation-delay:-{delay}s"/>')

    hud = "".join(
        f'<text{" class=\"blink anim\"" if blink else ""} x="{x}" y="{y}" font-size="{fs}" fill="{fill}">{t}</text>'
        for t, x, y, fs, fill, blink in HUD)
    stats = []
    for i, (label, frac, colour) in enumerate(STATS):
        y = 220 + 28 * i
        stats.append(
            f'<text x="744" y="{y + 11}" font-size="10" fill="{FG}">{label}</text>'
            f'<rect x="856" y="{y}" width="280" height="12" fill="#262C66"/>'
            f'<rect class="fillbar anim" x="856" y="{y}" width="{round(280 * frac)}" height="12" fill="{colour}" style="animation-delay:{0.25 * i}s"/>'
            f'<rect x="856" y="{y}" width="280" height="12" fill="url(#seg)"/>')

    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 440" width="1200" height="440" role="img" aria-labelledby="hero-title hero-desc">
<title id="hero-title">Matt Keas, Player 1</title>
<desc id="hero-desc">Pixel-art sprite of Matt Keas in white ski goggles and a red jacket, laughing in a looping animation while pixel snow falls, beside a game character-select panel: AI/ML software engineer at Google, Houston, now playing gibbs and kea.</desc>
<defs><style>
@font-face{{font-family:'PS2P';src:url(data:font/woff2;base64,{b64(woff2)}) format('woff2')}}
text{{font-family:'PS2P',ui-monospace,monospace}}
.px{{image-rendering:pixelated}}
.play{{animation:play {n / fps:g}s steps({n}) infinite}}
@keyframes play{{to{{transform:translateY(-{360 * n}px)}}}}
.flake{{fill:#fff;opacity:.85;animation:fall 8s steps(52) infinite}}
@keyframes fall{{to{{transform:translate(-24px,416px)}}}}
.blink{{animation:blink 1s steps(1,end) infinite}}
@keyframes blink{{50%{{opacity:0}}}}
.fillbar{{transform-box:fill-box;transform-origin:left;animation:fill 1.4s steps(14) both}}
@keyframes fill{{from{{transform:scaleX(0)}}}}
@media (prefers-reduced-motion:reduce){{.anim{{animation:none!important}}}}
</style>
<clipPath id="stage"><rect x="40" y="40" width="640" height="360"/></clipPath>
<pattern id="scan" width="4" height="4" patternUnits="userSpaceOnUse"><rect width="4" height="1" fill="#000" opacity=".18"/></pattern>
<pattern id="seg" x="856" width="8" height="12" patternUnits="userSpaceOnUse"><rect x="7" width="1" height="12" fill="{BG}"/></pattern>
</defs>
<rect width="1200" height="440" fill="{BG}"/>
<svg x="40" y="40" width="640" height="360" viewBox="0 0 640 360"><image class="px play anim" image-rendering="optimizeSpeed" width="640" height="{360 * n}" href="data:image/png;base64,{b64(sheet)}"/></svg>
<g clip-path="url(#stage)">{"".join(flakes)}<rect x="40" y="40" width="640" height="360" fill="url(#scan)"/></g>
<rect x="38" y="38" width="644" height="364" fill="none" stroke="{FG}" stroke-width="4"/>
<rect x="718" y="38" width="444" height="364" fill="{PANEL}" stroke="{FG}" stroke-width="4"/>
<image class="px" image-rendering="optimizeSpeed" x="744" y="64" width="128" height="128" href="data:image/png;base64,{b64(icon)}"/>
<rect x="742" y="62" width="132" height="132" fill="none" stroke="{FG}" stroke-width="4"/>
{hud}{"".join(stats)}
</svg>
"""


if __name__ == "__main__":
    svg = build()
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(svg, encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)} ({len(svg.encode()) // 1024} KB)")

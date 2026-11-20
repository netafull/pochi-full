#!/usr/bin/env python3
"""ポチフル自身のアイコン・OGP画像を docs/static/assets/ に書き出す。

pochi-branding の関数(icon_html・render_html・png_to_jpeg・make_ico・ogp_html)を
import して流用する。pochi-branding には何も書かない(中間ファイルは一時フォルダ)。
実行: python3 make_icons.py   (ヘッドレスChromeとネット接続(Googleフォント)が必要)
"""
import math
import sys
import tempfile
from pathlib import Path

BRANDING = Path.home() / "Desktop/Claude/pochi-branding"
sys.path.insert(0, str(BRANDING))
import make_branding  # noqa: E402
import ogp_html as ogp_mod  # noqa: E402
from make_branding import icon_html, render_html, png_to_jpeg, make_ico  # noqa: E402
from ogp_html import ogp_html  # noqa: E402

# ポチフルのボタンは単色ではなく、ポチ各サイトの色を円グラフ状に並べる(2026-11-20 コグレ選択、案C)。
# 形・つや・Pの位置は pochi-branding/icon_svg.py の icon() と同じ。ボタンの面だけを差し替える。
PIE = ["#C8322B", "#E0780F", "#C9971C", "#1E8A5A", "#0A8CA8", "#2B62C8", "#6B41C4", "#C2185B"]
RIM = "#3a3a48"          # ボタンの側面(厚み)
SQUARE_BG = "#eeebf3"    # 全面塗り版(apple-touch-icon)の背景
COLOR = "#37474F"        # ページのアクセント色と OGP 下端の帯以外では使わない
OGP_BAR = "linear-gradient(90deg," + ",".join(PIE) + ")"
TITLE = "ポチフル"


def _pie(cx, cy, r):
    n = len(PIE)
    out = ""
    for i, c in enumerate(PIE):
        a0 = -math.pi / 2 + 2 * math.pi * i / n
        a1 = a0 + 2 * math.pi / n
        x0, y0 = cx + r * math.cos(a0), cy + r * math.sin(a0)
        x1, y1 = cx + r * math.cos(a1), cy + r * math.sin(a1)
        out += f'<path d="M{cx} {cy} L{x0:.2f} {y0:.2f} A{r} {r} 0 0 1 {x1:.2f} {y1:.2f} Z" fill="{c}"/>'
    return out


def rainbow_icon(color=None, variant="large", square=False):
    """icon_svg.icon() と同じ寸法で、面をポチ各色の円グラフにした版。color は互換のため受けて無視する。"""
    if variant == "small":
        r, top, depth, fs, tx, ty = 30, 31, 3, 44, 33.5, 32
        gloss = ('<path d="M8.5 24 A25 25 0 0 1 19 10" fill="none" stroke="#fff" '
                 'stroke-opacity=".7" stroke-width="4.4" stroke-linecap="round"/>')
    else:
        r, top, depth, fs, tx, ty = 28, 29.5, 6, 42, 33.6, 30.5
        gloss = ('<path d="M13.5 22 A21 21 0 0 1 25 10.5" fill="none" stroke="#fff" '
                 'stroke-opacity=".55" stroke-width="3.6" stroke-linecap="round"/>')
    bg = (f'<rect width="64" height="64" fill="{SQUARE_BG}"/><g transform="translate(6.4 6.4) scale(.8)">'
          if square else "")
    end = "</g>" if square else ""
    cid = f"pf{variant}{int(square)}"
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">'
        f'<defs><clipPath id="{cid}"><circle cx="32" cy="{top}" r="{r}"/></clipPath></defs>'
        f'{bg}<circle cx="32" cy="{top + depth}" r="{r}" fill="{RIM}"/>'
        f'<g clip-path="url(#{cid})">{_pie(32, top, r)}</g>{gloss}'
        f'<text x="{tx}" y="{ty}" text-anchor="middle" dominant-baseline="central" '
        f'font-family="Fredoka" font-weight="700" font-size="{fs}" fill="#fff" '
        f'stroke="#00000033" stroke-width="1.2" paint-order="stroke">P</text>'
        f'{end}</svg>'
    )


# pochi-branding 側の関数が使う icon() をこのスクリプトの中だけ差し替える(ファイルは書き換えない)
make_branding.icon = rainbow_icon
ogp_mod.icon = rainbow_icon
TAGLINE = "ポチシリーズ全14サイトの一覧"

OUT = Path(__file__).parent / "docs/static/assets"


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as t:
        tmp = Path(t)
        render_html(icon_html(COLOR, "large", 132), 132, 132, OUT / "logo.png", transparent=True)
        render_html(icon_html(COLOR, "small", 96), 96, 96, OUT / "favicon.png", transparent=True)
        render_html(icon_html(COLOR, "large", 180, square=True, transparent=False), 180, 180,
                    OUT / "apple-touch-icon.png")
        sizes = {}
        for s in (16, 32, 48):
            p = tmp / f"f{s}.png"
            render_html(icon_html(COLOR, "small", s), s, s, p, transparent=True)
            sizes[s] = p
        make_ico(sizes, OUT / "favicon.ico")
        render_html(ogp_html(TITLE, TAGLINE, OGP_BAR), 1200, 630, tmp / "ogp.png")
        png_to_jpeg(tmp / "ogp.png", OUT / "ogp.jpg")
    for h in OUT.glob("*.html"):  # render_html が横に残す中間HTML
        h.unlink()
    for p in sorted(OUT.iterdir()):
        print(p)


if __name__ == "__main__":
    main()

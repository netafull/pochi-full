#!/usr/bin/env python3
"""data/sites.json から docs/ 一式（index.html・404.html・robots.txt・sitemap.xml・CSS・アイコン）を書き出す。
標準ライブラリのみ。ポチフル自身のアイコン/OGPは make_icons.py が別に作る。
実行: python3 build.py
"""
import json
import shutil
import sys
from html import escape
from pathlib import Path

ROOT = Path(__file__).parent
DOCS = ROOT / "docs"
BRANDING_BUILD = Path.home() / "Desktop/Claude/pochi-branding/build"
# sites.json の "icon" に ~/Desktop/Claude からの相対パスを書くと、pochi-branding の代わりにそのPNGを使う
# （pochi-branding に載せないサイト用。例: マンガ新刊ポチは自サイトの static/assets/logo.png）
SITE_ROOT = Path.home() / "Desktop/Claude"

BASE = "https://pochi.netaful.jp/"
TITLE = "ポチフル｜ネタフルのポチシリーズ一覧"
NAME = "ポチフル"


def load_sites():
    return json.loads((ROOT / "data/sites.json").read_text(encoding="utf-8"))


def groups(sites):
    """出現順を保ったまま (グループ名, [サイト]) のリストにする。"""
    out = {}
    for s in sites:
        out.setdefault(s["group"], []).append(s)
    return list(out.items())


GA4_ID = "G-HF34XXVV03"

# ダッシュボード（feed-spec.md）。チップの source キー → sites.json の key（電書ポチだけ違う）
CHIPS = [
    ("shinkan", "shinkan"), ("conbini", "conbini"), ("fastfood", "fastfood"), ("cafe", "cafe"),
    ("sushi", "sushi"), ("cupmen", "cupmen"), ("book", "kindle"), ("kaden", "kaden"), ("apple", "apple"),
    ("manga", "manga"), ("netaful", "netaful"),
]
# ネタフル本体の記事（タグ728）は feed.json ではなく WordPress REST から読む。sites.json には無いのでチップ用の定義をここに持つ。
NETAFUL = {"key": "netaful", "name": "ネタフル", "color": "#6B7A14"}
NETAFUL_WP = "https://netaful.jp/wp-json/wp/v2/posts?tags=728&per_page=20&_fields=id,date,link,title,jetpack_featured_media_url"
# 読みに行く feed。食ポチ5サイトは新発売ポチの feed にまとまっている
FEEDS = [
    "https://shinkan.netaful.jp/feed.json",
    "https://shinhatsubai.netaful.jp/feed.json",
    "https://book.netaful.jp/feed.json",
    "https://kaden.netaful.jp/feed.json",
    "https://apple.netaful.jp/feed.json",
    "https://manga.netaful.jp/feed.json",
]


def head(title, desc, canonical, extra=""):
    return f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<!-- アクセス解析（GA4、2026-11-20 マル作成のプロパティ「ポチフル」） -->
<script async src="https://www.googletagmanager.com/gtag/js?id={GA4_ID}"></script>
<script>
window.dataLayer = window.dataLayer || [];
function gtag(){{dataLayer.push(arguments);}}
gtag('js', new Date());
gtag('config', '{GA4_ID}');
</script>
<title>{escape(title)}</title>
<meta name="description" content="{escape(desc)}">
<link rel="canonical" href="{canonical}">
<link rel="icon" type="image/png" sizes="96x96" href="/static/assets/favicon.png">
<link rel="icon" href="/static/assets/favicon.ico" sizes="any">
<link rel="apple-touch-icon" href="/static/assets/apple-touch-icon.png">
<meta property="og:type" content="website">
<meta property="og:title" content="{escape(title)}">
<meta property="og:description" content="{escape(desc)}">
<meta property="og:url" content="{canonical}">
<meta property="og:site_name" content="{NAME}">
<meta property="og:locale" content="ja_JP">
<meta property="og:image" content="{BASE}static/assets/ogp.jpg">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta name="twitter:card" content="summary_large_image">
<link rel="stylesheet" href="/static/style.css">
{extra}</head>
<body>
"""


def header(tag):
    return f"""<header class="site-header">
<{tag} class="site-title"><a href="/"><img src="/static/assets/logo.png" alt="" width="44" height="44">{NAME}</a></{tag}>
<p class="tagline">ネタフルのポチシリーズ全{{n}}サイトをまとめて見られる一覧ページ</p>
</header>
"""


FOOTER = """<footer class="site-footer">
<p><a href="https://netaful.jp/">ネタフル</a></p>
</footer>
</body>
</html>
"""


def card(s):
    return (
        f'<li class="pf-card"><a href="{escape(s["url"])}" style="--c:{escape(s["color"])}">'
        f'<img src="/static/icons/{s["key"]}.png" alt="" width="48" height="48" loading="lazy" decoding="async">'
        f'<span class="pf-body"><span class="pf-name">{escape(s["name"])}</span>'
        f'<span class="pf-desc">{escape(s["description"])}</span></span></a></li>'
    )


# JS が無いときは出さない（hidden のまま）。リンク集ビューだけの今のページになる
TABS = """<div class="pf-tabs" id="pf-tabs" role="tablist" aria-label="表示の切り替え" hidden>
<button type="button" role="tab" class="pf-tab" id="tab-links" data-view="links" aria-selected="true" aria-controls="view-links">ホーム</button>
<button type="button" role="tab" class="pf-tab" id="tab-dash" data-view="dash" aria-selected="false" aria-controls="view-dash" tabindex="-1">ダッシュボード</button>
</div>
"""


def chip(source, s):
    if s["key"] == "netaful":  # ロゴ無し。カードは色の帯だけになる
        return (
            f'<button type="button" class="pf-chip" data-source="{source}" data-name="{escape(s["name"])}" '
            f'data-color="{escape(s["color"])}" data-icon="" aria-pressed="true" style="--c:{escape(s["color"])}">'
            f'{escape(s["name"])}</button>'
        )
    icon = f"/static/icons/{s['key']}.png"
    return (
        f'<button type="button" class="pf-chip" data-source="{source}" data-name="{escape(s["name"])}" '
        f'data-color="{escape(s["color"])}" data-icon="{icon}" aria-pressed="true" style="--c:{escape(s["color"])}">'
        f'<img src="{icon}" alt="" width="20" height="20" loading="lazy" decoding="async">{escape(s["name"])}</button>'
    )


def dashboard(sites):
    by_key = {s["key"]: s for s in sites}
    by_key["netaful"] = NETAFUL
    chips = "\n".join(chip(src, by_key[key]) for src, key in CHIPS)
    feeds = escape(json.dumps(FEEDS), quote=True)
    return f"""<div id="view-dash" role="tabpanel" aria-labelledby="tab-dash" data-feeds="{feeds}" data-wp="{escape(NETAFUL_WP, quote=True)}" hidden>
<h2 class="dash-h">ポチフルディスカバー</h2>
<div class="pf-chips" role="group" aria-label="表示するポチ">
{chips}
</div>
<p class="dash-status" id="dash-status" role="status" hidden></p>
<ul class="dash-list" id="dash-list"></ul>
</div>
"""


def build_index(sites):
    n = len(sites)
    desc = f"ネタフルのポチシリーズ全{n}サイトをまとめて見られる一覧ページ。旅・おでかけ、セール・買い物、食べ物・新発売、マンガのポチをここから探せます。"
    ld = [
        {"@context": "https://schema.org", "@type": "WebSite", "name": NAME, "url": BASE},
        {
            "@context": "https://schema.org", "@type": "ItemList", "name": "ポチシリーズ一覧",
            "numberOfItems": n,
            "itemListElement": [
                {"@type": "ListItem", "position": i, "url": s["url"], "name": s["name"]}
                for i, s in enumerate(sites, 1)
            ],
        },
    ]
    extra = "".join(
        f'<script type="application/ld+json">{json.dumps(d, ensure_ascii=False, separators=(",", ":"))}</script>\n'
        for d in ld
    )
    parts = [head(TITLE, desc, BASE, extra), header("h1").replace("{n}", str(n)), "<main>\n", TABS,
             '<div id="view-links" role="tabpanel" aria-labelledby="tab-links">\n']
    for g, items in groups(sites):
        parts.append(f'<section><h2>{escape(g)}</h2><ul class="pf-cards">\n')
        parts.extend(card(s) + "\n" for s in items)
        parts.append("</ul></section>\n")
    parts.append("</div>\n" + dashboard(sites))
    parts.append("</main>\n" + FOOTER.replace("</body>", '<script src="/static/dashboard.js" defer></script>\n</body>'))
    return "".join(parts)


def build_404(n):
    parts = [
        head("ページが見つかりません｜ポチフル", "お探しのページは見つかりませんでした。", BASE + "404.html",
             '<meta name="robots" content="noindex">\n'),
        header("div").replace("{n}", str(n)),
        '<main>\n<h2>ページが見つかりません</h2>\n<p>お探しのページは見つかりませんでした。<a href="/">ポチフルのトップ</a>から、ポチシリーズの一覧をご覧ください。</p>\n</main>\n',
        FOOTER,
    ]
    return "".join(parts)


def main():
    sites = load_sites()
    (DOCS / "static/icons").mkdir(parents=True, exist_ok=True)
    for s in sites:
        src = SITE_ROOT / s["icon"] if s.get("icon") else BRANDING_BUILD / s["key"] / "logo.png"
        if not src.exists():
            sys.exit(f"アイコンがありません: {src}（pochi-branding で作ってから再実行）")
        shutil.copy2(src, DOCS / f"static/icons/{s['key']}.png")
    shutil.copy2(ROOT / "static/style.css", DOCS / "static/style.css")
    shutil.copy2(ROOT / "static/dashboard.js", DOCS / "static/dashboard.js")
    (DOCS / "index.html").write_text(build_index(sites), encoding="utf-8")
    (DOCS / "404.html").write_text(build_404(len(sites)), encoding="utf-8")
    (DOCS / "robots.txt").write_text(f"User-agent: *\nAllow: /\n\nSitemap: {BASE}sitemap.xml\n", encoding="utf-8")
    (DOCS / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f"<url><loc>{BASE}</loc></url>\n</urlset>\n", encoding="utf-8")
    print(f"built {len(sites)} sites -> {DOCS}")


if __name__ == "__main__":
    main()

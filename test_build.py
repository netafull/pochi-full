import json
import re
import unittest
from pathlib import Path

import build

DOCS = Path(__file__).parent / "docs"
GROUPS = ["旅・おでかけ", "セール・買い物", "食べ物・新発売", "マンガ", "読みもの"]


class BuildTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        build.main()
        cls.sites = build.load_sites()
        cls.html = (DOCS / "index.html").read_text(encoding="utf-8")

    def test_count(self):
        self.assertEqual(len(self.sites), 17)
        self.assertEqual(len({s["key"] for s in self.sites}), 17)

    def test_group_order(self):
        self.assertEqual([g for g, _ in build.groups(self.sites)], GROUPS)

    def test_urls(self):
        for s in self.sites:
            self.assertRegex(s["url"], r"^https://[a-z]+\.netaful\.jp/$")

    def test_icons(self):
        for s in self.sites:
            self.assertTrue((DOCS / f"static/icons/{s['key']}.png").is_file(), s["key"])
        for f in ("logo.png", "favicon.png", "favicon.ico", "apple-touch-icon.png", "ogp.jpg"):
            self.assertTrue((DOCS / "static/assets" / f).is_file(), f)

    def test_index(self):
        for s in self.sites:
            self.assertIn(f'href="{s["url"]}"', self.html)
        self.assertEqual(len(re.findall(r'<li class="pf-card"><a href="https://', self.html)), 17)
        self.assertEqual(self.html.count("<h1"), 1)
        self.assertIn('<link rel="canonical" href="https://pochi.netaful.jp/">', self.html)

    def _display(self):
        return [s for _, items in build.groups(self.sites) for s in items]

    def _cards(self):
        return re.findall(r'<li class="pf-card">.*?</li>', self.html, re.S)

    def test_card_numbers_follow_display_order(self):
        cards = self._cards()
        self.assertEqual(len(cards), 17)
        nums = [re.search(r'<span class="pf-no">No\.(\d+)</span>', c).group(1) for c in cards]
        self.assertEqual(nums, [f"{i:02d}" for i in range(1, 18)])
        for c, s in zip(cards, self._display()):
            self.assertIn(f'href="{s["url"]}"', c)
        self.assertIn('href="https://michinoeki.netaful.jp/"', cards[0])
        self.assertIn("No.01", cards[0])
        self.assertIn('href="https://news.netaful.jp/"', cards[-1])
        self.assertIn("No.17", cards[-1])

    def test_card_domain_and_a11y(self):
        for c, s in zip(self._cards(), self._display()):
            host = s["url"].split("//")[1].rstrip("/")
            self.assertIn(f'<span class="pf-host">{host}</span>', c)
            # 番号とアイコンのスタブは読み上げ対象外 → アクセシブルネームはサイト名から始まる
            self.assertIn('<span class="pf-stub" aria-hidden="true">', c)
            self.assertNotIn("No.", c.split('<span class="pf-body">')[1])

    def test_card_css_has_no_left_accent(self):
        css = (Path(__file__).parent / "static/style.css").read_text(encoding="utf-8")
        for rule in re.findall(r"\.pf-card[^{]*\{[^}]*\}", css):
            self.assertNotIn("border-left", rule)

    def test_dashboard_markup_unchanged(self):
        self.assertIn('<ul class="dash-list" id="dash-list"></ul>', self.html)
        self.assertEqual(self.html.count('class="pf-chip"'), 12)
        self.assertIn('<h2 class="dash-h">ポチフルディスカバー</h2>', self.html)

    def test_jsonld(self):
        blocks = re.findall(r'<script type="application/ld\+json">(.*?)</script>', self.html, re.S)
        data = [json.loads(b) for b in blocks]
        self.assertEqual({d["@type"] for d in data}, {"WebSite", "ItemList"})
        items = next(d for d in data if d["@type"] == "ItemList")["itemListElement"]
        self.assertEqual(len(items), 17)
        self.assertTrue(all(i["url"] and i["name"] for i in items))


if __name__ == "__main__":
    unittest.main()

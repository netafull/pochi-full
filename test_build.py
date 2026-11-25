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

    def test_cards_follow_display_order_with_tilt_cycle(self):
        cards = self._cards()
        self.assertEqual(len(cards), 17)
        for c, s in zip(cards, self._display()):
            self.assertIn(f'href="{s["url"]}"', c)
        self.assertIn('href="https://michinoeki.netaful.jp/"', cards[0])
        self.assertIn('href="https://news.netaful.jp/"', cards[-1])
        tilts = [re.search(r"--tilt:([^;\"]+)", c).group(1) for c in cards]
        cycle = ["-5deg", "4deg", "-3deg"]
        self.assertEqual(tilts, [cycle[i % 3] for i in range(17)])
        self.assertEqual(tilts[:4], ["-5deg", "4deg", "-3deg", "-5deg"])

    def test_no_coupon_remains(self):
        for c in self._cards():
            for word in ("No.", "pf-stub", "pf-host", "pf-no", "dashed", "aria-hidden"):
                self.assertNotIn(word, c)
            self.assertIn('alt=""', c)
        css = (Path(__file__).parent / "static/style.css").read_text(encoding="utf-8")
        for rule in re.findall(r"\.pf-[a-z]*[^{]*\{[^}]*\}", css):
            if ".pf-card" in rule or ".pf-stub" in rule or ".pf-no" in rule or ".pf-host" in rule:
                for word in ("dashed", "dotted", "color-mix", "pf-stub", "pf-host", "pf-no", "border-left"):
                    self.assertNotIn(word, rule)
        self.assertNotIn("pf-stub", css)

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

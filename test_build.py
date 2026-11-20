import json
import re
import unittest
from pathlib import Path

import build

DOCS = Path(__file__).parent / "docs"
GROUPS = ["旅・おでかけ", "セール・買い物", "食べ物・新発売", "マンガ"]


class BuildTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        build.main()
        cls.sites = build.load_sites()
        cls.html = (DOCS / "index.html").read_text(encoding="utf-8")

    def test_count(self):
        self.assertEqual(len(self.sites), 15)
        self.assertEqual(len({s["key"] for s in self.sites}), 15)

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
        self.assertEqual(len(re.findall(r'<li class="pf-card"><a href="https://', self.html)), 15)
        self.assertEqual(self.html.count("<h1"), 1)
        self.assertIn('<link rel="canonical" href="https://pochi.netaful.jp/">', self.html)

    def test_jsonld(self):
        blocks = re.findall(r'<script type="application/ld\+json">(.*?)</script>', self.html, re.S)
        data = [json.loads(b) for b in blocks]
        self.assertEqual({d["@type"] for d in data}, {"WebSite", "ItemList"})
        items = next(d for d in data if d["@type"] == "ItemList")["itemListElement"]
        self.assertEqual(len(items), 15)
        self.assertTrue(all(i["url"] and i["name"] for i in items))


if __name__ == "__main__":
    unittest.main()

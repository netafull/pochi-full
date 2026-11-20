"""ダッシュボードの検証。HTML は build の出力を見る。JSの混ぜ方・3日切り・分散は macOS の osascript(JXA) で実行する（node 不要）。
osascript が無い環境ではJSのテストをスキップする（その場合は手元ブラウザで確認）。"""
import json
import re
import shutil
import subprocess
import unittest
from pathlib import Path

import build

ROOT = Path(__file__).parent
JS = ROOT / "static/dashboard.js"

RUNNER = r"""
ObjC.import('Foundation');
function readFile(p){ return ObjC.unwrap($.NSString.stringWithContentsOfFileEncodingError($(p), $.NSUTF8StringEncoding, null)); }
var args = $.NSProcessInfo.processInfo.arguments;
var jsPath = ObjC.unwrap(args.objectAtIndex(args.count - 2));
var casePath = ObjC.unwrap(args.objectAtIndex(args.count - 1));
var D = eval(readFile(jsPath) + ";PochiDash");
var C = JSON.parse(readFile(casePath));
var out = {
  today: D.jstToday(C.nowMs),
  mixed: D.mix(C.feeds, C.today).map(function (i) { return i.id; }),
  spread: D.spread(C.seq).map(function (i) { return i.id; }),
  visible: D.visible(C.seq, C.off).map(function (i) { return i.id; })
};
JSON.stringify(out);
"""


def run_js(case, tmp):
    runner = tmp / "runner.js"
    runner.write_text(RUNNER, encoding="utf-8")
    cf = tmp / "case.json"
    cf.write_text(json.dumps(case), encoding="utf-8")
    r = subprocess.run(["osascript", "-l", "JavaScript", str(runner), str(JS), str(cf)],
                       capture_output=True, text=True, timeout=60)
    if r.returncode != 0:
        raise RuntimeError(r.stderr)
    return json.loads(r.stdout.strip())


def it(id_, source, date, **kw):
    return {"id": id_, "title": id_, "url": "https://example.com/" + id_, "date": date, "source": source,
            "source_name": source, **kw}


class HtmlTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        build.main()
        cls.html = (ROOT / "docs/index.html").read_text(encoding="utf-8")

    def test_tabs_and_panels(self):
        h = self.html
        self.assertIn('role="tablist"', h)
        self.assertEqual(len(re.findall(r'role="tab"', h)), 2)
        self.assertIn('id="view-links"', h)
        self.assertIn('id="view-dash"', h)
        self.assertTrue((ROOT / "docs/static/dashboard.js").is_file())

    def test_chips(self):
        chips = re.findall(r'class="pf-chip" data-source="([a-z]+)"', self.html)
        self.assertEqual(chips, ["shinkan", "conbini", "fastfood", "cafe", "sushi", "cupmen", "book", "kaden", "apple"])

    def test_feeds(self):
        m = re.search(r'data-feeds="([^"]+)"', self.html)
        feeds = json.loads(m[1].replace("&quot;", '"'))
        self.assertEqual(len(feeds), 5)
        self.assertTrue(all(re.match(r"^https://[a-z]+\.netaful\.jp/feed\.json$", f) for f in feeds))

    def test_links_view_unchanged_markup(self):
        # リンク集のカード・見出しは従来どおり（グループ4つ、カード15）
        panel = self.html.split('id="view-links"')[1].split('id="view-dash"')[0]
        self.assertEqual(panel.count("<h2>"), 4)
        self.assertEqual(panel.count('<li class="pf-card">'), 15)

    def test_404_has_no_dashboard(self):
        self.assertNotIn("dashboard.js", (ROOT / "docs/404.html").read_text(encoding="utf-8"))

    def test_fixtures_valid(self):
        for f in (ROOT / "fixtures").glob("*.json"):
            d = json.loads(f.read_text(encoding="utf-8"))
            self.assertEqual(d["version"], 1)
            ids = [i["id"] for i in d["items"]]
            self.assertEqual(len(ids), len(set(ids)) if f.stem != "book" else len(ids))


@unittest.skipUnless(shutil.which("osascript"), "osascript が無いのでJSのロジックは未検証")
class LogicTest(unittest.TestCase):
    def setUp(self):
        import tempfile
        self._t = tempfile.TemporaryDirectory()
        self.tmp = Path(self._t.name)
        self.addCleanup(self._t.cleanup)

    def run_case(self, **kw):
        base = {"nowMs": 0, "today": "2026-11-20", "feeds": [], "seq": [], "off": []}
        base.update(kw)
        return run_js(base, self.tmp)

    def test_jst_today(self):
        # 2026-11-19T15:00:00Z = JST 11-20 00:00
        ms = 1795100400000
        self.assertEqual(self.run_case(nowMs=ms)["today"], "2026-11-20")
        self.assertEqual(self.run_case(nowMs=ms - 1)["today"], "2026-11-19")

    def test_mix_sort_cutoff_dedup(self):
        f1 = {"generated": "2026-11-20T05:00:00+09:00", "items": [
            it("a1", "a", "2026-11-20"), it("a2", "a", "2026-11-17"), it("a3", "a", "2026-11-16"),
            it("fut", "a", "2026-11-21"), {"id": "bad", "title": "no url", "date": "2026-11-20", "source": "a"}]}
        f2 = {"generated": "2026-11-20T09:00:00+09:00", "items": [
            it("b1", "b", "2026-11-20"), it("a1", "b", "2026-11-20"), it("old", "b", "2026-11-01")]}
        r = self.run_case(feeds=[f1, f2])["mixed"]
        # 未来が先頭、同日は generated が新しい feed が先、重複a1は最初のものだけ、3日より古い(11-16, 11-01)は捨てる
        self.assertEqual(r, ["fut", "b1", "a1", "a2"])

    def test_spread(self):
        seq = [it(f"x{i}", "x", "2026-11-20") for i in range(1, 5)] + [it("y1", "y", "2026-11-20"), it("z1", "z", "2026-11-20")]
        r = self.run_case(seq=seq)["spread"]
        src = {i["id"]: i["source"] for i in seq}
        s = [src[i] for i in r]
        for i in range(2, len(s)):
            self.assertFalse(s[i] == s[i - 1] == s[i - 2], s)
        self.assertEqual(sorted(r), sorted(src))

    def test_spread_impossible_keeps_all(self):
        seq = [it(f"x{i}", "x", "2026-11-20") for i in range(5)]
        self.assertEqual(self.run_case(seq=seq)["spread"], [f"x{i}" for i in range(5)])

    def test_visible_filter(self):
        seq = [it("a", "a", "2026-11-20"), it("b", "b", "2026-11-20"), it("c", "c", "2026-11-20")]
        self.assertEqual(self.run_case(seq=seq, off=["b"])["visible"], ["a", "c"])
        self.assertEqual(self.run_case(seq=seq, off=["a", "b", "c"])["visible"], [])


if __name__ == "__main__":
    unittest.main()

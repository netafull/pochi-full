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
  visible: D.visible(C.seq, C.off).map(function (i) { return i.id; }),
  wp: D.fromWp(C.wp),
  decoded: (C.titles || []).map(function (t) { return D.decodeTitle(t); })
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
        self.assertEqual(chips, ["shinkan", "conbini", "fastfood", "cafe", "sushi", "cupmen", "book", "kaden", "apple",
                                 "netaful", "manga"])
        self.assertNotIn('data-source="michinoeki"', self.html)  # 道の駅ポチはディスカバーから外した（オーナー決定 2026-11-21）
        for k in ("netaful", "manga"):  # 新しいものも既定でオン
            self.assertRegex(self.html, rf'data-source="{k}"[^>]*aria-pressed="true"')

    def test_heading_and_wp_url(self):
        self.assertIn('<h2 class="dash-h">ポチフルディスカバー</h2>', self.html)
        self.assertNotIn("最近の新着", self.html)
        self.assertIn("https://netaful.jp/wp-json/wp/v2/posts?tags=728&amp;per_page=20", self.html)

    def test_fallback_logos_exist(self):
        for k in ("manga",):
            self.assertIn(f'data-source="{k}"', self.html)
            self.assertIn(f'data-icon="/static/icons/{k}.png"', self.html)
            self.assertTrue((ROOT / f"docs/static/icons/{k}.png").is_file())

    def test_feeds(self):
        m = re.search(r'data-feeds="([^"]+)"', self.html)
        feeds = json.loads(m[1].replace("&quot;", '"'))
        self.assertEqual(len(feeds), 6)
        self.assertIn("https://manga.netaful.jp/feed.json", feeds)
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
            if f.stem == "netaful":  # WordPress REST の配列（feed ではない）
                self.assertIsInstance(d, list)
                continue
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
        base = {"nowMs": 0, "today": "2026-11-20", "feeds": [], "seq": [], "off": [], "wp": [], "titles": []}
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
        # 未来が先頭、同日は source を順番に1枚ずつ（a→b）、重複a1は最初のものだけ、3日より古い(11-16, 11-01)は捨てる
        self.assertEqual(r, ["fut", "b1", "a1", "a2"])  # 今日・未来は同じ帯で巡回（a の中は新しい順）

    def test_mix_round_robin_same_date(self):
        # 同じ日は source を固定順（チップ順: shinkan, book, kaden, apple）に1枚ずつ。各 source 内は元の順。feed の generated は関係ない
        late = {"generated": "2026-11-20T09:00:00+09:00", "items": [
            it("k1", "kaden", "2026-11-20"), it("k2", "kaden", "2026-11-20"), it("p1", "apple", "2026-11-20")]}
        early = {"generated": "2026-11-20T05:00:00+09:00", "items": [
            it("s1", "shinkan", "2026-11-20"), it("s2", "shinkan", "2026-11-20"), it("s3", "shinkan", "2026-11-20"),
            it("b1", "book", "2026-11-20")]}
        r = self.run_case(feeds=[late, early])["mixed"]
        self.assertEqual(r, ["s1", "b1", "k1", "p1", "s2", "k2", "s3"])
        self.assertEqual(r, self.run_case(feeds=[early, late])["mixed"])  # feed の順を入れ替えても同じ

    def test_mix_date_beats_round_robin(self):
        f = {"generated": "2026-11-20T05:00:00+09:00", "items": [
            it("s_old", "shinkan", "2026-11-19"), it("s_new", "shinkan", "2026-11-20"), it("s_new2", "shinkan", "2026-11-20"),
            it("c_old", "conbini", "2026-11-18"), it("c_new", "conbini", "2026-11-20")]}
        r = self.run_case(feeds=[f])["mixed"]
        self.assertEqual(r, ["s_new", "c_new", "s_new2", "s_old", "c_old"])

    def test_mix_caps_with_round_robin(self):
        # 上限は「新しいほうから6件」を先に決め、その6件を巡回に回す（古い日の枠を新しい日が取る）
        k = [it(f"k{i}", "kaden", "2026-11-20" if i < 2 else "2026-11-19") for i in range(10)]
        s = [it(f"s{i}", "shinkan", "2026-11-19") for i in range(3)]
        r = self.run_case(feeds=[{"generated": "", "items": k + s}])["mixed"]
        self.assertEqual([x for x in r if x.startswith("k")], [f"k{i}" for i in range(6)])
        self.assertEqual(r, ["s0", "k0", "s1", "k1", "s2", "k2", "k3", "k4", "k5"])  # 今日と昨日は同じ帯

    def test_mix_band_two_days(self):
        # 今日・昨日は1つの帯で巡回、2〜3日前は次の帯（帯どうしは新しい順）
        f = {"generated": "", "items": [
            it("c1", "conbini", "2026-11-20"), it("c2", "conbini", "2026-11-20"), it("c3", "conbini", "2026-11-19"),
            it("s1", "shinkan", "2026-11-19"), it("c4", "conbini", "2026-11-18"), it("s2", "shinkan", "2026-11-17")]}
        r = self.run_case(feeds=[f])["mixed"]
        self.assertEqual(r, ["s1", "c1", "c2", "c3", "s2", "c4"])

    def test_mix_caps_manga(self):
        m = [it(f"m{i}", "manga", "2026-11-20") for i in range(8)]
        r = self.run_case(feeds=[{"generated": "", "items": m}])["mixed"]
        self.assertEqual(r, ["m0", "m1", "m2"])

    def test_mix_caps_kaden_apple(self):
        # 家電・林檎は新しいほうから6件まで。他の source は上限なし
        k = [it(f"k{i}", "kaden", "2026-11-20" if i < 4 else "2026-11-19") for i in range(10)]
        a = [it(f"p{i}", "apple", "2026-11-20") for i in range(8)]
        s = [it(f"s{i}", "shinkan", "2026-11-20") for i in range(9)]
        f = {"generated": "2026-11-20T05:00:00+09:00", "items": k + a + s}
        r = self.run_case(feeds=[f])["mixed"]
        self.assertEqual([x for x in r if x.startswith("k")], [f"k{i}" for i in range(6)])
        self.assertEqual([x for x in r if x.startswith("p")], [f"p{i}" for i in range(6)])
        self.assertEqual(len([x for x in r if x.startswith("s")]), 9)

    def test_netaful_wp_conversion(self):
        posts = [
            {"id": 7, "date": "2026-11-20T07:30:12", "link": "https://netaful.jp/archives/7",
             "title": {"rendered": "A &#8211; B &#038; C &amp; D &#8217;E&#8217; &lt;b&gt; &hellip; &#x1F363;"},
             "jetpack_featured_media_url": "https://netaful.jp/wp-content/x.jpg"},
            {"id": 8, "date": "2026-11-19T23:59:59", "link": "https://netaful.jp/archives/8",
             "title": {"rendered": "<em>画像</em>なし"}, "jetpack_featured_media_url": ""},
            {"id": 9, "date": "2026-11-19T00:00:00", "link": "javascript:alert(1)", "title": {"rendered": "壊れ"}},
            {"id": 10, "date": "2026-11-19T00:00:00", "link": "https://netaful.jp/archives/10", "title": {"rendered": ""}},
        ]
        f = self.run_case(wp=posts)["wp"]
        self.assertEqual((f["site"], f["site_name"], f["version"]), ("netaful", "ネタフル", 1))
        self.assertEqual(len(f["items"]), 2)  # http でない link と空タイトルは捨てる
        a, b = f["items"]
        self.assertEqual(a, {"id": "netaful:7", "title": "A \u2013 B & C & D \u2019E\u2019 <b> \u2026 \U0001F363",
                             "url": "https://netaful.jp/archives/7", "date": "2026-11-20", "source": "netaful",
                             "source_name": "ネタフル", "image": "https://netaful.jp/wp-content/x.jpg"})
        self.assertNotIn("image_link", a)
        self.assertEqual(b["title"], "画像なし")
        self.assertNotIn("image", b)
        self.assertEqual(b["date"], "2026-11-19")
        # 変換後の feed はそのまま mix に流せる
        m = self.run_case(feeds=[f], today="2026-11-20")["mixed"]
        self.assertEqual(m, ["netaful:7", "netaful:8"])

    def test_decode_title_single_pass(self):
        r = self.run_case(titles=["&amp;lt;", "&#0;&#xD800;&unknown;", "a  b\n"])["decoded"]
        self.assertEqual(r, ["&lt;", "&#0;&#xD800;&unknown;", "a b"])

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

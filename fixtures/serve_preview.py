#!/usr/bin/env python3
"""手元確認用。docs/ を配信し、index.html 内の feed URL を fixtures/<site>.json に差し替える。
fixtures の {D+n} は今日(JST)からn日後の日付に置き換える。 実行: python3 fixtures/serve_preview.py  → http://localhost:8765/"""
import re
from datetime import datetime, timedelta, timezone
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HERE = Path(__file__).parent
DOCS = HERE.parent / "docs"


def fill(text):
    today = datetime.now(timezone(timedelta(hours=9))).date()
    return re.sub(r"\{D([+-]\d+)\}", lambda m: (today + timedelta(days=int(m[1]))).isoformat(), text)


class H(SimpleHTTPRequestHandler):
    def __init__(self, *a, **k):
        super().__init__(*a, directory=str(DOCS), **k)

    def do_GET(self):
        p = self.path.split("?")[0]
        if p.startswith("/fixtures/"):
            body = fill((HERE / Path(p).name).read_text(encoding="utf-8")).encode()
            ctype = "application/json"
        elif p in ("/", "/index.html"):
            html = (DOCS / "index.html").read_text(encoding="utf-8")
            html = re.sub(r"https://([a-z]+)\.netaful\.jp/feed\.json", r"/fixtures/\1.json", html)
            # ネタフルの WordPress REST（data-wp）も fixtures/netaful.json に差し替える
            html = re.sub(r"https://netaful\.jp/wp-json/wp/v2/posts\?[^\"]*", "/fixtures/netaful.json", html)
            body = html.encode()
            ctype = "text/html; charset=utf-8"
        else:
            return super().do_GET()
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


if __name__ == "__main__":
    ThreadingHTTPServer(("127.0.0.1", 8765), H).serve_forever()

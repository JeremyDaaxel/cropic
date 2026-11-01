import json
import os
import sys
import threading
import webbrowser
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

import os as _os
_os.environ.setdefault("CROPIC_PREFS",
                       _os.path.join(_os.path.dirname(_os.path.abspath(__file__)),
                                     "prefs-pruebas.json"))

from app import Api

BASE = os.path.dirname(os.path.abspath(__file__))
UI_DIR = os.path.join(BASE, "ui")
api = Api()


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=UI_DIR, **kw)

    def end_headers(self):
        self.send_header("Cache-Control", "no-store, must-revalidate")
        super().end_headers()

    def log_message(self, fmt, *args):
        msg = fmt % args
        if " 404 " in msg or " 500 " in msg:
            print("  !", msg)

    def do_POST(self):
        if not self.path.startswith("/api/"):
            self.send_error(404)
            return
        method = self.path[5:]
        fn = getattr(api, method, None)
        if fn is None or method.startswith("_"):
            self.send_error(404, "metodo desconocido")
            return
        length = int(self.headers.get("Content-Length", 0))
        args = json.loads(self.rfile.read(length) or "[]")
        try:
            result = fn(*args)
        except Exception as exc:
            result = {"ok": False, "error": str(exc)}
        body = json.dumps(result).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8770
    srv = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    url = f"http://127.0.0.1:{port}/index.html?web=1"
    print(f"Cropic en {url}  (Ctrl+C para parar)")
    if "--no-browser" not in sys.argv:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    srv.serve_forever()


if __name__ == "__main__":
    main()

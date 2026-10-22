"""Persistent local inference worker.

Keeps SegFormer / pose / FashionCLIP loaded between requests so ingest is
seconds, not a cold model load per photo. Local-only (binds 127.0.0.1);
the Express API is the only client.

  POST /ingest   {"image": path, "out": dir, "closet": [...]} -> IngestResult
  POST /relabel  {category, type, color, lab, pattern, sleeve, neckline}
                 -> {name, description, formality, color}
  GET  /health   -> {"ok": true}

/relabel is the naming half of the pipeline on its own: the VLM labeller in
the Express API sends back the attributes it read off the cutout and gets
the bilingual name, formality and template description for them — so the
i18n tables stay in one place, here.
"""
import json
import sys
import threading
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from . import s4_color, s4_formality, s5_naming
from .run import process

PORT = 5055
_LOCK = threading.Lock()   # one inference at a time (spec §9: no parallel inference)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):  # quiet
        pass

    def _send(self, code, obj):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/health":
            return self._send(200, {"ok": True})
        self._send(404, {"error": "not_found"})

    def do_POST(self):
        if self.path not in ("/ingest", "/relabel"):
            return self._send(404, {"error": "not_found"})
        try:
            n = int(self.headers.get("Content-Length", 0))
            req = json.loads(self.rfile.read(n))
            if self.path == "/relabel":
                return self._send(200, relabel(req))
            with _LOCK:
                result = process(req["image"], req["out"], use_clip=True,
                                 closet=req.get("closet") or None)
            self._send(200, result)
        except Exception:
            traceback.print_exc()
            self._send(500, {"error": "pipeline_failed"})


def relabel(req: dict) -> dict:
    """Name + formality for attributes somebody else read off the cutout."""
    category = req.get("category", "top")
    type_val = req.get("type")
    pattern = req.get("pattern")
    pattern = pattern if pattern and pattern not in ("solid", "unknown") else None

    entry = s4_color.resolve_named(req.get("color"), req.get("lab")) \
        or s4_color.palette_entry("grey")
    color = {
        "name": {"en": entry["en"], "ar": entry["ar"], "key": entry["key"]},
        "hex": entry["hex"],
        "lab": req.get("lab") or entry["lab"],
    }

    formality = s4_formality.formality(type_val or "", pattern)
    gen = s5_naming.generate(
        garment_type=type_val if type_val and type_val != "unknown" else category,
        category=category, color=color,
        neckline=req.get("neckline"), sleeve=req.get("sleeve"),
        pattern=pattern, formality=formality,
        temp_id=req.get("tempId", ""))
    return {"name": gen["name"], "description": gen["description"],
            "formality": formality, "color": color}


def main():
    # inference is not thread-safe across models; serialize requests
    server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    print(f"worker ready on 127.0.0.1:{PORT}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Local stand-ins used ONLY for testing the n8n workflow offline:
  POST /slack                          -> records the approval message (stands in for a Slack incoming webhook)
  POST /forms/chromium/convert/html    -> HTML->PDF via LibreOffice headless (stands in for Gotenberg)
  POST /v1/messages                    -> canned Anthropic Messages API reply (verifies request shape; NOT a real model)
  POST /log                            -> records the log row (stands in for Airtable/Sheets)
"""
import json, os, subprocess, sys, tempfile
from email.parser import BytesParser
from email.policy import default as _pol
from http.server import BaseHTTPRequestHandler, HTTPServer

OUT = sys.argv[1] if len(sys.argv) > 1 else "./stub_out"
os.makedirs(OUT, exist_ok=True)

class H(BaseHTTPRequestHandler):
    def _append(self, name, obj):
        with open(os.path.join(OUT, name), "a") as f:
            f.write(json.dumps(obj) + "\n")

    def do_POST(self):
        n = int(self.headers.get("content-length", 0))
        if self.path.startswith("/forms/chromium/convert/html"):
            raw = self.rfile.read(n)
            msg = BytesParser(policy=_pol).parsebytes(b"Content-Type: " + self.headers["content-type"].encode() + b"\r\n\r\n" + raw)
            html = next(part.get_payload(decode=True) for part in msg.iter_parts() if part.get_param("name", header="content-disposition") == "files")
            d = tempfile.mkdtemp()
            p = os.path.join(d, "index.html")
            with open(p, "wb") as f:
                f.write(html)
            subprocess.run(["soffice", "--headless", "--convert-to", "pdf", "--outdir", d, p],
                           check=True, capture_output=True, timeout=120)
            pdf = open(os.path.join(d, "index.pdf"), "rb").read()
            self.send_response(200)
            self.send_header("content-type", "application/pdf")
            self.send_header("content-length", str(len(pdf)))
            self.end_headers()
            self.wfile.write(pdf)
            return
        body = self.rfile.read(n).decode()
        if self.path.startswith("/v1/messages"):
            req = json.loads(body)
            self._append("anthropic_requests.jsonl", {"headers": {k: (v if k.lower() != "x-api-key" else "<redacted, present>") for k, v in self.headers.items()}, "body": req})
            reply = {"category": "Service call - refrigeration fault", "secondary_category": "Quote request - maintenance plan",
                     "priority": "URGENT", "priority_reason": "'stopped holding temp', 'reading 9 degrees', function Thursday for 60 people",
                     "summary": "Cool room not holding temperature (9C) ahead of a 60-person function on Thursday; also wants a maintenance-plan quote.",
                     "extracted_facts": ["Cool room reading 9 degrees", "Function Thursday, 60 people", "Last serviced in March"],
                     "missing_info": ["Site address", "Cool room make/model", "After-hours access"],
                     "draft_reply": "Hi Marie - understood on the urgency with Thursday's function. We'll call you this morning to book a technician within 24 hours. Could you reply with your site address, the cool room make/model and whether after-hours access is possible? We'll prepare a maintenance-plan quote alongside the repair. Kind regards, [Operator name]",
                     "confidence": 0.86}
            out = json.dumps({"id": "msg_stub", "type": "message", "role": "assistant", "model": req.get("model"),
                              "content": [{"type": "text", "text": "```json\n" + json.dumps(reply) + "\n```"}],
                              "stop_reason": "end_turn", "usage": {"input_tokens": 0, "output_tokens": 0}}).encode()
            self.send_response(200); self.send_header("content-type", "application/json"); self.end_headers(); self.wfile.write(out)
            return
        try:
            obj = json.loads(body)
        except Exception:
            obj = {"raw": body}
        self._append("slack.jsonl" if self.path.startswith("/slack") else "log.jsonl", obj)
        self.send_response(200)
        self.send_header("content-type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"ok":true}')

    def log_message(self, *a):
        pass

HTTPServer(("127.0.0.1", 5679), H).serve_forever()

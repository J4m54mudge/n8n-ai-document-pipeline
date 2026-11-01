# Test report: AI Document Pipeline with Human Approval
Run date: 2026-10-25 · Environment: n8n **1.123.0** (npm install, SQLite, Linux container), Node 22 · Tester: Claude, preparing the piece for Jordan

## Method
1. Generated the workflow from `gen_workflow.py`. Imported it with `n8n import:workflow`, saved it, and activated it through the n8n REST API.
2. Pointed the external dependencies at `test_harness_stub_server.py` on 127.0.0.1:5679:
   - `/slack` records the approval message (stand-in for a Slack incoming webhook)
   - `/forms/chromium/convert/html` turns HTML into PDF with LibreOffice headless (stand-in for Gotenberg)
   - `/v1/messages` returns a fixed Anthropic-style reply and records the request (stand-in for the API; **not a model**)
   - `/log` records the log row (stand-in for Sheets/Airtable)
3. Drove it with curl, clicking the approve/reject links by calling the Wait node's resume URL.

## Results
| # | Path | Input | Result |
|---|---|---|---|
| 1 | Webhook → **mock** LLM → approval → **approve** → HTML → PDF → save → log (webhook target) | `sample/sample_input.json` | PASS. Execution `success`; PDF written; log row `decision=APPROVE` |
| 2 | **Form Trigger** (multipart POST to `/form/intake`) → mock LLM → approval → **reject** → log | Made-up quote request | PASS. Execution `success`; no PDF; log row `decision=REJECT`, `pdf_path` empty |
| 3 | Webhook → **live** Claude HTTP node (URL pointed at the stand-in) → parse (fenced JSON) → approve → PDF → log | `sample/sample_input.json` | PASS. Request carried `x-api-key` (from the credential), `anthropic-version: 2023-06-01` and a valid Messages body (`sample/sample_claude_request.json`). The fenced JSON reply parsed; PDF and log correct |
| 4 | Re-import of the final exported JSON into the same instance | n/a | PASS (structural import OK) |

## Not tested
- The real Anthropic API (no key available here). The prompt's real-world extraction quality is **unmeasured**.
- Real Slack, Google Sheets OAuth append, real Gotenberg (Chromium rendering differs from the LibreOffice stand-in; the band header draws better in Chromium), and the IMAP trigger.
- The 72-hour expiry path (the Wait timeout). The logic exists (`Resolve Decision` → `expired`), but it was not run.
- The malformed-model-output → `REVIEW` flag path was not exercised with a bad reply.
- n8n 2.x. The env-var defaults in **Config** need `N8N_BLOCK_ENV_ACCESS_IN_NODE=false` there.

## Install note
On this network `npm install n8n` failed fetching `xlsx` from cdn.sheetjs.com (403). I installed it with an npm `overrides` entry pinning `xlsx` to the npm-registry version 0.18.5. That's fine for testing; on a normal machine `npx n8n` or Docker needs no workaround.

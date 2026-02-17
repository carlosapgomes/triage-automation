# Runtime Smoke Runbook

This runbook validates local runtime readiness before manual end-to-end testing.
It does not change workflow behavior; it only verifies that runtime processes,
database migrations, webhook authentication, and deterministic LLM execution are
working in a reproducible way.

## Decision Path Notice

- standard Room-2 decisions use Matrix structured replies.
- `/callbacks/triage-decision` is an emergency-only compatibility path.
- Callback compatibility is marked for near-term deprecation.

## Local UV Runtime Smoke

1. Prepare dependencies and env:

```bash
uv sync
cp .env.example .env
```

2. Start only Postgres:

```bash
docker compose up -d postgres
```

3. Apply migrations:

```bash
uv run alembic upgrade head
```

4. Start runtime processes in separate terminals:

```bash
uv run uvicorn apps.bot_api.main:create_app --factory --host 0.0.0.0 --port 8000
```

```bash
uv run python -m apps.bot_matrix.main
```

```bash
uv run python -m apps.worker.main
```

Set `LOG_LEVEL=DEBUG` in `.env` when you need heartbeat-style runtime traces.
At `INFO`, logs show startup and meaningful routed/claimed job activity.

5. Check API reachability:

```bash
curl -i http://127.0.0.1:8000/openapi.json
```

## Webhook HMAC Validation (Local)

1. Create a deterministic callback payload:

```bash
cat > /tmp/triage_callback.json <<'JSON'
{"case_id":"11111111-1111-1111-1111-111111111111","doctor_user_id":"@doctor:example.org","decision":"deny","support_flag":"none","reason":"manual smoke"}
JSON
```

2. Generate signature using local `WEBHOOK_HMAC_SECRET`:

```bash
export WEBHOOK_HMAC_SECRET="$(rg '^WEBHOOK_HMAC_SECRET=' .env | cut -d'=' -f2-)"
export TRIAGE_SIG="$(python - <<'PY'
import hashlib
import hmac
from pathlib import Path

secret = Path(".env").read_text(encoding="utf-8")
for line in secret.splitlines():
    if line.startswith("WEBHOOK_HMAC_SECRET="):
        key = line.split("=", 1)[1].encode("utf-8")
        break
else:
    raise SystemExit("WEBHOOK_HMAC_SECRET not found in .env")

body = Path("/tmp/triage_callback.json").read_bytes()
print(hmac.new(key, body, hashlib.sha256).hexdigest())
PY
)"
```

3. Invalid signature must be rejected:

```bash
curl -i -X POST "http://127.0.0.1:8000/callbacks/triage-decision" \
  -H "content-type: application/json" \
  -H "x-signature: bad-signature" \
  --data-binary "@/tmp/triage_callback.json"
```

Expected result: `401 invalid signature`.

4. Valid signature reaches webhook handler:

```bash
curl -i -X POST "http://127.0.0.1:8000/callbacks/triage-decision" \
  -H "content-type: application/json" \
  -H "x-signature: ${TRIAGE_SIG}" \
  --data-binary "@/tmp/triage_callback.json"
```

Expected result: `404 case not found` for synthetic case IDs (reachability + auth pass).

## Cloudflare Tunnel Webhook Validation

1. Expose local `bot-api`:

```bash
cloudflared tunnel --url http://127.0.0.1:8000
```

2. Copy the generated `https://<random>.trycloudflare.com` URL and post the same
signed payload through the tunnel:

```bash
export TUNNEL_URL="https://replace-me.trycloudflare.com"
curl -i -X POST "${TUNNEL_URL}/callbacks/triage-decision" \
  -H "content-type: application/json" \
  -H "x-signature: ${TRIAGE_SIG}" \
  --data-binary "@/tmp/triage_callback.json"
```

Expected result: same behavior as local call (`404` for synthetic case ID, `401`
if signature is invalid).

## Deterministic LLM Smoke Path

Use deterministic mode when provider credentials are unavailable:

```bash
export LLM_RUNTIME_MODE=deterministic
```

In this mode, worker runtime uses deterministic LLM adapters and still executes
the LLM-dependent stages (`LLM1`/`LLM2`) and enqueue transitions without changing
triage semantics.

For provider mode, set:
- `OPENAI_API_KEY`
- `OPENAI_MODEL_LLM1`
- `OPENAI_MODEL_LLM2`

## UV and Compose Parity

Use the same entrypoint commands from `docker-compose.yml`:

```bash
docker compose up --build
docker compose logs -f bot-api bot-matrix worker
```

Compose command parity:
- `bot-api`: `uv run uvicorn apps.bot_api.main:create_app --factory --host 0.0.0.0 --port 8000`
- `bot-matrix`: `uv run python -m apps.bot_matrix.main`
- `worker`: `uv run python -m apps.worker.main`

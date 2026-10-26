#!/bin/sh
# Local test: starts a DEV server on :8019 (SQLite, or Postgres if DATABASE_URL is exported) and runs test_flows.py
cd "$(dirname "$0")"; PY=../../.venv/bin
unset GEMINI_API_KEY OPENAI_API_KEY ANTHROPIC_API_KEY LLM_API_KEY RESEND_API_KEY  # tests run in mock mode (no paid calls)
export STRIPE_WEBHOOK_SECRET=${STRIPE_WEBHOOK_SECRET:-whsec_test_local} CRON_SECRET=${CRON_SECRET:-cron_test_local} RETENTION_LOOP=0 FREE_PER_IP_DAY=${FREE_PER_IP_DAY:-500} FREE_PER_DAY_TOTAL=${FREE_PER_DAY_TOTAL:-5000}
$PY/uvicorn app:app --port ${PORT:-8019} >/tmp/aa-test-server.log 2>&1 & S=$!
sleep 3; $PY/python test_flows.py http://localhost:${PORT:-8019}; R=$?; kill $S
MOCK_GROUND_FLAKY=1 $PY/uvicorn app:app --port 8032 >/tmp/aa-test-flaky.log 2>&1 & F=$!; sleep 3; $PY/python test_approve.py http://localhost:8032 || R=1; kill $F
$PY/python test_prefill.py || R=1; exit $R

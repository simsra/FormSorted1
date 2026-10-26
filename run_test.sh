#!/bin/sh
# Local test: starts a DEV server on :8019 (SQLite, or Postgres if DATABASE_URL is exported) and runs test_flows.py
cd "$(dirname "$0")"; PY=../../.venv/bin
unset GEMINI_API_KEY OPENAI_API_KEY ANTHROPIC_API_KEY LLM_API_KEY RESEND_API_KEY  # tests run in mock mode (no paid calls)
export STRIPE_WEBHOOK_SECRET=${STRIPE_WEBHOOK_SECRET:-whsec_test_local} CRON_SECRET=${CRON_SECRET:-cron_test_local} RETENTION_LOOP=0
$PY/uvicorn app:app --port ${PORT:-8019} >/tmp/aa-test-server.log 2>&1 & S=$!
sleep 3; $PY/python test_flows.py http://localhost:${PORT:-8019}; R=$?; kill $S
$PY/python test_prefill.py || R=1; exit $R

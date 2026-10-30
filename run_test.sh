#!/bin/sh
# Local test: starts a DEV server on :8019 (SQLite, or Postgres if DATABASE_URL is exported) and runs test_flows.py
cd "$(dirname "$0")"; PY=${PY:-../../.venv/bin}
unset GEMINI_API_KEY OPENAI_API_KEY ANTHROPIC_API_KEY LLM_API_KEY RESEND_API_KEY  # tests run in mock mode (no paid calls)
export STRIPE_WEBHOOK_SECRET=${STRIPE_WEBHOOK_SECRET:-whsec_test_local} CRON_SECRET=${CRON_SECRET:-cron_test_local} RETENTION_LOOP=0 FREE_PER_IP_DAY=${FREE_PER_IP_DAY:-500} FREE_PER_DAY_TOTAL=${FREE_PER_DAY_TOTAL:-5000}
# the older tests make many orders for different people from one address: review holds are tested on their own server below
export WHOLE_FORM=${WHOLE_FORM:-0}   # the older suites test the short flow; the whole-form flow has its own server below
export FOLLOWUPS=${FOLLOWUPS:-0}   # quick checks (followups.py) are tested in test_flow_branching.py and the after-sample run; older suites expect finish -> preview
export FRAUD_MAX_NAMES=${FRAUD_MAX_NAMES:-100000} FRAUD_SIMILAR=${FRAUD_SIMILAR:-2} FRAUD_MAX_REFUSED=${FRAUD_MAX_REFUSED:-100000}
$PY/uvicorn app:app --port ${PORT:-8019} >${LOGDIR:-/tmp}/aa-test-server.log 2>&1 & S=$!
sleep 3; $PY/python test_flows.py http://localhost:${PORT:-8019}; R=$?
$PY/python test_intake.py http://localhost:${PORT:-8019} || R=1
$PY/python test_premium.py http://localhost:${PORT:-8019} || R=1
$PY/python test_bluebadge.py http://localhost:${PORT:-8019} || R=1
$PY/python test_plus_next.py http://localhost:${PORT:-8019} || R=1; kill $S
MOCK_GROUND_FLAKY=1 $PY/uvicorn app:app --port ${PORT_FLAKY:-8032} >${LOGDIR:-/tmp}/aa-test-flaky.log 2>&1 & F=$!; sleep 3; $PY/python test_approve.py http://localhost:${PORT_FLAKY:-8032} || R=1; kill $F
MOCK_GROUND_SLOW=6 $PY/uvicorn app:app --port ${PORT_SLOW:-8033} >${LOGDIR:-/tmp}/aa-test-slow.log 2>&1 & W=$!; sleep 3; $PY/python test_responsive.py http://localhost:${PORT_SLOW:-8033} || R=1; kill $W
MOCK_DRAFT_SLOW=4 MOCK_GROUND_SLOW=3 $PY/uvicorn app:app --port ${PORT_PREP:-8034} >${LOGDIR:-/tmp}/aa-test-prep.log 2>&1 & P=$!; sleep 3; $PY/python test_prepare.py http://localhost:${PORT_PREP:-8034} || R=1; kill $P
EV=${LOGDIR:-/tmp}/ev-test; rm -rf $EV; mkdir -p $EV
FRAUD_MAX_NAMES=2 FRAUD_SIMILAR=0.9 FRAUD_MAX_REFUSED=1 SQLITE_PATH=$EV/orders.db OUT_DIR=$EV/out MAIL_LOG=$EV/mail.log $PY/uvicorn app:app --port ${PORT_EV:-8035} >${LOGDIR:-/tmp}/aa-test-evidence.log 2>&1 & V=$!; sleep 3
FRAUD_MAX_NAMES=2 FRAUD_SIMILAR=0.9 FRAUD_MAX_REFUSED=1 SQLITE_PATH=$EV/orders.db MAIL_LOG=$EV/mail.log $PY/python test_evidence.py http://localhost:${PORT_EV:-8035} || R=1; kill $V
WF=${LOGDIR:-/tmp}/wf-test; rm -rf $WF; mkdir -p $WF   # whole-form flow: own SQLite + files, never a remote DB or bucket
DATABASE_URL= SUPABASE_URL= WHOLE_FORM=1 WF_LOOKUPS=0 FOLLOWUPS=1 SQLITE_PATH=$WF/orders.db OUT_DIR=$WF/out MAIL_LOG=$WF/mail.log $PY/uvicorn app:app --port ${PORT_WF:-8036} >$WF/server.log 2>&1 & X=$!; sleep 3
DATABASE_URL= SQLITE_PATH=$WF/orders.db OUT_DIR=$WF/out MAIL_LOG=$WF/mail.log WF_COVERAGE=$WF/coverage.json $PY/python test_wholeform.py http://localhost:${PORT_WF:-8036} $WF/orders.db $WF/server.log || R=1; kill $X
AC=${LOGDIR:-/tmp}/acct-test; rm -rf $AC; mkdir -p $AC   # customer accounts: own SQLite + console mail, ACCOUNTS_ENABLED only on this server
DATABASE_URL= SUPABASE_URL= ACCOUNTS_ENABLED=1 SQLITE_PATH=$AC/orders.db OUT_DIR=$AC/out MAIL_LOG=$AC/mail.log $PY/uvicorn app:app --port ${PORT_AC:-8037} >$AC/server.log 2>&1 & AS=$!
DATABASE_URL= SUPABASE_URL= SQLITE_PATH=$AC/orders.db OUT_DIR=$AC/out MAIL_LOG=$AC/mail.log $PY/uvicorn app:app --port ${PORT_AC0:-8038} >$AC/server-off.log 2>&1 & AO=$!; sleep 3
DATABASE_URL= $PY/python test_accounts.py http://localhost:${PORT_AC:-8037} $AC/orders.db $AC/mail.log http://localhost:${PORT_AC0:-8038} || R=1; kill $AS $AO
$PY/python test_prefill.py || R=1; $PY/python test_strength.py || R=1; $PY/python test_fill_gaps.py || R=1; $PY/python test_statement_ref.py || R=1; DATABASE_URL= SUPABASE_URL= $PY/python test_fallback.py || R=1; DATABASE_URL= SUPABASE_URL= $PY/python test_no_supporter_words.py || R=1; DATABASE_URL= SUPABASE_URL= $PY/python test_print_sign_post.py || R=1; $PY/python test_flow_branching.py || R=1; $PY/python test_writer.py || R=1; DATABASE_URL= SUPABASE_URL= $PY/python test_no_invent.py || R=1; exit $R

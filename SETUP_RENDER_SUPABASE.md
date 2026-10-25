# FormSorted app on Render (free) + Supabase (free)

The app keeps nothing on Render's disk: orders, answers, webhook ids and saved answers are in Supabase Postgres,
and the generated PDF/DOCX/HTML files are in a **private** Supabase Storage bucket, streamed to the customer by the app
(only after approval + details). Without these env vars the app falls back to SQLite + local files (local testing).

Free-plan facts: Render free sleeps after ~15 min idle (first request then takes ~30-60 s; Stripe retries webhooks, so
no order is lost). Supabase free pauses after 7 days without activity; the daily cron ping below prevents that.

## 1. Supabase (supabase.com, sign in, "New project")
1. Name `formsorted`, region **Central EU (Frankfurt)**, set a strong database password (save it). Create.
2. **Database URL:** top bar **Connect** -> "Connection string" -> URI -> **Transaction pooler** (port **6543**).
   Copy it and put your database password in place of `[YOUR-PASSWORD]`. Looks like
   `postgresql://postgres.abcdefgh:PASSWORD@aws-0-eu-central-1.pooler.supabase.com:6543/postgres`
   (Use the pooler, not the "Direct connection": Render can't reach the direct IPv6 address.)
3. **Project URL + service key:** Project Settings -> API (API Keys). Copy the Project URL (`https://abcdefgh.supabase.co`)
   and the **service_role** secret key (or a new "secret" key `sb_secret_...`). Never put it in the website or share it.
4. Storage bucket: nothing to do; the app creates a private bucket `orders` on first use. (Optional: Storage -> New bucket
   -> name `orders`, leave "Public" OFF.) Tables are also created automatically on first request.

## 2. Code on GitHub (Render deploys from a repo)
Push this folder (`aa-claim-service`) to a **private** GitHub repo, at the repo root. Don't commit `data/`, `out/` or keys.

## 3. Render (render.com, sign in with GitHub)
1. New -> **Blueprint** -> pick the repo. Render reads `render.yaml` (free plan, Python, Frankfurt, health check `/healthz`).
2. Fill in the secret values it asks for:

| Env var | Value |
|---|---|
| `DATABASE_URL` | Supabase Transaction pooler URI (step 1.2) |
| `SUPABASE_URL` | Supabase Project URL |
| `SUPABASE_SERVICE_KEY` | Supabase service_role / secret key |
| `ANTHROPIC_API_KEY` | Anthropic API key (drafting) |
| `OPENAI_API_KEY` | OpenAI API key (fallbacks; optional) |
| `GEMINI_API_KEY` | paid Gemini API key (fact-check; drafting fallback) |
| `STRIPE_SECRET_KEY` | Stripe secret or restricted key (`sk_test_`/`rk_test_` now, live later) |
| `STRIPE_WEBHOOK_SECRET` | `whsec_...` from step 4 (put a placeholder first, update after) |
| `RESEND_API_KEY` | Resend API key (`re_...`) |
| `PUBLIC_URL` | `https://formsorted-app.onrender.com` for now (later `https://app.formsorted.com`) |

   Already set by render.yaml: `BRAND`, `MAIL_BACKEND=resend`, `MAIL_FROM`, `LLM_PROVIDER=anthropic`, `LLM_MODEL=claude-opus-5-5`, `LLM_FALLBACKS`, `GROUNDING_PROVIDER=openai`, `GROUNDING_MODEL=gpt-5.4-mini`, `GROUNDING_FALLBACKS`,
   `RETENTION_DAYS=90`, `RETENTION_LOOP=0`, `SUPABASE_BUCKET=orders`, `CRON_SECRET` (auto-generated; copy it from
   the service's Environment tab for step 5).
3. Apply. When it's live, open `https://formsorted-app.onrender.com/healthz` -> `{"ok":true}`.

## 4. Stripe webhook
Stripe -> Developers -> Webhooks -> Add endpoint: `https://formsorted-app.onrender.com/webhooks/payment`,
event `checkout.session.completed`. Copy the signing secret `whsec_...` into Render's `STRIPE_WEBHOOK_SECRET` (Render redeploys).
Payment Links' after-payment redirect: the app's `PUBLIC_URL`.

## 5. Daily deletion + keep-alive (free)
The app deletes orders, saved answers and stored files older than 90 days when `POST /cron/retention` is called with
header `X-Cron-Secret: <CRON_SECRET>`. Pick one:
- **GitHub Actions** (in the repo already: `.github/workflows/retention.yml`, daily 03:17 UTC). Repo -> Settings ->
  Secrets and variables -> Actions -> add `APP_URL` = `https://formsorted-app.onrender.com` and `CRON_SECRET`.
- **cron-job.org** (free): new cronjob, URL `https://formsorted-app.onrender.com/cron/retention`, daily, Advanced ->
  method POST, header `X-Cron-Secret` = the secret, timeout 60 s.

Erasure on request (by email or token) still works locally against the same database:
`DATABASE_URL=... SUPABASE_URL=... SUPABASE_SERVICE_KEY=... python retention.py --email someone@example.com`.

## Local testing
`./run_test.sh` (SQLite + local files, mock AI, no emails). Against Postgres: `DATABASE_URL=postgresql://... ./run_test.sh`.

## Models (llm.py)
- Drafting: `LLM_PROVIDER`/`LLM_MODEL` (default anthropic / claude-opus-5-5, Anthropic Messages API; chosen over Sonnet for accuracy, see live_test), then `LLM_FALLBACKS` in order (default `anthropic:claude-sonnet-5-5,gemini:gemini-3.8-flash,openai:gpt-5.5,openai:gpt-5.4`).
- Fact-check (grounding): `GROUNDING_PROVIDER`/`GROUNDING_MODEL` (default openai / gpt-5.4-mini), then `GROUNDING_FALLBACKS` (default `openai:gpt-5.4,gemini:gemini-3.8-flash,anthropic:claude-haiku-5-5,anthropic:claude-opus-5-5`). Models from the drafter's family are always tried last.
- A model that fails hard is skipped for `LLM_DOWN_SECS` (120s) so an outage doesn't slow every call. Retries cover 429/5xx/529 (Anthropic overloaded) and timeouts.
- Anthropic: system prompt is sent as top-level `system` with prompt caching; token counts include cache reads/writes.
- The check is mandatory: if every checker fails, the approve page shows "We're still checking your answers, try again in a few minutes" and nothing can be approved.
- Each call retries 429/5xx/529/timeouts with backoff (2,4,8,16s); out-of-credit/daily-quota errors skip straight to the next model. Entries whose API key is missing are skipped.
- Legacy: `LLM_API_KEY` + `LLM_BASE_URL` => provider `custom`.

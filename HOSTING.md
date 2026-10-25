# Hosting the FormSorted order backend (plan, not deployed)
Recommendation: keep the Python app as is, on one Hetzner Cloud CX23 (2 vCPU, 4 GB, 40 GB, EU: Nuremberg/Falkenstein/Helsinki).
Cost: EUR 5.49/month + EUR 0.50 IPv4 = EUR 5.99/month excl. VAT (Hetzner prices from 15 Jun 2026). Hourly billing, monthly cap.
Static marketing site stays on Cloudflare Pages (free). Point app.formsorted.com at the server through Cloudflare (free proxy + TLS).
Why not Workers + D1/R2: the app relies on pypdf (PDF form filling), python-docx, local files and SQLite. Workers' Python runtime would
need those rewritten for D1/R2 and the Pyodide package limits; days of work for ~EUR 5/month saving. EU hosting is fine for UK GDPR (adequacy).
Setup: Debian 12, `uvicorn app:app --port 8000` under systemd behind Caddy, daily `python retention.py` cron (or the built-in loop),
nightly encrypted DB backup kept <= 7 days (so the 90-day deletion promise holds).
Env: STRIPE_SECRET_KEY, STRIPE_WEBHOOK_SECRET, PUBLIC_URL=https://app.formsorted.com, ANTHROPIC_API_KEY/GEMINI_API_KEY/OPENAI_API_KEY, LLM_PROVIDER/LLM_MODEL/LLM_FALLBACKS, GROUNDING_PROVIDER/GROUNDING_MODEL/GROUNDING_FALLBACKS (see SETUP_RENDER_SUPABASE.md),
MAIL_BACKEND=resend|smtp (+RESEND_API_KEY or SMTP_*), MAIL_FROM, RETENTION_DAYS=90.
Payment webhook: endpoint https://app.formsorted.com/webhooks/payment, event checkout.session.completed.
Each Payment Link must carry metadata form=<aa|dla|pip|atw> and tier=<49|59|79>; amount must match the price or the order is refused.

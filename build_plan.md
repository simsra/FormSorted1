# Build plan: AA1 claim service (FormSorted)

## What exists now (local prototype, `/workspace/butter/apps/aa-claim-service/`)
- `app.py` (FastAPI): Stripe Checkout (£49/£79) → consent page (health data, digital-content waiver, truthfulness) → guided chat → prepare documents → download → delete my data.
- `llm.py`: interview and drafting prompts. Uses an OpenAI-compatible API; **mock mode** when there is no key.
- `fill_pdf.py` + `questions.py`: fills the **official AA1 (Nov 2025 version, 32 pages, AcroForm with 235 text fields and 193 tick boxes)**. Mapped fields: personal details, GP, conditions (6 slots), every care question's "tell us here" box (Q29–37, 39, 40, 42, 44), falls details, day/night counts, the statement from someone who knows the claimant (344), and extra information (354/315).
- `documents.py`: answers pack (HTML) with check-these notes, evidence checklist, GP letter, carer statement, and (£79) an online-claim script.
- `sample_case.json` + `demo_sample_case.py`: a fictional case. Output is in `out/sample/` (answers.html, AA1-filled.pdf, p13-13.png preview).
- Run: `../../.venv/bin/uvicorn app:app --port 8000`, then open http://localhost:8000 (DEV mode: no payment, mock AI).

## Deliberately NOT auto-filled
NI number, bank details, signatures and dates, and Yes/No tick boxes. We list exactly which to tick ("tick_yes"). Ticks could be automated in v1.1 once each question's widget export values are mapped from aa1_fields.json, but the user must still confirm them.

## Stack and hosting
- Python FastAPI + SQLite → move to Postgres (Neon free tier) only if needed.
- Host: Fly.io or Railway, about £4–5/month for a small always-on VM. Region: London (lhr). Cloudflare in front (free). Landing page: Cloudflare Pages (free).
- Email (private link plus receipt): Resend or Postmark free tier.
- Payments: Stripe Checkout + a webhook (`checkout.session.completed`) to add next. Fees about 1.5% + 20p (UK cards): **£0.94 on £49, £1.39 on £79**.
- Domain: about £5–10/year.
- **Fixed cost: about £10/month.**

## LLM cost per order (estimate)
Interview of about 30 turns with the system prompt resent each turn: about 60–90k input and 5k output tokens. Draft: about 10k input and 4k output.
- Small model (e.g. GPT-4o-mini class, about $0.15/$0.60 per M tokens): **under £0.05/order**.
- Mid/high-quality model (about $2.50–3/$10–15 per M): **about £0.30–0.60/order**. Recommended for the drafting step only.
- Margin per order is about £47 (£49 tier) or £77 (£79 tier) before ads. Ads are the real cost (see ad_test_plan.md).

## Privacy and compliance
- Special category health data: explicit consent tick before the chat (implemented), privacy notice (draft on the site), ICO fee (£52/yr tier 1), DPIA (one page).
- LLM provider with **zero data retention / no training** (OpenAI API ZDR, Azure OpenAI UK South, or Anthropic API). Sign the provider's DPA. Store data only in the UK/EU.
- Retention: auto-delete chat and docs 90 days after purchase (cron to add). A "Delete my information" button is implemented. Tokens are unguessable (24 bytes).
- Digital-content waiver before the service starts (implemented). 14-day cancellation honoured before start. Refunds via the Stripe dashboard.
- Guardrails: the prompt forbids inventing or exaggerating, and answers use only stated facts. The user must review. No success fees. "Not affiliated with DWP" on every output.
- AA1 version check: watch the GOV.UK page and re-map fields when DWP updates the form (field names are tied to this version).

## Timeline (about 2–3 weeks to a real launch, no pre-orders)
- Week 1: real LLM wired and tuned on 5–10 fictional cases; personal-details step in the UI; Stripe webhook and email link; tick-box mapping.
- Week 2: hosting, domain, privacy/terms final, ICO registration, retention cron, accessibility pass, PDF output check on 3 printed copies.
- Week 3: soft launch then Google Ads test (£100–150), measure cost per paid sale.

## Placeholders to fill
`STRIPE_SECRET_KEY` (Simon's restricted key), `LLM_API_KEY`/`LLM_BASE_URL`/`LLM_MODEL`, `PUBLIC_URL`, `BRAND`, email provider key.

## Known issue found in testing
The AA1 "tell us about this" boxes are small (about 5 lines at auto font size). Long answers get clipped when printed. Fix in week 1: keep each box answer to about 60 words, send the overflow to Q315 / Extra information (page 29) with "continued from question X", and set font size 0 (auto-size) on the filled fields.

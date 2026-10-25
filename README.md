# AA1 claim service: prototype
See build_plan.md. Quick demo with no keys: `../../.venv/bin/python demo_sample_case.py` → out/sample/. Server: `../../.venv/bin/uvicorn app:app --port 8000` (DEV mode).
Env vars: STRIPE_SECRET_KEY, PUBLIC_URL, ANTHROPIC_API_KEY, GEMINI_API_KEY, OPENAI_API_KEY, LLM_PROVIDER, LLM_MODEL, GROUNDING_MODEL (see SETUP_RENDER_SUPABASE.md), BRAND (default "FormSorted"; PUBLIC_URL e.g. https://app.formsorted.com). Official form: aa1.pdf (GOV.UK, Nov 2025); field dump: aa1_fields.json.


## Multi-form (23 Oct 2026)
One engine serves four forms, defined in `forms.py`. The user picks the form at `/`, then the tier at `/?form=<key>`. The order stores `form` in a DB column that is added automatically.
| key | Form | Delivery | Tiers |
|---|---|---|---|
| aa | AA1 Attendance Allowance | answers.html, plus AA1-filled.pdf (£79) | 49 / 79 |
| dla | DLA1A Child DLA (GOV.UK PDF, version 10/25, fillable AcroForm with 268 text fields and 160 buttons) | answers.html mapped to Q numbers, plus DLA1A-filled.pdf (£79) | 49 / 79 |
| pip | PIP2 "How your disability affects you" | typed answers mapped to PIP2 Q1–Q15 (activities = Q3–Q14). The £79 tier adds a call-prep sheet. | 59 / 79 |
| pipr | AR1 PIP review | typed answers mapped to the AR1 activity 1–12 sections, plus "what changed" | 59 / 79 |
- Files: `dla1a.pdf` (official), `dla1a_fields.json` (field dump with page, tooltip and size), `samples.py` (fictional MOCK drafts), and `ref_pip2_example.pdf` / `ref_ar1_example.pdf` (GOV.UK "example only" copies, for reference only).
- The DLA fill (`fill_pdf.fill_form`) covers child name, DOB and address, parent name, relationship, phone and email, conditions table (Q40), Q42, Q48, Q53, Q65, Q68 learning, Q72 (daytime care, supervision, senses, development and night narrative), Q70 night numbers, Q71, Q38 statement and Q89. It **never** fills NI numbers (fields 5, 76, 81_2), bank details (84–88), signatures or tick boxes; the tick boxes are listed in the pack.
- Test mode end to end: `../../.venv/bin/uvicorn app:app --port 8011 &` then `../../.venv/bin/python test_flows.py`. This runs every form and both tiers, and checks the downloads.
- Screenshots: screenshots/app-0-choose-form-desktop.png, app-1-choose-tier-pip-mobile.png, app-question-dla-desktop.png and app-question-pip-desktop.png.
- Known gaps: in-app personal-details form (as for AA), long answers can overflow the smaller DLA boxes (Q48/Q65 are about 200px wide), and the "question N" counter in chat.html counts screens rather than topics.
- Update (23 Oct, 21:15 Europe/Lisbon): long answers are now trimmed to fit each PDF box (`fill_pdf.fit`). The box text ends with "(continued on the additional information page)", and the remainder goes, under "Question N continued:", to AA1 field 354 or DLA1A Q89. The chat counter now shows "topic X of N" using the server's `topic`/`total`. With a real LLM, follow-up questions don't advance the topic count.

## v2 (24 Oct 2026): complaint-driven changes
Flow is now: choose → pay → agree → conversation → /deadline → /check (strength check) → /approve (each answer beside what the customer said; every answer must be ticked; downloads return 403 until approved) → /documents.
New modules: quality.py (rule-based strength check, `LLM_CHECK` hook), deadlines.py (GOV.UK-verified rules + phone script), letters.py (mandatory reconsideration draft).
Family-plan stubs (DEV only, "coming soon" otherwise): saved answers (`saved` table, save code), /review/{code} (pre-filled, asks only what changed), /letter.
TODO: 90-day automatic deletion of `saved` and orders is still NOT built. LLM review merge (old answer + change) is a TODO.
Screenshots: screenshots/v2-*.png

## Order backend (Oct 2026)
- `POST /webhooks/payment`: signed checkout.session.completed -> order + 256-bit private link, emailed via `mailer.py` (console/SMTP/Resend). Idempotent.
- `/details/{token}`: personal details asked only after approval, then documents are built. NI optional, never printed on the form.
- Deletion: `/delete/{token}` (customer), `python retention.py --email x` (request by email), daily 90-day purge (`retention.py` cron or in-app loop).
- See HOSTING.md. Tests: run server with STRIPE_WEBHOOK_SECRET=whsec_test_local, then `python test_flows.py` -> ALL OK.

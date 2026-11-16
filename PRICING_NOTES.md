# Pricing (Simon, 16 Nov 2026 23:16 GMT): £19.99 Download / £29.99 Posted to you, with support
Branch `chat-tidy` (on top of the v3 chat commit). NOT deployed. Stripe: no live changes; no Stripe test key on the box.

## What changed in the app
- forms.py: AA/DLA/PIP/PIP review tiers are `"1999"` Download £19.99 and `"2999"` Posted to you, with support £29.99.
  £99/£199 moved to `legacy_tiers` (existing orders keep working). `SUPPORT_DAYS=183` (= "up to 6 months", flag), `gbp()`, `RETURN_ADDR`.
- No package step: `/?form=aa` is "Before you start" (the 2 consent boxes) posting straight to `/checkout`. Old `tier=99/199` links start a Download order.
  `/package/{token}` now goes back to the pay screen. ATW keeps its package step; Blue Badge unchanged.
- Pay step: 2 options (radio cards), total and button update; discount line kept; postal address only on Posted (UK postcode checked).
  Posted sets `post_pack=1`, `post_to` (new column), `keep_until=paid+183 days` (answers kept while support runs).
- Stripe Checkout: price is in code (`price_data.unit_amount` 1999 / 2999), mode=payment, promotion codes on. No price ids needed.
- Fulfilment queue: `/admin` → "Orders to post" (ADMIN_SECRET). Shows address, the Freepost return address, sign-here pages
  (from the field map), files; "Open the form to print" (with NI overlay, kept max 14 days), "Mark as posted" (wipes NI/bank, emails customer).
- Support reminders: `POST /cron/support` (x-cron-secret) emails Posted customers at day 10, 42 and 120, once each, never after support ends.
  Needs a daily cron job added on Render when this goes live.
- `ALLOW_LEGACY_TIERS=1` only in run_test.sh so the old suites can still make £99/£199 orders. Never set it live.

## Site (test copy only)
`/workspace/butter/sites/aa-helper/pricing_edits.py dist OUT [--marked]` → `pricing_mrr/site_dist` (clean) and `site_dist_marked` (Terms/Privacy changes highlighted).
Not wired into launch_prep.py. Landing price line + price cards, 4 guides (option cards, one Start button, JSON-LD offers 19.99/29.99), FAQ, How it works, Terms, Privacy.

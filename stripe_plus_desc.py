"""Update the descriptions of the existing Done for you Plus products (fs_key aa_199, dla_199, pip_199, pipr_199) to the
'covers what comes next' copy in plus.summary(). Dry run by default: prints current vs new, changes nothing.
  STRIPE_KEY=rk_... python3 stripe_plus_desc.py            # dry run
  STRIPE_KEY=rk_... python3 stripe_plus_desc.py --apply    # update descriptions only (no new products, prices or links)
Needs a restricted key with Products: write. The key is never printed. Checkout sessions use inline product names only,
so this changes what Stripe shows on Payment Links / receipts for those products, not the app."""
import os, sys, json, base64, urllib.request, urllib.parse, urllib.error
import plus as PLUS
KEY=os.environ.get("STRIPE_KEY") or sys.exit("set STRIPE_KEY (restricted key, Products: write)")
APPLY="--apply" in sys.argv
def api(method,path,data=None):
    body=urllib.parse.urlencode(data).encode() if data else None
    if method=="GET" and data: path+="?"+body.decode(); body=None
    r=urllib.request.Request("https://api.stripe.com/v1"+path,body,method=method,headers={"Authorization":"Basic "+base64.b64encode((KEY+":").encode()).decode()})
    try: return json.load(urllib.request.urlopen(r))
    except urllib.error.HTTPError as e: raise SystemExit(f"{method} {path}: {e.code} {e.read().decode()[:300]}")
print("mode:","test" if "_test_" in KEY else "LIVE","| apply" if APPLY else "| dry run")
prods={p["metadata"].get("fs_key"):p for p in api("GET","/products",{"limit":100,"active":"true"})["data"]}
for form in PLUS.PLUS_FORMS:
    k=f"{form}_199"; new=PLUS.summary(form); p=prods.get(k)
    if not p: print(f"{k}: no product (checkout uses inline price data, so nothing to update; run stripe_setup.py only if a Payment Link is wanted)"); continue
    if p.get("description")==new: print(f"{k}: already up to date"); continue
    print(f"{k} {p['id']}\n  now: {p.get('description')}\n  new: {new}")
    if APPLY: api("POST",f"/products/{p['id']}",{"description":new}); print("  updated")

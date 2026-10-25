"""Idempotent Stripe setup for FormSorted Payment Links.
Usage: STRIPE_KEY=rk_test_... python3 stripe_setup.py [out.json]
Creates (or reuses) one product + GBP price + Payment Link per plan. Matches by metadata fs_key / price lookup_key.
Metadata form/tier match FORMS in forms.py (app.py webhook checks form, tier and amount_total)."""
import os, sys, json, base64, urllib.request, urllib.parse, urllib.error
from forms import FORMS
KEY=os.environ.get("STRIPE_KEY") or os.environ.get("STRIPE_TEST_KEY") or sys.exit("set STRIPE_KEY")
MODE="test" if "_test_" in KEY else "live"
THANKS=os.getenv("THANKS_URL","https://formsorted.com/thanks.html")
PLANS=[("aa","49","STRIPE_LINK_49"),("aa","79","STRIPE_LINK_79"),("dla","49","STRIPE_LINK_DLA_49"),("dla","79","STRIPE_LINK_DLA_79"),
       ("pip","59","STRIPE_LINK_PIP_59"),("pip","79","STRIPE_LINK_PIP_79"),("atw","49","STRIPE_LINK_ATW_49"),("atw","79","STRIPE_LINK_ATW_79")]
DESC={"49":"Your answers for every question on the form, drafted from what you tell us, for you to check and copy across.",
      "59":"Your answers for every question on the form, drafted from what you tell us, for you to check and copy across.",
      "79":"Your answers drafted from what you tell us, plus a completed form ready to check, sign and send."}
def api(method,path,data=None):
    body=urllib.parse.urlencode(data,doseq=True).encode() if data else None
    if method=="GET" and data: path+="?"+body.decode(); body=None
    r=urllib.request.Request("https://api.stripe.com/v1"+path,body,method=method,headers={"Authorization":"Basic "+base64.b64encode((KEY+":").encode()).decode()})
    try: return json.load(urllib.request.urlopen(r))
    except urllib.error.HTTPError as e: raise SystemExit(f"{method} {path}: {e.code} {e.read().decode()[:300]}")
def find_product(k):
    for p in api("GET","/products",{"limit":100,"active":"true"})["data"]:
        if p["metadata"].get("fs_key")==k: return p
def main():
    out={"mode":MODE,"links":{}}
    links=api("GET","/payment_links",{"limit":100,"active":"true"})["data"]
    for form,tier,cfg in PLANS:
        name,amount,_=FORMS[form]["tiers"][tier]; k=f"{form}_{tier}"; md={"form":form,"tier":tier,"fs_key":k}
        pname=f"{FORMS[form]['name']}: {name}"
        prod=find_product(k) or api("POST","/products",{"name":pname,"description":DESC[tier],**{f"metadata[{a}]":b for a,b in md.items()}})
        pr=api("GET","/prices",{"lookup_keys[]":f"fs_{k}_{amount}"})["data"]
        price=pr[0] if pr else api("POST","/prices",{"product":prod["id"],"currency":"gbp","unit_amount":amount,"lookup_key":f"fs_{k}_{amount}"})
        link=next((l for l in links if l["metadata"].get("fs_key")==k and l["metadata"].get("price")==price["id"]),None)
        if not link:
            for old in [l for l in links if l["metadata"].get("fs_key")==k]: api("POST",f"/payment_links/{old['id']}",{"active":"false"})
            d={"line_items[0][price]":price["id"],"line_items[0][quantity]":1,"after_completion[type]":"redirect",
               "after_completion[redirect][url]":THANKS,"customer_creation":"always","billing_address_collection":"auto",
               **{f"metadata[{a}]":b for a,b in {**md,"price":price["id"]}.items()},
               **{f"payment_intent_data[metadata][{a}]":b for a,b in md.items()}}
            link=api("POST","/payment_links",d)
        out["links"][cfg]={"url":link["url"],"payment_link":link["id"],"price":price["id"],"product":prod["id"],"form":form,"tier":tier,"amount":amount,"name":pname}
        print(cfg,pname,f"£{amount/100:.0f}",link["url"])
    fn=sys.argv[1] if len(sys.argv)>1 else f"stripe_links_{MODE}.json"
    json.dump(out,open(fn,"w"),indent=2); print("saved",fn)
if __name__=="__main__": main()

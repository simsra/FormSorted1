"""Blue Badge answers: £29 on its own, £15 add-on after a paid AA / DLA / PIP order (prefilled, no re-asking). DEV server: python test_bluebadge.py URL"""
import sys, re, urllib.request, urllib.parse
from forms import FORMS, tier_info, default_tier
import bluebadge as BB
assert list(FORMS["bb"]["tiers"])==["29","15"] and tier_info("bb","29")[1]==2900 and tier_info("bb","15")[1]==1500 and default_tier("bb")=="29"
# ---- prefill from each parent form's taps (unit)
p=BB.prefill("pip",{"who":"me","rows":{"a12":{"c":["lt50","pain"]},"a11":{"c":["panic"]}},"aids":["Walking stick"],"people":["GP"],"conds":[{"name":"COPD"}]})
assert p["dist"]=="20_50" and "pain" in p["eff"] and "panic" in p["hidden"] and p["aids"]==["stick"] and p["docs"]==["pip"] and "dist" in p["prefilled"]
d=BB.prefill("dla",{"who":"child","name":"Sam","rows":{"walk":{"c":["pain","tired"]},"out":{"c":["danger","anx"]}}})
assert d["who"]!="me" and "pain" in d["eff"] and d["hidden"] and d["docs"]==["dla"]
a=BB.prefill("aa",{"who":"parent","name":"Margaret","falls":"3-5","conds":[{"name":"Arthritis"}]})
assert a["conds"][0]["name"]=="Arthritis" and a["docs"]==["aa"] and "falls" in a["eff"]
p["time"]="1_5"; L=BB.letter(p,"2026-10-01","You can walk more than 80 metres.")
assert "1 October 2026" in L and "walk 20 to 50 metres" in L and "You can walk more than 80 metres." in L
B=sys.argv[1]
class NR(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*a,**k): return None
op=urllib.request.build_opener(NR)
def req(p,data=None):
    r=urllib.request.Request(B+p,urllib.parse.urlencode(data,doseq=True).encode() if data is not None else None)
    try: return op.open(r)
    except urllib.error.HTTPError as e: return e
body=lambda p: req(p).read().decode(); loc=lambda r: r.headers["location"]
DWP="You can claim directly from DWP for free; FormSorted is a paid online form-filling service."
def clean(h):
    low=h.lower().replace(DWP.lower(),"").replace("can\x27t guarantee","").replace("not affiliated","")
    assert not re.search(r"\bfree\b",low)
    for bad in ("stripe"," ai ","eligible","guarantee","you will get","you'll get a badge","on behalf of the council","we apply","we submit"): assert bad not in low, bad
    assert "gov.uk/" not in low
    assert not set(re.findall(r'href="?(https?://[^" >]+)',h))-{"https://formsorted.com/privacy.html","https://formsorted.com/terms.html"}, re.findall(r'href="?(https?://[^" >]+)',h)
    assert "online form-filling service" in h
# ---- standalone £29
h=body("/?form=bb"); clean(h); assert "£29" in h and "£15" in h and "Start my answers" in h
assert req("/checkout",{"form":"bb","tier":"15"}).status==400
tok=loc(req("/checkout",{"form":"bb","tier":"29"})).split("/")[-1]
assert "Blue Badge application is an offence" in body(f"/start/{tok}")
req(f"/consent/{tok}",{"health":"on","truth":"on"}); assert loc(req(f"/start/{tok}"))==f"/bb/{tok}"
f=body(f"/bb/{tok}"); clean(f);
for u in (f"/bb/{tok}/documents",f"/bb/{tok}/file/blue-badge-answers.html"): assert req(u).status==402, u
assert req(f"/bb/{tok}/letter",{"decision_date":"2026-10-01"}).status==402
assert loc(req(f"/bb/{tok}",{"who":"me","conds":"MS","dist":"lt20","time":"5p","eff":["pain","falls"],"hidden":["panic"],"hfreq":"most","docs":["pip"]}))==f"/preview/{tok}"
pv=body(f"/preview/{tok}"); clean(pv); assert "Pay £29" in pv and "I can walk" not in pv and "MS" not in pv
assert req(f"/bb/{tok}/file/blue-badge-answers.html").status==402
assert loc(req(f"/pay/{tok}",{"waive":"on"}))==f"/start/{tok}"; assert loc(req(f"/start/{tok}"))==f"/bb/{tok}/documents"
dc=body(f"/bb/{tok}/documents"); clean(dc); assert "Turned down?" in dc
fx=body(f"/bb/{tok}/file/blue-badge-answers.html"); assert "I have MS." in fx and "under 20 metres" in fx and "What to have ready" in fx and "http" not in fx
lt=req(f"/bb/{tok}/letter",{"decision_date":"2026-10-01","reason":"Not enough evidence"}).read().decode()
assert "1 October 2026" in lt and "Not enough evidence" in lt and "http" not in lt
assert req(f"/bb/{tok}/file/../app.py").status in (404,400)
# ---- £15 add-on from a paid PIP order: no re-asking, prefilled
pt=loc(req("/checkout",{"tier":"99","form":"pip"})).split("/")[-1]; req(f"/consent/{pt}",{"health":"on","truth":"on"})
os_=body(f"/?form=pip"); assert "Blue Badge application answers for £15" in os_
assert req(f"/bb/addon/{pt}",{}).status==402          # parent not paid yet
import app as A, json
c=A.db(); c.execute("update orders set status='paid', interview_done_at=1, intake=? where token=?",(json.dumps({"who":"me","rows":{"a12":{"c":["lt50","pain"]}},"aids":["Walking stick"],"conds":[{"name":"COPD"}]}),pt)); c.commit()
bt=loc(req(f"/bb/addon/{pt}",{})).split("/")[-1]; assert loc(req(f"/bb/addon/{pt}",{})).endswith(bt)  # one add-on per order
f=body(f"/bb/{bt}"); assert "filled in what you told us on your PIP form" in f; assert "COPD" in f
assert loc(req(f"/bb/{bt}",{"who":"me","conds":"COPD","dist":"20_50","eff":["pain"],"aids":["stick"],"docs":["pip"]}))==f"/preview/{bt}"
pv=body(f"/preview/{bt}"); clean(pv); assert "Pay £15" in pv and "£29" not in pv
assert req(f"/bb/{bt}/file/blue-badge-answers.html").status==402
req(f"/pay/{bt}",{"waive":"on"}); assert "COPD" in body(f"/bb/{bt}/file/blue-badge-answers.html")
assert A.get(bt)["tier"]=="15" and A.get(bt)["review_of"]==pt
# documents page of the parent offers the add-on; ATW parent can't
assert req(f"/bb/addon/nope",{}).status==404
print("bluebadge ok")

"""Done for you (£99) and Done for you Plus (£199): comparison, 3-year opt-in, briefing from approved answers only + request letters (the person writes their own words),
print-and-post (disabled, queued only), appeal (reconsideration) and renewal for Plus orders, retention. DEV server:  python test_premium.py URL"""
import sys, re, json, io, uuid, time, urllib.request, urllib.parse, os
from forms import FORMS, is_full, is_premium, tier_info, default_tier
import printmail, grounding
for f in ("aa","dla","pip","pipr"):
    assert list(FORMS[f]["tiers"])==["99","199"] and FORMS[f]["tiers"]["99"][1]==9900 and FORMS[f]["tiers"]["199"][1]==19900 and default_tier(f)=="99"
    assert tier_info(f,"79")[1]==7900   # legacy orders still render
assert is_full("99") and is_full("199") and is_premium("199") and not is_premium("99") and not printmail.ENABLED
B=sys.argv[1]
class NR(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*a,**k): return None
op=urllib.request.build_opener(NR)
def req(p,data=None,raw=None,ct=None):
    r=urllib.request.Request(B+p,raw,{"Content-Type":ct}) if raw is not None else urllib.request.Request(B+p,urllib.parse.urlencode(data,doseq=True).encode() if data is not None else None)
    try: return op.open(r)
    except urllib.error.HTTPError as e: return e
body=lambda p: req(p).read().decode(); loc=lambda r: r.headers["location"]
DWP="You can claim directly from DWP for free; FormSorted is a paid online form-filling service."
for form in ("aa","dla","pip"):
    h=body(f"/?form={form}")
    assert "£99" in h and "£199" in h and "Compare packs" in h and "Upgrade to Done for you Plus, £199" in h and "How much should we" not in h and h.count(DWP)==1
    hp=body(f"/?form={form}&tier=199"); assert "Done for you Plus" in hp and "Switch to Done for you, £99" in hp and "riefing" in hp
    for x in (h,hp):
        low=x.lower().replace(DWP.lower(),"").replace("freepost",""); assert "free" not in low and "stripe" not in low and " ai " not in low and "we claim for you" not in low and "we submit your claim" not in low and "claim pack" not in low and "claims service" not in low and "claims firm" not in low and "claim handling" not in low
        assert not set(re.findall(r'href="?(https?://[^" >]+)',x))-{"https://formsorted.com/privacy.html","https://formsorted.com/terms.html","https://formsorted.com/#prices"}
assert "How much should we do for you?" in body("/?form=atw")
# ---- Plus AA order through the intake
tok=loc(req("/checkout",{"tier":"199","form":"aa"})).split("/")[-1]; req(f"/consent/{tok}",{"health":"on","truth":"on"})
for s,d in [("about",{"who":"parent","name":"Margaret","signer":"poa"}),("conds",{"cond_0":"1","cond_0_since":"2015"}),("daily",{"bad":"3","r_bed_hard":"1","r_bed_help":"1","r_bed_freq":"every"}),("safety",{"falls":"3-5"}),("finish",{"people":["GP","Family carer"]})]:
    req(f"/intake/{tok}",{"sec":s,"nav":"next",**d})
pv=body(f"/preview/{tok}"); assert "Keep my answers for 3 years" in pv and "Pay £199" in pv and pv.count(DWP)==1 and "Margaret finds" not in pv
assert req(f"/appeal/nope").status==404
assert loc(req(f"/pay/{tok}",{"waive":"on","keep":"1"}))==f"/start/{tok}"; req(f"/start/{tok}"); req(f"/uploads/{tok}/done",{}); req(f"/prepare/{tok}")
ap=body(f"/approve/{tok}"); ok={f"ok_{t}":"on" for t,_,_ in FORMS["aa"]["topics"]}; ok["honest"]="on"
for rn in set(re.findall(r'name="(res_[^"]+)"',ap)): ok[rn]="keep"
r=req(f"/approve/{tok}",ok); assert loc(r)==f"/ticks/{tok}"
th=body(f"/ticks/{tok}"); tf=dict(re.findall(r'name="(t_[^"]+)" value="([^"]*)" checked',th)); tf["confirm"]="on"; req(f"/ticks/{tok}",tf)
dh=body(f"/details/{tok}"); assert "Print and post my pack" not in dh   # disabled until a provider is live
dd={"title":"Mrs","other_names":"Margaret","surname":"Tester","dob":"1940-01-02","addr1":"1 Test St","addr3":"Leeds","postcode":"LS1 1AA","post_pack":"1"}
assert loc(req(f"/details/{tok}",dd))==f"/documents/{tok}"
doc=body(f"/documents/{tok}"); m=re.search(r'href="/appeal/([^"]+)"',doc); assert m and "/review/"+m.group(1) in doc and "print and post your pack" not in doc
code=m.group(1)
for fn in ("assessment-briefing.html","supporting-letters.html","AA1-filled.pdf","answers.html"): assert f"/download/{tok}/{fn}" in doc, fn
br=body(f"/download/{tok}/assessment-briefing.html"); sl=body(f"/download/{tok}/supporting-letters.html")
import app as A
o=A.get(tok); d=json.loads(o["draft"])
for x in re.findall(r"<p class=you>(.*?)</p>",br):   # every quoted block is an approved answer, word for word
    import html as H; assert H.unescape(x) in d["answers"].values(), x
assert "For: GP" in sl and "For: Family carer" in sl and "http" not in br+sl
import html as H; slt=H.unescape(re.sub(r"<[^>]+>"," ",sl))
assert "Request letters" in sl and "question 56 (page 28)" in slt and "only write what you know to be true" in slt
for a in d["answers"].values():   # never the customer's answers pasted in for them to sign
    if a and len(a)>25: assert a not in slt, a
for bad in ("the following is correct","Signed:","Role:","I am Margaret","To whom it may concern","Letter for:"): assert bad not in slt, bad
assert o["keep_until"] and o["keep_until"]>time.time()+2.9*365*86400 and o["post_pack"]==0
assert not A.db().execute("select v from settings where k=?",(f"printjob_{tok}",)).fetchone()
# ---- appeal (reconsideration) included
ah=body(f"/appeal/{code}"); assert "1 month from the date on your decision letter" in ah and "can't guarantee" in ah
b=uuid.uuid4().hex; raw=(f'--{b}\r\nContent-Disposition: form-data; name="decision_date"\r\n\r\n2026-10-20\r\n--{b}\r\nContent-Disposition: form-data; name="topics"\r\n\r\n29\r\n'
     f'--{b}\r\nContent-Disposition: form-data; name="files"; filename="decision.png"\r\nContent-Type: image/png\r\n\r\n').encode()+b"\x89PNG fake"+f"\r\n--{b}--\r\n".encode()
r=req(f"/appeal/{code}",raw=raw,ct=f"multipart/form-data; boundary={b}"); at=loc(r).split("/")[-1]; assert loc(r)==f"/approve/{at}"
ap=body(f"/approve/{at}"); ok={f"ok_{t}":"on" for t,_,_ in FORMS["aa"]["topics"]}; ok["honest"]="on"
for rn in set(re.findall(r'name="(res_[^"]+)"',ap)): ok[rn]="keep"
nx=loc(req(f"/approve/{at}",ok))
if "/ticks/" in nx: th=body(nx); tf=dict(re.findall(r'name="(t_[^"]+)" value="([^"]*)" checked',th)); tf["confirm"]="on"; req(nx,tf)
req(f"/details/{at}",{"skip":"1"}); doc=body(f"/documents/{at}"); assert f"/download/{at}/reconsideration-letter.txt" in doc
mr=body(f"/download/{at}/reconsideration-letter.txt"); assert "20 October 2026" in mr and "decision.png" in mr and "mandatory reconsideration" in mr.lower()
# ---- renewal included (prefilled from saved answers)
rv=body(f"/review/{code}"); assert "What has changed?" in rv and "Last time you said" in rv
# ---- £99 order: no Plus extras, appeal not available
t9=loc(req("/checkout",{"tier":"99","form":"pip"})).split("/")[-1]; req(f"/consent/{t9}",{"health":"on","truth":"on"})
for s in ("about","conds","daily","out","finish"): req(f"/intake/{t9}",{"sec":s,"nav":"next","who":"me"})
p9=body(f"/preview/{t9}"); assert "How would you like it finished?" in p9 and "name=pack value=99 data-price=99 checked" in p9 and "name=pack value=199 data-price=199  required" in p9 and p9.index("Keep my answers for 3 years")>p9.index("<div class=keepopt>")   # only shown for Plus
req(f"/pay/{t9}",{"waive":"on","keep":"1"}); assert A.get(t9)["keep_until"] is None
# ---- retention: opted-in Plus answers survive the 90-day purge; erase removes them
import orders
c=A.db(); c.execute("update orders set created=? where token=?",(time.time()-200*86400,tok)); c.commit()
orders.purge(c,A.OUT); assert A.get(tok)["status"]=="paid" and c.execute("select 1 from saved where code=?",(code,)).fetchone()
orders.erase(c,A.OUT,tok); assert A.get(tok)["keep_until"] is None and not c.execute("select 1 from saved where code=?",(code,)).fetchone()
print("PREMIUM ALL OK")

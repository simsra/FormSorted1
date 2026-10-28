"""Plus 'covers what comes next' (Simon, 28 Oct 2026): per-form copy, the finish screen (£99 default, nothing ticked, no saving line),
reconsideration letter voice, 'next form included' entitlement (one per Plus order, same benefit and person), Blue Badge included once.
DEV server:  python test_plus_next.py URL"""
import sys, re, json, time, urllib.request, urllib.parse
import plus as PLUS, letters, printmail
from forms import FORMS
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
BANNED=["bought one by one","bought separately","you save","saving","save £","worth £","only today","limited time","hurry","ends soon","countdown"," ai ","stripe","we claim","we submit","we appeal for you","tribunal","sscs1","appeal form","guarantee an award","win "]
# ---- 1. copy
for f in PLUS.PLUS_FORMS:
    txt=" ".join(PLUS.flat(f)+PLUS.notes(f)+[PLUS.summary(f),PLUS.FOOT,FORMS[f]["tiers"]["199"][2]]).lower()
    for b in BANNED: assert b not in " "+txt+" ", (f,b)
    assert "reconsideration letter" in txt and "check, sign and send" in txt and "same price whatever dwp decides" in txt
    assert ("1 in 4" in txt)==(f in ("pip","pipr")), f
    assert ("posted to you" in txt) and (("coming soon" in txt) != PLUS.posting()), f   # posting: only 'coming soon' until live
    assert ("blue badge" in txt)==(f in PLUS.BB_FORMS), f
assert "may never need this" in " ".join(PLUS.flat("aa")) and "higher rate" in " ".join(PLUS.flat("aa"))
assert "renewal" in " ".join(PLUS.flat("dla")).lower() and "PIP claim at 16" in " ".join(PLUS.flat("dla"))
assert "review form" in " ".join(PLUS.flat("pip")) and "next PIP review form" in " ".join(PLUS.flat("pipr"))
for f in ("aa","dla","pip","pipr"): assert "Renewal included" not in FORMS[f]["tiers"]["199"][2] and "Freepost" not in FORMS[f]["tiers"]["199"][2]
for l,d,b,p in PLUS.compare_rows("aa"): assert b in (0,1,"£15 extra") and p==1   # nothing priced that can't be bought on its own
# ---- 2. reconsideration letter voice
L=lambda f,w: letters.mr_letter(f,{"name":"Margaret Tester","address":"1 Test St","decision_date":"1 October 2026","points":[],"for":w})
assert "my Attendance Allowance claim" in L("aa",{"who":"me"}) and "my Attendance Allowance claim" in L("aa",None)
t=L("aa",{"who":"parent","signer":"poa"}); assert "my Attendance" not in t and "claim for Margaret Tester" in t and "Power of Attorney" in t and "Claimant: Margaret Tester" in t
t=L("aa",{"who":"parent","signer":"ns"}); assert "on behalf of Margaret Tester" in t and "Signed by Margaret Tester" in t
t=L("aa",{"who":"parent","signer":"them"}); assert "my Attendance Allowance claim" in t and "Written with help from" in t   # they sign their own letter
t=L("dla",{"who":"parent"}); assert "claim for my child, Margaret Tester," in t and "my Disability" not in t and "Parent or guardian" in t
t=L("pip",{"who":"partner","signer":"appointee"}); assert "my Personal" not in t and "appointee" in t
# ---- 3. finish screen
def intake_order(tier,form="aa",who="parent"):
    tok=loc(req("/checkout",{"tier":tier,"form":form})).split("/")[-1]; req(f"/consent/{tok}",{"health":"on","truth":"on"})
    for s,d in [("about",{"who":who,"name":"Margaret","signer":"poa"}),("conds",{"cond_0":"1","cond_0_since":"2015"}),("daily",{"bad":"3","r_bed_hard":"1","r_bed_help":"1","r_bed_freq":"every"}),("safety",{"falls":"3-5"}),("finish",{"people":["GP","Family carer"]})]:
        req(f"/intake/{tok}",{"sec":s,"nav":"next",**d})
    return tok
t9=intake_order("99"); pv=body(f"/preview/{t9}"); low=pv.lower()
assert "How would you like it finished?" in pv and pv.count(DWP)==1 and "Pay £99" in pv
assert re.search(r"name=pack value=99 [^>]*checked",pv) and not re.search(r"name=pack value=199 [^>]*checked",pv)
assert not re.search(r"type=checkbox[^>]*checked",pv)   # nothing ticked for them
for b in BANNED[:10]: assert b not in low, b
assert "May never need this".lower() in low and "1 in 4" not in low
tp=intake_order("99","pip","me"); assert "1 in 4 of these requests leads to a change in award" in body(f"/preview/{tp}")
t1=intake_order("199"); assert re.search(r"name=pack value=199 [^>]*checked",body(f"/preview/{t1}"))   # picked Plus at the start: stays Plus
import app as A
assert loc(req(f"/pay/{t9}",{"waive":"on","pack":"199","keep":"1"}))==f"/start/{t9}"; o=A.get(t9); assert o["tier"]=="199" and o["keep_until"]>time.time()+2.9*365*86400
tq=intake_order("199"); req(f"/pay/{tq}",{"waive":"on","pack":"99","keep":"1"}); o=A.get(tq); assert o["tier"]=="99" and o["keep_until"] is None
assert req(f"/pay/{intake_order('99')}",{"waive":"on","pack":"0"}).status==303 and A.get(t9)["tier"]=="199"   # a made-up pack is ignored
# ---- 4. next form included: one per Plus order, same benefit, same person
def finish(tok,form="aa"):
    req(f"/start/{tok}"); req(f"/uploads/{tok}/done",{}); req(f"/prepare/{tok}")
    import app as A
    for _ in range(100):   # drafting runs in the background: wait for it rather than race it
        if A.get(tok)["draft"]: break
        time.sleep(0.1)
    approve(tok,form)
def approve(tok,form="aa"):
    ap=body(f"/approve/{tok}"); ok={f"ok_{t}":"on" for t,_,_ in FORMS[form]["topics"]}; ok["honest"]="on"
    for rn in set(re.findall(r'name="(res_[^"]+)"',ap)): ok[rn]="keep"
    nx=loc(req(f"/approve/{tok}",ok))
    if "/ticks/" in nx: th=body(nx); tf=dict(re.findall(r'name="(t_[^"]+)" value="([^"]*)" checked',th)); tf["confirm"]="on"; req(nx,tf)
finish(t9)
dd={"title":"Mrs","other_names":"Margaret","surname":"Tester","dob":"1940-01-02","addr1":"1 Test St","addr3":"Leeds","postcode":"LS1 1AA"}
req(f"/details/{t9}",dd); doc=body(f"/documents/{t9}")
c=A.db(); code=A.get(t9)["save_code"]; assert code and PLUS.status(c,A.get(t9),PLUS.NEXT)=="available"
assert "Next Attendance Allowance form: included." in doc and f"/review/{code}" in doc and "No charge." in doc
assert "Included with Done for you Plus: we turn the answers" in doc and "Add Blue Badge answers, £15" not in doc
# Blue Badge included once
bt=loc(req(f"/bb/addon/{t9}",{})).split("/")[-1]; bo=A.get(bt); assert bo["tier"]=="0" and PLUS.status(c,A.get(t9),PLUS.BB)=="used"
assert A.tier_info("bb","0")[1]==0 and "Get my answers (included" in body(f"/preview/{bt}") if A.get(bt)["interview_done_at"] else True
# redeem the next form
rv=body(f"/review/{code}"); assert "What has changed?" in rv
r=req(f"/review/{code}",{}); nt=loc(r).split("/")[-1]; n_before=c.execute("select count(*) from orders").fetchone()[0]
assert A.get(nt)["tier"]=="199" and A.get(nt)["review_of"]==code and PLUS.redeemed_from(c,nt)==t9 and PLUS.status(c,A.get(t9),PLUS.NEXT)=="used"
assert "has been used" in body(f"/review/{code}") and "has been used" in req(f"/review/{code}",{}).read().decode()
assert c.execute("select count(*) from orders").fetchone()[0]==n_before   # no second free order
assert not PLUS.grant(c,A.get(nt)) and PLUS.root(c,A.get(nt))["token"]==t9   # a free next-form order never grants another
assert not PLUS.allows(c,A.get(t9),PLUS.NEXT,"dla")   # other benefit: never
# same person only
approve(nt)
r=req(f"/details/{nt}",{**dd,"surname":"Someone","dob":"1950-05-05"}); assert "same person" in urllib.parse.unquote(loc(r))
assert loc(req(f"/details/{nt}",dd))==f"/documents/{nt}"
# a £99 order has no entitlement
t99=intake_order("99"); req(f"/pay/{t99}",{"waive":"on"}); finish(t99); assert PLUS.status(c,A.get(t99),PLUS.NEXT) is None
print("PLUS NEXT ALL OK")

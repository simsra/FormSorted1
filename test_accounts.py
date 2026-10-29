"""Customer accounts (accounts.py): passwordless emailed-link sign-in, saved answers, NI/bank never saved, off by default.
  python test_accounts.py URL_ON SQLITE_PATH MAIL_LOG [URL_OFF]   (URL_ON started with ACCOUNTS_ENABLED=1)"""
import sys, re, json, time, sqlite3, urllib.request, urllib.parse, http.cookiejar, os
from forms import FORMS
B=sys.argv[1]; DBP=sys.argv[2]; MAIL=sys.argv[3]; OFF=sys.argv[4] if len(sys.argv)>4 else None
import accounts as ACCT
# ---- unit: scrub never keeps NI numbers or bank details, at any depth
x={"ni":"QQ123456C","h_ni":"AB 12 34 56 C","personal":{"surname":"Tester","sort":"12-34-56","acc":"12345678","nino":"x"},"notes":["NI QQ 12 34 56 C here","sort 12-34-56"],"bank":"Barclays","cond_0":"1"}
s=ACCT.scrub(x); t=json.dumps(s)
for bad in ("QQ123456C","AB 12 34 56 C","12-34-56","12345678","Barclays","QQ 12 34 56 C"): assert bad not in t, bad
assert s["cond_0"]=="1" and s["personal"]["surname"]=="Tester"
assert ACCT.norm_email(" A@B.co.uk ")=="a@b.co.uk" and ACCT.norm_email("nope")=="" and ACCT.norm_email("a@b")==""
I,P=ACCT.carry({"intake":{"cond_0":"1","who":"me","bad":"3","conds":[{"name":"Arthritis"}],"ni":"QQ123456C"},"personal":{"surname":"T","dob":"1950-01-01","sort":"12-34-56"}},"aa","pip")
assert I=={"cond_0":"1","who":"me","conds":[{"name":"Arthritis"}]} and P=={"surname":"T","dob":"1950-01-01"}
assert ACCT.carry({"intake":{"cond_0":"1"},"personal":{"surname":"T"}},"aa","dla")==({},{})
I,P=ACCT.carry({"intake":{"cond_0":"1","bad":"3"},"personal":{"surname":"T"}},"aa","aa"); assert I["bad"]=="3"
# ---- HTTP helpers (each 'browser' has its own cookies)
class NR(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*a,**k): return None
def browser():
    j=http.cookiejar.CookieJar(); op=urllib.request.build_opener(NR,urllib.request.HTTPCookieProcessor(j))
    def req(p,data=None,base=B):
        r=urllib.request.Request(base+p,urllib.parse.urlencode(data,doseq=True).encode() if data is not None else None)
        try: return op.open(r)
        except urllib.error.HTTPError as e: return e
    return req,j
req,jar=browser()
body=lambda p,r=None: (r or req)(p).read().decode(); loc=lambda r: r.headers["location"]
def db(): c=sqlite3.connect(DBP); c.row_factory=sqlite3.Row; return c
def mails(): return [json.loads(l) for l in open(MAIL)] if os.path.exists(MAIL) else []
def last_link(to):
    for m in reversed(mails()):
        if m["to"]==to:
            u=re.search(r"/account/link/([A-Za-z0-9_\-]+)",m["text"])
            if u: return u.group(1)
def paid_order(email,form="aa"):
    tok=loc(req("/checkout",{"tier":"99","form":form})).split("/")[-1]; req(f"/consent/{tok}",{"health":"on","truth":"on"})
    for s,d in [("about",{"who":"me","name":"Margaret"}),("conds",{"cond_0":"1","cond_0_since":"2015"}),("daily",{"bad":"3","r_bed_hard":"1","r_bed_help":"1","r_bed_freq":"every"}),("safety",{"falls":"3-5"}),("finish",{"people":["GP"]})]:
        req(f"/intake/{tok}",{"sec":s,"nav":"next",**d})
    assert loc(req(f"/pay/{tok}",{"waive":"on"}))==f"/start/{tok}"; req(f"/start/{tok}"); req(f"/uploads/{tok}/done",{}); req(f"/prepare/{tok}")
    ap=body(f"/approve/{tok}"); ok={f"ok_{t}":"on" for t,_,_ in FORMS[form]["topics"]}; ok["honest"]="on"
    for rn in set(re.findall(r'name="(res_[^"]+)"',ap)): ok[rn]="keep"
    r=req(f"/approve/{tok}",ok)
    if loc(r)==f"/ticks/{tok}":
        th=body(f"/ticks/{tok}"); tf=dict(re.findall(r'name="(t_[^"]+)" value="([^"]*)" checked',th)); tf["confirm"]="on"; req(f"/ticks/{tok}",tf)
    req(f"/details/{tok}",{"title":"Mrs","other_names":"Margaret","surname":"Tester","dob":"1940-01-02","addr1":"1 Test St","addr3":"Leeds","postcode":"LS1 1AA","ni":"QQ123456C","bank":"Test Bank","sort":"12-34-56","acc":"12345678"})
    c=db(); c.execute("update orders set email=? where token=?",(email,tok)); c.commit()
    # simulate an older row that still held NI details in personal/intake: they must never reach an account
    p=json.loads(c.execute("select personal from orders where token=?",(tok,)).fetchone()[0] or "{}"); p.update({"ni":"QQ123456C","sort":"12-34-56","acc":"12345678"})
    c.execute("update orders set personal=? where token=?",(json.dumps(p),tok)); c.commit()
    return tok
EM=f"acct{int(time.time())}@example.com"
tok=paid_order(EM)
doc=body(f"/documents/{tok}"); assert "Save your answers for next time" in doc and EM in doc and "never keep your National Insurance number or bank details" in doc
assert "stripe" not in doc.lower() and " ai " not in doc.lower()
# ---- save: creates the account, signs this browser in, emails a welcome
r=req(f"/account/save/{tok}",{}); assert r.status==303 and loc(r).startswith(f"/documents/{tok}"), r.status
assert any(ck.name==ACCT.COOKIE for ck in jar)
assert "Saved to your account" in body(f"/documents/{tok}")
assert any(m["to"]==EM and "account" in m["subject"].lower() for m in mails())
c=db(); a=c.execute("select * from accounts where email=?",(EM,)).fetchone(); assert a
row=c.execute("select data from account_saved where account_id=?",(a["id"],)).fetchone(); assert row
for bad in ("QQ123456C","12-34-56","12345678","Test Bank"): assert bad not in row[0], bad
for t in ("accounts","account_saved","account_sessions","account_links"):
    for r_ in c.execute(f"select * from {t}").fetchall():
        for v in r_:
            assert not (isinstance(v,str) and ("QQ123456C" in v or "12345678" in v)), t
assert c.execute("select account_id from orders where token=?",(tok,)).fetchone()[0]==a["id"]
h=body("/account"); assert EM in h and "Attendance Allowance" in h and "Start a new Attendance Allowance form" in h and f"/documents/{tok}" in h
# ---- start a new form from saved answers: answers carried, nothing secret
r=req("/account/start",{"src":"aa","form":"aa"}); assert r.status==303 and loc(r).startswith("/start/"); nt=loc(r).split("/")[-1]
n=db().execute("select * from orders where token=?",(nt,)).fetchone(); assert n["status"]=="free" and n["account_id"]==a["id"]
NI_=json.loads(n["intake"]); assert NI_["conds"][0]["name"]=="Arthritis" and NI_["rows"]["bed"]["hard"] and "at" not in NI_ and "QQ123456C" not in (n["intake"] or "")+(n["personal"] or "") and json.loads(n["personal"])["surname"]=="Tester"
assert req("/account/start",{"src":"aa","form":"dla"}).status==400
# ---- sign out, then sign in by emailed link (single use, button not auto)
req("/account/signout",{}); assert loc(req("/account"))=="/account/signin"
before=len(mails())
ck=body("/account/signin",lambda p: req(p,{"email":EM})); assert "Check your email" in ck
t=last_link(EM); assert t and len(mails())==before+1
assert db().execute("select count(*) from account_links where tok_hash=?",(t,)).fetchone()[0]==0   # only the hash is stored
lp=body(f"/account/link/{t}"); assert "<form method=post" in lp and db().execute("select used_at from account_links where account_id=? order by created desc",(a["id"],)).fetchone()[0] is None
r=req(f"/account/link/{t}",{}); assert r.status==303 and loc(r)=="/account"
assert EM in body("/account")
assert "expired" in body(f"/account/link/{t}") and "expired" in req(f"/account/link/{t}",{}).read().decode()   # single use
# ---- unknown email: same page, no mail, no account
before=len(mails()); unk=f"nobody{int(time.time())}@example.com"
assert "Check your email" in req("/account/signin",{"email":unk}).read().decode() and len(mails())==before and not db().execute("select 1 from accounts where email=?",(unk,)).fetchone()
# ---- rate limit: 3 per email per 15 minutes
req2,_=browser()
for i in range(3): req2("/account/signin",{"email":EM})
assert "Please wait" in req2("/account/signin",{"email":EM}).read().decode()
# ---- expired link
c=db(); c.execute("update account_links set expires=? where email=?",(time.time()-1,EM)); c.commit()
assert "expired" in body(f"/account/link/x{t}")
# ---- someone with only an order link cannot open an existing account
tok2=paid_order(EM,"aa"); req3,j3=browser()
r=req3(f"/account/save/{tok2}",{}); h3=r.read().decode(); assert "already an account" in h3 and r.status==200
assert loc(req3("/account"))=="/account/signin"
assert db().execute("select account_id from orders where token=?",(tok2,)).fetchone()[0]==a["id"]
# ---- deleting an order removes the answers saved from it; deleting the account removes everything
r=req(f"/delete/{tok2}",{}); assert r.status==200
c=db(); assert c.execute("select status from orders where token=?",(tok2,)).fetchone()[0]=="deleted"
assert not c.execute("select 1 from account_saved where from_order=?",(tok2,)).fetchone() and c.execute("select 1 from accounts where id=?",(a["id"],)).fetchone()
assert c.execute("select account_id from orders where token=?",(tok2,)).fetchone()[0] is None
# sign the first browser in again via a fresh link (rate window reset for the test)
c=db(); c.execute("delete from account_links where email=?",(EM,)); c.commit()
req("/account/signin",{"email":EM}); t5=last_link(EM); assert loc(req(f"/account/link/{t5}",{}))=="/account"
assert req("/account/delete",{}).status==303 and db().execute("select 1 from accounts where id=?",(a["id"],)).fetchone()   # needs the tick
r=req("/account/delete",{"sure":"1"}); assert "account is deleted" in r.read().decode()
c=db()
for tb in ("accounts","account_saved","account_sessions"): assert not c.execute(f"select 1 from {tb} where {'id' if tb=='accounts' else 'account_id'}=?",(a["id"],)).fetchone(), tb
assert loc(req("/account"))=="/account/signin"
# ---- retention: accounts unused for 3 years are purged
import store
os.environ["SQLITE_PATH"]=DBP
c=db(); c.execute("insert into accounts(id,email,created,last_seen) values('old1','old@example.com',0,0)"); c.execute("insert into account_saved(account_id,form,data,from_order,saved_at) values('old1','aa','{}','x',0)"); c.commit()
class W:
    def __init__(s,c): s.c=c
    def execute(s,*a): return s.c.execute(*a)
    def commit(s): s.c.commit()
assert ACCT.purge(W(db()))>=1 and not db().execute("select 1 from accounts where id='old1'").fetchone() and not db().execute("select 1 from account_saved where account_id='old1'").fetchone()
# ---- off by default: no routes, no box
if OFF:
    ro,_=browser()
    assert ro("/account/signin",base=OFF).status==404 and ro("/account",base=OFF).status==404 and ro("/account/save/x",{},base=OFF).status==404
print("accounts ok")

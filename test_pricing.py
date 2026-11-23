"""Nov 2026 pricing (Simon, 16 Nov 2026): no package step; 2 options at the pay step, paid at the end, discount box kept.
£19.99 Download, £29.99 Posted to you, with support (postal address asked for on this option only). Stripe amounts are set in
code (price_data), checked here with the Stripe call captured (no network). Internal fulfilment queue at /admin/post."""
import os, sys, json, re, tempfile, sqlite3
D=tempfile.mkdtemp()
for k in ("GEMINI_API_KEY","OPENAI_API_KEY","ANTHROPIC_API_KEY","LLM_API_KEY","RESEND_API_KEY","DATABASE_URL","SUPABASE_URL","ALLOW_LEGACY_TIERS","STRIPE_SECRET_KEY"): os.environ.pop(k,None)
os.environ.update(POSTED_OPTION="1",SQLITE_PATH=D+"/orders.db",OUT_DIR=D+"/out",MAIL_LOG=D+"/mail.log",RETENTION_LOOP="0",CRON_SECRET="c",STRIPE_WEBHOOK_SECRET="w",ADMIN_SECRET="adm",WHOLE_FORM="0",FOLLOWUPS="0")
sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
import subprocess, time, urllib.request, urllib.parse, urllib.error
PORT=int(os.environ.get("PORT_PRICING","8044")); PY=os.path.join(os.environ.get("PY",os.path.join(os.path.dirname(os.path.abspath(__file__)),"../../.venv/bin")),"uvicorn")
srv=subprocess.Popen([PY,"app:app","--port",str(PORT)],cwd=os.path.dirname(os.path.abspath(__file__)),env=dict(os.environ),stdout=open(D+"/server.log","w"),stderr=subprocess.STDOUT)
import atexit; atexit.register(srv.terminate)
class NoRedir(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*a,**k): return None
_op=urllib.request.build_opener(NoRedir)
class Resp:
    def __init__(s,code,headers,body): s.status_code=code; s.headers={k.lower():v for k,v in headers.items()}; s.text=body
class C:
    def _go(s,url,data=None,follow=True):
        r=urllib.request.Request(f"http://localhost:{PORT}{url}",data=urllib.parse.urlencode(data).encode() if data is not None else None)
        try: x=(urllib.request.urlopen if follow else _op.open)(r,timeout=20); return Resp(x.status,dict(x.headers),x.read().decode())
        except urllib.error.HTTPError as e: return Resp(e.code,dict(e.headers),e.read().decode(errors="replace"))
    def get(s,url,follow_redirects=True): return s._go(url,None,follow_redirects)
    def post(s,url,data=None,follow_redirects=True): return s._go(url,data or {},follow_redirects)
c=C()
for _ in range(60):
    try: urllib.request.urlopen(f"http://localhost:{PORT}/healthz",timeout=1); break
    except Exception: time.sleep(0.25)
import app as A, forms
fails=0
def ok(cond,msg):
    global fails
    print(("ok  " if cond else "FAIL"),msg); fails+=0 if cond else 1
BANNED=re.compile(r"\b(Stripe|AI|Gemini|Claude|Anthropic|model)\b|we submit|we send it to DWP|we claim",re.I)
def text(h): return re.sub(r"<script.*?</script>|<[^>]+>"," ",h,flags=re.S)
# tiers
for f in ("aa","dla","pip","pipr"):
    ts=forms.FORMS[f]["tiers"]
    ok([ (t,p) for t,(n,p,_) in ts.items()]==[("1999",1999),("2999",2999)], f"{f}: 2 options at £19.99 and £29.99")
    ok("99" in forms.FORMS[f]["legacy_tiers"] and "199" in forms.FORMS[f]["legacy_tiers"], f"{f}: £99/£199 kept as legacy for existing orders")
# step 2 is 'Before you start', no packages
h=c.get("/?form=aa").text
ok("Before you start" in h and "Choose your package" not in h and "pkgs" not in h, "no package step")
ok("from £19.99" in h and "£99" not in h and "£199" not in h and "Plus" not in text(h), "start page: from £19.99, no £99/£199/Plus")
ok(not BANNED.search(text(h)), "start page wording")
# old £99 links start a £19.99 Download order, consent in the same step
r=c.post("/checkout",data={"form":"pip","tier":"99","health":"1","truth":"1"},follow_redirects=False); tok=r.headers["location"].rsplit("/",1)[1]
db=sqlite3.connect(D+"/orders.db"); db.row_factory=sqlite3.Row
o=db.execute("select * from orders where token=?",(tok,)).fetchone()
ok(o["tier"]=="1999" and o["consent_at"], "old link -> Download tier, consent recorded")
ok(c.post("/checkout",data={"form":"aa","tier":"199"},follow_redirects=False).status_code==303 and db.execute("select tier from orders order by rowid desc").fetchone()[0]=="1999", "£199 can't be bought any more")
# pay step
db.execute("update orders set interview_done_at=1, intake=? where token=?",(json.dumps({"name":"Sam"}),tok)); db.commit()
h=c.get(f"/preview/{tok}").text
ok("How would you like your form?" in h and "£19.99" in h and "£29.99" in h, "pay step: both options")
ok('id=postaddr class=postaddr hidden' in h, "address hidden until Posted is chosen")
ok("discount code" in h.lower(), "discount box kept")
ok("Pay £19.99 and get my form" in h and "Change package" not in h, "pay button shows £19.99")
ok(not BANNED.search(text(h)), "pay step wording")
ok("sign it" in text(h).lower() and "post it back yourself" in text(h), "customer signs and posts it themselves")
ok(c.get(f"/package/{tok}",follow_redirects=False).headers.get("location")==f"/preview/{tok}", "old package page goes to pay")
# Posted without an address: back with an error, nothing paid
r=c.post(f"/pay/{tok}",data={"waive":"1","pack":"2999"},follow_redirects=False)
ok("err=address" in r.headers.get("location",""), "Posted needs an address")
ok(db.execute("select status from orders where token=?",(tok,)).fetchone()[0]=="free", "not paid")
# Stripe Checkout amounts (TEST: the call is captured, nothing sent)
sent=[]
A.stripe=lambda m,p,d=None: (sent.append((m,p,d)) or {"id":"cs_test_x","url":"https://checkout.example/test"})
for t,amt in (("1999",1999),("2999",2999)):
    s=A.stripe_session({**dict(db.execute("select * from orders where token=?",(tok,)).fetchone()),"tier":t})
    d=sent[-1][2]; ok(d["line_items[0][price_data][unit_amount]"]==amt and d["mode"]=="payment" and d["allow_promotion_codes"]=="true", f"checkout session £{amt/100:.2f}, one-off, discount codes allowed")
    ok(d["line_items[0][price_data][product_data][name]"]==("PIP: Download" if t=="1999" else "PIP: Posted to you, with support"), "product name: "+d["line_items[0][price_data][product_data][name]"])
# Posted with an address (DEV: marked paid without a card)
r=c.post(f"/pay/{tok}",data={"waive":"1","pack":"2999","pt_name":"Sam Test","pt_addr1":"1 Test Street","pt_town":"Leeds","pt_postcode":"ls1 1aa"},follow_redirects=False)
o=db.execute("select * from orders where token=?",(tok,)).fetchone()
import time as _t
ok(o["keep_until"] and abs(o["keep_until"]-(_t.time()+forms.SUPPORT_DAYS*86400))<120, "Posted: answers kept until support ends")
ok(o["tier"]=="2999" and o["post_pack"]==1 and json.loads(o["post_to"])["postcode"]=="LS1 1AA" and o["status"]=="paid", "Posted: tier, address and paid")
# Download clears any address
r=c.post("/checkout",data={"form":"aa","tier":"1999","health":"1","truth":"1"},follow_redirects=False); t2=r.headers["location"].rsplit("/",1)[1]
db.execute("update orders set interview_done_at=1, intake=?, post_to=? where token=?",(json.dumps({"name":"Jo"}),json.dumps({"name":"x"}),t2)); db.commit()
c.post(f"/pay/{t2}",data={"waive":"1","pack":"1999"},follow_redirects=False)
o2=db.execute("select * from orders where token=?",(t2,)).fetchone()
ok(o2["tier"]=="1999" and not o2["post_to"] and o2["post_pack"]==0, "Download: no address kept")
# fulfilment queue
h=c.post("/admin/post",data={"key":"adm"}).text
ok("Orders to post (1)" in h and "LS1 1AA" in h and tok[:8] in h, "fulfilment queue lists the Posted order")
ok(c.post("/admin/post",data={"key":"no"}).status_code==403, "queue needs the admin key")
c.post(f"/admin/posted/{tok}",data={"key":"adm"})
ok("Orders to post (0)" in c.post("/admin/post",data={"key":"adm"}).text, "posted orders leave the queue")
ok(forms.RETURN_ADDR["aa"]=="Freepost DWP Attendance Allowance" and A.sign_pages("aa"), "return address and sign-here pages for AA")
# support reminders (cron): one email per step, none after support ends
db.execute("update orders set email='sam@example.com', paid_at=? where token=?",(_t.time()-11*86400,tok)); db.commit()
r=urllib.request.urlopen(urllib.request.Request(f"http://localhost:{PORT}/cron/support",data=b"",headers={"x-cron-secret":"c"}),timeout=20); n1=json.load(r)["sent"]
r=urllib.request.urlopen(urllib.request.Request(f"http://localhost:{PORT}/cron/support",data=b"",headers={"x-cron-secret":"c"}),timeout=20); n2=json.load(r)["sent"]
ok(n1==1 and n2==0, f"support reminder sent once ({n1},{n2})")
db.execute("update orders set paid_at=? where token=?",(_t.time()-200*86400,tok)); db.commit()
r=urllib.request.urlopen(urllib.request.Request(f"http://localhost:{PORT}/cron/support",data=b"",headers={"x-cron-secret":"c"}),timeout=20)
ok(json.load(r)["sent"]==0, "no reminders after support ends")
print("FAILURES:",fails); sys.exit(1 if fails else 0)

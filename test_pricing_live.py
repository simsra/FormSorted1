"""Live pricing (Simon, 23 Nov 2026): only the £19.99 Download is offered. Posted to you, with support (£29.99) is hidden
(POSTED_OPTION off) until its Terms and a posting provider are OK'd. Stripe call captured, nothing sent."""
import os, sys, json, re, tempfile, sqlite3
D=tempfile.mkdtemp()
for k in ("GEMINI_API_KEY","OPENAI_API_KEY","ANTHROPIC_API_KEY","LLM_API_KEY","RESEND_API_KEY","DATABASE_URL","SUPABASE_URL","ALLOW_LEGACY_TIERS","STRIPE_SECRET_KEY"): os.environ.pop(k,None)
os.environ.update(POSTED_OPTION="0",SQLITE_PATH=D+"/orders.db",OUT_DIR=D+"/out",MAIL_LOG=D+"/mail.log",RETENTION_LOOP="0",CRON_SECRET="c",STRIPE_WEBHOOK_SECRET="w",ADMIN_SECRET="adm",WHOLE_FORM="0",FOLLOWUPS="0")
sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
import subprocess, time, urllib.request, urllib.parse, urllib.error
PORT=int(os.environ.get("PORT_PRICING_LIVE","8046")); PY=os.path.join(os.environ.get("PY",os.path.join(os.path.dirname(os.path.abspath(__file__)),"../../.venv/bin")),"uvicorn")
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
POSTED=re.compile(r"Posted|29\.99|post it to you|prepaid envelope|Support until",re.I)
for f in ("aa","dla","pip","pipr"):
    ts=forms.FORMS[f]["tiers"]
    ok([(t,p) for t,(n,p,_) in ts.items()]==[("1999",1999)], f"{f}: one option, Download £19.99")
    ok(forms.options(f)==[] and forms.tier_info(f,"2999")[1]==2999, f"{f}: nothing to choose; 2999 still described for any old order")
ok(forms.FORMS["atw"]["tiers"]["49"][1]==4900 and forms.FORMS["atw"]["tiers"]["79"][1]==7900 and forms.FORMS["bb"]["tiers"]["29"][1]==2900, "Access to Work and Blue Badge prices unchanged")
h=c.get("/?form=aa").text
ok("Before you start" in h and "£19.99" in h and "from £19.99" not in h and "£99" not in h and not POSTED.search(text(h)), "start page: £19.99, no Posted")
ok(not BANNED.search(text(h)), "start page wording")
r=c.post("/checkout",data={"form":"aa","tier":"2999","health":"1","truth":"1"},follow_redirects=False); tok=r.headers["location"].rsplit("/",1)[1]
db=sqlite3.connect(D+"/orders.db"); db.row_factory=sqlite3.Row
ok(db.execute("select tier from orders where token=?",(tok,)).fetchone()[0]=="1999", "a 2999 link starts a Download order")
db.execute("update orders set interview_done_at=1, intake=? where token=?",(json.dumps({"name":"Sam"}),tok)); db.commit()
h=c.get(f"/preview/{tok}").text
ok("How would you like your form?" not in h and "postaddr" not in h and "Download" in h and "£19.99" in h, "pay step: Download only, no address")
ok("Pay £19.99 and get my form" in h and "discount code" in h.lower(), "pay button £19.99, discount box kept")
ok(not POSTED.search(text(h)) and not BANNED.search(text(h)), "pay step: no Posted, wording ok")
c.post(f"/pay/{tok}",data={"waive":"1","pack":"2999","pt_name":"X","pt_addr1":"1 St","pt_town":"Leeds","pt_postcode":"LS1 1AA"},follow_redirects=False)
o=db.execute("select * from orders where token=?",(tok,)).fetchone()
ok(o["tier"]=="1999" and not o["post_to"] and o["post_pack"]==0, "pack=2999 is ignored: still Download, no address kept")
sent=[]
A.stripe=lambda m,p,d=None: (sent.append((m,p,d)) or {"id":"cs_test_x","url":"https://checkout.example/test"})
A.stripe_session(dict(o)); d=sent[-1][2]
ok(d["line_items[0][price_data][unit_amount]"]==1999 and d["allow_promotion_codes"]=="true" and d["line_items[0][price_data][product_data][name]"]=="Attendance Allowance: Download", "checkout session £19.99, discount codes allowed")
import chatui
ok(not POSTED.search(chatui.FAQ_EXTRA[0][1]) and "£19.99" in chatui.FAQ_EXTRA[0][1], "chat FAQ: £19.99 only")
kb=open(os.path.join(os.path.dirname(os.path.abspath(__file__)),"assist_kb.json")).read()
ok("29.99" not in kb and "Posted to you" not in kb, "assistant help list: no Posted option")
print("FAILURES:",fails); sys.exit(1 if fails else 0)

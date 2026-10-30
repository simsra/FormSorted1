"""Per-connection start limit with RATE_LIMIT_ALLOW_IPS (30 Oct 2026).
Starts two local servers (own SQLite, mock mode, FREE_PER_IP_DAY=2): an allowed connection can start more than 2 forms,
any other connection is still stopped after 2. The client IP is read the same way as live (CF-Connecting-IP behind Render)."""
import os, subprocess, sys, tempfile, time, urllib.request, urllib.parse, urllib.error
PY=os.path.join(os.environ.get("PY","../../.venv/bin"),"uvicorn"); D=tempfile.mkdtemp(); PORT=8043
env={k:v for k,v in os.environ.items() if k not in ("GEMINI_API_KEY","OPENAI_API_KEY","ANTHROPIC_API_KEY","LLM_API_KEY","RESEND_API_KEY","DATABASE_URL","SUPABASE_URL")}
env.update(SQLITE_PATH=D+"/orders.db",OUT_DIR=D+"/out",MAIL_LOG=D+"/mail.log",RETENTION_LOOP="0",FREE_PER_IP_DAY="2",FREE_PER_DAY_TOTAL="100",
           RATE_LIMIT_ALLOW_IPS=" 203.0.113.7 , 2001:db8::1",CRON_SECRET="c",STRIPE_WEBHOOK_SECRET="w")
srv=subprocess.Popen([PY,"app:app","--port",str(PORT)],env=env,stdout=open(D+"/server.log","w"),stderr=subprocess.STDOUT)
class NoRedir(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*a,**k): return None
op=urllib.request.build_opener(NoRedir)
def start(ip):
    r=urllib.request.Request(f"http://localhost:{PORT}/checkout",data=urllib.parse.urlencode({"tier":"99","form":"aa"}).encode(),headers={"cf-connecting-ip":ip})
    try: x=op.open(r,timeout=10); return x.status, x.read().decode()
    except urllib.error.HTTPError as e: return e.code, ""
try:
    for _ in range(40):
        try: urllib.request.urlopen(f"http://localhost:{PORT}/healthz",timeout=1); break
        except Exception: time.sleep(0.25)
    # allowed connections (IPv4 and IPv6): well past the limit of 2
    for ip in ("203.0.113.7","2001:db8::1"):
        for i in range(5):
            s,b=start(ip); assert s==303, (ip,i,s,b[:200])
    # anyone else: 2 then the limit page
    other="198.51.100.9"
    assert start(other)[0]==303 and start(other)[0]==303
    s,b=start(other); assert s==200 and "started a few already today" in b, (s,b[:200])
    # a near miss is not allowed
    for i in range(2): start("203.0.113.70")
    s,b=start("203.0.113.70"); assert s==200 and "started a few already today" in b
    print("rate-limit allowlist: OK")
finally:
    srv.terminate()

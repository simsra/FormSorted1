"""'Not Secure' fix (30 Oct 2026): with an https PUBLIC_URL every response tells browsers to use https only (HSTS),
plain-http page requests are sent to the https address, and health checks, webhooks and cron are never redirected.
Run against a server started with PUBLIC_URL=https://app.formsorted.com."""
import sys, urllib.request, urllib.error
B=sys.argv[1] if len(sys.argv)>1 else "http://localhost:8039"
class NoRedir(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*a,**k): return None
op=urllib.request.build_opener(NoRedir)
def get(path,proto=None):
    r=urllib.request.Request(B+path,headers={"x-forwarded-proto":proto} if proto else {})
    try: x=op.open(r,timeout=10); return x.status,dict(x.headers)
    except urllib.error.HTTPError as e: return e.code,dict(e.headers)
s,h=get("/","https"); assert s==200 and h.get("strict-transport-security")=="max-age=31536000", (s,h)
s,h=get("/start?form=aa","https"); assert h.get("strict-transport-security"), h
s,h=get("/intake?s=conds&x=1","http"); assert s==301 and h["location"]=="https://app.formsorted.com/intake?s=conds&x=1", (s,h)
for p in ("/healthz",):
    s,h=get(p,"http"); assert s==200, (p,s)
print("https only + HSTS: OK")

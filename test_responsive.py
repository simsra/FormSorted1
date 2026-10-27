"""/healthz must stay responsive while an approve with a slow AI grounding call is running.
Run against a DEV server started with MOCK_GROUND_SLOW=6 (see run_test.sh)."""
import json, sys, time, threading, urllib.request, urllib.parse
B=sys.argv[1] if len(sys.argv)>1 else "http://localhost:8033"
class NoRedir(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*a,**k): return None
op=urllib.request.build_opener(NoRedir)
def req(path,data=None,js=None,timeout=60):
    if js is not None: r=urllib.request.Request(B+path,json.dumps(js).encode(),{"Content-Type":"application/json"})
    else: r=urllib.request.Request(B+path,urllib.parse.urlencode(data).encode() if data is not None else None)
    try: return op.open(r,timeout=timeout)
    except urllib.error.HTTPError as e: return e
tok=req("/checkout",{"tier":"99","form":"pipr"}).headers["location"].split("/")[-1]
req(f"/consent/{tok}",{"health":"on","digital":"on","truth":"on"})
n=0; j=json.load(req(f"/api/{tok}/message",js={"text":""}))
while not j["done"]: n+=1; j=json.load(req(f"/api/{tok}/message",js={"text":f"Sample answer {n}"}))
req(f"/api/{tok}/finish",{}); req(f"/pay/{tok}",{"waive":"on"}); req(f"/start/{tok}"); req(f"/prepare/{tok}")
out={}
def approve(): t=time.time(); req(f"/approve/{tok}",{"x":"1"},timeout=120); out["approve"]=time.time()-t
th=threading.Thread(target=approve); th.start(); time.sleep(1.0)
worst=0
for _ in range(5):
    t=time.time(); assert req("/healthz",timeout=10).status==200; worst=max(worst,time.time()-t); time.sleep(0.5)
th.join(); assert out["approve"]>=5, out          # the approve really was slow
assert worst<1.0, f"healthz blocked for {worst:.2f}s during approve"
print(f"responsive ok: healthz worst {worst*1000:.0f} ms while approve took {out['approve']:.1f}s")

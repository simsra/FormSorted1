"""Preparing the form after payment: a waiting page with real steps straight away (no blank page), drafting in the background,
the answer check done ahead so approve opens fast, and the site stays responsive. DEV server with MOCK_DRAFT_SLOW=4 MOCK_GROUND_SLOW=3."""
import json, sys, time, urllib.request, urllib.parse
B=sys.argv[1] if len(sys.argv)>1 else "http://localhost:8034"
class NoRedir(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*a,**k): return None
op=urllib.request.build_opener(NoRedir)
def req(path,data=None,timeout=60):
    r=urllib.request.Request(B+path,urllib.parse.urlencode(data).encode() if data is not None else None)
    try: return op.open(r,timeout=timeout)
    except urllib.error.HTTPError as e: return e
from forms import FORMS
import intake as I
tok=req("/checkout",{"tier":"99","form":"aa"}).headers["location"].split("/")[-1]
req(f"/consent/{tok}",{"health":"on","truth":"on"})
secs=[k for k,_ in I.SECTIONS["aa"]]
for s in secs: r=req(f"/intake/{tok}",{"sec":s,"nav":"next"})
assert r.headers["location"]==f"/preview/{tok}", r.headers["location"]
assert req(f"/api/{tok}/progress").status==402                          # nothing before payment
req(f"/pay/{tok}",{"waive":"on"}); assert req(f"/start/{tok}").headers["location"]==f"/uploads/{tok}"
t=time.time(); assert req(f"/uploads/{tok}/done",{}).headers["location"]==f"/prepare/{tok}"; assert time.time()-t<1.0
t=time.time(); r=req(f"/prepare/{tok}"); dt=wait_ms=time.time()-t; h=r.read().decode()
assert r.status==200 and dt<1.5, (r.status,dt)                         # waiting page shows at once
assert "We're filling in your form" in h and "Checking every answer against what you told us" in h and f"/api/{tok}/progress" in h
low=h.lower(); assert "stripe" not in low and " ai " not in low and "artificial" not in low and "model" not in low
assert req("/healthz",timeout=2).status==200
stages=[]
while True:
    j=json.load(req(f"/api/{tok}/progress")); stages.append(j["stage"])
    if j.get("next"): break
    assert time.time()-t<20, stages; time.sleep(0.3)
assert j["next"]==f"/deadline/{tok}" and "draft" in stages, stages
assert req(f"/prepare/{tok}").headers["location"]==f"/deadline/{tok}"  # done: straight on, never drafted twice
time.sleep(3.5)                                                         # customer reads the deadline page; the check finishes meanwhile
t=time.time(); ap=req(f"/approve/{tok}").read().decode(); dt=time.time()-t
assert "Check and approve every answer" in ap and dt<1.0, dt           # answer check was done ahead
print(f"prepare ok: waiting page in {wait_ms*1000:.0f} ms, stages {sorted(set(stages))}, approve {dt:.2f}s")

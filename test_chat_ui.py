"""16 Nov 2026 chat look: same steps, same posts, no banned words, message bar off where NI/bank details are typed,
and CHAT_UI=0 still gives the step-by-step look. No network (in-process, mock mode, own SQLite)."""
import os, tempfile, re, importlib
T=tempfile.mkdtemp(); os.environ.update(SQLITE_PATH=os.path.join(T,"t.db"),OUT_DIR=os.path.join(T,"out"),WF_LOOKUPS="0",DATABASE_URL="",SUPABASE_URL="",FREE_PER_IP_DAY="500")
for k in ("ANTHROPIC_API_KEY","OPENAI_API_KEY","GEMINI_API_KEY","STRIPE_SECRET_KEY","CHAT_UI"): os.environ.pop(k,None)
import sys, urllib.request, urllib.parse
B=sys.argv[1]; B0=sys.argv[2] if len(sys.argv)>2 else None   # chat server, and one started with CHAT_UI=0
class R:
    def __init__(s,text,loc=None): s.text=text; s.headers={"location":loc}
class NoRedir(urllib.request.HTTPRedirectHandler):
    def redirect_request(s,*a,**k): return None
class Client:
    def __init__(s,base): s.b=base
    def get(s,u): return R(urllib.request.urlopen(s.b+u).read().decode())
    def post(s,u,data,follow_redirects=True):
        body=urllib.parse.urlencode(data).encode()
        if follow_redirects: return R(urllib.request.urlopen(urllib.request.Request(s.b+u,body)).read().decode())
        op=urllib.request.build_opener(NoRedir)
        try: op.open(urllib.request.Request(s.b+u,body)); return R("")
        except urllib.error.HTTPError as e: return R("",e.headers.get("location"))
C=Client(B); FAIL=0
def check(ok,msg):
    global FAIL; print(("ok  " if ok else "FAIL")+" "+msg); FAIL+=0 if ok else 1
BANNED=re.compile(r"\b(AI|A\.I\.|artificial intelligence|Stripe|Gemini|Google|Claude|Anthropic|model|we claim|we submit)\b")
def visible(h):
    h=re.sub(r"<script.*?</script>|<style.*?</style>","",h,flags=re.S); return re.sub(r"<[^>]+>"," ",h)
def clean(h,where):
    m=BANNED.search(visible(h)); check(not m,f"{where}: no banned words ({m.group(0) if m else ''})")
    check("FormSorted</strong> is an independent online form-filling service. Not affiliated with DWP, GOV.UK or any government body. We can't guarantee an award or outcome." in h,f"{where}: footer disclaimer")
    check('href="https://formsorted.com/privacy.html"' in h and 'href="https://formsorted.com/terms.html"' in h,f"{where}: Privacy and Terms links")
    links=[u for u in re.findall(r'href="?(https?://[^"\s>]+)',h) if not re.match(r"https://(app\.)?formsorted\.com",u)]
    check(not links,f"{where}: no outbound links {links[:2]}")
    check("Sidechain" not in h and "14661600" not in h,f"{where}: no company details")
h=C.get("/").text; clean(h,"home")
check("Hi there," in h and "How can I help with your form?" in h and "Something else" in h and "Not sure which form?" in h and set(re.findall(r'class="qchip[^"]*" href="/\?form=(\w+)"',h))=={"aa","pip","pipr","dla","bb","atw"},"home: empty assistant state, a chip per form, Not sure and Something else")
check("/static/ui.css" in h and "app.css" not in h and "chat.css" not in h and "class=hdr" not in h and 'class="indep"' not in h and "Lexend" not in h,"home: Untitled UI stylesheet only, none of the old template")
check("class=vsteps" in h and "class=mbar" in h and 'placeholder="Ask a question or name your form"' in h,"home: step list (desktop), slim progress (phone), message bar wording")
check("Step 1 of 5: <strong>Choose your form</strong>" in h and "class=stepper" not in h and "id=composer" in h and "id=cfaq" in h,"home: quiet progress, no stepper, message bar")
check("£" not in visible(h),"home: no prices on step 1")
p=C.get("/?form=dla").text; clean(p,"package")
check("Step 2 of 5: <strong>Before you start</strong>" in p and p.count("action=/checkout")==1 and "Which package would you like?" not in p and 'class="turn me"' in p and "from £19.99" in p,"start (Nov 2026): the form as their bubble, no package choice, one /checkout post with the consent boxes")
r=C.post("/checkout",data={"form":"dla","tier":"99"},follow_redirects=False); tok=r.headers["location"].rsplit("/",1)[1]
s=C.get(f"/start/{tok}").text; clean(s,"before you start"); check(f"action=/consent/{tok}" in s and "name=health" in s and "name=truth" in s,"consent: same two boxes, same post")
C.post(f"/consent/{tok}",data={"health":"1","truth":"1"},follow_redirects=False)
i=C.get(f"/intake/{tok}").text; clean(i,"questions")
check("Part 1 of 10" in i and "Save and finish later" in i and ("Help with this question" in i or "convo.js" in i) and "Something else" in i and f"action=/intake/{tok}" in i,"questions: part progress, save later, help, Something else, same post")
check('form=qform name=nav value=save' in i and "class=crow" in i,"questions: Save and finish later sits under the message bar, same post")
check("QS_JS" not in i and "/static/chat.js" in i and "id=qs" in i,"questions: chat script runs the one-at-a-time view")
# placeholders on the typed follow-ups are real examples (unchanged)
d=C.post(f"/intake/{tok}",data={"sec":"about","rel":"Mum","name":"Leo","age":"5to15","nav":"next"},follow_redirects=True).text
check("Part 2 of 10" in d and "Part 1 of 10 saved" in d,"next part: earlier part shown as saved")
# NI / bank page: no message bar (those details go only onto the PDF)
import app as A
os.environ["CHAT_UI"]="1"
fake=A.chat_page('<form method=post action=/details/x><input name=ni></form>',"Last details",True).body.decode()
check("id=composer" not in fake and "id=cfaq" not in fake,"details page: no message bar")
# a missing or expired link in a browser: a page in the same look, not raw JSON
try: urllib.request.urlopen(urllib.request.Request(B+"/start/nope",headers={"Accept":"text/html"})); nf=""
except urllib.error.HTTPError as e: nf=e.read().decode() if e.code==404 else ""
check("can't find that page" in nf and "/static/ui.css" in nf,"404: friendly page in the new look")
try: urllib.request.urlopen(B+"/api/nope/info"); aj=""
except urllib.error.HTTPError as e: aj=e.read().decode()
check(aj.startswith("{"),"404 on the API stays JSON")
# switch back to the old look without a code change
if B0:
    o=Client(B0).get("/").text; check("class=stepper" in o and "How can I help" not in o and "chat.css" not in o and "ui.css" not in o,"CHAT_UI=0: step-by-step look")
print("FAILED" if FAIL else "all ok"); raise SystemExit(1 if FAIL else 0)

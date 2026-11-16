"""16 Nov 2026 live help ('ask a question so they never get stuck'). Runs against a server started with ASSIST_PER_DAY=5 and ASSIST_LOG
(mock mode: no keys, so replies come from the fixed help list). Checks: a question gets a short reply from the help notes, an unknown
question gets the 'email hello@formsorted.com' reply, the fixed post-check strips banned words / links / promises / 'we claim', NI and
bank details are masked before logging and never in the answers sent, the daily limit, and the browser only adds a note after Yes."""
import os, sys, re, json, urllib.request, tempfile
for k in ("ANTHROPIC_API_KEY","OPENAI_API_KEY","GEMINI_API_KEY"): os.environ.pop(k,None)
os.environ.setdefault("SQLITE_PATH",os.path.join(tempfile.mkdtemp(),"t.db"))
B=sys.argv[1]; LOG=sys.argv[2]
import assist as A
FAIL=0
def check(ok,msg):
    global FAIL; print(("ok  " if ok else "FAIL")+" "+msg); FAIL+=0 if ok else 1
def post(body):
    r=urllib.request.Request(B+"/api/assist",json.dumps(body).encode(),{"Content-Type":"application/json"})
    try: return 200,json.loads(urllib.request.urlopen(r).read())
    except urllib.error.HTTPError as e: return e.code,None
BANNED=re.compile(r"\b(AI|artificial intelligence|Stripe|Gemini|Google|Claude|Anthropic|OpenAI|model|we claim|we submit)\b")
# ---- the post-check on its own ----
r,d=A.post_check("You can stop and come back later. Our AI model will help. Visit https://www.gov.uk for more. We will submit it for you. You'll get £300 a week. Citizens Advice can help for free. Our team checks every form.","stop and come back later")
check(r=="You can stop and come back later.",f"post-check keeps only the safe sentence ({r!r})")
check(len(d)==6,"post-check drops AI/model, link, 'we submit', an amount not in the notes, a charity, and 'our team checks'")
r,_=A.post_check("Done for you is £99. Email hello@formsorted.com.","Done for you £99")
check("£99" in r and "hello@formsorted.com" in r,"amounts that ARE in the help notes and our email address stay")
long=" ".join(["This is a short sentence about the question."]*20); r,_=A.post_check(long,long)
check(len(r.split())<=A.MAX_WORDS,"replies are capped (about 90 words)")
# ---- privacy ----
m=A.mask("my NI is QQ 12 34 56 C and sort code 12-34-56 account 12345678")
check("QQ" not in m and "12-34-56" not in m and "12345678" not in m,f"NI number, sort code and account number masked ({m})")
t=A.answers_text({"name":"Leo","ni":"QQ123456C","bank_sort":"123456","acc_no":"12345678","rows":["washing"],"wf":{"p_first":"Carla"}})
check("QQ123456C" not in t and "12345678" not in t and "Leo" in t,"answers sent to the helper never include NI or bank fields")
# ---- the endpoint ----
code,j=post({"text":"When do I pay?","q":"Does your child need help washing?","hint":"","options":["Yes","No"],"box":False})
check(code==200 and j["kind"]=="question" and "end" in j["reply"].lower(),f"a question gets a reply from the help list ({j and j['reply'][:60]!r})")
check(not BANNED.search(j["reply"]),"reply has no banned words")
code,j=post({"text":"What's the weather like in Leeds tomorrow?","q":"Does your child need help washing?"})
check(code==200 and "hello@formsorted.com" in j["reply"],"something not in the notes: says so and gives hello@formsorted.com")
code,j=post({"text":"what does this mean, I don't understand","q":"How many nights a week?","hint":"A bad night is when they need you to get up to help them."})
check(code==200 and "bad night" in j["reply"].lower(),"'what does this mean' explains with the help text of the question on screen")
code,_=post({"text":""}); check(code==400,"empty message refused")
code,j=post({"text":"My NI number is QQ 12 34 56 C, is that ok?","token":"nope-not-a-real-token-123456"})
check(code==200,"unknown token: still answered (no order data used)")
code,j=post({"text":"Can I stop and come back?"})
code,j=post({"text":"Can I stop and come back?"})
check(code==200 and j.get("limited"),"daily limit (ASSIST_PER_DAY) gives a polite stop, not an error")
log=open(LOG).read()
check("QQ 12 34 56 C" not in log and "QQ123456C" not in log and "[NI number]" in log,"question log masks NI numbers")
check(all(set(json.loads(l))>={"q","reply","model","ms"} for l in log.splitlines() if '"error"' not in l),"each logged question has the reply, model and time (for new help entries)")
# ---- the question log is deleted after 90 days (Privacy notice) ----
import time as _t
lp=os.path.join(tempfile.mkdtemp(),"q.jsonl"); open(lp,"w").write(json.dumps({"t":_t.time()-91*86400,"q":"old"})+"\n"+json.dumps({"t":_t.time()-2*86400,"q":"new"})+"\n")
A.prune(lp); kept=[json.loads(l)["q"] for l in open(lp)]
check(kept==["new"],f"questions older than 90 days are deleted from the log ({kept})")
# ---- the browser side ----
js=open(os.path.join(os.path.dirname(os.path.abspath(__file__)),"static","chat.js")).read()
# v3 (Simon 16 Nov 22:43): the bar is for questions only, so the helper never writes into an answer (no 'Add this to your answer?')
check("/api/assist" in js and "Add this to your answer?" not in js and "data-add" not in js and "box.value=" not in js[js.index("function ask("):js.index("/* ---- which form")],"chat.js asks the helper; it never writes into an answer box")
check("Sorry, I couldn\\'t answer that just now, you can carry on or email" in js,"graceful error text")
check("Back to the question:" in js,"the question on screen is shown again after a reply")
check(not BANNED.search(re.sub(r"/\*.*?\*/","",js,flags=re.S).replace("model","")) ,"chat.js customer text has no banned words")
print("FAILURES:",FAIL); sys.exit(1 if FAIL else 0)

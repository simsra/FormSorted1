"""16 Nov 2026 (Simon): the questions as a conversation. Same questions and posts as before; convo.js only changes how they show.
Checks: the conversational script is on the question pages (and off with CONVO=0), its wording has no banned words, typed words
need a Yes before they fill an answer, the 'Here's what you told me' summary before paying shows only what was given (never NI or
bank details), and Change from the summary comes straight back to it."""
import os, re, sys, tempfile, urllib.request, urllib.parse, html
T=tempfile.mkdtemp(); os.environ.update(SQLITE_PATH=os.path.join(T,"t.db"),OUT_DIR=os.path.join(T,"out"),WF_LOOKUPS="0",DATABASE_URL="",SUPABASE_URL="")
for k in ("ANTHROPIC_API_KEY","OPENAI_API_KEY","GEMINI_API_KEY","STRIPE_SECRET_KEY","CHAT_UI","CONVO"): os.environ.pop(k,None)
B=sys.argv[1]; FAIL=0
def check(ok,msg):
    global FAIL; print(("ok  " if ok else "FAIL")+" "+msg); FAIL+=0 if ok else 1
class NoRedir(urllib.request.HTTPRedirectHandler):
    def redirect_request(s,*a,**k): return None
def get(u): return urllib.request.urlopen(B+u).read().decode()
def post(u,data):
    body=urllib.parse.urlencode(data,doseq=True).encode()
    try: urllib.request.build_opener(NoRedir).open(urllib.request.Request(B+u,body)); return ""
    except urllib.error.HTTPError as e: return e.headers.get("location") or ""
BANNED=re.compile(r"\b(AI|A\.I\.|artificial intelligence|Stripe|Gemini|Google|Claude|Anthropic|model|we claim|we submit|an adviser checks|a person checks)\b")
js=open(os.path.join(os.path.dirname(os.path.abspath(__file__)),"static","convo.js")).read()
strings=re.findall(r"'((?:[^'\\]|\\.)*)'",re.sub(r"/\*.*?\*/","",js,flags=re.S))
bad=[s for s in strings if BANNED.search(s)]
check(not bad,f"convo.js: no banned words in what customers see {bad[:2]}")
check("Shall I put that down as your answer, in your words?" in js and "data-c=own" in js and "Yes, use my words" in js,"typed words: a Yes is asked before they fill an answer")
cu=js[js.index("function confirmUse"):js.index("function say(")]
check(js.count("u.ebox.value=v")==1 and "u.ebox.value=v" in cu and "nx.boxes[0].value=v" in cu and "if(c=='no')" in cu and cu.index("if(c=='no')")<cu.index("u.ebox.value=v"),"typed words only go into an answer box inside the Yes handler")
check("You told me earlier" in js and "Yes, use it" in js,"don't ask twice: an earlier typed answer is offered, not assumed")
check("Back to the question:" in js,"a question mid-way gets an answer, then the question again")
# a whole DLA order through the same posts
loc=post("/checkout",{"form":"dla","tier":"99"}); tok=loc.rsplit("/",1)[1]
post(f"/consent/{tok}",{"health":"1","truth":"1"})
i=get(f"/intake/{tok}")
check('class="uapp chat convo"' in i and "/static/convo.js" in i and "/static/chat.js" in i,"questions: conversational script on the question page")
check("class=qform" not in i and i.count("<fieldset class=iq>")>=3,"questions: the same question markup is underneath")
check("form-card" not in i and "class=qcard" not in i,"questions: no form cards from the server")
import json
secs=[]; n=0
while n<20:
    n+=1; page=get(f"/intake/{tok}"); sec=re.search(r"name=sec value=(\w+)",page).group(1); secs.append(sec)
    data={"sec":sec,"nav":"next"}
    if sec=="about": data.update(rel="Mum",name="Leo",age="5to15")
    if sec=="child": data.update(first="Leo",surname="Testcase")
    if "data-last=1" in page:
        check("Here's what you told me" in open(os.path.join(os.path.dirname(os.path.abspath(__file__)),"static","convo.js")).read(),"end of the questions: Here's what you told me")
        j=json.loads(get(f"/api/{tok}/told?cur={sec}")); P={p["sec"]:p for p in j["parts"]}
        flat=" ".join(q+" "+" ".join(a) for p in j["parts"] for q,a in p["rows"])
        check(len(j["parts"])==10 and P[sec]["here"] and not P[sec]["rows"],"summary: every part, this part shown above it")
        check("Who are you to the child?" in flat and "Mum" in flat and "Leo" in flat and "Testcase" in flat,"summary: their answers, word for word")
        check("Dad" not in flat and "Grandparent" not in flat,"summary: nothing they didn't tap")
        e=get(f"/intake/{tok}?s=about&ret=1")
        check("name=ret value=1" in e and "Back to your summary" in e,"Change from the summary: one part, then straight back")
        l2=post(f"/intake/{tok}",{"sec":"about","nav":"next","ret":"1","rel":"Dad","name":"Leo","age":"5to15"})
        check(l2.endswith(f"/intake/{tok}?s={sec}"),f"after Change: back to the summary ({l2})")
        j=json.loads(get(f"/api/{tok}/told?cur={sec}")); flat=" ".join(" ".join(a) for p in j["parts"] for q,a in p["rows"])
        check("Dad" in flat and "Mum" not in flat,"summary shows the changed answer")
    loc=post(f"/intake/{tok}",data)
    if "/intake/" not in loc: break
check("/uploads/" in loc,"whole form: questions then evidence, as before")
post(f"/uploads/{tok}/done",{"nav":"next"})
p=get(f"/preview/{tok}")
check("Pay £" in p and "discount code" in p.lower() and "Testcase" not in p,"pay step unchanged (and still no answers on it before paying)")
# NI and bank details never appear in the summary
import told
P=told._P(); P.feed('<fieldset class=iq><legend>National Insurance number</legend><input name=ni value="QQ123456C"><input name="bank_acct" value="12345678"><input name="sort" value="112233"></fieldset>')
check(not P.out,"summary: never shows NI or bank details")
# CONVO=0: the one-question cards inside the chat, as on the live site
os.environ["CHAT_UI"]="1"; os.environ["CONVO"]="0"
import app as A
h=A.chat_page('<form id=qform method=post action=/intake/x><div class=qs id=qs></div></form>',"Q",True).body.decode()
check("convo.js" not in h and 'class="uapp chat"' in h,"CONVO=0: the earlier chat look")
os.environ["CONVO"]="1"; h=A.chat_page('<form id=qform method=post action=/intake/x><div class=qs id=qs></div></form>',"Q",True).body.decode()
check("convo.js" in h,"CONVO=1: the conversation")
# v2 (16 Nov, 21:32): every choice list has Something else; one Send per question group (no longer than live main)
check("cluster-send" in js and "Skip this question" in js,"v2: one Send per question group; a single tap question moves on with the tap")
loc=post("/checkout",{"form":"aa","tier":"99"}); t2=loc.rsplit("/",1)[1]; post(f"/consent/{t2}",{"health":"1","truth":"1"})
a=get(f"/intake/{t2}")
check('name="who_xon"' in a,"v2: Who is this form for? has Something else")
post(f"/intake/{t2}",{"sec":"about","nav":"next","who_xon":"1","who_x":"My aunt Jo","name":"Jo"})
c=get(f"/intake/{t2}?s=conds")
check("oc_xon" in c,"v2: the conditions list has Something else (opens the box to type it)")
tj=json.loads(get(f"/api/{t2}/told?cur=conds"))
check("My aunt Jo" in json.dumps(tj),"v2: their own words for who it is for are kept word for word")
import intake as I2, wholeform as W2
I2.X  # loaded
d2={"who":"other","else":{"who":"My aunt Jo"},"name":"Jo"}
check("This form is for: My aunt Jo" in json.dumps(I2.topic_texts("aa",d2)),"v2: the writer gets their words, not a guessed choice")
_,_,notes=W2.pdf_values("aa",{"wf":{"test_more1_x":"Maybe one more scan, not sure"}})
check(any("Maybe one more scan" in n for n in notes),"v2: Not sure / something else on Another test? reaches the form notes")
qh=W2.render_q(W2.Q("x1","Plain yes or no?","radio",W2.YN),{}) if hasattr(W2,"render_q") else ""
check("Not sure / something else" in qh,"v2: plain Yes/No questions offer Not sure / something else")
print("FAILED" if FAIL else "all ok"); raise SystemExit(1 if FAIL else 0)

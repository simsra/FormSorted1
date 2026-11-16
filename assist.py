"""Live help in the chat (Simon, 16 Nov 2026: 'ask a question so they never get stuck').
The customer types into the message bar at any step (not the NI/bank page). Clear answers to the question on screen are filled in by
the browser (chat.js); questions, and text that could be either, come here.
Replies are grounded ONLY in: our help list and guide-page FAQs (assist_kb.json), the help text of the question on screen, and the
customer's own answers so far. Anything else: we say we can't answer it here and give hello@formsorted.com.
Models: ASSIST_MODELS (default claude-haiku-5-5, then claude-sonnet-5-5: the reply has to come back in a few seconds); if every Claude
model fails, ASSIST_FALLBACK (default openai:gpt-5.4-mini, "" = off) with the same prompt and the same checks.
Each reply then goes through the OpenAI grounding check (llm.GROUND_CHAIN, same as the writer) and a fixed post-check
(no banned words, links, outcome promises, 'we claim/submit', charities). Unsupported sentences are removed; if nothing is left we
give the plain 'not covered' reply. Nothing is ever added to the form here: a suggested note is only offered as 'Add this to your
answer?' and the browser adds it only if the customer taps Yes.
Limits: ASSIST_PER_DAY (30) questions per order (or connection on step 1), ASSIST_MAX_CHARS (600) in, ~90 words out.
Log: ASSIST_LOG (jsonl) keeps the question (NI numbers, sort codes, account numbers and long digit runs masked), the reply, model and
time, so we can add help entries. Never the customer's answers."""
import os, re, json, time, threading
import claude, llm
from grounding import check_answer, sentences
HERE=os.path.dirname(os.path.abspath(__file__))
KB=json.load(open(os.path.join(HERE,"assist_kb.json")))
CHAIN=claude._chain("ASSIST_MODELS","claude-haiku-5-5,claude-sonnet-5-5")
PER_DAY=int(os.getenv("ASSIST_PER_DAY","30")); MAX_IN=int(os.getenv("ASSIST_MAX_CHARS","600")); MAX_WORDS=90
TIMEOUT=int(os.getenv("ASSIST_TIMEOUT","20"))
EMAIL="hello@formsorted.com"
NOT_COVERED=f"I can't answer that one here, sorry. You can email {EMAIL}. Your answers so far are kept."
FALLBACK=llm._avail(llm._chain(os.getenv("ASSIST_FALLBACK","openai:gpt-5.4-mini")))
def live(): return (bool(os.getenv("ANTHROPIC_API_KEY")) or bool(FALLBACK)) and os.getenv("ASSIST_MOCK")!="1"
def ground_live(): return bool(os.getenv("OPENAI_API_KEY")) and os.getenv("ASSIST_GROUNDING","1")!="0" and os.getenv("ASSIST_MOCK")!="1"
# ---------- privacy: never log or send NI / bank details ----------
NI=re.compile(r"\b[A-Z]{2}\s?\d{2}\s?\d{2}\s?\d{2}\s?[A-D]?\b",re.I)
SORT=re.compile(r"\b\d{2}[- ]\d{2}[- ]\d{2}\b"); DIGITS=re.compile(r"\d{6,}")
def mask(s): return DIGITS.sub("[number]",SORT.sub("[number]",NI.sub("[NI number]",s or "")))
SKIP_KEYS=re.compile(r"(^|_)(ni|nino|bank|sort|acc|account|holder|roll|iban)(_|$)",re.I)
def answers_text(d,limit=2500):
    """The customer's own answers so far, as plain 'key: value' lines (no NI or bank fields)."""
    out=[]
    for k,v in (d or {}).items():
        if SKIP_KEYS.search(k) or v in (None,"",[],{}): continue
        if isinstance(v,(list,tuple)): v=", ".join(str(x) for x in v)
        if isinstance(v,dict): v=json.dumps(v,ensure_ascii=False)[:200]
        out.append(f"{k}: {mask(str(v))[:200]}")
    t="\n".join(out); return t[:limit]
# ---------- rate limit ----------
_LOCK=threading.Lock(); _SEEN={}
def allow(key):
    day=time.strftime("%Y-%m-%d")
    with _LOCK:
        k=(key,day); n=_SEEN.get(k,0)
        if n>=PER_DAY: return False
        _SEEN[k]=n+1; return True
def log(rec):
    p=os.getenv("ASSIST_LOG") or os.path.join(os.getenv("OUT_DIR","/tmp"),"assist_log.jsonl")
    try:
        os.makedirs(os.path.dirname(p),exist_ok=True)
        with open(p,"a") as f: f.write(json.dumps(rec,ensure_ascii=False)+"\n")
    except OSError as e: print("assist log not written",e,flush=True)
# ---------- the fixed post-check ----------
BANNED=re.compile(r"\b(AI|A\.I\.|artificial intelligence|chatbot|bot|language model|model|LLM|Claude|Anthropic|OpenAI|GPT|Gemini|Google|Stripe)\b",re.I)
WECLAIM=re.compile(r"\bwe(?:'ll| will)? (?:claim|submit|send (?:it|the form|your form)|apply)\b",re.I)
PERSON=re.compile(r"\b(our (?:team|experts?|advisers?|advisors?|staff)|a (?:person|human|real person|caseworker|adviser) (?:checks?|reviews?|looks? at))\b",re.I)
OUTCOME=re.compile(r"\b(you(?:'ll| will) (?:get|be awarded|qualify|receive)|you (?:are|'re) (?:entitled|eligible)|guarantee[sd]?|definitely get|\d+ points?)\b",re.I)
CHARITY=re.compile(r"\b(citizens advice|age uk|scope|turn2us|mencap|contact\.org|welfare rights|advice centre|charity|charities|helpline|free help|free advice)\b",re.I)
LINK=re.compile(r"(https?://\S+|www\.\S+|\b[a-z0-9-]+\.(?:gov\.uk|org\.uk|co\.uk|com|org|uk)\b)",re.I)
NUM=re.compile(r"£\s?\d[\d,]*(?:\.\d+)?|\b\d+(?:\.\d+)?\b")
def post_check(reply,src=""):
    """Drop any sentence that breaks a rule, or has a number or amount that isn't in the sources. Returns (clean_reply, dropped)."""
    keep=[]; drop=[]; srcn={re.sub(r"[£,\s]","",m) for m in NUM.findall(src)}
    for s in sentences(reply):
        s2=s.replace(EMAIL,"@@EMAIL@@")
        bad=BANNED.search(s2) or WECLAIM.search(s2) or PERSON.search(s2) or OUTCOME.search(s2) or CHARITY.search(s2) or LINK.search(s2) \
            or any(re.sub(r"[£,\s]","",m) not in srcn for m in NUM.findall(s2))
        (drop if bad else keep).append(s)
    out=" ".join(keep).strip()
    w=out.split()
    if len(w)>MAX_WORDS:   # cap: keep whole sentences up to the limit
        acc=[]; n=0
        for s in sentences(out):
            if n+len(s.split())>MAX_WORDS and acc: break
            acc.append(s); n+=len(s.split())
        out=" ".join(acc)
    return out,drop
# ---------- the model call ----------
SYSTEM=f"""You are the FormSorted assistant inside an online form-filling service for UK disability benefit forms (Attendance Allowance, PIP, PIP review, DLA for a child, Blue Badge, Access to Work).
The customer is answering simple questions so we can complete their whole form in full, in plain English, from their answers. They check it, sign it and send it themselves.
They typed a message into the chat. Decide what it is:
- "answer": it is plainly their answer to the QUESTION ON SCREEN (for example a short fact about them that fits that question).
- "question": they are asking something, are confused, or want help.
If it is a question, reply warmly and briefly in plain English (UK spelling), at most 3 short sentences, like a kind helper talking to an older person.
STRICT RULES for the reply:
1. Use ONLY facts in HELP NOTES, QUESTION ON SCREEN (its wording, help text and answer options) and THEIR ANSWERS SO FAR. Never add facts, rules, amounts, rates, points, deadlines, time limits or eligibility from anywhere else.
   You may explain what the question on screen is asking in simpler words and suggest how to think about it (a typical week, include the bad days, pick the closest option, tap Something else and use their own words, skip it if unsure).
2. If the notes don't cover it, set covered=false and reply exactly: "{NOT_COVERED}"
3. Never give legal advice, never say whether they will get an award or how much, never guarantee an outcome.
4. Never say "we claim", "we submit", "we send" or "we apply": the customer sends the form themselves. Never say or imply that a person checks, reviews or reads their form.
5. Never mention artificial intelligence, models, chatbots, Claude, Anthropic, OpenAI, Stripe or Google. You are simply "the FormSorted assistant".
6. Never recommend or name charities, advice services, helplines or free services. No links or web addresses. The only contact you may give is {EMAIL}.
7. Never ask for or repeat National Insurance numbers or bank details.
ADD: only if the customer's message itself describes something true about their own situation that would help answer the question on screen
(e.g. "does it count if I need reminding to take my tablets?"), set add to a short note in their own words (first person, no new facts, nothing they didn't say). Otherwise add="".
Return JSON only."""
SCHEMA={"type":"object","properties":{"kind":{"type":"string","enum":["answer","question"]},"covered":{"type":"boolean"},"reply":{"type":"string"},"add":{"type":"string"}},"required":["kind","covered","reply","add"]}
FAQ=[]   # set by app.py: the help list shown on every screen (HELP_FAQ + chatui.FAQ_EXTRA)
def kb_text(form=""):
    """The help notes: every FAQ entry (they're short)."""
    rows=[f"Q: {q}\nA: {a}" for q,a in FAQ]+[f"Q: {k['q']}\nA: {k['a']}" for k in KB]
    return "\n\n".join(dict.fromkeys(rows))
def mock_reply(text,ctx):
    """No key (tests, preview): the same fixed help list, matched by words; else the plain 'not covered' reply."""
    ws={w for w in re.findall(r"[a-z]+",text.lower()) if len(w)>2}-set("like don didn would there here then than just about from have has had".split())-set("a an the i my me we you your is are do does can to of for it in on and or be if what how who when why will this that with any am get".split())
    hint=(ctx.get("hint") or "").strip()
    if hint and re.search(r"\b(mean|meant|understand|confus|explain)",text.lower()):
        return {"kind":"question","covered":True,"reply":hint,"add":""}
    best=None; bs=0
    for q,a in FAQ+[(k["q"],k["a"]) for k in KB]:
        s=2*len(ws & set(re.findall(r"[a-z]+",q.lower())))+len(ws & set(re.findall(r"[a-z]+",a.lower())))/4
        if s>bs: bs=s; best=(q,a)
    if best and bs>=2: return {"kind":"question","covered":True,"reply":best[1],"add":""}
    return {"kind":"question","covered":False,"reply":NOT_COVERED,"add":""}
GROUND_PROMPT="""You check a short help reply written to a customer of a UK benefit-form filling service against the SOURCE (the service's help notes, the question on screen and the customer's own answers).
List every claim in the REPLY that the SOURCE does not support: facts, rules, amounts, rates, points, deadlines, time limits, eligibility or outcome statements,
named organisations or services, promises, or anything saying a person checks the form or that the service sends or claims for them.
Plain guidance on how to answer the question on screen (think about a typical week, include bad days, pick the closest option, use your own words, you can skip it or come back) is fine.
So is rephrasing the question on screen in simpler words, and kind words. Return JSON only: {"unsupported":[{"phrase":"exact words from the reply","reason":"short reason"}]}."""
def ground(reply,src):
    if llm.MOCK: return []
    out=llm._call([{"role":"system","content":GROUND_PROMPT},{"role":"user","content":f"SOURCE:\n{src}\n\nREPLY:\n{reply}"}],json_mode=True,chain=llm.GROUND_CHAIN,effort=llm.GROUND_EFFORT)
    return json.loads(out).get("unsupported",[])
def answer(text,ctx,answers="",form=""):
    """-> dict(kind, reply, add, covered, model, ms, dropped). Raises claude.Unavailable when every model fails."""
    t0=time.time(); text=mask(text.strip())[:MAX_IN]
    q=ctx.get("q") or "(no question on screen: the customer is choosing their form)"
    opts=", ".join(ctx.get("options") or [])[:600]
    user=(f"HELP NOTES:\n{kb_text(form)}\n\nFORM: {form or 'not chosen yet'}\n\nQUESTION ON SCREEN: {q[:400]}\nIts help text: {(ctx.get('hint') or '')[:600]}\n"
          f"Its answer options: {opts}\nIt has a box for their own words: {'yes' if ctx.get('box') else 'no'}\n\nTHEIR ANSWERS SO FAR:\n{answers or '(none yet)'}\n\nTHEIR MESSAGE: {text}")
    model="rules"
    if live():
        old=claude.MAX_TOKENS; out=None
        try:
            claude.MAX_TOKENS=1200
            out=claude.call(CHAIN,SYSTEM,user,schema=SCHEMA,purpose="assist",timeout=TIMEOUT,retries=0)
            model=llm.USED[-1][1] if llm.USED else CHAIN[0][0]
        except claude.Unavailable:
            if not FALLBACK: raise
            # every Claude model failed (e.g. out of credit): the same prompt and checks on the OpenAI chain (ASSIST_FALLBACK, "" = off)
            out=json.loads(llm._call([{"role":"system","content":SYSTEM+"\nReturn a JSON object with keys kind, covered, reply, add."},{"role":"user","content":user}],json_mode=True,chain=FALLBACK,effort="low"))
            model=llm.USED[-1][1] if llm.USED else "fallback"
        finally: claude.MAX_TOKENS=old
    else: out=mock_reply(text,ctx)
    out={"kind":out.get("kind","question"),"covered":bool(out.get("covered",True)),"reply":(out.get("reply") or "").strip(),"add":(out.get("add") or "").strip()}
    if out["kind"]=="answer" and not ctx.get("q"): out["kind"]="question"
    dropped=[]
    if out["kind"]=="question":
        src=f"{kb_text(form)}\n\nQUESTION ON SCREEN: {q}\nHelp text: {ctx.get('hint') or ''}\nOptions: {opts}\n\nTHEIR ANSWERS SO FAR:\n{answers}\n\nTHEIR MESSAGE: {text}\n\n{NOT_COVERED}"
        rep=out["reply"]
        if rep and rep!=NOT_COVERED and ground_live():
            try:
                flags=ground(rep,src)   # OpenAI checker chain, same models as the writer's check
                for f in flags:
                    ph=(f.get("phrase") or "").lower()
                    for s in sentences(rep):
                        if ph and ph in s.lower(): dropped.append(s); rep=rep.replace(s,"").strip()
            except Exception as e:   # the check is mandatory for this reply: without it we only give the fixed text
                print("assist grounding unavailable",str(e)[:160],flush=True); dropped.append("(grounding unavailable)"); rep=NOT_COVERED
        rep,d2=post_check(rep,src); dropped+=d2
        out["reply"]=rep if len(rep.split())>=4 else NOT_COVERED
        if out["reply"]==NOT_COVERED: out["covered"]=False
        # a suggested note is only ever the customer's own words: drop it if it adds anything they didn't say
        if out["add"]:
            a,_=post_check(out["add"],text)
            if not ctx.get("box") or check_answer(a,text) or len(a.split())<3: a=""
            out["add"]=a
    else: out["reply"]=""; out["add"]=""
    out.update(model=model,ms=int((time.time()-t0)*1000),dropped=dropped)
    return out

"""Claude writer tests (30 Oct 2026). Mocked Claude by default; with ANTHROPIC_API_KEY and CLAUDE_LIVE=1 also one real PIP draft.
Checks: every sentence cites the customer's answers; uncited sentences, numbers or strong words not in the answers and
anything the verifier rejects are removed; DLA statement left blank; customer copy never mentions AI/Google; whole-form
answers are facts (and so in the answer check's source); first person."""
import os, sys, json, re
LIVE=os.getenv("CLAUDE_LIVE")=="1" and os.getenv("ANTHROPIC_API_KEY")
if not LIVE: os.environ["CLAUDE_MOCK"]="1"
os.environ["WF_LOOKUPS"]="0"
import writer, claude as cl, intake as I
from test_personas import walk, PIP_STEPS, AA_STEPS, DLA_STEPS
FAILS=[]
def check(ok,msg):
    if not ok: FAILS.append(msg); print("FAIL",msg)
d,_=walk("pip",{"who":"me"},PIP_STEPS,stop="more")
F=writer.facts("pip",d); ids={f["id"]:f for f in F}
check(any("Using a hob or cooker safely" in f["text"] and f["topic"]=="a1" for f in F),"row taps become facts in their box")
a1=[f["id"] for f in F if f["topic"]=="a1"]; a4=[f["id"] for f in F if f["topic"]=="a4"]
def fake(chain,system,user,schema=None,purpose="",**k):
    if purpose=="draft": return {"boxes":[{"topic":"a1","sentences":[
        {"text":"I struggle to prepare food.","facts":a1[:1]},
        {"text":"I burnt my hand last week.","facts":[]},                         # no citation -> dropped
        {"text":"It takes me 45 minutes.","facts":a1[:1]},                        # number not in answers -> dropped
        {"text":"I can never use the hob.","facts":a1},                           # 'never' stronger than answers -> dropped
        {"text":"My daughter cooks for me.","facts":a1}]},                        # verifier rejects
        {"topic":"a4","sentences":[{"text":"It is like this 4 days a week.","facts":a4}]},
        {"topic":"zz","sentences":[{"text":"Not a box.","facts":a1}]}]}
    if purpose=="extras": return {"checklist":["Your repeat prescription list","Made with AI"],"gp_letter":"Dear Dr,","notes_for_user":["Checked by our team","Keep a copy"],"call_prep":["Think about bad days"]}
    if purpose=="verify":
        v=json.loads(user); return {"verdicts":[{"n":x["n"],"supported":"daughter" not in x["sentence"],"problem":"no daughter in answers"} for x in v]}
    raise AssertionError(purpose)
if not LIVE:
    real=cl.call; cl.call=fake
    r=writer.write("pip",d); cl.call=real
    check(r["answers"]["a1"]=="I struggle to prepare food.",f"only supported sentences kept: {r['answers']['a1']!r}")
    check(r["answers"]["a4"]=="It is like this 4 days a week.","number in the answers is kept")
    why=" | ".join(x["why"] for x in r["verifier"]["removed"])
    for k in ("no matching answer","number not in your answers","'never' is stronger","verifier"): check(k in why,f"removed reason: {k}")
    check(r["checklist"]==["Your repeat prescription list"] and r["notes_for_user"]==["Keep a copy"],"customer copy never mentions AI or checking")
    check(all(r["sources"].get(t) for t,v in r["answers"].items() if v),"every answer has its sources")
    check(r["drafted_from"]=="claude" and r["facts"],"facts kept for the answer check")
    # DLA statement box is never written
    dd,_=walk("dla",DLA_STEPS["about"],DLA_STEPS,stop="more")
    def fake2(chain,system,user,schema=None,purpose="",**k):
        if purpose=="draft":
            F2=json.loads(user)["facts"]; return {"boxes":[{"topic":"statement","sentences":[{"text":"Mrs Brown would say Leo needs help.","facts":[F2[0]["id"]]}]}]}
        return {"verdicts":[]} if purpose=="verify" else {"checklist":[],"gp_letter":"","notes_for_user":[]}
    cl.call=fake2; r2=writer.write("dla",dd); cl.call=real
    check(r2["answers"].get("statement","")=="","DLA statement left blank")
    # whole-form answers are facts in the right box
    da,_=walk("aa",{"who":"parent","name":"Margaret","signer":"poa"},AA_STEPS,stop="more")
    FA=writer.facts("aa",da)
    check(any(f["topic"]=="34" and "falls" in f["text"].lower() for f in FA),"whole-form falls answer is a fact for Q34")
    check(any(f["topic"]=="30" and "times a day" in f["text"] for f in FA),"times a day is a fact for Q30")
    # rule check on its own
    check(writer.rule_check("I need help every day.",["Dressing: like this 7 days a week."])==[],"'every day' fine when 7 days a week")
    check(writer.rule_check("I fall twice a week.",["Falls: 1 to 2 in the last year."])!=[],"'twice a week' not in answers is caught")
else:
    r=writer.write("pip",d); fx=r["facts"]
    for c in r["cites"]:
        check(c["facts"] and all(i in fx for i in c["facts"]),f"live: sentence cites answers: {c['text']}")
        check(not writer.rule_check(c["text"],[fx[i] for i in c["facts"]]),f"live: no new numbers/strong words: {c['text']}")
    allt=" ".join(r["answers"].values())
    check(re.search(r"\bI\b",allt) and not re.search(r"\b(Daniel|he|she) (needs|struggles)\b",allt),"live: first person")
    check(not writer.BANNED_COPY.search(json.dumps([r.get("checklist"),r.get("notes_for_user"),r.get("gp_letter")])),"live: no AI mentions in customer copy")
    print("live cost $%.4f"%cl.cost(), r["verifier"]["status"], len(r["verifier"]["removed"]),"removed")
check(not writer.rule_check("He can't spot a warning and tell an adult.",["Can Leo spot a warning and tell an adult: No."]),"rule: 'No' to 'Can X' allows can't")
check(writer.rule_check("He can never spot a warning.",["Can Leo spot a warning and tell an adult: No."]),"rule: never still flagged")
check(writer.tidy("dla",{"about":{"who":"parent","name":"Leo"},"I":{"name":"Leo"}},"What's hard is that he doesn't follow instructions.")=="He doesn't follow instructions.","tidy: meta opener")
check(writer.tidy("dla",{},"I struggle with getting him dressed.").startswith("I struggle"),"tidy: parent voice kept")
check(not writer.tidy("dla",{},"I struggle with communicating.").startswith("I "),"tidy: DLA child not 'I'")
check(writer.tidy("dla",{},"I need help or someone with me with dressing.").startswith("My child needs help or someone with them"),"tidy: DLA help is the child's")
check(writer.tidy("pip",{},"I struggle with cooking.").startswith("I struggle"),"tidy: PIP first person kept")
check(writer.tidy("aa",{},"Not discussed.")=="","no 'Not discussed'")
check(writer.APPROVED.search("Leo needs help or someone with him with dressing."),"approved level wording")
# 30 Oct: typed details per tapped chip (inline intake follow-ups) reach the writer as own-words facts, the fallback and the answer check
import intake as _I
_d={"wf_v":1,"who":"me","rows":{"a1":{"lvl":"help","c":["hob"],"cx":{"hob":"I left a pan on and it caught fire in May"},"detail":"My partner cooks most nights"}}}
_F=[f["text"] for f in writer.facts("pip",_d)]
check(any("typed detail in the customer's own words: I left a pan on and it caught fire in May" in x for x in _F),"per-chip typed detail is a fact")
check(any("My partner cooks most nights" in x for x in _F),"whole-task typed detail is a fact")
_src="\n".join(m["content"] for m in _I.history("pip",_d) if m["role"]=="user")
check("caught fire in May" in _src,"typed detail is in the answer-check source")
check("caught fire in May" in _I.fallback_draft("pip",_d)["answers"]["a1"],"typed detail is in the fallback draft")
check("Typed detail" in writer.SYS,"writer told to prefer typed details")
# 30 Oct: long answers are wrapped by us and the box font shrinks to fit (DLA Q72 ran off the right edge)
import fill_pdf as _F
_sz,_tx=_F.layout("dla1a.pdf","72","Leo needs help every time he uses the toilet, every day. "*60)
_w,_h=_F._rects("dla1a.pdf")["72"]
check(7<=_sz<=10 and all(_F._sw(l,_sz)<=_w-8 for l in _tx.split("\n")),"Q72: every line fits the box width")
check(len(_tx.split("\n"))*_sz*1.17<=_h,"Q72: all lines fit the box height")
check(_F.layout("dla1a.pdf","72","Short.")[0]==10,"short answers keep 10pt")
check(_F.layout("dla1a.pdf","72","It\u2019s 2\u20133 times \u201cbad\u201d days \u2265 week \U0001F600")[0]==10,"non-Latin-1 text measures")
print("writer:", "FAIL "+str(len(FAILS)) if FAILS else "OK"); sys.exit(1 if FAILS else 0)


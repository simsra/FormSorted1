"""30 Oct (Simon): never invent. Sparse answers in -> nothing beyond them out. Mock only (no paid calls).
1) the no-AI fallback draft for sparse personas adds nothing; 2) the Claude writer pipeline removes every invented sentence
(rule check, checker, grounding) and logs each removal."""
import os, json, re
os.environ.setdefault("CLAUDE_MOCK","1")
import intake as I, grounding as G, writer, claude as cl
FAILS=[]
def check(ok,msg):
    if not ok: FAILS.append(msg); print("FAIL",msg)
SPARSE={   # (form, intake): one tap each
 "aa_one_chip":("aa",{"wf_v":1,"who":"me","rows":{"wash":{"lvl":"help","c":["in"]}}}),
 "aa_carer_one_chip":("aa",{"wf_v":1,"who":"parent","name":"Margaret","rows":{"dress":{"lvl":"slow","c":["fast"]}}}),
 "dla_one_chip":("dla",{"wf_v":1,"name":"Leo","rel":"Mum","age":"5to15","rows":{"dress":{"lvl":"help","c":["sens"]}}}),
 "pip_level_only":("pip",{"wf_v":1,"who":"me","rows":{"a1":{"lvl":"slow"}}}),
}
PAD=re.compile(r"\b(every day|daily|every night|always|never|often|usually|family|daughter|son|husband|wife|carer|partner|fell|fall|injur\w*|because|due to|so that|without help|could|would|risk|danger|minutes?|hours?|times? a|twice|once|week|aid|frame|rail|seat|alarm|anxious|pain|affects my|rely on)\b",re.I)
for k,(form,d) in SPARSE.items():
    src="\n".join(m["content"] for m in I.history(form,d) if m["role"]=="user")
    fb=I.fallback_draft(form,d); allt=" ".join(a for a in fb["answers"].values() if a)
    check(allt.strip(),f"{k}: fallback says something")
    check(G.check(fb["answers"],src,use_llm=False)=={},f"{k}: fallback grounded {G.check(fb['answers'],src,use_llm=False)}")
    extra=[w for w in {m.group(0).lower() for m in PAD.finditer(allt)} if not re.search(r"\b"+re.escape(w)+r"\b",src,re.I)]
    check(not extra,f"{k}: fallback added {extra}: {allt}")
    F=writer.facts(form,d); check(all(f["text"] for f in F),f"{k}: facts")
    check(len([f for f in F if f["topic"]!="*"])<=3,f"{k}: sparse facts stay sparse: {[f['text'] for f in F]}")
print("fallback adds nothing: OK" if not FAILS else "fallback: FAIL")

# The writer pipeline with a model that pads: every invented sentence must be removed and logged.
form,d=SPARSE["aa_one_chip"]; F=writer.facts(form,d); fid=[f["id"] for f in F if "bath" in f["text"].lower()][0]
INVENT=["I have difficulty getting in or out of the bath or shower.",   # true
        "This happens every day.",                                       # frequency not given (rule check)
        "My daughter helps me in and out.",                              # person not given (grounding)
        "I slipped once and hurt my hip.",                               # event + condition not given (grounding)
        "This affects my daily life.",                                   # padding (grounding: 'daily')
        "I feel unsafe and worried when bathing.",                       # feeling not given (checker)
        "I need a hand with it."]                                        # checker gives no verdict
VER={}
def fake(chain,system,user,schema=None,purpose="",**k):
    if purpose=="draft": return {"boxes":[{"topic":"31","sentences":[{"text":t,"facts":[fid]} for t in INVENT]}]}
    if purpose=="extras": return {"checklist":["A letter from your GP","Your repeat prescription list, as it relates to your pain"],"notes_for_user":["Keep a copy of the form.","Say it happens every day."],
                                  "gp_letter":"Dear Doctor,\n\nI find it hard to get in or out of the bath. This is due to my arthritis.\n\nYours sincerely,\n"}
    if purpose=="verify":
        vin=json.loads(user); VER["n"]=len(vin)
        return {"verdicts":[{"n":x["n"],"problem":"feeling not in the facts" if "worried" in x["sentence"] else "none","supported":"worried" not in x["sentence"]} for x in vin if "a hand" not in x["sentence"]]}
    raise AssertionError(purpose)
real=cl.call; cl.call=fake
try: out=writer.write(form,d)
finally: cl.call=real
a=out["answers"]["31"]; rm=out["verifier"]["removed"]
check(a=="I have difficulty getting in or out of the bath or shower.",f"only the true sentence is left: {a!r}")
rm=[r for r in rm if not r["topic"].startswith("extras:")]
check(len(rm)==len(INVENT)-1,f"each invented sentence is logged: {[r['text'] for r in rm]}")
for r in rm: check(r["why"].strip(),f"removal has a reason: {r}")
why={r["text"]:r["why"] for r in rm}
check("every day" in why.get("This happens every day.",""),"rule check catches the frequency")
check(why.get("My daughter helps me in and out.","").startswith("grounding"),"grounding removes the invented person")
check(why.get("I slipped once and hurt my hip.","").startswith(("grounding","number")),"invented event removed")
check(why.get("This affects my daily life.","").startswith("grounding"),"grounding removes padding")
check(why.get("I feel unsafe and worried when bathing.","").startswith("verifier"),"checker removes an invented feeling")
check(why.get("I need a hand with it.","")=="verifier: no verdict from the checker","a sentence the checker skipped is not kept")
check(out["verifier"]["grounding"]=="checked",out["verifier"])
check(out["checklist"]==["A letter from your GP"] and out["notes_for_user"]==["Keep a copy of the form."],("extras grounded",out["checklist"],out["notes_for_user"]))
check("arthritis" not in out["gp_letter"] and "bath" in out["gp_letter"] and out["gp_letter"].startswith("Dear Doctor,"),("GP letter grounded",out["gp_letter"]))
check(all(not out["answers"][t] for t in out["answers"] if t!="31"),"no other box is written from one tap")
# causes and links the facts don't give are cut (live run 30 Oct: 'Leo has sensory issues with clothes, which makes dressing difficult for him')
check(writer.cut_cause("Leo has sensory issues with clothes, which makes dressing difficult for him.",["Dressing, what's hard: Sensory issues with clothes."])==("Leo has sensory issues with clothes.","which makes dressing difficult for him."),"cause clause cut")
check(writer.cut_cause("Because of my knees I can't bathe.",["Washing: can't do it safely on their own."])[0]=="","sentence built on a cause is dropped")
check(writer.cut_cause("I fall because my legs give way.",["Falls: because my legs give way"])[0]=="I fall because my legs give way.","cause the customer gave is kept")
check(writer.tidy("pip",{},"Preparing food is slow, painful or tiring for me (at least one of these, not said which).")=="Preparing food is slow, painful or tiring for me.","fact-label notes never reach the customer")
print("no-invent:", "FAIL "+str(len(FAILS)) if FAILS else "OK"); raise SystemExit(1 if FAILS else 0)

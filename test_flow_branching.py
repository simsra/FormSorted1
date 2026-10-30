"""Branching and wording tests for the tap intake (30 Oct 2026). No server, no AI (quick checks use the no-AI rules).
'For myself' must never see other-person questions or 'they/them' about the claimant; 'someone else' gets their name;
quick checks: at most 2 per task, never ask what we already know, every list has 'Something else', all skippable."""
import os, re, sys, html
os.environ["CLAUDE_MOCK"]="1"; os.environ["WF_LOOKUPS"]="0"; os.environ["FOLLOWUPS"]="1"
import intake as I, wholeform as W, followups as FU
from test_personas import FM, rows, walk, AA_STEPS, PIP_STEPS, DLA_STEPS
FAILS=[]
def check(ok,msg):
    if not ok: FAILS.append(msg); print("FAIL",msg)
# labels about OTHER people (helpers, professionals, school), where 'they/their' is right
OK_OTHER=re.compile(r"^(Their (name|postcode|house|town|phone|first name)|Who are they|What do they help|How often|Who will sign|chip: (They will sign|I'm their|I have Power|None of them|I'll type them)|.*\b(doctor|nurse|consultant|school|teacher|hospital|helps? (you|them))\b)",re.I)
def vis(L,me_vals):   # visible for this answer: no dep, or dep satisfied by who
    return [x for x in L if not x[2] or (x[2]=="who" and me_vals in x[3].split())]
# 1. 'For myself' (AA and PIP): no other-person questions, no they/them about the claimant, no 'Does you'
for form,steps in (("aa",AA_STEPS),("pip",PIP_STEPS)):
    d,L=walk(form,{"who":"me","name":"Stray","signer":"poa"},steps)
    check(d.get("name")=="" and d.get("signer")=="",f"{form} me: name/signer cleared on save")
    about=[x for x in L if x[0]=="about" and not x[1].startswith("chip")]
    shown=[x[1] for x in about if not x[2]]
    check(not any("first name" in s.lower() or "sign" in s.lower() for s in shown),f"{form} me: other-person questions hidden by default: {shown}")
    check(all(x[2]=="who" and "me" not in x[3].split() for x in about if "first name" in x[1].lower() or "sign" in x[1].lower()),f"{form} me: name/signer only for someone else")
    for sec,lab,dep,vals,_ in L:
        if sec=="about" or dep=="who": continue
        if re.search(r"\b(Does|does|Is|is|Has|has|Was|was) you\b",lab): check(False,f"{form} me grammar: {lab}")
        if re.search(r"\b(they|them|their|themselves)\b",lab,re.I) and not OK_OTHER.search(lab): check(False,f"{form} me: they/them about the claimant: [{sec}] {lab}")
    # no duplicate question text in one part
    seen={}
    for sec,lab,*_ in L:
        if lab.startswith("chip"): continue
        if (sec,lab) in seen and not [x for x in L if x[0]==sec and x[1]==lab and x[2]] and not re.search(r"Date|Why did|Where did|Something else",lab): check(False,f"{form} me: asked twice in {sec}: {lab}")
        seen[(sec,lab)]=1
# 2. Someone else with a name: their name in the questions, never 'you' for the claimant's own care
d,L=walk("aa",{"who":"parent","name":"Margaret","signer":"poa"},AA_STEPS)
labs=[x[1] for x in L]
check(any("Margaret falls" in l for l in labs),"aa other: 'What usually happens when Margaret falls?'")
check(any("keep an eye on Margaret" in l for l in labs),"aa other: keep an eye on Margaret")
check(not any(re.search(r"\b(Does|does|Is|is|Has|has|Was|was) you\b|\bdoes them\b|\bthem have\b",l) for l in labs),"aa other: grammar")
check(not any("Cleaning yourself" in l for l in labs),"aa other: chips say themselves")
check(any(x[0]=="helper" for x in L) or "helper" in [k for k,_ in I.sections("aa",d)],"aa other with POA: helper section applies")
# 3. Someone else with no name: 'your parent', never 'them' as a name
d,L=walk("aa",{"who":"parent","name":"","signer":"them"},AA_STEPS)
check(I.name(d,"aa")=="your parent","no-name default is 'your parent'")
check(not any(re.search(r"\b(does|Does) them\b|\bthem (has|have|is)\b",x[1]) for x in L),"aa other, no name: no 'does them'")
check("helper" not in [k for k,_ in I.sections("aa",d)],"aa: signs themselves -> no helper section")
# 4. Me: chips in the first person
d,L=walk("aa",{"who":"me"},AA_STEPS,stop="safety")
check(any(x[1]=="chip: Cleaning yourself" for x in L),"aa me: 'Cleaning yourself' chip")
# 5. pendant alarm told under falls is pre-ticked in aids (never ask twice)
d={"wf_v":1,"who":"me","fallx":["alarm"]}
b=I.section_body("aa","finish",d)
check(re.search(r'value="Pendant alarm" checked',b) is not None,"pendant alarm pre-ticked")
# 6. 'Different for some parts?' rides on the question above (no separate screen)
d,L=walk("aa",{"who":"me"},AA_STEPS,stop="finish")
b=[x[4] for x in L if x[0]=="often"]
check(b and "<legend>Different for some" not in b[0] and "diffopt" in b[0],"diff merged into its question")
# 7. quick checks: cap, per-task limit, never re-ask, Something else, skippable, answers become facts
for form,about,steps in (("aa",{"who":"me"},AA_STEPS),("pip",{"who":"me"},PIP_STEPS),("dla",DLA_STEPS["about"],DLA_STEPS)):
    d,L=walk(form,about,steps,stop="more")
    qs=d.get("fu_qs") or []
    check(len(qs)<=FU.CAP[form],f"{form}: quick checks within cap ({len(qs)})")
    per={}
    for rid,dim in qs: per[rid]=per.get(rid,0)+1
    check(all(v<=2 for v in per.values()),f"{form}: at most 2 per task")
    for rid,dim in qs:
        v=(d.get("rows") or {}).get(rid) or {}
        if dim=="often": check(not I._ok(v.get("days")),f"{form}: never ask how often when days were given ({rid})")
        if form=="dla": check(dim!="who",f"dla: never ask who helps (the parent does)")
    for q in FU.questions(form,d):
        if q["kind"] in("radio","checks"): check(q["other"],f"{form}: {q['id']} has Something else")
        check(len(q["label"])<=70,f"{form}: one short line: {q['label']}")
    if qs:
        check("more" in [k for k,_ in I.sections(form,d)],f"{form}: quick checks part shown")
        # skip all: nothing stored as a fact, marked skipped, and not asked again when they come back through
        d=I.save(form,"more",d,FM({})); check(all(st=="skipped" for st in d["fu"].values()),f"{form}: skipped")
        check(not any(k.startswith("fu_") for k in d.get("clarify",{})),f"{form}: skipped adds no facts")
        before=list(qs); d=I.save(form,"finish",d,FM(steps.get("finish",{})))
        check(not set(map(tuple,d.get("fu_qs") or []))&set(map(tuple,before)),f"{form}: never re-asks a skipped check")
    # answer one: becomes a 'Checked with you' fact in the right box
    d,_=walk(form,about,steps,stop="more"); qs=d.get("fu_qs") or []
    if qs:
        q=FU.questions(form,d)[0]; val=q["opts"][0][0] if q["opts"] else "Last week I needed help"
        d=I.save(form,"more",d,FM({q["id"]:[val] if q["kind"]=="checks" else val}))
        _,T=I.topic_texts(form,d); topic=dict((r[0],r[1]) for r in I.rows(form,None,d))[qs[0][0]]
        check("Checked with you:" in T.get(topic,""),f"{form}: answer goes into box {topic}")
        check(d["coverage"] and any("asked: answered" in v.values() for v in d["coverage"].values()),f"{form}: coverage map records it")
# 8. FOLLOWUPS=0 switches them off
os.environ["FOLLOWUPS"]="0"; d,_=walk("pip",{"who":"me"},PIP_STEPS); check("more" not in [k for k,_ in I.sections("pip",d)],"FOLLOWUPS=0 off"); os.environ.pop("FOLLOWUPS")
print("flow branching:", "FAIL "+str(len(FAILS)) if FAILS else "OK"); sys.exit(1 if FAILS else 0)

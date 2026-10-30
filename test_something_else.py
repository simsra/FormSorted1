"""Every tap list in the AA, DLA and PIP question flows has a 'Something else' choice with a box to type in
(30 Oct 2026, Simon: 'every list must have Something else'). Fails if a new list is added without one.
AR1 (PIP review) is a typed interview plus a 'still the same / it has changed' page with a box, so it has no tap lists to check.
A list may only skip it when listed in EXEMPT with the reason; none of these lists' help text promises one."""
import os, re, html, itertools
os.environ["WF_LOOKUPS"]="0"
import intake as I, wholeform as W
from test_personas import FM, walk, AA_STEPS, PIP_STEPS, DLA_STEPS
EXEMPT={  # name pattern -> why it can't have one
 r"who":"Who the form is for: 'Someone else' is itself the open choice and goes straight on to typing their name",
 r"cond_\d+":"One tick per named condition; the list's own typed choice is the 'Another condition (type it)' box under it",
 r"\w+_more\d+":"'Another one? Yes / No' repeater (another test, hospital stay or address): Yes opens boxes to type it",
 r"\w+_diff":"single 'It's different for some of these' toggle that opens the per-item version of the same question",
}
def groups(body):
    """{name: set of values} for every radio/checkbox group on the page (Something else's own tick box excluded)."""
    g={}
    for m in re.finditer(r'<input type=(radio|checkbox) name="([^"]+)" value="?([^" >]*)',body):
        n=m.group(2)
        if n.endswith("_xon"): continue
        g.setdefault(n,set()).add(m.group(3))
    return g
def has_else(n,vals,body):
    if f'name="{n}_xon"' in body: return True                 # Something else chip + box
    if "else" in vals and n.startswith("r_") and "_f_" in n: return True   # inline follow-up: Something else + an always-visible box
    return False
def exempt(n): return any(re.fullmatch(p,n) for p in EXEMPT)
def everything(form):
    """Every card hard, every chip tapped, every safety and finish answer given: shows every follow-up question."""
    st={}
    for sec in ("daily","out","safety"):
        sp={}
        for r in I.rows(form,sec,{"age":"5to15"}):
            tk,fx=I.card_opts(form,r[0],r[4]); sp[r[0]]=("cant",[v for v,_ in tk+fx],"7")
        st[sec]={"bad":"5",**__import__("test_personas").rows(sp)} if sec=="daily" else __import__("test_personas").rows(sp)
    st["safety"].update({"falls":"3-5","lastfall":"week","fallx":["getup","hurt","clinic","alarm"],"eye":["danger","wander","fits","confused"],"alone":"never",
        "night":["toilet","turn","pain","meds","confused"],"nights":"7","ntimes":"4+","nmins":"60p","watch":"most","fits":"day","varies":"varies","nn":[k for k,_ in I.NIGHT_DLA]})
    st["conds"]={"cond_0":"1","cond_1":"1","cond_2":"1"}
    st["finish"]={"aids":list(I.AIDS[form])[:6],"people":list(I.PEOPLE[form])[:3],"school":[k for k,_ in I.SCHOOL]}
    return st
PERSONAS=[("aa",{"who":"me"},everything("aa")),("aa",{"who":"parent","name":"Mum","signer":"appointee"},everything("aa")),
          ("pip",{"who":"me"},everything("pip")),("dla",{"rel":"Mum","name":"Leo","age":"5to15"},everything("dla")),("aa",{"who":"me"},AA_STEPS),("aa",{"who":"parent","name":"Mum","signer":"poa"},AA_STEPS),("aa",{"who":"partner"},AA_STEPS),
          ("pip",{"who":"me"},PIP_STEPS),("pip",{"who":"other","name":"Sam"},PIP_STEPS),("dla",{},DLA_STEPS),
          ("dla",{},{**DLA_STEPS,"about":{"rel":"Dad","name":"Mia","age":"u3"}})]
def pages(form,about,steps):
    """Every page the person would see (walk() saves each page as they go, so later pages show their follow-ups)."""
    d={"wf_v":1} if form in("aa","dla") else {}; seen=set(); st={"about":about,**steps}
    while True:
        ids=[k for k,_ in I.sections(form,d)]; nxt=[k for k in ids if k not in seen]
        if not nxt: break
        sec=nxt[0]; seen.add(sec); yield sec,re.sub(r"<script.*?</script>","",I.section_body(form,sec,d),flags=re.S)
        d=I.save(form,sec,d,FM(st.get(sec,{})))
missing=[]; checked=set()
for form,about,steps in PERSONAS:
    for sec,body in pages(form,about,steps):
        for n,vals in groups(body).items():
            checked.add((form,n))
            if exempt(n) or has_else(n,vals,body): continue
            missing.append(f"{form}/{sec}: {n} {sorted(vals)[:6]}")
print(f"tap lists checked: {len(checked)}")
assert not missing, "No 'Something else' on:\n  "+"\n  ".join(sorted(set(missing)))
# the AA bad-days question has 'It varies a lot' and Something else
b=I.section_body("aa","daily",{"who":"me"})
assert 'name="bad" value="varies"' in b and 'name="bad_xon"' in b
d=I.save("aa","daily",{"who":"me"},FM({"bad":"varies","bad_xon":"1","bad_x":"Depends on the weather"}))
it,_=I.topic_texts("aa",d); assert "varies a lot" in it and "Depends on the weather" in it, it
print("something else everywhere: OK")

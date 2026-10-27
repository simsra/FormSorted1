"""Strength check v2: only real gaps on hard tasks, max 3, taps, never no-difficulty/blank, never re-ask."""
import quality, intake as INTAKE
from forms import FORMS
def simon():
    ok={"lvl":"ok"}
    return {"who":"me","name":"Pat","bad":"3","nights":"7","ntimes":"4+","night":["meds"],"falls":"0",
     "rows":{"bed":ok,"toilet":ok,"dress":ok,"eat":ok,"meds":ok,"comm":ok,"social":ok,
             "wash":{"lvl":"help","help":True,"c":["every","long","feet"],"days":"7"},
             "indoors":{"lvl":"help","help":True,"c":["every"],"days":"7"}}}
I=simon(); G=quality.gaps_v4("aa",I)
assert 0<len(G)<=3, G
rids={g["rid"] for g in G}; assert rids<={"wash","indoors"}, rids          # never no-difficulty tasks
assert all(g["kind"]!="days" for g in G)                                 # v4 days-per-week counts as frequency
assert not any(g["rid"]=="wash" and g["kind"]=="time" for g in G)       # 'takes twice as long' already answered
assert G[0]["kind"]=="safe" and G[0]["opts"]==quality.Q_SAFE              # safety ranked first
# all no difficulty -> nothing to ask
assert quality.gaps_v4("aa",{"rows":{r[0]:{"lvl":"ok"} for r in INTAKE.AA_ROWS}})==[]
assert quality.gaps_v4("aa",{})==[]
# answered -> never re-asked; fall tap becomes a grounded sentence and a row fact
g=[x for x in G if x["rid"]=="indoors" and x["kind"]=="safe"][0]
s=quality.gap_sentence("aa",I,g,"fall"); assert s=="Moving around indoors: I have had a fall doing this.", s
quality.apply_gap(I,g,"fall"); assert "wrong" in I["rows"]["indoors"]["c"]
assert not any(x["rid"]=="indoors" and x["kind"]=="safe" for x in quality.gaps_v4("aa",I))
g2=[x for x in quality.gaps_v4("aa",I) if x["kind"]=="safe"][0]
quality.apply_gap(I,g2,""); assert not any(x["rid"]==g2["rid"] and x["kind"]=="safe" for x in quality.gaps_v4("aa",I))   # 'something else' only
assert quality.gap_sentence("aa",I,g2,"","Slipped getting out once")=="Washing, bathing and showering: Slipped getting out once."
assert quality.gap_sentence("aa",I,g2,"bogus")==""
# days asked only when missing; third person for someone else
J={"who":"mum","name":"Ann","rows":{"bed":{"lvl":"cant","c":[]}}}
k={x["kind"] for x in quality.gaps_v4("aa",J)}; assert "safe" in k
gd={"rid":"bed","topic":"29","label":"Getting in and out of bed","kind":"days"}
assert "7 days a week" in quality.gap_sentence("aa",J,gd,"7")
# at most 3 across many hard tasks
H={"rows":{r[0]:{"lvl":"cant"} for r in INTAKE.AA_ROWS}}; assert len(quality.gaps_v4("aa",H))==3
# legacy chat forms: never flag no difficulty / none / blank, max 3
T=FORMS["aa"]["topics"]; ans={t:"I have no difficulty." for t,_,_ in T}; ans["34"]="None."; ans["44"]=""
assert quality.check_legacy_v2(ans,T,"aa")==[]
ans["31"]="I struggle."; ans["33"]="Hard."; ans["29"]="Bad."; ans["30"]="Difficult."
L=quality.check_legacy_v2(ans,T,"aa"); assert 0<len(L)<=3 and all(len(x["flags"])<=2 for x in L)
print("test_strength OK")

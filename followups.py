"""Quick checks (30 Oct 2026): a completeness check per DWP descriptor before anything is written.
For every task the customer said is hard we look at what we already know about the six things DWP decides on:
how often, how long, who helps, aids, what could go wrong (safety) and a real example. Anything we can work out
from earlier answers counts as known and is never asked again. Gemini picks which gaps matter most for that
descriptor (at most 2 per task, a small total per form); if Gemini can't be reached the same rules pick them.
Every check is ONE short line with tap answers plus 'Something else', and every check can be skipped.
The answers go into the customer's facts as 'Checked with you: ...' so the writer and the answer check use them."""
import json, os
import intake as I
DIMS=("often","long","who","aids","risk","example")
CAP={"aa":3,"dla":3,"pip":2}; PER_TOPIC=2   # 30 Oct: kept low so the whole journey is no longer than before (screens.py)
OFTEN=[("every","Every day"),("most","Most days"),("some","Some days"),("rarely","Now and then")]
LONG=[("lt10","Under 10 min"),("10_30","10 to 30 min"),("30_60","30 to 60 min"),("60p","Over an hour")]
WHO=[("partner","My partner"),("family","Family"),("friend","A friend or neighbour"),("carer","A paid carer"),("nobody","No one, so it goes undone")]
RISK=[("fall","Could fall"),("hurt","Could get hurt or burnt"),("choke","Could choke"),("miss","Would forget or miss it"),("undone","Wouldn't get done properly")]
# aids that count as 'known' for a task, and the ones offered as chips
AIDS={"bed":["Grab rails","Bed rails or safe space bed","Commode"],"toilet":["Raised toilet seat","Grab rails","Commode"],"wash":["Shower seat","Grab rails","Perching stool"],
 "indoors":["Walking stick","Walking frame","Stairlift","Wheelchair","Crutches"],"meds":["Pill organiser","Alarms or reminders on phone"],"comm":["Hearing aid","Glasses"],
 "a1":["Perching stool","Grab rails"],"a3":["Pill organiser","Alarms or reminders on phone"],"a4":["Shower seat","Grab rails"],"a5":["Grab rails","Raised toilet seat"],
 "a7":["Hearing aid"],"a12":["Walking stick","Crutches","Wheelchair"],"walk":["Buggy or wheelchair"],"a11":["Alarms or reminders on phone"]}
OFTEN_WF={"superv":("superv_g",),"out":("out_g",),"dev":("dev_g",),"comm":("comm_g",),"indoors":("pr_indoors",)}
TIMED={"bed","toilet","wash","dress","eat","indoors","a1","a2","a4","a5","a6"}
RISKY={"bed","toilet","wash","indoors","eat","meds","a1","a2","a3","a4","a5","a11","a12","walk","out","superv"}
RISK_FX={"wrong","burn","std_safe","fell","safe","danger","road","choke","swallow","falls","mix","harm","lt20"}
def _rows(form,d):
    out=[]
    for r in I.rows(form,None,d):
        v=(d.get("rows") or {}).get(r[0]) or {}
        if v.get("lvl") in ("slow","help","cant") or v.get("help") or v.get("hard"): out.append((r,v))
    return out
def known(form,d,r,v):
    """Which of the six things we can already tell from earlier answers (never ask these)."""
    rid=r[0]; w=d.get("wf") or {}; c=set(v.get("c") or []); fu=(d.get("fu") or {})
    k=set()
    if I._ok(v.get("days")) or I._ok(v.get("freq")) or w.get(f"t_{rid}") or "every" in c or any(w.get(x) for x in OFTEN_WF.get(rid,())): k.add("often")
    if I._ok(v.get("time")) or "long" in c or any(x.startswith(f"m_{rid}") and w.get(x) for x in w): k.add("long")
    if form=="dla" or w.get("hp_rel") or "nobody" in c or (w.get("hp_any")=="yes" and w.get("hp_what")) or v.get("lvl") in ("ok","slow"): k.add("who")
    al=AIDS.get(rid)
    if not al or any(a in (d.get("aids") or []) for a in al) or I.X(d,"aids"): k.add("aids")
    if rid not in RISKY or c&RISK_FX or (rid=="indoors" and d.get("falls") not in (None,"","0")): k.add("risk")
    if v.get("x") or v.get("lvl")!="cant": k.add("example")
    if rid not in TIMED: k.add("long")   # 'how long' only means something for a task with a start and an end
    for dim in DIMS:
        if f"{rid}_{dim}" in fu: k.add(dim)
    return k
def gaps(form,d):
    """[(rid, label, topic, [missing dims])] for the hard tasks."""
    out=[]
    for r,v in _rows(form,d):
        miss=[x for x in DIMS if x not in known(form,d,r,v)]
        if miss: out.append((r[0],r[2],r[1],miss))
    return out
PRI={"risk":0,"often":1,"who":2,"long":3,"aids":4,"example":5}
def pick_rules(form,d,G):
    """No-Gemini fallback: the most important gap per task (safety first), worst tasks first, up to the cap."""
    R=d.get("rows") or {}; order={"cant":0,"help":1,"slow":2}
    G=sorted(G,key=lambda g:order.get((R.get(g[0]) or {}).get("lvl"),3))
    out=[]; used={}
    for rid,_,_,m in G:   # vary the checks: the same kind of question over and over feels like a test
        dim=sorted(m,key=lambda x:(used.get(x,0),PRI[x]))[0]; used[dim]=used.get(dim,0)+1; out.append((rid,dim))
    return out[:CAP[form]]
SYS="""You decide which short follow-up checks would most improve a UK benefit form (AA1, DLA1A or PIP2) before it is written.
For each hard task you get what the customer already told us and the details still missing. DWP decides on: what can't be done,
how often, how long it takes, safety risks, who helps and aids. Pick only the checks that would change how well the answer shows
the need. Prefer safety and how often. Skip a task whose answer is already clear. Never pick more than 2 per task or more than
CAP in total. Never pick 'example' unless the task is 'cant' and nothing in the customer's own words covers it. Return JSON only."""
SCHEMA={"type":"object","properties":{"picks":{"type":"array","items":{"type":"object","properties":{"task":{"type":"string"},"need":{"type":"string","enum":list(DIMS)}},"required":["task","need"]}},
  "enough":{"type":"array","items":{"type":"string"}}},"required":["picks"]}
def pick(form,d):
    """Choose the checks for this order: [(rid, dim)], stored with the reason it came from."""
    G=gaps(form,d)
    if not G: return [],"no gaps"
    import gem
    if gem.mock(): return pick_rules(form,d,G),"rules"
    intro,T=I.topic_texts(form,d); R=d.get("rows") or {}
    tasks=[{"task":rid,"name":lab,"level":(R.get(rid) or {}).get("lvl"),"known":T.get(top,""),"missing":m} for rid,lab,top,m in G]
    try:
        out=gem.call(gem.FOLLOW,SYS.replace("CAP",str(CAP[form])),json.dumps({"form":form,"about":intro,"own_words":d.get("words",""),"tasks":tasks},ensure_ascii=False),SCHEMA,purpose="followups",timeout=int(os.getenv("FOLLOWUP_TIMEOUT","10")),retries=0)
    except Exception as e:
        print("FOLLOWUPS fallback:",str(e)[:160],flush=True); return pick_rules(form,d,G),"rules"
    ok={rid:set(m) for rid,_,_,m in G}; seen=set(); per={}; P=[]
    for p in out.get("picks") or []:
        rid,dim=str(p.get("task")),str(p.get("need"))
        if dim in ok.get(rid,()) and (rid,dim) not in seen and per.get(rid,0)<PER_TOPIC:
            seen.add((rid,dim)); per[rid]=per.get(rid,0)+1; P.append((rid,dim))
    return P[:CAP[form]],"gemini"
def _task(lab,me):
    return lab
def question(form,d,rid,dim):
    """One short line with tap answers (always 'Something else'); the example is the only free text, and it's optional."""
    import wholeform as W
    P=W.PR(d,form); me=I.is_me(d,form); lab=dict((r[0],r[2]) for r in I.rows(form,None,d))[rid]
    who=[(v,t if me else t.replace("My partner",f"{P['poss'].capitalize()} partner").replace("No one, so it goes undone","No one, so it goes undone")) for v,t in WHO]
    if form=="dla": who=[("parent","Me, the parent"),("other","Another adult"),("nobody","No one")]
    risk=[(v,t) for v,t in RISK if not (v=="choke" and rid not in ("eat","a2")) and not (v=="hurt" and rid in ("comm","a7","a8","a10"))]
    aids=[(a,a) for a in AIDS.get(rid,[])]+[("none","Nothing")]
    q={"often":(f"{lab}: how often is it like this?","radio",OFTEN,""),
       "long":(f"{lab}: how long does it take {P['obj']}?","radio",LONG,""),
       "who":(f"{lab}: who helps?","radio",who,""),
       "aids":(f"{lab}: is anything used to help?","checks",aids,""),
       "risk":(f"{lab}: what could happen without help?","checks",risk,""),
       "example":(f"{lab}: a recent example (optional)","text",[],"e.g. \u201cLast week I couldn\u2019t\u2026\u201d" if me else "e.g. \u201cLast week she couldn\u2019t\u2026\u201d")}[dim]
    Q=W.Q(f"fu_{rid}_{dim}",q[0],q[1],q[2],hint="Skip if you're not sure." if dim!="example" else "Skip this if you like.",ph=q[3],maxlen=200)
    return Q
def questions(form,d):
    return [question(form,d,rid,dim) for rid,dim in (d.get("fu_qs") or [])]
LBL={"often":"how often","long":"how long it takes","who":"who helps","aids":"what's used to help","risk":"what could happen without help","example":"example"}
def absorb(form,d):
    """Turn the answers into 'Checked with you' facts (customer's own taps/words), and keep a coverage map."""
    w=d.get("wf") or {}; fu=d.setdefault("fu",{}); cl=d.setdefault("clarify",{}); rows={r[0]:r for r in I.rows(form,None,d)}
    for q in questions(form,d):
        rid,dim=q["id"][3:].rsplit("_",1); lab=rows[rid][2]
        v=w.get(q["id"]); x=w.get(q["id"]+"_x","")
        opts=dict(q["opts"]); parts=[opts[t] for t in (v if isinstance(v,list) else [v] if v else []) if t in opts]+([x] if x else [])
        if q["kind"]=="text": parts=[v] if v else []
        fu[f"{rid}_{dim}"]="answered" if parts else "skipped"
        if parts: cl[q["id"]]={"s":f"{lab}, {LBL[dim]}: "+"; ".join(parts)+".","topic":rows[rid][1]}
        else: cl.pop(q["id"],None)
    d["coverage"]=coverage(form,d)
def coverage(form,d):
    """Per hard task: which of the six things were already known, which we asked about, and the result."""
    out={}; asked={(r,dm) for r,dm in (d.get("fu_qs") or [])}; fu=d.get("fu") or {}
    for r,v in _rows(form,d):
        kn=known(form,d,r,v); row={}
        for dim in DIMS:
            st=fu.get(f"{r[0]}_{dim}")
            row[dim]=("asked: "+st) if (r[0],dim) in asked and st else "asked" if (r[0],dim) in asked else "known" if dim in kn else "not asked"
        out[r[2]]=row
    return out
CUES={"safety":"That's the hardest part done.","often":"Nearly done with everyday help.","more":"Just a few quick taps to make your answers stronger.",
      "you":"Great, the health questions are done. Now the details DWP needs.","child":"Great, the care questions are done. Now the details DWP needs.","out":"Halfway there."}

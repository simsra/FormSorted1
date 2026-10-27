"""Strength check: rule-based flags for thin or vague answers before download.
LLM hook: set quality.LLM_CHECK = callable(topic_label, answer) -> list[str] to add model-generated prompts later."""
import re
LLM_CHECK=None
FREQ=r"\b(\d+|once|twice|every|each|daily|nightly|weekly|a day|a week|a night|a month|most (days|nights|mornings)|times?|always|usually|often|days? a week|nights? a week)\b"
DUR=r"\b(\d+\s*(min|mins|minutes|hours?|hrs?|seconds)|takes?|took|long|all day|all night|quarter of an hour|half an hour)\b"
HELP=r"\b(help|helps|helped|prompt|remind|someone|partner|daughter|son|wife|husband|carer|parent|mum|dad|i need|needs|assist|support|aid|aids|frame|stick|rail|seat|supervis|watch|hold)"
SAFE=r"\b(fall|fell|falls|danger|safe|safely|unsafe|risk|hurt|injur|burn|choke|wander|run off|runs off|accident|scald)"
BAD=r"\b(bad days?|good days?|flare|vary|varies|worse|better days|some days|on bad|exhaust|after(wards)?)\b"
SAFETY_TOPICS=("34","40","44","outdoors","supervision_day","65","a1","a4","a11","a12","daycare","night","42","30","31","33")
NA_TOPICS=("conditions","statement","school","senses","development","37","39","other","a7","a8","a10")
WORK_IMPACT=r"\b(takes? (me )?(longer|twice|ages)|miss(ed|es)?|can't|cannot|unable|struggle|hard|difficult|mistakes?|late|deadline|pain|tired|exhaust)"
SUPPORT_SPECIFIC=r"\b(software|equipment|chair|desk|keyboard|mouse|screen|headset|support worker|job coach|coach|coaching|interpreter|taxi|travel|hours? a week|adapt|ramp|parking)"
def check_atw(answers, topics):
    out=[]
    for tid,label,_ in topics:
        a=(answers.get(tid) or "").strip(); low=a.lower(); fl=[]
        if not a: out.append({"id":tid,"label":label,"answer":a,"flags":["Nothing written yet. Add a sentence if this applies to you."],"blank":True}); continue
        if len(a)<60: fl.append("This is quite short. Add a real example from work.")
        if tid=="job" and not re.search(r"\b\d+\s*(hours?|days?)\b",low): fl.append("Hours? Say how many hours or days a week you work.")
        if tid in("barriers","communication"):
            if not re.search(FREQ,low): fl.append("How often? Say how often this happens at work (every day, a few times a week).")
            if not re.search(WORK_IMPACT,low): fl.append("What's the effect? Say what happens at work (it takes longer, mistakes, missed deadlines, pain).")
        if tid=="travel" and not re.search(r"\b(bus|train|tube|drive|car|walk|taxi|lift|cycle|bike|home)\b",low): fl.append("How do you travel? Say how you get to work and what makes it hard, if anything.")
        if tid=="support" and not re.search(SUPPORT_SPECIFIC,low): fl.append("Be specific: name the equipment, software, support worker hours or travel help you think you need.")
        if tid=="tried" and not re.search(r"\b(help(ed)?|didn't|did not|work(ed)?|still)\b",low): fl.append("Did it help? Say whether what was tried made a difference.")
        out.append({"id":tid,"label":label,"answer":a,"flags":fl})
    return out
def check(answers, topics, form=None):
    if form=="atw": return check_atw(answers, topics)
    """answers: {topic_id: text}; topics: [(id,label,prompt)]. Returns list of {id,label,answer,flags:[...]}."""
    out=[]; all_text=" ".join(answers.values()).lower()
    for tid,label,_ in topics:
        a=(answers.get(tid) or "").strip(); low=a.lower(); flags=[]
        if not a:
            out.append({"id":tid,"label":label,"answer":a,"flags":["Nothing written yet. If there's no difficulty, leave it blank. If there is, add a sentence or two."],"blank":True}); continue
        if len(a)<80: flags.append("This is quite short. Add a real example of what happens.")
        if tid not in NA_TOPICS:
            if not re.search(FREQ,low): flags.append("How often? Say how many times a day, or how many days or nights a week.")
            if not re.search(DUR,low) and tid not in ("a7","a8","a9","a10","37","39"): flags.append("How long? Say how long it takes, or how long help is needed each time.")
            if not re.search(HELP,low): flags.append("What help? Say who helps, what they do, or what aids are used.")
            if tid in SAFETY_TOPICS and not re.search(SAFE,low): flags.append("Safety? Say if anything has gone wrong or could go wrong without help (falls, burns, danger).")
        if LLM_CHECK:
            try: flags+=list(LLM_CHECK(label,a))
            except Exception: pass
        out.append({"id":tid,"label":label,"answer":a,"flags":flags})
    if not re.search(BAD,all_text):
        out.insert(0,{"id":"_bad","label":"Good days and bad days","answer":"","flags":["None of your answers mention bad days or how things vary. Say what a bad day is like and how many bad days you have a week."]})
    return out
def score(results):
    flagged=sum(1 for r in results if r["flags"] and not r.get("blank")); total=sum(1 for r in results if not r.get("blank"))
    return flagged,total

# ---------- v2 (Oct 2026): "We can make these stronger" ----------
# Only real gaps on tasks the customer said are hard, ranked by impact, at most 3, asked as taps.
# Never flags "no difficulty", "none" or blank optional sections; v4 days-per-week, bad days and night counts count as frequency.
NODIFF=r"(\bno difficulty\b|\bno problems?\b|\bnone\b|\bno falls\b|\bnot applicable\b|\bn/a\b|^no\.?$|\bdoesn't apply\b|\bdoes not apply\b|\bmanage(s)? fine\b)"
MAX_GAPS=3
SAFE_ROWS={"aa":("bed","toilet","wash","indoors","meds"),"dla":("wash","indoors","walk","out","eat"),"pip":("a1","a3","a4","a5","a11","a12")}
NO_TIME_ROWS=("superv","comm","social","see","hear","speak","dev","out","a7","a8","a9","a10","a11")
SAFE_DONE=("wrong","burn","std_safe","fell","safe","falls","choke","danger","road")
Q_SAFE=[("fall","Fall"),("near","Near-miss"),("no","No")]
Q_TIME=[("lt10","Under 10 min"),("10_30","10–30 min"),("30_60","30–60 min"),("60p","Over an hour")]
Q_DAYS=[(str(i),str(i)) for i in range(1,8)]
LVL_W={"cant":3,"help":2,"slow":1}
def _lvl(v): return v.get("lvl") or ("cant" if v.get("hard") and v.get("help") else "help" if v.get("help") else "slow" if v.get("hard") else "")
def gaps_v4(form,I):
    """Ranked list of tap questions for hard tasks only. Each: {rid,topic,label,kind,q,opts,score}."""
    import intake as INTAKE
    R=I.get("rows") or {}; asked=I.get("gaps") or {}; out=[]; me=INTAKE.is_me(I,form)
    for rid,topic,label,_,_ in INTAKE.rows(form,None,I):
        v=R.get(rid) or {}; lv=_lvl(v)
        if not lv or v.get("lvl")=="ok": continue
        w=LVL_W[lv]; c=set(v.get("c") or []); done=asked.get(rid) or {}
        if rid in SAFE_ROWS.get(form,()) and not (c & set(SAFE_DONE)) and "safe" not in done:
            out.append({"rid":rid,"topic":topic,"label":label,"kind":"safe","q":"Has anything gone wrong doing this?","opts":Q_SAFE,"score":w*3})
        if not INTAKE._ok(v.get("days")) and not INTAKE._ok(v.get("freq")) and "days" not in done:
            out.append({"rid":rid,"topic":topic,"label":label,"kind":"days","q":"How many days a week is it like this?","opts":Q_DAYS,"score":w*2.5,"noelse":True})
        if rid not in NO_TIME_ROWS and "long" not in c and not INTAKE._ok(v.get("time")) and "time" not in done:
            out.append({"rid":rid,"topic":topic,"label":label,"kind":"time","q":("How long does it take you each time?" if me else "How long does it take each time?"),"opts":Q_TIME,"score":w*2})
    out.sort(key=lambda g:-g["score"]); seen=set(); top=[]
    for g in out:   # one question per task first, so 3 different tasks get a look-in
        if g["rid"] in seen: continue
        seen.add(g["rid"]); top.append(g)
        if len(top)==MAX_GAPS: return top
    for g in out:
        if g not in top: top.append(g)
        if len(top)==MAX_GAPS: break
    return top
def gap_sentence(form,I,g,val,other=""):
    """The customer's own tapped answer as a plain sentence (used as their words for drafting and grounding)."""
    import intake as INTAKE
    me=INTAKE.is_me(I,form); who=INTAKE.name(I,form); L=g["label"]
    if g["kind"]=="safe":
        s={"fall":(f"I have had a fall doing this" if me else f"{who} has had a fall doing this"),"near":(f"I have had a near-miss doing this" if me else f"{who} has had a near-miss doing this"),"no":"Nothing has gone wrong doing this so far"}.get(val,"")
    elif g["kind"]=="days": s=f"It is like this {val} days a week" if val in dict(Q_DAYS) else ""
    else: s=f"Each time takes {INTAKE.TIME_T[val]}" if val in dict(Q_TIME) else ""
    other=(other or "").strip()[:500]
    if other: s=(s+". " if s else "")+other.rstrip(".")
    return f"{L}: {s}." if s else ""
def apply_gap(I,g,val):
    """Record the tap so it is never asked again, and update the row facts it covers."""
    r=(I.setdefault("rows",{})).setdefault(g["rid"],{}); I.setdefault("gaps",{}).setdefault(g["rid"],{})[g["kind"]]=val or "else"
    if g["kind"]=="safe" and val in ("fall","near"): r["c"]=list(dict.fromkeys((r.get("c") or [])+["wrong"]))
    if g["kind"]=="days" and val in dict(Q_DAYS): r["days"]=val
    if g["kind"]=="time" and val in dict(Q_TIME): r["time"]=val
def check_legacy_v2(answers,topics,form=None):
    """Chat-based forms: the old rules, but never flag no-difficulty/none/blank, and only the top 3, 2 prompts each."""
    res=[x for x in check(answers,topics,form) if x["flags"] and not x.get("blank") and x["id"]!="_bad" and not re.search(NODIFF,x["answer"].lower())]
    for x in res: x["flags"]=[f for f in x["flags"] if not f.startswith("This is quite short")][:2] or x["flags"][:1]
    res.sort(key=lambda x:-len(x["flags"])); return res[:MAX_GAPS]

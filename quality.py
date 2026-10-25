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

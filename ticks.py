"""Tick boxes on the official AA1 (11/25) and DLA1A (10/25) forms.
We only PROPOSE ticks from the customer's approved answers (simple, explainable word matches).
The customer sees every tick on a preview page and confirms or changes each one; only confirmed choices are written.
Never ticked by us: consent, declarations, signing-for-someone-else, residence/nationality, benefits, bank, checklist boxes."""
import os, re
from pypdf import PdfReader
HERE=os.path.dirname(os.path.abspath(__file__))
HELP=r"\b(help|helps|helped|assist|support|I (lift|hold|guide|walk behind)|carer)\b"
NEG=r"(can't|cannot|can not|couldn't|unable to|not able to|struggles? to|doesn't|does not)"
# (field, question shown to the customer, topic, rule)
# rule: "gate" -> Yes when the topic has an approved answer; "more" -> Yes when we filled that question's free-text box;
#       (regex, state) or (regex, state, regex2) -> state when the approved answer matches regex (and regex2)
AA=[
 ("x29","Q29: Do you usually have difficulty or need help getting in or out of bed?","29","gate"),
 ("x29-1","Q29: Difficulty getting into bed","29",(r"into bed","/Yes")),
 ("x29-2","Q29: Difficulty getting out of bed","29",(r"out of bed|sit up|swing (her|his|their|my) legs|get up in the morning","/Yes")),
 ("x29-3","Q29: Need help getting into bed","29",(r"into bed","/Yes",HELP)),
 ("x29-4","Q29: Need help getting out of bed","29",(r"out of bed|sit up|swing (her|his|their|my) legs","/Yes",HELP)),
 ("x29-7","Q29: Anything else to tell us? (our prepared answer goes in this box)","29","more"),
 ("x30","Q30: Difficulty or help with toilet needs?","30","gate"),
 ("x30-8","Q30: Anything else to tell us?","30","more"),
 ("x31","Q31: Difficulty or help with washing, bathing or showering?","31","gate"),
 ("x31-11","Q31: Anything else to tell us?","31","more"),
 ("x32","Q32: Difficulty or help with dressing or undressing?","32","gate"),
 ("x32-9","Q32: Anything else to tell us?","32","more"),
 ("x33","Q33: Difficulty or help moving around indoors?","33","gate"),
 ("x33-1","Q33: Difficulty walking around indoors","33",(r"walk|frame|stick|indoors","/Yes")),
 ("x33-2","Q33: Difficulty going up or down stairs","33",(r"stair","/Yes")),
 ("x33-3","Q33: Difficulty getting in or out of a chair","33",(r"chair","/Yes")),
 ("x33-5","Q33: Need help walking around indoors","33",(r"walk|indoors","/Yes",HELP)),
 ("x33-6","Q33: Need help going up or down stairs","33",(r"stair","/Yes",HELP+r"|walk behind")),
 ("x33-7","Q33: Need help getting in or out of a chair","33",(r"chair","/Yes",HELP)),
 ("x33-10","Q33: Anything else to tell us?","33","more"),
 ("x34","Q34: Do you fall or stumble?","34",(r"\b(fell|falls?|fallen)\b","/Fall")),
 ("x34-3","Q34: Do you need help to get up after a fall?","34",(NEG+r" (to )?get (her|him|them|my|me)?\s*(self |selves )?up|pendant|alarm|help(ed)? (her|him|them|me) up","/Yes")),
 ("x34-2","Q34: Have you been referred to a Falls Clinic?","34",(r"falls clinic","/Yes")),
 ("x35","Q35: Difficulty or help with eating and drinking?","35","gate"),
 ("x35-6","Q35: Anything else to tell us?","35","more"),
 ("x36","Q36: Difficulty or help with medicines or treatment?","36","gate"),
 ("x36-7","Q36: Anything else to tell us?","36","more"),
 ("x37","Q37: Do you usually need help to communicate?","37","gate"),
 ("x37-1","Q37: Difficulty understanding people you do not know well","37",(r"understand(ing)? (people|others|what)","/Yes")),
 ("x37-3","Q37: Difficulty concentrating or remembering things","37",(r"forget|remember|memory|concentrat|confus","/Yes")),
 ("x37-4","Q37: Difficulty answering or using the phone","37",(r"phone","/Yes")),
 ("x37-5","Q37: Difficulty reading letters, filling in forms, replying to mail","37",(r"read|letters|post\b|mail|forms","/Yes")),
 ("x37-9","Q37: Need help concentrating or remembering things","37",(r"forget|remember|memory|concentrat|confus","/Yes",HELP+r"|remind")),
 ("x37-10","Q37: Need help answering or using the phone","37",(r"phone","/Yes",HELP)),
 ("x37-11","Q37: Need help reading letters, filling in forms, replying to mail","37",(r"letters|post\b|mail|forms","/Yes",HELP+r"|I read|reads? (them|it|her|him|my|me)\b|reads")),
 ("x37-13","Q37: Anything else to tell us?","37","more"),
 ("x39","Q39: Do you need help to take part in hobbies, social or religious activities?","39","gate"),
 ("x40","Q40: Do you usually need someone to keep an eye on you?","40","gate"),
 ("x40-2","Q40: Not aware of common dangers","40",(r"danger","/Yes")),
 ("x40-5","Q40: May wander","40",(r"wander","/Yes")),
 ("x40-7","Q40: May have fits, dizzy spells or blackouts","40",(r"\bfits?\b|dizz|blackout|faint","/Yes")),
 ("x40-8","Q40: May get confused","40",(r"confus","/Yes")),
 ("x40-11","Q40: Anything else to tell us?","40","more"),
 ("x42","Q42: Difficulty or help during the night?","42","gate"),
 ("x42-17","Q42: Anything else to tell us?","42","more"),
 ("302","Q44: Do you usually need someone to watch over you at night?","44","gate"),
 ("308","Q44: Watching over because you may get confused","44",(r"confus","/Yes")),
 ("306","Q44: Watching over because you may wander","44",(r"wander","/Yes")),
 ("312","Q44: Anything else to tell us?","44","more"),
]
DLA=[
 ("42","Q42: Do the child's needs stay the same most days, or change from day to day?","42",(r"vary|varies|change|bad days?|good days?|depends","/Changes from day to day")),
 ("44","Q44: Difficulty standing and moving around?","walking","gate"),
 ("48","Q48: Other difficulties during or after standing and moving around?","walking",(r"pain|tired|exhaust|breathless|sore|ache","/Yes")),
 ("49","Q49: Need guidance or supervision most of the time outdoors?","outdoors","gate"),
 ("49_3","Q49: Can they walk safely next to a busy road?","outdoors",(r"road|traffic|run(s)? off|bolt","/No")),
 ("49_4","Q49: Can they cross a road safely?","outdoors",(r"road|traffic|run(s)? off|bolt","/No")),
 ("49_5","Q49: Can they understand common dangers outdoors?","outdoors",(r"no sense of danger|(not|n't) (understand|aware of|recogni[sz]e) (common )?danger","/No")),
 ("49_6","Q49: Do they regularly become anxious, distressed, confused or disorientated?","outdoors",(r"anxi|panic|distress|meltdown|confus|disorient","/Yes")),
 ("50","Q50: Do they fall due to their condition?","outdoors",(r"\b(fell|falls?|fallen)\b","/Yes")),
 ("55","Q55: Need help to manage toilet needs?","daycare",(r"toilet|nappy|nappies|pad|wet|soil|wipe","/Yes")),
 ("55_7","Q55: manage nappies or pads","daycare",(r"nappy|nappies|pads?\b","/manage nappies or pads")),
 ("56","Q56: Need help moving around indoors, stairs, chairs?","daycare",(r"stair|indoors|chair","/Yes")),
 ("57","Q57: Need help with washing, bathing, showering?","daycare",(r"wash|bath|shower","/Yes")),
 ("58","Q58: Need help to dress and undress?","daycare",(r"dress|clothes|button|zip|shoes|socks","/Yes")),
 ("59","Q59: Need help to eat and drink?","daycare",(r"\beat|drink|food|meal|feed","/Yes")),
 ("60","Q60: Need help with medication or treatments at home?","daycare",(r"medic|inhaler|insulin|treatment|tablet|physio","/Yes")),
 ("61","Q61: Difficulty seeing?","senses",(r"\bsee\b|sight|vision|visual","/Yes")),
 ("62","Q62: Difficulty hearing?","senses",(r"hear|deaf","/Yes")),
 ("63","Q63: Difficulty speaking?","senses",(r"speak|speech|words|verbal","/Yes")),
 ("64","Q64: Difficulty and need help communicating?","senses",(r"communicat|understand|makaton|pecs|sign","/Yes")),
 ("65","Q65: Fits, blackouts or seizures?","65","gate"),
 ("66","Q66: Need to be supervised during the day to keep them safe?","supervision_day","gate"),
 ("66_1","Q66: Can they recognise and react to common dangers?","supervision_day",(r"no sense of danger|(not|n't) (understand|aware of|recogni[sz]e) (common )?danger","/No")),
 ("66_3","Q66: Can they cope with unplanned changes to routine?","supervision_day",(r"change|routine","/No")),
 ("66_4","Q66: Do they regularly feel anxious or panic?","supervision_day",(r"anxi|panic","/Yes")),
 ("66_5","Q66: Do they regularly become upset or frustrated?","supervision_day",(r"upset|frustrat|meltdown|tantrum","/Yes")),
 ("66_9","Q66: Do they regularly act impulsively?","supervision_day",(r"impuls|run(s)? off|bolt","/Yes")),
 ("66_10","Q66: Do they regularly become overwhelmed or distressed?","supervision_day",(r"overwhelm|distress|meltdown","/Yes")),
 ("67","Q67: Need extra help with their development?","development","gate"),
 ("68","Q68: Need encouragement, prompting or assistance at school or nursery?","school","gate"),
 ("70","Q70: Wake and need assistance or supervision during the night?","night","gate"),
 ("36","Q36: Is this a specialist school?","school",(r"specialist school","/Yes")),
 ("37_1","Q37: Does the child have an Educational Health Care Plan?","school",(r"\bEHCP\b|education,? health and care plan","/Educational Health Care Plan")),
 ("41","Q41: Does the child use any aids or adaptations?","daycare",(r"aids used","/Yes")),
]
CATALOG={"aa":AA,"dla":DLA}
PDF={"aa":"aa1.pdf","dla":"dla1a.pdf"}
_OPTS={}
def options(form):
    """{field: (page, [on-states])} read from the bundled official PDF."""
    if form in _OPTS: return _OPTS[form]
    r=PdfReader(os.path.join(HERE,PDF[form])); o={}
    for i,p in enumerate(r.pages):
        for a in p.get("/Annots") or []:
            a=a.get_object(); par=a.get("/Parent"); par=par.get_object() if par else {}
            if (a.get("/FT") or par.get("/FT"))!="/Btn": continue
            n=str(a.get("/T") or par.get("/T"))
            for k in (a.get("/AP",{}).get("/N",{}) or {}).keys():
                if k!="/Off":
                    pg,st=o.setdefault(n,(i+1,[]))
                    if k not in st: st.append(k)
    _OPTS[form]=o; return o
def label(state): return re.sub(r"[\x00-\x1f]","",state.lstrip("/")).replace("\u00d0","-").strip()
def _snip(txt,m): s=max(0,m.start()-50); return ("…" if s else "")+txt[s:m.end()+50].strip()+("…" if m.end()+50<len(txt) else "")
def _negated(txt,m):
    """'I am not confused', 'never falls': skip matches directly negated (but 'can't read' is a difficulty, so kept)."""
    if re.search(r"\b(not|never|no)\s+(\w+\s+){0,2}$",txt[max(0,m.start()-30):m.start()],re.I): return True
    # 28 Oct: 'I have no difficulty getting in and out of bed' -> the whole sentence is negated, not just the next 2 words
    sent=re.split(r"[.!?\n]\s*",txt[:m.start()])[-1]
    return bool(re.search(r"\bno (difficulty|difficulties|problems?|trouble|help needed)\b|\bdoes(n't| not) need\b",sent,re.I))
def propose(form, answers, filled=None):
    """Return list of dicts: field, question, page, options, proposed (state or ''), why (customer-facing evidence)."""
    a=answers or {}; out=[]; opts=options(form); filled=filled or {}
    for field,q,topic,rule in CATALOG.get(form,[]):
        if field not in opts: continue
        txt=(a.get(topic) or "").strip(); st=""; why="Not discussed, so we have left this blank. Tick it yourself if it applies."
        if rule=="gate":
            if txt: st,why="/Yes","You described help for this question."
        elif rule=="more":
            if txt: st,why="/Yes","We have written your approved answer in this question's box."
        else:
            rx,state,*need=rule; m=next((m for m in re.finditer(rx,txt,re.I) if not _negated(txt,m)),None)
            if not m and txt: why="Not mentioned in your approved answer, so we have left this blank. Tick it yourself if it applies."
            if m and (not need or re.search(need[0],txt,re.I)): st,why=state,f'Based on your approved answer: "{_snip(txt,m)}"'
        if st and st not in opts[field][1]: st=""
        out.append({"field":field,"question":q,"topic":topic,"page":opts[field][0],"options":opts[field][1],"proposed":st,"why":why})
    return out
def propose_tapped(form, answers, intake_ticks, no_diff=()):
    """Proposals for orders that came through the tap questions (28 Oct fix).
    The taps are the source of truth: a box is ticked only if the customer tapped something that maps to it,
    and 'No difficulty' answers the form's Yes/No question with No. Wording in the drafted answers never adds a tick
    (before this, 'I have no difficulty getting in and out of bed' ticked 'difficulty getting out of bed')."""
    it=intake_ticks or {}; out=propose(form,answers)
    for x in out:
        st=it.get(x["field"],"")
        rule=next(r for f,_,_,r in CATALOG[form] if f==x["field"])
        if not st and rule=="more" and x["topic"] not in no_diff and x["proposed"]: st=x["proposed"]   # we wrote text in that box
        if not st and rule=="more" and x["topic"] in no_diff: st="/No"   # nothing else to tell for a 'no difficulty' question
        parent=re.split(r"[-_]",x["field"])[0]
        if not st and isinstance(rule,tuple) and parent!=x["field"] and it.get(parent) not in (None,"","/No") and x["proposed"]:
            st=x["proposed"]   # a detail box under a question they tapped Yes, backed by a quote from their approved answer
        if st and st not in x["options"]: st=""
        x["proposed"]=st
        x["why"]=("You told us there's no difficulty with this." if st=="/No" else
                  "We have written your approved answer in this question's box." if st and rule=="more" else
                  "From what you tapped in the questions." if st else
                  "You didn't tap anything for this, so we have left it blank. Tick it yourself if it applies.")
    return out
def validate(form, choices):
    """Keep only catalogued fields and real on-states. choices: {field: state or ''}"""
    opts=options(form); ok={f for f,*_ in CATALOG.get(form,[])}
    return {f:s for f,s in (choices or {}).items() if f in ok and f in opts and s in opts[f][1]}
def apply(writer, choices):
    """Set check/radio widgets: matching widget gets its on-state, siblings /Off; parent /V set."""
    from pypdf.generic import NameObject
    done=0
    for p in writer.pages:
        for a in p.get("/Annots") or []:
            a=a.get_object(); par=a.get("/Parent"); po=par.get_object() if par else None
            n=str(a.get("/T") or (po.get("/T") if po else ""))
            if n not in choices: continue
            want=choices[n]; ons=[k for k in (a.get("/AP",{}).get("/N",{}) or {}).keys() if k!="/Off"]
            if want in ons:
                a[NameObject("/AS")]=NameObject(want); done+=1
                tgt=po if (po is not None and "/T" in po and not a.get("/T")) else a
                tgt[NameObject("/V")]=NameObject(want)
            else: a[NameObject("/AS")]=NameObject("/Off")
    return done

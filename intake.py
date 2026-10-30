"""Intake v4 (on top of v3): tap-first questions for AA1, DLA1A and PIP2 (no chat).
Each fact is asked once. Taps map straight to form tick boxes and number boxes; we also turn the taps into plain
sentences (the customer's own answers) that the drafter and the grounding check use as the source.
Before payment we only collect answers: nothing here shows advice, answer text or drafts."""
import re, os
from html import escape as esc
FORMS_V3=("aa","dla","pip")
FREQ=[("rarely","Rarely"),("some","Some days"),("most","Most days"),("every","Every day"),("ns","Not sure")]
TIME=[("lt10","Under 10 min"),("10_30","10–30 min"),("30_60","30–60 min"),("60p","Over an hour"),("ns","Not sure")]
FREQ_T=dict(FREQ); TIME_T={"lt10":"under 10 minutes","10_30":"10 to 30 minutes","30_60":"30 to 60 minutes","60p":"over an hour","ns":""}
def C(cid,text,*ticks,help=()): return (cid,text,list(ticks),list(help))
# Rows: (id, topic id in forms.py, label, gate tick (field,state) or None, chips)
AA_ROWS=[
 ("bed","29","Getting in and out of bed",("x29","/Yes"),[C("out","Getting out of bed",("x29-2","/Yes"),help=[("x29-4","/Yes")]),C("in","Getting into bed",("x29-1","/Yes"),help=[("x29-3","/Yes")]),C("turn","Sitting up or turning over")]),
 ("toilet","30","Using the toilet",("x30","/Yes"),[C("onoff","Getting on and off the toilet"),C("acc","Accidents or wears pads"),C("clean","Cleaning themselves"),C("often","Needs to go often or urgently")]),
 ("wash","31","Washing, bathing and showering",("x31","/Yes"),[C("in","Getting in or out of the bath or shower"),C("hair","Washing hair"),C("fell","Has slipped or fallen in the bathroom"),C("feet","Washing feet or lower body"),C("groom","Shaving, teeth or appearance")]),
 ("dress","32","Dressing and undressing",("x32","/Yes"),[C("fast","Buttons, zips or fastenings"),C("feet","Socks and shoes"),C("choose","Choosing suitable clothes"),C("slow","Takes a very long time")]),
 ("indoors","33","Moving around indoors",("x33","/Yes"),[C("walk","Walking between rooms",("x33-1","/Yes"),help=[("x33-5","/Yes")]),C("stairs","Stairs",("x33-2","/Yes"),help=[("x33-6","/Yes")]),C("chair","Getting up from a chair",("x33-3","/Yes"),help=[("x33-7","/Yes")])]),
 ("eat","35","Eating and drinking",("x35","/Yes"),[C("cut","Cutting up food"),C("cup","Holding cups or cutlery"),C("forget","Forgets to eat or drink"),C("swallow","Chewing or swallowing")]),
 ("meds","36","Medicines and treatment",("x36","/Yes"),[C("forget","Forgets medicines"),C("open","Opening packets or bottles"),C("mix","Mixes up doses"),C("treat","Needs help with treatment (e.g. creams, eye drops, injections)")]),
 ("comm","37","Communicating",("x37","/Yes"),[C("und","Understanding people they don't know well",("x37-1","/Yes")),C("mem","Remembering or concentrating",("x37-3","/Yes"),help=[("x37-9","/Yes")]),C("phone","Using the phone",("x37-4","/Yes"),help=[("x37-10","/Yes")]),C("read","Reading letters or filling in forms",("x37-5","/Yes"),help=[("x37-11","/Yes")]),C("hear","Hearing or sight")]),
 ("social","39","Hobbies, seeing people, faith activities",("x39","/Yes"),[C("get","Getting there"),C("with","Needs someone with them"),C("stopped","Has stopped going because of this")]),
]
DLA_ROWS=[
 ("toilet","daycare","Toilet, nappies or pads",("55","/Yes"),[C("pads","Still in nappies or pads",("55_7","/manage nappies or pads")),C("wipe","Wiping and cleaning"),C("acc","Accidents"),C("remind","Needs reminding to go")]),
 ("wash","daycare","Washing and bathing",("57","/Yes"),[C("in","Getting in and out of the bath"),C("hair","Hair washing (distress or refuses)"),C("safe","Not safe left alone in the bath")]),
 ("dress","daycare","Dressing",("58","/Yes"),[C("fast","Fastenings, socks and shoes"),C("sens","Sensory issues with clothes"),C("order","Getting clothes on in the right order")]),
 ("eat","daycare","Eating and drinking",("59","/Yes"),[C("cut","Needs food cut up or to be fed"),C("limited","Very limited diet"),C("choke","Choking or swallowing problems"),C("tube","Tube feeding")]),
 ("indoors","daycare","Moving around indoors and stairs",("56","/Yes"),[C("stairs","Stairs"),C("lift","Needs lifting or carrying"),C("chair","Getting on and off chairs")]),
 ("meds","daycare","Medicines and treatment at home",("60","/Yes"),[C("meds","Medicines given"),C("inhaler","Inhaler or nebuliser"),C("physio","Physio or exercises"),C("monitor","Monitoring (e.g. blood sugar)")]),
 ("see","senses","Seeing",("61","/Yes"),[]),("hear","senses","Hearing",("62","/Yes"),[]),("speak","senses","Speaking",("63","/Yes"),[]),
 ("comm","senses","Communicating and being understood",("64","/Yes"),[C("signs","Uses signs, pictures or a device"),C("instr","Doesn't follow instructions")]),
 ("superv","supervision_day","Needs watching during the day",("66","/Yes"),[C("danger","No sense of danger",("66_1","/No")),C("change","Can't cope with changes to routine",("66_3","/No")),C("anx","Anxious or panics",("66_4","/Yes")),C("upset","Gets very upset or frustrated",("66_5","/Yes")),C("imp","Acts impulsively or runs off",("66_9","/Yes")),C("over","Becomes overwhelmed",("66_10","/Yes")),C("harm","Hurts themselves or others")]),
 ("dev","development","Learning, play and social skills",("67","/Yes"),[C("play","Needs help to play"),C("social","Needs help with social skills"),C("learn","Needs help to learn at home")]),
]
DLA_MOB=[
 ("walk","walking","Walking",("44","/Yes"),[C("pain","Pain",("48","/Yes")),C("tired","Gets very tired",("48","/Yes")),C("breath","Breathless",("48","/Yes")),C("carry","Needs carrying or a buggy/wheelchair")]),
 ("out","outdoors","Being outdoors",("49","/Yes"),[C("road","Runs off or no road sense",("49_3","/No"),("49_4","/No")),C("danger","Doesn't understand dangers",("49_5","/No")),C("anx","Anxious, distressed or meltdowns outside",("49_6","/Yes")),C("falls","Falls",("50","/Yes"))]),
]
PIP_A=[("a1","Preparing food",[C("hob","Using a hob or cooker safely"),C("chop","Chopping or lifting pans"),C("micro","Can only use a microwave"),C("prompt","Needs prompting to cook")]),
 ("a2","Eating and drinking",[C("cut","Cutting food"),C("mouth","Getting food to mouth"),C("prompt","Needs prompting to eat"),C("tube","Tube feeding")]),
 ("a3","Medicines and treatment",[C("remind","Needs reminding"),C("monitor","Monitoring symptoms or blood sugar"),C("therapy","Therapy at home")]),
 ("a4","Washing and bathing",[C("in","Getting in or out of the bath or shower"),C("hair","Washing hair"),C("safe","Unsafe alone (falls, fits, dizziness)")]),
 ("a5","Toilet needs",[C("onoff","Getting on and off the toilet"),C("clean","Cleaning yourself"),C("incont","Incontinence")]),
 ("a6","Dressing",[C("fast","Fastenings, socks and shoes"),C("choose","Choosing suitable clothes"),C("prompt","Needs prompting to change")]),
 ("a7","Talking and hearing",[C("hear","Hearing"),C("speak","Speaking"),C("und","Understanding what people say")]),
 ("a8","Reading",[C("basic","Basic signs and labels"),C("complex","Letters and complex information")]),
 ("a9","Mixing with people",[C("anx","Severe anxiety or distress"),C("someone","Needs someone with them"),C("avoid","Avoids people completely")]),
 ("a10","Money and bills",[C("change","Working out change"),C("bills","Budgeting and bills")]),
 ("a11","Planning and following journeys",[C("unfam","Unfamiliar journeys"),C("alone","Can't go out alone"),C("panic","Panic or anxiety going out"),C("lost","Gets lost or confused")]),
 ("a12","Moving around",[C("lt20","Can't walk more than 20 metres"),C("lt50","Can't walk more than 50 metres"),C("pain","Pain, breathlessness or exhaustion"),C("wheel","Uses a wheelchair")]),
]
PIP_STD=[("safe","Not safely"),("std","Not to a good standard"),("repeat","Not again when needed"),("slow","Only very slowly")]
PIP_ROWS=[(i,i,l,None,ch) for i,l,ch in PIP_A]
CONDS={"aa":["Arthritis","Dementia or memory problems","Heart condition","COPD or breathing problems","Stroke","Parkinson's","Diabetes","Sight loss","Hearing loss","Depression or anxiety","Cancer"],
 "dla":["Autism","ADHD","Learning disability","Cerebral palsy","Epilepsy","Speech and language delay","Global developmental delay","Down's syndrome","Asthma","Diabetes","Sensory processing difficulties"],
 "pip":["Anxiety","Depression","Back or joint pain","Arthritis","Fibromyalgia","ME or chronic fatigue","MS","Epilepsy","Diabetes","COPD or asthma","Autism or ADHD","PTSD"]}
TREAT=[("tabs","Tablets"),("inj","Injections"),("inh","Inhaler"),("phys","Physio"),("talk","Talking therapy"),("none","No treatment"),("ns","Not sure")]
AIDS={"aa":["Walking stick","Walking frame","Wheelchair","Stairlift","Grab rails","Shower seat","Commode","Raised toilet seat","Pendant alarm","Pill organiser","Hearing aid"],
 "dla":["Buggy or wheelchair","Ear defenders","Visual timetable","Car seat harness","Hearing aid","Glasses","Bed rails or safe space bed","Feeding equipment"],
 "pip":["Walking stick","Crutches","Wheelchair","Grab rails","Shower seat","Perching stool","Pill organiser","Hearing aid","Alarms or reminders on phone"]}
# 30 Oct (last screen): 'Who knows about your condition?' (was 'Who knows you well?'). Professionals get an optional name line.
PEOPLE={"aa":["GP","Nurse","Consultant or specialist","Social worker","Carer","Family or friend"],
 "dla":["GP","Nurse or health visitor","Paediatrician or specialist","Teacher or SENCo","Social worker","Carer","Family or friend"],
 "pip":["GP","Nurse","Consultant or specialist","Social worker","Carer","Family or friend"]}
PROF_PEOPLE={"GP","Nurse","Consultant or specialist","Social worker","Nurse or health visitor","Paediatrician or specialist","Teacher or SENCo"}
# 'Is there anything you need help with but no one is there to help?' -> the form box each one belongs to
NOHELP=[("wash","Washing"),("meals","Meals"),("night","At night"),("out","Going out"),("meds","Taking medicines")]
NOHELP_WHAT={"wash":"with washing","meals":"with meals","night":"at night","out":"with going out","meds":"with taking medicines"}
NOHELP_TOPIC={"aa":{"wash":"31","meals":"35","night":"42","out":"39","meds":"36"},
 "dla":{"wash":"daycare","meals":"daycare","night":"night","out":"outdoors","meds":"daycare"},
 "pip":{"wash":"a4","meals":"a1","night":"other","out":"a11","meds":"a3"}}
OWN_TOPIC={"aa":"40","dla":"42","pip":"other"}   # where free words sit in the transcript (the writer may use them in any box)
SCHOOL=[("ehcp","Has an EHCP (or plan in progress)"),("one","1:1 support"),("special","Specialist school or unit"),("reduced","Reduced timetable"),("transport","School transport"),("notatschool","Not in school or nursery")]
NIGHT_DLA=[("night_bed","Getting into or out of bed"),("night_toilet","Toilet, nappy or pad change"),("night_treatment","Medicine or treatment"),("night_settle","Settling back to sleep"),("night_danger","Keeping them safe"),("night_wander","Wandering"),("night_behaviour","Behaviour or distress")]
SECTIONS={"aa":[("about","About them"),("conds","Health conditions"),("daily","Everyday help"),("safety","Nights and safety"),("finish","Aids and anything else")],
 "dla":[("about","About your child"),("conds","Health conditions"),("daily","Everyday care"),("safety","Nights, safety and getting out"),("finish","School, aids and anything else")],
 "pip":[("about","About you"),("conds","Health conditions"),("daily","Everyday tasks"),("out","Talking, people and getting out"),("finish","Aids and anything else")]}
def rows(form,sec=None,data=None):
    """Grid rows for a section (sec=None: all rows for the form)."""
    if form=="aa": return AA_ROWS if sec in (None,"daily") else []
    if form=="dla":
        mob=DLA_MOB if (data or {}).get("age")!="u3" else []
        if sec is None: return DLA_ROWS+mob
        return {"daily":DLA_ROWS,"safety":mob}.get(sec,[])
    if sec is None: return PIP_ROWS
    return {"daily":PIP_ROWS[:6],"out":PIP_ROWS[6:]}.get(sec,[])
# ---------- rendering ----------
def name(d,form):
    n=(d.get("name") or "").strip()
    if n: return n
    if form=="dla": return "your child"
    if d.get("who","me") in ("me",""): return "you"
    # 30 Oct: no name given for someone else -> a noun that works as subject and object ('them' gave "does them have")
    return {"parent":"your parent","partner":"your partner"}.get(d.get("who"),"the person you help")
def is_me(d,form): return form!="dla" and d.get("who","me") in ("me","")
def _chk(n,v,txt,on,cls=""): return f'<label class="chip{cls}"><input type=checkbox name="{n}" value="{esc(v)}" {"checked" if on else ""}><span>{esc(txt)}</span></label>'
def _rad(n,v,txt,cur): return f'<label class=chip><input type=radio name="{n}" value="{esc(v)}" {"checked" if cur==v else ""}><span>{esc(txt)}</span></label>'
def _radios(n,opts,cur,cls="",x=None): return f"<div class='chips{cls}'>"+"".join(_rad(n,v,t,cur) for v,t in opts)+(_else(n,x) if x is not None else "")+"</div>"
def _else(n,txt):
    """'Something else' chip that reveals a short text box for this question (stored per question)."""
    return f'<span class=else><label class=chip><input type=checkbox name="{n}_xon" value=1 {"checked" if txt else ""}><span>Something else</span></label><input class=elsebox name="{n}_x" value="{esc(txt or "")}" maxlength=200 placeholder="Tell us briefly" aria-label="Something else: tell us briefly"></span>'
def _checks(n,opts,cur,x=None): cur=cur or []; return "<div class=chips>"+"".join(_chk(n,v,t,v in cur) for v,t in opts)+(_else(n,x) if x is not None else "")+"</div>"
def other_txt(fm,n):
    """The 'Something else' text for question n, only if its chip is on."""
    return re.sub(r"\s+"," ",str(fm.get(f"{n}_x") or "")).strip()[:200] if fm.get(f"{n}_xon") else ""
def X(d,k): return (d.get("else") or {}).get(k,"")
def _q(label,inner,hint=""): return f'<fieldset class=iq><legend>{esc(label)}</legend>{f"<p class=hint>{esc(hint)}</p>" if hint else ""}{inner}</fieldset>'
def NUM(a,b): return [(str(i),str(i)) for i in range(a,b+1)]+[("ns","Not sure")]
# v4: one tap per task ("On most days..."), then at most 2 follow-ups, shown only when it isn't fine (assessor-style prompts).
LVL=[("ok","No difficulty"),("slow","Slow, painful or tiring"),("help","Needs help or watching"),("cant","Can't do it or unsafe")]
FX=[("every","Needs help every time"),("long","Takes twice as long or more"),("rest","Has to stop and rest"),("pain","Pain or exhaustion afterwards"),("wrong","Fall or near-miss"),("half","Result not good enough (half-done, not clean)"),("prompt","Needs reminding, encouraging or watching"),("aid","Uses an aid for it, even sometimes"),("nobody","Nobody there to help, so goes without")]
PIP_FX=[("std_safe","Not safe doing it alone"),("burn","Burns, cuts or near-misses")]
DAYS=[(str(i),str(i)) for i in range(1,8)]+[("ns","Not sure")]
FX_T={"every":"needs help every time","long":"takes at least twice as long as normal","rest":"has to stop and rest","pain":"pain or exhaustion afterwards","wrong":"has had a fall or near-miss doing it","half":"the result is not good enough (half-done or not clean)","prompt":"needs reminding, encouraging or watching","aid":"uses an aid for it, at least sometimes","nobody":"there is nobody there to help, so it goes without","std_safe":"not safe doing it alone","burn":"has had burns, cuts or near-misses doing it"}
# 'What happens?' per card: 2-4 task options + the assessor probes that matter for that task, never more than 6.
FX_ALL=dict(FX+PIP_FX)
CARD={"aa":{"bed":("out in",["every","long","pain","wrong"]),"toilet":("onoff acc clean",["every","long","wrong"]),"wash":("in fell feet",["every","long","pain"]),
 "dress":("fast feet choose",["every","long","pain"]),"indoors":("walk stairs chair",["every","pain","wrong"]),"eat":("cut forget swallow",["every","long","prompt"]),
 "meds":("forget open mix",["prompt","wrong","every"]),"comm":("und mem phone read",["prompt","every"]),"social":("get with stopped",["prompt","pain","nobody"])},
 "dla":{"superv":("danger imp over anx change harm",[]),"walk":("pain tired breath carry",["wrong","rest"]),"out":("road danger anx falls",["every","prompt"]),"_":(None,["every","long","prompt"])},
 "pip":{"a1":("hob chop prompt",["std_safe","long","burn"]),"a9":("anx someone avoid",["prompt","every"]),"a10":("change bills",["prompt","every","nobody"]),
 "a11":("unfam alone panic lost",["prompt","every"]),"a12":("lt20 lt50 wheel",["pain","std_safe","rest"]),"_":(None,["std_safe","long","pain"])}}
def card_opts(form,rid,chips):
    t,f=CARD[form].get(rid) or CARD[form].get("_") or (None,["every","long","pain"])
    cm={c[0]:c[1] for c in chips}; ids=t.split() if t else [c[0] for c in chips[:3]]
    tk=[(i,cm[i]) for i in ids if i in cm]; fx=[(x,FX_ALL[x]) for x in f][:6-len(tk)]
    return tk,fx
def pw(t,me,form):
    """Chip wording for who the form is about (30 Oct: 'Cleaning themselves' was shown to people filling it in for themselves)."""
    if form=="dla": return t.replace("Cleaning yourself","Cleaning themselves")
    if me: return t.replace("themselves","yourself").replace("they don't","you don't").replace("with them","with you")
    return t.replace("yourself","themselves")
def row_card(form,r,d):
    rid,topic,label,gate,chips=r; cur=(d.get("rows") or {}).get(rid,{}); me=is_me(d,form)
    lvl=cur.get("lvl") or ("cant" if cur.get("hard") and cur.get("help") else "help" if cur.get("help") else "slow" if cur.get("hard") else "")
    tk,fx=card_opts(form,rid,chips); cv=cur.get("c") or []
    tk=[(v,pw(t,me,form)) for v,t in tk]
    fu=cur.get("fu") or {}
    # 30 Oct: each tapped chip opens its own one-line follow-up right under it (same card, same screen)
    opts="".join(_chk(f"r_{rid}_c",v,t,v in cv,cls=f" fx-{v}")+fu_block(form,rid,v,fu.get(v),d) for v,t in tk+fx)
    lf="".join(fu_block(form,rid,"lvl:"+lv,fu.get("lvl:"+lv),d,cls=f" fu-lvl fu-lvl-{lv}") for lv in ("slow","help","cant"))
    more=lf+'<p class=sub>What happens? <span class=hint>(tap any)</span></p><div class="chips two">'+opts+_else(f"r_{rid}_c",cur.get("x",""))+'</div>'
    more+='<p class=sub>How many days a week is it like this?</p>'+_radios(f"r_{rid}_days",DAYS,cur.get("days")," nums",x=cur.get("days_x",""))
    lvls="".join(_rad(f"r_{rid}_lvl",v,t,lvl) for v,t in LVL)+_else(f"r_{rid}_lvl",cur.get("lvl_x",""))
    return f'<div class=card><h3>{esc(label)}</h3><div class="chips main lvl">{lvls}</div><div class=more>{more}</div></div>'
# ---------- inline follow-ups on activity cards (30 Oct 2026, Simon: 'ask a little more about what they tapped, and let them type') ----------
# One short line under each tapped chip, on the same card (never a new screen): 2-3 taps that matter under the official
# criteria (how often, how long, safety/falls, who helps) + Something else, and an always-visible box for their own words.
# Typed words are kept exactly as typed; the box is never required (one gentle nudge on Next).
FU_T={  # template: (question for Me, question for someone else / {n}=name, taps)
 "last":("When was the last time?","When was the last time?",[("week","Last week"),("month","Last month"),("months","Last few months")]),
 "who":("Who helps you?","Who helps {n}?",[("partner","Partner"),("family","Family"),("carer","Carer"),("noone","No one, but I need it|No one, but they need it")]),
 "lasts":("How long does it last?","How long does it last?",[("hour","About an hour"),("hours","A few hours"),("day","The rest of the day or more")]),
 "long":("How long does it take you?","How long does it take {n}?",[("15","About 15 min"),("30","About 30 min"),("60","An hour or more")]),
 "often":("How often does it happen?","How often does it happen?",[("day","Every day"),("week","A few times a week"),("less","Less often")]),
 "risk":("What could happen?","What could happen?",[("fall","A fall or getting hurt"),("undone","It doesn't get done"),("upset","Distress or panic")]),
 "age":("Compared with other children the same age?","Compared with other children the same age?",[("far","Far more help than them"),("more","More help than them"),("same","About the same")]),
}
# chip -> (template, example for the text box: written as {I}/{my}/{me} so it reads right for Me, a parent or a child)
FU_C={
 "every":("who","e.g. {I} need someone to help with this every morning"), "long":("long","e.g. it takes {me} 40 minutes and {I} have to sit down twice"),
 "rest":("lasts","e.g. {I} have to stop after a few steps to get {my} breath"), "pain":("lasts","e.g. {my} back aches for the rest of the morning"),
 "wrong":("last","e.g. {I} slipped getting out of bed in June and hurt {my} hip"), "half":("often","e.g. {I} can't rinse {my} hair properly, so it's left soapy"),
 "prompt":("often","e.g. {I} forget unless someone reminds {me}"), "aid":("often","e.g. {I} use a frame, but still need a hand"),
 "nobody":("risk","e.g. {I} go without a wash when no one is there"), "std_safe":("risk","e.g. {I} get dizzy and could fall"),
 "burn":("last","e.g. {I} burned {my} hand on a pan last month"),
 "out":("who","e.g. {I} need pulling up, it takes a few goes"), "in":("who","e.g. {I} can't lift {my} legs in without help"),
 "onoff":("who","e.g. {I} need a hand to get up off the toilet"), "acc":("often","e.g. {I} don't always get there in time at night"),
 "clean":("who","e.g. {I} can't reach to wipe properly"), "fell":("last","e.g. {I} slipped getting out of the bath in June and hurt {my} hip"),
 "feet":("who","e.g. {I} can't bend to reach {my} feet"), "fast":("who","e.g. {my} fingers can't do up small buttons"),
 "choose":("often","e.g. {I} put on summer clothes in winter"), "walk":("risk","e.g. {I} hold on to the furniture to get around"),
 "stairs":("risk","e.g. {I} go up on {my} bottom, one step at a time"), "chair":("who","e.g. {I} need a push to stand up"),
 "cut":("who","e.g. {I} can't grip a knife, so someone cuts it up"), "forget":("often","e.g. {I} skip lunch unless someone reminds {me}"),
 "swallow":("risk","e.g. {I} choke on dry food a few times a week"), "open":("who","e.g. {I} can't press tablets out of the blister pack"),
 "mix":("last","e.g. {I} took the evening tablets twice last week"), "und":("who","e.g. {I} need someone to explain what the doctor said"),
 "mem":("often","e.g. {I} lose track halfway through a conversation"), "phone":("who","e.g. {I} can't hear well enough on the phone"),
 "read":("who","e.g. someone reads {my} letters to {me}"), "get":("who","e.g. {I} need a lift, {I} can't manage the bus"),
 "with":("who","e.g. {I} get anxious if no one is with {me}"), "stopped":("last","e.g. {I} stopped going to church last year"),
 # PIP
 "hob":("risk","e.g. {I} forget the hob is on"), "chop":("risk","e.g. {I} drop pans, {my} grip goes"), "mouth":("who","e.g. {I} spill food, {my} hand shakes"),
 "remind":("often","e.g. {I} forget {my} tablets unless reminded"), "monitor":("who","e.g. {my} partner checks {my} blood sugar"),
 "therapy":("long","e.g. physio exercises take 30 minutes a day"), "incont":("often","e.g. accidents most nights"),
 "hear":("who","e.g. {I} need someone to repeat things"), "speak":("who","e.g. people can't understand {me}, so someone speaks for {me}"),
 "basic":("who","e.g. {I} can't read signs, someone reads for {me}"), "complex":("who","e.g. someone reads {my} letters to {me} and explains it all"),
 "someone":("who","e.g. {I} only go out if {my} sister comes too"), "avoid":("last","e.g. {I} haven't seen anyone outside the family for months"),
 "bills":("who","e.g. {my} son pays {my} bills, {I} get muddled"), "unfam":("who","e.g. {I} get lost unless someone comes with {me}"),
 "alone":("risk","e.g. {I} panic and freeze if {I} go out alone"), "panic":("lasts","e.g. {I} shake and have to go home"),
 "lost":("last","e.g. {I} got lost coming back from the shop in March"), "lt20":("risk","e.g. {I} have to stop after 15 metres, {my} legs give way"),
 "change":("who","e.g. {I} can't work out change, so someone pays for {me}"), "safe":("risk","e.g. {I} get dizzy in the shower and have fallen"),
 "hair":("who","e.g. {I} can't lift {my} arms to wash {my} hair"), "anx":("lasts","e.g. {I} shake and can't leave the house"),
 "lt50":("risk","e.g. {I} have to stop at the corner because of pain"), "wheel":("who","e.g. someone pushes {me}, {I} can't self-propel"),
}
# DLA: the parent fills it in, so {I} is the child's name and the examples are in the parent's voice
FU_D={
 "every":("age","e.g. I help {me} every time, other children {my} age do it alone"), "long":("long","e.g. it takes 30 minutes because {I} won't keep still"),
 "prompt":("age","e.g. I have to stand over {me} and remind {me} every step"), "wrong":("last","e.g. {I} fell off the bed last week"),
 "rest":("lasts","e.g. {I} sits down on the pavement and won't move"),
 "pads":("age","e.g. {I} still needs pads day and night"), "wipe":("age","e.g. {I} can't wipe properly, so I do it every time"),
 "hair":("age","e.g. {I} screams and fights when I wash {my} hair"), "safe":("risk","e.g. {I} has had seizures in the bath"),
 "sens":("long","e.g. labels hurt, so getting dressed takes 30 minutes"), "order":("age","e.g. {I} puts clothes on back to front"),
 "limited":("age","e.g. {I} only eats 5 foods, I make separate meals"), "choke":("last","e.g. {I} choked on pasta last week"),
 "lift":("age","e.g. I lift {me} in and out of the bath"), "meds":("long","e.g. 3 medicines a day, 10 minutes each time"),
 "inhaler":("long","e.g. nebuliser twice a day, 20 minutes each time"), "physio":("long","e.g. stretches every evening for 30 minutes"),
 "signs":("age","e.g. {I} uses pictures to ask for things"), "instr":("age","e.g. I have to repeat simple instructions many times"),
 "danger":("risk","e.g. {I} climbs on the window sill"), "imp":("last","e.g. {I} ran into the road last week"),
 "over":("lasts","e.g. a meltdown lasts an hour and I have to stay close"), "anx":("lasts","e.g. {I} panics in shops and can't calm down"),
 "change":("lasts","e.g. a change of plan means screaming for an hour"), "harm":("last","e.g. {I} bit {my} sister yesterday"),
 "play":("age","e.g. I have to sit with {me} to play"), "social":("age","e.g. {I} doesn't understand taking turns"),
 "learn":("age","e.g. homework takes an hour with me beside {me}"), "tired":("lasts","e.g. after a short walk {I} needs the buggy"),
 "breath":("lasts","e.g. {I} gets breathless after a few metres"), "carry":("age","e.g. I carry {me} after about 50 metres"),
 "road":("last","e.g. {I} pulled free and ran at the road in May"), "falls":("last","e.g. {I} fell on the pavement and cut {my} knee last week"),
}
FU_L={"slow":("long","e.g. it takes {me} twice as long and {I} need to sit down"),"help":("who","e.g. {my} daughter helps every morning and evening"),"cant":("risk","e.g. {I} tried last month and fell")}
FU_LD={"slow":("long","e.g. it takes an hour, other children {my} age take 10 minutes"),"help":("age","e.g. I do it all for {me}, other children {my} age manage alone"),"cant":("risk","e.g. {I} would fall if I let go")}
FU_P={"last":"Last time: {}.","who":"Who helps: {}.","lasts":"It lasts {}.","long":"It takes {}.","often":"It happens {}.","risk":"What could happen: {}.","age":"Compared with other children the same age: {}."}
FU_PROMPT="Tell us what happens"; FU_NUDGE="A few words here really helps your form."
def _fu_tpl(form,t): return {"who":"age"}.get(t,t) if form=="dla" else t   # DLA: the parent helps, so ask what scores (more than other children)
def _fu_say(s,form,d):
    """Example text in the person's own perspective (Me: I/my/me; someone else: they/their/them; DLA: the child's name)."""
    if is_me(d,form): return s.format(I="I",my="my",me="me")
    if form=="dla":
        n=(d.get("name") or "").strip() or "my child"; t=s.format(I=n,my="their",me="them")
        return t.replace("e.g. my child","e.g. My child")
    return s.format(I="they",my="their",me="them")
def fu_spec(form,key,d):
    """(template id, question, taps, example) for one chip id or 'lvl:<level>'."""
    me=is_me(d,form); nm=name(d,form)
    dla=form=="dla"; L,Cm=(FU_LD,FU_D) if dla else (FU_L,FU_C)
    t,ex=L.get(key[4:]) if key.startswith("lvl:") else Cm.get(key,("often","e.g. what happens, in a few words"))
    t=_fu_tpl(form,t); qm,qo,taps=FU_T[t]
    q=qm if me else qo.format(n=nm)
    taps=[(v,(l.split("|")[0] if me else l.split("|")[-1])) for v,l in taps]
    return t,q,taps,_fu_say(ex,form,d)
def known_who(d):
    """A 'who helps' answer already given on an earlier card (carried forward so it is one tap to confirm, never asked afresh)."""
    for v in (d.get("rows") or {}).values():
        for f in (v.get("fu") or {}).values():
            if f.get("tpl")=="who" and f.get("t") not in ("","else",None): return f["t"]
    return ""
def fu_block(form,rid,key,cur,d,cls=""):
    """Inline follow-up shown under its chip only once that chip is tapped (CSS); never its own screen."""
    t,q,taps,ex=fu_spec(form,key,d); f=dict(cur or {}); k=key.replace(":","_"); n=f"r_{rid}_f_{k}"; w=f"r_{rid}_w_{k}"
    if t=="who" and not f.get("t") and known_who(d): f["t"]=known_who(d); cls+=" carried"
    tp="".join(_rad(n,v,l,f.get("t")) for v,l in taps)+_rad(n,"else","Something else",f.get("t"))
    return (f'<div class="fu{cls}" data-fu="{t}"><p class=fuq>{esc(q)}</p><div class="chips futaps">{tp}</div>'
            f'<label class=fuw><span>{FU_PROMPT}</span><input type=text name="{w}" value="{esc(f.get("w",""))}" maxlength=300 placeholder="{esc(ex)}"></label>'
            f'<p class=carry>Same as before? Change it if not.</p><p class=nudge hidden>{FU_NUDGE}</p></div>')
def fu_keys(form,rid,chips):
    tk,fx=card_opts(form,rid,chips); return [v for v,_ in tk+fx]+["lvl:slow","lvl:help","lvl:cant"]
def fu_save(form,fm,rid,keys,d):
    out={}
    for key in keys:
        k=key.replace(":","_"); t=str(fm.get(f"r_{rid}_f_{k}") or "").strip()[:20]; w=str(fm.get(f"r_{rid}_w_{k}") or "")
        w=re.sub(r"\s+"," ",w).strip()[:300]   # their words exactly (spaces tidied, length capped)
        if t or w: out[key]={"t":t,"w":w,"tpl":fu_spec(form,key,d)[0]}
    return out
def fu_lines(form,r,v,d):
    """(their own words, tapped answers) for one card's follow-ups, words first."""
    rid,topic,label,gate,chips=r; cm={c[0]:c[1] for c in chips}; cm.update(FX_ALL); words=[]; taps=[]
    for key,f in (v.get("fu") or {}).items():
        if key.startswith("lvl:"):
            if v.get("lvl")!=key[4:]: continue
            what=dict(LVL).get(key[4:],"")
        else:
            if key not in (v.get("c") or []): continue
            what=pw(cm.get(key,key),is_me(d,form),form)
        if f.get("w"): words.append(f'"{f["w"]}" ({what.lower()})')
        t,q,tp,_=fu_spec(form,key,d); tl=dict(tp).get(f.get("t"))
        if tl: taps.append(FU_P[t].format(tl[0].lower()+tl[1:]))
    return words,taps
FU_JS="""<script>(function(){
 /* Inline follow-ups: one per tapped chip. If the same question is already showing on this card, only its words box shows.
    'Who helps' carries to the next cards (shown as a tap they can change). One gentle nudge on Next if a shown box is empty. */
 function vis(e){return e.offsetParent!==null}
 function tidy(card){var seen={};card.querySelectorAll('.fu').forEach(function(f){if(!vis(f))return;var t=f.dataset.fu;
   f.classList.toggle('dup',!!seen[t]&&!f.querySelector('.futaps input:checked'));seen[t]=1})}
 var last=null;
 document.querySelectorAll('.card').forEach(function(c){c.addEventListener('change',function(e){
   var i=e.target;if(i.closest('.fu[data-fu=who] .futaps')&&i.checked&&i.value!='else')last=i.value;
   if(!i.closest('.fu')&&last){setTimeout(function(){c.querySelectorAll('.fu[data-fu=who]').forEach(function(f){
     if(vis(f)&&!f.querySelector('.futaps input:checked')){var r=f.querySelector('.futaps input[value="'+last+'"]');if(r){r.checked=true;f.classList.add('carried')}}})},0)}
   if(i.closest('.fu .futaps'))i.closest('.fu').classList.remove('carried');
   setTimeout(function(){tidy(c)},0)})});
 document.addEventListener('click',function(e){var b=e.target.closest('button');if(!b||!(b.value==='next'||b.textContent==='Next question'))return;
   var empty=[].filter.call(document.querySelectorAll('.fu'),function(f){return vis(f)&&!f.dataset.nudged&&!f.querySelector('.fuw input').value.trim()});
   if(!empty.length)return;e.preventDefault();e.stopImmediatePropagation();empty.forEach(function(f){f.dataset.nudged=1});
   empty.forEach(function(f){f.querySelector('.nudge').hidden=false});empty[0].querySelector('.fuw input').focus()},true);
})();</script>"""
def sections(form,d):
    """Sections for this order: whole-form orders (wf_v) get the extra ones from wholeform.py."""
    import wholeform; return wholeform.sections(form,d or {})
def section_body(form,sec,d):
    import wholeform
    if wholeform.is_wf_section(sec): return wholeform.section_body(form,sec,d)
    nm=name(d,form); me=is_me(d,form); you=("you" if me else nm); h=""
    if sec=="about":
        if form=="dla":
            h+=_q("Who are you to the child?",_radios("rel",[("Mum","Mum"),("Dad","Dad"),("Grandparent","Grandparent"),("Guardian","Guardian")],d.get("rel"),x=X(d,"rel")))
            h+=_q("Child's first name",f'<input name=name value="{esc(d.get("name",""))}" autocomplete=off maxlength=40>',"We use it in the questions. Optional.")
            h+=_q("How old are they?",_radios("age",[("u3","Under 3"),("3to4","3 or 4"),("5to15","5 to 15"),("ns","Not sure")],d.get("age"),x=X(d,"age")))
        else:
            opts=[("me","Me"),("parent","My mum or dad"),("partner","My partner"),("other","Someone else")] if form=="aa" else [("me","Me"),("other","Someone I help")]
            h+=_q("Who is this form for?",_radios("who",opts,d.get("who")))
            # 30 Oct: only shown once 'someone else' is picked (one question per screen skips hidden ones); 'Me' never sees them
            dv=" ".join(v for v,_ in opts if v!="me")
            h+=f'<div class=wdep data-dep="who" data-vals="{dv}">'+_q("Their first name",f'<input name=name value="{esc(d.get("name",""))}" autocomplete=off maxlength=40 placeholder="e.g. Mum or Margaret">',"We use it in the questions. Optional.")+'</div>'
            h+=f'<div class=wdep data-dep="who" data-vals="{dv}">'+_q("Who will sign the form?",_radios("signer",[("them","They will sign it themselves"),("poa","I have Power of Attorney"),("appointee","I'm their appointee"),("deputy","I'm their deputy (Court of Protection)"),("ns","Not sure yet")],d.get("signer"),x=X(d,"signer")))+'</div>'
            h+=wholeform.DEP_JS

    elif sec=="conds":
        have={c.get("name"):c for c in d.get("conds") or []}
        yrs=[("","When did it start?")]+[(str(y),str(y)) for y in range(2026,1939,-1)]+[("ns","Not sure")]
        def sel(n,cur): return f'<select name="{n}" aria-label="When did it start">'+"".join(f'<option value="{v}" {"selected" if cur==v else ""}>{t}</option>' for v,t in yrs)+"</select>"
        lst=""
        for i,cn in enumerate(CONDS[form]):
            c=have.get(cn,{}); lst+=f'<div class=cond>{_chk(f"cond_{i}","1",cn,bool(c),cls=" k")}<div class=more>{sel(f"cond_{i}_since",c.get("since",""))}{_checks(f"cond_{i}_t",TREAT,c.get("treat"),c.get("tx",""))}</div></div>'
        others=[c for c in d.get("conds") or [] if c.get("name") not in CONDS[form]]+[{}]
        for j,c in enumerate(others[:3]):
            lst+=f'<div class="cond other"><input name="oc_{j}" value="{esc(c.get("name",""))}" placeholder="Another condition (type it)" maxlength=80 aria-label="Another condition">{sel(f"oc_{j}_since",c.get("since",""))}{_checks(f"oc_{j}_t",TREAT,c.get("treat"),c.get("tx",""))}</div>'
        h+=_q("Which health conditions or disabilities "+("do you have?" if me else f"does {nm} have?"),lst,"Tap each one that applies, then roughly when it started. No diagnosis needed.")
    elif sec in ("daily","out"):
        if sec=="daily":
            h+=_q("How many bad days in a normal week?",_radios("bad",NUM(0,7)[:-1]+[("varies","It varies a lot"),("ns","Not sure")],d.get("bad")," nums",x=X(d,"bad")),"A bad day is when things are harder than usual. We work out the rest.")
            # v4: AA 'days a week needing help' is no longer asked; it comes from the per-task days answers (see save)
        h+='<p class=lede2>How is each of these? One tap each. We only ask more if it isn\'t fine.</p>'+"".join(row_card(form,r,d) for r in rows(form,sec,d))+FU_JS
    elif sec=="safety":
        if form=="aa":
            h+='<div class=gq><div class=g>'+_q("Falls in the last year",_radios("falls",[("0","None"),("1-2","1–2"),("3-5","3–5"),("6+","6 or more"),("ns","Not sure")],d.get("falls"),x=X(d,"falls")))+'</div><div class=dep>'
            h+=_q("When was the last fall?",_radios("lastfall",[("week","This week"),("month","This month"),("months","1–6 months ago"),("year","Over 6 months ago"),("ns","Not sure")],d.get("lastfall"),x=X(d,"lastfall")))
            h+=_q("After a fall",_checks("fallx",[("getup","Can't get up without help"),("hurt","Was hurt or went to hospital"),("clinic","Referred to a falls clinic"),("alarm","Has a pendant alarm")],d.get("fallx"),X(d,"fallx")))+'</div></div>'
            h+=_q(f"Does someone need to keep an eye on {you} in the day?",_checks("eye",[("danger","Not aware of dangers"),("wander","May wander"),("fits","Dizzy spells, fits or blackouts"),("confused","Gets confused")],d.get("eye"),X(d,"eye")))
            h+=_q(f"How long can {you} safely be left alone?",_radios("alone",[("always","As long as needed"),("hours","A few hours"),("lt1","Under an hour"),("never","Not at all"),("ns","Not sure")],d.get("alone"),x=X(d,"alone")))
            h+='<div class=gq><div class=g>'+_q("Help during the night (after everyone has gone to bed)",_checks("night",[("toilet","Toilet"),("turn","Turning over or settling"),("pain","Pain or breathing"),("meds","Medicines"),("confused","Confused or distressed")],d.get("night"),X(d,"night")),"Skip if none.")+'</div><div class=dep>'
            h+=_q("Nights a week",_radios("nights",NUM(0,7),d.get("nights")," nums",x=X(d,"nights")))+_q("Times a night",_radios("ntimes",[("1","1"),("2","2"),("3","3"),("4+","4 or more"),("ns","Not sure")],d.get("ntimes"),x=X(d,"ntimes")))+_q("Minutes each time",_radios("nmins",TIME,d.get("nmins"),x=X(d,"nmins")))
            h+=_q(f"Does someone need to stay awake to watch over {you} at night?",_radios("watch",[("no","No"),("some","Some nights"),("most","Most nights"),("ns","Not sure")],d.get("watch"),x=X(d,"watch")))+'</div></div>'
        else:
            h+=_q("Fits, blackouts or seizures?",_radios("fits",[("no","No"),("month","Less than weekly"),("week","Weekly"),("day","Daily"),("ns","Not sure")],d.get("fits"),x=X(d,"fits")))
            h+=_q(f"Do {nm}'s needs change from day to day?" if d.get("name") else "Do their needs change from day to day?",_radios("varies",[("same","Mostly the same"),("varies","They change a lot"),("ns","Not sure")],d.get("varies"),x=X(d,"varies")))
            nn=d.get("nn") or []; q=d.get("nnum") or {}
            inner="".join(f'<div class=cond>{_chk("nn",k,t,k in nn,cls=" k")}<div class=more>{_radios(f"nn_{k}_n",[(str(i),f"{i} nights") for i in range(1,8)]+[("ns","Not sure")],q.get(k,{}).get("n"),x=q.get(k,{}).get("n_x",""))}{_radios(f"nn_{k}_t",[(str(i),f"{i}× a night") for i in range(1,5)]+[("ns","Not sure")],q.get(k,{}).get("t"),x=q.get(k,{}).get("t_x",""))}{_radios(f"nn_{k}_m",[("10","10 min"),("20","20 min"),("30","30 min"),("45","45 min"),("60","1 hour+"),("ns","Not sure")],q.get(k,{}).get("m"),x=q.get(k,{}).get("m_x",""))}</div></div>' for k,t in NIGHT_DLA)
            inner+=f'<div class=chips>{_else("nn",X(d,"nn"))}</div>'
            h+=_q(f"Help {nm} needs at night (after everyone is in bed)",inner,"Tap a reason, then nights a week, times a night and minutes. Skip if none.")
            if d.get("age")!="u3": h+='<p class=lede2>Getting out and about</p>'+"".join(row_card(form,r,d) for r in rows(form,"safety",d))+FU_JS
    elif sec=="finish":
        # 30 Oct: a pendant alarm tapped under falls is already ticked here (never ask the same thing twice)
        cur=d.get("aids") if d.get("aids") is not None else (["Pendant alarm"] if "alarm" in (d.get("fallx") or []) and "Pendant alarm" in AIDS[form] else [])
        h+=_q("Aids or equipment used",_checks("aids",[(a,a) for a in AIDS[form]],cur,X(d,"aids")))
        if form=="dla": h+=_q("School or nursery",_checks("school",SCHOOL,d.get("school"),X(d,"school")))
        h+=last_things(form,d)
    return h
# ---------- saving ----------
def save(form,sec,d,fm):
    """Merge one section's answers (starlette FormData) into d. Untouched rows/questions are simply skipped."""
    import wholeform
    if wholeform.is_wf_section(sec): return wholeform.save(form,sec,d,fm)
    if form in ("aa","dla") and wholeform.on() and "wf_v" not in d and not d.get("rows"): d["wf_v"]=1
    g=lambda k:(str(fm.get(k) or "").strip())[:200]; gl=lambda k:[str(x)[:80] for x in fm.getlist(k)]
    if sec=="about":
        for k in ("who","name","signer","rel","age"): d[k]=g(k)
        for k in ("signer","rel","age"): d.setdefault("else",{})[k]=other_txt(fm,k)
        d["name"]=re.sub(r"[^\w '\-.]","",d["name"])[:40]
        if form!="dla" and d.get("who") in ("me",""): d["signer"]=""; d["name"]=""; d["else"]["signer"]=""   # 'Me': no other-person answers kept
    elif sec=="conds":
        cs=[]
        for i,cn in enumerate(CONDS[form]):
            if fm.get(f"cond_{i}"): cs.append({"name":cn,"since":g(f"cond_{i}_since"),"treat":gl(f"cond_{i}_t"),"tx":other_txt(fm,f"cond_{i}_t")})
        for j in range(3):
            n=g(f"oc_{j}")[:80]
            if n: cs.append({"name":n,"since":g(f"oc_{j}_since"),"treat":gl(f"oc_{j}_t"),"tx":other_txt(fm,f"oc_{j}_t")})
        d["conds"]=cs
    elif sec in ("daily","out","safety"):
        R=d.setdefault("rows",{})
        for r in rows(form,sec,d):
            rid=r[0]; lvl=g(f"r_{rid}_lvl")
            v={"hard":bool(fm.get(f"r_{rid}_hard")) or lvl in ("slow","cant"),"help":bool(fm.get(f"r_{rid}_help")) or lvl in ("help","cant"),"lvl":lvl if lvl in dict(LVL) else "","c":gl(f"r_{rid}_c"),"std":gl(f"r_{rid}_std"),"freq":g(f"r_{rid}_freq"),"time":g(f"r_{rid}_time"),"days":g(f"r_{rid}_days"),"x":other_txt(fm,f"r_{rid}_c"),"lvl_x":other_txt(fm,f"r_{rid}_lvl"),"days_x":other_txt(fm,f"r_{rid}_days")}
            v["fu"]=fu_save(form,fm,rid,fu_keys(form,rid,r[4]),d)
            if lvl in ("cant","slow"): v["c"]=[x for x in v["c"] if x!="every"]
            # keep only follow-ups for what is tapped now (their words are never dropped for a chip they still have on)
            v["fu"]={k:f for k,f in v["fu"].items() if (k[4:]==lvl if k.startswith("lvl:") else k in v["c"])}
            if not v["fu"]: v.pop("fu")
            for k in ("lvl_x","days_x"):
                if not v[k]: v.pop(k)
            if lvl=="ok": v={"lvl":"ok"}   # 'No difficulty': follow-ups ignored
            if v.get("hard") or v.get("help") or v.get("c") or v.get("std") or v.get("x") or v.get("lvl_x") or lvl=="ok": R[rid]=v
            else: R.pop(rid,None)
        if sec=="daily" and form=="aa" and not fm.get("days_help"):   # derived from their own per-task answers, never guessed
            dd=[int(v["days"]) for v in R.values() if v.get("help") and str(v.get("days","")).isdigit()]
            d["days_help"]=str(max(dd)) if dd else ""
        keys={"daily":("bad",)+(("days_help",) if fm.get("days_help") else ()),"out":(),"safety":("falls","lastfall","alone","nights","ntimes","nmins","watch","fits","varies")}[sec]
        for k in keys: d[k]=g(k); d.setdefault("else",{})[k]=other_txt(fm,k)
        if sec=="safety":
            for k in ("fallx","eye","night","nn"): d[k]=gl(k); d.setdefault("else",{})[k]=other_txt(fm,k)
            d["nnum"]={k:{**{x:g(f"nn_{k}_{x}") for x in "ntm"},**{x+"_x":other_txt(fm,f"nn_{k}_{x}") for x in "ntm" if other_txt(fm,f"nn_{k}_{x}")}} for k in d["nn"]}
    elif sec=="finish":
        for k in ("aids","school","people"): d[k]=gl(k); d.setdefault("else",{})[k]=other_txt(fm,k)
        d["words"]=str(fm.get("words") or "").strip()[:3000]
        save_last(form,d,fm)
        import followups   # completeness check per hard task before anything is written (asked once; answered checks count as known)
        keep=[tuple(x) for x in d.get("fu_qs") or [] if f"{x[0]}_{x[1]}" not in (d.get("fu") or {})]
        # 30 Oct (claude-live): off by default now the inline follow-ups (6504e73) ask the same things on each task card; FOLLOWUPS=1 turns the extra "quick checks" page back on
        if os.getenv("FOLLOWUPS","0")=="0": d["fu_qs"],d["fu_how"]=[],"off"
        elif keep: d["fu_qs"]=keep   # coming back through: same checks, no new model call
        else: d["fu_qs"],d["fu_how"]=followups.pick(form,d)
        d["coverage"]=followups.coverage(form,d)
    return d
# ---------- turning taps into the customer's own answers ----------
def _ok(v): return v not in (None,"","ns")
def _rowtext(form,r,v,d):
    rid,topic,label,gate,chips=r; me=is_me(d,form); who=name(d,form); bits=[]
    if v.get("lvl")=="ok": return f"{label}: no difficulty."
    words,taps=fu_lines(form,r,v,d)
    if v.get("lvl_x"): words.insert(0,'"'+v["lvl_x"]+'"')
    lv=v.get("lvl")
    if lv:
        t={"slow":("I manage, but it is slow, painful or tiring" if me else f"{who} manages, but it is slow, painful or tiring"),"help":("I need help, prompting or watching" if me else f"{who} needs help, prompting or watching"),"cant":("I can't do it, or it isn't safe for me to" if me else f"{who} can't do it, or it isn't safe to")}[lv]
        bits.append(t)
        fx=[FX_T[x] for x in v.get("c",[]) if x in FX_T]
        if fx: bits.append("; ".join(fx))
        if _ok(v.get("days")): bits.append(f"on {v['days']} days a week")
    if v.get("hard") and not lv: bits.append("I find this hard" if me else f"{who} finds this hard")
    if v.get("help") and not lv: bits.append("I need help or reminding" if me else "needs help or reminding")
    cm={c[0]:c[1] for c in chips}; cs=[cm[x] for x in v.get("c",[]) if x in cm]
    if cs: bits.append("difficulty with: "+"; ".join(x[0].lower()+x[1:] for x in cs))
    if v.get("x"): bits.append("also: "+v["x"].rstrip("."))
    sm=dict(PIP_STD); st=[sm[x].lower() for x in v.get("std",[]) if x in sm]
    if st: bits.append("it can be done "+", ".join(st))
    if _ok(v.get("freq")): bits.append("like this "+FREQ_T[v["freq"]].lower())
    if TIME_T.get(v.get("time","")): bits.append("each time takes "+TIME_T[v["time"]])
    if v.get("days_x"): bits.append("how many days a week: "+v["days_x"].rstrip("."))
    # 30 Oct: their own typed words go first (the drafter uses these first), then the tapped details
    own=("In my own words: "+"; ".join(words)+". ") if words else ""
    t=", ".join(bits)+("." if bits else "")
    if taps: t=(t+" " if t else "")+" ".join(taps)
    return (f"{label}: "+own+t).strip() if (bits or words or taps) else ""
def topic_texts(form,d):
    """(intro, {topic id: plain text of what the customer tapped})."""
    from forms import FORMS
    me=is_me(d,form); nm=name(d,form); T={t:[] for t,_,_ in FORMS[form]["topics"]}
    if form=="dla": intro=f"This form is for my child{(' '+d['name']) if d.get('name') else ''}"+(f"; I am their {d['rel'].lower()}." if d.get("rel") and d["rel"]!="Other" else f"; I am their {X(d,'rel').rstrip('.')}." if X(d,"rel") else ".")
    else: intro={"me":"This form is for me.","parent":"This form is for my parent","partner":"This form is for my partner","other":"This form is for someone I help"}.get(d.get("who") or "me","")
    if not me and form!="dla": intro+=(f" ({d['name']})." if d.get("name") else ".")
    intro+=" "+{"them":"They will sign the form themselves.","poa":"I have Power of Attorney.","appointee":"I am their appointee.","ns":"I'm not sure yet who will sign."}.get(d.get("signer",""),"")
    if _ok(d.get("age")): intro+=" Age: "+{"u3":"under 3","3to4":"3 or 4","5to15":"5 to 15"}[d["age"]]+"."
    if X(d,"age"): intro+=f" Age: {X(d,'age').rstrip('.')}."
    if X(d,"signer") and not me: intro+=f" Who will sign: {X(d,'signer').rstrip('.')}."
    cl=[]
    for c in d.get("conds") or []:
        tm=dict(TREAT); tr=[tm[x].lower() for x in c.get("treat",[]) if x in tm and x!="ns"]
        cl.append(c["name"]+(f" since {c['since']}" if _ok(c.get("since")) else "")+(f" (treatment: {', '.join(tr+([c['tx']] if c.get('tx') else []))})" if tr or c.get("tx") else ""))
    if cl:
        s="Health conditions: "+"; ".join(cl)+"."
        if "conditions" in T: T["conditions"].append(s)
        else: intro+=" "+s
    if _ok(d.get("bad")) or X(d,"bad"):
        s=("Bad days: it varies a lot from week to week." if d.get("bad")=="varies" else f"Bad days: about {d['bad']} a week." if _ok(d.get("bad")) else "")+(f" Bad days, in my own words: {X(d,'bad').rstrip('.')}." if X(d,"bad") else "")
        s=s.strip()
        if form=="dla": T["42"].append(s)
        elif form=="pip": T["other"].append(s)
        else: intro+=" "+s
    if form=="aa" and _ok(d.get("days_help")): intro+=f" Needs help with care {d['days_help']} days a week."
    for r in rows(form,None,d):
        v=(d.get("rows") or {}).get(r[0]); t=_rowtext(form,r,v,d) if v else ""
        if t: T[r[1]].append(t)
    S=lambda k,m:m.get(d.get(k) or "","")
    if form=="aa":
        f=" ".join(x for x in (S("falls",{"0":"No falls in the last year.","1-2":"1 to 2 falls in the last year.","3-5":"3 to 5 falls in the last year.","6+":"6 or more falls in the last year."}),
            S("lastfall",{"week":"Last fall: this week.","month":"Last fall: this month.","months":"Last fall: 1 to 6 months ago.","year":"Last fall: over 6 months ago."})) if x)
        fx={"getup":"Can't get up after a fall without help.","hurt":"Has been hurt or gone to hospital after a fall.","clinic":"Referred to a falls clinic.","alarm":"Has a pendant alarm."}; f=(f+" "+" ".join(fx[x] for x in d.get("fallx") or [] if x in fx)).strip()
        if f: T["34"].append(f)
        ey={"danger":"not aware of dangers","wander":"may wander","fits":"has dizzy spells, fits or blackouts","confused":"gets confused"}; e=[ey[x] for x in d.get("eye") or [] if x in ey]
        a=S("alone",{"always":"Can be left alone as long as needed.","hours":"Can only be left alone for a few hours.","lt1":"Can only be left alone for under an hour.","never":"Can't be left alone at all."})
        if e or a: T["40"].append(((("Needs someone to keep an eye on them: "+", ".join(e)+". ") if e else "")+a).strip())
        nt={"toilet":"toilet","turn":"turning over or settling","pain":"pain or breathing","meds":"medicines","confused":"being confused or distressed"}; n=[nt[x] for x in d.get("night") or [] if x in nt]
        if n:
            s="Help at night with: "+", ".join(n)+"."
            if _ok(d.get("nights")): s+=f" {d['nights']} nights a week."
            if _ok(d.get("ntimes")): s+=f" {d['ntimes']} times a night."
            if TIME_T.get(d.get("nmins") or ""): s+=f" Each time takes {TIME_T[d['nmins']]}."
            T["42"].append(s)
        w=S("watch",{"some":"Someone needs to stay awake to watch over them some nights.","most":"Someone needs to stay awake to watch over them most nights."})
        if w: T["44"].append(w)
    if form=="dla":
        fs=S("fits",{"month":"Fits or seizures: less than once a week.","week":"Fits or seizures: weekly.","day":"Fits or seizures: daily."})
        if fs: T["65"].append(fs)
        vv=S("varies",{"same":"Needs are mostly the same each day.","varies":"Needs change a lot from day to day."})
        if vv: T["42"].append(vv)
        nd=dict(NIGHT_DLA); ns=[]
        for k in d.get("nn") or []:
            q=(d.get("nnum") or {}).get(k,{})
            parts=[p for p in (f"{q['n']} nights a week" if _ok(q.get("n")) else "",f"{q['t']} times a night" if _ok(q.get("t")) else "",f"about {q['m']} minutes each time" if _ok(q.get("m")) else "") if p]
            parts+=[q[x+"_x"].rstrip(".") for x in "ntm" if q.get(x+"_x")]
            ns.append(nd.get(k,k)+(" ("+", ".join(parts)+")" if parts else ""))
        if ns: T["night"].append("Help at night with: "+"; ".join(ns)+".")
        sc=dict(SCHOOL); s=[sc[x] for x in d.get("school") or [] if x in sc]
        if s: T["school"].append("School or nursery: "+"; ".join(s)+".")
        if d.get("people"): T["statement"].append("People who know about the child's condition: "+people_txt(d)+".")
    if form=="pip" and d.get("people"): T["other"].append("People who know about "+("my" if me else "their")+" condition: "+people_txt(d)+".")
    for k in d.get("nohelp") or []:   # help needed even though no one gives it: ONLY the activities they named
        tp=NOHELP_TOPIC[form].get(k)
        if tp in T: T[tp].append(f"Needs help {NOHELP_WHAT[k]}, but no one is there to help.")
    for k in ("nohelp_x","nohelp_w"):
        v=(X(d,"nohelp") if k=="nohelp_x" else d.get("nohelp_w") or "").strip().rstrip(".")
        if v: T[OWN_TOPIC[form]].append(f"Help needed but no one there to help, in my own words: {v}.")
    if form=="pip" and d.get("badday"): T["other"].append(f"A recent bad day, in my own words: {d['badday'].strip().rstrip('.')}.")
    E=lambda k: X(d,k).rstrip(".")
    for k,tp,lab in (("falls","34","Falls in the last year"),("lastfall","34","Last fall"),("alone","40","Being left alone"),("nights","42","Nights a week needing help"),
                     ("ntimes","42","Times a night"),("nmins","42","Minutes each time at night"),("watch","44","Someone staying awake at night"),("fits","65","Fits or seizures"),("varies","42","How needs change day to day")):
        if E(k) and tp in T: T[tp].append(f"{lab}, in my own words: {E(k)}.")
    if form=="aa":
        if E("fallx"): T["34"].append(f"After a fall, also: {E('fallx')}.")
        if E("eye"): T["40"].append(f"Keeping an eye on them, also: {E('eye')}.")
        if E("night"): T["42"].append(f"Help at night, also: {E('night')}.")
        if E("people"): T["40"].append(f"Other people who know them well: {E('people')}.")
        if d.get("people"): T["40"].append("People who know about their condition: "+people_txt(d)+".")
    if form=="dla":
        if E("nn"): T["night"].append(f"Help at night, also: {E('nn')}.")
        if E("school"): T["school"].append(f"School or nursery, also: {E('school')}.")
        if E("people"): T["statement"].append(f"Other people who know the child well: {E('people')}.")
    if form=="pip" and E("people"): T["other"].append(f"Other people who know {'me' if me else 'them'}: {E('people')}.")
    if E("aids"): T[{"aa":"33","dla":"daycare","pip":"other"}[form]].append(f"Other aids used: {E('aids')}.")
    if d.get("aids"): T[{"aa":"33","dla":"daycare","pip":"other"}[form]].append("Aids used: "+", ".join(d["aids"])+".")
    if d.get("words"): T[{"aa":"40","dla":"42","pip":"other"}[form]].append("In my own words: "+d["words"])
    if d.get("meds_confirmed"):   # only medicines the customer confirmed on /confirm (never straight from a document)
        s="Medicines (I checked these against my documents): "+", ".join(d["meds_confirmed"])+"."
        if "conditions" in T: T["conditions"].append(s)
        else: intro+=" "+s
    for k,c in (d.get("clarify") or {}).items():   # answers to the short "which is right?" questions: override earlier taps
        if not c.get("s"): continue
        s="Checked with you: "+c["s"]
        if c.get("topic") in T: T[c["topic"]].append(s)
        else: intro+=" "+s
    return " ".join(intro.split()),{k:" ".join(v) for k,v in T.items()}
def history(form,d):
    """Q/A transcript in topic order (one answer per topic), so drafting, grounding and 'what you told us' work unchanged."""
    from forms import FORMS
    intro,T=topic_texts(form,d); h=[{"role":"assistant","content":"About the claim"},{"role":"user","content":intro or "(No details given.)"}]
    for t,l,_ in FORMS[form]["topics"]: h+=[{"role":"assistant","content":l},{"role":"user","content":T.get(t) or "Nothing selected for this."}]
    return h
# ---------- plain sentences straight from the taps (used when the drafter can't be reached, and in local MOCK runs) ----------
# Every sentence below is a rewording of one tapped answer; nothing is added. The answer check still runs on the result.
FX_S={"every":("I need help every time.","{w} needs help every time."),
 "long":("It takes me at least twice as long as normal.","It takes {w} at least twice as long as normal."),
 "rest":("I have to stop and rest.","{w} has to stop and rest."),
 "pain":("I have pain or exhaustion afterwards.","{w} has pain or exhaustion afterwards."),
 "wrong":("I have had a fall or near-miss doing it.","{w} has had a fall or near-miss doing it."),
 "half":("The result is not good enough (half-done or not clean).","The result is not good enough (half-done or not clean)."),
 "prompt":("I need reminding, encouraging or watching.","{w} needs reminding, encouraging or watching."),
 "aid":("I use an aid for it, at least sometimes.","{w} uses an aid for it, at least sometimes."),
 "nobody":("There is nobody there to help, so it goes without.","There is nobody there to help, so it goes without."),
 "std_safe":("It is not safe for me to do it alone.","It is not safe for {w} to do it alone."),
 "burn":("I have had burns, cuts or near-misses doing it.","{w} has had burns, cuts or near-misses doing it.")}
def _who(d,form):
    me=is_me(d,form); w=name(d,form)
    if w in ("you","them","your child"): w={"you":"I","them":"The person I help","your child":"My child"}[w]
    return me,("I" if me else w)
def _v3(me,first,third): return first if me else third   # verb for 'I' vs a named person
def _rowprose(form,r,v,d):
    rid,topic,label,gate,chips=r; me,w=_who(d,form); lab=label[0].lower()+label[1:]; out=[]
    if v.get("lvl")=="ok": return ""
    lv=v.get("lvl")
    if lab.startswith("needs "): lab=lab[6:]; lv_needs=True   # e.g. DLA 'Needs watching during the day'
    else: lv_needs=False
    if lv_needs and lv: out.append(f"{w} {_v3(me,'need','needs')} {lab}.")
    elif lv=="help": out.append(f"{w} {_v3(me,'need','needs')} help, prompting or watching with {lab}.")
    elif lv=="slow": out.append(f"{w} {_v3(me,'manage','manages')} {lab}, but it is slow, painful or tiring.")
    elif lv=="cant": out.append(f"{w} can't manage {lab}, or it isn't safe for {_v3(me,'me','them')} to.")
    else:
        if v.get("hard"): out.append(f"{w} {_v3(me,'find','finds')} {lab} hard.")
        if v.get("help"): out.append(f"{w} {_v3(me,'need','needs')} help or reminding with {lab}.")
    for x in v.get("c",[]):
        if x in FX_S: out.append(FX_S[x][0 if me else 1].format(w=w))
    cm={c[0]:c[1] for c in chips}; cs=[cm[x][0].lower()+cm[x][1:] for x in v.get("c",[]) if x in cm]
    if me: cs=[c.replace("with them","with me").replace("themselves","myself") for c in cs]
    VB={"needs":"need","has":"have","forgets":"forget","mixes":"mix","gets":"get","runs":"run","acts":"act","becomes":"become","wanders":"wander","screams":"scream"}
    nd=[c for c in cs if c.split(" ")[0] in VB]; cs=[c for c in cs if c.split(" ")[0] not in VB]   # 'forgets medicines' reads as its own sentence
    if cs: out.append(f"{w} {_v3(me,'have','has')} difficulty with: "+"; ".join(cs)+".")
    for c in nd:
        v0,rest=(c.split(" ",1)+[""])[:2]
        rest=rest.replace(" or no "," or "+_v3(me,"have","has")+" no ")   # 'runs off or no road sense'
        out.append(f"{w} {VB[v0] if me else v0} {rest}".rstrip()+".")
    if v.get("x"): out.append("Also: "+v["x"].rstrip(".")+".")
    sm=dict(PIP_STD); st=[sm[x].lower() for x in v.get("std",[]) if x in sm]
    if st: out.append("It can only be done: "+", ".join(st)+".")
    if lv and _ok(v.get("days")): out.append(f"This happens {v['days']} days a week.")
    if _ok(v.get("freq")) and FREQ_T.get(v["freq"]): out.append("This happens "+FREQ_T[v["freq"]].lower()+".")
    if TIME_T.get(v.get("time","")): out.append("Each time takes "+TIME_T[v["time"]]+".")
    if v.get("days_x"): out.append("How many days a week: "+v["days_x"].rstrip(".")+".")
    words,taps=fu_lines(form,r,v,d)
    if v.get("lvl_x"): words.insert(0,'"'+v["lvl_x"]+'"')
    out+=taps
    tw=[(f.get("w") or "").strip() for k,f in (v.get("fu") or {}).items() if f.get("w") and ((k[4:]==v.get("lvl")) if k.startswith("lvl:") else k in (v.get("c") or []))]
    tw=([v["lvl_x"].strip()] if v.get("lvl_x") else [])+tw
    out=["In my own words: \u00ab"+x.rstrip(".")+"\u00bb." for x in tw]+out   # their typed words first, one sentence each
    t=" ".join(out)
    if me: t=re.sub(r"\bthemselves\b","myself",re.sub(r"\bthey don't\b","I don't",t))
    return t
def _conj(items,me):
    """'gets confused, may wander, not aware of dangers, has ...' -> verbs that match the subject."""
    out=[]
    for x in items.split(", "):
        if x.startswith("not "): x=("am " if me else "is ")+x
        elif me and x.startswith("gets "): x="get "+x[5:]
        elif me and x.startswith("has "): x="have "+x[4:]
        out.append(x)
    return ", ".join(out)
def _polish(t,me,w):
    """Turn the short tapped lines used for the transcript into sentences (same facts, same words where possible)."""
    obj=_v3(me,"me","them"); S=lambda a,b:_v3(me,a,b)
    R=[(r"\bNo falls in the last year\.",f"{w} {S('have','has')} had no falls in the last year."),
       (r"\b(1 to 2|3 to 5|6 or more) falls in the last year\.",lambda m:f"{w} {S('have','has')} had {m[1]} falls in the last year."),
       (r"\bLast fall: ([^.]+)\.",lambda m:f"{S('My','The')} last fall was {m[1]}."),
       (r"\bCan't get up after a fall without help\.",f"{w} can't get up after a fall without help."),
       (r"\bHas been hurt or gone to hospital after a fall\.",f"{w} {S('have','has')} been hurt or gone to hospital after a fall."),
       (r"\bReferred to a falls clinic\.",f"{w} {S('have','has')} been referred to a falls clinic."),
       (r"\bHas a pendant alarm\.",f"{w} {S('have','has')} a pendant alarm."),
       (r"\bNeeds someone to keep an eye on them: ([^.]+)\.",lambda m:f"Someone needs to keep an eye on {_v3(me,'me',w)} during the day, because {w} "+_conj(m[1],me)+"."),
       (r"\bPeople who know them well: ",f"People who know {obj} well: "),(r"\bPeople who know about their condition: ",f"People who know about {S('my','their')} condition: "),
       (r"\bNeeds help ((?:with|at) [^,.]+), but no one is there to help\.",lambda m:f"{w} {S('need','needs')} help {m[1]}, but no one is there to help."),(r"\bOther people who know them well: ",f"Other people who know {obj} well: "),
       (r"\bBad days: about (\S+) a week\.",lambda m:f"{w} {S('have','has')} bad days about {m[1]} a week."),
       (r"\bNeeds change a lot from day to day\.",f"{S('My','Their') if w in ('I','My child') else w+chr(39)+'s'} needs change a lot from day to day."),
       (r"\bNeeds are mostly the same each day\.",f"{S('My','Their') if w in ('I','My child') else w+chr(39)+'s'} needs are mostly the same each day."),
       (r"\bFits or seizures: ([^.]+)\.",lambda m:f"{w} {S('have','has')} fits or seizures {m[1]}."),
       (r"\bCan (only )?be left alone",lambda m:f"{w} can {m[1] or ''}be left alone"),(r"\bCan't be left alone",f"{w} can't be left alone"),
       (r"\bHelp at night with: ",f"{w} {S('need','needs')} help at night with: "),
       (r"(?<=\. )(\d+|6\+) nights a week\. (\d+|6\+) times a night\.",lambda m:f"This is {m[1]} nights a week, {m[2]} times a night."),
       (r"(?<=\. )(\d+|6\+) nights a week\.",lambda m:f"This is {m[1]} nights a week."),(r"(?<=\. )(\d+|6\+) times a night\.",lambda m:f"This is {m[1]} times a night."),
       (r"\bwatch over them\b",f"watch over {obj if me else w}"),
       (r"\bNeeds help with care (\d) days a week\.",lambda m:f"{w} {S('need','needs')} help with care {m[1]} days a week."),
       (r"\bAids used: ",f"Aids {S('I use','used')}: "),(r"\bOther aids used: ","Other aids: "),
       (r"\bKeeping an eye on them, also: ","Keeping an eye on "+obj+", also: "),
       (r"\bIn my own words: ","In my own words: ")]
    for a,b in R: t=re.sub(a,b,t)
    return " ".join(t.split())
RISK_S={"Could fall":"could fall","Could get hurt or burnt":"could get hurt or burnt","Could choke":"could choke","Would forget or miss it":"would forget or miss it"}
SAYS='The person helping me with this form says: "{}"'
def _fb_voice(t,form,me,w,carer):
    """Fallback text in the claimant's voice: 'Checked with you' answers as plain sentences, no 'In my own words:' labels,
    and (AA filled in by someone else) the helper's own words quoted as theirs, because the rest is in the claimant's first person."""
    S=lambda a,b:_v3(me,a,b); obj=_v3(me,"me",w)
    def chk(m):
        dim,ans=m[2],m[3].strip().rstrip(".")
        if dim=="what could happen without help":
            out=[]
            for a in ans.split("; "):
                if a=="Wouldn't get done properly": out.append("Without help, it wouldn't get done properly.")
                elif a in RISK_S: out.append(f"Without help, {w} {RISK_S[a]}.")
                elif a: out.append(f"Without help: {a}.")
            return " ".join(out)
        if dim=="how often": return f"This happens {ans[0].lower()+ans[1:]}."
        if dim=="how long it takes": return "Each time takes "+ans.lower().replace(" min"," minutes")+"."
        if dim=="who helps":
            out=[]
            for a in ans.split("; "):
                if a=="No one, so it goes undone": out.append(f"No one helps {obj}, so it goes undone.")
                elif a=="Me, the parent": out.append(f"I help {w} with this.")
                elif a=="No one": out.append(f"No one helps {obj} with this.")
                elif a: out.append(f"{a[0].upper()+a[1:]} helps {obj}.")
            return " ".join(out)
        if dim=="what's used to help":
            return w+" "+S("don't","doesn't")+" use anything to help with this." if ans=="Nothing" else f"{w} {S('use','uses')}: {ans}."
        if dim=="example": return SAYS.format(ans+".") if carer else ans+"."
        return f"{dim[0].upper()+dim[1:]}: {ans}."
    t=re.sub(r"Checked with you: ([^,.]+), (how often|how long it takes|who helps|what's used to help|what could happen without help|example): (.+?\.)(?=\s|$)",chk,t)
    t=t.replace("Checked with you: ","")
    cap=lambda x:x[:1].upper()+x[1:]
    t=re.sub(r"In my own words: \u00ab(.+?)\u00bb\.",(lambda m:SAYS.format(m[1].strip()+".")) if carer else (lambda m:cap(m[1].strip())+"."),t)
    t=re.sub(r"In my own words: (.+?)(?=$)",(lambda m:SAYS.format(m[1].strip())) if carer else (lambda m:m[1]),t)
    # inline follow-up taps (FU_P lines) as plain sentences
    WHO={"partner":"My partner helps "+obj+".","family":"Family helps "+obj+".","carer":"A carer helps "+obj+"."}
    t=re.sub(r"Who helps: (partner|family|carer)\.",lambda m:WHO[m[1]],t)
    t=re.sub(r"Who helps: no one, but (?:I|they) need it\.",f"No one helps {obj}, but {w} {S('need','needs')} it.",t)
    t=re.sub(r"What could happen: (.+?)\.",lambda m:{"a fall or getting hurt":"It could lead to a fall or getting hurt.","it doesn't get done":"It doesn't get done.","distress or panic":"It can cause distress or panic."}.get(m[1],f"What could happen: {m[1]}."),t)
    t=re.sub(r"Last time: (.+?)\.",lambda m:f"The last time was {m[1]}.",t)
    t=re.sub(r"Compared with other children the same age: (far more|more) help than them\.",lambda m:f"{w} {S('need','needs')} {m[1]} help than other children the same age.",t)
    t=re.sub(r"Compared with other children the same age: about the same\.",f"{w} {S('need','needs')} about the same help as other children the same age.",t)
    if carer: t=re.sub(r"Also: (.+?\.)(?=\s|$)",lambda m:SAYS.format(m[1]) if re.search(r"\b(she|he|her|him|his|they|them|mum|dad|my (mum|dad|mother|father|wife|husband))\b",m[1],re.I) else m[1],t)
    else: t=re.sub(r"\bAlso: ","",t)
    return " ".join(t.split())
def fallback_draft(form,d):
    """A complete, grounded draft from the taps alone: no AI. Same shape as llm.draft().
    Written in the claimant's first person (AA and PIP: 'I'; child DLA: the parent is 'I' and the child is named)."""
    from forms import FORMS
    carer=form=="aa" and not is_me(d,form)
    said=topic_texts(form,d)[1]   # 'what you told us' stays in the words of whoever filled in the form
    bn=badday_note(form,d)   # before the AA voice switch below: a carer's words are labelled as theirs
    if form=="aa": d={**d,"who":"me"}   # the AA1 is the claimant's own form: always 'I', even when someone else fills it in
    me,w=_who(d,form); T={t:[] for t,_,_ in FORMS[form]["topics"]}; intro,raw=topic_texts(form,d)
    rowtopics={}
    for r in rows(form,None,d):
        v=(d.get("rows") or {}).get(r[0]); p=_rowprose(form,r,v,d) if v else ""
        if p: T[r[1]].append(p)
        rowtopics.setdefault(r[1],[]).append(_rowtext(form,r,v,d) if v else "")
    for t,txt in raw.items():   # the rest of each topic's text (everything that isn't a task row), as sentences
        rest=txt
        for rt in rowtopics.get(t,[]):
            if rt: rest=rest.replace(rt,"",1)
        rest=" ".join(rest.split())
        if rest: T[t].append(_polish(rest,me,w))
    ans={t:_fb_voice(" ".join(v).strip(),form,me,w,carer) for t,v in T.items()}
    if form=="dla": ans["statement"]=""   # the statement box is for someone who knows the child: never our words
    tick_yes=[t for t,a in ans.items() if a and t.isdigit()] if form=="aa" else []
    out={"answers":ans,"sources":{t:[said[t]] for t in ans if said.get(t)},"tick_yes":tick_yes,"conditions":[],"extra":{},
            "checklist":[],"notes_for_user":[],"gp_letter":"","drafted_from":"taps"}
    if bn: out["badday_note"]=bn   # their bad day, word for word, in the form's extra-information box (the writer drops this when it used it in a box)
    return out
def coverage(form,d):
    from forms import FORMS
    _,T=topic_texts(form,d); tops=FORMS[form]["topics"]; return sum(1 for t,_,_ in tops if T.get(t)),len(tops)
def ticks(form,d):
    """Tick-box states taken straight from the taps (only what was tapped; never consent/declaration/bank boxes)."""
    out={}
    for r in rows(form,None,d):
        v=(d.get("rows") or {}).get(r[0])
        if not v: continue
        if v.get("lvl")=="ok":   # 28 Oct: "no difficulty" is an answer too: the form's Yes/No question is No, never Yes
            if r[3] and "/No" in NO_OK.get(form,()) and r[3][0] not in out: out[r[3][0]]="/No"
            continue
        if r[3]: out[r[3][0]]=r[3][1]
        for cid,_,tk,hp in r[4]:
            if cid in (v.get("c") or []):
                for f,s in tk: out[f]=s
                if v.get("help"):
                    for f,s in hp: out[f]=s
    if form=="aa":
        if d.get("falls") in ("1-2","3-5","6+"): out["x34"]="/Fall"
        elif d.get("falls")=="0": out["x34"]="/No"
        if d.get("alone")=="always" and not d.get("eye"): out["x40"]="/No"
        if d.get("watch")=="no": out["302"]="/No"
        fx=d.get("fallx") or []
        if "getup" in fx: out["x34-3"]="/Yes"
        if "clinic" in fx: out["x34-2"]="/Yes"
        em={"danger":"x40-2","wander":"x40-5","fits":"x40-7","confused":"x40-8"}; e=d.get("eye") or []
        for k in e: out[em[k]]="/Yes"
        if e or d.get("alone") in ("lt1","never","hours"): out["x40"]="/Yes"
        if d.get("night"): out["x42"]="/Yes"
        if d.get("watch") in ("some","most"):
            out["302"]="/Yes"
            if "confused" in (d.get("night") or []) or "confused" in e: out["308"]="/Yes"
            if "wander" in e: out["306"]="/Yes"
    if form=="dla":
        if d.get("fits") in ("month","week","day"): out["65"]="/Yes"
        if d.get("varies")=="varies": out["42"]="/Changes from day to day"
        if d.get("nn"): out["70"]="/Yes"
        if [x for x in d.get("school") or [] if x!="notatschool"]: out["68"]="/Yes"
        if "special" in (d.get("school") or []): out["36"]="/Yes"
        if "ehcp" in (d.get("school") or []): out["37_1"]="/Educational Health Care Plan"
        if d.get("aids"): out["41"]="/Yes"
    return out
NO_OK={"aa":("/No",),"dla":("/No",)}
def no_difficulty(form,d):
    """Topic ids where every row the customer answered was 'No difficulty' (and nothing else was added to that topic).
    These questions are answered No on the form: no 'difficulty' tick and no 'no difficulty' sentence in the box."""
    d=d or {}; R=d.get("rows") or {}; by={}
    for r in rows(form,None,d):
        v=R.get(r[0])
        if v: by.setdefault(r[1],[]).append(v.get("lvl")=="ok")
    out=[t for t,oks in by.items() if oks and all(oks)]
    if form=="aa" and d.get("falls")=="0" and not d.get("fallx") and not X(d,"fallx"): out.append("34")
    return out
def aids_list(d):
    """Aids the customer tapped (plus 'Something else' text), for the form's aids table."""
    a=list((d or {}).get("aids") or [])
    x=X(d or {},"aids").strip()
    if x: a+=[y.strip() for y in re.split(r"[,;\n]",x) if y.strip()]
    return a
def extra(form,d):
    """Number boxes on the PDF, from taps only."""
    e={}
    if aids_list(d): e["aids"]=aids_list(d)
    if form=="aa":
        if _ok(d.get("days_help")): e["days_week_day"]=d["days_help"]
        if _ok(d.get("nights")) and d.get("night"): e["nights_week"]=d["nights"]
        if d.get("falls") in ("1-2","3-5","6+"): e["falls_year"]=d["falls"].replace("-"," to ")
        lf={"week":"This week","month":"This month","months":"In the last 6 months","year":"Over 6 months ago"}.get(d.get("lastfall"))
        if lf: e["last_fell"]=lf
        fx=d.get("fallx") or []
        if "getup" in fx:   # x34-3 'Do you need help to get up after a fall?' is ticked Yes from this tap: its 'Tell us about this' box
            me,w=True,"I"; S=lambda a,b:_v3(me,a,b)   # the AA1 is in the claimant's own voice (first person), even when a carer fills it in
            fd=[f"{w} can't get up after a fall without help."]
            if "alarm" in fx: fd.append(f"{w} {S('have','has')} a pendant alarm.")
            if "hurt" in fx: fd.append(f"{w} {S('have','has')} been hurt or gone to hospital after a fall.")
            if X(d,"fallx"): fd.append("Also: "+X(d,"fallx").rstrip(".")+".")
            e["fall_detail"]=" ".join(fd)
        al={"hours":"A few hours","lt1":"Less than an hour","never":"Not at all"}.get(d.get("alone"))
        if al: e["safe_alone"]=al
    if form=="dla":
        for k in d.get("nn") or []:
            q=(d.get("nnum") or {}).get(k,{}); v=[q.get(x) if _ok(q.get(x)) else "" for x in "nmt"]
            if any(v): e[k]=v
    return e
def conditions(d):
    tm=dict(TREAT)
    return [{"name":c["name"],"since":c["since"] if _ok(c.get("since")) else "","meds":", ".join(tm[x] for x in c.get("treat",[]) if x in tm and x!="ns"),"dose":""} for c in d.get("conds") or []]
def notes(form,d):
    n={"poa":"You told us you have Power of Attorney. Sign the declaration as their attorney and send a copy of the Power of Attorney with the form.",
       "appointee":"You told us you are their appointee. Sign the declaration as appointee and give your appointee reference if you have it.",
       "them":"They will sign the form themselves. Read the answers through with them first.",
       "ns":"Before you post it, decide who signs. The person claiming signs if they can; otherwise their attorney or appointee signs."}
    out=[n[d["signer"]]] if d.get("signer") in n else []
    if d.get("people"): out.append("People who could support the claim: "+people_txt(d)+".")
    return out
def personal_prefill(form,d):
    p={}
    nm=(d.get("name") or "").strip()
    if nm and (form=="dla" or not is_me(d,form)) and nm.lower() not in ("mum","dad","mom","mam","nan","gran","nana","grandma","grandad"): p["other_names"]=nm
    if form=="dla" and d.get("rel") and d["rel"]!="Other": p["relationship"]=d["rel"]
    return p

# ---------- the last screen (30 Oct 2026): 'A few last things that really help your form' ----------
# Three prompts on the SAME screen as aids (one question step, so no extra screens): a recent bad day, help they need but
# go without, and who knows about their condition. Everything here is the customer's own words or taps; nothing is guessed.
def people_txt(d):
    """'GP (Dr Patel, Hill Surgery), Carer': the names are only what they typed; never added."""
    kn=d.get("know_names") or {}
    return ", ".join(p+(f" ({kn[p]})" if kn.get(p) else "") for p in d.get("people") or [])
def badday_note(form,d):
    b=(d.get("badday") or "").strip()
    if not b or form not in ("aa","dla"): return ""
    carer=form=="aa" and not is_me(d,form)
    return ("A recent bad day, described by the person helping me: " if carer else "A recent bad day: ")+b
def _starters(target,items):
    return '<div class="chips starters">'+"".join(f'<button type=button class=starter data-for="{target}" data-s="{esc(x)} "><span>{esc(x)}…</span></button>' for x in items)+'</div>'
def last_things(form,d):
    me=is_me(d,form); nm=name(d,form); dla=form=="dla"
    N=(d.get("name") or "").strip()
    subj="I" if me else (N or ("My child" if dla else "They"))
    poss="your" if me else ("their" if not N else f"{N}'s")
    ex=("e.g. Last Tuesday I couldn't get out of bed until my daughter came at 11" if me else
        f"e.g. Last Tuesday {N or 'my child'} couldn't get dressed and I had to stay home from work" if dla else
        f"e.g. Last Tuesday {N or 'they'} couldn't get out of bed until I came at 11")
    if me: st=["I couldn't get up until","I fell when","I forgot","I needed help to"]
    elif dla: st=[f"{subj} couldn't",f"{subj} got very upset when",f"I had to help {subj if N else 'them'} to"]
    else: st=[f"{subj} couldn't get up until",f"{subj} fell when",f"{subj} forgot",f"{subj} needed help to"]
    they="you" if me else "they"
    b=d.get("badday",""); nh=d.get("nohelp") or (["no"] if d.get("nohelp_no") else []); pp=d.get("people") or (["None"] if d.get("people_none") else []); kn=d.get("know_names") or {}
    h=('<fieldset class="iq lastq"><legend>A few last things that really help your form</legend>'
       '<p class=hint>Skip anything you are not sure about. We do the writing.</p>')
    # 1. a recent bad day
    h+=(f'<div class=lt><h3 class=ltq>Tell us about a recent bad day{"" if me else " for "+nm}</h3>'
        f'<p class=tip>Think of one day recently. What happened, what {they} couldn\'t do, and who helped.</p>'
        f'{_starters("badday",st)}'
        f'<textarea id=badday name=badday rows=3 maxlength=1000 aria-label="A recent bad day" placeholder="{esc(ex)}">{esc(b)}</textarea>'
        f'<p class=nudge hidden>{FU_NUDGE}</p></div>')
    # 2. help they need but go without
    q2="Is there anything you need help with but no one is there to help?" if me else f"Is there anything {('your child' if dla and not N else nm)} needs help with but no one is there to help?"
    tip2="Count help you need even if no one gives it. Don't say you cope if it's a struggle." if me else "Count help they need even if no one gives it. Don't say they cope if it's a struggle."
    h+=(f'<div class=lt><h3 class=ltq>{esc(q2)}</h3><p class=tip>{esc(tip2)}</p>'
        '<div class="chips solo" data-solo=no>'+"".join(_chk("nohelp",v,t,v in nh) for v,t in NOHELP)+_else("nohelp",X(d,"nohelp"))+_chk("nohelp","no","No",("no" in nh))+'</div>'
        '<label class=ltw for=nohelp_w><span>Anything to add? (you can skip this)</span></label>'
        +_starters("nohelp_w",["No one is there when "+("I" if me else "they" if not N else N),("I go without" if me else ("They go without" if not N else N+" goes without"))])
        +f'<input id=nohelp_w name=nohelp_w value="{esc(d.get("nohelp_w",""))}" maxlength=300 placeholder="{esc("e.g. I skip lunch when no one is here" if me else (f"e.g. {N} goes without lunch when no one is there" if N else "e.g. they go without lunch when no one is there"))}"></div>')
    # 3. who could back it up
    q3=f"Who knows about {poss} condition?"
    tip3="Anyone who's seen how your condition affects you. You don't need their details now." if me else "Anyone who's seen how their condition affects them. You don't need their details now."
    chips=""
    for p in PEOPLE[form]:
        chips+=_chk("people",p,p,p in pp)
        if p in PROF_PEOPLE:
            chips+=(f'<label class=kn><span>Their name or surgery, if you know it</span><input name="know_{PEOPLE[form].index(p)}" value="{esc(kn.get(p,""))}" maxlength=80 '
                    f'placeholder="{esc("e.g. Dr Patel, Hill Surgery" if p=="GP" else "e.g. Dr Shah at St James\'s")}"></label>')
    h+=(f'<div class=lt><h3 class=ltq>{esc(q3)}</h3><p class=tip>{esc(tip3)}</p>'
        '<div class="chips solo knowc" data-solo=None>'+chips+_else("people",X(d,"people"))+_chk("people","None","None",("None" in pp))+'</div></div>')
    # 4. the old free box, now a small last line
    h+=(f'<label class="ltw ltlast"><span>Anything else? (you can skip this)</span><textarea name=words rows=2 maxlength=3000 placeholder="Anything we haven\'t asked about">{esc(d.get("words",""))}</textarea></label>'
        '</fieldset>'+LAST_JS)
    return h
LAST_JS="""<script>(function(){
 document.querySelectorAll('.starter').forEach(function(b){b.addEventListener('click',function(){var t=document.getElementById(b.dataset.for);if(!t)return;
   var v=t.value.replace(/\\s+$/,'');t.value=(v?v+(/[.!?]$/.test(v)?' ':'. '):'')+b.dataset.s;t.focus();try{t.setSelectionRange(t.value.length,t.value.length)}catch(e){}})});
 document.querySelectorAll('.chips.solo').forEach(function(g){var solo=g.dataset.solo;g.addEventListener('change',function(e){var i=e.target;if(i.type!=='checkbox'||!i.checked)return;
   g.querySelectorAll('input[type=checkbox]').forEach(function(o){if(o!==i&&(i.value===solo||o.value===solo))o.checked=false})})});
 var t=document.getElementById('badday');if(t)t.addEventListener('input',function(){if(t.value.trim()){var n=t.closest('.lt').querySelector('.nudge');if(n)n.hidden=true}});
 document.addEventListener('click',function(e){var b=e.target.closest('button');if(!b||!t||b.value!=='next'||t.dataset.nudged||t.value.trim())return;var box=t.closest('.lt');if(!box||box.offsetParent===null)return;
   e.preventDefault();e.stopImmediatePropagation();t.dataset.nudged=1;box.querySelector('.nudge').hidden=false;t.focus()},true);
})();</script>"""
def save_last(form,d,fm):
    g=lambda k:re.sub(r"\s+"," ",str(fm.get(k) or "")).strip()
    d["badday"]=str(fm.get("badday") or "").strip()[:1000]
    nh=[x for x in fm.getlist("nohelp") if x in NOHELP_WHAT]
    d["nohelp"]=nh; d["nohelp_no"]=("no" in fm.getlist("nohelp")) and not nh and not X(d,"nohelp")
    d["nohelp_w"]=g("nohelp_w")[:300]
    pp=[p for p in fm.getlist("people") if p in PEOPLE[form]]
    d["people_none"]="None" in fm.getlist("people") and not pp and not X(d,"people"); d["people"]=pp
    d["know_names"]={p:g(f"know_{PEOPLE[form].index(p)}")[:80] for p in pp if p in PROF_PEOPLE and g(f"know_{PEOPLE[form].index(p)}")}

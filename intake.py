"""Intake v3: tap-first questions for AA1, DLA1A and PIP2 (no chat).
Each fact is asked once. Taps map straight to form tick boxes and number boxes; we also turn the taps into plain
sentences (the customer's own answers) that the drafter and the grounding check use as the source.
Before payment we only collect answers: nothing here shows advice, answer text or drafts."""
import re
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
 ("wash","31","Washing, bathing and showering",("x31","/Yes"),[C("in","Getting in or out of the bath or shower"),C("hair","Washing hair"),C("fell","Has slipped or fallen in the bathroom"),C("groom","Shaving, teeth or appearance")]),
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
PEOPLE={"aa":["GP","Practice nurse","Consultant","Occupational therapist","District nurse","Social worker","Family carer"],
 "dla":["GP","Paediatrician","Teacher or SENCo","Speech therapist","Occupational therapist","Health visitor","CAMHS"],
 "pip":["GP","Consultant","Mental health team","Physio","Occupational therapist","Support worker","Family or friend"]}
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
    return "you" if d.get("who","me")=="me" else "them"
def is_me(d,form): return form!="dla" and d.get("who","me") in ("me","")
def _chk(n,v,txt,on,cls=""): return f'<label class="chip{cls}"><input type=checkbox name="{n}" value="{esc(v)}" {"checked" if on else ""}><span>{esc(txt)}</span></label>'
def _rad(n,v,txt,cur): return f'<label class=chip><input type=radio name="{n}" value="{esc(v)}" {"checked" if cur==v else ""}><span>{esc(txt)}</span></label>'
def _radios(n,opts,cur): return "<div class=chips>"+"".join(_rad(n,v,t,cur) for v,t in opts)+"</div>"
def _checks(n,opts,cur): cur=cur or []; return "<div class=chips>"+"".join(_chk(n,v,t,v in cur) for v,t in opts)+"</div>"
def _q(label,inner,hint=""): return f'<fieldset class=iq><legend>{esc(label)}</legend>{f"<p class=hint>{esc(hint)}</p>" if hint else ""}{inner}</fieldset>'
def NUM(a,b): return [(str(i),str(i)) for i in range(a,b+1)]+[("ns","Not sure")]
def row_card(form,r,d):
    rid,topic,label,gate,chips=r; cur=(d.get("rows") or {}).get(rid,{}); me=is_me(d,form)
    hard="I find this hard" if me else f"Hard for {name(d,form)}"
    helpt="I need help or reminding" if me else "Needs help or reminding"
    more=""
    if chips: more+='<p class=sub>What happens? <span class=hint>(tap any)</span></p>'+_checks(f"r_{rid}_c",[(c[0],c[1]) for c in chips],cur.get("c"))
    if form=="pip": more+='<p class=sub>Can it be done… <span class=hint>(tap any that are true)</span></p>'+_checks(f"r_{rid}_std",PIP_STD,cur.get("std"))
    more+='<p class=sub>How often is it like this?</p>'+_radios(f"r_{rid}_freq",FREQ,cur.get("freq"))
    more+='<p class=sub>How long does it take each time?</p>'+_radios(f"r_{rid}_time",TIME,cur.get("time"))
    return f'<div class=card><h3>{esc(label)}</h3><div class="chips main">{_chk(f"r_{rid}_hard","1",hard,cur.get("hard"),cls=" k")}{_chk(f"r_{rid}_help","1",helpt,cur.get("help"),cls=" k")}</div><div class=more>{more}</div></div>'
def section_body(form,sec,d):
    nm=name(d,form); me=is_me(d,form); you=("you" if me else nm); h=""
    if sec=="about":
        if form=="dla":
            h+=_q("Who are you to the child?",_radios("rel",[("Mum","Mum"),("Dad","Dad"),("Grandparent","Grandparent"),("Guardian","Guardian"),("Other","Someone else")],d.get("rel")))
            h+=_q("Child's first name",f'<input name=name value="{esc(d.get("name",""))}" autocomplete=off maxlength=40>',"We use it in the questions. Optional.")
            h+=_q("How old are they?",_radios("age",[("u3","Under 3"),("3to4","3 or 4"),("5to15","5 to 15"),("ns","Not sure")],d.get("age")))
        else:
            opts=[("me","Me"),("parent","My mum or dad"),("partner","My partner"),("other","Someone else")] if form=="aa" else [("me","Me"),("other","Someone I help")]
            h+=_q("Who is this form for?",_radios("who",opts,d.get("who")))
            h+=_q("Their first name (if it's not you)",f'<input name=name value="{esc(d.get("name",""))}" autocomplete=off maxlength=40 placeholder="e.g. Mum or Margaret">',"We use it in the questions. Optional.")
            h+=_q("If it's someone else: who will sign the form?",_radios("signer",[("them","They will sign it themselves"),("poa","I have Power of Attorney"),("appointee","I'm their appointee"),("ns","Not sure yet")],d.get("signer")),"Skip this if the form is for you.")
    elif sec=="conds":
        have={c.get("name"):c for c in d.get("conds") or []}
        yrs=[("","When did it start?")]+[(str(y),str(y)) for y in range(2026,1939,-1)]+[("ns","Not sure")]
        def sel(n,cur): return f'<select name="{n}" aria-label="When did it start">'+"".join(f'<option value="{v}" {"selected" if cur==v else ""}>{t}</option>' for v,t in yrs)+"</select>"
        lst=""
        for i,cn in enumerate(CONDS[form]):
            c=have.get(cn,{}); lst+=f'<div class=cond>{_chk(f"cond_{i}","1",cn,bool(c),cls=" k")}<div class=more>{sel(f"cond_{i}_since",c.get("since",""))}{_checks(f"cond_{i}_t",TREAT,c.get("treat"))}</div></div>'
        others=[c for c in d.get("conds") or [] if c.get("name") not in CONDS[form]]+[{},{},{}]
        for j,c in enumerate(others[:3]):
            lst+=f'<div class="cond other"><input name="oc_{j}" value="{esc(c.get("name",""))}" placeholder="Another condition (type it)" maxlength=80 aria-label="Another condition">{sel(f"oc_{j}_since",c.get("since",""))}{_checks(f"oc_{j}_t",TREAT,c.get("treat"))}</div>'
        h+=_q("Which health conditions or disabilities "+("do you have?" if me else f"does {nm} have?"),lst,"Tap each one that applies, then roughly when it started. No diagnosis needed.")
    elif sec in ("daily","out"):
        if sec=="daily":
            h+=_q("How many bad days in a normal week?",_radios("bad",NUM(0,7),d.get("bad")),"A bad day is when things are harder than usual. We work out the rest.")
            if form=="aa": h+=_q(("How many days a week do you" if me else f"How many days a week does {nm}")+" need help with care?",_radios("days_help",NUM(0,7),d.get("days_help")))
        h+='<p class=lede2>Tap what applies on most days. Leave anything that\'s fine.</p>'+"".join(row_card(form,r,d) for r in rows(form,sec,d))
    elif sec=="safety":
        if form=="aa":
            h+=_q("Falls in the last year",_radios("falls",[("0","None"),("1-2","1–2"),("3-5","3–5"),("6+","6 or more"),("ns","Not sure")],d.get("falls")))
            h+=_q("When was the last fall?",_radios("lastfall",[("week","This week"),("month","This month"),("months","1–6 months ago"),("year","Over 6 months ago"),("ns","Not sure")],d.get("lastfall")),"Skip if no falls.")
            h+=_q("After a fall",_checks("fallx",[("getup","Can't get up without help"),("clinic","Referred to a falls clinic"),("alarm","Has a pendant alarm")],d.get("fallx")))
            h+=_q(f"Does someone need to keep an eye on {you} in the day?",_checks("eye",[("danger","Not aware of dangers"),("wander","May wander"),("fits","Dizzy spells, fits or blackouts"),("confused","Gets confused")],d.get("eye")))
            h+=_q(f"How long can {you} safely be left alone?",_radios("alone",[("always","As long as needed"),("hours","A few hours"),("lt1","Under an hour"),("never","Not at all"),("ns","Not sure")],d.get("alone")))
            h+=_q("Help during the night (after everyone has gone to bed)",_checks("night",[("toilet","Toilet"),("turn","Turning over or settling"),("pain","Pain or breathing"),("meds","Medicines"),("confused","Confused or distressed")],d.get("night")),"Skip if none.")
            h+=_q("Nights a week",_radios("nights",NUM(0,7),d.get("nights")))+_q("Times a night",_radios("ntimes",[("1","1"),("2","2"),("3","3"),("4+","4 or more"),("ns","Not sure")],d.get("ntimes")))+_q("Minutes each time",_radios("nmins",TIME,d.get("nmins")))
            h+=_q(f"Does someone need to stay awake to watch over {you} at night?",_radios("watch",[("no","No"),("some","Some nights"),("most","Most nights"),("ns","Not sure")],d.get("watch")))
        else:
            h+=_q("Fits, blackouts or seizures?",_radios("fits",[("no","No"),("month","Less than weekly"),("week","Weekly"),("day","Daily"),("ns","Not sure")],d.get("fits")))
            h+=_q("Do their needs change from day to day?",_radios("varies",[("same","Mostly the same"),("varies","They change a lot"),("ns","Not sure")],d.get("varies")))
            nn=d.get("nn") or []; q=d.get("nnum") or {}
            inner="".join(f'<div class=cond>{_chk("nn",k,t,k in nn,cls=" k")}<div class=more>{_radios(f"nn_{k}_n",[(str(i),f"{i} nights") for i in range(1,8)]+[("ns","Not sure")],q.get(k,{}).get("n"))}{_radios(f"nn_{k}_t",[(str(i),f"{i}× a night") for i in range(1,5)]+[("ns","Not sure")],q.get(k,{}).get("t"))}{_radios(f"nn_{k}_m",[("10","10 min"),("20","20 min"),("30","30 min"),("45","45 min"),("60","1 hour+"),("ns","Not sure")],q.get(k,{}).get("m"))}</div></div>' for k,t in NIGHT_DLA)
            h+=_q(f"Help {nm} needs at night (after everyone is in bed)",inner,"Tap a reason, then nights a week, times a night and minutes. Skip if none.")
            if d.get("age")!="u3": h+='<p class=lede2>Getting out and about</p>'+"".join(row_card(form,r,d) for r in rows(form,"safety",d))
    elif sec=="finish":
        h+=_q("Aids or equipment used",_checks("aids",[(a,a) for a in AIDS[form]],d.get("aids")))
        if form=="dla": h+=_q("School or nursery",_checks("school",SCHOOL,d.get("school")))
        h+=_q(f"Who knows {you} well?",_checks("people",[(p,p) for p in PEOPLE[form]],d.get("people")),"We'll list who could support the claim.")
        h+=_q("Anything else, in your own words (optional)",f'<textarea name=words rows=4 maxlength=3000 placeholder="For example: what a bad day looks like.">{esc(d.get("words",""))}</textarea>',"Skip this if you like. You only tap, we do the writing.")
    return h
# ---------- saving ----------
def save(form,sec,d,fm):
    """Merge one section's answers (starlette FormData) into d. Untouched rows/questions are simply skipped."""
    g=lambda k:(str(fm.get(k) or "").strip())[:200]; gl=lambda k:[str(x)[:80] for x in fm.getlist(k)]
    if sec=="about":
        for k in ("who","name","signer","rel","age"): d[k]=g(k)
        d["name"]=re.sub(r"[^\w '\-.]","",d["name"])[:40]
        if d.get("who")=="me": d["signer"]=""
    elif sec=="conds":
        cs=[]
        for i,cn in enumerate(CONDS[form]):
            if fm.get(f"cond_{i}"): cs.append({"name":cn,"since":g(f"cond_{i}_since"),"treat":gl(f"cond_{i}_t")})
        for j in range(3):
            n=g(f"oc_{j}")[:80]
            if n: cs.append({"name":n,"since":g(f"oc_{j}_since"),"treat":gl(f"oc_{j}_t")})
        d["conds"]=cs
    elif sec in ("daily","out","safety"):
        R=d.setdefault("rows",{})
        for r in rows(form,sec,d):
            rid=r[0]; v={"hard":bool(fm.get(f"r_{rid}_hard")),"help":bool(fm.get(f"r_{rid}_help")),"c":gl(f"r_{rid}_c"),"std":gl(f"r_{rid}_std"),"freq":g(f"r_{rid}_freq"),"time":g(f"r_{rid}_time")}
            if v["hard"] or v["help"] or v["c"] or v["std"]: R[rid]=v
            else: R.pop(rid,None)
        keys={"daily":("bad","days_help"),"out":(),"safety":("falls","lastfall","alone","nights","ntimes","nmins","watch","fits","varies")}[sec]
        for k in keys: d[k]=g(k)
        if sec=="safety":
            for k in ("fallx","eye","night","nn"): d[k]=gl(k)
            d["nnum"]={k:{x:g(f"nn_{k}_{x}") for x in "ntm"} for k in d["nn"]}
    elif sec=="finish":
        for k in ("aids","school","people"): d[k]=gl(k)
        d["words"]=str(fm.get("words") or "").strip()[:3000]
    return d
# ---------- turning taps into the customer's own answers ----------
def _ok(v): return v not in (None,"","ns")
def _rowtext(form,r,v,d):
    rid,topic,label,gate,chips=r; me=is_me(d,form); who=name(d,form); bits=[]
    if v.get("hard"): bits.append("I find this hard" if me else f"{who} finds this hard")
    if v.get("help"): bits.append("I need help or reminding" if me else "needs help or reminding")
    cm={c[0]:c[1] for c in chips}; cs=[cm[x] for x in v.get("c",[]) if x in cm]
    if cs: bits.append("difficulty with: "+"; ".join(x[0].lower()+x[1:] for x in cs))
    sm=dict(PIP_STD); st=[sm[x].lower() for x in v.get("std",[]) if x in sm]
    if st: bits.append("it can be done "+", ".join(st))
    if _ok(v.get("freq")): bits.append("like this "+FREQ_T[v["freq"]].lower())
    if TIME_T.get(v.get("time","")): bits.append("each time takes "+TIME_T[v["time"]])
    return (f"{label}: "+", ".join(bits)+".") if bits else ""
def topic_texts(form,d):
    """(intro, {topic id: plain text of what the customer tapped})."""
    from forms import FORMS
    me=is_me(d,form); nm=name(d,form); T={t:[] for t,_,_ in FORMS[form]["topics"]}
    if form=="dla": intro=f"This form is for my child{(' '+d['name']) if d.get('name') else ''}"+(f"; I am their {d['rel'].lower()}." if d.get("rel") and d["rel"]!="Other" else ".")
    else: intro={"me":"This form is for me.","parent":"This form is for my parent","partner":"This form is for my partner","other":"This form is for someone I help"}.get(d.get("who") or "me","")
    if not me and form!="dla": intro+=(f" ({d['name']})." if d.get("name") else ".")
    intro+=" "+{"them":"They will sign the form themselves.","poa":"I have Power of Attorney.","appointee":"I am their appointee.","ns":"I'm not sure yet who will sign."}.get(d.get("signer",""),"")
    if _ok(d.get("age")): intro+=" Age: "+{"u3":"under 3","3to4":"3 or 4","5to15":"5 to 15"}[d["age"]]+"."
    cl=[]
    for c in d.get("conds") or []:
        tm=dict(TREAT); tr=[tm[x].lower() for x in c.get("treat",[]) if x in tm and x!="ns"]
        cl.append(c["name"]+(f" since {c['since']}" if _ok(c.get("since")) else "")+(f" (treatment: {', '.join(tr)})" if tr else ""))
    if cl:
        s="Health conditions: "+"; ".join(cl)+"."
        if "conditions" in T: T["conditions"].append(s)
        else: intro+=" "+s
    if _ok(d.get("bad")):
        s=f"Bad days: about {d['bad']} a week."
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
        fx={"getup":"Can't get up after a fall without help.","clinic":"Referred to a falls clinic.","alarm":"Has a pendant alarm."}; f=(f+" "+" ".join(fx[x] for x in d.get("fallx") or [] if x in fx)).strip()
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
            ns.append(nd.get(k,k)+(" ("+", ".join(parts)+")" if parts else ""))
        if ns: T["night"].append("Help at night with: "+"; ".join(ns)+".")
        sc=dict(SCHOOL); s=[sc[x] for x in d.get("school") or [] if x in sc]
        if s: T["school"].append("School or nursery: "+"; ".join(s)+".")
        if d.get("people"): T["statement"].append("People who know the child well: "+", ".join(d["people"])+".")
    if form=="pip" and d.get("people"): T["other"].append("Professionals and people who know "+("me" if me else "them")+": "+", ".join(d["people"])+".")
    if d.get("aids"): T[{"aa":"33","dla":"daycare","pip":"other"}[form]].append("Aids used: "+", ".join(d["aids"])+".")
    if d.get("words"): T[{"aa":"40","dla":"42","pip":"other"}[form]].append("In my own words: "+d["words"])
    return " ".join(intro.split()),{k:" ".join(v) for k,v in T.items()}
def history(form,d):
    """Q/A transcript in topic order (one answer per topic), so drafting, grounding and 'what you told us' work unchanged."""
    from forms import FORMS
    intro,T=topic_texts(form,d); h=[{"role":"assistant","content":"About the claim"},{"role":"user","content":intro or "(No details given.)"}]
    for t,l,_ in FORMS[form]["topics"]: h+=[{"role":"assistant","content":l},{"role":"user","content":T.get(t) or "Nothing selected for this."}]
    return h
def coverage(form,d):
    from forms import FORMS
    _,T=topic_texts(form,d); tops=FORMS[form]["topics"]; return sum(1 for t,_,_ in tops if T.get(t)),len(tops)
def ticks(form,d):
    """Tick-box states taken straight from the taps (only what was tapped; never consent/declaration/bank boxes)."""
    out={}
    for r in rows(form,None,d):
        v=(d.get("rows") or {}).get(r[0])
        if not v: continue
        if r[3]: out[r[3][0]]=r[3][1]
        for cid,_,tk,hp in r[4]:
            if cid in (v.get("c") or []):
                for f,s in tk: out[f]=s
                if v.get("help"):
                    for f,s in hp: out[f]=s
    if form=="aa":
        if d.get("falls") in ("1-2","3-5","6+"): out["x34"]="/Fall"
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
    return out
def extra(form,d):
    """Number boxes on the PDF, from taps only."""
    e={}
    if form=="aa":
        if _ok(d.get("days_help")): e["days_week_day"]=d["days_help"]
        if _ok(d.get("nights")) and d.get("night"): e["nights_week"]=d["nights"]
        if d.get("falls") in ("1-2","3-5","6+"): e["falls_year"]=d["falls"].replace("-"," to ")
        lf={"week":"This week","month":"This month","months":"In the last 6 months","year":"Over 6 months ago"}.get(d.get("lastfall"))
        if lf: e["last_fell"]=lf
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
    if d.get("people"): out.append("People who could support the claim: "+", ".join(d["people"])+".")
    return out
def personal_prefill(form,d):
    p={}
    nm=(d.get("name") or "").strip()
    if nm and (form=="dla" or not is_me(d,form)) and nm.lower() not in ("mum","dad","mom","mam","nan","gran","nana","grandma","grandad"): p["other_names"]=nm
    if form=="dla" and d.get("rel") and d["rel"]!="Other": p["relationship"]=d["rel"]
    return p

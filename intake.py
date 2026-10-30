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
    if d.get("who","me") in ("me",""): return "you"
    # 30 Oct: no name given for someone else -> a noun that works as subject and object ('them' gave "does them have")
    return {"parent":"your parent","partner":"your partner"}.get(d.get("who"),"the person you help")
def is_me(d,form): return form!="dla" and d.get("who","me") in ("me","")
def _chk(n,v,txt,on,cls=""): return f'<label class="chip{cls}"><input type=checkbox name="{n}" value="{esc(v)}" {"checked" if on else ""}><span>{esc(txt)}</span></label>'
def _rad(n,v,txt,cur): return f'<label class=chip><input type=radio name="{n}" value="{esc(v)}" {"checked" if cur==v else ""}><span>{esc(txt)}</span></label>'
def _radios(n,opts,cur,cls=""): return f"<div class='chips{cls}'>"+"".join(_rad(n,v,t,cur) for v,t in opts)+"</div>"
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
    opts="".join(_chk(f"r_{rid}_c",v,t,v in cv,cls=f" fx-{v}") for v,t in tk+fx)
    more='<p class=sub>What happens? <span class=hint>(tap any)</span></p><div class="chips two">'+opts+_else(f"r_{rid}_c",cur.get("x",""))+'</div>'
    more+='<p class=sub>How many days a week is it like this?</p>'+_radios(f"r_{rid}_days",DAYS,cur.get("days")," nums")
    return f'<div class=card><h3>{esc(label)}</h3><div class="chips main lvl">{"".join(_rad(f"r_{rid}_lvl",v,t,lvl) for v,t in LVL)}</div><div class=more>{more}</div></div>'
def sections(form,d):
    """Sections for this order: whole-form orders (wf_v) get the extra ones from wholeform.py."""
    import wholeform; return wholeform.sections(form,d or {})
def section_body(form,sec,d):
    import wholeform
    if wholeform.is_wf_section(sec): return wholeform.section_body(form,sec,d)
    nm=name(d,form); me=is_me(d,form); you=("you" if me else nm); h=""
    if sec=="about":
        if form=="dla":
            h+=_q("Who are you to the child?",_radios("rel",[("Mum","Mum"),("Dad","Dad"),("Grandparent","Grandparent"),("Guardian","Guardian"),("Other","Someone else")],d.get("rel")))
            h+=_q("Child's first name",f'<input name=name value="{esc(d.get("name",""))}" autocomplete=off maxlength=40>',"We use it in the questions. Optional.")
            h+=_q("How old are they?",_radios("age",[("u3","Under 3"),("3to4","3 or 4"),("5to15","5 to 15"),("ns","Not sure")],d.get("age")))
        else:
            opts=[("me","Me"),("parent","My mum or dad"),("partner","My partner"),("other","Someone else")] if form=="aa" else [("me","Me"),("other","Someone I help")]
            h+=_q("Who is this form for?",_radios("who",opts,d.get("who")))
            # 30 Oct: only shown once 'someone else' is picked (one question per screen skips hidden ones); 'Me' never sees them
            dv=" ".join(v for v,_ in opts if v!="me")
            h+=f'<div class=wdep data-dep="who" data-vals="{dv}">'+_q("Their first name",f'<input name=name value="{esc(d.get("name",""))}" autocomplete=off maxlength=40 placeholder="e.g. Mum or Margaret">',"We use it in the questions. Optional.")+'</div>'
            h+=f'<div class=wdep data-dep="who" data-vals="{dv}">'+_q("Who will sign the form?",_radios("signer",[("them","They will sign it themselves"),("poa","I have Power of Attorney"),("appointee","I'm their appointee"),("deputy","I'm their deputy (Court of Protection)"),("ns","Not sure yet")],d.get("signer")))+'</div>'
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
            h+=_q("How many bad days in a normal week?",_radios("bad",NUM(0,7),d.get("bad")," nums"),"A bad day is when things are harder than usual. We work out the rest.")
            # v4: AA 'days a week needing help' is no longer asked; it comes from the per-task days answers (see save)
        h+='<p class=lede2>How is each of these? One tap each. We only ask more if it isn\'t fine.</p>'+"".join(row_card(form,r,d) for r in rows(form,sec,d))
    elif sec=="safety":
        if form=="aa":
            h+='<div class=gq><div class=g>'+_q("Falls in the last year",_radios("falls",[("0","None"),("1-2","1–2"),("3-5","3–5"),("6+","6 or more"),("ns","Not sure")],d.get("falls")))+'</div><div class=dep>'
            h+=_q("When was the last fall?",_radios("lastfall",[("week","This week"),("month","This month"),("months","1–6 months ago"),("year","Over 6 months ago"),("ns","Not sure")],d.get("lastfall")))
            h+=_q("After a fall",_checks("fallx",[("getup","Can't get up without help"),("hurt","Was hurt or went to hospital"),("clinic","Referred to a falls clinic"),("alarm","Has a pendant alarm")],d.get("fallx"),X(d,"fallx")))+'</div></div>'
            h+=_q(f"Does someone need to keep an eye on {you} in the day?",_checks("eye",[("danger","Not aware of dangers"),("wander","May wander"),("fits","Dizzy spells, fits or blackouts"),("confused","Gets confused")],d.get("eye"),X(d,"eye")))
            h+=_q(f"How long can {you} safely be left alone?",_radios("alone",[("always","As long as needed"),("hours","A few hours"),("lt1","Under an hour"),("never","Not at all"),("ns","Not sure")],d.get("alone")))
            h+='<div class=gq><div class=g>'+_q("Help during the night (after everyone has gone to bed)",_checks("night",[("toilet","Toilet"),("turn","Turning over or settling"),("pain","Pain or breathing"),("meds","Medicines"),("confused","Confused or distressed")],d.get("night"),X(d,"night")),"Skip if none.")+'</div><div class=dep>'
            h+=_q("Nights a week",_radios("nights",NUM(0,7),d.get("nights")," nums"))+_q("Times a night",_radios("ntimes",[("1","1"),("2","2"),("3","3"),("4+","4 or more"),("ns","Not sure")],d.get("ntimes")))+_q("Minutes each time",_radios("nmins",TIME,d.get("nmins")))
            h+=_q(f"Does someone need to stay awake to watch over {you} at night?",_radios("watch",[("no","No"),("some","Some nights"),("most","Most nights"),("ns","Not sure")],d.get("watch")))+'</div></div>'
        else:
            h+=_q("Fits, blackouts or seizures?",_radios("fits",[("no","No"),("month","Less than weekly"),("week","Weekly"),("day","Daily"),("ns","Not sure")],d.get("fits")))
            h+=_q(f"Do {nm}'s needs change from day to day?" if d.get("name") else "Do their needs change from day to day?",_radios("varies",[("same","Mostly the same"),("varies","They change a lot"),("ns","Not sure")],d.get("varies")))
            nn=d.get("nn") or []; q=d.get("nnum") or {}
            inner="".join(f'<div class=cond>{_chk("nn",k,t,k in nn,cls=" k")}<div class=more>{_radios(f"nn_{k}_n",[(str(i),f"{i} nights") for i in range(1,8)]+[("ns","Not sure")],q.get(k,{}).get("n"))}{_radios(f"nn_{k}_t",[(str(i),f"{i}× a night") for i in range(1,5)]+[("ns","Not sure")],q.get(k,{}).get("t"))}{_radios(f"nn_{k}_m",[("10","10 min"),("20","20 min"),("30","30 min"),("45","45 min"),("60","1 hour+"),("ns","Not sure")],q.get(k,{}).get("m"))}</div></div>' for k,t in NIGHT_DLA)
            inner+=f'<div class=chips>{_else("nn",X(d,"nn"))}</div>'
            h+=_q(f"Help {nm} needs at night (after everyone is in bed)",inner,"Tap a reason, then nights a week, times a night and minutes. Skip if none.")
            if d.get("age")!="u3": h+='<p class=lede2>Getting out and about</p>'+"".join(row_card(form,r,d) for r in rows(form,"safety",d))
    elif sec=="finish":
        # 30 Oct: a pendant alarm tapped under falls is already ticked here (never ask the same thing twice)
        cur=d.get("aids") if d.get("aids") is not None else (["Pendant alarm"] if "alarm" in (d.get("fallx") or []) and "Pendant alarm" in AIDS[form] else [])
        h+=_q("Aids or equipment used",_checks("aids",[(a,a) for a in AIDS[form]],cur,X(d,"aids")))
        if form=="dla": h+=_q("School or nursery",_checks("school",SCHOOL,d.get("school"),X(d,"school")))
        h+=_q(f"Who knows {you} well?",_checks("people",[(p,p) for p in PEOPLE[form]],d.get("people"),X(d,"people")),"We'll list who could support the claim.")
        h+=_q("Anything else, in your own words (optional)",f'<textarea name=words rows=4 maxlength=3000 placeholder="For example: what a bad day looks like.">{esc(d.get("words",""))}</textarea>',"Skip this if you like. You only tap, we do the writing.")
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
        d["name"]=re.sub(r"[^\w '\-.]","",d["name"])[:40]
        if form!="dla" and d.get("who") in ("me",""): d["signer"]=""; d["name"]=""   # 'Me': no other-person answers kept
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
            v={"hard":bool(fm.get(f"r_{rid}_hard")) or lvl in ("slow","cant"),"help":bool(fm.get(f"r_{rid}_help")) or lvl in ("help","cant"),"lvl":lvl if lvl in dict(LVL) else "","c":gl(f"r_{rid}_c"),"std":gl(f"r_{rid}_std"),"freq":g(f"r_{rid}_freq"),"time":g(f"r_{rid}_time"),"days":g(f"r_{rid}_days"),"x":other_txt(fm,f"r_{rid}_c")}
            if lvl in ("cant","slow"): v["c"]=[x for x in v["c"] if x!="every"]
            if lvl=="ok": v={"lvl":"ok"}   # 'No difficulty': follow-ups ignored
            if v.get("hard") or v.get("help") or v.get("c") or v.get("std") or v.get("x") or lvl=="ok": R[rid]=v
            else: R.pop(rid,None)
        if sec=="daily" and form=="aa" and not fm.get("days_help"):   # derived from their own per-task answers, never guessed
            dd=[int(v["days"]) for v in R.values() if v.get("help") and str(v.get("days","")).isdigit()]
            d["days_help"]=str(max(dd)) if dd else ""
        keys={"daily":("bad",)+(("days_help",) if fm.get("days_help") else ()),"out":(),"safety":("falls","lastfall","alone","nights","ntimes","nmins","watch","fits","varies")}[sec]
        for k in keys: d[k]=g(k)
        if sec=="safety":
            for k in ("fallx","eye","night","nn"): d[k]=gl(k); d.setdefault("else",{})[k]=other_txt(fm,k)
            d["nnum"]={k:{x:g(f"nn_{k}_{x}") for x in "ntm"} for k in d["nn"]}
    elif sec=="finish":
        for k in ("aids","school","people"): d[k]=gl(k); d.setdefault("else",{})[k]=other_txt(fm,k)
        d["words"]=str(fm.get("words") or "").strip()[:3000]
        import followups   # completeness check per hard task before anything is written (asked once; answered checks count as known)
        keep=[tuple(x) for x in d.get("fu_qs") or [] if f"{x[0]}_{x[1]}" not in (d.get("fu") or {})]
        if os.getenv("FOLLOWUPS","1")=="0": d["fu_qs"],d["fu_how"]=[],"off"
        elif keep: d["fu_qs"]=keep   # coming back through: same checks, no new model call
        else: d["fu_qs"],d["fu_how"]=followups.pick(form,d)
        d["coverage"]=followups.coverage(form,d)
    return d
# ---------- turning taps into the customer's own answers ----------
def _ok(v): return v not in (None,"","ns")
def _rowtext(form,r,v,d):
    rid,topic,label,gate,chips=r; me=is_me(d,form); who=name(d,form); bits=[]
    if v.get("lvl")=="ok": return f"{label}: no difficulty."
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
        cl.append(c["name"]+(f" since {c['since']}" if _ok(c.get("since")) else "")+(f" (treatment: {', '.join(tr+([c['tx']] if c.get('tx') else []))})" if tr or c.get("tx") else ""))
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
            ns.append(nd.get(k,k)+(" ("+", ".join(parts)+")" if parts else ""))
        if ns: T["night"].append("Help at night with: "+"; ".join(ns)+".")
        sc=dict(SCHOOL); s=[sc[x] for x in d.get("school") or [] if x in sc]
        if s: T["school"].append("School or nursery: "+"; ".join(s)+".")
        if d.get("people"): T["statement"].append("People who know the child well: "+", ".join(d["people"])+".")
    if form=="pip" and d.get("people"): T["other"].append("Professionals and people who know "+("me" if me else "them")+": "+", ".join(d["people"])+".")
    E=lambda k: X(d,k).rstrip(".")
    if form=="aa":
        if E("fallx"): T["34"].append(f"After a fall, also: {E('fallx')}.")
        if E("eye"): T["40"].append(f"Keeping an eye on them, also: {E('eye')}.")
        if E("night"): T["42"].append(f"Help at night, also: {E('night')}.")
        if E("people"): T["40"].append(f"Other people who know them well: {E('people')}.")
        if d.get("people"): T["40"].append("People who know them well: "+", ".join(d["people"])+".")
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
    if cs: out.append(f"{w} {_v3(me,'have','has')} difficulty with: "+"; ".join(cs)+".")
    if v.get("x"): out.append("Also: "+v["x"].rstrip(".")+".")
    sm=dict(PIP_STD); st=[sm[x].lower() for x in v.get("std",[]) if x in sm]
    if st: out.append("It can only be done: "+", ".join(st)+".")
    if lv and _ok(v.get("days")): out.append(f"This happens {v['days']} days a week.")
    if _ok(v.get("freq")) and FREQ_T.get(v["freq"]): out.append("This happens "+FREQ_T[v["freq"]].lower()+".")
    if TIME_T.get(v.get("time","")): out.append("Each time takes "+TIME_T[v["time"]]+".")
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
       (r"\bPeople who know them well: ",f"People who know {obj} well: "),(r"\bOther people who know them well: ",f"Other people who know {obj} well: "),
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
def fallback_draft(form,d):
    """A complete, grounded draft from the taps alone: no AI. Same shape as llm.draft()."""
    from forms import FORMS
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
    ans={t:" ".join(v).strip() for t,v in T.items()}
    tick_yes=[t for t,a in ans.items() if a and t.isdigit()] if form=="aa" else []
    return {"answers":ans,"sources":{t:[raw[t]] for t in ans if raw.get(t)},"tick_yes":tick_yes,"conditions":[],"extra":{},
            "checklist":[],"notes_for_user":[],"gp_letter":"","drafted_from":"taps"}
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
    if d.get("people"): out.append("People who could support the claim: "+", ".join(d["people"])+".")
    return out
def personal_prefill(form,d):
    p={}
    nm=(d.get("name") or "").strip()
    if nm and (form=="dla" or not is_me(d,form)) and nm.lower() not in ("mum","dad","mom","mam","nan","gran","nana","grandma","grandad"): p["other_names"]=nm
    if form=="dla" and d.get("rel") and d["rel"]!="Other": p["relationship"]=d["rel"]
    return p

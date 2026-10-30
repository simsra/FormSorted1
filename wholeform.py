"""Whole form (28 Oct 2026): the rest of every fillable AA1 / DLA1A box, asked as one-tap questions BEFORE payment.
Every list has 'Something else'. Questions only appear when an earlier answer makes them relevant, and nothing already
asked is asked again (names, who signs, aids, people, rows and nights come from the earlier intake sections).
Signatures, declaration dates and the 'statement from someone who knows you' boxes are always left for the customer.
NI numbers and bank details are NOT asked here: see secure.py (asked after payment, encrypted, wiped after download)."""
import re, json, datetime
from html import escape as esc
import intake as I
_rad,_chk,_else,_q,X=I._rad,I._chk,I._else,I._q,I.X
YN=[("yes","Yes"),("no","No")]; YNS=YN+[("ns","Not sure")]
TITLES=[("Mr","Mr"),("Mrs","Mrs"),("Miss","Miss"),("Ms","Ms"),("Mx","Mx"),("Dr","Dr")]
NAT=[("British","British"),("Irish","Irish"),("EEA","EU, EEA or Swiss")]
SEEN=[("month","This month"),("1to3","1 to 3 months ago"),("3to6","3 to 6 months ago"),("6to12","6 to 12 months ago"),("over","Over a year ago")]
HOWOFTEN=[("weekly","Every week"),("monthly","Every month"),("3m","Every 3 months"),("6m","Every 6 months"),("year","Once a year")]
DOSE=[("1d","Once a day"),("2d","Twice a day"),("3d","3 times a day"),("4d","4 times a day"),("prn","When needed")]
TIMESD=[("1","1"),("2","2"),("3","3"),("4","4"),("5","5"),("6+","6 or more")]
MINS=[("5","5 min"),("10","10 min"),("15","15 min"),("20","20 min"),("30","30 min"),("45","45 min"),("60","1 hour+")]
SECTIONS={"aa":[("you","Personal details"),("helper","About you, the person helping"),("health","Doctors and treatment"),("home","Home and a few checks")],
          "dla":[("child","Your child's details"),("parent","Your details"),("health","Doctors, school and treatment"),("home","Home and a few checks")]}
OFTEN=("often","How often and how long")
MORE=("more","A few quick checks")
# minutes per section for 'about N minutes left' (measured on the walk-through; see test_wholeform.py)
WEIGHT={"more":.4,"about":.4,"conds":.8,"daily":1.6,"safety":.9,"often":1.3,"finish":.5,"you":1.0,"child":1.0,"helper":.5,"parent":.8,"health":1.2,"home":.8,"evidence":.5}
def on(): import os; return os.getenv("WHOLE_FORM","1")!="0"
def sections(form,d):
    """Section list for intake.py. Whole-form orders get the extra sections; the 'often' one goes after nights."""
    base=list(I.SECTIONS[form])
    if (d or {}).get("fu_qs"):   # quick checks straight after 'Aids and anything else' (followups.py)
        j=[k for k,_ in base].index("finish")+1; base=base[:j]+[MORE]+base[j:]
    if form not in SECTIONS or not (d or {}).get("wf_v"): return base
    ids=[k for k,_ in base]; out=base[:ids.index("finish")]+[OFTEN]+base[ids.index("finish"):]+SECTIONS[form]
    return [(k,l) for k,l in out if applies(form,k,d)]
def applies(form,sec,d):
    if sec=="helper": return d.get("who","me") not in ("me","") and d.get("signer") in ("poa","appointee","deputy")
    return True
COST={"radio":2.5,"checks":4,"text":9,"tel":8,"date":8,"month":6,"pc":6,"email":9,"num":6,"note":0}
def q_secs(q,w):
    """Rough seconds to answer one question that's still to come; dep-gated ones count only if they'll show."""
    if dep_ok(q,w): f=1
    elif any(dn not in w and dn[:-4]+"_x" not in w for dn,_ in _deps(q)): f=.1 if any(dn.endswith("diff") for dn,_ in _deps(q)) else .25
    else: return 0
    k=q["kind"]
    c=2*len(q["rows"])/3+3 if k=="tap" else 2.5*len(q["rows"]) if k=="grid" else COST.get(k,4)
    if k=="text" and "optional" in q["label"].lower(): c=3
    return f*c
def minutes_left(form,d,sec):
    """Minutes left, from the questions actually still to come given the answers so far (it can go up if an answer adds questions)."""
    ids=[k for k,_ in sections(form,d)]; i=ids.index(sec) if sec in ids else 0; w=W(d); left=30
    for j,k in enumerate(ids[i:]):
        if k in WF_IDS(form) and not (k=="often" and "daily" in ids[i:]):
            try: left+=6+sum(q_secs(q,w) for q in questions(form,k,d))
            except Exception: left+=60*WEIGHT.get(k,.8)
        else: left+=60*WEIGHT.get(k,.8)
    n=max(1,round(left/60)); d["left_min"]=n; return n
def WF_IDS(form): return {"often","more"}|{k for k,_ in SECTIONS.get(form,[])}
# ---------- question model ----------
def Q(id,label,kind="radio",opts=(),hint="",dep=None,ac="off",ph="",cls="",maxlen=120,rows=None,other=True,pre=None):
    """dep: (name, values) or a list of them (all must hold). pre: options the customer already told us about earlier;
    shown as ONE button that ticks them (never pre-ticked: the customer confirms by tapping). kind 'tap': rows
    (field, label, 'need'|'can') as one 'tap any that apply' list with None of these."""
    return {"id":id,"label":label,"kind":kind,"opts":list(opts),"hint":hint,"dep":dep,"ac":ac,"ph":ph,"cls":cls,"maxlen":maxlen,"rows":rows or [],"other":other,"pre":pre or []}
def _deps(q): d=q["dep"]; return [] if not d else (d if isinstance(d,list) else [d])
INPUT={"text":"text","date":"date","month":"month","tel":"tel","email":"email","pc":"text","num":"text"}
def _grid(q,w):
    out=""
    for sid,lab in q["rows"]:
        cur=w.get(sid,"")
        out+=f'<div class=yn><span class=ynq>{esc(lab)}</span><span class="chips yn2">{_rad(sid,"yes","Yes",cur)}{_rad(sid,"no","No",cur)}</span></div>'
    return out+f'<div class=chips>{_else(q["id"],w.get(q["id"]+"_x",""))}</div>'
def _tap(q,w):
    cur=w.get(q["id"]) or []
    return I._checks(q["id"],[(sid,lab) for sid,lab,_ in q["rows"]]+[("none","None of these")],cur,w.get(q["id"]+"_x",""))
def _pre_btn(q):
    lab={v:t for v,t in q["opts"]}; pre=[x for x in q["pre"] if x in lab]
    if not pre: return ""
    return f'<p class=prebtn><button type=button class="btn btn-2 usepre" data-for="{esc(q["id"])}" data-vals="{esc(" ".join(pre))}">Tap to use what you told us: {esc(", ".join(lab[x] for x in pre))}</button></p>'
def render_q(q,w):
    n,k=q["id"],q["kind"]; cur=w.get(n)
    if k=="tap": inner=_tap(q,w)
    elif k=="radio": inner=f"<div class='chips{q['cls']}'>"+"".join(_rad(n,v,t,cur or "") for v,t in q["opts"])+(_else(n,w.get(n+"_x","")) if q["other"] else "")+"</div>"
    elif k=="checks": inner=_pre_btn(q)+I._checks(n,q["opts"],cur if isinstance(cur,list) else [],w.get(n+"_x","") if q["other"] else None)
    elif k=="grid": inner=_grid(q,w)
    elif k=="note": inner=""
    else:
        extra=' inputmode=numeric' if k=="num" else ' autocapitalize=characters' if k=="pc" else ''
        inner=f'<input name="{n}" id="w_{n}" type={INPUT[k]} value="{esc(str(cur or ""))}" autocomplete="{q["ac"]}" maxlength={q["maxlen"]} placeholder="{esc(q["ph"])}"{extra}>'
        if k=="pc": inner=f'<div class=pcrow>{inner}<button type=button class="btn btn-2 pcfind" data-for="{n}">Find</button></div><p class="hint pcout" id="pc_{n}" aria-live=polite></p>'
    h=_q(q["label"],inner,q["hint"])
    for dn,vals in reversed(_deps(q)): h=f'<div class=wdep data-dep="{esc(dn)}" data-vals="{esc(" ".join(vals))}">{h}</div>'
    return h
def _clean(s,n=120): return re.sub(r"[\x00-\x1f<>]"," ",str(s or "")).strip()[:n]
def save_q(q,fm,w):
    n,k=q["id"],q["kind"]
    if k=="note": return
    if k=="tap":
        picked=[x for x in fm.getlist(n) if x in {sid for sid,_,_ in q["rows"]}|{"none"}]; xon=I.other_txt(fm,n)
        if "none" in picked: picked=["none"]
        w[n]=picked; w[n+"_x"]=xon
        for sid,_,pol in q["rows"]:   # answered only if they tapped something (an item, None of these or Something else)
            on_=sid in picked
            w[sid]=("" if not (picked or xon) else ("yes" if on_ else "no") if pol=="need" else ("no" if on_ else "yes"))
        return
    if k=="checks": w[n]=[_clean(x,80) for x in fm.getlist(n) if x in {v for v,_ in q["opts"]}]
    elif k=="grid":
        for sid,_ in q["rows"]: w[sid]=_clean(fm.get(sid),5) if fm.get(sid) in ("yes","no") else ""
    elif k=="radio": v=_clean(fm.get(n),80); w[n]=v if v in {x for x,_ in q["opts"]} else ""
    else:
        v=_clean(fm.get(n),q["maxlen"])
        if k=="pc": v=re.sub(r"\s+"," ",v.upper()); v=v if re.fullmatch(r"[A-Z]{1,2}\d[A-Z\d]? ?\d[A-Z]{2}",v) else ""
        if k=="pc" and v and " " not in v: v=v[:-3]+" "+v[-3:]
        if k=="date": v=v if re.fullmatch(r"\d{4}-\d{2}-\d{2}",v) else ""
        if k=="month": v=v if re.fullmatch(r"\d{4}-\d{2}",v) else ""
        if k=="tel": v=re.sub(r"[^\d+ ]","",v)[:20]
        if k=="email": v=v if re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+",v) else ""
        w[n]=v
    if k in ("radio","checks","grid") and q["other"]: w[n+"_x"]=I.other_txt(fm,n)
def dep_ok(q,w):
    for dn,vals in _deps(q):
        if dn.endswith("_xon"):
            if not w.get(dn[:-4]+"_x"): return False
            continue
        v=w.get(dn)
        if not any(x in vals for x in (v if isinstance(v,list) else [v])): return False
    return True
# ---------- helpers ----------
def W(d): return d.setdefault("wf",{})
def nm(d,form): return I.name(d,form)
def me(d,form): return I.is_me(d,form)
def _you(d,form): return "you" if me(d,form) else nm(d,form)
def _your(d,form): return "your" if me(d,form) else (nm(d,form)+"'s" if form!="dla" or I.name(d,form)!="your child" else "your child's")
def _do(d,form): return "do you" if me(d,form) else f"does {nm(d,form)}"
def PR(d,form):
    """Wording for the person the form is about (30 Oct: 'Does you...', 'when they fall' for 'Me' orders).
    me: you/your; someone else: their name (or 'your parent' etc.) with the right verb forms."""
    m=me(d,form); n=nm(d,form)
    if m: return {"subj":"you","obj":"you","poss":"your","do":"do you","be":"are you","have":"have you","were":"were you","refl":"yourself","dont":"don't","s":lambda v:v}
    return {"subj":n,"obj":n,"poss":_your(d,form),"do":f"does {n}","be":f"is {n}","have":f"has {n}","were":f"was {n}","refl":"themselves","dont":"doesn't","s":lambda v:v+("es" if v.endswith(("sh","ch")) else "s")}
def cap(t): return t[:1].upper()+t[1:]
def _ac(d,form,tok): return tok if me(d,form) else "off"
def conds(d): return [c for c in d.get("conds") or [] if c.get("name")][:6 if True else 5]
def aids(d): return I.aids_list(d)[:6]
def bad_rows(form,d):
    R=d.get("rows") or {}; return [r for r in I.rows(form,None,d) if R.get(r[0]) and R[r[0]].get("lvl")!="ok"]
PROFS={"aa":["Consultant","Practice nurse","Occupational therapist","District nurse","Social worker"],"dla":["Paediatrician","Speech therapist","Occupational therapist","Health visitor","CAMHS"]}
def prof(form,d):
    p=[x for x in d.get("people") or [] if x in PROFS[form]]; x=X(d,"people").strip()
    return p[0] if p else (x.split(",")[0].strip()[:60] if x else "")
# ---------- AA / DLA subtasks for 'how often each day' ----------
# (key, label, chip ids that mean this part is hard, fields...) AA: (difficulty fields, help field, prompt field)
AA_SUB={
 "toilet":[("toilet","Using the toilet",("onoff","clean","often",""),(["30-1","30-2"],"30-4","30-6")),("incont","Incontinence (accidents or pads)",("acc",),(["30-3"],"30-5","30-7"))],
 "wash":[("wash","Washing and drying",("feet","hair",""),(["31-3"],"31-7","31-10")),("bath","Getting in or out of the bath",("in",),(["31-2"],"31-6",None)),("shower","Getting in or out of the shower",(),(["31-4"],"31-8",None)),("look","Shaving, teeth or appearance",("groom",),(["31-1"],"31-5","31-9"))],
 "dress":[("on","Putting clothes on",("fast","feet","slow",""),(["32-1"],"32-4","32-7")),("off","Taking clothes off",(),(["32-2"],"32-5",None)),("choose","Choosing suitable clothes",("choose",),(["32-3"],"32-6","32-8"))],
 "eat":[("eat","Eating and drinking",("cup","forget","swallow",""),(["35-1"],"35-3","35-5")),("cut","Cutting up food",("cut",),(["35-2"],"35-4",None))],
 "meds":[("meds","Taking medicines",("forget","open","mix",""),(["36-1"],"36-3","36-5")),("treat","Treatment or therapy",("treat",),(["36-2"],"36-4","36-6"))]}
DLA_SUB={
 "bed":[("out","Getting out of bed","54_1","54_2"),("in","Getting into bed","54_3","54_4"),("settle","Settling in bed","54_5","54_6")],
 "wash":[("wash","Washing or bathing","57_1","57_2"),("teeth","Cleaning teeth","57_3","57_4"),("hair","Washing hair","57_5","57_6"),("bath","In or out of the bath","57_7","57_8"),("shower","In or out of the shower","57_9","57_10"),("clean","Cleaning themselves in the bath or shower","57_11","57_12"),("dry","Drying themselves","57_13","57_14"),("look","Checking their appearance","57_15","57_16")],
 "dress":[("on","Dressing","58_1","58_2"),("off","Undressing","58_3","58_4"),("fast","Zips, buttons and fastenings","58_5","58_6"),("choose","Choosing clothes","58_7","58_8")],
 "eat":[("eat","Eating","59_1","59_2"),("cutlery","Using cutlery or a spoon","59_3","59_4"),("cut","Cutting up food","59_5","59_6"),("drink","Drinking","59_7","59_8"),("tube","Tube feeding","59_9","59_10")],
 "meds":[("meds","Taking the right medicine","60_1","60_2"),("when","Knowing when to take it","60_3","60_4"),("therapy","Doing their therapy","60_5","60_6"),("remind","Remembering when to do therapy","60_7","60_8")]}
DLA_PRE={"wash":{"in":["bath"],"hair":["hair"],"safe":["wash"]},"dress":{"fast":["fast"],"order":["on"],"sens":["on"]},"eat":{"cut":["cut"],"tube":["tube"],"limited":["eat"],"choke":["eat","drink"]},
 "meds":{"meds":["meds"],"inhaler":["meds"],"physio":["therapy"],"monitor":["therapy"]}}
DLA_TOILET=[("55_1","Going to the toilet"),("55_2","Managing clothes"),("55_3","Getting on and off the toilet"),("55_4","Wiping or cleaning themselves"),("55_5","Washing and drying hands"),("55_6","A catheter, ostomy or stoma"),("55_7","Nappies or pads")]
DLA_TOILET_PRE={"pads":"55_7","wipe":"55_4","remind":"55_1"}
DLA_INDOORS=[("56_1","Up and down one step"),("56_2","Going upstairs"),("56_3","Going downstairs"),("56_4","Moving around safely"),("56_5","Getting into or out of a chair"),("56_6","Sitting in a chair")]
DLA_INDOORS_PRE={"stairs":["56_2","56_3"],"chair":["56_5"],"lift":["56_4"]}
ACTS_AA=[("hobby","A hobby at home"),("visits","Having visitors"),("calls","Phone or video calls"),("family","Visiting family or friends"),("faith","Church, mosque or other faith group"),("club","A club or day centre"),("shops","Shops or a café")]
ACT_HOME={"hobby","visits","calls"}
ACTS_DLA=[("club","After-school club or activity"),("swim","Swimming or sport"),("park","Park or playground"),("party","Parties and play dates"),("faith","Faith activities"),("trips","Family trips out")]
ACT_HELP=[("with","Someone with them all the time"),("there","Help getting there"),("prompt","Encouraging and reminding"),("care","Personal care while there"),("calm","Calming them if distressed")]
ACT_OFTEN=[("daily","Every day"),("few","A few times a week"),("weekly","Once a week"),("monthly","Once a month")]
ACT_LONG=[("30","30 minutes"),("1h","1 hour"),("2h","2 hours"),("half","Half a day or more")]
# ---------- the questions ----------
def questions(form,sec,d):
    if sec=="more": import followups; return followups.questions(form,d)
    w=d.get("wf") or {}; you=_you(d,form); do=_do(d,form); your=_your(d,form); qs=[]; P=PR(d,form)
    if sec in ("you","child"):
        child=form=="dla"; who="your child" if child else you
        t=lambda x:_ac(d,form,x) if not child else "off"
        if not child: qs.append(Q("title","Title","radio",TITLES,cls=" nums"))
        qs+= [Q("first",("Child's first and middle names" if child else "First and middle names"),"text",ac=t("given-name"),maxlen=60),
              Q("surname","Surname","text",ac=t("family-name"),maxlen=60)]
        if child: qs.append(Q("othernames","Any other surname they've been known by? (optional)","text",maxlen=60))
        qs+= [Q("dob","Date of birth","date",ac=t("bday")),
              Q("sex","Sex","radio",[("female","Female"),("male","Male")]),
              Q("nat","Nationality","radio",NAT),Q("nat_c","Which country?","text",maxlen=40,dep=("nat",["EEA"])),
              Q("pc","Postcode","pc",ac=t("postal-code"),maxlen=9,hint="Tap Find and we fill in the town."),
              Q("addr1","House number and street","text",ac=t("address-line1"),maxlen=60),
              Q("addr2","Second address line (optional)","text",ac=t("address-line2"),maxlen=60),
              Q("town","Town or city","text",ac=t("address-level2"),maxlen=40)]
        if not child:
            qs+= [Q("phone","Daytime phone","tel",ac=t("tel"),maxlen=20),Q("mobile","Mobile (optional)","tel",ac=t("tel"),maxlen=20),
                  Q("welsh","Letters in Welsh?","radio",[("no","English is fine"),("yes","Welsh, please (Wales only)")])]
        qs.append(Q("eea_before",f"{cap(P['were'])} living in the UK before 1 January 2021?","radio",[("yes","Yes"),("no","No"),("ns","Not sure")],dep=("nat",["EEA"])))
    elif sec=="helper":
        qs+= [Q("h_name","Your full name","text",ac="name",maxlen=80),Q("h_dob","Your date of birth","date",ac="bday"),
              Q("h_same",f"Do you live at the same address as {nm(d,form)}?","radio",YN),
              Q("h_pc","Your postcode","pc",ac="postal-code",maxlen=9,dep=("h_same",["no"])),Q("h_addr1","House number and street","text",ac="address-line1",maxlen=60,dep=("h_same",["no"])),
              Q("h_town","Town or city","text",ac="address-level2",maxlen=40,dep=("h_same",["no"])),
              Q("h_phone","Your phone","tel",ac="tel",maxlen=20)]
        if d.get("signer")=="poa": qs.append(Q("h_online","Does your Power of Attorney (property and finance) have an online account?","radio",YN))
        if d.get("signer")=="appointee": qs.append(Q("h_org","If an organisation is the appointee, its name (optional)","text",maxlen=80))
    elif sec=="parent":
        qs+= [Q("p_title","Your title","radio",TITLES,cls=" nums"),Q("p_first","Your first and middle names","text",ac="given-name",maxlen=60),
              Q("p_surname","Your surname","text",ac="family-name",maxlen=60),Q("p_dob","Your date of birth","date",ac="bday"),
              Q("p_nat","Your nationality","radio",NAT),Q("p_nat_c","Which country?","text",maxlen=40,dep=("p_nat",["EEA"])),
              Q("p_same","Do you live at the same address as your child?","radio",YN),
              Q("p_pc","Your postcode","pc",ac="postal-code",maxlen=9,dep=("p_same",["no"])),Q("p_addr1","House number and street","text",ac="address-line1",maxlen=60,dep=("p_same",["no"])),
              Q("p_town","Town or city","text",ac="address-level2",maxlen=40,dep=("p_same",["no"])),
              Q("p_phone","Your phone","tel",ac="tel",maxlen=20),Q("p_email","Your email (optional)","email",ac="email",maxlen=80),
              Q("p_text","Text you when DWP gets the form?","radio",[("yes","Yes, text my phone"),("no","No thanks")]),
              Q("p_welsh","Letters in Welsh?","radio",[("no","English is fine"),("yes","Welsh, please (Wales only)")]),
              Q("p_is","Are you getting, or waiting to hear about, Income Support?","radio",YNS),
              Q("p_his","Is anyone else in your home getting, or waiting to hear about, Income Support?","radio",YNS),
              Q("p_his_name","Their full name","text",maxlen=80,dep=("p_his",["yes"])),
              Q("p_his_rel","Who are they to you?","radio",[("Partner","Partner"),("Parent","My parent"),("Adult child","Adult child")],dep=("p_his",["yes"]))]
    elif sec=="health":
        if conds(d):
            qs.append(Q("meds_how","Medicines","radio",[("type","I'll type them now"),("photo","I'll add a photo of the repeat prescription list"),("none","No regular medicines")],hint="A photo is quickest. We write 'see the repeat prescription list' on the form and remind you to send a copy."))
        for i,c in enumerate(conds(d)):
            qs.append(Q(f"med_{i}",f"Medicines for {c['name']} (optional)","text",maxlen=100,ph="e.g. Ramipril 5mg",hint="Names and strength, as on the box or repeat list.",dep=("meds_how",["type"])))
            qs.append(Q(f"dose_{i}","How often?","radio",DOSE,dep=[("meds_how",["type"])]))
        g=w.get("gp_list") or []
        if g: qs.append(Q("gp",f"{'Your' if me(d,form) else 'Their'} GP surgery","radio",[(x["id"],x["label"]) for x in g][:12],hint="Practices near the postcode you gave. Not listed? Tap Something else and type the surgery name."))
        qs+= ([] if g else [Q("gp_name","Surgery name","text",maxlen=80)])+[Q("gp_pc","Surgery postcode","pc",maxlen=9,dep=("gp_xon",["1"]) if g else None),
              Q("gp_addr","Surgery street","text",maxlen=60,dep=("gp_xon",["1"]) if g else None),Q("gp_town","Surgery town","text",maxlen=40,dep=("gp_xon",["1"]) if g else None),
              Q("gp_tel","Surgery phone (optional)","tel",maxlen=20,dep=("gp_xon",["1"]) if g else None),
              Q("gp_doc","Doctor's name (optional)","text",maxlen=60,ph="e.g. Dr Patel"),
              Q("gp_seen",f"When did {you} last see the GP?","radio",SEEN)]
        p=prof(form,d)
        if p:
            qs+= [Q("pr_name",f"The {p}'s name (optional)","text",maxlen=60),Q("pr_where","Where do you see them?","text",maxlen=80,ph="e.g. St James's Hospital"),
                  Q("pr_pc","Postcode of that place (optional)","pc",maxlen=9),Q("pr_town","Town","text",maxlen=40),Q("pr_tel","Their phone (optional)","tel",maxlen=20),
                  Q("pr_hosp","Hospital number (optional)","text",maxlen=20,hint="On appointment letters."),
                  Q("pr_cond","What for?","radio",[(c["name"],c["name"]) for c in conds(d)][:6]),
                  Q("pr_often","How often?","radio",HOWOFTEN),Q("pr_seen","Last seen","radio",SEEN)]
        else: qs.append(Q("pr_any",f"Apart from the GP, {P['have']} seen anyone about this in the last 12 months?","radio",YN,hint="For example a consultant, nurse or therapist."))
        if form=="aa":
            carer=d.get("who") not in ("me","") or "Family carer" in (d.get("people") or [])
            hpo=([("me","Yes, me (the person filling this in)"),("yes","Yes, someone else")] if not me(d,form) else [("yes","Yes")])+[("no","No")]
            mine=["yes"] if applies(form,"helper",d) else ["yes","me"]
            qs+= [Q("hp_any",f"Does anyone help {you} because of this?","radio",hpo),
                  Q("hp_name","Their name","text",maxlen=60,dep=("hp_any",mine)),Q("hp_pc","Their postcode","pc",maxlen=9,dep=("hp_any",mine)),Q("hp_addr","Their house number and street","text",maxlen=60,dep=("hp_any",mine)),
                  Q("hp_town","Their town","text",maxlen=40,dep=("hp_any",mine)),Q("hp_tel","Their phone (optional)","tel",maxlen=20,dep=("hp_any",mine)),
                  Q("hp_rel","Who are they?","radio",[("Partner","Partner"),("Son or daughter","Son or daughter"),("Friend","Friend"),("Neighbour","Neighbour"),("Paid carer","Paid carer")],dep=("hp_any",["yes","me"])),
                  Q("hp_what","What do they help with?","checks",[("personal care","Washing and dressing"),("meals","Meals"),("medicines","Medicines"),("getting about","Getting about"),("keeping an eye",f"Keeping an eye on {P['obj']}")],dep=("hp_any",["yes","me"])),
                  Q("hp_often","How often?","radio",[("every day","Every day"),("most days","Most days"),("a few times a week","A few times a week"),("weekly","Once a week")],dep=("hp_any",["yes","me"]))]
        qs.append(Q("tests",f"Any tests, scans or assessments for {'your' if me(d,form) else 'their'} conditions{' (done or booked)' if form=='dla' else ''}?","radio",YN))
        qs+=rep("test",2 if form=="aa" else 5,"tests",lambda i,dp:[Q(f"test{i}","Which test, and when?","text",maxlen=80,ph="e.g. MRI scan, March 2026",dep=dp),
              Q(f"test{i}r","What did it show?","radio",[("waiting","Still waiting for results"),("see letter","It's in the letter we're sending")],dep=dp)],"Another test?")
        if form=="aa":
            qs.append(Q("surg",f"{cap(P['be'])} on a waiting list for surgery?","radio",YN))
            qs+=rep("surg",2,"surg",lambda i,dp:[Q(f"surg{i}_what","What surgery?","text",maxlen=80,ph="e.g. right hip replacement",dep=dp),
                  Q(f"surg{i}_when",f"When {P['were']} put on the list?","month",dep=dp),Q(f"surg{i}_date","Date planned (if known)","month",dep=dp)],"Another operation?")
            qs+= [
                  Q("care_start",f"Roughly when did {you} start needing this help?","month",hint="A rough month is fine. DWP needs it to be at least 6 months ago.")]
        else:
            sch=[x for x in d.get("school") or [] if x!="notatschool"]
            if d.get("school") is None or sch or not d.get("school"):
                if "notatschool" not in (d.get("school") or []):
                    qs+= [Q("sc_name","School or nursery name","text",maxlen=80),Q("sc_pc","Its postcode","pc",maxlen=9),Q("sc_addr","Its street","text",maxlen=60),Q("sc_town","Its town","text",maxlen=40),
                          Q("sc_contact","Teacher or SENCo who knows them best (optional)","text",maxlen=60),Q("sc_tel","School phone (optional)","tel",maxlen=20),Q("sc_email","School email (optional)","email",maxlen=80),
                          Q("sc_behav","Their behaviour at school or nursery","radio",[("Generally good","Generally good"),("Good some days, hard on others","Good some days, hard on others"),("Often hard for staff to manage","Often hard for staff to manage")]),
                          Q("sc_travel","How do they get to and from school?","radio",[("We drive them","We drive them"),("We walk with them","We walk with them"),("Council taxi or minibus with an escort","Council taxi or minibus"),("By bus with an adult","By bus with an adult"),("On their own","On their own")]),
                          Q("sc_type","Type of school","radio",[("main","Mainstream"),("special","Specialist school or unit"),("nursery","Nursery or pre-school")]),
                          Q("plans","Any plans or reports? (tap all)","checks",[(k,l) for k,l in [("iep","Individual Education Plan"),("ibp","Behaviour plan"),("sen","SEN statement or letter"),("csp","Co-ordinated Support Plan"),("waiting","Waiting to hear about a plan"),("none","None of these")] if not (k=="ehcp")])]
            qs+= [Q("care_start","Roughly when did their extra care needs start?","month",hint="A rough month is fine.")]
            if bad_rows(form,d) and any(r[0] in ("walk","out") for r in bad_rows(form,d)): qs+= [Q("mob_start","And their walking or getting-about needs?","month"),Q("motab","Would you like information from Motability?","radio",YN)]
        qs.append(Q("consent",f"Can DWP ask {'your' if me(d,form) else 'their'} doctors and others for more information?","radio",[("yes","Yes"),("no","No")],hint="This usually helps the claim go faster. It's your choice."))
    elif sec=="home":
        if form=="aa":
            qs+= [Q("acc",f"Where {P['do']} live?","radio",[("house","House"),("bungalow","Bungalow"),("flat","Flat"),("sheltered","Sheltered housing"),("care","Care home")]),
                  Q("liveswith","Who else lives there?","radio",[("alone","Lives alone"),("partner","Partner"),("family","Family"),("carer","Live-in carer")]),
                  Q("toiletat","Where is the toilet?","checks",[("up","Upstairs"),("down","Downstairs")]),Q("sleepat",f"Where {P['do']} sleep?","radio",[("up","Upstairs"),("down","Downstairs")])]
            qs+=aid_qs(form,d,[("h","How do the aids help?",[(v,t.replace("them",P["obj"]).replace("their own",P["poss"]+" own")) for v,t in AID_H_AA]),("d","Any problems using them?",AID_D_AA)])
            if "Wheelchair" in aids(d) and "indoors" in {r[0] for r in bad_rows(form,d)}:   # aids are tapped after the 'often' part, so this is asked here
                qs.append(Q("wchair","Getting in or out of the wheelchair","radio",[("diff","Has difficulty"),("help","Needs help")]))
        else:
            qs+=aid_qs(form,d,[("h",f"What help {P['do']} need with them?",AID_H_DLA)])
        ev=[("abroad","Been abroad for more than 4 weeks in the last 3 years"),("eeaben","Gets a pension or benefit from an EU/EEA country or Switzerland"),("eeawork","Works in or pays insurance to an EU/EEA country or Switzerland"),("scot","Moved here from Scotland"),("notgb","Doesn't normally live in "+("England or Wales" if form=="dla" else "Great Britain"))]
        ev+= [("padp","Gets or has claimed Pension Age Disability Payment"),("warcaa","Gets War Pension Constant Attendance Allowance"),("iicaa","Gets Industrial Injuries Constant Attendance Allowance")] if form=="aa" else [("cdp","Gets or has claimed Child Disability Payment"),("newuk","Came to live in the UK in the last 3 years")]
        ev+= [("sr",f"{cap(P['have'])} been told {P['subj']} may have 12 months or less to live")]
        qs.append(Q("checks",f"Do any of these apply to {P['obj']}{(' or '+P['poss']+' partner') if form=='aa' else ' or you'}? Tap any, or None of these.","checks",ev+[("none","None of these")],hint="Most people tap None of these."))
        qs+=rep("ab",1 if form=="aa" else 5,("checks","abroad"),lambda i,dp:[Q(f"ab{i}_left",f"Date {P['subj']} left","date",dep=dp),Q(f"ab{i}_back",f"Date {P['subj']} came back","date",dep=dp),
              Q(f"ab{i}_where",f"Where did {P['subj']} go?","text",maxlen=60,dep=dp),Q(f"ab{i}_why","Why?","radio",[("Holiday","Holiday"),("Visiting family","Visiting family"),("Medical treatment","Medical treatment"),("Work","Work")],dep=dp)],"Another trip?")
        qs+= [Q("scot_date",f"Date {P['subj']} moved from Scotland","date",dep=("checks",["scot"]))]
        if form=="dla": qs+= [Q("uk_date",f"Date {P['subj']} came to live in the UK","date",dep=("checks",["newuk"])),Q("uk_passport","Passport number (optional)","text",maxlen=20,dep=("checks",["newuk"]))]
        hq="Is "+("you" if me(d,form) else nm(d,form))+" in hospital, a care home or a hospice now?" if form=="aa" else "Is your child in hospital now?"
        qs+= [Q("hosp",("Are you" if me(d,form) else f"Is {nm(d,form)}")+" in hospital, a care home or similar now?" if form=="aa" else hq,"radio",([("no","No"),("hosp","In hospital"),("care","In a care home or hospice")] if form=="aa" else [("no","No"),("hosp","Yes")])),
              Q("h_in",f"Date {P['subj']} went in","date",dep=("hosp",["hosp","care"])),Q("h_place","Name of the hospital or home","text",maxlen=80,dep=("hosp",["hosp","care"])),
              Q("h_pc","Its postcode","pc",maxlen=9,dep=("hosp",["hosp","care"])),Q("h_town","Its town","text",maxlen=40,dep=("hosp",["hosp","care"])),
              Q("h_why",f"Why did {P['subj']} go in?","text",maxlen=100,dep=("hosp",["hosp"]))]+([Q("h_tel","Hospital phone (optional)","tel",maxlen=20,dep=("hosp",["hosp"]))] if form=="dla" else [])
        if form=="aa":
            qs+= [Q("h_pays","Does a council, NHS or government department pay towards the stay?","radio",YNS,dep=("hosp",["hosp","care"])),Q("h_payer","Which one?","text",maxlen=60,dep=("h_pays",["yes"])),
                  Q("out6",f"{cap(P['have'])} come out of hospital or a care home in the last 6 weeks?","radio",YN),
                  Q("o_in",f"Date {P['subj']} went in","date",dep=("out6",["yes"])),Q("o_out",f"Date {P['subj']} came out","date",dep=("out6",["yes"])),Q("o_place","Name of the place","text",maxlen=80,dep=("out6",["yes"])),
                  Q("o_pc","Its postcode","pc",maxlen=9,dep=("out6",["yes"])),Q("o_town","Its town","text",maxlen=40,dep=("out6",["yes"])),Q("o_why",f"Why did {P['subj']} go in?","text",maxlen=100,dep=("out6",["yes"]))]
        else:
            qs+= [Q("h_nhs","Is the NHS paying for the stay?","radio",YNS,dep=("hosp",["hosp"])),
                  Q("stays",f"In the last year, {P['have']} stayed in a hospice, respite or residential home?","radio",YN),
                  Q("s_in",f"Date {P['subj']} went in","date",dep=("stays",["yes"])),Q("s_out",f"Date {P['subj']} came out","date",dep=("stays",["yes"])),Q("s_place","Name of the place","text",maxlen=80,dep=("stays",["yes"])),
                  Q("s_pc","Its postcode","pc",maxlen=9,dep=("stays",["yes"])),Q("s_town","Its town","text",maxlen=40,dep=("stays",["yes"])),Q("s_tel","Its phone (optional)","tel",maxlen=20,dep=("stays",["yes"])),Q("s_pays","Who paid towards it?","radio",[("la","Local authority"),("ha","Health authority"),("gov","Government department"),("nhs","NHS"),("none","None of these")],dep=("stays",["yes"])),
                  Q("s_payer","Name of the authority (optional)","text",maxlen=60,dep=("s_pays",["la","ha","gov"]))]
        qs+= [Q("stmt",f"Who could write a short statement about {P['obj']} for the form?","radio",[("family","A family member"),("friend","A friend"),("carer","A carer"),("prof","A professional"),("noone","No one")],hint="They write it themselves on the form. We'll print a note for them."),
              Q("stmt_name","Their name (optional)","text",maxlen=60,dep=("stmt",["family","friend","carer","prof"])),
              Q("asked","When did you ask DWP for this form?","date",hint="The date on DWP's letter, if they sent one. Skip if you printed it yourself.")]
    elif sec=="often": qs+=often_qs(form,d)
    return qs
def often_qs(form,d):
    w=d.get("wf") or {}; you=_you(d,form); qs=[]; R=d.get("rows") or {}; bad={r[0] for r in bad_rows(form,d)}; P=PR(d,form); DO=cap(P['do'])
    if form=="aa":
        prt=[]
        for rid,subs in AA_SUB.items():
            if rid not in bad: continue
            v=R[rid]; c=set(v.get("c") or []); lab=dict((r[0],r[2]) for r in I.AA_ROWS)[rid]
            opts=[(k,l) for k,l,_,_ in subs]; pre=[k for k,l,chips,_ in subs if c & {x for x in chips if x}]
            qs.append(Q(f"sub_{rid}",f"{lab}: which parts? (tap all)","checks",opts,pre=pre))
            qs+=times_qs(rid,lab,subs)
            if "prompt" not in c: prt.append((rid,lab))
        if prt: qs.append(Q("pr_tasks",f"{DO} also need reminding or encouraging with any of these? (tap any)","checks",prt+[("none","None of these")]))
        if "bed" in bad: qs.append(Q("bed_enc",f"{DO} need encouraging to get up or go to bed?","checks",[("up","To get up"),("down","To go to bed")]))
        if "indoors" in bad: qs.append(Q("pr_indoors",f"{DO} need encouraging to move about?","radio",YN))
        if "comm" in bad: qs.append(Q("comm2","Communicating: is any of this also hard? (tap any)","checks",[("und",f"Being understood by people {P['subj']} {P['dont']} know"),("ask","Asking for help when needed")]))
        if "social" in bad:
            qs.append(Q("acts",f"Which activities {P['do']} need help to do? (up to 6)","checks",ACTS_AA))
            qs+=act_qs(ACTS_AA,[("ah","what help?",ACT_HELP),("ao","how often?",ACT_OFTEN)])
        if d.get("falls") in ("1-2","3-5","6+"): qs+= [Q("falls_m","Falls in the last month","radio",[("0","None"),("1","1"),("2","2"),("3+","3 or more")],cls=" nums"),Q("fall_what",f"What usually happens when {P['subj']} {P['s']('fall')}?","radio",[("legs","Legs give way"),("trip","Trips"),("dizzy","Dizzy or blacks out"),("balance","Loses balance")])]
        qs+= [Q("stum_m",f"Stumbles or near-falls in the last month","radio",[("0","None"),("1-2","1–2"),("3-5","3–5"),("6+","6 or more")],cls=" nums"),
              Q("stum_y","And in the last year","radio",[("0","None"),("1-5","1–5"),("6-20","6–20"),("20+","More than 20")],cls=" nums"),
              Q("stum_last","Last stumble","radio",[("week","This week"),("month","This month"),("months","1–6 months ago"),("year","Over 6 months ago")],dep=("stum_m",["1-2","3-5","6+"]))]
        if d.get("eye") or d.get("alone") in ("lt1","never","hours"):
            qs+= [Q("eye2",f"Why does someone need to keep an eye on {P['obj']}? (tap any)","checks",[("prevent",f"Could put {P['refl']} or others in danger"),("neglect",f"May neglect {P['refl']}"),("harm",f"May harm {P['refl']}"),("aggr","Can be aggressive or antisocial"),("voices","Hear voices or have disturbing thoughts")]),
                  Q("eye_days",f"Days a week someone needs to keep an eye on {P['obj']}","radio",I.DAYS[:7],cls=" nums")]
        if d.get("watch") in ("some","most"):
            qs+= [Q("w_times",f"Times a night someone has to be awake to watch over {P['obj']}","radio",[("1","1"),("2","2"),("3","3"),("4+","4 or more")],cls=" nums"),
                  Q("w_long","How long each time?","radio",[("10 minutes","10 min"),("20 minutes","20 min"),("30 minutes","30 min"),("an hour","1 hour"),("over an hour","Over an hour")]),
                  Q("w_nights","Nights a week someone stays awake for this","radio",I.DAYS[:7],cls=" nums")]
        if "toilet" in (d.get("night") or []) and "acc" in set((R.get("toilet") or {}).get("c") or []): qs.append(Q("n_incont","At night, is it also incontinence (accidents or pads)?","radio",YN))
        if "meds" in (d.get("night") or []): qs.append(Q("n_treat","At night, is it also treatment or therapy (e.g. oxygen, creams)?","radio",YN))
        if d.get("night") and ("prompt" in set((R.get("toilet") or {}).get("c") or []) or "confused" in (d.get("night") or [])): qs.append(Q("n_prompt",f"At night, {P['do']} need reminding or encouraging? (tap any)","checks",[("toilet","To use the toilet"),("meds","To take medicines")]))
    else:
        for rid,subs in DLA_SUB.items():
            if rid!="bed" and rid not in bad: continue
            if rid=="bed":
                qs.append(Q("bed",f"During the day, {P['do']} need help or encouraging to get in or out of bed, or settle?","radio",YN)); dp=("bed",["yes"])
            else: dp=None
            c=set((R.get(rid) or {}).get("c") or []); pre=[k for k,*_ in subs if k in {x for kk in c for x in DLA_PRE.get(rid,{}).get(kk,[])}]
            lab={"bed":"Bed","wash":"Washing","dress":"Dressing","eat":"Eating and drinking","meds":"Medicines and therapy"}[rid]
            qs.append(Q(f"sub_{rid}",f"{lab}: which parts need help? (tap all)","checks",[(k,l) for k,l,_,_ in subs],dep=dp,pre=pre))
            qs+=times_qs(rid,lab,subs,dp)
            qs.append(Q(f"m_{rid}",f"{lab}: minutes each time, roughly","radio",MINS,cls=" nums",dep=dp))
        if "toilet" in bad: qs.append(Q("toilet2","Toilet: which parts need help? (tap all)","checks",[(k,l) for k,l in DLA_TOILET if k not in [DLA_TOILET_PRE[c] for c in (R["toilet"].get("c") or []) if c in DLA_TOILET_PRE]]))
        if "indoors" in bad: qs.append(Q("indoors2","Moving about indoors: which parts need help? (tap all)","checks",[(k,l) for k,l in DLA_INDOORS if k not in [x for c in (R["indoors"].get("c") or []) for x in DLA_INDOORS_PRE.get(c,[])]]))
        G=lambda id,label,rows:Q(id,label+" (tap any that apply)","tap",rows=rows,hint="Anything you leave untapped goes on the form as not a problem.")
        if "see" in bad: qs+= [Q("sight_cert",f"{cap(P['be'])} certified as","radio",[("severe","Severely sight impaired"),("si","Sight impaired"),("neither","Neither")]),G("see_g","Even with glasses",[("61_2","Can't see keyboard keys or large print","can"),("61_3","Can't see a TV well enough to follow a story","can"),("61_4","Can't see the shape of furniture","can"),("61_5","Can't recognise a face across a room","can"),("61_6","Can't recognise someone across a street","can")])]
        if "hear" in bad: qs.append(G("hear_g","Hearing",[("62_1","Had a hearing test in the last 6 months","need"),("62_2","Can't hear a whisper in a quiet room","can"),("62_3","Can't hear a normal voice in a quiet room","can"),("62_4","Can't hear a loud voice in a quiet room","can"),("62_5","Can only hear the TV at very loud volume","need"),("62_6","Can't hear a school bell or car horn","can")]))
        if "speak" in bad: qs.append(G("speak_g","Speaking",[("63_1","Can't speak clearly in sentences","can"),("63_2","Can't put words together in simple sentences","can"),("63_3","Can't say single words","can"),("63_4","Can't talk with someone they know","can"),("63_5","Can't talk with someone they don't know","can")]))
        if "comm" in bad: qs+= [Q("comm_how",f"How {P['do']} communicate? (tap any)","checks",[("64_1","Writing"),("64_1_2","BSL"),("64_1_3","Lip reading"),("64_1_4","Gestures and body language"),("64_1_5","Makaton"),("64_1_6","Signed Supported English"),("64_1_7","Signed English"),("64_1_8","Finger spelling"),("64_1_9","PECS (pictures)"),("64_1_10","Tadoma")]),
                                G("comm_g","Communicating",[("64_3","Can't communicate with someone they know","can"),("64_4","Can't communicate with someone they don't know","can")])]
        if d.get("fits") in ("month","week","day"):
            Y3=[("yes","Yes"),("no","No"),("some","Sometimes")]
            qs+= [Q("fit_type","What type?","checks",[("tonic-clonic seizures","Tonic-clonic"),("absence seizures","Absences"),("focal seizures","Focal"),("blackouts","Blackouts"),("drop attacks","Drop attacks")]),
                  Q("fit_warn","Any warning before one?","radio",Y3),Q("fit_tell",f"Can {P['subj']} spot a warning and tell an adult?","radio",Y3),Q("fit_act",f"Can {P['subj']} spot a warning and get safe?","radio",Y3),
                  G("fit_g","Fits",[("65_5","Seriously injured by a fit in the last 6 months","need"),("65_6","At risk of harm after a fit","need"),("65_11","Status epilepticus in the last 12 months","need")]),
                  Q("fit_days","Days a month with fits","radio",[("1","1"),("2-4","2–4"),("5-10","5–10"),("11-20","11–20"),("20+","Over 20")],cls=" nums"),Q("fit_per","Fits on those days","radio",[("1","1"),("2","2"),("3-5","3–5"),("6+","6 or more")],cls=" nums"),
                  Q("fit_nights","Nights a month with fits","radio",[("0","None"),("1","1"),("2-4","2–4"),("5-10","5–10"),("10+","Over 10")],cls=" nums"),Q("fit_nper","Fits on those nights","radio",[("1","1"),("2","2"),("3+","3 or more")],cls=" nums",dep=("fit_nights",["1","2-4","5-10","10+"]))]
        if "superv" in bad:
            known={f for c in (R["superv"].get("c") or []) for cid,_,tk,_ in I.DLA_ROWS[10][4] if cid==c for f,_ in tk}
            rows=[(f,l,pl) for f,l,pl in [("66_1","Don't recognise or react to common dangers","can"),("66_2","Can't cope with planned changes to routine","can"),("66_3","Can't cope with unplanned changes","can"),("66_4","Often feel anxious or panic","need"),("66_5","Often get upset or frustrated","need"),("66_6","Often harm themselves or others","need"),("66_7","Often feel someone may harm them","need"),("66_8","Often become verbally abusive or distressed in a way that could cause harm","need"),("66_9","Often act impulsively","need"),("66_10","Often become overwhelmed","need")] if f not in known]
            if rows: qs.append(G("superv_g","Keeping safe",rows))
        if "dev" in bad: qs.append(G("dev_g","They need help to",[(f,l,"need") for f,l in [("67_1","Understand the world around them"),("67_2","Recognise their surroundings"),("67_3","Follow instructions"),("67_4","Play with others"),("67_5","Play on their own"),("67_6","Join in activities with others"),("67_7","Behave appropriately"),("67_8","Understand and respond to other people's behaviour")]]))
        if "notatschool" not in (d.get("school") or []):
            qs.append(G("school_g","At school or nursery, they need help to",[(f,l,"need") for f,l in [("68_1","Go to and use the toilet"),("68_2","Move safely between lessons"),("68_3","Change for PE"),("68_4","Eat meals"),("68_5","Take medicine or manage therapy"),("68_6","Communicate")]]))
        if d.get("age")!="u3" and "walk" in bad:
            qs+= [Q("canwalk",f"Can {P['subj']} physically walk?","radio",YN),
                  Q("dist",f"How far can {P['subj']} walk before needing to stop?","radio",[("200+","Over 200 metres"),("51-200","51 to 200 metres"),("50","50 metres or less"),("few","A few steps")],dep=("canwalk",["yes"])),
                  Q("wtime","How long does that take?","radio",[("5+","Over 5 minutes"),("3-4","3 to 4 minutes"),("1-2","1 to 2 minutes"),("lt1","Under a minute")],dep=("canwalk",["yes"])),
                  Q("speed","Walking speed compared with other children","radio",[("normal","Normal"),("slow","Slow (twice as long)"),("vslow","Very slow (can't keep up)")],dep=("canwalk",["yes"])),
                  Q("walk_other","Any other problems during or after walking, like pain, breathlessness or exhaustion?","radio",YN),
                  Q("gait",f"The way {P['subj']} {P['s']('walk')}","radio",[("normal","Normally"),("limp","With a limp"),("shuffle","Shuffle"),("drag","Drag a leg"),("in","Feet turned in"),("toes","On their toes"),("balance","Poor balance"),("unable","Times they can't walk"),("refuse","Refuse or get distressed")],dep=("canwalk",["yes"]))]
        if d.get("age")!="u3" and "out" in bad:
            c=set(R["out"].get("c") or []); known={f for cid,_,tk,_ in I.DLA_MOB[1][4] if cid in c for f,_ in tk}
            rows=[(f,l,pl) for f,l,pl in [("49_1","Can't find their way around places they know","can"),("49_2","Can't ask for and follow directions","can"),("49_3","Can't walk safely next to a busy road","can"),("49_4","Can't cross a road safely","can"),("49_5","Don't understand common dangers outdoors","can"),("49_6","Often get anxious, distressed or disorientated outside","need"),("49_7","Often behave unpredictably outside","need"),("49_8","Often need physical restraint","need")] if f not in known]
            if rows: qs.append(G("out_g","Outdoors",rows))
            if "falls" in c: qs+= [Q("falls_m","Falls a month","radio",[("1","1"),("2-4","2–4"),("5-10","5–10"),("10+","Over 10")],cls=" nums"),G("falls_g","After a fall",[("50_2","Can't get up without help","can"),("50_3","Injuries that needed hospital treatment","need")])]
        qs.append(Q("hobby",f"{DO} need help to join in hobbies, clubs or activities?","radio",YN))
        qs.append(Q("acts","Which ones? (tap up to 6)","checks",ACTS_DLA,dep=("hobby",["yes"])))
        qs+=act_qs(ACTS_DLA,[("ah","what help?",ACT_HELP),("ao","how often?",ACT_OFTEN),("al","how long each time?",ACT_LONG)])
    return qs
def times_qs(rid,lab,subs,dp=None):
    """One 'times a day' for the whole task; each part only if the customer says it differs."""
    qs=[Q(f"t_{rid}",f"{lab}: times a day"+(" (for each part)" if len(subs)>1 else ""),"radio",TIMESD,cls=" nums",dep=dp)]
    if len(subs)>1:
        qs.append(Q(f"t_{rid}_diff","Different for some parts?","checks",[("1","Yes, set each part")],other=False,dep=dp))
        for k,l,*_ in subs: qs.append(Q(f"t_{rid}_{k}",f"{l}: times a day","radio",TIMESD,cls=" nums",dep=[(f"t_{rid}_diff",["1"]),(f"sub_{rid}",[k])]))
    return qs
def act_qs(ACTS,parts):
    dp=("acts",[k for k,_ in ACTS]); qs=[Q(f"{p}_all",f"For these activities: {l}","radio",O,dep=dp) for p,l,O in parts]
    qs.append(Q("a_diff","Different for some activities?","checks",[("1","Yes, set each one")],other=False,dep=dp))
    for k,al in ACTS: qs+=[Q(f"{p}_{k}",f"{al}: {l}","radio",O,dep=[("a_diff",["1"]),("acts",[k])]) for p,l,O in parts]
    return qs
AID_H_AA=[("safer","Keeps them safer"),("indep","Can do more on their own"),("pain","Less pain"),("atall","Couldn't manage without it")]
AID_D_AA=[("none","No problems"),("help","Needs help to use it"),("still","Still struggles with it"),("pain","Painful or tiring to use")]
AID_H_DLA=[("none","None"),("puton","Someone puts it on or sets it up"),("watch","Needs watching while using it"),("remind","Needs reminding to use it")]
def aid_qs(form,d,parts):
    A=aids(d); qs=[]
    if not A: return qs
    qs.append(Q("aid_p","Which were given or recommended by a doctor, nurse or occupational therapist? (tap any)","checks",[(str(i),a) for i,a in enumerate(A)]+([("all","All of them")] if len(A)>1 else [])+[("none","None of them")]))
    for k,label,O in parts:
        if len(A)==1:
            one={"How do the aids help?":"how does it help?","Any problems using them?":"any problems using it?"}.get(label) or (label[0].lower()+label[1:]).replace(" with them?"," with it?")
            qs.append(Q(f"aid_{k}",f"{A[0]}: {one}","radio",O)); continue
        qs+= [Q(f"aid_{k}",label,"radio",O,hint="For all of them."),Q(f"aid_{k}_diff","Different for some aids?","checks",[("1","Yes, set each one")],other=False)]
        qs+= [Q(f"aid_{k}_{i}",a,"radio",O,dep=(f"aid_{k}_diff",["1"])) for i,a in enumerate(A)]
    return qs
def _copy(w,src,dst):
    """Use the 'for all' answer for one item unless the customer set that item separately."""
    if not (w.get(dst) or w.get(dst+"_x")) and (w.get(src) or w.get(src+"_x")): w[dst]=w.get(src,""); w[dst+"_x"]=w.get(src+"_x","")
def normalise(form,sec,d):
    w=W(d)
    if sec=="often":
        for rid,subs in (AA_SUB if form=="aa" else DLA_SUB).items():
            for k,*_ in subs:
                if k in (w.get(f"sub_{rid}") or []): _copy(w,f"t_{rid}",f"t_{rid}_{k}")
        sel=w.get("pr_tasks") or []
        if sel:
            for rid in AA_SUB: w[f"pr_{rid}"]="yes" if rid in sel else "no"
        for k in w.get("acts") or []:
            for p in ("ah","ao","al"): _copy(w,f"{p}_all",f"{p}_{k}")
    if sec=="home":
        sel=w.get("aid_p") or []
        for i,_ in enumerate(aids(d)):
            if sel: w[f"aid_p_{i}"]="yes" if (str(i) in sel or "all" in sel) else "no"
            else: w.pop(f"aid_p_{i}",None)
            for k in ("h","d"): _copy(w,f"aid_{k}",f"aid_{k}_{i}")
def rep(pre,n,base,make,more_label):
    """Up to n repeats of a group: the first shows when base is answered yes, each next one after 'Another?' Yes."""
    out=[]; dp=(base,["yes"]) if isinstance(base,str) else (base[0],[base[1]])
    for i in range(1,n+1):
        out+=make(i,dp)
        if i<n: out.append(Q(f"{pre}_more{i}",more_label,"radio",YN,dep=dp,other=False)); dp=(f"{pre}_more{i}",["yes"])
    return out
def is_wf_section(sec): return sec in {"you","child","helper","parent","health","home","often","more"}
def section_body(form,sec,d):
    w=W(d); pre=prefill(form,d)
    for k,v in pre.items(): w.setdefault(k,v)
    hs=[]
    for q in questions(form,sec,d):
        if q["id"].endswith("_diff") and hs:   # 30 Oct: 'Different for some parts?' rides on the question above (one screen, not two)
            inner=I._checks(q["id"],q["opts"],w.get(q["id"]) if isinstance(w.get(q["id"]),list) else [],None)
            k=hs[-1].rfind("</fieldset>"); hs[-1]=hs[-1][:k]+f'<div class=diffopt>{inner}</div>'+hs[-1][k:]; continue
        hs.append(render_q(q,w))
    return "".join(hs)+DEP_JS
def save(form,sec,d,fm):
    w=W(d); qs=questions(form,sec,d)
    for q in qs: save_q(q,fm,w)
    for q in qs:
        if not dep_ok(q,w):
            w.pop(q["id"],None); w.pop(q["id"]+"_x",None)
            for r in (q["rows"] if q["kind"]=="tap" else []): w.pop(r[0],None)
    if sec=="home" and "none" in (w.get("checks") or []): w["checks"]=["none"]
    if sec=="more": import followups; followups.absorb(form,d); return d
    normalise(form,sec,d)
    if sec in ("you","child") and w.get("pc"): pc_meta(w,"pc")
    if sec=="you" or sec=="parent" or sec=="child" or sec=="health":
        if sec=="health" and w.get("gp_list") and w.get("gp_x"): w["gp_name"]=w["gp_x"]   # 'Something else' text is the surgery name
        if sec=="health" and w.get("gp") and not w.get("gp_x"): gp_detail(w)
    if sec in ("you","child","parent") and w.get("pc") and not w.get("gp_list"): gp_options(w)
    return d
def prefill(form,d):
    p={}; n=(d.get("name") or "").strip()
    if n and (form=="dla" or not me(d,form)) and n.lower() not in ("mum","dad","mom","mam","nan","gran","nana","grandma","grandad"): p["first"]=n
    return p
DEP_JS="""<script>(function(){function upd(){document.querySelectorAll('[data-dep]').forEach(function(e){var n=e.getAttribute('data-dep'),v=e.getAttribute('data-vals').split(' '),on=false;document.querySelectorAll('[name="'+n+'"]').forEach(function(i){if(i.checked&&v.indexOf(i.value)>=0)on=true});e.hidden=!on})}
document.addEventListener('change',upd);upd();
document.querySelectorAll('.usepre').forEach(function(b){b.addEventListener('click',function(){var n=b.getAttribute('data-for');b.getAttribute('data-vals').split(' ').forEach(function(v){var i=document.querySelector('[name="'+n+'"][value="'+v+'"]');if(i&&!i.checked){i.checked=true;i.dispatchEvent(new Event('change',{bubbles:true}))}});b.parentNode.hidden=true})});
document.querySelectorAll('.pcfind').forEach(function(b){var i=document.getElementById('w_'+b.getAttribute('data-for')),last='';if(i)i.addEventListener('input',function(){var v=i.value.replace(/\\s+/g,'').toUpperCase();if(v!=last&&/^[A-Z]{1,2}[0-9][A-Z0-9]?[0-9][A-Z]{2}$/.test(v)){last=v;b.click()}})});
document.querySelectorAll('.pcfind').forEach(function(b){b.addEventListener('click',function(){var f=b.getAttribute('data-for'),i=document.getElementById('w_'+f),o=document.getElementById('pc_'+f);if(!i.value)return;o.textContent='Looking up…';
fetch('/api/lookup/postcode?pc='+encodeURIComponent(i.value)).then(function(r){return r.json()}).then(function(j){if(!j.ok){o.textContent="We couldn't find that postcode. Type the address below.";return}i.value=j.postcode;o.textContent=j.town+(j.country?', '+j.country:'');
var t=document.querySelector('[name="'+(f=='pc'?'town':f.replace(/pc$/,'town'))+'"]');if(t&&!t.value)t.value=j.town}).catch(function(){o.textContent='Type the address below.'})})})})();</script>"""
# ---------- free lookups (no signup): postcodes.io and NHS ODS. Never fatal: typed fields always work ----------
import urllib.request, urllib.parse
def _get(url,t=4):
    import os
    if os.getenv("WF_LOOKUPS","1")=="0": return None   # tests: typed fields only
    try:
        with urllib.request.urlopen(urllib.request.Request(url,headers={"Accept":"application/json","User-Agent":"FormSorted/1.0"}),timeout=t) as r: return json.loads(r.read().decode())
    except Exception: return None
_PC={}
def postcode(pc):
    pc=re.sub(r"\s+","",(pc or "").upper())
    if not re.fullmatch(r"[A-Z]{1,2}\d[A-Z\d]?\d[A-Z]{2}",pc): return None
    if pc in _PC: return _PC[pc]
    j=_get("https://api.postcodes.io/postcodes/"+urllib.parse.quote(pc))
    r=(j or {}).get("result")
    out={"postcode":r["postcode"],"town":r.get("admin_district") or r.get("parish") or "","country":r.get("country") or ""} if r else None
    if out: _PC[pc]=out
    return out
def pc_meta(w,k):
    m=postcode(w.get(k))
    if m:
        w[k]=m["postcode"]; w[k+"_country"]=m["country"]
        tk={"pc":"town"}.get(k,k[:-2]+"town")
        if not w.get(tk): w[tk]=m["town"].title() if m["town"].isupper() else m["town"]
ODS="https://directory.spineservices.nhs.uk/ORD/2-0-0/organisations"
def gp_options(w):
    pc=(w.get("pc") or "").split(" ")[0]
    if not pc: return
    j=_get(ODS+"?"+urllib.parse.urlencode({"PrimaryRoleId":"RO177","NonPrimaryRoleId":"RO76","PostCode":pc,"Status":"Active","Limit":"12"}))
    lst=[{"id":o["OrgId"],"label":f'{o["Name"].title()}, {o.get("PostCode","")}'} for o in (j or {}).get("Organisations") or [] if o.get("OrgId")]
    if lst: w["gp_list"]=lst
def gp_detail(w):
    j=_get(ODS+"/"+urllib.parse.quote(w["gp"]))
    o=(j or {}).get("Organisation")
    if not o: return
    loc=(o.get("GeoLoc") or {}).get("Location") or {}
    tel=next((c.get("value") for c in ((o.get("Contacts") or {}).get("Contact") or []) if c.get("type")=="tel"),"")
    w.update({"gp_name":o.get("Name","").title(),"gp_addr":(loc.get("AddrLn1") or "").title(),"gp_addr2":(loc.get("AddrLn2") or "").title(),"gp_town":(loc.get("Town") or "").title(),"gp_pc":loc.get("PostCode",""),"gp_tel":w.get("gp_tel") or tel})
# ---------- personal details (non-sensitive) for the existing PERSONAL_FIELDS / DLA_PERSONAL mapping ----------
def personal(form,d):
    w=d.get("wf") or {}; p={}
    put=lambda k,v: p.__setitem__(k,v) if v else None
    if form=="aa": put("title",w.get("title") or w.get("title_x"))
    put("other_names",w.get("first")); put("surname",w.get("surname")); put("dob",w.get("dob"))
    put("addr1",w.get("addr1")); put("addr2",w.get("addr2")); put("addr3",w.get("town")); put("postcode",w.get("pc"))
    if form=="aa": put("phone",w.get("phone"))
    else:
        put("parent_title",w.get("p_title") or w.get("p_title_x")); put("parent_other_names",w.get("p_first")); put("parent_surname",w.get("p_surname"))
        put("phone",w.get("p_phone")); put("email",w.get("p_email")); put("parent_dob",w.get("p_dob"))
        if d.get("rel") and d["rel"]!="Other": put("relationship",d["rel"])
    if w.get("gp_name"):
        put("gp_name",(w.get("gp_doc")+", " if w.get("gp_doc") else "")+w["gp_name"]); put("gp_addr1",w.get("gp_addr")); put("gp_postcode",w.get("gp_pc")); put("gp_phone",w.get("gp_tel"))
    return p
# ---------- answers -> PDF boxes and tick boxes ----------
def ukd(s):
    m=re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})",s or "")
    if m: return f"{m[3]}/{m[2]}/{m[1]}"
    m=re.fullmatch(r"(\d{4})-(\d{2})",s or "")
    if m: return datetime.date(int(m[1]),int(m[2]),1).strftime("%B %Y")
    return s or ""
def seen_txt(v,x=""):
    if x: return x
    t=datetime.date.today()
    def ago(mo): y,m=divmod(t.year*12+t.month-1-mo,12); return datetime.date(y,m+1,1).strftime("%B %Y")
    return {"month":f"Within the last month ({ago(0)})","1to3":f"About {ago(2)} (1 to 3 months ago)","3to6":f"About {ago(4)} (3 to 6 months ago)",
            "6to12":f"About {ago(9)} (6 to 12 months ago)","over":"Over a year ago"}.get(v,"")
def lab(opts,v,x=""):
    if x: return x
    return dict(opts).get(v,"") if v not in ("","ns",None) else ""
_OPTS={}
def st(form,field,want):
    """The PDF's real on-state for a box, matched by its start (some states carry odd characters)."""
    import ticks as T
    if form not in _OPTS: _OPTS[form]=T.options(form)
    o=_OPTS[form].get(field)
    if not o: return None
    w=want.lower().replace(" ","")
    for s in o[1]:
        if s.lower().replace(" ","").startswith(w): return s
    return None
def yn(v): return {"yes":"/Yes","no":"/No","ns":"/Do not know"}.get(v)
def pdf_values(form,d,uploads=None):
    """(values, ticks, notes) from the whole-form answers. notes: 'Something else' texts with no box of their own."""
    w=d.get("wf") or {}; V={}; T={}; notes=[]
    def v(f,x):
        if x not in (None,"") and f: V[f]=str(x)
    def t(f,want):
        if not f or not want: return
        s=st(form,f,want)
        if s: T[f]=s
    def other(label,k):
        if w.get(k+"_x"): notes.append(f"{label}: {w[k+'_x']}")
    chk=set(w.get("checks") or []); answered=bool(chk)
    ev=[x for x in (d.get("evidence") or []) if x not in ("none","nothing")]
    ups=[u.get("name") for u in (uploads if uploads is not None else d.get("uploads") or [])]
    def addr(lines,parts):
        parts=[p for p in parts if p]
        for f,p in zip(lines,parts): v(f,p)
    me_=me(d,form)
    if form=="aa":
        if answered: t("01_03" if "sr" in chk else "01_04","/Yes" if "sr" in chk else "/No")
        t("01-04",{"female":"/Female","male":"/Male"}.get(w.get("sex"))); other("Sex",'sex')
        v("7",w.get("nat_c") if w.get("nat")=="EEA" else (w.get("nat") or w.get("nat_x")))
        if w.get("nat")=="EEA": t("x7",yn(w.get("eea_before"))); other("Living in the UK before 2021","eea_before")
        v("01-06ii",w.get("mobile"))
        if answered:
            t("x8","/No" if "notgb" in chk else "/Yes"); t("x9","/Yes" if "abroad" in chk else "/No")
            t("x10","/Yes" if "eeaben" in chk else "/No"); t("x11","/Yes" if "eeawork" in chk else "/No")
            t("x14","/Yes") if "scot" in chk else t("x24","/No"); t("x16","/Yes") if "padp" in chk else t("x19","/No")
            if "warcaa" in chk: t("333","/Yes")
            if "iicaa" in chk: t("334","/Yes")
        if w.get("welsh")=="yes": t("x8_1","/Yes")
        if "abroad" in chk: v("9_1",ukd(w.get("ab1_left"))); v("9_2",ukd(w.get("ab1_back"))); v("9_3",w.get("ab1_where")); v("9_4",lab([],w.get("ab1_why"),w.get("ab1_why_x")) or w.get("ab1_why"))
        if "scot" in chk: v("13_2",ukd(w.get("scot_date")))
        other("Also applies","checks")
        # Q15 signing for someone
        sg=d.get("signer")
        if me_ or sg=="them": t("x15","/No")
        elif sg in ("poa","appointee","deputy"):
            t("x15","/Yes"); t("x15_1",{"poa":"/I hold Power","deputy":"/I am a Deputy","appointee":"/I am a Corporate" if w.get("h_org") else "/I am an appointee"}[sg])
            if sg=="poa": t("x15_1a",yn(w.get("h_online")))
            v("15_2",w.get("h_org")); v("15_3",w.get("h_name")); v("15_5",ukd(w.get("h_dob"))); v("15_10",w.get("h_phone"))
            if w.get("h_same")=="yes": addr(["15_6","15_7","15_8"],[w.get("addr1"),w.get("addr2"),w.get("town")]); v("15_9",w.get("pc"))
            else: addr(["15_6","15_7","15_8"],[w.get("h_addr1"),w.get("h_town")]); v("15_9",w.get("h_pc"))
        # Q16 conditions: medicines and how often (names and start years come from the conditions section)
        from questions import CONDITION_FIELDS as CF
        for i,c in enumerate(conds(d)):
            if i<len(CF): v(CF[i][2],w.get(f"med_{i}") or None); v(CF[i][3],lab(DOSE,w.get(f"dose_{i}"),w.get(f"dose_{i}_x")))
        if w.get("meds_how")=="photo" and conds(d): v(CF[0][2],"See the repeat prescription list sent with this form")
        other("Medicines","meds_how")
        # Q17 professional, Q18 helper, Q19 GP
        p=prof(form,d)
        if p:
            t("x17","/Yes"); v("17_1",w.get("pr_name") or f"My {p.lower()}"); v("17_2",p); addr(["17_3","17_4","17_5"],[w.get("pr_where"),w.get("pr_town")])
            v("17_6",w.get("pr_pc")); v("17_7",w.get("pr_tel")); v("17_8",w.get("pr_hosp")); v("17_9",lab([(x,x) for x in [c["name"] for c in conds(d)]],w.get("pr_cond"),w.get("pr_cond_x")))
            v("17_10",lab(HOWOFTEN,w.get("pr_often"),w.get("pr_often_x"))); v("17_11",seen_txt(w.get("pr_seen"),w.get("pr_seen_x")))
        elif w.get("pr_any"): t("x17",yn(w["pr_any"]))
        hp=w.get("hp_any")
        if hp in ("yes","me"):
            t("x18","/Yes")
            if hp=="me" and applies(form,"helper",d):
                v("18_1",w.get("h_name")); v("18_6",w.get("h_phone"))
                if w.get("h_same")=="yes": addr(["18_2","18_3","18_4"],[w.get("addr1"),w.get("addr2"),w.get("town")]); v("18_5",w.get("pc"))
                else: addr(["18_2","18_3","18_4"],[w.get("h_addr1"),w.get("h_town")]); v("18_5",w.get("h_pc"))
            else:
                v("18_1",w.get("hp_name")); addr(["18_2","18_3","18_4"],[w.get("hp_addr"),w.get("hp_town")]); v("18_5",w.get("hp_pc")); v("18_6",w.get("hp_tel"))
            what=[dict([("personal care","Washing and dressing"),("meals","Meals"),("medicines","Medicines"),("getting about","Getting about"),("keeping an eye","Keeping an eye on me")])[x] for x in w.get("hp_what") or []]+([w["hp_what_x"]] if w.get("hp_what_x") else [])
            v("18_7",", ".join(what)); v("18_8",w.get("hp_rel_x") or w.get("hp_rel")); v("18_9",w.get("hp_often_x") or w.get("hp_often"))
        elif hp=="no": t("x18","/No")
        if w.get("gp_name"):
            v("19-2",w.get("gp_addr2")); v("19-3",w.get("gp_town")); v("19-6",seen_txt(w.get("gp_seen"),w.get("gp_seen_x")))
        t("x20",yn(w.get("consent"))); other("Consent","consent")
        t("x21","/Yes" if (ups or ev) else "/No")
        if w.get("surg")=="yes":
            t("x22","/Yes")
            for i,(a,b,c) in enumerate([("22-1","22-2","22-3"),("22-4","22-5","22-6")],1):
                v(a,ukd(w.get(f"surg{i}_when"))); v(b,w.get(f"surg{i}_what")); v(c,ukd(w.get(f"surg{i}_date")) or ("Not known yet" if w.get(f"surg{i}_what") else ""))
        elif w.get("surg")=="no": t("x22","/No")
        if w.get("tests")=="yes":
            t("x23","/Yes")
            for i,(a,b) in enumerate([("23-1","23-2"),("23-3","23-4")],1):
                v(a,w.get(f"test{i}")); v(b,lab([("waiting","Waiting for results"),("see letter","See the enclosed letter")],w.get(f"test{i}r"),w.get(f"test{i}r_x")) if w.get(f"test{i}") else "")
        elif w.get("tests")=="no": t("x23","/No")
        acc=lab([("house","House"),("bungalow","Bungalow"),("flat","Flat"),("sheltered","Sheltered housing"),("care","Care home")],w.get("acc"),w.get("acc_x"))
        lw=lab([("alone","lives alone"),("partner","lives with partner"),("family","lives with family"),("carer","lives with a live-in carer")],w.get("liveswith"),w.get("liveswith_x"))
        v("24",". ".join(x[:1].upper()+x[1:] for x in (acc,lw) if x))
        ta=w.get("toiletat") or []
        if "up" in ta: t("x25","/Yes")
        if "down" in ta: t("x25-1","/Yes")
        if w.get("toiletat_x"): t("x25-2","/Yes"); v("25-3",w["toiletat_x"])
        sa=w.get("sleepat")
        if sa=="up": t("x26-1","/Yes")
        if sa=="down": t("x26-2","/Yes")
        if w.get("sleepat_x"): t("x26-3","/Yes"); v("26-4",w["sleepat_x"])
        for i,a in enumerate(aids(d)):
            base=4*i+1
            if w.get(f"aid_p_{i}")=="yes": t(f"27-{base+1}","/Yes")
            v(f"27-{base+2}",lab([("safer","Keeps me safer"),("indep","Lets me do more on my own"),("pain","Less pain"),("atall","Couldn't manage without it")],w.get(f"aid_h_{i}"),w.get(f"aid_h_{i}_x")))
            v(f"27-{base+3}",lab([("none","No problems using it"),("help","I need help to use it"),("still","I still struggle even with it"),("pain","Painful or tiring to use")],w.get(f"aid_d_{i}"),w.get(f"aid_d_{i}_x")))
        v("28",ukd(w.get("care_start")))
        if w.get("care_start"): t("363","/Yes")
        # how often each day
        R=d.get("rows") or {}
        for rid,subs in AA_SUB.items():
            r=R.get(rid)
            if not r or r.get("lvl")=="ok": continue
            sel=w.get(f"sub_{rid}") or []; pr=("prompt" in (r.get("c") or [])) or w.get(f"pr_{rid}")=="yes"
            for k,_,_,(diff,helpf,prf) in subs:
                n=lab(TIMESD,w.get(f"t_{rid}_{k}"),w.get(f"t_{rid}_{k}_x"))
                if k not in sel or not n: continue
                for f in diff: v(f,n)
                if r.get("help") or r.get("lvl") in ("help","cant"): v(helpf,n)
                if pr: v(prf,n)
        be=w.get("bed_enc") or []
        if "up" in be: t("x29-5","/Yes")
        if "down" in be: t("x29-6","/Yes")
        if w.get("wchair")=="diff": t("x33-4","/Yes")
        if w.get("wchair")=="help": t("x33-4","/Yes"); t("x33-8","/Yes")
        if w.get("pr_indoors")=="yes": t("x33-9","/Yes")
        c2=w.get("comm2") or []; ch=(R.get("comm") or {}).get("help")
        if "und" in c2: t("x37-2","/Yes"); ch and t("x37-8","/Yes")
        if "ask" in c2: t("x37-6","/Yes"); ch and t("x37-12","/Yes")
        if ch and "und" in ((R.get("comm") or {}).get("c") or []): t("x37-7","/Yes")
        home=[k for k in w.get("acts") or [] if k in ACT_HOME][:3]; out=[k for k in w.get("acts") or [] if k not in ACT_HOME][:3]
        for grp,start in ((home,1),(out,10)):
            for j,k in enumerate(grp):
                f=start+3*j; v(f"39-{f}",dict(ACTS_AA)[k]); v(f"39-{f+1}",lab(ACT_HELP,w.get(f"ah_{k}"),w.get(f"ah_{k}_x"))); v(f"39-{f+2}",lab(ACT_OFTEN,w.get(f"ao_{k}"),w.get(f"ao_{k}_x")))
        if w.get("acts_x") and len(home)<3: v(f"39-{1+3*len(home)}",w["acts_x"])
        v("34-1",lab([("legs","My legs give way"),("trip","I trip"),("dizzy","I get dizzy or black out"),("balance","I lose balance")],w.get("fall_what"),w.get("fall_what_x")))
        v("34-7",lab([("0","None"),("1","1"),("2","2"),("3+","3 or more")],w.get("falls_m")))
        v("34-9",lab([("0","None"),("1-2","1 to 2"),("3-5","3 to 5"),("6+","6 or more")],w.get("stum_m"))); v("34-10",lab([("0","None"),("1-5","1 to 5"),("6-20","6 to 20"),("20+","More than 20")],w.get("stum_y")))
        v("34-6",lab([("week","This week"),("month","This month"),("months","In the last 6 months"),("year","Over 6 months ago")],w.get("stum_last"),w.get("stum_last_x")))
        e2=w.get("eye2") or []; em={"prevent":("x40-1","303"),"neglect":("x40-3",None),"harm":("x40-4","305"),"aggr":("x40-6","307"),"voices":("x40-9","309")}
        for k in e2:
            t(em[k][0],"/Yes")
            if d.get("watch") in ("some","most") and em[k][1]: t(em[k][1],"/Yes")
        if d.get("watch") in ("some","most") and "danger" in (d.get("eye") or []): t("304","/Yes")
        v("41",w.get("eye_days")); other("Keeping an eye on me","eye2")
        v("310",lab([("1","Once"),("2","Twice"),("3","3 times"),("4+","4 or more times")],w.get("w_times"),w.get("w_times_x"))); v("311",w.get("w_long_x") or w.get("w_long")); v("314",w.get("w_nights"))
        nt={"1":"/Once","2":"/Twice","3":"/Three","4+":"/Three"}.get(d.get("ntimes")); nmn=I.TIME_T.get(d.get("nmins"),"")
        night=set(d.get("night") or []); np_=set(w.get("n_prompt") or [])
        for key,(rf,mf) in {"turn":("x42-1","42-2"),"pain":("x42-3","42-4"),"toilet":("x42-5","42-6"),"incont":("x42-7","42-8"),"meds":("x42-9","42-10"),"treat":("x42-11","42-12"),"ptoilet":("x42-13","42-14"),"pmeds":("x42-15","42-16")}.items():
            hit=key in night or (key=="incont" and w.get("n_incont")=="yes") or (key=="treat" and w.get("n_treat")=="yes") or (key[0]=="p" and key[1:] in np_)
            if hit: t(rf,nt); v(mf,nmn)
        # Q47-49 hospital, care home
        if w.get("hosp") in ("hosp","care"):
            t("316","/Yes"); v("Date 317",ukd(w.get("h_in"))); v("356",w.get("h_place")); v("355",w.get("h_town")); v("352",w.get("h_pc")); v("322",w.get("h_why"))
            t("323",yn(w.get("h_pays")) if w.get("h_pays")!="ns" else None); v("324",w.get("h_payer"))
        elif w.get("hosp")=="no": t("316","/No")
        if w.get("out6")=="yes":
            t("325","/Yes"); v("Date 326",ukd(w.get("o_in"))); v("Date 3274",ukd(w.get("o_out"))); v("328",w.get("o_place")); v("329",w.get("o_town")); v("331",w.get("o_pc")); v("332",w.get("o_why"))
        elif w.get("out6")=="no": t("325","/No")
        # checklist boxes we can honestly tick (the signing ones are left for the customer)
        if w.get("gp_name"): t("360","/No")   # this box's on-state is called /No on the PDF
        if "17_1" in V: t("361","/Yes")
        if hp in ("yes","me"): t("362","/Yes")
        docs=ups+[dict(I_EV(form)).get(x,x) for x in ev if x not in ("none",)]
        v("364",", ".join(dict.fromkeys(x for x in docs if x)))
    else:
        if answered:
            t("1","/Yes" if "sr" in chk else "/No"); t("11","/No" if "notgb" in chk else "/Yes"); t("12","/Yes" if "scot" in chk else "/No")
            t("14","/Yes" if "cdp" in chk else "/No"); t("15","/Yes" if "newuk" in chk else "/No"); t("18","/Yes" if "abroad" in chk else "/No")
            t("19","/Yes" if "eeaben" in chk else "/No"); t("20","/Yes" if "eeawork" in chk else "/No")
        other("Also applies","checks")
        if "scot" in chk: v("13",ukd(w.get("scot_date")))
        if "newuk" in chk: v("16",ukd(w.get("uk_date"))); v("17",w.get("uk_passport"))
        if "abroad" in chk:
            for i in range(1,6):
                b=4*(i-1); v(f"18_{b+1}",ukd(w.get(f"ab{i}_left"))); v(f"18_{b+2}",ukd(w.get(f"ab{i}_back"))); v(f"18_{b+3}",w.get(f"ab{i}_where")); v(f"18_{b+4}",w.get(f"ab{i}_why_x") or w.get(f"ab{i}_why"))
        t("7",{"female":"/Female","male":"/Male"}.get(w.get("sex"))); other("Sex","sex")
        v("4",w.get("othernames")); v("9",w.get("nat_c") if w.get("nat")=="EEA" else (w.get("nat") or w.get("nat_x")))
        if w.get("nat")=="EEA": t("10",yn(w.get("eea_before")))
        if w.get("p_text")=="yes": v("0_2",w.get("p_phone"))
        v("75",ukd(w.get("p_dob"))); v("83",w.get("p_nat_c") if w.get("p_nat")=="EEA" else (w.get("p_nat") or w.get("p_nat_x")))
        if w.get("p_same")=="no": v("77",w.get("p_addr1")); v("77_1",w.get("p_town")); v("77_3",w.get("p_pc"))
        t("78","/Yes" if w.get("p_welsh")=="yes" else "/No" if w.get("p_welsh") else None)
        t("80",yn(w.get("p_is")) if w.get("p_is")!="ns" else None); t("81",yn(w.get("p_his")) if w.get("p_his")!="ns" else None)
        if w.get("p_his")=="yes": v("81_1",w.get("p_his_name")); v("81_3",w.get("p_his_rel_x") or w.get("p_his_rel"))
        if w.get("hosp")=="hosp":
            t("21","/Yes"); v("21_1",ukd(w.get("h_in"))); v("21_2",w.get("h_place")); v("21_3",w.get("h_town")); v("21_5",w.get("h_pc")); v("21_6",w.get("h_tel")); v("21_7",w.get("h_why"))
            t("21_8",yn(w.get("h_nhs")) if w.get("h_nhs")!="ns" else None)
        elif w.get("hosp")=="no": t("21","/No")
        if w.get("stays")=="yes":
            t("22","/Yes"); v("22_1",ukd(w.get("s_in"))); v("22_2",ukd(w.get("s_out"))); v("22_3",w.get("s_place")); v("22_4",w.get("s_town")); v("22_6",w.get("s_pc")); v("22_7",w.get("s_tel"))
            t("22_8",{"la":"/Local","ha":"/Health","gov":"/Government","nhs":"/NHS","none":"/None"}.get(w.get("s_pays"))); v("22_9",w.get("s_payer"))
        elif w.get("stays")=="no": t("22","/No")
        if w.get("tests")=="yes":
            t("23","/Yes")
            rows=[("23_1_1","23_1_2","23_1_3")]+[(f"23_{3*k-1}",f"23_{3*k}",f"23_{3*k+1}") for k in range(1,5)]
            for i,(a,b,c) in enumerate(rows,1):
                if not w.get(f"test{i}"): continue
                v(a,w.get(f"test{i}")); r=w.get(f"test{i}r")
                v(b,w.get(f"test{i}r_x") or ("Waiting for results" if r=="waiting" else "See the enclosed letter" if r else ""))
                t(c,"/Yes" if r=="waiting" else "/No" if r else None)
        elif w.get("tests")=="no": t("23","/No")
        t("24","/Yes" if (ups or ev) else "/No")
        docs=ups+[dict(I_EV(form)).get(x,x) for x in ev]
        v("24_1",", ".join(dict.fromkeys(x for x in docs if x)))
        p=prof(form,d)
        if p:
            t("25","/Yes"); v("25_1",w.get("pr_name") or f"My {p.lower()}"); v("25_2",p); addr(["25_3","25_4","25_5"],[w.get("pr_where"),w.get("pr_town")]); v("25_6",w.get("pr_pc"))
            v("25_7",w.get("pr_tel")); v("25_8",w.get("pr_hosp")); v("25_9",w.get("pr_cond_x") or w.get("pr_cond")); v("25_10",seen_txt(w.get("pr_seen"),w.get("pr_seen_x")))
            t("89_3","/You have included")
        elif w.get("pr_any"): t("25",yn(w["pr_any"]))
        if w.get("gp_name"):
            v("26",w.get("gp_doc") or w.get("gp_name")); addr(["27","27_1","27_2"],[w.get("gp_name") if w.get("gp_doc") else None,w.get("gp_addr"),w.get("gp_addr2"),w.get("gp_town")]); v("27_3",w.get("gp_pc")); v("28",w.get("gp_tel"))
            v("29",seen_txt(w.get("gp_seen"),w.get("gp_seen_x"))); t("89_4","/You have included")
        if w.get("sc_name"):
            v("30",w.get("sc_name")); v("31",w.get("sc_addr")); v("31_1",w.get("sc_town")); v("31_3",w.get("sc_pc")); v("32",w.get("sc_contact")); v("33",w.get("sc_tel")); v("34",w.get("sc_email"))
            ty=w.get("sc_type"); t("35","/Yes" if ty in ("main","nursery") else "/No" if ty else None); t("36","/Yes" if ty=="special" or "special" in (d.get("school") or []) else "/No" if ty else None)
            v("68_8",w.get("sc_behav_x") or w.get("sc_behav")); v("68_9",w.get("sc_travel_x") or w.get("sc_travel"))
            v("36_1",w.get("sc_type_x") or {"main":"Mainstream","special":"Specialist","nursery":"Nursery or pre-school"}.get(ty,""))
        pl=w.get("plans") or []
        for k,f,s in [("iep","37_2","/Individual Education"),("ibp","37_3","/Individual Behaviour"),("sen","37_4","/A letter"),("csp","37_5","/Co-ordinated"),("waiting","37_6","/I am waiting")]:
            if k in pl: t(f,s)
        if "none" in pl and "ehcp" not in (d.get("school") or []): t("37_7","/The child does not")
        other("Plans or reports","plans")
        if w.get("stmt"): t("38","/No" if w["stmt"]=="noone" else "/Yes")
        t("39",{"yes":"/Yes","no":"/No"}.get(w.get("consent")))
        from forms import DLA_CONDITION_FIELDS as CF
        for i,c in enumerate(conds(d)):
            if i<len(CF): v(CF[i][2],w.get(f"med_{i}") or None); v(CF[i][3],lab(DOSE,w.get(f"dose_{i}"),w.get(f"dose_{i}_x")))
        if w.get("meds_how")=="photo" and conds(d): v(CF[0][2],"See the repeat prescription list sent with this form")
        other("Medicines","meds_how")
        AF=[("41_2","41_3"),("41_5","41_6"),("41_8","41_9"),("41_11","41_12"),("41_14","41_15"),("14_17","41_18")]
        for i,a in enumerate(aids(d)):
            hf,pf=AF[i]; v(hf,lab([("none","None"),("puton","Someone puts it on or sets it up"),("watch","Needs watching while using it"),("remind","Needs reminding to use it")],w.get(f"aid_h_{i}"),w.get(f"aid_h_{i}_x")))
            t(pf,yn(w.get(f"aid_p_{i}")))
        if w.get("canwalk"):
            t("43",yn(w["canwalk"]))
            t("45",{"200+":"/over","51-200":"/51","50":"/50","few":"/a few"}.get(w.get("dist"))); t("45_1",{"5+":"/more","3-4":"/3","1-2":"/1","lt1":"/less"}.get(w.get("wtime")))
            t("48",yn(w.get("walk_other")))
            t("46",{"normal":"/Normal","slow":"/Slow","vslow":"/Very"}.get(w.get("speed")))
            g={"normal":"/They walk normally","limp":"/They walk with a limp","shuffle":"/They shuffle","drag":"/They drag","in":"/They walk with one","toes":"/They walk on","balance":"/They have poor","unable":"/They have times","refuse":"/They refuse"}.get(w.get("gait"))
            if w.get("gait_x"): g="/Something"; v("47_1",w["gait_x"])
            t("47",g)
        R=d.get("rows") or {}
        if (R.get("walk") or {}).get("lvl") not in (None,"ok"): t("44","/Yes")
        elif (R.get("walk") or {}).get("lvl")=="ok":
            t("44","/No")
            if not w.get("canwalk"): t("43",yn("yes"))   # no difficulty walking: they can walk (Q43 Yes, then Q44 No -> go to Q49)
        for f in [f"49_{i}" for i in range(1,9)]+["50_2","50_3","61_2","61_3","61_4","61_5","61_6"]+[f"62_{i}" for i in range(1,7)]+[f"63_{i}" for i in range(1,6)]+["64_3","64_4","65_5","65_6","65_11"]+[f"66_{i}" for i in range(1,11)]+[f"67_{i}" for i in range(1,9)]+[f"68_{i}" for i in range(1,7)]:
            if w.get(f) in ("yes","no"): t(f,yn(w[f]))
        for g_,l in [("out_g","Outdoors"),("falls_g","Falls"),("see_g","Seeing"),("hear_g","Hearing"),("speak_g","Speaking"),("comm_g","Communicating"),("fit_g","Fits"),("superv_g","Supervision"),("dev_g","Development"),("school_g","At school")]: other(l,g_)
        v("50_1",w.get("falls_m")); v("51",ukd(w.get("mob_start"))); t("52",yn(w.get("motab")))
        if w.get("bed")=="yes": t("54","/Yes")
        elif w.get("bed")=="no": t("54","/No")
        for rid,subs in DLA_SUB.items():
            sel=w.get(f"sub_{rid}") or []; m=lab(MINS,w.get(f"m_{rid}"),w.get(f"m_{rid}_x"))
            for k,_,tf,mf in subs:
                n=lab(TIMESD,w.get(f"t_{rid}_{k}"),w.get(f"t_{rid}_{k}_x"))
                if k in sel and n: v(tf,n); v(mf,m)
        for f in w.get("toilet2") or []: t(f,"/"+dict(DLA_TOILET)[f][:4].lower()) if False else T.__setitem__(f,st(form,f,"/")) if st(form,f,"/") else None
        for f in w.get("indoors2") or []: T.__setitem__(f,st(form,f,"/")) if st(form,f,"/") else None
        for c in (R.get("toilet") or {}).get("c") or []:
            if c in DLA_TOILET_PRE: f=DLA_TOILET_PRE[c]; T[f]=st(form,f,"/") or T.get(f)
        for c in (R.get("indoors") or {}).get("c") or []:
            for f in DLA_INDOORS_PRE.get(c,[]): T[f]=st(form,f,"/")
        for rid,f in [("see","61"),("hear","62"),("speak","63"),("comm","64")]:
            lv=(R.get(rid) or {}).get("lvl")
            if lv: t(f,"/No" if lv=="ok" else "/Yes")
        t("61_1",{"severe":"/Certified severely","si":"/Certified sight"}.get(w.get("sight_cert")))
        for f in w.get("comm_how") or []: T[f]=st(form,f,"/")
        v("64_2",w.get("comm_how_x"))
        if d.get("fits")=="no": t("65","/No")
        Y3={"yes":"/Yes","no":"/No","some":"/Sometimes"}
        t("65_2",Y3.get(w.get("fit_warn"))); t("65_3",Y3.get(w.get("fit_tell"))); t("65_4",Y3.get(w.get("fit_act")))
        v("65_7",w.get("fit_days")); v("65_8",w.get("fit_per")); v("65_9",w.get("fit_nights")); v("65_10",w.get("fit_nper"))
        ft=[x for x in w.get("fit_type") or []]+([w["fit_type_x"]] if w.get("fit_type_x") else [])
        if ft: V["_fit_type"]=", ".join(ft)
        sv=(R.get("superv") or {}).get("lvl"); 
        if sv=="ok": t("66","/No")
        dv=(R.get("dev") or {}).get("lvl")
        if dv: t("67","/No" if dv=="ok" else "/Yes")
        if w.get("hobby"): t("69",yn(w["hobby"]))
        if w.get("hobby")=="yes":
            for j,k in enumerate([k for k in w.get("acts") or []][:6]):
                b=4*j+1; v(f"69_{b}",dict(ACTS_DLA)[k]); v(f"69_{b+1}",lab(ACT_HELP,w.get(f"ah_{k}"),w.get(f"ah_{k}_x"))); v(f"69_{b+2}",lab(ACT_OFTEN,w.get(f"ao_{k}"),w.get(f"ao_{k}_x"))); v(f"69_{b+3}",lab(ACT_LONG,w.get(f"al_{k}"),w.get(f"al_{k}_x")))
            if w.get("acts_x") and len(w.get("acts") or [])<6: v(f"69_{4*len(w.get('acts') or [])+1}",w["acts_x"])
        v("71",ukd(w.get("care_start")))
        if w.get("asked"): pass
    T={k:s for k,s in T.items() if s}
    return V,T,notes
def I_EV(form):
    try:
        import evidence as E; return E.options(form)
    except Exception: return []
# The statement box for the person who knows them: (question number printed on the form, PDF field name prefix).
# Pages are read from the form's field map, so a new form version moves them automatically; test_statement_ref.py
# checks the question number is still printed on those pages of the current PDF (AA1 11/25: Q56 p28; DLA1A 10/25: Q38 pp10-11).
STATEMENT={"aa":("56",("344",)),"dla":("38",("38_",))}
def statement_pages(form):
    import os
    qn,pre=STATEMENT[form]
    fm=json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)),{"aa":"aa1_fields.json","dla":"dla1a_fields.json"}[form])))
    return sorted({x["page"] for x in fm if any(x["name"]==p or (p.endswith("_") and x["name"].startswith(p)) for p in pre)})
def statement_ref(form):
    qn,_=STATEMENT[form]; pg=statement_pages(form)
    where=f"page {pg[0]}" if len(pg)==1 else "pages "+", ".join(map(str,pg[:-1]))+f" and {pg[-1]}"
    return f"question {qn} ({where})"
def statement_note(form,d,personal):
    """Plain note for the person who knows them: what the statement box is for. Never our wording in their box."""
    w=d.get("wf") or {}; who=w.get("stmt_name") or {"family":"the family member","friend":"the friend","carer":"the carer","prof":"the professional"}.get(w.get("stmt"),"someone who knows them well")
    claimant=" ".join(x for x in (personal.get("other_names"),personal.get("surname")) if x) or ("your child" if form=="dla" else "the person claiming")
    q=statement_ref(form)
    R=d.get("rows") or {}; topics=[r[2].lower() for r in I.rows(form,None,d) if R.get(r[0]) and R[r[0]].get("lvl")!="ok"]
    return who,claimant,q,topics

"""Blue Badge answers: taps -> answers to paste into the online Blue Badge application (grouped by its sections),
a hidden-disability write-up, a document checklist and, if refused, a letter asking the council to look again.
Sold as a £15 add-on to a paid AA / DLA / PIP order (prefilled from that order, no re-asking) or £29 on its own.
Text is built only from what the customer tapped or typed (no drafting model), so nothing is added that they didn't say.
Rules: pay at the end; nothing usable before payment; no outbound links; never imply eligibility or council affiliation;
the customer applies themselves; we are an online form-filling service."""
import re, html, json, datetime
esc=lambda s: html.escape(str(s or ""),quote=True)
ADDON_TIER, SOLO_TIER = "15", "29"
PARENT_FORMS=("aa","dla","pip")
NOT_ELIG=("We can't tell you whether a badge will be issued. Your council decides. "
          "FormSorted is an online form-filling service, not part of any council, DWP or GOV.UK. You apply yourself.")
DIST=[("none","Can't walk at all"),("lt20","Under 20 metres"),("20_50","20 to 50 metres"),("50_100","50 to 100 metres"),("100p","More than 100 metres"),("ns","Not sure")]
TIME=[("lt1","Under 1 minute"),("1_5","1 to 5 minutes"),("5_10","5 to 10 minutes"),("10p","Over 10 minutes"),("ns","Not sure")]
EFFECTS=[("pain","Pain"),("breath","Breathlessness"),("tired","Exhaustion"),("dizzy","Dizziness"),("unsteady","Unsteady or loses balance"),("falls","Falls")]
AIDS=[("stick","Walking stick"),("crutches","Crutches"),("frame","Walking frame"),("wheelchair","Wheelchair"),("scooter","Mobility scooter"),("arm","Someone's arm"),("none","No aids")]
RECOVER=[("lt10","Under 10 minutes"),("10_60","10 minutes to an hour"),("hours","Hours"),("nextday","Until the next day"),("ns","Not sure")]
HIDDEN=[("panic","Panic or severe anxiety in traffic, car parks or crowds"),("danger","No sense of danger near roads"),("runs","Runs off or bolts"),
        ("melt","Meltdowns or intense distress on journeys"),("lost","Gets lost or confused"),("toilet","Needs a toilet quickly"),("freeze","Freezes or refuses to move")]
HFREQ=[("every","Every journey"),("most","Most journeys"),("some","Some journeys"),("rarely","Rarely")]
PROS=[("GP","GP"),("Consultant","Consultant"),("Physiotherapist","Physiotherapist"),("Occupational therapist","Occupational therapist"),("Nurse","Nurse"),("Mental health team","Mental health team"),("Social worker","Social worker")]
DOCS=[("pip","PIP award letter"),("dla","DLA award letter"),("aa","Attendance Allowance letter"),("meds","Repeat prescription list"),("hosp","Hospital or consultant letters"),
      ("ot","Occupational therapist or physio report"),("ehcp","EHCP or school report"),("photo","Recent passport-style photo"),("id","Proof of identity"),("addr","Proof of address (last 3 months)")]
T=lambda opts:dict(opts)
def _chk(n,v,t,on): return f'<label class=chip><input type=checkbox name="{n}" value="{esc(v)}" {"checked" if on else ""}><span>{esc(t)}</span></label>'
def _rad(n,v,t,cur): return f'<label class=chip><input type=radio name="{n}" value="{esc(v)}" {"checked" if cur==v else ""}><span>{esc(t)}</span></label>'
def _else(n,txt): return f'<span class=else><label class=chip><input type=checkbox name="{n}_xon" value=1 {"checked" if txt else ""}><span>Something else</span></label><input class=elsebox name="{n}_x" value="{esc(txt)}" maxlength=200 placeholder="Tell us briefly" aria-label="Something else: tell us briefly"></span>'
def checks(n,opts,cur,x=""): return "<div class=chips>"+"".join(_chk(n,v,t,v in (cur or [])) for v,t in opts)+_else(n,x)+"</div>"
def radios(n,opts,cur): return "<div class=chips>"+"".join(_rad(n,v,t,cur) for v,t in opts)+"</div>"
def q(label,inner,hint=""): return f'<fieldset class=iq><legend>{esc(label)}</legend>{f"<p class=hint>{esc(hint)}</p>" if hint else ""}{inner}</fieldset>'
def nm(d): return (d.get("name") or "").strip() or ("you" if d.get("who","me")=="me" else "them")

def prefill(form,I):
    """Reuse what the customer already told us on their AA / DLA / PIP order. Only taps they made; nothing inferred beyond a direct mapping."""
    I=I or {}; R=I.get("rows") or {}; c=lambda rid:(R.get(rid) or {}).get("c") or []
    d={"who":"me" if (form!="dla" and I.get("who","me") in ("me","")) else "other","name":I.get("name",""),"from":form,
       "conds":[{"name":x.get("name"),"since":x.get("since","")} for x in I.get("conds") or [] if x.get("name")],"else":{}}
    eff,aid,hid=set(),set(),set()
    if form=="pip":
        a12=c("a12"); d["dist"]="lt20" if "lt20" in a12 else "20_50" if "lt50" in a12 else ""
        if "pain" in a12: eff|={"pain","breath","tired"}
        if "wheel" in a12: aid.add("wheelchair")
        a11=c("a11"); hid|={"panic"} if "panic" in a11 else set(); hid|={"lost"} if "lost" in a11 else set()
    if form=="dla":
        w=c("walk"); eff|={k for k in ("pain","tired","breath") if k in w}
        if "carry" in w: aid.add("arm")
        o=c("out"); hid|={"runs"} if "road" in o else set(); hid|={"danger"} if "danger" in o else set(); hid|={"melt"} if "anx" in o else set()
        if "falls" in o: eff.add("falls")
    if form=="aa":
        if (I.get("falls") or "") not in ("","0","none","ns"): eff.add("falls")
        if "walk" in c("indoors"): eff.add("unsteady")
    amap={"Walking stick":"stick","Walking frame":"frame","Wheelchair":"wheelchair","Crutches":"crutches","Mobility scooter":"scooter"}
    aid|={amap[a] for a in I.get("aids") or [] if a in amap}
    d["eff"],d["aids"],d["hidden"]=sorted(eff),sorted(aid),sorted(hid)
    d["pros"]=[p for p in I.get("people") or [] if p in T(PROS)]
    d["docs"]=[form] if form in ("pip","dla","aa") else []
    d["prefilled"]=[k for k in ("conds","dist","eff","aids","hidden","pros") if d.get(k)]
    return d

def body(d):
    me=d.get("who","me")=="me"; you="you" if me else nm(d)
    pre=f'<div class=inset>We\'ve filled in what you told us on your {esc({"aa":"Attendance Allowance","dla":"DLA","pip":"PIP"}.get(d.get("from"),""))} form. Check it and add anything missing.</div>' if d.get("prefilled") else ""
    h=pre
    if not d.get("from"):
        h+=q("Who is the badge for?",radios("who",[("me","Me"),("other","Someone I help")],d.get("who")))
        h+=q("Their first name (if it's not you)",f'<input name=name value="{esc(d.get("name",""))}" maxlength=40 autocomplete=off>',"Optional.")
    conds=", ".join(c["name"] for c in d.get("conds") or [])
    h+=q("Health conditions or disabilities",f'<input name=conds value="{esc(conds)}" maxlength=300 placeholder="e.g. Arthritis, COPD, autism">',"Separate them with commas. No diagnosis needed.")
    h+=q(f"How far can {you} walk before needing to stop?",radios("dist",DIST,d.get("dist")),"Using any aids you normally use, on flat ground.")
    h+=q("How long does that take?",radios("time",TIME,d.get("time")))
    h+=q("What happens when walking?",checks("eff",EFFECTS,d.get("eff"),d["else"].get("eff","")))
    h+=q("What do "+("you" if me else "they")+" use to get around?",checks("aids",AIDS,d.get("aids"),d["else"].get("aids","")))
    h+=q("How long to recover after walking that far?",radios("rec",RECOVER,d.get("rec")))
    h+=q("On journeys: anything that isn't about walking?",checks("hidden",HIDDEN,d.get("hidden"),d["else"].get("hidden","")),"For example anxiety, distress or risk near traffic. Skip if none.")
    h+=q("How often does that happen?",radios("hfreq",HFREQ,d.get("hfreq")))
    h+=q("Who treats or supports "+("you" if me else "them")+"?",checks("pros",PROS,d.get("pros"),d["else"].get("pros","")))
    h+=q("Medicines or treatments (optional)",f'<input name=meds value="{esc(d.get("meds",""))}" maxlength=300 placeholder="e.g. Morphine patches, inhalers, physio">')
    h+=q("Which of these do you have?",checks("docs",DOCS,d.get("docs"),d["else"].get("docs","")),"We list what to upload with the application.")
    return h

def save(d,fm):
    g=lambda k:fm.getlist(k) if hasattr(fm,"getlist") else ([fm[k]] if isinstance(fm.get(k),str) else fm.get(k) or [])
    x=lambda n:re.sub(r"\s+"," ",str(fm.get(f"{n}_x") or "")).strip()[:200] if fm.get(f"{n}_xon") else ""
    if "who" in fm: d["who"]=fm.get("who")
    if "name" in fm: d["name"]=str(fm.get("name"))[:40]
    d["conds"]=[{"name":c.strip()[:80]} for c in str(fm.get("conds","")).split(",") if c.strip()][:10]
    for k,opts in (("dist",DIST),("time",TIME),("rec",RECOVER),("hfreq",HFREQ)):
        v=fm.get(k,""); d[k]=v if v in T(opts) else ""
    for k,opts in (("eff",EFFECTS),("aids",AIDS),("hidden",HIDDEN),("pros",PROS),("docs",DOCS)):
        d[k]=[v for v in g(k) if v in T(opts)]; d.setdefault("else",{})[k]=x(k)
    d["meds"]=re.sub(r"\s+"," ",str(fm.get("meds",""))).strip()[:300]
    return d

def ready(d): return bool(d.get("dist") or d.get("hidden") or d["else"].get("hidden"))
def _list(keys,opts,extra=""):
    t=T(opts); xs=[t[k] if t[k][:2].isupper() else t[k][0].lower()+t[k][1:] for k in keys if k in t]+([extra] if extra else [])
    return ", ".join(xs[:-1])+(" and " if len(xs)>1 else "")+xs[-1] if xs else ""

def answers(d):
    """(section, answer) pairs in the order of the online application's health and walking questions."""
    me=d.get("who","me")=="me"; I="I" if me else nm(d).capitalize(); my="my" if me else "their"; out=[]
    if d.get("conds"): out.append(("Your health conditions",("I have " if me else f"{I} has ")+", ".join(c["name"] for c in d["conds"])+"."))
    if d.get("meds"): out.append(("Medicines and treatments",d["meds"].rstrip(".")+"."))
    if d.get("dist"):
        if d["dist"]=="none": s=f"{I} can't walk at all."
        elif d["dist"]=="ns": s=""
        else:
            s=f"{I} can walk {T(DIST)[d['dist']].lower()} before {'I have' if me else 'they have'} to stop"
            if d.get("time") not in ("","ns",None): s+=f", and it takes {T(TIME)[d['time']].lower()}"
            s+="."
        if s: out.append(("How far you can walk",s))
    ef=_list(d.get("eff") or [],EFFECTS,d["else"].get("eff",""))
    if ef: out.append(("What happens when you walk",("When I walk I get " if me else f"When {I} walks, they get ")+ef+"."))
    if d.get("rec") not in ("","ns",None): out.append(("Recovering after walking",f"It takes {'me' if me else 'them'} {T(RECOVER)[d['rec']].lower()} to recover."))
    ai=[k for k in d.get("aids") or [] if k!="none"]
    al=_list(ai,[("stick","a walking stick"),("crutches","crutches"),("frame","a walking frame"),("wheelchair","a wheelchair"),("scooter","a mobility scooter"),("arm","someone's arm")],d["else"].get("aids",""))
    if al: out.append(("Mobility aids",("I use " if me else f"{I} uses ")+al+" to get around."))
    elif "none" in (d.get("aids") or []): out.append(("Mobility aids",("I don't" if me else f"{I} doesn't")+" use any mobility aids."))
    hl=_list(d.get("hidden") or [],HIDDEN,d["else"].get("hidden",""))
    if hl: out.append(("Difficulties on journeys",("On journeys I have: " if me else f"On journeys {I} has: ")+hl+(f". This happens on {T(HFREQ)[d['hfreq']].lower()}." if d.get("hfreq") else ".")))
    pl=_list(d.get("pros") or [],[(k,("my " if me else "their ")+(k if k=="GP" else k.lower())) for k,_ in PROS],d["else"].get("pros",""))
    if pl: out.append(("Healthcare professionals",("I see " if me else f"{I} sees ")+pl+"."))
    return out

def hidden_writeup(d):
    if not (d.get("hidden") or d["else"].get("hidden")): return ""
    me=d.get("who","me")=="me"; I="I" if me else nm(d).capitalize()
    parts=[f"{T(HIDDEN)[k]}." for k in d.get("hidden") or []]+([d["else"]["hidden"].rstrip(".")+"."] if d["else"].get("hidden") else [])
    f=f" This happens on {T(HFREQ)[d['hfreq']].lower()}." if d.get("hfreq") else ""
    return (("These are the difficulties I have on journeys, in my own words:" if me else f"These are the difficulties {I} has on journeys:")+" "+" ".join(parts)+f)

def checklist(d):
    have=set(d.get("docs") or []); t=T(DOCS); out=[]
    for k in ("photo","id","addr"): out.append(("✓ " if k in have else "☐ ")+t[k])
    for k in ("pip","dla","aa","meds","hosp","ot","ehcp"):
        if k in have: out.append("✓ "+t[k]+" (upload a clear photo or scan of every page)")
    if d["else"].get("docs"): out.append("✓ "+d["else"]["docs"])
    out.append("☐ Your National Insurance number, if you have one")
    return out

def letter(d,decision_date,reason):
    me=d.get("who","me")=="me"; who="me" if me else nm(d)
    try: dd=datetime.date.fromisoformat(decision_date).strftime("%-d %B %Y")
    except Exception: dd="[date on your decision letter]"
    lines=["[Your name]","[Your address]","","[Date]","","To the Blue Badge team, [council name]","",f"Blue Badge application: request to look at the decision again",f"Decision letter dated: {dd}","",
           f"I am writing to ask you to look again at your decision not to issue a Blue Badge to {who}. Please consider the information below, which may not have been clear in the application.",""]
    if reason.strip(): lines+=["Your letter said: "+re.sub(r"\s+"," ",reason.strip())[:600],""]
    for s,a in answers(d): lines.append(f"{s}: {a}")
    hw=hidden_writeup(d)
    if hw: lines+=["",hw]
    lines+=["","I have enclosed copies of: "+", ".join(T(DOCS)[k] for k in d.get("docs") or [] if k not in ("photo","id","addr")) if [k for k in d.get("docs") or [] if k not in ("photo","id","addr")] else "", "",
            "Please contact me if you need anything else.","","Yours faithfully,","","[Signature]","[Your name]"]
    return "\n".join(l for l in lines if l is not None)

def answers_html(d,brand="FormSorted"):
    rows="".join(f"<h2>{esc(s)}</h2><p class=you>{esc(a)}</p>" for s,a in answers(d))
    hw=hidden_writeup(d)
    return f"""<!doctype html><meta charset=utf-8><title>Blue Badge answers</title><style>body{{font:16px/1.5 system-ui;max-width:720px;margin:2em auto;padding:0 1em}}h2{{font-size:1.05em;margin:1.4em 0 .3em}}.you{{background:#f3f6f8;padding:.6em .8em;border-radius:6px}}</style>
<h1>Your Blue Badge answers</h1><p>Copy each answer into the matching part of the online Blue Badge application, or onto your council's paper form. Change anything that isn't right. You apply yourself.</p>{rows}
{f"<h2>Hidden disability: in your own words</h2><p class=you>{esc(hw)}</p>" if hw else ""}
<h2>What to have ready</h2><ul>{"".join(f"<li>{esc(x)}</li>" for x in checklist(d))}</ul>
<p><small>{esc(NOT_ELIG)}</small></p>"""

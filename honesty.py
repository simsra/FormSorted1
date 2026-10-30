"""Honesty (Oct 2026): we only write what's true, in the customer's words.
- refuse(): free text asking us to exaggerate is not saved; the customer sees a polite message.
- contradictions(): answers that can't both be right get ONE short tap question each (max 3) before drafting.
  The customer's choice fixes the tapped facts and/or is kept as their own words ("Checked with you: ...")."""
import re
REFUSE_MSG="We only write what's true, in your words, so we can't make things sound worse than they are. Please tell us what really happens on a typical day, and on bad days. That's what gives the most accurate form."
_NEG=""
NEG=re.compile(r"\b(don't|dont|do not|not|never|without|no|won't|wouldn't|doesn't|didn't|nor)\b[^.!?]{0,25}$",re.I)
REFUSE=re.compile(r"\b(?:"
 r"make (?:it|this|that|things|me|him|her|them|my \w+|the form|the answers?) (?:sound|look|seem|appear) (?:a lot |much |a bit |even )?(?:worse|more severe|more serious|bad|really bad|terrible)"
 r"|sound (?:a lot |much |even )?worse than (?:it|they|i|he|she|things) (?:is|are|am|really)"
 r"|"+_NEG+r"exaggerat\w*|"+_NEG+r"embellish\w*|"+_NEG+r"over-?stat\w*|lay it on (?:thick|a bit)|pile it on"
 r"|(?:get|max|maximise|maximize|most|more|enough|extra) (?:the )?points"
 r"|(?:worst|worse) case (?:as|for) (?:every|each|all)"
 r"|(?:pretend|lie|fib)(?:s|d)? (?:that|about|on)"
 r"|say (?:i|he|she|they|we) (?:can't|cannot|can not) .{0,40}(?:even though|but really|when actually) (?:i|he|she|they) can"
 r")\b",re.I)
def refuse(text):
    """True if the text asks us to exaggerate ("don't want to exaggerate" is fine)."""
    t=str(text or "")
    return any(not NEG.search(t[max(0,m.start()-40):m.start()]) for m in REFUSE.finditer(t))
def scrub(d):
    """Remove refused free text from saved intake data in place. Returns how many were removed."""
    n=0
    if refuse(d.get("words")): d["words"]=""; n+=1
    for k,v in list((d.get("else") or {}).items()):
        if refuse(v): d["else"][k]=""; n+=1
    for v in (d.get("rows") or {}).values():
        for k in ("x","lvl_x","days_x"):
            if refuse(v.get(k)): v[k]=""; n+=1
        for f in (v.get("fu") or {}).values():   # 30 Oct: words typed in the inline follow-ups
            if refuse(f.get("w")): f["w"]=""; n+=1
    for q in (d.get("nnum") or {}).values():
        for k in ("n_x","t_x","m_x"):
            if refuse(q.get(k)): q[k]=""; n+=1
    for c in d.get("conds") or []:
        if refuse(c.get("tx")): c["tx"]=""; n+=1
    if n: d["refused"]=int(d.get("refused") or 0)+1   # one refused request per answer submitted
    return n
# ---------- contradictions ----------
ACTIVE=re.compile(r"\b(walk(?:s|ing)? (?:the|my|our|his|her) dogs?|(?:go|goes|going|went) (?:to the )?gym|(?:go|goes|going) (?:for )?(?:a )?(?:run|jog|long walk|hike|bike ride)s?|running|jogging|hiking|(?:play|plays|playing) (?:football|tennis|golf|squash|rugby)|cycl(?:e|es|ing) (?:to|every|most)|swim(?:s|ming)? (?:every|most|lengths)|walk(?:s|ing)? (?:to|into) (?:the )?(?:shops?|town|work|village)|long walks?)\b",re.I)
SLEEPS=re.compile(r"\b(sleeps? (?:right |all the way )?through(?: the night)?|sleeps? (?:fine|well|ok|okay) at night|no (?:problems|help|issues) at night|(?:good|fine) nights?)\b",re.I)
SOCIAL=re.compile(r"\b((?:meet|meets|meeting|see|sees|seeing) (?:up with )?(?:my |his |her |their )?friends|(?:go|goes|going) (?:to the )?(?:pub|parties|party|nightclub|concerts?|football matches?)|socialis\w+ (?:a lot|every|most))\b",re.I)
def free_text(d):
    parts=[d.get("words","")]+list((d.get("else") or {}).values())+[v.get(k,"") for v in (d.get("rows") or {}).values() for k in ("x","lvl_x","days_x")]
    parts+=[f.get("w","") for v in (d.get("rows") or {}).values() for f in (v.get("fu") or {}).values()]
    return " ".join(p for p in parts if p)
def _lv(d,rid): return ((d.get("rows") or {}).get(rid) or {})
def contradictions(form,d,limit=3):
    """[{id,topic,q,opts:[(v,label)]}] not yet answered (d['clarify']), most important first."""
    import intake as INTAKE
    me=INTAKE.is_me(d,form); nm=INTAKE.name(d,form); you="you" if me else nm; done=d.get("clarify") or {}; out=[]; txt=free_text(d)
    TM=dict(INTAKE.TREAT)
    # walking/mobility at its hardest vs free text describing activity
    mob={"aa":"indoors","dla":"walk","pip":"a12"}[form]; mv=_lv(d,mob)
    worst=mv.get("lvl")=="cant" or (form=="pip" and set(mv.get("c") or [])&{"lt20","wheel"})
    m=ACTIVE.search(txt)
    if worst and m:
        out.append({"id":"active","topic":{"aa":"33","dla":"walking","pip":"a12"}[form],
          "q":f"You told us “{m.group(0)}”, and also that moving around is very hard. Which is closest on a typical day?",
          "opts":[("aid","Only with help or an aid"),("good","Only on good days"),("short","A short way, with pain or rests"),("fine","No real difficulty walking")],"quote":m.group(0)})
    # night help vs 'sleeps through'
    night=(form=="aa" and d.get("night")) or (form=="dla" and d.get("nn"))
    m=SLEEPS.search(txt)
    if night and m:
        out.append({"id":"sleeps","topic":"42" if form=="aa" else "night",
          "q":f"You told us “{m.group(0)}”, and also that {you} need{'' if me else 's'} help at night. Which is closest in a normal week?",
          "opts":[("most","Help most nights"),("some","Help some nights"),("none","No help at night")]})
    if form=="aa":
        lf=d.get("lastfall") in ("week","month","months"); fx=set(d.get("fallx") or [])&{"hurt","getup","clinic"}
        if d.get("falls")=="0" and (lf or fx):
            out.append({"id":"falls","topic":"34","q":"You said no falls in the last year, but also told us about a recent fall. How many falls in the last year?",
              "opts":[("1-2","1–2"),("3-5","3–5"),("6+","6 or more"),("0","None")]})
        if d.get("night") and d.get("nights")=="0":
            out.append({"id":"nights","topic":"42","q":f"You told us about help at night, and also 0 nights a week. How many nights a week does {you} need help?" if not me else "You told us about help at night, and also 0 nights a week. How many nights a week do you need help?",
              "opts":[(str(i),str(i)) for i in range(1,8)]+[("none","No help at night")],"nums":True})
        if d.get("alone")=="always" and (d.get("eye") or d.get("watch") in ("some","most")):
            out.append({"id":"alone","topic":"40","q":f"You said {you} can be left alone as long as needed, and also that someone needs to keep an eye on {'you' if me else 'them'}. Which is closer?",
              "opts":[("always","As long as needed"),("hours","A few hours"),("lt1","Under an hour"),("never","Not at all")]})
    if form=="pip":
        m=SOCIAL.search(txt)
        if "avoid" in (_lv(d,"a9").get("c") or []) and m:
            out.append({"id":"social","topic":"a9","q":f"You told us “{m.group(0)}”, and also that {you} avoid{'' if me else 's'} people completely. Which is closest?",
              "opts":[("someone","Only with someone I trust" if me else "Only with someone they trust"),("rare","Rarely, and it causes great distress"),("avoid","Avoids people completely"),("ok","Can mix with people")]})
    for i,c in enumerate(d.get("conds") or []):
        tr=c.get("treat") or []
        if "none" in tr and [x for x in tr if x not in ("none","ns")]:
            others=", ".join(TM[x].lower() for x in tr if x in TM and x not in ("none","ns"))
            out.append({"id":f"treat{i}","topic":"conditions","q":f"{c['name']}: you ticked “No treatment” and also {others}. Which is right?",
              "opts":[("has",f"Treatment: {others}"),("none","No treatment")],"cond":i})
    return [x for x in out if x["id"] not in done][:limit]
def apply(form,d,item,v,other=""):
    """Record the answer (never asked again) and fix the tapped facts it covers. Returns the customer's own sentence (or '')."""
    import intake as INTAKE
    me=INTAKE.is_me(d,form); nm=INTAKE.name(d,form); s=""; other=re.sub(r"\s+"," ",other or "").strip()[:300]
    if refuse(other): other=""; d["refused"]=int(d.get("refused") or 0)+1
    lab=dict(item["opts"]).get(v,""); k=item["id"]
    if k=="active":
        mob={"aa":"indoors","dla":"walk","pip":"a12"}[form]
        if v=="fine": d.setdefault("rows",{})[mob]={"lvl":"ok"}
        s={"aid":"Walking: I can only do that with help or an aid","good":"Walking: I can only do that on good days","short":"Walking: I can walk a short way, with pain or rests","fine":"Walking: no real difficulty walking"}.get(v,"")
        if s and not me: s=s.replace("I can","they can")
    elif k=="sleeps":
        if v=="none":
            if form=="aa": d["night"]=[]; d["nights"]=""; d["ntimes"]=""; d["nmins"]=""
            else: d["nn"]=[]; d["nnum"]={}
            s="No help is needed at night"
        else: s={"most":"Help is needed at night on most nights","some":"Help is needed at night on some nights, not every night"}.get(v,"")
    elif k=="falls":
        d["falls"]=v if v in ("1-2","3-5","6+","0") else d.get("falls")
        if v=="0": d["lastfall"]=""; d["fallx"]=[x for x in d.get("fallx") or [] if x=="alarm"]
    elif k=="nights":
        if v=="none": d["night"]=[]; d["nights"]=""; d["ntimes"]=""; d["nmins"]=""
        elif v in [str(i) for i in range(1,8)]: d["nights"]=v
    elif k=="alone":
        if v in ("always","hours","lt1","never"): d["alone"]=v
    elif k=="social":
        s={"someone":"Mixing with people: only with someone I trust" if me else "Mixing with people: only with someone they trust","rare":"Mixing with people: rarely, and it causes great distress","avoid":"Mixing with people: avoids people completely","ok":"Mixing with people: can mix with people"}.get(v,"")
        r=_lv(d,"a9")
        if v=="ok": d.setdefault("rows",{})["a9"]={"lvl":"ok"}
        elif v in ("someone","rare") and r: r["c"]=[x for x in r.get("c") or [] if x!="avoid"]+(["someone"] if v=="someone" else [])
    elif k.startswith("treat"):
        c=(d.get("conds") or [])[item["cond"]]
        if v=="none": c["treat"]=["none"]
        elif v=="has": c["treat"]=[x for x in c.get("treat") or [] if x!="none"]
    if other: s=(s+". " if s else "")+other.rstrip(".")
    d.setdefault("clarify",{})[k]={"v":v or "else","topic":item["topic"],"s":(s.rstrip(".")+".") if s else ""}
    return s

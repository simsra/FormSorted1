"""Last screen (30 Oct 2026): 'A few last things that really help your form'. Mock mode only (no paid calls).
Checks: one screen (no new sections, one step), visible tips and starters, perspective; the three answers reach the writer
as the customer's own words; the PDF mapping (Q17/Q25 name, bad day in the extra-information box when not used in a box);
and nothing at all is added when the fields are empty (no invented names, examples or 'no one helps' lines)."""
import os, re, json
os.environ["CLAUDE_MOCK"]="1"; os.environ["WF_LOOKUPS"]="0"
for k in ("ANTHROPIC_API_KEY","GEMINI_API_KEY","OPENAI_API_KEY"): os.environ.pop(k,None)
import intake as I, writer, claude as cl, wholeform as WF, fill_pdf, html
from test_personas import walk, FM, AA_STEPS, PIP_STEPS, DLA_STEPS
FAILS=[]
def check(ok,msg):
    if not ok: FAILS.append(msg); print("FAIL",msg)
BAD="Last Tuesday I couldn't get out of bed until my daughter came at 11. I missed my breakfast."
def filled(form):
    pro={"aa":"Consultant or specialist","pip":"Consultant or specialist","dla":"Paediatrician or specialist"}[form]
    ix=lambda p:I.PEOPLE[form].index(p)
    return {"badday":BAD,"nohelp":["wash","night"],"nohelp_w":"I skip lunch when no one is here","people":["GP",pro,"Carer"],
            f"know_{ix('GP')}":"Dr Patel, Hill Surgery",f"know_{ix(pro)}":"Dr Shah",f"know_{ix('Carer')}":"should be ignored"}
STEPS={"aa":AA_STEPS,"pip":PIP_STEPS,"dla":DLA_STEPS}
ABOUT={"aa":{"who":"me"},"pip":{"who":"me"},"dla":DLA_STEPS["about"]}
# ---- 1. one screen, tips, starters, perspective ----
for form,about in (("aa",{"who":"me"}),("aa",{"who":"parent","name":"Mum"}),("pip",{"who":"me"}),("pip",{"who":"other","name":"Sam"}),("dla",{"rel":"Mum","name":"Leo","age":"5to15"})):
    d=I.save(form,"about",{"wf_v":1} if form!="pip" else {},FM(about))
    secs=[k for k,_ in I.sections(form,d)]
    check(secs.count("finish")==1 and not any("last" in s or "badday" in s for s in secs),f"{form}: no new screens {secs}")
    body=html.unescape(I.section_body(form,"finish",d)); qs=re.sub(r"<script.*?</script>","",body,flags=re.S)
    check(qs.count('class="iq lastq"')==1 and "A few last things that really help your form</legend>" in qs,f"{form}: one 'A few last things' step")
    lq=qs[qs.index('class="iq lastq"'):]
    check("optional" not in lq.lower(),f"{form}: no 'optional' label in the last things")
    for q in ("Tell us about a recent bad day","no one is there to help?","condition?"): check(q in lq,f"{form}: question {q}")
    me=I.is_me(d,form)
    tips=["Think of one day recently. What happened, what "+("you" if me else "they")+" couldn't do, and who helped.",
          ("Count help you need even if no one gives it. Don't say you cope if it's a struggle." if me else "Count help they need even if no one gives it. Don't say they cope if it's a struggle."),
          ("Anyone who's seen how your condition affects you." if me else "Anyone who's seen how their condition affects them.")+" You don't need their details now."]
    for t in tips: check(f"<p class=tip>{t}</p>" in lq,f"{form}/{about.get('who')}: visible tip {t[:30]}")
    st=re.findall(r'data-for="badday" data-s="([^"]*)"',lq)
    check(len(st)>=2 and (st[0].startswith("I couldn't get up until") if me else not st[0].startswith("I ")),f"{form}: starters in their voice {st}")
    if not me and form!="dla": check("Is there anything "+about["name"]+" needs help with" in lq and about["name"]+"'s condition" in lq,f"{form}: named person")
    if form=="dla": check("Leo's condition" in lq and "Teacher or SENCo" in lq,"dla: child's perspective")
    check("name=words" in lq and "Anything else?" in lq,f"{form}: the free box stays as a small last line")
    for ch in ("Washing","Meals","At night","Going out","Taking medicines","Something else",">No<",">None<","Family or friend","Social worker"): check(ch in lq,f"{form}: chip {ch}")
    check("e.g. Last Tuesday" in lq,f"{form}: placeholder")
    check(len(re.findall(r'name="know_\d+"',lq))==len([p for p in I.PEOPLE[form] if p in I.PROF_PEOPLE]),f"{form}: a name line for each professional only")
    check(not re.search(r"\b(AI|Claude|Stripe|we claim|we submit)\b",lq),f"{form}: copy rules")
# ---- 2. save ----
d=I.save("aa","finish",{"who":"me"},FM(filled("aa")))
check(d["badday"]==BAD and d["nohelp"]==["wash","night"] and d["people"]==["GP","Consultant or specialist","Carer"],"saved")
check(d["know_names"]=={"GP":"Dr Patel, Hill Surgery","Consultant or specialist":"Dr Shah"},f"names only for ticked professionals {d['know_names']}")
d2=I.save("aa","finish",{"who":"me"},FM({"nohelp":["no"],"people":["None"]}))
check(d2["nohelp"]==[] and d2["nohelp_no"] and d2["people"]==[] and d2["people_none"] and d2["know_names"]=={},"No / None saved as flags, not as people")
d3=I.save("aa","finish",{"who":"me"},FM({"nohelp":["no","wash"],"people":["None","GP"]}))
check(d3["nohelp"]==["wash"] and not d3["nohelp_no"] and d3["people"]==["GP"] and not d3["people_none"],"a real answer wins over No/None")
# ---- 3. writer facts, transcript, fallback, PDF ----
for form in ("aa","dla","pip"):
    d,_=walk(form,ABOUT[form],{**STEPS[form],"finish":{**STEPS[form].get("finish",{}),**filled(form)}},stop="more")
    F=writer.facts(form,d); txt=[f["text"] for f in F]
    bd=[f for f in F if f["text"].startswith(writer.BADDAY)]
    check(len(bd)==1 and bd[0]["topic"]=="*" and bd[0]["text"].endswith(BAD),f"{form}: bad day is one whole own-words fact")
    check(not any("I missed my breakfast" in t and not t.startswith(writer.BADDAY) for t in txt),f"{form}: bad day not split or repeated")
    nt=I.NOHELP_TOPIC[form]
    for k in ("wash","night"):
        check(any(f["topic"]==(nt[k] if nt[k]!="other" else "*") and f"help {I.NOHELP_WHAT[k]}, but no one is there to help" in f["text"] for f in F),f"{form}: no-one-helps fact for {k} in {nt[k]}")
    for k in ("meals","out","meds"): check(not any(f"help {I.NOHELP_WHAT[k]}," in t for t in txt),f"{form}: no 'no one helps' for {k} (not named)")
    check(any(t==writer.NOHELP_OWN+"I skip lunch when no one is here" for t in txt),f"{form}: own words about help they go without")
    check(any("Dr Patel, Hill Surgery" in t and "Dr Shah" in t for t in txt) and not any("should be ignored" in t for t in txt),f"{form}: who knows, with typed names only")
    fb=I.fallback_draft(form,d)
    if form in ("aa","dla"):
        check(fb.get("badday_note","").endswith(BAD),f"{form}: bad day kept for the extra-information box")
        vals=fill_pdf.build_values({},fb) if form=="aa" else fill_pdf.dla_values({},fb)
        box={"aa":"354","dla":"89"}[form]
        check(vals.get(box,"").startswith("A recent bad day: "+BAD),f"{form}: bad day in box {box}: {vals.get(box,'')[:60]!r}")
        V,_,_=WF.pdf_values(form,d)
        f1={"aa":"17_1","dla":"25_1"}[form]; f2={"aa":"17_2","dla":"25_2"}[form]
        check(V.get(f1)=="Dr Shah" and V.get(f2) in ("Consultant or specialist","Paediatrician or specialist"),f"{form}: professional's name from the last screen in {f1}: {V.get(f1)!r}")
        check(WF.prefill(form,d).get("pr_name")=="Dr Shah",f"{form}: name shown filled in on the health screen")
    else:
        check("A recent bad day" in fb["answers"]["other"] and "missed my breakfast" in fb["answers"]["other"],"pip: bad day in the other-information box")
    tt=" ".join(I.topic_texts(form,d)[1].values())
    check("Dr Patel, Hill Surgery" in tt,f"{form}: names in what you told us")
# carer filling in AA: their words are labelled as theirs
d,_=walk("aa",{"who":"parent","name":"Mum","signer":"appointee"},{**AA_STEPS,"finish":{"badday":"Last week Mum couldn't get up until I came at 11."}},stop="more")
check(I.fallback_draft("aa",d).get("badday_note","").startswith("A recent bad day, described by the person helping me: Last week Mum"),"aa carer: bad-day note says who wrote it")
# ---- 4. the writer uses the bad day once; if it does, it is not repeated in the extra box ----
d,_=walk("aa",{"who":"me"},{**AA_STEPS,"finish":filled("aa")},stop="more")
F=writer.facts("aa",d); bid=[f["id"] for f in F if f["text"].startswith(writer.BADDAY)][0]
def fake(use):
    def f(chain,system,user,schema=None,purpose="",**k):
        if purpose=="draft":
            check("'One recent bad day' fact: use it ONCE" in system and "Needs help but no one is there to help' facts" in system,"writer rules for the new facts")
            return {"boxes":[{"topic":"29","sentences":[{"text":"Last Tuesday I couldn't get out of bed until my daughter came at 11.","facts":[bid] if use else []}]}]}
        if purpose=="extras":
            check("Never invent a name, surgery, hospital or job title" in system,"extras rule: never invent names")
            return {"checklist":["A letter from your consultant, Dr Shah"],"gp_letter":"Dear Dr Patel,","notes_for_user":[]}
        if purpose=="verify":
            v=json.loads(user); v=v["sentences"] if isinstance(v,dict) else v; return {"verdicts":[{"n":x["n"],"supported":True,"problem":"none"} for x in v]}
        return {}
    return f
real=cl.call
cl.call=fake(True); r=writer.write("aa",d)
check("Last Tuesday" in r["answers"]["29"] and "badday_note" not in r,"bad day used in a box: not repeated in box 354")
cl.call=fake(False); r=writer.write("aa",d); cl.call=real
check(r.get("badday_note","").endswith(BAD),"bad day not used in a box: kept for box 354")
check(any("Dr Shah" in x for x in r["checklist"]),"checklist may name a person the customer gave")
# ---- 5. empty: nothing added ----
for form in ("aa","dla","pip"):
    d,_=walk(form,ABOUT[form],{**STEPS[form],"finish":{}},stop="more")
    F=" ".join(f["text"] for f in writer.facts(form,d))
    check(not re.search(r"bad day, in|no one is there|know about|own words: $",F),f"{form}: empty last screen adds no facts")
    fb=I.fallback_draft(form,d); allans=" ".join(fb["answers"].values())
    check("badday_note" not in fb and "no one is there to help" not in allans and "recent bad day" not in allans.lower(),f"{form}: empty adds nothing to the boxes")
    if form!="pip":
        vals=fill_pdf.build_values({},fb) if form=="aa" else fill_pdf.dla_values({},fb)
        check("bad day" not in vals.get({"aa":"354","dla":"89"}[form],""),f"{form}: empty bad day leaves the extra box alone")
        V,_,_=WF.pdf_values(form,d); check(not V.get({"aa":"17_1","dla":"25_1"}[form]),f"{form}: no professional, no name")
        check("pr_name" not in WF.prefill(form,d),f"{form}: no name prefilled")
# 'Dr Shah, St James's': the name goes in the name box and the place in the address line (their words, split at the comma)
d,_=walk("aa",{"who":"me"},{**AA_STEPS,"finish":{"people":["Consultant or specialist"],"know_2":"Dr Shah, St James's"}},stop="more")
V,_,_=WF.pdf_values("aa",d); check(V.get("17_1")=="Dr Shah" and V.get("17_3")=="St James's" and WF.prefill("aa",d).get("pr_where")=="St James's",f"name and place split: {V.get('17_1')!r} {V.get('17_3')!r}")
d,_=walk("aa",{"who":"me"},{**AA_STEPS,"finish":{"people":["Consultant or specialist"],"know_2":"Hill Surgery, Leeds"}},stop="more")
V,_,_=WF.pdf_values("aa",d); check(V.get("17_1")=="Hill Surgery, Leeds","no title: kept whole as typed")
# request letters (Plus): the typed name is used as typed, never made up
import premium
dd={"who":"me","people":["GP","Consultant or specialist","Carer"],"know_names":{"GP":"Dr Patel, Hill Surgery","Consultant or specialist":"Dr Shah, St James's"}}
sl=premium.supporting_letters("Form Sorted","aa",{},{"answers":{}},dd["people"],dd)
check("For: GP (Dr Patel, Hill Surgery)" in sl and "Dear Dr Patel," in sl and "Dear Dr Shah," in sl and "For: Carer." in sl,"request letters use the typed names")
sl=premium.supporting_letters("Form Sorted","aa",{},{"answers":{}},["GP","Consultant or specialist"],{"who":"me","people":["GP","Consultant or specialist"]})
check("Dear Dr ____," in sl and "Dear consultant or specialist," in sl and "Dr Patel" not in sl,"no typed names: placeholders, nothing invented")
# ticked a professional without a name: never invented
d,_=walk("aa",{"who":"me"},{**AA_STEPS,"finish":{"people":["Consultant or specialist"]}},stop="more")
V,_,_=WF.pdf_values("aa",d); check(V.get("17_1")=="My consultant or specialist" and "Dr" not in V.get("17_1",""),f"no name typed: no name invented ({V.get('17_1')!r})")
# the sentence the live AA run wrote (30 Oct) passes the number check against the bad-day fact
live="On one recent bad day, last Tuesday, I couldn't get up until 11. My daughter came and helped me up and get washed, and I missed my breakfast."
check(writer.rule_check(live,[writer.BADDAY+BAD])==[],f"live bad-day sentence passes the number check: {writer.rule_check(live,[writer.BADDAY+BAD])}")
check(writer.rule_check("On one recent bad day I couldn't get up until 9.",[writer.BADDAY+BAD])!=[],"a changed time is still caught")
print("last screen:", "OK" if not FAILS else f"{len(FAILS)} FAILED"); raise SystemExit(1 if FAILS else 0)

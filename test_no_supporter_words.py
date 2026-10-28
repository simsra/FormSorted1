"""28 Oct (Simon): we never draft the supporter's statement. The note only says what to write and where."""
import os, json; os.environ.setdefault("DATABASE_URL",""); os.environ.setdefault("SUPABASE_URL","")
import llm, documents, intake as I, wholeform as WF, contsheet
from forms import FORMS
BAD=("carer_statement","Draft statement from someone who knows","I have taught","I help my partner","I am Margaret's daughter")
for form in ("aa","dla","pip","pipr","atw"):
    assert "carer_statement" not in llm.draft_system(form), form
    m=llm.MOCK; llm.MOCK=True; d=llm.draft([{"role":"user","content":"x"}],form); llm.MOCK=m
    if d is not None: assert "carer_statement" not in d and not any(b in json.dumps(d) for b in BAD[2:]), form
# old stored drafts (made before this change) still carry it: never shown
old={"answers":{"30":"x"},"checklist":[],"notes_for_user":[],"gp_letter":"","carer_statement":"I am her daughter and I help every day."}
for form in ("aa","dla","pip"):
    h=documents.pack_html("FormSorted",{},old,"99") if form=="aa" else documents.pack_form("FormSorted",{},old,"99",form)
    assert "I am her daughter" not in h and not any(b in h for b in BAD), form
assert llm._strip(dict(old))=={k:v for k,v in old.items() if k!="carer_statement"}
assert all(not I.fallback_draft(f,{"wf_v":1,"rows":{}}).get("carer_statement") for f in ("aa","dla"))
assert "Statement from someone" not in dict((t,l) for t,l,_ in FORMS["dla"]["topics"])["statement"]
# the note says what to write and where, never words for them
for form,ref in (("aa","question 56 (page 28)"),("dla","question 38 (pages 10 and 11)")):
    args=WF.statement_note(form,{"wf":{"stmt":"family"}},{"other_names":"Margaret"}); txt=json.dumps(args)
    assert ref in txt, (form,txt)
    pdf=contsheet.supporter_note(form,*args); assert pdf[:4]==b"%PDF"
print("no drafted supporter statement ok")
# Plus request letters: from the customer, asking the person to write in their own words. No supporter-voice statement, no sign-off for them.
import premium, re, html as H
SUP=re.compile(r"\bI am (?:\w+'s|her|his|their) (?:GP|carer|daughter|son|teacher|family carer|consultant)|the following is correct|To whom it may concern|"
               r"Signed:|Role:|Name: _|Date: _|I confirm|I can confirm|I have known|I have taught|I help (?:my|her|him)", re.I)
cases=[("aa",{"who":"parent","name":"Margaret","people":["GP","Family carer","Social worker"]},{"answers":{"30":"Margaret needs help getting on and off the toilet on 7 days a week.","34":"Margaret falls 3 to 5 times a month.","29":""},"no_difficulty":["29"]}),
       ("aa",{"who":"me","people":[]},{"answers":{"32":"I need help with buttons."}}),
       ("dla",{"name":"Leo","people":["Teacher or SENCo","Paediatrician"]},{"answers":{"65":"Leo has fits about once a week.","supervision_day":"Leo needs watching all day."}}),
       ("pip",{"who":"me","people":["Family or friend","GP"]},{"answers":{"a4":"I need help washing my hair on most days."}}),
       ("pipr",{"who":"me","people":["Consultant"]},{"answers":{"a1":"I can't stand to cook for long."}}),
       ("atw",{"people":["Support worker"]},{"answers":{"barriers":"Long meetings are hard for me."}})]
for form,I_,d in cases:
    h=premium.supporting_letters("FormSorted",form,{"other_names":I_.get("name",""),"surname":"Test" if I_.get("name") else ""},d,I_.get("people"),I_)
    t=H.unescape(re.sub(r"<[^>]+>"," ",h)); t=re.sub(r"\s+"," ",t)
    assert not SUP.search(t), (form,SUP.search(t).group(0))
    for a in d["answers"].values():
        if a: assert a not in t, (form,a)                                  # the customer's answers are not pasted in for them
    assert "in your own words" in t and "only write what you know to be true" in t and "[Your name]" in t, form
    assert t.count("Dear ")==len(I_.get("people") or [1,2]), form
    if form=="aa": assert "question 56 (page 28)" in t
    if form=="dla": assert "question 38 (pages 10 and 11)" in t
    if form=="aa" and I_.get("who")=="parent": assert "falls and stumbles" in t and "getting out of bed" not in t and "toilet needs" in t   # topics only where they described help
    if form=="dla": assert "diagnoses" in t.split("Paediatrician")[1] and "diagnoses" not in t.split("Paediatrician")[0].split("Teacher or SENCo")[-1]
assert "supporting letters to sign" not in json.dumps(FORMS) and "drafted for your GP" not in json.dumps(premium.PLUS_ITEMS)
print("request letters ok")

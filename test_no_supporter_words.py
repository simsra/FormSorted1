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

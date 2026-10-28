"""28 Oct (Simon): 'Print, sign, post' guide per form; NI number and bank details are no longer the customer's job (only signature and date)."""
import os, re; os.environ.setdefault("DATABASE_URL",""); os.environ.setdefault("SUPABASE_URL","")
import documents, psp
d={"answers":{"30":"x","conditions":"y","a1":"z"},"checklist":[],"notes_for_user":[],"gp_letter":""}
WANT={"aa":["question 20 on page 9","question 64 on page 30","question 15 on page 5","Questions 55 to 62 on page 28","Freepost DWP Attendance Allowance"],
      "dla":["question 39 on page 12","Declaration on page 38","Question 38 on pages 10 and 11","sign and date each sheet","Freepost DWP DLA Child"],
      "pip":["paper PIP2 DWP sent you","envelope DWP sent you"],"pipr":["Section 1","Section 3","paper AR1 DWP sent you","envelope DWP sent you"]}
BAD=re.compile(r"Add the (child's )?NI number|NI number, bank details|we claim|we submit|online|href=|Stripe|\bAI\b",re.I)
for form,want in WANT.items():
    for tier in ("99","199"):
        for hd in (False,True):
            h=documents.pack_form("FormSorted",{},d,tier,form,hand_details=hd)
            assert "Print, sign, post: step by step" in h, form
            for w in want: assert w in h, (form,w)
            g=psp.html_section(form,hand_details=hd)
            assert not BAD.search(g), (form,BAD.search(g))
            for k in ("Actual size","black ink","correction fluid","copies of your evidence, never originals","Keep a copy"): assert k in g, (form,k)
            assert ("write the National Insurance number and bank details by hand" in g)==(hd and form in ("aa","dla")), (form,hd)
    assert "Add the NI number, bank details" not in documents.pack_form("FormSorted",{},d,"99",form)
assert "Freepost" not in psp.html_section("pip")+psp.html_section("pipr")
assert psp.html_section("atw")==""
import contsheet, subprocess, tempfile
b=contsheet.continuation("DLA1A","10/25","Test",[("Q89","word "*1500)])
f=tempfile.NamedTemporaryFile(suffix=".pdf",delete=False); f.write(b); f.close()
t=subprocess.run(["pdftotext",f.name,"-"],capture_output=True,text=True).stdout
assert t.count("Signature:")==t.count("Page ")>=2, t.count("Signature:")   # DLA: sign and date every sheet
print("print sign post ok")

"""The supporter note must point at the statement box's real question number and pages on the current PDF."""
import re, wholeform as W
from pypdf import PdfReader
for form,pdf in (("aa","aa1.pdf"),("dla","dla1a.pdf")):
    qn,_=W.STATEMENT[form]; pages=W.statement_pages(form); rd=PdfReader(pdf)
    txt=rd.pages[pages[0]-1].extract_text()
    assert re.search(rf"(^|\s){qn}\s+\S",txt), (form,qn,pages)
    for p in pages: assert f"{p} of {len(rd.pages)}" in rd.pages[p-1].extract_text(), (form,p)   # printed page number = PDF page
    print(form, W.statement_ref(form))
assert W.statement_ref("aa")=="question 56 (page 28)" and W.statement_ref("dla")=="question 38 (pages 10 and 11)"
print("statement ref ok")

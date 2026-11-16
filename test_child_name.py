"""16 Nov 2026 bug: DLA 'Your child's details' showed another person's name (the professional typed on the last
screen) in the child's first-names box. The claimant's / child's name boxes must come ONLY from the name given for
the person the form is about; the carer's / parent's / helper's name stays in their own boxes. No network."""
import os, tempfile, re
os.environ.setdefault("SQLITE_PATH",os.path.join(tempfile.mkdtemp(),"t.db")); os.environ["WF_LOOKUPS"]="0"
from pypdf import PdfReader
import wholeform as WF, fill_pdf
FAIL=0
def check(ok,msg):
    global FAIL; print(("ok  " if ok else "FAIL")+" "+msg); FAIL+=0 if ok else 1
def boxval(html,n):
    m=re.search(r'<input name="%s" [^>]*value="([^"]*)"'%n,html); return m.group(1) if m else None
CARER_F,CARER_S="Carla","Carerson"; CHILD="Leo"; NURSE="Sarah Jones"
# ---- DLA: child's name from the about step only; never the nurse's, never the parent's ----
d={"name":CHILD,"rel":"Mum","age":"5to15","people":["Nurse or health visitor","Teacher or SENCo"],
   "know_names":{"Nurse or health visitor":NURSE,"Teacher or SENCo":"Mr Brown"},"wf_v":1,"wf":{"p_first":CARER_F,"p_surname":CARER_S}}
p=WF.prefill("dla",d)
check(p.get("first")==CHILD,f"dla: child's first names prefilled from the child's name ({p.get('first')!r})")
check(p.get("pr_name")==NURSE,"dla: the health visitor's name still goes to the professional's box")
check("surname" not in p and "othernames" not in p,"dla: surname never guessed")
h=WF.section_body("dla","child",d)
check(boxval(h,"first")==CHILD and boxval(h,"surname")=="" and boxval(h,"othernames")=="",f"dla child screen: first={boxval(h,'first')!r} surname={boxval(h,'surname')!r}")
check(CARER_F not in h and CARER_S not in h and NURSE not in h,"dla child screen: no carer or nurse name anywhere")
# no child name given: stays blank (nothing borrowed from anyone else)
d2={"name":"","rel":"Dad","age":"5to15","people":["Nurse or health visitor"],"know_names":{"Nurse or health visitor":NURSE},"wf_v":1,"wf":{"p_first":CARER_F,"p_surname":CARER_S}}
h2=WF.section_body("dla","child",d2)
check(boxval(h2,"first")=="" and "first" not in WF.prefill("dla",d2),f"dla, no child name: first-names box blank ({boxval(h2,'first')!r})")
# parent screen keeps the carer's own name; the PDF puts each name in its own section
d["wf"].update({"first":CHILD,"surname":"Smith","p_title":"Mrs"})
P=WF.personal("dla",d)
check(P.get("other_names")==CHILD and P.get("surname")=="Smith","dla personal: child's name in the child's fields")
check(P.get("parent_other_names")==CARER_F and P.get("parent_surname")==CARER_S,"dla personal: carer's name in the parent fields")
out=tempfile.mktemp(suffix=".pdf"); fill_pdf.fill_form("dla",P,{"answers":{},"extra":{}},out)
F={k:str(v.get("/V","")) for k,v in PdfReader(out).get_fields().items()}
check(F.get("3")==CHILD and F.get("2")=="Smith",f"dla PDF part 1 (child): {F.get('3')!r} {F.get('2')!r}")
check(F.get("74")==CARER_F and F.get("73")==CARER_S,f"dla PDF parent section: {F.get('74')!r} {F.get('73')!r}")
# ---- AA for someone else: the claimant's name from the about step; the helper's name only in the helper boxes ----
for who in ("parent","partner","other"):
    a={"who":who,"name":"Rose","signer":"appointee","people":["Consultant or specialist"],"know_names":{"Consultant or specialist":"Dr Shah"},"wf_v":1,"wf":{"h_name":"Carla Carerson"}}
    pa=WF.prefill("aa",a); ha=WF.section_body("aa","you",a)
    check(pa.get("first")=="Rose" and boxval(ha,"first")=="Rose" and boxval(ha,"surname")=="",f"aa for someone else ({who}): claimant's first names = their name ({boxval(ha,'first')!r})")
    check("Dr Shah" not in ha and "Carla" not in ha,f"aa ({who}): no professional or helper name on the claimant's screen")
    check(pa.get("pr_name")=="Dr Shah","aa: professional name still prefilled on the health screen")
a2={"who":"parent","name":"Mum","people":["Consultant or specialist"],"know_names":{"Consultant or specialist":"Dr Shah"},"wf_v":1,"wf":{}}
check("first" not in WF.prefill("aa",a2),"aa: 'Mum' is not a name; box left blank")
m={"who":"me","name":"","people":["Consultant or specialist"],"know_names":{"Consultant or specialist":"Dr Shah"},"wf_v":1,"wf":{}}
check("first" not in WF.prefill("aa",m) and boxval(WF.section_body("aa","you",m),"first")=="","aa for me: first names blank (browser autofill only)")
print("test_child_name:", "OK" if not FAIL else f"{FAIL} FAILED"); raise SystemExit(1 if FAIL else 0)

"""Regression test for the 28 Oct 'so much missing / wrong on the form' report (orders 3U5OdoHUCk AA, LDkNZfAv0h DLA).
Reproduces both orders' taps (no personal data) and checks the filled PDF:
 - 'No difficulty' taps answer the form's Yes/No question No; they never tick 'Yes, difficulty' and never put text in the box
   (before: 'I have no difficulty getting in and out of bed' ticked AA Q29 Yes + 'difficulty getting out of bed').
 - every topic the customer tapped a difficulty for has its answer in the PDF.
 - aids go into the aids table (AA Q27, DLA Q41); DLA specialist school / EHCP are ticked; dates are DD/MM/YYYY."""
import json,os,sys,tempfile
sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
import intake as INTAKE, ticks as TICKS, fill_pdf
from pypdf import PdfReader
OK={"lvl":"ok"}; H=lambda *c:{"hard":True,"help":True,"lvl":"help","c":list(c),"std":[],"freq":"","time":"10_30","days":"7","x":""}
fails=[]
def check(c,msg):
    if not c: fails.append(msg); print("FAIL",msg)
def fields(path): return {k:(v.get("/V") or "") for k,v in (PdfReader(path).get_fields() or {}).items()}
def run(form,I,answers,personal):
    t=INTAKE.ticks(form,I); nd=INTAKE.no_difficulty(form,I)
    props=TICKS.propose_tapped(form,answers,t,nd); chosen={x["field"]:x["proposed"] for x in props if x["proposed"]}
    check(TICKS.validate(form,chosen)==chosen if isinstance(TICKS.validate(form,chosen),dict) else True,f"{form}: ticks validate")
    d={"answers":answers,"no_difficulty":nd,"extra":{"aids":INTAKE.aids_list(I)}}
    out=os.path.join(tempfile.mkdtemp(),"o.pdf"); fill_pdf.fill_form(form,personal,d,out,ticks=chosen)
    return chosen,nd,fields(out)

# ---- AA (order 3U5OdoHUCk): only washing and dressing are difficult ----
I={"who":"parent","name":"Chase","conds":[{"name":"Arthritis","since":"2020","treat":["tabs"],"tx":""}],
   "rows":{"bed":OK,"toilet":OK,"wash":H("in","every","wrong"),"dress":H("feet"),"indoors":OK,"eat":OK,"meds":OK,"comm":OK,"social":OK},
   "falls":"0","alone":"always","eye":["wander"],"night":["meds"],"nights":"7","ntimes":"1","nmins":"lt10","watch":"no",
   "aids":["Walking stick"],"else":{"aids":"Grab rail"}}
A={"29":"I have no difficulty getting in and out of bed.","30":"I have no difficulty using the toilet.",
   "31":"I need help every time I wash, bathe or shower, 7 days a week. I have difficulty getting in or out of the bath or shower.",
   "32":"I need help with dressing and undressing 7 days a week. I have difficulty with socks and shoes.",
   "33":"I have no difficulty moving around indoors. I use a walking stick.","34":"I have had no falls in the last year.",
   "35":"I have no difficulty eating and drinking.","36":"I have no difficulty with medicines and treatment.",
   "37":"I have no difficulty communicating.","39":"I have no difficulty with hobbies, seeing people or faith activities.",
   "40":"I need someone to keep an eye on me because I may wander.","42":"I need help at night with medicines 7 nights a week, 1 time a night."}
ch,nd,f=run("aa",I,A,{"surname":"Test","other_names":"Chase","dob":"1950-03-07","addr1":"1 Test Street"})
for q in ("29","30","33","35","36","37","39"):
    check(ch.get(f"x{q}")=="/No",f"AA Q{q}: no difficulty must be answered No, got {ch.get('x'+q)!r}")
    check(not [k for k,v in ch.items() if k.startswith(f"x{q}-") and v not in ("/No",)],f"AA Q{q}: no sub-tick/'tell us more' tick for a no-difficulty question: {[k for k in ch if k.startswith('x'+q+'-')]}")
check(ch.get("x34")=="/No","AA Q34: no falls -> No")
check(ch.get("x29-7")=="/No","AA Q29 'anything else to tell us' -> No for a no-difficulty question")
for q in ("31","32","40","42"): check(ch.get(f"x{q}")=="/Yes",f"AA Q{q}: tapped difficulty -> Yes")
from questions import CARE_QUESTIONS
box={str(q):fld for q,_,_,fld in CARE_QUESTIONS}
for q in ("29","30","33","35","36","37","39"): check(not f.get(box[q]),f"AA Q{q}: 'no difficulty' sentence must not go in the 'tell us' box: {f.get(box[q])!r}")
for q in ("31","32","40","42"): check(bool(f.get(box[q])) or "Question "+q in json.dumps(f),f"AA Q{q}: tapped difficulty answer missing from the PDF")
check(f.get("27-1")=="Walking stick" and f.get("27-5")=="Grab rail",f"AA Q27 aids table: {f.get('27-1')!r} {f.get('27-5')!r}")
check("07/03/1950" in json.dumps(f) and "1950-03-07" not in json.dumps(f),"AA date of birth must be DD/MM/YYYY")

# ---- DLA (order LDkNZfAv0h): care difficulties, eating/medicines/senses/supervision/development/walking all fine ----
C=lambda *c:{**H(*c),"lvl":"cant"}
I={"name":"Krillian","rel":"Mum","age":"5to15","conds":[{"name":"Autism","since":"2022","treat":["tabs"],"tx":""}],
   "rows":{"toilet":C("long"),"wash":C("long","wrong"),"dress":C("long"),"eat":OK,"indoors":C("long","wrong"),"meds":OK,"see":OK,"hear":OK,
           "speak":OK,"comm":OK,"superv":OK,"dev":OK,"walk":OK,"out":H("road")},
   "bad":"7","varies":"varies","aids":["Buggy or wheelchair","Glasses"],"school":["one","special","ehcp","transport"],"nn":["night_wander"],
   "nnum":{"night_wander":{"n":"7","t":"4","m":"60"}}}
A={"conditions":"Autism since 2022.","daycare":"Krillian needs help with the toilet, washing, dressing and moving indoors. He has no difficulty eating and drinking.",
   "senses":"Krillian has no difficulty seeing, hearing, speaking or communicating.","supervision_day":"Krillian has no difficulty with supervision during the day.",
   "development":"Krillian has no difficulty with development.","walking":"Krillian has no difficulty walking.",
   "outdoors":"Krillian needs someone with him near roads.","school":"Krillian goes to a specialist school with 1:1 support and an EHCP.",
   "night":"Krillian wanders at night 7 nights a week."}
ch,nd,f=run("dla",I,A,{"surname":"Test","other_names":"Krillian","dob":"2014-10-08"})
for q in ("44","59","60","61","62","63","64","66","67"): check(ch.get(q)=="/No",f"DLA Q{q}: no difficulty must be No, got {ch.get(q)!r}")
for q in ("55","56","57","58","49","70","68","36","41"): check(ch.get(q)=="/Yes",f"DLA Q{q}: tapped -> Yes, got {ch.get(q)!r}")
check(ch.get("37_1")=="/Educational Health Care Plan","DLA Q37 EHCP ticked")
check(f.get("41_1")=="Buggy or wheelchair" and f.get("41_4")=="Glasses",f"DLA Q41 aids table: {f.get('41_1')!r} {f.get('41_4')!r}")
check("08/10/2014" in json.dumps(f) and "2014-10-08" not in json.dumps(f),"DLA date of birth must be DD/MM/YYYY")
allv=json.dumps(f)
for k in ("senses","supervision_day","development","walking"): check(A[k] not in allv,f"DLA {k}: 'no difficulty' text must not be on the form")
for k in ("daycare","outdoors","school","night"): check(A[k][:40] in allv,f"DLA {k}: tapped difficulty answer missing from the PDF")
# negation: the text fallback (non-tap orders) must not read 'no difficulty ... out of bed' as a difficulty
p={x["field"]:x["proposed"] for x in TICKS.propose("aa",{"29":"I have no difficulty getting in and out of bed."})}
check(p.get("x29-2","")=="","text fallback: 'no difficulty getting in and out of bed' must not tick 'difficulty getting out of bed'")
print("FAILED" if fails else "OK", f"test_fill_gaps: {len(fails)} failure(s)"); sys.exit(1 if fails else 0)

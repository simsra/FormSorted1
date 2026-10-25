"""Fill the official AA1 PDF (AcroForm) with prepared answers. Text fields only; tick boxes listed for the user."""
import os
from pypdf import PdfReader, PdfWriter
from questions import CARE_QUESTIONS, EXTRA_FIELDS, PERSONAL_FIELDS, CONDITION_FIELDS
HERE=os.path.dirname(__file__)
def build_values(personal, draft):
    v={}
    for k,f in PERSONAL_FIELDS.items():
        if personal.get(k): v[f]=personal[k]
    for q,_,_,f in CARE_QUESTIONS:
        a=draft["answers"].get(str(q),"")
        if a: v[f]=a
    for k,f in EXTRA_FIELDS.items():
        if draft.get("extra",{}).get(k): v[f]=draft["extra"][k]
    for c,fs in zip(draft.get("conditions",[]),CONDITION_FIELDS):
        for key,f in zip(("name","since","meds","dose"),fs):
            if c.get(key): v[f]=c[key]
    if draft.get("carer_statement"): v["344"]=draft["carer_statement"]
    return v
AA_LABELS={f:f"Question {q} ({t})" for q,t,_,f in CARE_QUESTIONS}
def fill(personal, draft, out_path):
    r=PdfReader(os.path.join(HERE,"aa1.pdf"))
    if r.is_encrypted: r.decrypt("")
    w=PdfWriter(); w.append(r)
    vals=fit(build_values(personal,draft),"aa1.pdf","354",AA_LABELS)
    for p in w.pages:
        w.update_page_form_field_values(p,vals,auto_regenerate=False)
    w.set_need_appearances_writer(True)
    with open(out_path,"wb") as f: w.write(f)
    return vals

# ---- Child DLA (DLA1A, GOV.UK version 10/25) ----
from forms import DLA_FIELDS, DLA_NIGHT_FIELDS, DLA_PERSONAL, DLA_CONDITION_FIELDS
def dla_values(personal, draft):
    a=draft.get("answers",{}); v={}
    for k,f in DLA_PERSONAL.items():
        if personal.get(k): v[f]=personal[k]
    j=lambda *ks:"\n\n".join(a[k] for k in ks if a.get(k))
    m={"42":a.get("42",""),"walking":a.get("walking",""),"65":a.get("65",""),"school_learning":a.get("school",""),
       "mobility_other":j("outdoors"),"care_other":j("daycare","supervision_day","senses","development","night"),
       "anything_else":a.get("other",""),"statement":draft.get("carer_statement","")}
    for k,txt in m.items():
        if txt: v[DLA_FIELDS[k]]=txt
    for k,fs in DLA_NIGHT_FIELDS.items():
        for val,f in zip(draft.get("extra",{}).get(k) or [],fs):
            if val: v[f]=str(val)
    if draft.get("extra",{}).get("care_start"): v["71"]=draft["extra"]["care_start"]
    for c,fs in zip(draft.get("conditions",[]),DLA_CONDITION_FIELDS):
        for key,f in zip(("name","since","meds","dose"),fs):
            if c.get(key): v[f]=c[key]
    return v
DLA_LABELS={"42_1":"Question 42","48_1":"Question 48","53":"Question 53","65_1":"Question 65","68_7":"Question 68","72":"Question 72","38_3":"Question 38"}
def fill_form(form, personal, draft, out_path):
    if form=="aa": return fill(personal,draft,out_path)
    r=PdfReader(os.path.join(HERE,"dla1a.pdf"))
    if r.is_encrypted: r.decrypt("")
    w=PdfWriter(); w.append(r); vals=fit(dla_values(personal,draft),"dla1a.pdf","89",DLA_LABELS)
    for p in w.pages: w.update_page_form_field_values(p,vals,auto_regenerate=False)
    w.set_need_appearances_writer(True)
    with open(out_path,"wb") as f: w.write(f)
    return vals

# ---- Fit long answers into boxes; overflow goes to the additional-information box ----
import re as _re
FS=8.0  # assumed font size (pt) for capacity estimate; conservative
NOTE=" (continued on the additional information page)"
def _rects(pdf):
    r=PdfReader(os.path.join(HERE,pdf))
    if r.is_encrypted: r.decrypt("")
    out={}
    for p in r.pages:
        for a in p.get("/Annots") or []:
            a=a.get_object(); par=a.get("/Parent"); n=a.get("/T") or (par.get_object().get("/T") if par else None)
            if n and "/Rect" in a:
                x0,y0,x1,y1=[float(v) for v in a["/Rect"]]; out[str(n)]=(abs(x1-x0),abs(y1-y0))
    return out
_RC={}
def capacity(pdf,name):
    if pdf not in _RC: _RC[pdf]=_rects(pdf)
    w,h=_RC[pdf].get(name,(0,0))
    cols=int((w-4)/(FS*0.52)); rows=max(1,int((h-2)/(FS*1.2)))
    return cols*rows - cols//2*rows//3  # allow ~1/6 for word-wrap waste
def fit(values, pdf, overflow_field, labels):
    """Trim each long value to its box; collect the rest into overflow_field with 'Qx continued:' headings."""
    spill=[]
    for f,txt in list(values.items()):
        if f==overflow_field or not isinstance(txt,str): continue
        cap=capacity(pdf,f)
        if cap<=0 or len(txt)<=cap: continue
        cut=txt[:max(0,cap-len(NOTE))]; cut=cut[:cut.rfind(" ")] if " " in cut else cut
        values[f]=cut.rstrip(" ,;")+"…"+NOTE
        spill.append(f"{labels.get(f,'Question '+f)} continued: …{txt[len(cut):].strip()}")
    if spill:
        prev=values.get(overflow_field,"")
        values[overflow_field]=("\n\n".join(spill)+("\n\n"+prev if prev else ""))
    return values

"""Fill the official AA1 / DLA1A PDFs (AcroForm) with approved answers and the tick boxes the customer confirmed.
Answers too long even for the extra-information box go onto continuation sheets appended to the same PDF."""
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
def fill(personal, draft, out_path, ticks=None):
    return _write("aa",build_values(personal,draft),personal,out_path,ticks)
VERSION={"aa":("AA1","11/25"),"dla":("DLA1A","10/25")}
OVERFLOW={"aa":("354","Question 63"),"dla":("89","Question 89")}
def _write(form, values, personal, out_path, ticks=None):
    import io, ticks as T, contsheet
    pdf={"aa":"aa1.pdf","dla":"dla1a.pdf"}[form]; ov,ovl=OVERFLOW[form]
    vals,spill=fit(values,pdf,ov,AA_LABELS if form=="aa" else DLA_LABELS,ovl)
    r=PdfReader(os.path.join(HERE,pdf))
    if r.is_encrypted: r.decrypt("")
    w=PdfWriter(); w.append(r)
    for p in w.pages: w.update_page_form_field_values(p,vals,auto_regenerate=False)
    if ticks: T.apply(w,T.validate(form,ticks))
    w.set_need_appearances_writer(True)
    if spill:
        name=" ".join(x for x in (personal.get("title"),personal.get("other_names"),personal.get("surname")) if x)
        code,ver=VERSION[form]
        for pg in PdfReader(io.BytesIO(contsheet.continuation(code,ver,name,spill))).pages: w.add_page(pg)
    with open(out_path,"wb") as f: w.write(f)
    vals["_continuation_sections"]=len(spill)
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
def fill_form(form, personal, draft, out_path, ticks=None):
    if form=="aa": return fill(personal,draft,out_path,ticks)
    return _write("dla",dla_values(personal,draft),personal,out_path,ticks)

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
CONT=" (continued on the extra sheet at the end of this form)"
def fit(values, pdf, overflow_field, labels, overflow_label="the additional information box"):
    """Trim each long value to its box; the rest goes to overflow_field under 'Qx continued:' headings.
    Whatever doesn't fit in overflow_field either is returned as continuation-sheet sections [(heading,text)]."""
    chunks=[]
    for f,txt in list(values.items()):
        if f==overflow_field or not isinstance(txt,str): continue
        cap=capacity(pdf,f)
        if cap<=0 or len(txt)<=cap: continue
        cut=txt[:max(0,cap-len(NOTE))]; cut=cut[:cut.rfind(" ")] if " " in cut else cut
        values[f]=cut.rstrip(" ,;")+"…"+NOTE
        chunks.append((f"{labels.get(f,'Question '+f)} continued",txt[len(cut):].strip()))
    prev=values.get(overflow_field,"")
    if prev: chunks.append((overflow_label,prev))
    if not chunks: return values,[]
    cap=capacity(pdf,overflow_field); room=cap-len(CONT)-2; box=[]; sheet=[]
    for h,t in chunks:
        piece=f"{h}: …{t}" if h!=overflow_label else t
        used=len("\n\n".join(box))
        if not sheet and used+len(piece)+2<=room: box.append(piece); continue
        if not sheet and room-used>200:   # split this chunk: start it in the box, finish it on the sheet
            k=room-used-2; part=piece[:k]; part=part[:part.rfind(" ")] if " " in part else part
            box.append(part.rstrip(" ,;")+"…"); sheet.append((h if h!=overflow_label else f"{overflow_label} continued","…"+piece[len(part):].strip()))
            continue
        sheet.append((h,t))
    values[overflow_field]="\n\n".join(box)+(CONT if sheet else "")
    return values,sheet

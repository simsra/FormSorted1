"""Fill the official AA1 / DLA1A PDFs (AcroForm) with approved answers and the tick boxes the customer confirmed.
Answers too long even for the extra-information box go onto continuation sheets appended to the same PDF."""
import os
from pypdf import PdfReader, PdfWriter
from questions import CARE_QUESTIONS, EXTRA_FIELDS, PERSONAL_FIELDS, CONDITION_FIELDS
HERE=os.path.dirname(__file__)
import re as _r
def uk_date(s):
    """'2014-10-08' -> '08/10/2014' (the forms ask for DD / MM / YYYY). Anything else is left as typed."""
    m=_r.match(r"^\s*(\d{4})-(\d{2})-(\d{2})\s*$",s or "")
    return f"{m[3]}/{m[2]}/{m[1]}" if m else s
DATE_KEYS=("dob","parent_dob")
AA_AIDS=[("27-1","27-3"),("27-5","27-7"),("27-9","27-11"),("27-13","27-15"),("27-17","27-19"),("27-21","27-23")]
DLA_AIDS=["41_1","41_4","41_7","41_10","41_13","14_16"]
def _personal(personal, mapping):
    return {f:(uk_date(personal[k]) if k in DATE_KEYS else personal[k]) for k,f in mapping.items() if personal.get(k)}
def build_values(personal, draft):
    v=_personal(personal,PERSONAL_FIELDS); nd=set(draft.get("no_difficulty") or [])
    for q,_,_,f in CARE_QUESTIONS:
        a=draft["answers"].get(str(q),"")
        if a and str(q) not in nd: v[f]=a   # a 'no difficulty' question is answered No: its box stays empty
    for aid,(f,_) in zip((draft.get("extra") or {}).get("aids") or [],AA_AIDS): v[f]=aid
    for k,f in EXTRA_FIELDS.items():
        if (draft.get("extra") or {}).get(k): v[f]=draft["extra"][k]
    for c,fs in zip(draft.get("conditions",[]),CONDITION_FIELDS):
        for key,f in zip(("name","since","meds","dose"),fs):
            if c.get(key): v[f]=c[key]
    _badday(v,"354",draft)
    # Q56 (box 344, page 28 of the AA1 11/25) is the supporter's own statement: never our words. It is left blank; a note goes with the pack.
    return v
AA_LABELS={f:f"Question {q} ({t})" for q,t,_,f in CARE_QUESTIONS}
def _badday(v,f,draft):
    """Last screen: their recent bad day, word for word, leads the extra-information box (only when the writer didn't use it in a box)."""
    n=(draft.get("badday_note") or "").strip()
    if n: v[f]=n+("\n\n"+v[f] if v.get(f) else "")
def fill(personal, draft, out_path, ticks=None, extra=None):
    return _write("aa",build_values(personal,draft),personal,out_path,ticks,extra)
VERSION={"aa":("AA1","11/25"),"dla":("DLA1A","10/25")}
OVERFLOW={"aa":("354","Question 63"),"dla":("89","Question 89")}
def merge_extra(form, values, extra):
    """Whole-form answers: (values, ticks, notes). Typed answers already drafted win; notes join the extra-information box."""
    if not extra: return values, {}
    xv,xt,notes=extra; values=dict(values)
    ft=xv.pop("_fit_type",None) if isinstance(xv,dict) else None
    for f,t in (xv or {}).items():
        if t and not values.get(f): values[f]=t
    if form=="aa" and values.get("01-01i") and not values.get("01-01i 2"): values["01-01i 2"]=values["01-01i"]   # surname repeated on page 3
    if ft: values["65_1"]=f"Type of fits: {ft}"+("\n\n"+values["65_1"] if values.get("65_1") else "")
    if notes:
        ov=OVERFLOW[form][0]; values[ov]=((values.get(ov)+"\n\n") if values.get(ov) else "")+"\n".join(notes)
    return values, dict(xt or {})
def _write(form, values, personal, out_path, ticks=None, extra=None):
    import io, ticks as T, contsheet
    pdf={"aa":"aa1.pdf","dla":"dla1a.pdf"}[form]; ov,ovl=OVERFLOW[form]
    values,xticks=merge_extra(form,values,extra)
    if form=="aa" and not values.get("34-4") and values.get("34-1"):
        tk={**(xticks or {}),**(T.validate(form,ticks) if ticks else {})}
        if tk.get("x34-3")=="/Yes":   # 'help to get up after a fall' is Yes: its box is never left empty when we have the fall answer
            values["34-4"]="Please see my answer about what happens when I fall or stumble, above."
    vals,spill=fit(values,pdf,ov,AA_LABELS if form=="aa" else DLA_LABELS,ovl)
    r=PdfReader(os.path.join(HERE,pdf))
    if r.is_encrypted: r.decrypt("")
    w=PdfWriter(); w.append(r)
    wv={k:v for k,v in vals.items() if not k.startswith("_")}
    try: wv=set_layout(w,pdf,wv)
    except Exception as e: print("pdf layout skipped:",type(e).__name__,e)   # never lose the form over line-wrapping
    for p in w.pages: w.update_page_form_field_values(p,wv,auto_regenerate=False)
    if ticks: T.apply(w,T.validate(form,ticks))
    if xticks:   # whole-form ticks: each state was read off the PDF itself, so check it is still offered there
        opts=T.options(form); T.apply(w,{f:s for f,s in xticks.items() if f in opts and s in opts[f][1]})
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
    nd=set(draft.get("no_difficulty") or [])
    a={k:t for k,t in draft.get("answers",{}).items() if k not in nd}; v=_personal(personal,DLA_PERSONAL)
    for aid,f in zip((draft.get("extra") or {}).get("aids") or [],DLA_AIDS): v[f]=aid
    j=lambda *ks:"\n\n".join(a[k] for k in ks if a.get(k))
    m={"42":a.get("42",""),"walking":a.get("walking",""),"65":a.get("65",""),"school_learning":a.get("school",""),
       "mobility_other":j("outdoors"),"care_other":j("daycare","supervision_day","senses","development","night"),
       "anything_else":a.get("other","")}   # Q38 statement box is left for the supporter
    for k,txt in m.items():
        if txt: v[DLA_FIELDS[k]]=txt
    for k,fs in DLA_NIGHT_FIELDS.items():
        for val,f in zip(draft.get("extra",{}).get(k) or [],fs):
            if val: v[f]=str(val)
    _badday(v,DLA_FIELDS["anything_else"],draft)
    if draft.get("extra",{}).get("care_start"): v["71"]=draft["extra"]["care_start"]
    for c,fs in zip(draft.get("conditions",[]),DLA_CONDITION_FIELDS):
        for key,f in zip(("name","since","meds","dose"),fs):
            if c.get(key): v[f]=c[key]
    return v
DLA_LABELS={"42_1":"Question 42","48_1":"Question 48","53":"Question 53","65_1":"Question 65","68_7":"Question 68","72":"Question 72","38_3":"Question 38"}
def fill_form(form, personal, draft, out_path, ticks=None, extra=None):
    if form=="aa": return fill(personal,draft,out_path,ticks,extra)
    return _write("dla",dla_values(personal,draft),personal,out_path,ticks,extra)
def overlay(form, pdf_bytes, fields, tick=None):
    """Write private fields (NI number, bank details) into an already-built PDF, in memory only. Returns bytes."""
    import io
    r=PdfReader(io.BytesIO(pdf_bytes)); w=PdfWriter(); w.append(r)
    vals={k:v for k,v in fields.items() if v}; tk={k:v for k,v in (tick or {}).items() if v}
    for p in w.pages: w.update_page_form_field_values(p,vals,auto_regenerate=False)
    if tk:
        import ticks as T; opts=T.options(form); T.apply(w,{f:s for f,s in tk.items() if f in opts and s in opts[f][1]})
    w.set_need_appearances_writer(True); b=io.BytesIO(); w.write(b); return b.getvalue()

# ---- Wrap multi-line boxes ourselves, so every viewer shows the same lines inside the box ----
_FP=None
def _sw(t,size):
    """Width in pt of t in Helvetica (same metrics as the form's ArialMT)."""
    global _FP
    if _FP is None:
        from fpdf import FPDF
        _FP=FPDF(unit="pt"); _FP.add_page()
    _FP.set_font("Helvetica",size=size)
    t="".join(c if ord(c)<256 else "n" for c in t)   # core font is Latin-1 only: measure dashes, curly quotes etc. as an 'n'
    return _FP.get_string_width(t)
PAD=4.0; SAFE=0.93   # inner padding each side (pt) and slack for viewers whose text is a little wider than Helvetica
def wrap(text,width,size):
    """Lines of text broken at spaces so each fits width at size (very long words are split)."""
    lim=(width-2*PAD)*SAFE; out=[]
    for para in str(text).replace("\r","").split("\n"):
        line=""
        for wd in para.split(" "):
            cand=(line+" "+wd) if line else wd
            if _sw(cand,size)<=lim: line=cand; continue
            if line: out.append(line)
            while _sw(wd,size)>lim and len(wd)>1:   # split a word too long for the box
                k=len(wd)
                while k>1 and _sw(wd[:k],size)>lim: k-=1
                out.append(wd[:k]); wd=wd[k:]
            line=wd
        out.append(line)
    return out
SIZES=(10,9,8,7)
def layout(pdf,name,text):
    """(size, wrapped text) for a multi-line box: the largest of SIZES at which all lines fit its height."""
    if pdf not in _RC: _RC[pdf]=_rects(pdf)
    w,h=_RC[pdf].get(name,(0,0))
    for size in SIZES:
        lines=wrap(text,w,size)
        if len(lines)*size*1.17<=h-2*PAD/2: return size,"\n".join(lines)
    return SIZES[-1],"\n".join(wrap(text,w,SIZES[-1]))
def set_layout(w,pdf,vals):
    """Pre-wrap each multi-line value and set its box's font size (DA) to match. Returns the new values."""
    if pdf not in _RC: _RC[pdf]=_rects(pdf)
    from pypdf.generic import NameObject, TextStringObject
    sizes={}; vals=dict(vals)
    for n in _ML.get(pdf,()):
        if isinstance(vals.get(n),str) and vals[n].strip(): sizes[n],vals[n]=layout(pdf,n,vals[n])
    for p in w.pages:
        for a in p.get("/Annots") or []:
            a=a.get_object(); n=a.get("/T")
            if n in sizes: a[NameObject("/DA")]=TextStringObject(f"/ArialMT {sizes[n]} Tf 0 g")
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
                ff=int(a.get("/Ff") or (par.get_object().get("/Ff") if par else 0) or 0)
                if ff & 4096: _ML.setdefault(pdf,set()).add(str(n))
    return out
_RC={}; _ML={}
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

"""'Here's what you told me' (Simon, 16 Nov 2026): before paying, the customer sees their own answers, part by part, with Change.
Read straight from the same question HTML the intake uses (intake.section_body with their saved answers): only what they tapped
or typed, word for word. Nothing is written, guessed or summarised. National Insurance and bank details are never on these pages."""
import html,re
from html.parser import HTMLParser
SKIP=re.compile(r"(^|_)(ni|nino|bank|sort|acct|account)(_|$)",re.I)
VOID={"input","br","img","hr","meta","link","source","wbr","col","area","base","embed","param","track"}
class _P(HTMLParser):
    """Walks the question HTML in order. Each question (legend, card title, follow-up, box label) applies inside its own block;
    when the block ends, the question before it applies again. Records only ticked taps, chosen options and filled boxes."""
    def __init__(s):
        super().__init__(convert_charrefs=True); s.out=[]; s.qs=[(-1,None)]; s.dep=0; s.grab=None; s.gdep=0; s.buf=""; s.pend=None
        s.cond=None; s.sel=None; s.selq=None; s.opt=False; s.ta=False; s.xon=set(); s.lab=None; s.chipk=False
    @property
    def q(s): return s.qs[-1][1]
    def _add(s,q,a):
        a=(a or "").strip()
        if not a or not q: return
        if s.out and s.out[-1][0]==q:
            if a not in s.out[-1][1]: s.out[-1][1].append(a)
        else: s.out.append([q,[a]])
    def _qa(s):  # the question an answer belongs to (inside a condition's block: 'question · condition')
        if s.cond and s.dep>s.cond[0] and s.cond[2]==s.q: return s.cond[1]
        return s.q
    def handle_starttag(s,t,a):
        a=dict(a); c=(a.get("class") or "").split()
        if t not in VOID: s.dep+=1
        if t=="label": s.lab=(s.dep,"chip" not in c,bool(a.get("for"))); s.chipk="k" in c
        isq=t in("legend","h3") or (t=="p" and ("sub" in c or "fuq" in c)) or (t=="span" and ("ynq" in c or (s.lab and s.lab[1] and s.lab[0]==s.dep-1)))
        if isq and not s.grab:
            par=s.dep-1
            if t=="span" and s.lab and s.lab[2]: par-=1
            s.grab=t; s.gdep=s.dep; s.gpar=par; s.buf=""; return
        if t=="div" and "cond" in c: s.cdiv=s.dep
        if t=="input":
            n=a.get("name") or ""; ty=a.get("type") or "text"
            if SKIP.search(n) or ty in("hidden","file"): return
            if ty in("radio","checkbox"):
                if "checked" in a: s.pend=("else" if n.endswith("_xon") else "chip",n)
                if "checked" in a and n.endswith("_xon"): s.xon.add(n[:-4])
                return
            v=a.get("value","")
            if "elsebox" in c:
                if n.endswith("_x") and n[:-2] in s.xon: s._add(s._qa(),v)
                return
            s._add(s._qa() if s.q else a.get("aria-label"),_d(v) if ty=="date" else v)
        if t=="select": s.sel=a.get("name"); s.selq=(f"{s.cond[1]}: when did it start" if s.cond and s.dep>s.cond[0] else (a.get("aria-label") if not s.q else s.q))
        if t=="option" and s.sel and "selected" in a and a.get("value"): s.opt=True; s.buf=""
        if t=="textarea" and not SKIP.search(a.get("name") or ""): s.ta=True; s.buf=""
        if t=="span" and s.pend and not s.grab: s.grab="chip"; s.gdep=s.dep; s.buf=""
    def handle_endtag(s,t):
        if s.grab and s.dep==s.gdep:
            txt=re.sub(r"\s+"," ",s.buf).strip()
            if s.grab=="chip":
                kind,n=s.pend; s.pend=None
                if kind=="chip":
                    if s.chipk: s._add(s.q,txt); s.cond=(getattr(s,"cdiv",s.dep-2),txt,s.q)
                    else: s._add(s._qa(),txt)
            else:
                while s.qs[-1][0]>=s.gpar+1 and len(s.qs)>1: s.qs.pop()
                s.qs.append((s.gpar,txt))
            s.grab=None
        if t=="option" and s.opt: s._add(s.selq,s.buf.strip()); s.opt=False
        if t=="select": s.sel=None
        if t=="textarea" and s.ta: s._add(s._qa(),s.buf); s.ta=False
        if t=="label": s.lab=None
        if t not in VOID:
            s.dep-=1
            while len(s.qs)>1 and s.dep<s.qs[-1][0]: s.qs.pop()
            if s.cond and s.dep<s.cond[0]: s.cond=None
    def handle_data(s,d):
        if s.grab or s.opt or s.ta: s.buf+=d
def _d(v):
    m=re.match(r"(\d{4})-(\d\d)-(\d\d)$",v or ""); return f"{m.group(3)}/{m.group(2)}/{m.group(1)}" if m else v
def section(form,sec,d):
    import intake
    p=_P(); p.feed(intake.section_body(form,sec,d)); return [(q,a) for q,a in p.out if q and a]

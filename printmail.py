"""'Post it to me to sign': we print the completed pack and post it to the CUSTOMER, who signs it in ink and sends it to DWP
(Freepost return envelope or label for AA1/DLA1A; DWP's own envelope for PIP2/AR1). Included in Done for you Plus; an optional
paid add-on (POST_ADDON_PENCE, default 999 = £9.99) for Done for you. Every order can always download instead.
OFF unless PRINT_MAIL_ENABLED=1 (default 0: the option is not shown, nothing is posted, no print emails are sent).

Env:
  PRINT_MAIL_ENABLED=0|1        master switch (default 0)
  PRINT_PROVIDER=intelliprint   provider (PRINT_MAIL_PROVIDER is still read as a fallback). Default "none".
  INTELLIPRINT_API_KEY          API key (Authorization: Bearer <key>)
  INTELLIPRINT_TESTMODE=1|0     default 1: jobs are created in Intelliprint test mode ("not charged and are not sent").
                                Live posting needs INTELLIPRINT_TESTMODE=0 set on purpose.
  INTELLIPRINT_POSTAGE          default uk_second_class (any documented postage[service] value)
  INTELLIPRINT_INSERT_AA, INTELLIPRINT_INSERT_DLA
                                optional insert IDs (ins_...) for pre-printed Freepost DWP return envelopes kept in stock
                                by Intelliprint (their "inserts" value-added service, enabled on request). Without one, the
                                pack carries a cut-out Freepost address label instead.
  INTELLIPRINT_REQUIRE_INSERT=1 hold the order for review instead of posting without a return envelope.
  INTELLIPRINT_API_BASE         default https://api.intelliprint.net/v1 (tests point it at a local mock)
  POST_ADDON_PENCE              price of the add-on for Done for you orders, in pence (default 999). Charged as an inline
                                Checkout line item: no Stripe product or price is created for it.

API (https://www.intelliprint.net/reference): POST /prints (JSON), GET /prints/{id}. Mail item statuses: draft,
waiting_to_print, printing, enclosing, shipping, sent, returned, cancelled, invalid_address (+ 'delivered', an estimate,
sent by the letter.updated webhook)."""
import os, json, time, base64, io, threading, urllib.request, urllib.error
from fpdf import FPDF
HERE=os.path.dirname(os.path.abspath(__file__)); FONTS=os.path.join(HERE,"fonts")
def _env(k,d=""): return os.getenv(k,d).strip()
ENABLED=_env("PRINT_MAIL_ENABLED","0")=="1"
PROVIDER=(_env("PRINT_PROVIDER") or _env("PRINT_MAIL_PROVIDER") or "none").lower()
FORMS_POSTED=("aa","dla","pip","pipr")

# Return addresses, checked on GOV.UK on 28 Oct 2026. "Do not write anything except the freepost address on the
# envelope. You do not need a postcode or a stamp."
FREEPOST={
 "aa":{"address":"Freepost DWP Attendance Allowance","source":"https://www.gov.uk/attendance-allowance/how-to-claim"},
 "dla":{"address":"Freepost DWP DLA Child","source":"https://www.gov.uk/government/publications/disability-living-allowance-for-children-claim-form"},
}
# PIP2 and AR1 are DWP-issued forms with the claimant's own barcode and come with DWP's return envelope. GOV.UK gives no
# separate return address for them ("Freepost DWP PIP 1" is only for starting a claim), so we don't print one.
OWN_ENVELOPE={"pip":"PIP2","pipr":"AR1"}
FORM_CODE={"aa":"AA1","dla":"DLA1A","pip":"PIP2","pipr":"AR1"}
FORM_NAME={"aa":"Attendance Allowance claim form (AA1)","dla":"Disability Living Allowance for children claim form (DLA1A)",
           "pip":"PIP extra sheets for your 'How your disability affects you' form (PIP2)","pipr":"PIP extra sheets for your review form (AR1)"}
IN_PROGRESS=("submitted","draft","waiting_to_print","printing","enclosing","shipping")
FINAL=("sent","delivered","returned","cancelled","invalid_address")

class PrintError(Exception):
    def __init__(self,msg,kind="error",code="",retry=False): super().__init__(msg); self.kind=kind; self.code=code; self.retry=retry

def insert_for(form): return _env(f"INTELLIPRINT_INSERT_{form.upper()}") or None
def return_envelope(form):
    """('insert', id) | ('label', address) | ('own', form code) | (None, None)"""
    if form in OWN_ENVELOPE: return "own",OWN_ENVELOPE[form]
    if form in FREEPOST: return ("insert",insert_for(form)) if insert_for(form) else ("label",FREEPOST[form]["address"])
    return None,None

# ---------------- recipient (from the customer's details step) ----------------
def recipient(form,p):
    """Name + address from the details the customer gave. For DLA the pack goes to the parent at the child's address."""
    if form=="dla" and (p.get("parent_other_names") or p.get("parent_surname")):
        name=" ".join(x for x in (p.get("parent_title"),p.get("parent_other_names"),p.get("parent_surname")) if x)
    else: name=" ".join(x for x in (p.get("title"),p.get("other_names"),p.get("surname")) if x)
    line=", ".join(x.strip() for x in (p.get("addr1"),p.get("addr2"),p.get("addr3")) if x and x.strip())
    pc=(p.get("postcode") or "").strip().upper()
    return {"name":name.strip(),"line":line,"postcode":pc,"country":"GB"}
def missing_address(r):
    return [k for k,v in (("name",r["name"]),("address",r["line"]),("postcode",r["postcode"])) if not v]

# ---------------- the printed pack ----------------
# Posted to the CUSTOMER to sign and send back (AA1, PIP2 and AR1 need an ink signature, so we never post to DWP).
import re as _re, psp
ADDON_PENCE=int(_env("POST_ADDON_PENCE","999") or 999)   # 'Post it to me to sign' add-on for Done for you (£99); Plus includes it
REMIND_DAYS=(5,10)                                           # reminder emails after the pack is posted
class _Doc(FPDF):
    def __init__(self):
        super().__init__(format="A4"); self.add_font("D","",os.path.join(FONTS,"DejaVuSans.ttf")); self.add_font("D","B",os.path.join(FONTS,"DejaVuSans-Bold.ttf"))
        self.add_font("D","I",os.path.join(FONTS,"DejaVuSans.ttf")); self.add_font("D","BI",os.path.join(FONTS,"DejaVuSans-Bold.ttf"))
        self.set_auto_page_break(True,18); self.set_margins(20,20,20)
def html_pdf(h):
    """Our own HTML documents (answers, request letters) as plain printable A4. Links become plain text."""
    h=_re.sub(r"(?is)<(style|script|title|head)[^>]*>.*?</\1>","",h); h=_re.sub(r"(?is)<!doctype[^>]*>|</?(html|body|meta|link)[^>]*>","",h)
    h=_re.sub(r"(?is)</?(div|section|article|span|small|figure|figcaption|label|code)[^>]*>","",h)
    h=_re.sub(r"(?is)<pre[^>]*>(.*?)</pre>",lambda m:"<p>"+m.group(1).replace("\n","<br>")+"</p>",h)
    h=_re.sub(r"(?is)<a\b[^>]*>(.*?)</a>",r"\1",h); h=_re.sub(r"(?i)<(p|h[1-6]|li|ul|ol|em|strong|b|i)\s[^>]*>",r"<\1>",h)
    p=_Doc(); p.set_margins(18,16,18); p.add_page(); p.set_font("D","",11); p.write_html(h,font_family="D")
    return bytes(p.output())
def cover_sheet(form,rcpt,ret,brand="FormSorted",contents=()):
    """2 pages so the form starts on its own sheet when printed double-sided. Page 1 leaves the top-left address-window
    area empty (Intelliprint prints the recipient address; address_window=left): what's in the pack and the exact boxes
    to sign. Page 2: the step-by-step guide and how to send it back (Freepost label, envelope insert, or DWP's envelope)."""
    p=_Doc(); p.add_page(); code=FORM_CODE[form]; own=form in OWN_ENVELOPE
    p.set_y(100); p.set_font("D","B",18); p.multi_cell(0,9,"Sign here and post it back",new_x="LMARGIN",new_y="NEXT")
    p.set_font("D","",11); p.multi_cell(0,6,f"Your {code} pack from {brand}",new_x="LMARGIN",new_y="NEXT"); p.ln(3)
    hi=f"Dear {rcpt['name']}," if rcpt.get("name") else "Hello,"
    for t in (hi,(f"Here are your extra sheets for the {code} form DWP sent you, made from the answers you approved." if own
                  else f"Here is your {FORM_NAME[form]}, filled in from the answers you approved."),
              (f"We have not sent anything to DWP. You copy your answers onto the {code}, sign it in ink and post it yourself." if own
               else "We have not sent anything to DWP. You check it, sign it in ink and post it yourself.")):
        p.multi_cell(0,6,t,new_x="LMARGIN",new_y="NEXT"); p.ln(1)
    p.ln(2); p.set_font("D","B",12); p.cell(0,7,"Sign and date in black ink, by hand, here:",new_x="LMARGIN",new_y="NEXT"); p.set_font("D","",11)
    for s in psp.SIGN_BOXES[form]: p.multi_cell(0,6,"\u2610  "+s,new_x="LMARGIN",new_y="NEXT"); p.ln(1)
    p.multi_cell(0,6,"Do not type, paste or e-sign a signature, and do not use correction fluid.",new_x="LMARGIN",new_y="NEXT")
    if contents:
        p.ln(3); p.set_font("D","B",12); p.cell(0,7,"In this pack",new_x="LMARGIN",new_y="NEXT"); p.set_font("D","",11)
        for c in contents: p.multi_cell(0,6,"\u2022  "+c,new_x="LMARGIN",new_y="NEXT")
        if ret[0]=="insert": p.multi_cell(0,6,f"\u2022  A return envelope addressed to {FREEPOST[form]['address']}",new_x="LMARGIN",new_y="NEXT")
    p.add_page(); kind,val=ret
    p.set_font("D","B",14); p.cell(0,9,"Step by step",new_x="LMARGIN",new_y="NEXT"); p.set_font("D","",10)
    steps=[(h,t) for h,t in psp.steps(form) if h not in ("Print it","Print the extra sheets","Post it")]
    for i,(h,t) in enumerate(steps,1):
        p.set_font("D","B",10); p.multi_cell(0,5,f"{i}. {h}",new_x="LMARGIN",new_y="NEXT"); p.set_font("D","",10); p.multi_cell(0,5,t,new_x="LMARGIN",new_y="NEXT"); p.ln(1)
    p.ln(2); p.set_font("D","B",12); p.cell(0,8,"Sending it back",new_x="LMARGIN",new_y="NEXT"); p.set_font("D","",11)
    if kind=="insert":
        p.multi_cell(0,6,f"Use the return envelope in this pack. It is already addressed to {FREEPOST[form]['address']}. You do not need a stamp.",new_x="LMARGIN",new_y="NEXT")
    elif kind=="label":
        p.multi_cell(0,6,"Put the signed form in an envelope and write only this address on it, or cut out the label below and stick it on. Write nothing else on the envelope. You do not need a postcode or a stamp.",new_x="LMARGIN",new_y="NEXT")
        if p.get_y()>230: p.add_page()
        p.ln(5); y=p.get_y(); p.set_dash_pattern(dash=2,gap=2); p.rect(30,y,150,36); p.set_dash_pattern()
        p.set_xy(30,y+12); p.set_font("D","B",16); p.cell(150,10,val,align="C"); p.set_y(y+39); p.set_font("D","",9)
        p.cell(0,5,"Cut along the dotted line",align="C",new_x="LMARGIN",new_y="NEXT")
    elif kind=="own":
        p.multi_cell(0,6,dict(psp.steps(form))["Post it"],new_x="LMARGIN",new_y="NEXT")
    return bytes(p.output())
def build_pack(form,rcpt,ret,parts,brand="FormSorted"):
    """Cover sheet (2 pages) + each part [(label, pdf bytes)] in order (form first), as one PDF.
    Each part starts on a new sheet when printed double-sided."""
    from pypdf import PdfReader, PdfWriter
    if isinstance(parts,(bytes,bytearray)): parts=[(FORM_NAME[form],parts)]
    w=PdfWriter()
    for src in [cover_sheet(form,rcpt,ret,brand,[l for l,_ in parts])]+[b for _,b in parts]:
        if len(w.pages)%2: w.add_blank_page(width=595.28,height=841.89)
        for pg in PdfReader(io.BytesIO(src)).pages: w.add_page(pg)
    b=io.BytesIO(); w.write(b); return b.getvalue()

# ---------------- providers ----------------
class Provider:
    name="none"
    def send(self,job): raise PrintError("print-and-post provider is not configured","config")
    def status(self,print_id): raise PrintError("print-and-post provider is not configured","config")
class Intelliprint(Provider):
    name="intelliprint"
    def __init__(self):
        self.key=_env("INTELLIPRINT_API_KEY"); self.base=_env("INTELLIPRINT_API_BASE","https://api.intelliprint.net/v1").rstrip("/")
        self.testmode=_env("INTELLIPRINT_TESTMODE","1")!="0"; self.postage=_env("INTELLIPRINT_POSTAGE","uk_second_class")
    def _call(self,method,path,body=None):
        if not self.key: raise PrintError("INTELLIPRINT_API_KEY is not set","config")
        h={"Authorization":"Bearer "+self.key,"Accept":"application/json","User-Agent":"FormSorted/1.0 (+https://formsorted.com)"}
        data=None
        if body is not None: data=json.dumps(body).encode(); h["Content-Type"]="application/json"
        try:
            with urllib.request.urlopen(urllib.request.Request(self.base+path,data,h,method=method),timeout=60) as r: return json.loads(r.read() or b"{}")
        except urllib.error.HTTPError as e:
            try: err=(json.loads(e.read() or b"{}").get("error") or {})
            except Exception: err={}
            kind=err.get("type") or f"http_{e.code}"
            raise PrintError(f"{e.code} {kind}: {err.get('message') or e.reason}"+(f" (param {err['param']})" if err.get("param") else ""),kind,err.get("code",""),
                             retry=e.code==429 or e.code>=500 or kind in ("rate_limited","internal_error"))
        except (urllib.error.URLError,TimeoutError,OSError) as e: raise PrintError(f"network error: {e}","network_error",retry=True)
    def payload(self,job):
        body={"type":"letter","testmode":self.testmode,"confirmed":True,"reference":job["reference"][:100],
              "file":{"content":base64.b64encode(job["pdf"]).decode(),"name":job["filename"]},
              "recipients":[{"address":job["recipient"]}],
              "printing":{"double_sided":"yes","black_and_white":True},
              "postage":{"service":self.postage,"ideal_envelope":"c4"},
              "address_window":"left","confidential":True,"metadata":{"order":job["token"],"form":job["form"]}}
        if job.get("insert"): body["insert"]=job["insert"]
        return body
    def send(self,job):
        r=self._call("POST","/prints",self.payload(job))
        if not r.get("id"): raise PrintError("no print id in the response","invalid_response")
        return _summary(r)
    def status(self,print_id): return _summary(self._call("GET","/prints/"+urllib.request.quote(print_id,safe="")))
def _summary(r):
    L=(r.get("letters") or [{}])[0] or {}
    return {"print_id":r.get("id"),"letter_id":L.get("id"),"status":L.get("status") or ("waiting_to_print" if r.get("confirmed") else "draft"),
            "testmode":bool(r.get("testmode")),"pages":r.get("pages"),"sheets":r.get("sheets"),"returned":L.get("returned"),
            "tracking_number":L.get("tracking_number"),"shipped_date":L.get("shipped_date"),"cost":r.get("cost") or L.get("cost")}
PROVIDERS={"none":Provider,"intelliprint":Intelliprint}
def provider(): return PROVIDERS.get(PROVIDER,Provider)()
def live(): return ENABLED and PROVIDER in PROVIDERS and PROVIDER!="none"

# ---------------- job record on the order (orders.print_job, JSON) ----------------
def job_of(o):
    try: return json.loads(o["print_job"] or "null")
    except Exception: return None
def save_job(c,token,job):
    c.execute("update orders set print_job=? where token=?",(json.dumps(job),token)); c.commit()
_LOCKS={}; _LL=threading.Lock()
def lock(token):
    with _LL: return _LOCKS.setdefault(token,threading.Lock())

def dispatch(c,o,parts,brand="FormSorted",force=False):
    """Create the print job for one approved Plus order. Returns the job dict saved on the order.
    Never raises: any problem leaves the job as status 'held' with the reason (the caller notifies us)."""
    token=o["token"]; form=o["form"] or "aa"; old=job_of(o) or {}
    if old.get("status") in IN_PROGRESS+FINAL and not force: return old   # already posted (double submit / re-save)
    p=json.loads(o["personal"] or "{}"); rc=recipient(form,p); ret=return_envelope(form)
    job={"provider":PROVIDER,"status":"held","at":time.time(),"form":form,"attempts":int(old.get("attempts") or 0)+1,"history":old.get("history",[])[-20:],
         "recipient_postcode":rc["postcode"],"return":ret[0],"insert":ret[1] if ret[0]=="insert" else None}
    def hold(msg): job.update(status="held",error=msg[:300]); job["history"].append({"at":time.time(),"status":"held","error":msg[:200]}); save_job(c,token,job); return job
    if not live(): return hold("print-and-post is switched off (PRINT_MAIL_ENABLED / PRINT_PROVIDER)")
    if form not in FORMS_POSTED: return hold(f"form {form} is not printed")
    miss=missing_address(rc)
    if miss: return hold("missing "+", ".join(miss)+" in the customer's details")
    if ret[0]=="label" and _env("INTELLIPRINT_REQUIRE_INSERT")=="1": return hold(f"no return-envelope insert configured (INTELLIPRINT_INSERT_{form.upper()})")
    if not parts: return hold("no filled form PDF to print (pre-fill may be switched off for this form)")
    try:
        pdf=build_pack(form,rc,ret,parts,brand)
        r=provider().send({"token":token,"form":form,"pdf":pdf,"filename":f"{FORM_CODE[form]}-pack-{token[:8]}.pdf","recipient":rc,
                           "insert":job["insert"],"reference":f"{brand} {token[:8]} {FORM_CODE[form]}"})
    except PrintError as e: return hold(f"{e.kind}: {e}")
    except Exception as e: return hold(f"unexpected: {type(e).__name__}: {e}")
    job.update(r); job["submitted_at"]=time.time(); job.pop("error",None)
    job["history"].append({"at":time.time(),"status":job["status"],"letter_id":job.get("letter_id")})
    save_job(c,token,job); return job

def refresh(c,o):
    """Re-read the job's status from the provider (a webhook body is never trusted, only used as a nudge).
    Returns (job, event): event is 'sent' the first time it is posted, 'problem' when it is returned/cancelled/refused."""
    job=job_of(o)
    if not job or not job.get("print_id") or job.get("status") in ("delivered","cancelled","invalid_address","returned","held"): return job,None
    if not live(): return job,None
    try: r=provider().status(job["print_id"])
    except PrintError as e: job["last_check_error"]=str(e)[:200]; job["checked_at"]=time.time(); save_job(c,o["token"],job); return job,None
    before=job.get("status"); job.update({k:v for k,v in r.items() if v is not None}); job["checked_at"]=time.time()
    ev=None
    if job["status"]!=before:
        job.setdefault("history",[]).append({"at":time.time(),"status":job["status"]})
        if job["status"] in ("sent","delivered") and not job.get("sent_emailed_at"): ev="sent"
        if job["status"] in ("returned","cancelled","invalid_address"):
            ev="problem"; job["needs_review"]=True; job["error"]=f"letter {job['status']}"+(f": {job['returned'].get('reason')}" if isinstance(job.get("returned"),dict) else "")
    if job["status"] in ("sent","delivered") and not job.get("sent_at"): job["sent_at"]=job.get("shipped_date") or time.time()
    save_job(c,o["token"],job); return job,ev

# ---------------- wording ----------------
def customer_status(job):
    """(heading, sentence) for the customer's documents page, or None."""
    if not job: return None
    s=job.get("status")
    if s in ("sent","delivered"):
        when=time.strftime("%-d %B %Y",time.localtime(job.get("sent_at") or job.get("shipped_date") or time.time()))
        return "Posted",f"Your printed pack was posted to you on {when}. It usually arrives in 2 to 3 working days."
    if s in IN_PROGRESS: return "Being printed","We're printing your pack. We'll email you when it has been posted."
    if s=="returned": return "Came back to us","Your printed pack came back undelivered. We're looking into it and will email you."
    if s in ("held","invalid_address","cancelled"): return "Being checked","We're checking a detail before we post your printed pack. We'll email you. You can still download everything below."
    return None
def _what_to_do(o):
    f=o["form"] or "aa"
    if f in OWN_ENVELOPE: return f"copy your answers onto the {FORM_CODE[f]} DWP sent you, sign and date it in black ink in the boxes listed on the cover sheet, and post it with the extra sheets."
    return "sign and date it in black ink in the boxes listed on the cover sheet, and post it."
def _how_back(o,job):
    code=FORM_CODE.get(o["form"] or "aa","form"); ret=job.get("return")
    return {"insert":"Use the return envelope in the pack. You do not need a stamp.","label":"The pack shows the Freepost address to write on the envelope. You do not need a stamp.",
            "own":f"Post it in the envelope DWP sent with your {code}."}.get(ret,"")
def sent_email(brand,public,o,job):
    code=FORM_CODE.get(o["form"] or "aa","form")
    return (f"{brand}: your {code} pack has been posted",
            f"Your printed {code} pack has been posted to you. It usually arrives in 2 to 3 working days.\n\n"
            f"When it arrives: check it, then {_what_to_do(o)} {_how_back(o,job)}\n\n"
            f"Your documents are also here: {public}/documents/{o['token']}\nKeep this link private.\n\n{brand}")
def reminders_due(job,now=None):
    """Reminder days (5, 10) now due for a posted pack and not yet sent."""
    if not job or job.get("status") not in ("sent","delivered"): return []
    t0=job.get("sent_at") or job.get("shipped_date")
    if not t0: return []
    now=now or time.time(); done=job.get("reminded") or []
    return [d for d in REMIND_DAYS if d not in done and now-float(t0)>=d*86400]
def reminder_email(brand,public,o,job,day):
    code=FORM_CODE.get(o["form"] or "aa","form")
    when=time.strftime("%-d %B",time.localtime(float(job.get("sent_at") or job.get("shipped_date") or time.time())))
    keep=dict(psp.steps(o["form"] or "aa")).get("Keep a copy","")
    start=(" "+keep.split(". ",1)[1]) if (o["form"] or "aa") in ("aa","dla") and ". " in keep else ""   # same words as the guide
    return (f"{brand}: have you signed and posted your {code}?",
            f"We posted your printed {code} pack to you on {when}.\n\nIf you haven't yet: {_what_to_do(o)} {_how_back(o,job)}{start}\n\n"
            f"If you've already posted it, you can ignore this email.\n\nYour documents: {public}/documents/{o['token']}\nKeep this link private.\n\n{brand}")
def review_email(public,o,job):
    return (f"Print-and-post held: order {o['token'][:8]} ({o['form']})",
            f"A Plus print-and-post job did not go out and is held for review.\n\nOrder: {o['token'][:8]}\nForm: {o['form']}\nProvider: {job.get('provider')}\n"
            f"Reason: {job.get('error') or job.get('status')}\nAttempt: {job.get('attempts')}\n\nReview it at {public}/admin (Print holds).")
def submitted(o):
    """True once the pack has gone to the printer (NI / bank details kept for it can then be deleted)."""
    j=job_of(o); return bool(j and j.get("print_id") and j.get("status") not in ("held",))

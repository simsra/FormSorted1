"""Print-and-post for Done for you Plus orders. OFF unless PRINT_MAIL_ENABLED=1 (default 0: nothing is ever sent).

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
class _Doc(FPDF):
    def __init__(self):
        super().__init__(format="A4"); self.add_font("D","",os.path.join(FONTS,"DejaVuSans.ttf")); self.add_font("D","B",os.path.join(FONTS,"DejaVuSans-Bold.ttf"))
        self.set_auto_page_break(True,18); self.set_margins(20,20,20)
def cover_sheet(form,rcpt,ret,brand="FormSorted"):
    """2 pages so the form starts on its own sheet when printed double-sided. Page 1 leaves the top-left address-window
    area empty (Intelliprint prints the recipient address; address_window=left). Page 2: how to send it back."""
    p=_Doc(); p.add_page(); code=FORM_CODE[form]
    p.set_y(100); p.set_font("D","B",16); p.multi_cell(0,8,f"Your {code} pack from {brand}",new_x="LMARGIN",new_y="NEXT"); p.ln(3)
    p.set_font("D","",11)
    hi=f"Dear {rcpt['name']}," if rcpt.get("name") else "Hello,"
    para=[hi,f"Here is your {FORM_NAME[form]}, filled in from the answers you approved." if form in ("aa","dla") else f"Here are your {FORM_NAME[form]}, made from the answers you approved.",
          "We have not sent anything to DWP. You check it, sign it and post it yourself."]
    for t in para: p.multi_cell(0,6,t,new_x="LMARGIN",new_y="NEXT"); p.ln(2)
    p.set_font("D","B",12); p.cell(0,8,"What to do now",new_x="LMARGIN",new_y="NEXT"); p.set_font("D","",11)
    if form in ("aa","dla"):
        steps=[f"Read every page of the {code} form. If anything is wrong, change it in pen.",
               "Sign and date the declaration at the end of the form. We have left it blank: only you can sign it.",
               "Add anything we left for you, such as your National Insurance number and bank details if the form asks.",
               ("Put the form, and any evidence you want to send, in the return envelope in this pack and post it. You do not need a stamp." if ret[0]=="insert" else
                "Put the form, and any evidence you want to send, in an envelope with the Freepost address on the next page, and post it. You do not need a stamp.")]
    else:
        steps=[f"Find the {code} form DWP sent you. It has your own barcode on it, so use that one.",
               f"In each question box on your {code}, write \"See extra sheet\", or copy the answer in.",
               "Write your National Insurance number on every extra sheet.",
               f"Sign and date the declaration on your {code}. Only you can sign it.",
               f"Post the {code} and these sheets in the envelope DWP sent with your form."]
    for i,s in enumerate(steps,1): p.multi_cell(0,6,f"{i}.  {s}",new_x="LMARGIN",new_y="NEXT"); p.ln(1)
    p.ln(2); p.set_font("D","",10)
    p.multi_cell(0,5,"Keep a copy of everything you send. If DWP asks you about your claim, your answers are also in your documents online.",new_x="LMARGIN",new_y="NEXT")
    p.add_page(); kind,val=ret
    p.set_font("D","B",14); p.cell(0,9,"Sending it back",new_x="LMARGIN",new_y="NEXT"); p.set_font("D","",11)
    if kind=="insert":
        p.multi_cell(0,6,f"Use the return envelope in this pack. It is already addressed to {FREEPOST[form]['address']}. You do not need a stamp.",new_x="LMARGIN",new_y="NEXT")
    elif kind=="label":
        p.multi_cell(0,6,"Put the signed form in an envelope and write only this address on it, or cut out the label below and stick it on. You do not need a postcode or a stamp.",new_x="LMARGIN",new_y="NEXT")
        p.ln(8); y=p.get_y(); p.set_dash_pattern(dash=2,gap=2); p.rect(30,y,150,40); p.set_dash_pattern()
        p.set_xy(30,y+14); p.set_font("D","B",16); p.cell(150,10,val,align="C"); p.set_y(y+44); p.set_font("D","",9)
        p.cell(0,5,"Cut along the dotted line",align="C",new_x="LMARGIN",new_y="NEXT")
    elif kind=="own":
        p.multi_cell(0,6,f"Use the envelope DWP sent you with your {val} form. If you have lost it, phone the PIP enquiry line and ask where to send it.",new_x="LMARGIN",new_y="NEXT")
    p.ln(6); p.set_font("D","",10)
    p.multi_cell(0,5,"Post it before your deadline. If you need more time, phone DWP before the deadline and ask.",new_x="LMARGIN",new_y="NEXT")
    return bytes(p.output())
def build_pack(form,rcpt,ret,form_pdf,brand="FormSorted"):
    """Cover sheet (2 pages) + the filled form / extra sheets, as one PDF."""
    from pypdf import PdfReader, PdfWriter
    w=PdfWriter()
    for src in (cover_sheet(form,rcpt,ret,brand),form_pdf):
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

def dispatch(c,o,form_pdf,brand="FormSorted",force=False):
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
    if not form_pdf: return hold("no filled form PDF to print (pre-fill may be switched off for this form)")
    try:
        pdf=build_pack(form,rc,ret,form_pdf,brand)
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
def sent_email(brand,public,o,job):
    code=FORM_CODE.get(o["form"] or "aa","form"); ret=job.get("return")
    how={"insert":"Use the return envelope in the pack. You do not need a stamp.","label":"The pack shows the Freepost address to write on the envelope. You do not need a stamp.",
         "own":f"Post it in the envelope DWP sent with your {code}."}.get(ret,"")
    return (f"{brand}: your {code} pack has been posted",
            f"Your printed {code} pack has been posted to you. It usually arrives in 2 to 3 working days.\n\n"
            f"When it arrives: read it, sign and date the declaration, and post it back. {how}\n\n"
            f"Your documents are also here: {public}/documents/{o['token']}\nKeep this link private.\n\n{brand}")
def review_email(public,o,job):
    return (f"Print-and-post held: order {o['token'][:8]} ({o['form']})",
            f"A Plus print-and-post job did not go out and is held for review.\n\nOrder: {o['token'][:8]}\nForm: {o['form']}\nProvider: {job.get('provider')}\n"
            f"Reason: {job.get('error') or job.get('status')}\nAttempt: {job.get('attempts')}\n\nReview it at {public}/admin (Print holds).")

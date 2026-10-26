"""FormSorted claim service prototype (AA1, DLA1A, PIP2, AR1). Run: uvicorn app:app --port 8000
Env: STRIPE_SECRET_KEY, PUBLIC_URL, ANTHROPIC_API_KEY/GEMINI_API_KEY/OPENAI_API_KEY, LLM_PROVIDER/LLM_MODEL/LLM_FALLBACKS, GROUNDING_PROVIDER/GROUNDING_MODEL/GROUNDING_FALLBACKS (see SETUP_RENDER_SUPABASE.md), BRAND. Placeholders => DEV mode (no payment, mock LLM)."""
import os, json, sqlite3, secrets, urllib.request, urllib.parse, base64, time
from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse, JSONResponse
import orders, mailer, asyncio, hmac, store
from fastapi.responses import Response
import llm, fill_pdf, documents, quality, deadlines, letters, grounding, facts, ticks as TICKS, contsheet, formwatch
from html import escape as esc
from forms import FORMS
BRAND=os.getenv("BRAND","FormSorted"); STRIPE=os.getenv("STRIPE_SECRET_KEY","STRIPE_SECRET_KEY_PLACEHOLDER")
PUBLIC=os.getenv("PUBLIC_URL","http://localhost:8000"); DEV=STRIPE.endswith("PLACEHOLDER")
HERE=os.path.dirname(os.path.abspath(__file__)); OUT=store.OUT; DB=store.SQLITE_PATH
os.makedirs(OUT,exist_ok=True)
CRON_SECRET=os.getenv("CRON_SECRET","")
def db(): return store.connect()   # Postgres if DATABASE_URL is set, else SQLite (see store.py)
def get(token):
    r=db().execute("select * from orders where token=?",(token,)).fetchone()
    if not r: raise HTTPException(404)
    return r
STEPS=["Choose","Pay","Agree","Conversation","Deadline","Strength check","Approve","Your documents"]
def prog(n): return f"<p class=progress>Step {n} of {len(STEPS)}: {STEPS[n-1]}</p><div class=bar><span style='width:{n*100//len(STEPS)}%'></span></div>"
def page(body,title="FormSorted",gov="https://www.gov.uk/browse/benefits/disability"): return HTMLResponse(f"""<!doctype html><html lang=en-GB><head><meta charset=utf-8><meta name=viewport content='width=device-width,initial-scale=1'><link rel=icon href=/static/favicon.svg><link rel=stylesheet href=/static/app.css><title>{title} | {BRAND}</title><meta name=robots content=noindex></head><body><a href="#main" class="skip">Skip to main content</a>
<header class="hdr"><div class="wrap"><a class="logo" href="/"><img src="/static/logo.svg" alt="FormSorted home" width="170" height="36"></a></div></header>
<div class="indep"><div class="wrap"><span class="tag">Independent</span>Not DWP or GOV.UK. You can claim free at <a href="{gov}">GOV.UK</a>.</div></div><main id=main><div class=wrap>{body}</div></main><footer class="ftr"><div class="wrap"><p><strong>FormSorted</strong> is an independent, paid service. Not affiliated with DWP, GOV.UK or any government body. We can't guarantee an award or outcome.</p><p>Free help: Citizens Advice · Age UK 0800 678 1602 · Contact 0808 808 3555 · gov.uk</p><p><a href="https://formsorted.com/privacy.html">Privacy</a><a href="https://formsorted.com/terms.html">Terms</a><a data-contact href="mailto:hello@formsorted.com">Contact</a></p></div></footer></body></html>""")
def stripe(method,path,data=None):
    req=urllib.request.Request("https://api.stripe.com/v1"+path,urllib.parse.urlencode(data).encode() if data else None,method=method,
        headers={"Authorization":"Basic "+base64.b64encode((STRIPE+":").encode()).decode()})
    return json.load(urllib.request.urlopen(req,timeout=30))
app=FastAPI()
@app.middleware("http")
async def _canonical_host(request:Request, call_next):
    # Old onrender.com address -> app.formsorted.com (keep health checks, webhooks and cron working on either host)
    host=(request.headers.get("host") or "").split(":")[0]
    p=request.url.path
    if host.endswith(".onrender.com") and PUBLIC.startswith("https://") and request.method in ("GET","HEAD") and not (p=="/healthz" or p.startswith("/webhooks") or p.startswith("/cron")):
        q=("?"+request.url.query) if request.url.query else ""
        return RedirectResponse(PUBLIC+p+q,301)
    return await call_next(request)
from fastapi.staticfiles import StaticFiles
app.mount("/static",StaticFiles(directory=os.path.join(HERE,"static")),name="static")
PREVIEW="<div class=panel><p><strong>Preview mode:</strong> no payment is taken and answers are sample drafts.</p></div>"
@app.get("/")
def home(form:str="", tier:str=""):
    pv=PREVIEW if DEV else ""
    if form not in FORMS:
        opts="".join(f"""<label class=radio><input type=radio name=form value={k} {'checked' if i==0 else ''} required><span><strong>{f['short']}</strong><span class=hint>For {f['who']}. England &amp; Wales.</span></span></label>""" for i,(k,f) in enumerate(FORMS.items()))
        return page(prog(1)+pv+f"""<form method=get action=/><fieldset style="border:0;padding:0;margin:0"><legend><h1>Which form do you need sorted?</h1></legend>{opts}</fieldset>
<div class=inset>Live in Scotland? We don't cover Scotland. Apply to Social Security Scotland instead (Pension Age, Child or Adult Disability Payment).</div>
<button class=btn>Continue</button></form>""","Choose your form")
    f=FORMS[form]; ts=list(f["tiers"].items())
    opts="".join(f"""<label class=radio><input type=radio name=tier value={t} {'checked' if (t==tier if tier in f['tiers'] else i==len(ts)-1) else ''} required><span><strong>{n} – £{p//100}</strong><span class=hint>{d}</span></span></label>""" for i,(t,(n,p,d)) in enumerate(ts))
    return page(prog(1)+pv+f"""<p class=caption>{f['short']}</p><form method=post action=/checkout><input type=hidden name=form value={form}><fieldset style="border:0;padding:0;margin:0"><legend><h1>Which service do you want?</h1></legend>{opts}</fieldset>
<div class=promise><strong>Your words only.</strong> You approve every word before you send.</div><div class=inset>One-off fee. No success fee. Secure card payment. 14-day cancellation rights until your conversation starts.</div>
<button class="btn">Continue to payment</button></form><p><a href=/>Choose a different form</a></p>""","Choose your service",f["gov"])
@app.post("/checkout")
def checkout(tier:str=Form(...), form:str=Form("aa")):
    if form not in FORMS or tier not in FORMS[form]["tiers"]: raise HTTPException(400)
    name,price,_=FORMS[form]["tiers"][tier]
    token=orders.new_token(); c=db()
    if DEV:
        c.execute("insert into orders(token,tier,status,created,form) values(?,?,?,?,?)",(token,tier,"paid",time.time(),form)); c.commit()
        return RedirectResponse(f"/start/{token}",303)
    s=stripe("POST","/checkout/sessions",{"mode":"payment","line_items[0][quantity]":1,"line_items[0][price_data][currency]":"gbp",
      "line_items[0][price_data][unit_amount]":price,"line_items[0][price_data][product_data][name]":f"{FORMS[form]['name']}: {name}",
      "client_reference_id":token,"adaptive_pricing[enabled]":"false","locale":"en-GB","customer_creation":"always","consent_collection[terms_of_service]":"required",
      "success_url":f"{PUBLIC}/success?session_id={{CHECKOUT_SESSION_ID}}","cancel_url":f"{PUBLIC}/?form={form}"})
    c.execute("insert into orders(token,tier,status,stripe_session,created,form) values(?,?,?,?,?,?)",(token,tier,"pending",s["id"],time.time(),form)); c.commit()
    return RedirectResponse(s["url"],303)
@app.get("/success")
def success(session_id:str=""):
    c=db(); row=c.execute("select * from orders where stripe_session=?",(session_id,)).fetchone() if session_id else None
    try: s=stripe("GET","/checkout/sessions/"+urllib.parse.quote(session_id)) if session_id else {}
    except Exception: s={}
    if s.get("payment_status")=="paid":
        c.execute("update orders set status='paid', email=coalesce(?,email) where stripe_session=?",((s.get("customer_details") or {}).get("email"),session_id)); c.commit()
        return RedirectResponse(f"/start/{s.get('client_reference_id') or row['token']}",303)
    if row and row["status"]!="pending": return RedirectResponse(f"/start/{row['token']}",303)   # webhook already confirmed it
    if not s and session_id: return page("<h1>We're confirming your payment</h1><p>This can take a minute. <a href='/success?session_id="+urllib.parse.quote(session_id)+"'>Refresh this page</a>. If you were charged, email <a href=mailto:hello@formsorted.com>hello@formsorted.com</a>.</p>","Confirming payment")
    return page("<h1>Payment not completed</h1><p>You have not been charged. <a href=/>Go back and try again</a>.</p>","Payment not completed")
WHSEC=os.getenv("STRIPE_WEBHOOK_SECRET","")
@app.post("/webhooks/payment")
async def payment_webhook(req:Request):
    raw=await req.body()
    try: ev=orders.verify_signature(raw,req.headers.get("stripe-signature",""),WHSEC)
    except ValueError: raise HTTPException(400,"bad signature")
    c=db()
    if c.execute("select 1 from events where id=?",(ev.get("id"),)).fetchone(): return {"ok":True,"duplicate":True}
    c.execute("insert into events(id,received) values(?,?)",(ev.get("id"),time.time())); c.commit()
    if ev.get("type")!="checkout.session.completed": return {"ok":True,"ignored":ev.get("type")}
    s=ev["data"]["object"]
    if s.get("payment_status")!="paid": return {"ok":True,"ignored":"unpaid"}
    email=(s.get("customer_details") or {}).get("email"); md=s.get("metadata") or {}
    row=c.execute("select * from orders where stripe_session=?",(s["id"],)).fetchone()
    if not row and s.get("client_reference_id"): row=c.execute("select * from orders where token=?",(s["client_reference_id"],)).fetchone()
    if row: token=row["token"]; form=row["form"] or "aa"; c.execute("update orders set status='paid', email=?, paid_at=?, stripe_session=? where token=?",(email,time.time(),s["id"],token))
    else:   # Payment Link sale from the static site: link metadata must carry form + tier
        form=md.get("form"); tier=md.get("tier")
        if form not in FORMS or tier not in FORMS[form]["tiers"] or FORMS[form]["tiers"][tier][1]!=s.get("amount_total"): raise HTTPException(422,"unknown product")
        token=orders.new_token()
        c.execute("insert into orders(token,tier,status,stripe_session,email,created,paid_at,form) values(?,?,?,?,?,?,?,?)",(token,tier,"paid",s["id"],email,time.time(),time.time(),form))
    c.commit()
    if email:
        subj,txt=orders.link_email(BRAND,FORMS[form]["short"],f"{PUBLIC}/start/{token}"); mailer.send(email,subj,txt)
    return {"ok":True}
DELETED_PAGE="<h1>Your information has been deleted</h1><p>Everything you told us for this order has been deleted. This link no longer works.</p>"
@app.get("/start/{token}")
def start(token:str):
    o=get(token)
    if o["status"]=="deleted": return page(DELETED_PAGE,"Deleted")
    if o["status"]!="paid": raise HTTPException(402)
    if o["consent_at"]: return RedirectResponse(f"/static/chat.html#{token}",303)
    return page(prog(3)+f"""<h1>Before we start</h1><p class=lead>Payment received. Please confirm 3 things.</p><form method=post action=/consent/{token}>
<label class=cb><input type=checkbox name=health required><span>I agree to {BRAND} using the health information I give to prepare this form. If it's about someone else, they agree, or I can act for them.</span></label>
<label class=cb><input type=checkbox name=digital required><span>I want my answers prepared now. I understand that once the service starts I lose my 14-day right to cancel.</span></label>
<label class=cb><input type=checkbox name=truth required><span>I'll only give true information and will check everything before sending it.</span></label>
<div class=warning>Giving false information on a benefit claim is an offence.</div>
<button class="btn btn-start">Start my conversation</button></form><p class=small>We delete your information after 90 days, or sooner if you ask. <a href="https://formsorted.com/privacy.html">Privacy notice</a></p>""","Before we start")
@app.post("/consent/{token}")
def consent(token:str, health:str=Form(...), digital:str=Form(...), truth:str=Form(...)):
    get(token); c=db(); c.execute("update orders set consent_at=? where token=?",(time.time(),token)); c.commit()
    return RedirectResponse(f"/static/chat.html#{token}",303)
def ready(token):
    o=get(token)
    if o["status"]!="paid" or not o["consent_at"]: raise HTTPException(403)
    if o["created"] and o["created"]<time.time()-86400*orders.RETENTION_DAYS: raise HTTPException(410)
    return o
@app.post("/api/{token}/message")
async def message(token:str, req:Request):
    o=ready(token); h=json.loads(o["history"]); msg=(await req.json()).get("text","").strip()
    if msg: h.append({"role":"user","content":msg[:4000]})
    q=llm.next_question(h,o["form"] or "aa"); h.append({"role":"assistant","content":q})
    c=db(); c.execute("update orders set history=? where token=?",(json.dumps(h),token)); c.commit()
    total=len(FORMS[o["form"] or "aa"]["topics"])+1; answered=sum(1 for m in h if m["role"]=="user" and m["content"].strip())
    return {"reply":q,"done":"[[DONE]]" in q,"topic":min(answered+1,total),"total":total}
@app.post("/api/{token}/finish")
def finish(token:str):
    o=ready(token); h=json.loads(o["history"]); personal=json.loads(o["personal"])
    form=o["form"] or "aa"; F=FORMS[form]
    d=llm.draft(h,form); d.setdefault("answers",{})
    c=db(); c.execute("update orders set draft=?, approved_at=null where token=?",(json.dumps(d),token)); c.commit()
    return {"next":f"/deadline/{token}"}
def build_files(token,o,d):
    form=o["form"] or "aa"; F=FORMS[form]; personal=json.loads(o["personal"] or "{}"); od=os.path.join(OUT,token); os.makedirs(od,exist_ok=True)
    if form=="atw":
        open(os.path.join(od,"answers.html"),"w").write(documents.pack_atw(BRAND,d,o["tier"]))
        documents.atw_docx(BRAND,d,o["tier"],os.path.join(od,"AccessToWork-answers.docx")); files=["answers.html","AccessToWork-answers.docx"]
        store.put_dir(token,od,files); return files
    pf=pack_files(o); off=prefill_off(o)
    open(os.path.join(od,"answers.html"),"w").write(documents.pack_form(BRAND,personal,d,o["tier"],form,prefill_off=bool(off)))
    files=["answers.html"]
    if F.get("pdf_out") in pf:
        fill_pdf.fill_form(form,personal,d,os.path.join(od,F["pdf_out"]),ticks=d.get("ticks") if d.get("ticks_confirmed_at") else None); files.append(F["pdf_out"])
    if "PIP-extra-sheets.pdf" in pf:
        open(os.path.join(od,"PIP-extra-sheets.pdf"),"wb").write(pip_sheet_pdf(form,personal,d)); files.append("PIP-extra-sheets.pdf")
    store.put_dir(token,od,files)   # to private Supabase bucket when configured (local temp copy removed)
    return files
def prefill_off(o):
    """Reason pre-fill is switched off for this order's form (e.g. GOV.UK published a new version), else None."""
    F=FORMS[o["form"] or "aa"]
    return formwatch.disabled_reason(o["form"] or "aa") if (o["tier"]=="79" and F["pdf"]) else None
def pack_files(o):
    form=o["form"] or "aa"; F=FORMS[form]
    if form=="atw": return ["answers.html","AccessToWork-answers.docx"]
    files=["answers.html"]
    if o["tier"]=="79" and F["pdf"] and not prefill_off(o): files.append(F["pdf_out"])
    if form in ("pip","pipr"): files.append("PIP-extra-sheets.pdf")
    return files
def needs_ticks(o): return (o["form"] or "aa") in TICKS.CATALOG and o["tier"]=="79" and FORMS[o["form"] or "aa"]["pdf"] and not prefill_off(o)
def pip_sheet_pdf(form,personal,d):
    from forms import PIP_ACTIVITIES
    a=d.get("answers",{}); code="AR1" if form=="pipr" else "PIP2"
    items=[("Questions 1 and 2: Health conditions, medicines and treatments",a.get("conditions",""))]
    items+=[(f"{'Activity '+str(n) if form=='pipr' else 'Question '+q[1:]}: {name}",a.get(f"a{n}","")) for n,name,q,_ in PIP_ACTIVITIES]
    items+=[("Question 15: Additional information",a.get("other",""))]
    name=" ".join(x for x in (personal.get("title"),personal.get("other_names"),personal.get("surname")) if x)
    return contsheet.pip_sheets(name,items,code)
@app.get("/api/{token}/info")
def info(token:str):
    o=ready(token); f=FORMS[o["form"] or "aa"]; return {"form":o["form"] or "aa","short":f["short"],"gov":f["gov"],"pdf":f.get("pdf_out")}
@app.post("/api/{token}/personal")
async def personal(token:str, req:Request):
    ready(token); c=db(); c.execute("update orders set personal=? where token=?",(json.dumps(await req.json()),token)); c.commit(); return {"ok":True}
@app.get("/download/{token}/{name}")
def download(token:str,name:str):
    o=ready(token)
    if not o["approved_at"] or not o["details_at"]: raise HTTPException(403,"Approve your answers first")
    if name not in ("answers.html","AA1-filled.pdf","DLA1A-filled.pdf","AccessToWork-answers.docx","PIP-extra-sheets.pdf"): raise HTTPException(404)
    data=store.read(token,name)
    if data is None: raise HTTPException(404)
    ct={"html":"text/html; charset=utf-8","pdf":"application/pdf","docx":"application/vnd.openxmlformats-officedocument.wordprocessingml.document"}[name.rsplit(".",1)[1]]
    disp="inline" if name.endswith(".html") else f'attachment; filename="{name}"'
    return Response(data,media_type=ct,headers={"Content-Disposition":disp,"Cache-Control":"private, no-store"})
@app.post("/api/{token}/delete")
def delete(token:str):
    get(token); orders.erase(db(),OUT,token); return {"deleted":True}
@app.get("/delete/{token}")
def delete_page(token:str):
    o=get(token)
    if o["status"]=="deleted": return page(DELETED_PAGE,"Deleted")
    return page(f"""<h1>Delete my information</h1><p class=lead>This deletes everything you told us for this order: your answers, your details and your documents. It can't be undone.</p>
<div class=warning>Download your documents first if you want to keep them.</div><form method=post action=/delete/{token}><button class="btn btn-warn">Delete everything now</button></form><p><a href=/start/{token}>Go back</a></p>""","Delete my information")
@app.post("/delete/{token}")
def delete_post(token:str):
    get(token); orders.erase(db(),OUT,token); return page(DELETED_PAGE,"Deleted")
DETAIL_FIELDS=[("title","Title (optional)","",False),("other_names","First and middle names","",True),("surname","Surname","",True),("dob","Date of birth","date",True),
 ("addr1","Address line 1","",True),("addr2","Address line 2 (optional)","",False),("addr3","Town or city","",True),("postcode","Postcode","",True),("phone","Phone (optional)","tel",False),
 ("ni","National Insurance number (optional, for your reference only. We never print it on the form)","",False)]
DLA_EXTRA=[("parent_title","Your title (parent or guardian, optional)","",False),("parent_other_names","Your first names","",True),("parent_surname","Your surname","",True),("relationship","Your relationship to the child","",True)]
def detail_fields(form):
    if form=="atw": return [f for f in DETAIL_FIELDS if f[0] in("other_names","surname","ni")]
    return DETAIL_FIELDS+(DLA_EXTRA if form=="dla" else [])
import re as _re
NI_RE=_re.compile(r"^[A-CEGHJ-PR-TW-Z]{2}\d{6}[A-D]$")
@app.get("/details/{token}")
def details_page(token:str, err:str=""):
    o=ready(token)
    if not o["approved_at"]: return RedirectResponse(f"/approve/{token}",303)
    if ticks_pending(o): return RedirectResponse(f"/ticks/{token}",303)
    p=json.loads(o["personal"] or "{}"); form=o["form"] or "aa"
    who="the child" if form=="dla" else "the person claiming"
    rows="".join(f"""<div class=field><label class=q for=d_{k}>{esc(l)}</label><input id=d_{k} name={k} {'type='+t if t else ''} value="{esc(p.get(k,''))}" {'required' if req else ''} autocomplete=off></div>""" for k,l,t,req in detail_fields(form))
    return page(prog(8)+f"""<h1>Your details</h1><p class=lead>We add these to your documents{'' if form=='atw' else f' for {who}'} so you have less to fill in by hand. We only ask now, at the end, so we don't keep them longer than needed.</p>
{f'<div class=warning>{esc(err)}</div>' if err else ''}<form method=post action=/details/{token}>{rows}<button class=btn>Save and make my documents</button></form>
<form method=post action=/details/{token}><input type=hidden name=skip value=1><button class="btn btn-2">Skip. I'll write my details in by hand</button></form>
<p class=small>We never ask for bank details. We delete everything 90 days after your order, or now: <a href=/delete/{token}>delete my information</a>.</p>""","Your details")
@app.post("/details/{token}")
async def details_save(token:str, req:Request):
    o=ready(token)
    if not o["approved_at"]: return RedirectResponse(f"/approve/{token}",303)
    if ticks_pending(o): return RedirectResponse(f"/ticks/{token}",303)
    fm=await req.form(); form=o["form"] or "aa"; p={}
    if not fm.get("skip"):
        for k,_,_,need in detail_fields(form):
            v=str(fm.get(k,"")).strip()[:200]
            if need and not v: return RedirectResponse(f"/details/{token}?err="+urllib.parse.quote("Please fill in every required box, or choose Skip."),303)
            if v: p[k]=v
        if p.get("ni"):
            p["ni"]=p["ni"].replace(" ","").upper()
            if not NI_RE.match(p["ni"]): return RedirectResponse(f"/details/{token}?err="+urllib.parse.quote("That National Insurance number doesn't look right. It's 2 letters, 6 numbers, then A, B, C or D."),303)
    c=db(); c.execute("update orders set personal=?, details_at=? where token=?",(json.dumps(p),time.time(),token)); c.commit()
    o=get(token); build_files(token,o,json.loads(o["draft"]))
    return RedirectResponse(f"/documents/{token}",303)

# ---------- Deadline tracker, strength check, approval, saved answers, review mode, MR letter ----------
PROMISE="<div class=promise><strong>Your words only.</strong> We only use what you told us. You approve every word before you send.</div>"
def ordered(token):
    o=ready(token)
    if not o["draft"]: return RedirectResponse(f"/static/chat.html#{token}",303),None,None
    return None,o,json.loads(o["draft"])
def said_map(o):
    """Traceability: what the customer said for each topic. Uses LLM-provided 'sources' if present, else conversation order
    (question 0 = intro, question k+1 = topic k)."""
    h=json.loads(o["history"]); topics=FORMS[o["form"] or "aa"]["topics"]; d=json.loads(o["draft"] or "{}")
    users=[m["content"] for m in h if m["role"]=="user" and m["content"].strip()]
    m={t[0]:(users[i+1] if i+1<len(users) else "") for i,t in enumerate(topics)}
    if users: m["_intro"]=users[0]
    for k,v in (d.get("sources") or {}).items(): m[k]=" … ".join(v) if isinstance(v,list) else v
    for k,v in (d.get("said") or {}).items(): m[k]=v  # review-mode carry-over
    return m
@app.get("/deadline/{token}")
def deadline_page(token:str):
    r,o,d=ordered(token)
    if r: return r
    form=o["form"] or "aa"; dl=json.loads(o["deadline"] or "{}"); res=deadlines.compute(form,dl.get("how","phone"),dl.get("requested"),dl.get("received")) if dl else None
    if form=="atw": howq=f"""<fieldset style="border:0;padding:0"><legend class=q>How do you work?</legend>
<label class=radio><input type=radio name=how value=employed {'checked' if dl.get('how','employed')!='self' else ''}><span><strong>I'm employed (or about to start a job)</strong></span></label>
<label class=radio><input type=radio name=how value=self {'checked' if dl.get('how')=='self' else ''}><span><strong>I'm self-employed</strong></span></label></fieldset>"""
    else: howq="" if form in("pip","pipr") else f"""<fieldset style="border:0;padding:0"><legend class=q>How did you get the form?</legend>
<label class=radio><input type=radio name=how value=phone {'checked' if dl.get('how','phone')=='phone' else ''}><span><strong>I phoned DWP and they posted it</strong></span></label>
<label class=radio><input type=radio name=how value=print {'checked' if dl.get('how')=='print' else ''}><span><strong>I printed or downloaded it</strong></span></label></fieldset>"""
    box=""
    if res:
        when=f"<p class=big>{'Apply by' if form=='atw' else 'Send it back by'} <strong>{datetime_fmt(res['deadline'])}</strong>{'' if res['days_left'] is None else f' · {res['days_left']} days left' if res['days_left']>=0 else ' · this date has passed, phone DWP now'}</p>" if res.get("deadline") else ""
        box=f"""<div class="tracker" id=tracker>{when}<p>{esc(res['rule'])}</p>{f"<p><strong>{esc(res['backdate'])}</strong></p>" if res['backdate'] else ''}<p class=small>Source: <a href="{res['source']}">{res['source'].replace('https://www.','')}</a> (checked 24 Oct 2026)</p></div>
{'' if form=='atw' else "<h2>Need more time? What to say on the phone</h2><ol class=steps>"+''.join(f'<li>{esc(x)}</li>' for x in deadlines.script(form))+"</ol>"}{f"<p>Questions? Access to Work helpline: <strong>{facts.v('atw_helpline')}</strong> (Mon–Fri 9am–5pm). You can ask for all contact by email.</p>" if form=='atw' else ''}
<p><a class="btn" href="/check/{token}">Continue to strength check</a></p>"""
    return page(prog(5)+(f"""<h1>Timing</h1><p class=lead>When you apply can affect who pays for equipment. Tell us when you started (or will start) this job.</p>""" if form=='atw' else f"""<h1>Your deadline</h1><p class=lead>Tell us when you asked for the form, and we'll show the date to send it back by, so you don't lose money.</p>""")+f"""
<form method=post action=/deadline/{token}>{howq}
<div class=field><label class=q for=req>{'When did you start (or will you start) this job?' if form=='atw' else 'When did you ask DWP for the form?' if form in('aa','dla') else 'When did you get the form? (or the date on the letter)'}</label><input type=date id=req name=requested value="{dl.get('requested','')}"></div>
{'' if form in('aa','dla') else f'<input type=hidden name=received value="">'}
<button class="btn btn-2">Show my deadline</button> <a href="/check/{token}">Skip this step</a></form>{box}""","Your deadline")
def datetime_fmt(s):
    from datetime import date as _d
    return _d.fromisoformat(s).strftime("%-d %B %Y")
@app.post("/deadline/{token}")
def deadline_save(token:str, how:str=Form("phone"), requested:str=Form(""), received:str=Form("")):
    ready(token); c=db(); c.execute("update orders set deadline=? where token=?",(json.dumps({"how":how,"requested":requested,"received":received}),token)); c.commit()
    return RedirectResponse(f"/deadline/{token}#tracker",303)
@app.get("/check/{token}")
def check_page(token:str):
    r,o,d=ordered(token)
    if r: return r
    F=FORMS[o["form"] or "aa"]; res=quality.check(d["answers"],F["topics"],o["form"]); fl,tot=quality.score(res)
    rows="".join(f"""<div class="sc {'ok' if not x['flags'] else 'weak'}"><h3>{'✓' if not x['flags'] else '!'} {esc(x['label'])}</h3>{f'<p class=ans>{esc(x["answer"])}</p>' if x['answer'] else ''}
{''.join(f'<p class=flag>{esc(f)}</p>' for f in x['flags'])}{f'<label class=hint for="add_{x["id"]}">Add detail in your own words (optional)</label><textarea id="add_{x["id"]}" name="add_{x["id"]}" rows=2></textarea>' if x['flags'] else ''}</div>""" for x in res if x['flags'] or not x.get('blank'))
    return page(prog(6)+f"""<h1>Strength check</h1><p class=lead>{fl} of {tot} answers could be clearer. Vague answers are a common reason claims are turned down. Add detail where you can. Only add what's true.</p>
<div class=panel><p>We look for: how often, how long, what help is needed, safety, and what bad days are like.</p></div>
<form method=post action=/check/{token}>{rows}<button class=btn>Save and continue to approve</button></form>""","Strength check")
@app.post("/check/{token}")
async def check_save(token:str, req:Request):
    r,o,d=ordered(token)
    if r: return r
    fm=await req.form(); a=d["answers"]; extra=d.setdefault("user_added",{})
    for k,v in fm.items():
        if k.startswith("add_") and v.strip():
            tid=k[4:]; v=v.strip()[:2000]
            if tid=="_bad": d.setdefault("answers",{})["other"]=((a.get("other") or "")+" "+v).strip(); extra["other"]=(extra.get("other","")+" "+v).strip()
            else: a[tid]=((a.get(tid) or "")+" "+v).strip(); extra[tid]=(extra.get(tid,"")+" "+v).strip()
    c=db(); c.execute("update orders set draft=? where token=?",(json.dumps(d),token)); c.commit()
    return RedirectResponse(f"/approve/{token}",303)
def BUSY(token):
    return page(f"""<h1>We're still checking your answers</h1><p class=lead>We check every answer against what you told us before you approve it. That check is taking longer than usual. Your answers are saved. Please try again in a few minutes.</p><a class="btn btn-start" href="/approve/{token}">Try again</a>""","Checking your answers")
def source_text(o,d):
    h=json.loads(o["history"] or "[]"); parts=[m["content"] for m in h if m["role"]=="user"]
    parts+=list((d.get("user_added") or {}).values())+[v for v in (d.get("said") or {}).values()]
    return "\n".join(parts)
def ground(o,d):
    F=FORMS[o["form"] or "aa"]
    return grounding.check({t:d["answers"].get(t,"") for t,_,_ in F["topics"]},source_text(o,d))
def flag_html(t,fl):
    if not fl: return ""
    items="".join(f"""<li><p><strong>"{esc(x['phrase'])}"</strong> <span class=hint>({esc(x['kind'])})</span></p><div class=resopts>
<label><input type=radio name="res_{t}_{i}" value=keep required> Keep, it's true</label><label><input type=radio name="res_{t}_{i}" value=edit> I've edited the answer</label><label><input type=radio name="res_{t}_{i}" value=remove> Remove it</label></div></li>""" for i,x in enumerate(fl))
    return f"""<div class=ground><p class=flag>We couldn't find this in what you told us — keep, edit or remove</p><ul>{items}</ul></div>"""
@app.get("/approve/{token}")
def approve_page(token:str):
    r,o,d=ordered(token)
    if r: return r
    F=FORMS[o["form"] or "aa"]; sm=said_map(o); added=d.get("user_added",{})
    try: G=ground(o,d)
    except grounding.GroundingUnavailable as e: print("grounding unavailable",e); return BUSY(token)
    rows="".join(f"""<div class=trace><h3>{esc(l)}</h3><div class=cols><div><p class=lbl>What you told us</p><p class=you>{esc(sm.get(t,'')) or '<em>Nothing for this topic</em>'}{f'<br><strong>You added:</strong> {esc(added[t])}' if t in added else ''}</p></div>
<div><p class=lbl>What goes on the form (edit if needed)</p><textarea name="ans_{t}" rows=4>{esc(d['answers'].get(t,''))}</textarea></div></div>
{flag_html(t,G.get(t))}<label class=cb><input type=checkbox name="ok_{t}" required><span>I approve this answer. It is true and in my words.</span></label></div>""" for t,l,_ in F["topics"])
    return page(prog(7)+f"""<h1>Check and approve every answer</h1>{PROMISE}<p class=lead>Each answer is shown next to what you told us. Change anything that isn't right. Nothing is ready to download until you approve each answer.</p>
<form method=post action=/approve/{token}>{rows}
<label class=cb><input type=checkbox name=save><span>Save my answers for next time (for a review or renewal). We'll give you a save code. Saved answers are kept for 90 days unless you delete them.</span></label>
<div class=warning>Giving false information on a benefit claim is an offence.</div><button class="btn btn-start">I approve. Make my documents</button></form>""","Approve your answers")
@app.post("/approve/{token}")
async def approve_save(token:str, req:Request):
    r,o,d=ordered(token)
    if r: return r
    fm=await req.form(); F=FORMS[o["form"] or "aa"]
    try: G=ground(o,d)
    except grounding.GroundingUnavailable as e: print("grounding unavailable",e); return BUSY(token)
    missing=[l for t,l,_ in F["topics"] if not fm.get(f"ok_{t}")]
    unresolved=[f'"{x["phrase"]}"' for t,fl in G.items() for i,x in enumerate(fl) if fm.get(f"res_{t}_{i}") not in ("keep","edit","remove")]
    if missing or unresolved: return page(f"<h1>Please approve every answer</h1>{f'<p>Not approved yet: {esc(chr(44).join(missing))}</p>' if missing else ''}{f'<p>Please choose keep, edit or remove for: {esc(chr(44).join(unresolved))}</p>' if unresolved else ''}<p><a href=/approve/{token}>Go back</a></p>","Approve every answer")
    res=d.setdefault("grounding_resolved",[])
    for t,_,_ in F["topics"]:
        a=str(fm.get(f"ans_{t}",d["answers"].get(t,"")))[:4000]
        for i,x in enumerate(G.get(t,[])):
            ch=fm.get(f"res_{t}_{i}"); res.append({"topic":t,"phrase":x["phrase"],"choice":ch,"at":time.time()})
            if ch=="remove": a=grounding.remove_phrase(a,x["phrase"])
        d["answers"][t]=a
    files=build_files(token,o,d); c=db(); code=o["save_code"]
    if fm.get("save"):
        code=code or secrets.token_urlsafe(9); sm=said_map(o)
        c.execute("insert into saved(code,form,answers,personal,created) values(?,?,?,?,?) on conflict(code) do update set form=excluded.form, answers=excluded.answers, personal=excluded.personal, created=excluded.created",(code,o["form"] or "aa",json.dumps({"answers":d["answers"],"said":{t:sm.get(t,"") for t,_,_ in F["topics"]}}),o["personal"],time.time()))
    d.pop("ticks_confirmed_at",None)   # answers changed: ticks must be checked again
    c.execute("update orders set draft=?, approved_at=?, save_code=? where token=?",(json.dumps(d),time.time(),code,token)); c.commit()
    return RedirectResponse(f"/ticks/{token}" if needs_ticks(o) else f"/details/{token}",303)
def ticks_pending(o):
    return needs_ticks(o) and not json.loads(o["draft"] or "{}").get("ticks_confirmed_at")
@app.get("/ticks/{token}")
def ticks_page(token:str, err:str=""):
    r,o,d=ordered(token)
    if r: return r
    if not o["approved_at"]: return RedirectResponse(f"/approve/{token}",303)
    form=o["form"] or "aa"
    if not needs_ticks(o): return RedirectResponse(f"/details/{token}",303)
    saved=d.get("ticks") if d.get("ticks_confirmed_at") else None; F=FORMS[form]; rows=""; last=None
    for i,x in enumerate(TICKS.propose(form,d.get("answers",{}))):
        cur=saved.get(x["field"],"") if saved is not None else x["proposed"]
        q=x["question"].split(":")[0]
        if q!=last: rows+=f"<h2 class=tickq>{esc(q)} <span class=hint>(page {x['page']} of the form)</span></h2>"; last=q
        opts="".join(f'<label><input type=radio name="t_{esc(x["field"])}" value="{esc(s)}" {"checked" if s==cur else ""}> Tick “{esc(TICKS.label(s))}”</label>' for s in x["options"])
        opts+=f'<label><input type=radio name="t_{esc(x["field"])}" value="" {"checked" if not cur else ""}> Leave blank</label>'
        rows+=f"""<div class=trace><p><strong>{esc(x['question'].split(':',1)[1].strip())}</strong></p><p class=hint>{esc(x['why'])}</p><div class=resopts>{opts}</div></div>"""
    return page(prog(7)+f"""<h1>Check the tick boxes on your {esc(F['form'])}</h1>{PROMISE}<p class=lead>These are the tick boxes we will mark on the official form. We have suggested each one from the answers you approved. Change anything that isn't right. We only tick what you confirm here.</p>
{f'<div class=warning>{esc(err)}</div>' if err else ''}<form method=post action=/ticks/{token}>{rows}
<p class=small>We never tick the consent, declaration, bank or "signing for someone else" boxes. You do those yourself.</p>
<label class=cb><input type=checkbox name=confirm required><span>I have checked every tick box above. They are true.</span></label>
<button class="btn btn-start">Confirm tick boxes</button></form>""","Check the tick boxes")
@app.post("/ticks/{token}")
async def ticks_save(token:str, req:Request):
    r,o,d=ordered(token)
    if r: return r
    if not o["approved_at"]: return RedirectResponse(f"/approve/{token}",303)
    if not needs_ticks(o): return RedirectResponse(f"/details/{token}",303)
    fm=await req.form(); form=o["form"] or "aa"
    if not fm.get("confirm"): return RedirectResponse(f"/ticks/{token}?err="+urllib.parse.quote("Please confirm you have checked every tick box."),303)
    d["ticks"]=TICKS.validate(form,{x["field"]:str(fm.get("t_"+x["field"],"")) for x in TICKS.propose(form,d.get("answers",{}))})
    d["ticks_confirmed_at"]=time.time()
    c=db(); c.execute("update orders set draft=? where token=?",(json.dumps(d),token)); c.commit()
    return RedirectResponse(f"/details/{token}",303)
@app.get("/documents/{token}")
def documents_page(token:str):
    o=ready(token)
    if not o["approved_at"]: return RedirectResponse(f"/approve/{token}",303)
    if ticks_pending(o): return RedirectResponse(f"/ticks/{token}",303)
    if not o["details_at"]: return RedirectResponse(f"/details/{token}",303)
    F=FORMS[o["form"] or "aa"]; lab={'PIP-extra-sheets.pdf':'Printable extra sheets, one per question (PDF), to send with your form','answers.html':'Your approved answers, checklist and letters','AA1-filled.pdf':'Official AA1 form, filled in (PDF)','DLA1A-filled.pdf':'Official DLA1A form, filled in (PDF)','AccessToWork-answers.docx':'Your answers as a Word document (DOCX), in application order'}
    files=pack_files(o)
    dl=json.loads(o["deadline"] or "{}"); res=deadlines.compute(o["form"] or "aa",dl.get("how","phone"),dl.get("requested"),dl.get("received")) if dl.get("requested") else None
    saved=f"<div class=panel><p><strong>Your save code: <code>{o['save_code']}</code></strong><br>Keep it safe. {'Keep a copy of your answers too. They will help when your grant is due for renewal (you can apply to renew 12 weeks before it ends).' if o['form']=='atw' else "Use it at <a href=/review>/review</a> when your review form arrives, and we'll only ask what has changed."}</p></div>" if o["save_code"] else ""
    return page(prog(8)+f"""<div class=done><h1>{"Your answers are ready" if o["form"]=="atw" else "Your claim is sorted"}</h1><p>You approved every answer. Your documents are ready.</p></div>
{''.join(f'<div class=dl><span><strong>{lab.get(f,f)}</strong></span><a class=btn href="/download/{token}/{f}" download>Download</a></div>' for f in files)}
{f"<div class=tracker><p class=big>Send it back by <strong>{datetime_fmt(res['deadline'])}</strong></p></div>" if res and res.get('deadline') else ''}{saved}
{ATW_NEXT if o['form']=='atw' else ''}<h2{' hidden' if o['form']=='atw' else ''}>What to do next</h2><ol class=steps{' hidden' if o['form']=='atw' else ''}><li><strong>Read it once more</strong> before you send it.</li><li><strong>Copy the answers into your claim</strong>, or print, sign and post the filled-in form.</li><li><strong>Turned down?</strong> You can ask DWP to look again (mandatory reconsideration), usually within one month of the decision letter. <a href=/letter>Draft a letter</a>.</li></ol>
<p class=small>We delete everything 90 days after your order. <a href=/delete/{token}>Delete my information now</a>.</p>""","Your documents")
ATW_NEXT=f"""<h2>What to do next</h2><ol class=steps><li><strong>Read it once more</strong> and change anything that isn't right.</li><li><strong>Apply online or by phone</strong> at <a href="https://www.gov.uk/access-to-work/apply">gov.uk/access-to-work/apply</a>, or call {facts.v('atw_helpline')} (Mon–Fri 9am–5pm). Paste or read out each answer.</li><li><strong>Add your own details</strong>: workplace address, workplace contact, NI number (or UTR if self-employed).</li><li><strong>Disagree with the decision?</strong> Call the helpline and ask for it to be reconsidered.</li></ol>"""
FAMILY_ONLY="<h1>Coming soon with FormSorted Family</h1><p>This feature isn't available yet. We don't take payment for it until it's ready.</p>"
@app.get("/review")
def review_start(code:str=""):
    if not DEV: return page(FAMILY_ONLY,"Coming soon")
    if code: return RedirectResponse(f"/review/{urllib.parse.quote(code)}",303)
    return page(PREVIEW+"""<h1>Review mode</h1><p class=lead>Got a review or renewal form? Enter your save code. We'll show your last answers and only ask what has changed.</p>
<form method=get action=/review><div class=field><label class=q for=code>Save code</label><input id=code name=code required></div><button class=btn>Continue</button></form>""","Review mode")
@app.get("/review/{code}")
def review_page(code:str):
    if not DEV: return page(FAMILY_ONLY,"Coming soon")
    s=db().execute("select * from saved where code=?",(code,)).fetchone()
    if not s: raise HTTPException(404)
    F=FORMS[s["form"]]; a=json.loads(s["answers"])["answers"]
    rows="".join(f"""<div class=trace><h3>{esc(l)}</h3><p class=lbl>Last time you said</p><p class=you>{esc(a.get(t,'')) or '<em>No difficulty given</em>'}</p>
<fieldset style="border:0;padding:0"><label class=radio><input type=radio name="st_{t}" value=same checked><span>Still the same</span></label><label class=radio><input type=radio name="st_{t}" value=changed><span>It has changed</span></label></fieldset>
<label class=hint for="ch_{t}">If it has changed, what's different now?</label><textarea id="ch_{t}" name="ch_{t}" rows=2></textarea></div>""" for t,l,_ in F["topics"])
    target="pipr" if s["form"] in("pip","pipr") else s["form"]
    return page(PREVIEW+f"""<h1>What has changed?</h1><p class=lead>{esc(FORMS[target]['short'])}. Your previous answers are filled in. Only tell us what's different.</p>
<form method=post action=/review/{urllib.parse.quote(code)}>{rows}<button class="btn btn-start">Update my answers</button></form>""","What has changed")
@app.post("/review/{code}")
async def review_save(code:str, req:Request):
    if not DEV: return page(FAMILY_ONLY,"Coming soon")
    s=db().execute("select * from saved where code=?",(code,)).fetchone()
    if not s: raise HTTPException(404)
    fm=await req.form(); prev=json.loads(s["answers"]); a=dict(prev["answers"]); said={}; changes=[]
    target="pipr" if s["form"] in("pip","pipr") else s["form"]; F=FORMS[target]
    for t,l,_ in F["topics"]:
        ch=str(fm.get(f"ch_{t}","")).strip()
        if fm.get(f"st_{t}")=="changed" and ch:
            a[t]=ch[:4000]; said[t]=ch; changes.append(f"{l.split(': ',1)[-1]}: {ch}")  # TODO LLM: merge old answer + change into one answer
        else: said[t]="(Same as last time) "+(prev.get("said",{}).get(t) or a.get(t,""))
    d={"answers":a,"said":said,"changes":" ".join(changes) or "No changes reported.","checklist":["Any new letters or reports since your last award"],"notes_for_user":["Review mode: answers carried over from last time. Check each one is still true."],"extra":{},"conditions":[],"tick_yes":[]}
    token=orders.new_token(); c=db()
    c.execute("insert into orders(token,tier,status,created,form,consent_at,draft,personal,review_of) values(?,?,?,?,?,?,?,?,?)",(token,"59" if target=="pipr" else "49","paid",time.time(),target,time.time(),json.dumps(d),s["personal"] or "{}",code)); c.commit()
    return RedirectResponse(f"/deadline/{token}",303)
@app.get("/letter")
def letter_form():
    if not DEV: return page(FAMILY_ONLY,"Coming soon")
    opts="".join(f"<option value={k}>{esc(letters.NAMES[k])}</option>" for k in ("aa","dla","pip"))
    pts="".join(f"""<div class=field><label class=q for=i{i}>Part {i} you disagree with{' (optional)' if i>1 else ''}</label><input id=i{i} name=issue{i} placeholder="e.g. Washing and bathing: they said I need no help"><label class=hint for=w{i}>What actually happens (how often, how long, what help)</label><textarea id=w{i} name=why{i} rows=3></textarea></div>""" for i in (1,2,3))
    return page(PREVIEW+f"""<h1>Turned down? Draft your reconsideration letter</h1><p class=lead>You can ask DWP to look at a decision again. This is called mandatory reconsideration. It's free, and you usually need to ask within one month of the date on your decision letter.</p>
{PROMISE}<form method=post action=/letter><div class=field><label class=q for=b>Benefit</label><select id=b name=form>{opts}</select></div>
<div class=field><label class=q for=n>Your name</label><input id=n name=name></div><div class=field><label class=q for=ad>Your address</label><textarea id=ad name=address rows=2></textarea></div>
<div class=field><label class=q for=dd>Date on your decision letter</label><input type=date id=dd name=decision_date></div>{pts}
<div class=field><label class=q for=ev>Evidence you'll send (one per line)</label><textarea id=ev name=evidence rows=3></textarea></div>
<button class=btn>Draft my letter</button></form><p class=small>Source: <a href="https://www.gov.uk/mandatory-reconsideration">gov.uk/mandatory-reconsideration</a>. Free help: Citizens Advice.</p>""","Reconsideration letter")
@app.post("/letter")
async def letter_make(req:Request):
    if not DEV: return page(FAMILY_ONLY,"Coming soon")
    fm=await req.form(); form=fm.get("form","aa")
    if form not in letters.NAMES: raise HTTPException(400)
    dd=fm.get("decision_date",""); dds=datetime_fmt(dd) if dd else ""
    from datetime import date as _d
    warn=""
    if dd:
        due=deadlines.add_month(_d.fromisoformat(dd)); days=(due-_d.today()).days
        warn=f"<div class=tracker><p class=big>Ask by about <strong>{due:%-d %B %Y}</strong>{f' · {days} days left' if days>=0 else ''}</p><p>{'One month from your decision letter has passed. You can still ask if you have a good reason (for example hospital or bereavement). Say why in the letter.' if days<0 else 'That is one month from the date on your decision letter.'}</p></div>"
    txt=letters.mr_letter(form,{"name":fm.get("name",""),"address":fm.get("address",""),"decision_date":dds,
        "points":[{"issue":fm.get(f"issue{i}",""),"why":fm.get(f"why{i}","")} for i in (1,2,3)],"evidence":str(fm.get("evidence","")).splitlines()})
    return page(f"""<h1>Your draft letter</h1>{warn}{PROMISE}<p>Read it, add your National Insurance number, sign it and send it to the address on your decision letter. You can also ask by phone.</p>
<pre class=letter id=letter>{esc(txt)}</pre><button class=btn onclick="navigator.clipboard.writeText(document.getElementById('letter').innerText)">Copy letter</button>
<p class=small>We only used what you typed. Free help with reconsideration: Citizens Advice.</p>""","Your draft letter")

# ---------- 90-day deletion ----------
# Render free has no always-on loop: an external scheduler calls POST /cron/retention daily with header X-Cron-Secret.
# The same ping wakes the app and touches the database, which also stops the free Supabase project from pausing.
@app.get("/healthz")
def healthz(): return {"ok":True}
@app.post("/cron/retention")
def cron_retention(req:Request):
    got=req.headers.get("x-cron-secret","")
    if not CRON_SECRET or not hmac.compare_digest(got,CRON_SECRET): raise HTTPException(403)
    return {"ok":True,"purged":orders.purge(db(),OUT)}
@app.post("/cron/formwatch")
def cron_formwatch(req:Request):
    """Weekly: compare GOV.UK's current AA1/DLA1A with the bundled copies; switches pre-fill off if a new version appears."""
    got=req.headers.get("x-cron-secret","")
    if not CRON_SECRET or not hmac.compare_digest(got,CRON_SECRET): raise HTTPException(403)
    return {"ok":True,"forms":[{k:v for k,v in r.items() if k!="expected"} for r in formwatch.run(db())]}
@app.on_event("startup")
async def _retention_loop():
    if os.getenv("RETENTION_LOOP","1")!="1": return   # set RETENTION_LOOP=0 on Render (cron endpoint does the work)
    async def loop():
        while True:
            try: print("retention purge",orders.purge(db(),OUT))
            except Exception as e: print("retention error",e)
            await asyncio.sleep(86400)
    asyncio.create_task(loop())

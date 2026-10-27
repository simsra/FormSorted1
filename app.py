import hashlib
"""FormSorted claim service prototype (AA1, DLA1A, PIP2, AR1). Run: uvicorn app:app --port 8000
Env: STRIPE_SECRET_KEY, PUBLIC_URL, ANTHROPIC_API_KEY/GEMINI_API_KEY/OPENAI_API_KEY, LLM_PROVIDER/LLM_MODEL/LLM_FALLBACKS, GROUNDING_PROVIDER/GROUNDING_MODEL/GROUNDING_FALLBACKS (see SETUP_RENDER_SUPABASE.md), BRAND. Placeholders => DEV mode (no payment, mock LLM)."""
import os, json, sqlite3, secrets, urllib.request, urllib.parse, base64, time
from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse, JSONResponse
import orders, mailer, asyncio, hmac, store
from fastapi.responses import Response, PlainTextResponse
import intake as INTAKE
import llm, fill_pdf, documents, quality, deadlines, letters, grounding, facts, ticks as TICKS, contsheet, formwatch
from html import escape as esc
from forms import FORMS, is_full, tier_info, default_tier, is_premium
import premium as PREMIUM
import bluebadge as BB, printmail
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
STEPS=["Choose","Pay","Agree","Questions","Deadline","Strength check","Approve","Your documents"]
BB_STEPS=["Choose","Agree","Your answers","Check and pay","Your Blue Badge answers"]
def bbprog(n): return f"<p class=progress>Step {n} of {len(BB_STEPS)}: {BB_STEPS[n-1]}</p><div class=bar><span style='width:{n*100//len(BB_STEPS)}%'></span></div>"
def prog(n): return f"<p class=progress>Step {n} of {len(STEPS)}: {STEPS[n-1]}</p><div class=bar><span style='width:{n*100//len(STEPS)}%'></span></div>"
def page(body,title="FormSorted",gov="https://www.gov.uk/browse/benefits/disability",minimal=False):
    if minimal:  # order summary: no outbound links except Terms/Privacy
        indep='<div class="indep"><div class="wrap"><span class="tag">Independent</span>Not affiliated with DWP or GOV.UK.</div></div>'
        ftr='<footer class="ftr"><div class="wrap"><p><strong>FormSorted</strong> is an independent online form-filling service. Not affiliated with DWP, GOV.UK or any government body. We can\'t guarantee an award or outcome.</p><p><a href="https://formsorted.com/privacy.html">Privacy</a><a href="https://formsorted.com/terms.html">Terms</a></p></div></footer>'
    else:
        indep=f'<div class="indep"><div class="wrap"><span class="tag">Independent</span>Not affiliated with DWP or GOV.UK.</div></div>'
        ftr='<footer class="ftr"><div class="wrap"><p><strong>FormSorted</strong> is an independent online form-filling service. Not affiliated with DWP, GOV.UK or any government body. We can\'t guarantee an award or outcome.</p><p><a href="https://formsorted.com/privacy.html">Privacy</a><a href="https://formsorted.com/terms.html">Terms</a><a data-contact href="mailto:hello@formsorted.com">Contact</a></p></div></footer>'
    return HTMLResponse(f"""<!doctype html><html lang=en-GB><head><meta charset=utf-8><meta name=viewport content='width=device-width,initial-scale=1'><link rel=icon href=/static/favicon.svg><link rel=stylesheet href=/static/app.css><title>{title} | {BRAND}</title><meta name=robots content=noindex></head><body><a href="#main" class="skip">Skip to main content</a>
<header class="hdr"><div class="wrap"><a class="logo" href="/"><img src="/static/logo.svg" alt="FormSorted home" width="170" height="36"></a></div></header>
{indep}<main id=main><div class=wrap>{body}</div></main>{ftr}</body></html>""")
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
        return page(prog(1)+pv+f"""<form method=get action=/><fieldset style="border:0;padding:0;margin:0"><legend><h1>Which form should we do for you?</h1></legend>{opts}</fieldset>
<div class=inset>Live in Scotland? We don't cover Scotland yet.</div>
<button class=btn>Continue</button></form>""","Choose your form")
    if form=="bb": return bb_summary(pv)
    f=FORMS[form]; ts=list(f["tiers"].items())
    if tier in f["tiers"]: return order_summary(form,tier,pv)
    if len(ts)<=2 and form!="atw": return order_summary(form,default_tier(form),pv)   # one product (+ optional upgrade shown on the summary)
    opts="".join(f"""<label class=radio><input type=radio name=tier value={t} {'checked' if (t==tier if tier in f['tiers'] else i==len(ts)-1) else ''} required><span><strong>{n} – £{p//100}</strong><span class=hint>{d}</span></span></label>""" for i,(t,(n,p,d)) in enumerate(ts))
    return page(prog(1)+pv+f"""<p class=caption>{f['short']}</p><form method=post action=/checkout><input type=hidden name=form value={form}><fieldset style="border:0;padding:0;margin:0"><legend><h1>How much should we do for you?</h1></legend>{opts}</fieldset>
<div class=promise><strong>Done for you, in your words.</strong> We write the answers and fill in the form; you check, sign and post it.</div><div class=inset>One-off fee. No success fee. Secure card payment. 14-day cancellation rights until your conversation starts.</div>
<button class="btn">Continue to payment</button></form><p><a href=/>Choose a different form</a></p>""","Choose your service",f["gov"])
PRICING_URL="https://formsorted.com/#prices"
DWP_LINE="You can claim directly from DWP for free; FormSorted is a paid online form-filling service."
TAPLINE="<div class=promise><strong>About 10 minutes. You only tap, we do the writing.</strong> Skip anything you're not sure about, and save your progress to finish later.</div>"
TRUST="<div class=trust><h2 class=h3>Our promise</h2><ul class=ticks><li><strong>Fixed price.</strong> You pay this once. Never a percentage of any award.</li><li><strong>You approve everything</strong> before you sign. Nothing is sent without you.</li><li>You get a copy of every page to keep for reviews.</li></ul></div>"
def chat_url(o): return f"/bb/{o['token']}" if o["form"]=="bb" else f"/intake/{o['token']}" if (o["form"] or "aa") in INTAKE.FORMS_V3 else f"/static/chat.html#{o['token']}"
def pack_items(form,tier):
    """What's included, as bullets, for one pack (a higher tier includes the lower one)."""
    out=[]
    for t,(n,p,d) in FORMS[form]["tiers"].items():
        d=d.replace("Everything above, plus ","").replace(", ready to check, sign and post free.",", ready to check, sign and post.").rstrip(".")
        out.append(d[0].upper()+d[1:])
        if t==tier: break
    return out
def order_summary(form,tier,pv=""):
    f=FORMS[form]; n,p,_=f["tiers"][tier]
    if is_premium(tier): items="".join(f"<li>{esc(i)}</li>" for i in pack_items(form,default_tier(form))+PREMIUM.PLUS_ITEMS+["You check and approve every word before anything is final"])
    else: items="".join(f"<li>{esc(i)}</li>" for i in pack_items(form,tier)+["You check and approve every word before anything is final"])
    up=upgrade_box(form,tier)
    return page(prog(1)+pv+f"""<div class=summary><p class=caption>Your order</p><h1>{esc(n)}</h1><p class=sub>{esc(f['short'])}</p>
<p class=lede><strong>We fill in your form. You check, sign and post.</strong> We ask you simple questions in plain English, then write it all up in your words.</p>{TAPLINE if form in INTAKE.FORMS_V3 else ""}
<h2 class=h3>What's included</h2><ul class=ticks>{items}</ul>
<div class=total><span>Total</span><strong>£{p//100}</strong></div><p class=hint>Nothing to pay now. Answer the questions first; you pay once at the end, when your form is ready to prepare. One-off fee. No success fee.</p>
<form method=post action=/checkout><input type=hidden name=form value={form}><input type=hidden name=tier value={tier}><button class="btn btn-wide">Start my form</button></form>
{up}{BB_ADDON_LINE if form in BB.PARENT_FORMS else ""}<p class=hint>{esc(DWP_LINE)}</p><p class=change><a href="{PRICING_URL}">Change form or pack</a></p></div>""",f"Your order: {n}",minimal=True)
def upgrade_box(form,tier):
    """Clear side-by-side comparison of the two packs, with a button to switch."""
    ts=FORMS[form]["tiers"]
    if len(ts)<2 or form=="atw": return ""
    base,plus=list(ts)[0],[t for t in ts if is_premium(t)]
    if not plus: return ""
    plus=plus[0]; (bn,bp,_),(pn,pp,_)=ts[base],ts[plus]
    rows=[("Official form filled in, or extra sheets",1,1),("Your answers in your own words, checked against what you told us",1,1),("Evidence checklist",1,1)]+[(x,0,1) for x in PREMIUM.PLUS_ITEMS]
    tr="".join(f"<tr><td>{esc(l)}</td><td>{'✓' if b else '–'}</td><td>{'✓' if p else '–'}</td></tr>" for l,b,p in rows)
    other=plus if tier==base else base; on,op,_=ts[other]
    return f"""<div class=compare><h2 class=h3>Compare packs</h2><table><thead><tr><th></th><th>{esc(bn)}<br>£{bp//100}</th><th>{esc(pn)}<br>£{pp//100}</th></tr></thead><tbody>{tr}</tbody></table>
<form method=get action=/><input type=hidden name=form value={form}><input type=hidden name=tier value={other}><button class="btn btn-2">{'Upgrade to' if other==plus else 'Switch to'} {esc(on)}, £{op//100}</button></form></div>"""
FREE_PER_IP_DAY=int(os.getenv("FREE_PER_IP_DAY","5")); MAX_TURNS=int(os.getenv("MAX_TURNS","40")); FREE_PER_DAY_TOTAL=int(os.getenv("FREE_PER_DAY_TOTAL","500"))
def client_ip(req):
    """Real visitor IP. Render sits behind Cloudflare: True-Client-IP / CF-Connecting-IP are set by Cloudflare and can't be spoofed.
    Render only appends to X-Forwarded-For (leftmost entries are client-controlled), so the fallback is the entry Cloudflare added
    (second from the right, before the Cloudflare edge), then the socket address (local dev)."""
    for h in ("true-client-ip","cf-connecting-ip"):
        v=req.headers.get(h,"").strip()
        if v: return v[:64]
    xff=[x.strip() for x in req.headers.get("x-forwarded-for","").split(",") if x.strip()]
    if len(xff)>=2: return xff[-2][:64]
    return (xff[-1] if xff else (req.client.host if req.client else ""))[:64]
@app.post("/checkout")
def checkout(req:Request, tier:str=Form(...), form:str=Form("aa")):
    """Pick a pack -> free interview (pay at the end, on the preview page)."""
    if form not in FORMS or tier not in FORMS[form]["tiers"] or (form=="bb" and tier!=BB.SOLO_TIER): raise HTTPException(400)
    ip=client_ip(req); c=db()
    day=time.time()-86400
    n=c.execute("select count(*) from orders where ip=? and created>?",(ip,day)).fetchone()[0]
    tot=c.execute("select count(*) from orders where status='free' and created>?",(day,)).fetchone()[0]
    if (ip and n>=FREE_PER_IP_DAY) or tot>=FREE_PER_DAY_TOTAL:
        return page("<h1>You've started a few already today</h1><p class=lead>To keep things fair we limit how many new forms can be started from one connection each day. Please come back tomorrow, or use the link to a form you've already started.</p>","Please try tomorrow")
    token=orders.new_token()
    c.execute("insert into orders(token,tier,status,created,form,ip) values(?,?,?,?,?,?)",(token,tier,"free",time.time(),form,ip)); c.commit()
    return RedirectResponse(f"/start/{token}",303)
def stripe_session(o):
    form=o["form"] or "aa"; name,price,_=tier_info(form,o["tier"]); token=o["token"]
    return stripe("POST","/checkout/sessions",{"mode":"payment","line_items[0][quantity]":1,"line_items[0][price_data][currency]":"gbp",
      "line_items[0][price_data][unit_amount]":price,"line_items[0][price_data][product_data][name]":f"{FORMS[form]['name']}: {name}",
      "client_reference_id":token,"adaptive_pricing[enabled]":"false","locale":"en-GB","allow_promotion_codes":"true","customer_creation":"always","consent_collection[terms_of_service]":"required",
      "success_url":f"{PUBLIC}/success?session_id={{CHECKOUT_SESSION_ID}}","cancel_url":f"{PUBLIC}/preview/{token}"})
def covered(o):
    h=json.loads(o["history"] or "[]"); total=len(FORMS[o["form"] or "aa"]["topics"])
    return min(sum(1 for m in h if m["role"]=="user" and m["content"].strip()),total),total
@app.get("/preview/{token}")
def preview(token:str):
    o=ready(token,paid=False)
    if o["status"]=="paid": return RedirectResponse(f"/start/{token}",303)
    if not o["interview_done_at"]: return RedirectResponse(chat_url(o),303)
    if o["form"]=="bb": return bb_preview(o)
    f=FORMS[o["form"] or "aa"]; n,p,_=tier_info(o["form"] or "aa",o["tier"]); got,total=INTAKE.coverage(o["form"],json.loads(o["intake"])) if o["intake"] else covered(o)
    facts=[f"Your details cover {got} of {total} sections of the form" if o["intake"] else f"{got} of {total} topics covered in your conversation",f"Prepared for the {esc(f['short'])}"]+[esc(i) for i in pack_items(o["form"] or "aa",o["tier"])]
    return page(f"""<div class=summary><p class=caption>Details gathered</p><h1>We're ready to fill in your form</h1>
<p class=lede><strong>We fill in the whole official form for you. You just check it, sign it and post it.</strong> Pay once and we write every section from what you tapped, check each one against what you told us, and you approve it before anything is final.</p>
<figure class=lockprev><img src="/static/preview-placeholder.svg" alt="Example illustration of a filled-in form (not your answers)" width=520 height=360><figcaption>Illustration only. Your own answers appear after payment.</figcaption></figure>
<ul class=ticks>{''.join(f'<li>{x}</li>' for x in facts)}</ul>
<div class=total><span>{esc(n)}</span><strong>£{p//100}</strong></div>
<form method=post action=/pay/{token}>{KEEP_OPT if is_premium(o["tier"]) else ""}<label class=cb><input type=checkbox name=waive required><span>Please start preparing my form straight away. I understand that once you start I lose my 14-day right to cancel.</span></label>
<button class="btn btn-wide">Pay £{p//100} to get your completed form</button></form>{TRUST}{f'<p class=change><a href="/intake/{token}?s=about">Change my answers</a></p>' if o["intake"] else ''}
<p class=hint>One-off fee. No success fee. If you don't pay, we delete everything you told us after 7 days.</p><p class=hint>{esc(DWP_LINE)}</p></div>""","Your form is ready",minimal=True)
KEEP_OPT="<label class=cb><input type=checkbox name=keep value=1><span>Keep my answers for 3 years, so you can help with a reconsideration or my renewal without asking again. I can delete them at any time. (Optional. Without this we delete them after 90 days.)</span></label>"
THREE_YEARS=3*365*86400
@app.post("/pay/{token}")
def pay(token:str, waive:str=Form(...), keep:str=Form("")):
    o=ready(token,paid=False)
    if keep and is_premium(o["tier"]) and o["status"]!="paid": c0=db(); c0.execute("update orders set keep_until=? where token=?",(time.time()+THREE_YEARS,token)); c0.commit()
    if o["status"]=="paid": return RedirectResponse(f"/start/{token}",303)
    if not o["interview_done_at"]: return RedirectResponse(chat_url(o),303)
    c=db()
    if DEV:
        c.execute("update orders set status='paid', paid_at=? where token=?",(time.time(),token)); c.commit(); return RedirectResponse(f"/start/{token}",303)
    s=stripe_session(o); c.execute("update orders set stripe_session=? where token=?",(s["id"],token)); c.commit()
    return RedirectResponse(s["url"],303)
@app.get("/success")
def success(session_id:str=""):
    c=db(); row=c.execute("select * from orders where stripe_session=?",(session_id,)).fetchone() if session_id else None
    try: s=stripe("GET","/checkout/sessions/"+urllib.parse.quote(session_id)) if session_id else {}
    except Exception: s={}
    if s.get("payment_status")=="paid":
        c.execute("update orders set status='paid', email=coalesce(?,email) where stripe_session=?",((s.get("customer_details") or {}).get("email"),session_id)); c.commit()
        return RedirectResponse(f"/start/{s.get('client_reference_id') or row['token']}",303)
    if row and row["status"]=="paid": return RedirectResponse(f"/start/{row['token']}",303)   # webhook already confirmed it
    if not s and session_id: return page("<h1>We're confirming your payment</h1><p>This can take a minute. <a href='/success?session_id="+urllib.parse.quote(session_id)+"'>Refresh this page</a>. If you were charged, email <a href=mailto:hello@formsorted.com>hello@formsorted.com</a>.</p>","Confirming payment")
    back=f"/preview/{row['token']}" if row else "/"
    return page(f"<h1>Payment not completed</h1><p>You have not been charged. <a href={back}>Go back and try again</a>.</p>","Payment not completed")
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
        if form not in FORMS or not ({**FORMS[form].get("legacy_tiers",{}),**FORMS[form]["tiers"]}.get(tier) or (0,None))[1]==s.get("amount_total"): raise HTTPException(422,"unknown product")
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
    if o["status"] not in ("paid","free"): raise HTTPException(402)
    if o["consent_at"] and o["form"]=="bb":
        return RedirectResponse(f"/bb/{token}/documents" if o["status"]=="paid" else f"/preview/{token}" if o["interview_done_at"] else f"/bb/{token}",303)
    if o["consent_at"]:
        if o["status"]=="paid" and o["interview_done_at"] and not o["draft"]:
            if o["intake"] and not json.loads(o["intake"]).get("uploads_done"): return RedirectResponse(f"/uploads/{token}",303)
            return RedirectResponse(f"/prepare/{token}",303)
        if o["status"]=="free" and o["interview_done_at"]: return RedirectResponse(f"/preview/{token}",303)
        if o["draft"] and (o["form"] or "aa") in INTAKE.FORMS_V3: return RedirectResponse(f"/{'documents' if o['approved_at'] and o['details_at'] else 'details' if o['approved_at'] else 'deadline'}/{token}",303)
        return RedirectResponse(chat_url(o),303)
    lead="Payment received. Please confirm 2 things." if o["status"]=="paid" else "Answer the questions first. You only pay at the end, if you want your completed form. Please confirm 2 things."
    return page((bbprog(2) if o["form"]=="bb" else prog(3))+f"""<h1>Before we start</h1><p class=lead>{lead}</p><form method=post action=/consent/{token}>
<label class=cb><input type=checkbox name=health required><span>I agree to {BRAND} using the health information I give to prepare this form. If it's about someone else, they agree, or I can act for them.</span></label>
<label class=cb><input type=checkbox name=truth required><span>I'll only give true information and will check everything before sending it.</span></label>
<div class=warning>{"Giving false information on a Blue Badge application is an offence." if o["form"]=="bb" else "Giving false information on a benefit claim is an offence."}</div>
<button class="btn btn-start">Start</button></form><p class=small>If you don't pay, we delete your information after 7 days. If you do, after 90 days, or sooner if you ask. <a href="https://formsorted.com/privacy.html">Privacy notice</a></p>""","Before we start")
@app.post("/consent/{token}")
def consent(token:str, health:str=Form(...), truth:str=Form(...), digital:str=Form("")):
    o=get(token)
    if o["status"] not in ("paid","free"): raise HTTPException(403)
    c=db(); c.execute("update orders set consent_at=? where token=?",(time.time(),token)); c.commit()
    return RedirectResponse(chat_url(o),303)
@app.get("/prepare/{token}")
def prepare(token:str):
    """After payment: draft from the interview (the only place drafting happens), then continue the paid flow."""
    o=ready(token)
    if not o["draft"]:
        h=json.loads(o["history"]); I=json.loads(o["intake"] or "{}")
        if I.get("doc_text"): h=h+[{"role":"assistant","content":"Documents you uploaded"},{"role":"user","content":I["doc_text"][:12000]}]
        d=llm.draft(h,o["form"] or "aa"); d.setdefault("answers",{})
        if I: merge_intake(o["form"] or "aa",d,I)
        c=db(); c.execute("update orders set draft=?, approved_at=null where token=? and draft is null",(json.dumps(d),token)); c.commit()
    return RedirectResponse(f"/deadline/{token}",303)
def merge_intake(form,d,I):
    """Facts the customer tapped go straight in (numbers, conditions, signing notes, tick boxes); the drafter only writes sentences."""
    d.setdefault("extra",{}).update(INTAKE.extra(form,I))
    if I.get("conds"): d["conditions"]=INTAKE.conditions(I)
    d["notes_for_user"]=INTAKE.notes(form,I)+list(d.get("notes_for_user") or [])
    if I.get("uploads"): d.setdefault("checklist",[]).append("Documents you uploaded to us: "+", ".join(u["name"] for u in I["uploads"])+". Send copies (not originals) with your form.")
    d["intake_ticks"]=INTAKE.ticks(form,I)
def ready(token,paid=True):
    """paid=True (default) for everything that exposes or produces answers; paid=False only for the free interview."""
    o=get(token)
    if o["status"] not in (("paid",) if paid else ("paid","free")) or not o["consent_at"]: raise HTTPException(402 if o["status"]=="free" else 403)
    if o["created"] and o["created"]<time.time()-86400*orders.RETENTION_DAYS: raise HTTPException(410)
    return o
@app.post("/api/{token}/message")
async def message(token:str, req:Request):
    o=ready(token,paid=False); h=json.loads(o["history"]); msg=(await req.json()).get("text","").strip()
    total=len(FORMS[o["form"] or "aa"]["topics"])+1
    if o["interview_done_at"] and o["status"]!="paid": return {"reply":"[[DONE]]","done":True,"topic":total,"total":total}
    if msg: h.append({"role":"user","content":msg[:4000]})
    if sum(1 for m in h if m["role"]=="user")>MAX_TURNS:
        c=db(); c.execute("update orders set history=? where token=?",(json.dumps(h),token)); c.commit()
        return {"reply":"[[DONE]]","done":True,"topic":total,"total":total}
    q=llm.next_question(h,o["form"] or "aa"); h.append({"role":"assistant","content":q})
    c=db(); c.execute("update orders set history=? where token=?",(json.dumps(h),token)); c.commit()
    answered=sum(1 for m in h if m["role"]=="user" and m["content"].strip())
    return {"reply":q,"done":"[[DONE]]" in q,"topic":min(answered+1,total),"total":total}
@app.post("/api/{token}/finish")
def finish(token:str):
    o=ready(token,paid=False)
    c=db(); c.execute("update orders set interview_done_at=coalesce(interview_done_at,?) where token=?",(time.time(),token)); c.commit()
    return {"next":f"/prepare/{token}" if o["status"]=="paid" else f"/preview/{token}"}
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
    if is_premium(o["tier"]):
        I=json.loads(o["intake"] or "{}")
        open(os.path.join(od,"assessment-briefing.html"),"w").write(PREMIUM.briefing(BRAND,form,personal,d)); files.append("assessment-briefing.html")
        open(os.path.join(od,"supporting-letters.html"),"w").write(PREMIUM.supporting_letters(BRAND,form,personal,d,I.get("people"))); files.append("supporting-letters.html")
        if o["appeal"]:
            ap=json.loads(o["appeal"]); nm=" ".join(x for x in (personal.get("other_names"),personal.get("surname")) if x)
            addr=", ".join(personal.get(k) for k in ("addr1","addr2","addr3","postcode") if personal.get(k))
            txt=letters.mr_letter(form if form in letters.NAMES else "pip",{"name":nm,"address":addr,"decision_date":datetime_fmt(ap["decision_date"]) if ap.get("decision_date") else "","points":PREMIUM.appeal_letter_points(form,d,ap.get("topics",[])),"evidence":["A copy of the decision letter"]+[u["name"] for u in ap.get("uploads",[])]})
            open(os.path.join(od,"reconsideration-letter.txt"),"w").write(txt); files.append("reconsideration-letter.txt")
    store.put_dir(token,od,files)   # to private Supabase bucket when configured (local temp copy removed)
    return files
def prefill_off(o):
    """Reason pre-fill is switched off for this order's form (e.g. GOV.UK published a new version), else None."""
    F=FORMS[o["form"] or "aa"]
    return formwatch.disabled_reason(o["form"] or "aa") if (is_full(o["tier"]) and F["pdf"]) else None
def pack_files(o):
    form=o["form"] or "aa"; F=FORMS[form]
    if form=="atw": return ["answers.html","AccessToWork-answers.docx"]
    files=["answers.html"]
    if is_full(o["tier"]) and F["pdf"] and not prefill_off(o): files.append(F["pdf_out"])
    if form in ("pip","pipr"): files.append("PIP-extra-sheets.pdf")
    if is_premium(o["tier"]): files+=["assessment-briefing.html","supporting-letters.html"]+(["reconsideration-letter.txt"] if o["appeal"] else [])
    return files
def needs_ticks(o): return (o["form"] or "aa") in TICKS.CATALOG and is_full(o["tier"]) and FORMS[o["form"] or "aa"]["pdf"] and not prefill_off(o)
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
    o=ready(token,paid=False); f=FORMS[o["form"] or "aa"]; return {"form":o["form"] or "aa","short":f["short"],"gov":f["gov"],"pdf":f.get("pdf_out")}
@app.post("/api/{token}/personal")
async def personal(token:str, req:Request):
    ready(token); c=db(); c.execute("update orders set personal=? where token=?",(json.dumps(await req.json()),token)); c.commit(); return {"ok":True}
@app.get("/download/{token}/{name}")
def download(token:str,name:str):
    o=ready(token)
    if not o["approved_at"] or not o["details_at"]: raise HTTPException(403,"Approve your answers first")
    if name not in pack_files(o): raise HTTPException(404)
    data=store.read(token,name)
    if data is None: raise HTTPException(404)
    ct={"html":"text/html; charset=utf-8","txt":"text/plain; charset=utf-8","pdf":"application/pdf","docx":"application/vnd.openxmlformats-officedocument.wordprocessingml.document"}[name.rsplit(".",1)[1]]
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
POST_OPT="<label class=cb><input type=checkbox name=post_pack value=1><span>Print and post my pack to the address above, with a return envelope. You still check, sign and send the form yourself.</span></label>"
@app.get("/details/{token}")
def details_page(token:str, err:str=""):
    o=ready(token)
    if not o["approved_at"]: return RedirectResponse(f"/approve/{token}",303)
    if ticks_pending(o): return RedirectResponse(f"/ticks/{token}",303)
    p=json.loads(o["personal"] or "{}"); form=o["form"] or "aa"
    if o["intake"] and not o["details_at"]: p={**INTAKE.personal_prefill(form,json.loads(o["intake"])),**p}
    who="the child" if form=="dla" else "the person claiming"
    rows="".join(f"""<div class=field><label class=q for=d_{k}>{esc(l)}</label><input id=d_{k} name={k} {'type='+t if t else ''} value="{esc(p.get(k,''))}" {'required' if req else ''} autocomplete=off></div>""" for k,l,t,req in detail_fields(form))
    return page(prog(8)+f"""<h1>Your details</h1><p class=lead>We add these to your documents{'' if form=='atw' else f' for {who}'} so you have less to fill in by hand. We only ask now, at the end, so we don't keep them longer than needed.</p>
{f'<div class=warning>{esc(err)}</div>' if err else ''}<form method=post action=/details/{token}>{rows}{POST_OPT if (is_premium(o["tier"]) and printmail.ENABLED) else ""}<button class=btn>Save and make my documents</button></form>
<form method=post action=/details/{token}><input type=hidden name=skip value=1><button class="btn btn-2">Skip. I'll write my details in by hand</button></form>
<p class=small>We never ask for bank details. We delete everything 90 days after your order, or now: <a href=/delete/{token}>delete my information</a>.</p>""","Your details")
@app.post("/details/{token}")
async def details_save(token:str, req:Request):
    o=ready(token)
    if not o["approved_at"]: return RedirectResponse(f"/approve/{token}",303)
    if ticks_pending(o): return RedirectResponse(f"/ticks/{token}",303)
    fm=await req.form(); form=o["form"] or "aa"; p={}
    def back(msg):  # keep what they typed so a validation error doesn't wipe the form
        c=db(); c.execute("update orders set personal=? where token=?",(json.dumps(p),token)); c.commit()
        return RedirectResponse(f"/details/{token}?err="+urllib.parse.quote(msg),303)
    if not fm.get("skip"):
        missing=False
        for k,_,_,need in detail_fields(form):
            v=str(fm.get(k,"")).strip()[:200]
            if need and not v: missing=True
            if v: p[k]=v
        if missing: return back("Please fill in every required box, or choose Skip.")
        if p.get("ni"):
            p["ni"]=p["ni"].replace(" ","").upper()
            if not NI_RE.match(p["ni"]): return back("That National Insurance number doesn't look right. It's 2 letters, 6 numbers, then A, B, C or D.")
    c=db(); c.execute("update orders set personal=?, details_at=?, post_pack=? where token=?",(json.dumps(p),time.time(),1 if (fm.get("post_pack") and is_premium(o["tier"]) and printmail.ENABLED and not fm.get("skip")) else 0,token)); c.commit()
    o=get(token); files=build_files(token,o,json.loads(o["draft"]))
    if o["post_pack"]: printmail.queue(c,token,{k:p.get(k,"") for k in ("title","other_names","surname","addr1","addr2","addr3","postcode")},files)
    return RedirectResponse(f"/documents/{token}",303)

# ---------- Intake v3: tap-first questions (AA1, DLA1A, PIP2) ----------
def _intake_order(token):
    o=ready(token,paid=False)
    if (o["form"] or "aa") not in INTAKE.FORMS_V3: raise HTTPException(404)
    return o
def _intake_closed(o):
    """Paid orders that have been drafted can't change their answers here (they edit on the approve page)."""
    return o["status"]=="paid" and o["draft"]
@app.get("/intake/{token}")
def intake_page(token:str, s:str=""):
    o=_intake_order(token)
    if _intake_closed(o): return RedirectResponse(f"/start/{token}",303)
    form=o["form"]; secs=INTAKE.SECTIONS[form]; ids=[k for k,_ in secs]; d=json.loads(o["intake"] or "{}")
    sec=s if s in ids else (d.get("at") if d.get("at") in ids else ids[0]); i=ids.index(sec)
    left=max(1,round(10*(len(ids)-i)/len(ids)))
    bar="".join(f'<li class="{"done" if j<i else "now" if j==i else ""}">{esc(l)}</li>' for j,(k,l) in enumerate(secs))
    reassure="<p class=reassure>It's normal for this to feel hard. You only tap, we do the writing. Skip anything you're not sure about.</p>" if i==0 else ""
    return page(f"""<div class=intake><p class="progress ip"><span>Building your form · Part {i+1} of {len(secs)}</span><span class=left>~{left} min</span></p><div class="bar slim"><span style='width:{(i+1)*100//len(secs)}%'></span></div>
{'<h1>We\'ll fill in your form for you</h1><p class=donefor>About 10 minutes. You only tap, we do the writing. Skip anything you\'re not sure about.</p>' if i==0 else f'<h1>{esc(secs[i][1])}</h1><p class=donefor>Just tap what fits. We\'ll write this section of the official form for you.</p>'}
<form method=post action=/intake/{token}><input type=hidden name=sec value={sec}>{INTAKE.section_body(form,sec,d)}
<div class=navrow>{f'<button class="btn btn-2" name=nav value=back>Back</button>' if i else ''}<button class="btn btn-start" name=nav value=next>{'Finish' if i==len(ids)-1 else 'Next: '+esc(secs[i+1][1])}</button></div>
<button class="linkbtn" name=nav value=save>Save and finish later</button></form></div>""",secs[i][1],minimal=True)
@app.post("/intake/{token}")
async def intake_save(token:str, req:Request):
    o=_intake_order(token)
    if _intake_closed(o): return RedirectResponse(f"/start/{token}",303)
    form=o["form"]; ids=[k for k,_ in INTAKE.SECTIONS[form]]; fm=await req.form(); sec=str(fm.get("sec",""))
    if sec not in ids: raise HTTPException(400)
    d=INTAKE.save(form,sec,json.loads(o["intake"] or "{}"),fm); i=ids.index(sec); nav=fm.get("nav","next")
    nxt=ids[max(0,i-1)] if nav=="back" else ids[i] if nav=="save" else (ids[i+1] if i+1<len(ids) else None)
    d["at"]=nxt or sec; c=db()
    if nxt is None:   # finished: build the answers transcript the rest of the pipeline uses
        c.execute("update orders set intake=?, history=?, interview_done_at=? where token=?",(json.dumps(d),json.dumps(INTAKE.history(form,d)),time.time(),token)); c.commit()
        return RedirectResponse(f"/start/{token}" if o["status"]=="paid" else f"/preview/{token}",303)
    c.execute("update orders set intake=?, interview_done_at=null where token=? and status in ('free','paid')",(json.dumps(d),token)); c.commit()
    if nav=="save":
        return page(f"""<h1>Your answers are saved</h1><p class=lead>Come back any time in the next 7 days with this private link. Keep it safe: anyone with the link can see your answers.</p>
<p class=savelink><code>{esc(PUBLIC)}/intake/{token}</code></p><button class=btn onclick="navigator.clipboard.writeText('{esc(PUBLIC)}/intake/{token}')">Copy link</button>
<p><a href="/intake/{token}?s={nxt}">Carry on now</a></p>""","Saved",minimal=True)
    return RedirectResponse(f"/intake/{token}?s={nxt}",303)
UP_MAX=10*1024*1024; UP_TYPES={"application/pdf":"pdf","image/jpeg":"jpg","image/png":"png","image/heic":"heic","image/webp":"webp"}
@app.get("/uploads/{token}")
def uploads_page(token:str, err:str=""):
    o=ready(token)   # paid only
    if o["draft"]: return RedirectResponse(f"/start/{token}",303)
    I=json.loads(o["intake"] or "{}"); ups=I.get("uploads") or []
    lst="".join(f"<li>{esc(u['name'])}</li>" for u in ups)
    return page(prog(4)+f"""<h1>Got any letters or lists? (optional)</h1><p class=lead>Payment received, thank you. If you have a photo or PDF of a medication list, hospital or clinic letter, care plan, EHCP or previous award letter, add it here. We use it to make your answers more complete. You'll still check everything before it's final.</p>
{f'<div class=warning>{esc(err)}</div>' if err else ''}{f'<h2 class=h3>Added</h2><ul class=ticks>{lst}</ul>' if ups else ''}
<form method=post action=/uploads/{token} enctype=multipart/form-data><div class=field><label class=q for=up>Add photos or PDFs (up to 10MB each)</label><input id=up type=file name=files multiple accept="image/*,application/pdf" capture=environment></div><button class="btn btn-2">Add</button></form>
<form method=post action=/uploads/{token}/done><button class="btn btn-start">{'Continue' if ups else 'Skip. Prepare my form'}</button></form>
<p class=small>Your documents are deleted with the rest of your order after 90 days, or sooner if you ask.</p>""","Add documents")
@app.post("/uploads/{token}")
async def uploads_add(token:str, req:Request):
    o=ready(token)
    if o["draft"]: return RedirectResponse(f"/start/{token}",303)
    fm=await req.form(); I=json.loads(o["intake"] or "{}"); ups=I.setdefault("uploads",[]); err=""
    from pypdf import PdfReader; import io
    for f in fm.getlist("files"):
        if not getattr(f,"filename",None): continue
        data=await f.read(); ext=UP_TYPES.get(f.content_type or "")
        if not ext or len(data)>UP_MAX or len(ups)>=10: err="Some files weren't added: we take photos and PDFs up to 10MB, 10 files at most."; continue
        safe=_re.sub(r"[^A-Za-z0-9._-]","_",f.filename)[:60]; nm=f"upload-{len(ups)+1}-{safe}"
        od=os.path.join(OUT,token,"up"); os.makedirs(od,exist_ok=True); open(os.path.join(od,nm),"wb").write(data); store.put_dir(token,od,[nm])
        ups.append({"name":f.filename[:80],"key":nm,"type":ext})
        if ext=="pdf":
            try: I["doc_text"]=(I.get("doc_text","")+f"\n[{f.filename[:80]}]\n"+"\n".join((pg.extract_text() or "") for pg in PdfReader(io.BytesIO(data)).pages[:15]))[:20000]
            except Exception as e: print("pdf text failed",e)
    c=db(); c.execute("update orders set intake=? where token=?",(json.dumps(I),token)); c.commit()
    return RedirectResponse(f"/uploads/{token}"+("?err="+urllib.parse.quote(err) if err else ""),303)
@app.post("/uploads/{token}/done")
def uploads_done(token:str):
    o=ready(token); I=json.loads(o["intake"] or "{}"); I["uploads_done"]=True
    c=db(); c.execute("update orders set intake=? where token=?",(json.dumps(I),token)); c.commit()
    return RedirectResponse(f"/prepare/{token}",303)

# ---------- Deadline tracker, strength check, approval, saved answers, review mode, MR letter ----------
PROMISE="<div class=promise><strong>Your words only.</strong> We only use what you told us. You approve every word before you send.</div>"
def ordered(token):
    o=ready(token)
    if not o["draft"]: return RedirectResponse(chat_url(o),303),None,None
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
        box=f"""<div class="tracker" id=tracker>{when}<p>{esc(res['rule'])}</p>{f"<p><strong>{esc(res['backdate'])}</strong></p>" if res['backdate'] else ''}<p class=small>Source: {res['source'].replace('https://www.','')} (checked 24 Oct 2026)</p></div>
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
def _strength(o,d):
    """('v4', gaps, intake) for tap forms; ('legacy', results, None) for chat forms."""
    form=o["form"] or "aa"; I=json.loads(o["intake"] or "{}") if o["intake"] else {}
    if I and form in INTAKE.FORMS_V3: return "v4",quality.gaps_v4(form,I),I
    return "legacy",quality.check_legacy_v2(d["answers"],FORMS[form]["topics"],o["form"]),None
@app.get("/check/{token}")
def check_page(token:str):
    r,o,d=ordered(token)
    if r: return r
    mode,G,I=_strength(o,d); skip=f'<a class="btn btn-2" href="/approve/{token}">Skip, my form is ready</a>'
    if not G:
        return page(prog(6)+f"""<h1>Your answers look complete</h1><p class=lead>We've got what we need to fill in your form.</p><p><a class=btn href="/approve/{token}">Continue to check your form</a></p>""","Strength check")
    if mode=="v4":
        rows="".join(f"""<fieldset class="sc iq"><legend><strong>{esc(g['label'])}</strong>: {esc(g['q'])}</legend><div class="chips{' nums' if g['kind']=='days' else ''}">{''.join(f'<label class=chip><input type=radio name="g_{g["rid"]}_{g["kind"]}" value="{v}"><span>{esc(t)}</span></label>' for v,t in g['opts'])}</div>
{'' if g.get('noelse') else f'<label class=hint for="g_{g["rid"]}_{g["kind"]}_x">Something else, or add a detail (optional)</label><input type=text id="g_{g["rid"]}_{g["kind"]}_x" name="g_{g["rid"]}_{g["kind"]}_x" maxlength=500>'}</fieldset>""" for g in G)
    else:
        rows="".join(f"""<div class="sc"><h3>{esc(x['label'])}</h3><p class=ans>{esc(x['answer'])}</p>{''.join(f'<p class=hint>{esc(f)}</p>' for f in x['flags'])}<label class=hint for="add_{x['id']}">Add detail in your own words (optional)</label><textarea id="add_{x['id']}" name="add_{x['id']}" rows=2></textarea></div>""" for x in G)
    n=len(G); qs=f"{n} quick question{'s' if n>1 else ''}"
    return page(prog(6)+f"""<h1>We can make these stronger</h1><p class=lead>{qs} to make your form stronger (optional). Only add what's true.</p>
<form method=post action=/check/{token}>{rows}<p><button class=btn>Save and continue</button> {skip}</p></form>""","Strength check")
@app.post("/check/{token}")
async def check_save(token:str, req:Request):
    r,o,d=ordered(token)
    if r: return r
    fm=await req.form(); a=d["answers"]; extra=d.setdefault("user_added",{})
    def add(tid,v):
        a[tid]=((a.get(tid) or "")+" "+v).strip(); extra[tid]=(extra.get(tid,"")+" "+v).strip()
    mode,G,I=_strength(o,d)
    if mode=="v4":
        form=o["form"]; changed=False
        for g in G:
            n=f"g_{g['rid']}_{g['kind']}"; val=str(fm.get(n) or ""); other=str(fm.get(n+"_x") or "").strip()
            if val not in dict(g["opts"]): val=""
            if not val and not other: continue
            s=quality.gap_sentence(form,I,g,val,other)
            if s: add(g["topic"],s)
            quality.apply_gap(I,g,val); changed=True
        if changed: c=db(); c.execute("update orders set intake=? where token=?",(json.dumps(I),token)); c.commit()
    for k,v in fm.items():
        if k.startswith("add_") and v.strip():
            tid=k[4:]; v=v.strip()[:2000]
            add("other" if tid=="_bad" else tid,v)
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
def _ghash(o,d):
    F=FORMS[o["form"] or "aa"]
    return hashlib.sha256(json.dumps([[d["answers"].get(t,"") for t,_,_ in F["topics"]],source_text(o,d)]).encode()).hexdigest()[:16]
def ground_cached(o,d,token):
    """The checker can return different phrases each call, so the flags shown on the page are stored and the same ones
    are used when the page is submitted (otherwise choices no longer match and people get stuck)."""
    h=_ghash(o,d); gc=d.get("gcache") or {}
    if gc.get("h")==h: return gc["G"]
    G=ground(o,d); d["gcache"]={"h":h,"G":G}
    c=db(); c.execute("update orders set draft=? where token=?",(json.dumps(d),token)); c.commit()
    return G
def sentence_of(answer,phrase):
    """The whole sentence in the answer that contains the flagged phrase (None if it isn't in the answer)."""
    pl=" ".join(phrase.lower().split())
    for snt in grounding.sentences(answer):
        if pl and pl in " ".join(snt.lower().split()): return snt
    return None
def flag_items(o,d,G):
    """One item per distinct flagged sentence. Identical sentences (even in different answers) share one choice."""
    F=FORMS[o["form"] or "aa"]; items={}
    for t,_,_ in F["topics"]:
        for x in G.get(t,[]):
            snt=sentence_of(d["answers"].get(t,""),x["phrase"])
            if not snt: continue   # phrase not actually in this answer: nothing to approve or remove
            k=hashlib.sha1(" ".join(snt.lower().split()).encode()).hexdigest()[:10]
            it=items.setdefault(k,{"key":k,"sentence":snt,"topics":[],"kinds":[]})
            if t not in it["topics"]: it["topics"].append(t)
            if x["kind"] not in it["kinds"]: it["kinds"].append(x["kind"])
    return list(items.values())
def flag_html(t,its,fm,need,labels):
    its=[i for i in its if i["topics"][0]==t]
    if not its: return ""
    def one(i):
        ch=fm.get(f"res_{i['key']}") if fm else None; also=[labels[x] for x in i["topics"][1:]]
        opts="".join(f'<label><input type=radio name="res_{i["key"]}" value={v} required {"checked" if ch==v else ""}> {l}</label>' for v,l in (("keep","Keep, it's true"),("edit","I've edited the answer"),("remove","Remove it")))
        return f"""<li id="res_{i['key']}" class="{'needs' if i['key'] in need else ''}">{'<p class=err>Please choose one</p>' if i['key'] in need else ''}<p><strong>"{esc(i['sentence'])}"</strong> <span class=hint>({esc(', '.join(i['kinds']))})</span></p>{f'<p class=hint>Also in: {esc(", ".join(also))}. Your choice applies to both.</p>' if also else ''}<div class=resopts>{opts}</div></li>"""
    return f"""<div class=ground><p class=flag>We couldn't find this in what you told us — keep, edit or remove</p><ul>{''.join(one(i) for i in its)}</ul></div>"""
def render_approve(token,o,d,G,fm=None,need_ok=(),need_res=()):
    F=FORMS[o["form"] or "aa"]; sm=said_map(o); added=d.get("user_added",{}); labels={t:l for t,l,_ in F["topics"]}; its=flag_items(o,d,G)
    ans=lambda t: str(fm.get(f"ans_{t}")) if fm and fm.get(f"ans_{t}") is not None else d['answers'].get(t,'')
    rows="".join(f"""<div class="trace{' needs' if t in need_ok else ''}" id="topic_{t}"><h3>{esc(l)}</h3><div class=cols><div><p class=lbl>What you told us</p><p class=you>{esc(sm.get(t,'')) or '<em>Nothing for this topic</em>'}{f'<br><strong>You added:</strong> {esc(added[t])}' if t in added else ''}</p></div>
<div><p class=lbl>What goes on the form (edit if needed)</p><textarea name="ans_{t}" rows=4>{esc(ans(t))}</textarea></div></div>
{flag_html(t,its,fm,need_res,labels)}{'<p class=err>Please tick to approve this answer</p>' if t in need_ok else ''}<label class=cb><input type=checkbox id="ok_{t}" name="ok_{t}" required {'checked' if fm and fm.get(f'ok_{t}') else ''}><span>I approve this answer. It is true and in my words.</span></label></div>""" for t,l,_ in F["topics"])
    n=len(need_ok)+len(need_res); summary=""
    if n:
        links=[f'<li><a href="#topic_{t}">Approve: {esc(labels[t])}</a></li>' for t in need_ok]+[f'<li><a href="#res_{i["key"]}">Choose keep, edit or remove: "{esc(i["sentence"][:80])}{"…" if len(i["sentence"])>80 else ""}"</a></li>' for i in its if i["key"] in need_res]
        summary=f"""<div class=errsum role=alert tabindex=-1 id=errsum><h2>{n} answer{'s' if n!=1 else ''} still need{'' if n!=1 else 's'} a choice</h2><ul>{''.join(links)}</ul></div>"""
    pending=[i for i in its if not (fm and fm.get(f"res_{i['key']}") in ("keep","edit","remove"))]
    keepall=f"""<p><button class="btn btn-2" name=keepall value=1 formnovalidate>Keep all remaining ({len(pending)}) as true</button> <span class=hint>Only if every one of them is true.</span></p>""" if pending else ""
    return page(prog(7)+f"""{summary}<h1>Check and approve every answer</h1>{PROMISE}<p class=lead>Each answer is shown next to what you told us. Change anything that isn't right. Nothing is ready to download until you approve each answer.</p>
<form method=post action=/approve/{token}>{rows}{keepall}
<label class=cb><input type=checkbox name=save {'checked' if fm and fm.get('save') else ''}><span>Save my answers for next time (for a review or renewal). We'll give you a save code. Saved answers are kept for 90 days unless you delete them.</span></label>
<div class=warning>Giving false information on a benefit claim is an offence.</div><button class="btn btn-start">I approve. Make my documents</button></form>""","Approve your answers")
@app.get("/approve/{token}")
def approve_page(token:str):
    r,o,d=ordered(token)
    if r: return r
    try: G=ground_cached(o,d,token)
    except grounding.GroundingUnavailable as e: print("grounding unavailable",e); return BUSY(token)
    return render_approve(token,o,d,G)
@app.post("/approve/{token}")
async def approve_save(token:str, req:Request):
    r,o,d=ordered(token)
    if r: return r
    fm=dict((await req.form()).items()); F=FORMS[o["form"] or "aa"]
    try: G=ground_cached(o,d,token)
    except grounding.GroundingUnavailable as e: print("grounding unavailable",e); return BUSY(token)
    its=flag_items(o,d,G)
    if fm.get("keepall"):
        for i in its:
            if fm.get(f"res_{i['key']}") not in ("keep","edit","remove"): fm[f"res_{i['key']}"]="keep"
    need_ok=[t for t,_,_ in F["topics"] if not fm.get(f"ok_{t}")]
    need_res=[i["key"] for i in its if fm.get(f"res_{i['key']}") not in ("keep","edit","remove")]
    if need_ok or need_res: return render_approve(token,o,d,G,fm,need_ok,need_res)
    d.pop("gcache",None)
    res=d.setdefault("grounding_resolved",[]); removed=[]
    for i in its:
        ch=fm.get(f"res_{i['key']}"); res.append({"topics":i["topics"],"phrase":i["sentence"],"choice":ch,"at":time.time()})
        if ch=="remove": removed.append(i["sentence"])
    for t,_,_ in F["topics"]:
        a=str(fm.get(f"ans_{t}",d["answers"].get(t,"")))[:4000]
        for snt in removed: a=grounding.remove_sentence(a,snt)
        d["answers"][t]=a
    files=build_files(token,o,d); c=db(); code=o["save_code"]
    if fm.get("save") or (is_premium(o["tier"]) and o["keep_until"]):
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
    saved=d.get("ticks") if d.get("ticks_confirmed_at") else None; F=FORMS[form]; rows=""; last=None; it=d.get("intake_ticks") or {}; nset=0
    for i,x in enumerate(TICKS.propose(form,d.get("answers",{}))):
        if x["field"] in it and it[x["field"]] in x["options"]: x["proposed"]=it[x["field"]]; x["why"]="From what you tapped in the questions."
        cur=saved.get(x["field"],"") if saved is not None else x["proposed"]; nset+=bool(cur)
        q=x["question"].split(":")[0]
        if q!=last: rows+=f"<h2 class=tickq>{esc(q)} <span class=hint>(page {x['page']} of the form)</span></h2>"; last=q
        opts="".join(f'<label><input type=radio name="t_{esc(x["field"])}" value="{esc(s)}" {"checked" if s==cur else ""}> Tick “{esc(TICKS.label(s))}”</label>' for s in x["options"])
        opts+=f'<label><input type=radio name="t_{esc(x["field"])}" value="" {"checked" if not cur else ""}> Leave blank</label>'
        rows+=f"""<div class=trace><p><strong>{esc(x['question'].split(':',1)[1].strip())}</strong></p><p class=hint>{esc(x['why'])}</p><div class=resopts>{opts}</div></div>"""
    return page(prog(7)+f"""<h1>Check the tick boxes on your {esc(F['form'])}</h1>{PROMISE}<p class=lead>{f"We have already set {nset} tick boxes from your answers, so you don't need to answer anything again. Open the list if you want to check or change one." if it else "These are the tick boxes we will mark on the official form. We have suggested each one from the answers you approved. Change anything that isn't right. We only tick what you confirm here."}</p>
{f'<div class=warning>{esc(err)}</div>' if err else ''}<form method=post action=/ticks/{token}>{f'<details class=tickall><summary>See or change the tick boxes</summary>{rows}</details>' if it else rows}
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
    F=FORMS[o["form"] or "aa"]; lab={'assessment-briefing.html':'Assessment and phone-call briefing','supporting-letters.html':'Supporting letters for others to sign','reconsideration-letter.txt':'Your reconsideration letter, ready to sign and send','PIP-extra-sheets.pdf':'Printable extra sheets, one per question (PDF), to send with your form','answers.html':'Your approved answers, checklist and letters','AA1-filled.pdf':'Official AA1 form, filled in (PDF)','DLA1A-filled.pdf':'Official DLA1A form, filled in (PDF)','AccessToWork-answers.docx':'Your answers as a Word document (DOCX), in application order'}
    files=pack_files(o)
    dl=json.loads(o["deadline"] or "{}"); res=deadlines.compute(o["form"] or "aa",dl.get("how","phone"),dl.get("requested"),dl.get("received")) if dl.get("requested") else None
    saved=f"<div class=panel><p><strong>Your save code: <code>{o['save_code']}</code></strong><br>Keep it safe. {'Keep a copy of your answers too. They will help when your grant is due for renewal (you can apply to renew 12 weeks before it ends).' if o['form']=='atw' else "Use it at <a href=/review>/review</a> when your review form arrives, and we'll only ask what has changed."}</p></div>" if o["save_code"] else ""
    if is_premium(o["tier"]) and o["save_code"]:
        saved+=f"""<div class=panel><h2 class=h3>Included with Done for you Plus</h2><p><strong>Turned down?</strong> You usually have 1 month from the date on the decision letter to ask DWP to look again. <a href="/appeal/{o['save_code']}">Send us the decision letter</a> and we prepare your reconsideration letter and revised answers at no extra charge.</p>
<p><strong>Review form arrived?</strong> <a href="/review/{o['save_code']}">Start your renewal</a>. We fill it in from your saved answers at no extra charge.</p>{'<p>We will print and post your pack to you.</p>' if o['post_pack'] else ''}</div>"""
    return page(prog(8)+f"""<div class=done><h1>{"Your answers are ready" if o["form"]=="atw" else "Your form is done"}</h1><p>You approved every answer. Your documents are ready.</p></div>
{''.join(f'<div class=dl><span><strong>{lab.get(f,f)}</strong></span><a class=btn href="/download/{token}/{f}" download>Download</a></div>' for f in files)}
{f"<div class=tracker><p class=big>Send it back by <strong>{datetime_fmt(res['deadline'])}</strong></p></div>" if res and res.get('deadline') else ''}{saved}
{bb_addon_box(o)}{ATW_NEXT if o['form']=='atw' else ''}<h2{' hidden' if o['form']=='atw' else ''}>What to do next</h2><ol class=steps{' hidden' if o['form']=='atw' else ''}><li><strong>Read it once more</strong> before you send it.</li><li><strong>Copy the answers into your claim</strong>, or print, sign and post the filled-in form.</li><li><strong>Turned down?</strong> You can ask DWP to look again (mandatory reconsideration), usually within one month of the decision letter. <a href=/letter>Draft a letter</a>.</li></ol>
<p class=small>We delete everything 90 days after your order. <a href=/delete/{token}>Delete my information now</a>.</p>""","Your documents")
ATW_NEXT=f"""<h2>What to do next</h2><ol class=steps><li><strong>Read it once more</strong> and change anything that isn't right.</li><li><strong>Apply online or by phone</strong> at GOV.UK (search 'Access to Work apply'), or call {facts.v('atw_helpline')} (Mon–Fri 9am–5pm). Paste or read out each answer.</li><li><strong>Add your own details</strong>: workplace address, workplace contact, NI number (or UTR if self-employed).</li><li><strong>Disagree with the decision?</strong> Call the helpline and ask for it to be reconsidered.</li></ol>"""
FAMILY_ONLY="<h1>Coming soon with FormSorted Family</h1><p>This feature isn't available yet. We don't take payment for it until it's ready.</p>"
@app.get("/review")
def plus_order(code):
    """The paid 'Done for you Plus' order a save code belongs to (appeal and renewal are included for these)."""
    if not code: return None
    o=db().execute("select * from orders where save_code=? and status='paid'",(code,)).fetchone()
    return o if o and is_premium(o["tier"]) else None
def review_start(code:str=""):
    if not DEV and not plus_order(code): return page(FAMILY_ONLY,"Coming soon")
    if code: return RedirectResponse(f"/review/{urllib.parse.quote(code)}",303)
    return page(PREVIEW+"""<h1>Review mode</h1><p class=lead>Got a review or renewal form? Enter your save code. We'll show your last answers and only ask what has changed.</p>
<form method=get action=/review><div class=field><label class=q for=code>Save code</label><input id=code name=code required></div><button class=btn>Continue</button></form>""","Review mode")
@app.get("/review/{code}")
def review_page(code:str):
    if not DEV and not plus_order(code): return page(FAMILY_ONLY,"Coming soon")
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
    if not DEV and not plus_order(code): return page(FAMILY_ONLY,"Coming soon")
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
    c.execute("insert into orders(token,tier,status,created,form,consent_at,draft,personal,review_of) values(?,?,?,?,?,?,?,?,?)",(token,("199" if plus_order(code) else default_tier(target)) if target!="atw" else "49","paid",time.time(),target,time.time(),json.dumps(d),s["personal"] or "{}",code)); c.commit()
    return RedirectResponse(f"/deadline/{token}",303)
@app.get("/appeal/{code}")
def appeal_page(code:str, err:str=""):
    po=plus_order(code); s=db().execute("select * from saved where code=?",(code,)).fetchone()
    if not po or not s: raise HTTPException(404)
    F=FORMS[s["form"]]; a=json.loads(s["answers"])["answers"]
    opts="".join(f'<label class=cb><input type=checkbox name=topics value="{t}"><span>{esc(l)}</span></label>' for t,l,_ in F["topics"] if a.get(t))
    return page(f"""<h1>Turned down? We'll prepare your reconsideration</h1><p class=lead>Included with Done for you Plus. You usually have <strong>1 month from the date on your decision letter</strong> to ask DWP to look again. We prepare the letter and revised answers; you check, sign and send them.</p>
{f'<div class=warning>{esc(err)}</div>' if err else ''}<form method=post action=/appeal/{code} enctype=multipart/form-data>
<div class=field><label class=q for=dd>Date on your decision letter</label><input type=date id=dd name=decision_date required></div>
<div class=field><label class=q for=up>Photo or PDF of the decision letter</label><input id=up type=file name=files multiple accept="image/*,application/pdf"></div>
<fieldset class=iq><legend>Which parts do you disagree with? <span class=hint>(tap any)</span></legend>{opts}</fieldset>
<button class="btn btn-start">Prepare my reconsideration</button></form><p class=small>We can't guarantee a different decision.</p>""","Reconsideration")
@app.post("/appeal/{code}")
async def appeal_start(code:str, req:Request):
    po=plus_order(code); s=db().execute("select * from saved where code=?",(code,)).fetchone()
    if not po or not s: raise HTTPException(404)
    fm=await req.form(); dd=str(fm.get("decision_date") or "")[:10]
    from datetime import date as _d
    try: _d.fromisoformat(dd)
    except ValueError: return RedirectResponse(f"/appeal/{code}?err="+urllib.parse.quote("Please enter the date on your decision letter."),303)
    F=FORMS[s["form"]]; valid={t for t,_,_ in F["topics"]}; topics=[t for t in fm.getlist("topics") if t in valid]
    prev=json.loads(s["answers"]); token=orders.new_token(); ups=[]
    for f in fm.getlist("files"):
        if not getattr(f,"filename",None): continue
        data=await f.read(); ext=UP_TYPES.get(f.content_type or "")
        if not ext or len(data)>UP_MAX or len(ups)>=10: continue
        nm=f"upload-{len(ups)+1}-"+_re.sub(r"[^A-Za-z0-9._-]","_",f.filename)[:60]; od=os.path.join(OUT,token,"up"); os.makedirs(od,exist_ok=True)
        open(os.path.join(od,nm),"wb").write(data); store.put_dir(token,od,[nm]); ups.append({"name":f.filename[:80],"key":nm,"type":ext})
    d={"answers":dict(prev["answers"]),"said":prev.get("said",{}),"checklist":["A copy of the decision letter","Any new letters or reports since you applied"],
       "notes_for_user":["Reconsideration: these are your approved answers from before. Change any that DWP got wrong, adding what really happens (how often, how long, what help)."],"extra":{},"conditions":[],"tick_yes":[]}
    c=db(); c.execute("insert into orders(token,tier,status,created,form,consent_at,draft,personal,review_of,appeal,keep_until,paid_at) values(?,?,?,?,?,?,?,?,?,?,?,?)",
        (token,"199","paid",time.time(),s["form"],time.time(),json.dumps(d),s["personal"] or "{}",code,json.dumps({"decision_date":dd,"topics":topics,"uploads":ups}),po["keep_until"],time.time())); c.commit()
    return RedirectResponse(f"/approve/{token}",303)
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
<button class=btn>Draft my letter</button></form>""","Reconsideration letter")
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
<p class=small>We only used what you typed.</p>""","Your draft letter")

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

# ---------------- Blue Badge answers (add-on £15 after an AA / DLA / PIP order, or £29 on its own) ----------------
BB_ADDON_LINE="<p class=hint>Applying for a Blue Badge too? After you pay, you can add Blue Badge application answers for £15, made from the answers you give here.</p>"
BB_TRUST="<div class=trust><h2 class=h3>Our promise</h2><ul class=ticks><li><strong>Fixed price.</strong> You pay this once. No subscription, nothing more to pay us.</li><li><strong>Only your words.</strong> Every answer is built from what you told us. You check and change anything before you use it.</li><li><strong>You stay in control.</strong> You apply yourself, and we never contact your council for you.</li><li><strong>Yours to keep.</strong> Download your answers and checklist to use now, or later if you need to ask the council to look again.</li></ul></div>"
BB_ITEMS=["Answers for each health and walking question on the online Blue Badge application, ready to copy and paste","A hidden-disability write-up in your own words, if journeys are hard for reasons other than walking","A checklist of what to upload, and the photo and proof you need","If the council says no: a letter asking them to look at the decision again","You check every word. You apply yourself"]
def bb_summary(pv=""):
    n,p,_=FORMS["bb"]["tiers"][BB.SOLO_TIER]
    return page(bbprog(1)+pv+f"""<div class=summary><p class=caption>Your order</p><h1>{esc(n)}</h1><p class=sub>For the Blue Badge application</p>
<p class=lede><strong>Tap your answers. We write them up. You paste them into your application.</strong></p><div class=promise><strong>About 3 minutes. You only tap, we do the writing.</strong></div>
<h2 class=h3>What's included</h2><ul class=ticks>{''.join(f'<li>{esc(i)}</li>' for i in BB_ITEMS)}</ul>
<div class=total><span>Total</span><strong>£{p//100}</strong></div><p class=hint>Nothing to pay now. Answer the questions first; you pay once at the end. One-off fee.</p>
<form method=post action=/checkout><input type=hidden name=form value=bb><input type=hidden name=tier value={BB.SOLO_TIER}><button class="btn btn-wide">Start my answers</button></form>
<p class=hint>{esc(BB.NOT_ELIG)}</p><p class=hint>Already ordered an Attendance Allowance, DLA or PIP form with us? Add Blue Badge answers for £15 from your documents page instead.</p></div>""","Blue Badge answers",minimal=True)
def bb_data(o): return json.loads(o["intake"] or "{}") or {"who":"me","else":{}}
def bb_parent(o):
    p=get(o["review_of"]) if o["review_of"] else None
    return p if p and p["status"]=="paid" else None
@app.get("/bb/{token}")
def bb_form(token:str):
    o=ready(token,paid=False)
    if o["form"]!="bb": raise HTTPException(404)
    if o["status"]=="paid": return RedirectResponse(f"/bb/{token}/documents",303)
    d=bb_data(o); d.setdefault("else",{})
    return page(bbprog(3)+f"""<h1>Your Blue Badge answers</h1><p class=lead>Tap what applies. It takes about 3 minutes.</p>
<form method=post action=/bb/{token} class=intake>{BB.body(d)}<button class="btn btn-wide">Continue</button></form><p class=hint>{esc(BB.NOT_ELIG)}</p>""","Blue Badge answers",minimal=True)
@app.post("/bb/{token}")
async def bb_save(token:str, req:Request):
    o=ready(token,paid=False)
    if o["form"]!="bb": raise HTTPException(404)
    if o["status"]=="paid": return RedirectResponse(f"/bb/{token}/documents",303)
    fm=await req.form(); d=BB.save(bb_data(o),fm)
    c=db(); c.execute("update orders set intake=?, interview_done_at=? where token=?",(json.dumps(d),time.time() if BB.ready(d) else None,token)); c.commit()
    if not BB.ready(d): return page(f"<h1>Just one more thing</h1><p class=lead>Please tell us how far you can walk, or what makes journeys hard, so we have something to write up.</p><p><a class=btn href=/bb/{token}>Go back</a></p>","One more thing",minimal=True)
    return RedirectResponse(f"/preview/{token}",303)
def bb_preview(o):
    token=o["token"]; n,p,_=tier_info("bb",o["tier"]); d=bb_data(o); k=len(BB.answers(d))
    return page(bbprog(4)+f"""<div class=summary><p class=caption>Your answers are saved</p><h1>Your Blue Badge answers are ready to prepare</h1>
<ul class=ticks><li>{k} answers to write up for the online application</li>{''.join(f'<li>{esc(i)}</li>' for i in BB_ITEMS[1:4])}</ul>
<div class=total><span>{esc(n)}</span><strong>£{p//100}</strong></div>
<form method=post action=/pay/{token}><label class=cb><input type=checkbox name=waive required><span>Please prepare my answers straight away. I understand that once you start I lose my 14-day right to cancel.</span></label>
<button class="btn btn-wide">Pay £{p//100} to get your answers</button></form>{BB_TRUST}<p class=change><a href="/bb/{token}">Change my answers</a></p>
<p class=hint>{esc(BB.NOT_ELIG)}</p><p class=hint>If you don't pay, we delete everything you told us after 7 days.</p></div>""","Your Blue Badge answers",minimal=True)
@app.get("/bb/{token}/documents")
def bb_documents(token:str):
    o=ready(token)
    if o["form"]!="bb": raise HTTPException(404)
    files=[("blue-badge-answers.html","Your Blue Badge answers, hidden-disability write-up and checklist")]
    return page(bbprog(5)+f"""<div class=done><h1>Your Blue Badge answers are ready</h1><p>Copy each answer into the matching part of the online application, or your council's paper form. Change anything that isn't right.</p></div>
{''.join(f'<div class=dl><span><strong>{esc(l)}</strong></span><a class=btn href="/bb/{token}/file/{f}" download>Download</a></div>' for f,l in files)}
<div class=panel><h2 class=h3>Turned down?</h2><p>Tell us the date on the council's letter and what it said. We'll prepare a letter asking them to look again. You send it.</p>
<form method=post action=/bb/{token}/letter><label>Date on the letter<input type=date name=decision_date required></label><label>What the letter said (optional)<textarea name=reason maxlength=600 rows=3></textarea></label><button class="btn btn-2">Make my letter</button></form></div>
<p class=hint>{esc(BB.NOT_ELIG)}</p><p class=small>We delete everything 90 days after your order. <a href=/delete/{token}>Delete my information now</a>.</p>""","Your Blue Badge answers")
@app.get("/bb/{token}/file/{name}")
def bb_file(token:str,name:str):
    o=ready(token)
    if o["form"]!="bb" or name!="blue-badge-answers.html": raise HTTPException(404)
    return HTMLResponse(BB.answers_html(bb_data(o)),headers={"Content-Disposition":'attachment; filename="blue-badge-answers.html"'})
@app.post("/bb/{token}/letter")
def bb_letter(token:str, decision_date:str=Form(...), reason:str=Form("")):
    o=ready(token)
    if o["form"]!="bb": raise HTTPException(404)
    return PlainTextResponse(BB.letter(bb_data(o),decision_date,reason),headers={"Content-Disposition":'attachment; filename="blue-badge-reconsideration-letter.txt"'})
@app.post("/bb/addon/{parent}")
def bb_addon(parent:str):
    """Add-on from a paid AA / DLA / PIP order: prefilled from that order's taps (no re-asking), £15, paid separately at the end."""
    p=ready(parent)
    if (p["form"] or "aa") not in BB.PARENT_FORMS: raise HTTPException(404)
    c=db(); ex=c.execute("select token from orders where form='bb' and review_of=? and status in ('free','paid')",(parent,)).fetchone()
    if ex: return RedirectResponse(f"/start/{ex[0]}",303)
    token=orders.new_token(); d=BB.prefill(p["form"] or "aa",json.loads(p["intake"] or "{}"))
    c.execute("insert into orders(token,tier,status,created,form,ip,review_of,consent_at,intake,email) values(?,?,?,?,?,?,?,?,?,?)",(token,BB.ADDON_TIER,"free",time.time(),"bb",p["ip"],parent,time.time(),json.dumps(d),p["email"])); c.commit()
    return RedirectResponse(f"/bb/{token}",303)
def bb_addon_box(o):
    if (o["form"] or "aa") not in BB.PARENT_FORMS: return ""
    return f"""<div class=panel><h2 class=h3>Applying for a Blue Badge too?</h2><p>We can turn the answers you've already given us into answers for the online Blue Badge application, with a checklist of what to upload. £15, and you only pay once you've checked your answers.</p>
<form method=post action=/bb/addon/{o['token']}><button class="btn btn-2">Add Blue Badge answers, £15</button></form><p class=hint>{esc(BB.NOT_ELIG)}</p></div>"""

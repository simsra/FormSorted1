import hashlib
"""FormSorted claim service prototype (AA1, DLA1A, PIP2, AR1). Run: uvicorn app:app --port 8000
Env: STRIPE_SECRET_KEY, PUBLIC_URL, ANTHROPIC_API_KEY/GEMINI_API_KEY/OPENAI_API_KEY, LLM_PROVIDER/LLM_MODEL/LLM_FALLBACKS, GROUNDING_PROVIDER/GROUNDING_MODEL/GROUNDING_FALLBACKS (see SETUP_RENDER_SUPABASE.md), BRAND. Placeholders => DEV mode (no payment, mock LLM)."""
import threading, os, json, sqlite3, secrets, urllib.request, urllib.parse, base64, time
from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse, JSONResponse
import orders, mailer, asyncio, hmac, store
from fastapi.responses import Response, PlainTextResponse
import intake as INTAKE
from starlette.concurrency import run_in_threadpool
import llm, fill_pdf, documents, quality, deadlines, letters, grounding, facts, ticks as TICKS, contsheet, formwatch
from html import escape as esc
from forms import FORMS, is_full, tier_info, default_tier, is_premium
import plus as PLUS
import premium as PREMIUM
import psp as PSP
import bluebadge as BB, printmail
import evidence as EVID, honesty as HONEST, fraud as FRAUD
import wholeform as WF, secure as SECURE
import accounts as ACCT
BRAND=os.getenv("BRAND","FormSorted"); STRIPE=os.getenv("STRIPE_SECRET_KEY","STRIPE_SECRET_KEY_PLACEHOLDER")
PUBLIC=os.getenv("PUBLIC_URL","http://localhost:8000"); DEV=STRIPE.endswith("PLACEHOLDER")
HERE=os.path.dirname(os.path.abspath(__file__)); OUT=store.OUT; DB=store.SQLITE_PATH
import hashlib as _hl; CSS_V=_hl.sha256(open(os.path.join(HERE,"static","app.css"),"rb").read()).hexdigest()[:10]   # cache-bust: browsers keep old app.css otherwise (30 Oct 2026)
os.makedirs(OUT,exist_ok=True)
CRON_SECRET=os.getenv("CRON_SECRET","")
def db(): return store.connect()
def is_wf(o):
    """Whole-form order: every box filled from the questions asked before payment (wholeform.py)."""
    try: return (o["form"] or "aa") in ("aa","dla") and bool(json.loads(o["intake"] or "{}").get("wf_v"))
    except (ValueError, TypeError, KeyError, IndexError): return False   # Postgres if DATABASE_URL is set, else SQLite (see store.py)
def get(token):
    r=db().execute("select * from orders where token=?",(token,)).fetchone()
    if not r: raise HTTPException(404)
    return r
STEPS=["Choose your form","Choose your package","Answer the questions","Pay","Get your form"]   # Oct 2026 simple journey: form -> package -> questions -> pay -> get your form
STEPS_SHORT=["Form","Package","Questions","Pay","Get form"]
def bbprog(n):
    """Blue Badge uses the same 5 steps. Old BB step numbers: 1 summary, 2 agree, 3 answers, 4 check and pay, 5 answers ready."""
    return prog({1:2,2:3,3:3,4:4,5:5}.get(n,n),{2:"Before you start"}.get(n))
def prog(n,label=None,sub=""):
    """5-step bar shown on every screen: 1 Choose your form, 2 Choose your package, 3 Answer the questions, 4 Pay, 5 Get your form.
    label: what this screen is, within the step."""
    lis="".join(f'<li class="{"past" if j<n else "now" if j==n else ""}"{" aria-current=step" if j==n else ""}><span class=n>{j}</span><span class=s>{esc(STEPS_SHORT[j-1])}</span><span class=l>{esc(t)}</span></li>' for j,t in enumerate(STEPS,1))
    lab=STEPS[n-1]+(f": {label}" if label and label!=STEPS[n-1] else "")
    return f"""<nav aria-label="Your progress"><ol class=stepper>{lis}</ol></nav><p class=stepnow>Step {n} of {len(STEPS)}: <strong>{esc(lab)}</strong>{f" · {sub}" if sub else ""}</p>"""
HELP_FAQ=[("When do I pay?","Only at the end, after the questions. You see the price before you start, and you can change package before you pay."),
 ("Can I stop and come back?","Yes. Tap \u201cSave and finish later\u201d to get your private link. If you don't pay, we delete your answers after 7 days."),
 ("I'm filling this in for someone else","That's fine. Answer about them. They sign the form, or you sign it if you have the right to act for them."),
 ("I'm not sure what to answer","Pick the answer closest to a normal day. Skip anything you're not sure about. You check every answer before anything is final."),
 ("Is this part of the government?","No. FormSorted is an independent online form-filling service. It isn't part of DWP, GOV.UK or your council."),
 ("Who sends the form?","You do. You check it, sign it and send it yourself.")]
def need_help():
    """Small help area at the bottom of every screen: common questions behind a toggle, plus the email address. No promise that a person checks anything."""
    qa="".join(f"<details class=qa><summary>{esc(q)}</summary><p>{esc(a)}</p></details>" for q,a in HELP_FAQ)
    return f"""<section class=needhelp aria-labelledby=nh><h2 id=nh>Need help?</h2><details class=more><summary>Questions people ask</summary>{qa}</details><p>Or email <a href="mailto:hello@formsorted.com">hello@formsorted.com</a></p></section>"""
def page(body,title="FormSorted",gov="https://www.gov.uk/browse/benefits/disability",minimal=False):
    if minimal:  # order summary: no outbound links except Terms/Privacy
        indep='<div class="indep"><div class="wrap"><span class="tag">Independent</span>Not affiliated with DWP or GOV.UK.</div></div>'
        ftr='<footer class="ftr"><div class="wrap"><p><strong>FormSorted</strong> is an independent online form-filling service. Not affiliated with DWP, GOV.UK or any government body. We can\'t guarantee an award or outcome.</p><p><a href="https://formsorted.com/privacy.html">Privacy</a><a href="https://formsorted.com/terms.html">Terms</a></p></div></footer>'
    else:
        indep=f'<div class="indep"><div class="wrap"><span class="tag">Independent</span>Not affiliated with DWP or GOV.UK.</div></div>'
        ftr='<footer class="ftr"><div class="wrap"><p><strong>FormSorted</strong> is an independent online form-filling service. Not affiliated with DWP, GOV.UK or any government body. We can\'t guarantee an award or outcome.</p><p><a href="https://formsorted.com/privacy.html">Privacy</a><a href="https://formsorted.com/terms.html">Terms</a><a data-contact href="mailto:hello@formsorted.com">Contact</a></p></div></footer>'
    return HTMLResponse(f"""<!doctype html><html lang=en-GB><head><meta charset=utf-8><meta name=viewport content='width=device-width,initial-scale=1'><link rel=icon href=/static/favicon.svg><link rel=stylesheet href=/static/app.css?v={CSS_V}><title>{title} | {BRAND}</title><meta name=robots content=noindex></head><body><a href="#main" class="skip">Skip to main content</a>
<header class="hdr"><div class="wrap"><a class="logo" href="/"><img src="/static/logo.svg" alt="FormSorted home" width="170" height="36"></a></div></header>
{indep}<main id=main><div class=wrap>{body}{need_help()}</div></main>{ftr}</body></html>""")
def stripe(method,path,data=None):
    req=urllib.request.Request("https://api.stripe.com/v1"+path,urllib.parse.urlencode(data).encode() if data else None,method=method,
        headers={"Authorization":"Basic "+base64.b64encode((STRIPE+":").encode()).decode()})
    return json.load(urllib.request.urlopen(req,timeout=30))
app=FastAPI()
@app.middleware("http")
async def _timing(request:Request, call_next):
    t=time.time(); r=await call_next(request); dt=time.time()-t
    if dt>0.5: print(f"timing slow {request.method} /{request.url.path.split('/')[1]} {dt:.2f}s",flush=True)
    return r
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
FORM_CARDS=[("aa","Attendance Allowance","For people over State Pension age who need help with care, day or night."),
 ("pip","PIP","For people aged 16 to State Pension age with a health condition or disability."),
 ("pipr","PIP review","Already get PIP and DWP has sent a review form (AR1)."),
 ("dla","DLA for a child","For a child under 16 who needs more care or watching than other children their age."),
 ("bb","Blue Badge","For a parking badge if walking or getting around is hard."),
 ("atw","Access to Work","For help at work, for people in or starting a job.")]
NOT_SURE=[("Is it for a child under 16?","DLA for a child","dla"),("Are they State Pension age or over, and need help with care?","Attendance Allowance","aa"),
 ("Aged 16 to State Pension age, with a health condition or disability?","PIP","pip"),("Already get PIP, and got a review form?","PIP review","pipr"),
 ("Need a parking badge?","Blue Badge (you can also get one of the forms above)","bb")]
def form_cards():
    main="".join(f"""<a class=fcard href="/?form={k}"><span class=fn>{esc(t)}</span><span class=fw>{esc(w)}</span><span class=fp>Choose</span></a>""" for k,t,w in FORM_CARDS if k!="atw")
    k,t,w=FORM_CARDS[-1]
    return f"""<div class=fcards>{main}</div><p class=alsoform>Also: <a href="/?form={k}">{esc(t)}</a>. {esc(w)}</p>"""
def not_sure():
    li="".join(f"<li><strong>{esc(q)}</strong> Choose <a href=\"/?form={k}\">{esc(a)}</a>.</li>" for q,a,k in NOT_SURE)
    return more("Not sure which form?",f"<p>Answer yes to one of these:</p><ul class=notsure>{li}</ul><p>Still not sure? Look at the letter or form DWP sent you. The form's name is on the first page.</p>")
@app.get("/")
def home(form:str="", tier:str=""):
    pv=PREVIEW if DEV else ""
    if form not in FORMS:
        return page(prog(1)+pv+f"""<h1>Get your benefit form filled in</h1><p class=one>Answer simple questions. We fill in the form. You check it, sign it and send it.</p>
<h2 class=h3 id=pick>Which form do you need?</h2>{form_cards()}{not_sure()}
<p class=hint>England and Wales only. You only pay at the end, after the questions.</p>""","Choose your form",minimal=True)
    if form=="bb": return bb_summary(pv)
    return order_summary(form,tier if tier in FORMS[form]["tiers"] else "",pv)
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
def more(title,body,open_=False):
    """Extra information, closed by default: one small '+ More info' line instead of a block of text."""
    return f"<details class=more{' open' if open_ else ''}><summary>{title}</summary>{body}</details>"
def ui_notes(form):
    """Plus notes for the customer pages. Posting is hidden in the clean-steps UI (decision pending, Oct 2026)."""
    return [x for x in PLUS.notes(form) if x!=getattr(PLUS,"POST_SOON",None)]
def how_it_works(form,price):
    pay=f"Choose your pack and pay £{price}" if (form in PLUS.PLUS_FORMS) else f"Pay £{price}"
    return f"""<ol class=howit><li><strong>Answer simple questions.</strong> {"Mostly taps, about 10 minutes." if form in INTAKE.FORMS_V3 else "In plain English, at your own pace."}</li><li><strong>{pay}.</strong> Only at the end, if you want your form.</li>
<li><strong>Check every answer</strong> and change anything that isn't right.</li><li><strong>Download your form</strong>, then print, sign and post it.</li></ol>"""
def no_printer():
    """Posting is Plus-only (Simon, 30 Oct 2026). Says 'coming soon' until print-and-post is really live."""
    return "No printer? We'll post you a printed copy"+("" if PLUS.posting() else " (coming soon)")
NEED_POST="<p class=hint>Need it posted? Choose Plus.</p>"
def pkg_bullets(form,t):
    """3-4 short bullets per package for the package cards."""
    ts=FORMS[form]["tiers"]
    if form in PLUS.PLUS_FORMS:
        if t=="99": return [l for l,d,b,p_ in PLUS.compare_rows(form) if b==1][:3]+["You check every answer before it's final"]
        return ["Everything in "+ts["99"][0]]+[l for l,d in PLUS.items(form) if l not in PLUS.POST_ON.values()][:2]+[no_printer()]
    items=pack_items(form,t); names=list(ts); k=names.index(t)
    return items[:1] if k==0 else ["Everything in "+ts[names[k-1]][0]]+items[k:]
def order_summary(form,tier="",pv=""):
    """Step 2, choose your package: one big card per package, each with its own Choose button (POST /checkout). Nothing to pay yet.
    tier: the package they picked on the website, marked 'Your choice'."""
    f=FORMS[form]; ts=list(f["tiers"].items())
    cards=""
    for t,(n,p,_) in ts:
        mine=(t==tier)
        cards+=f"""<div class="pkg{' mine' if mine else ''}">{'<p class=pill>Your choice</p>' if mine else ''}<h2>{esc(n)}</h2><p class=pr>£{p//100} <small>one-off</small></p><ul class=ticks>{''.join(f'<li>{esc(x)}</li>' for x in pkg_bullets(form,t))}</ul>{NEED_POST if t=="99" and form in PLUS.PLUS_FORMS else ""}
<form method=post action=/checkout><input type=hidden name=form value={form}><input type=hidden name=tier value={t}><button class="btn btn-big">{'Continue with' if mine else 'Choose'} {esc(n)}</button></form></div>"""
    up=upgrade_box(form,tier or default_tier(form))
    return page(prog(2)+pv+f"""<p class=caption>{esc(f['short'])}</p><h1>Choose your package</h1><p class=one>Nothing to pay now. You pay once, at the end, after the questions. You can change package before you pay.</p>
<div class=pkgs>{cards}</div>
{more("Compare the packages in detail",up) if up else ""}{more("Applying for a Blue Badge too?",BB_ADDON_LINE) if form in BB.PARENT_FORMS else ""}
<p class=hint>{esc(DWP_LINE)} No success fee.</p><p class=change><a href="/">Choose a different form</a></p>""",f"Choose your package: {f['name']}",minimal=True)
def can_change_pack(o): return o["status"]!="paid" and (o["form"] or "aa") in PLUS.PLUS_FORMS and o["tier"] in ("99","199")
@app.get("/package/{token}")
def change_package(token:str):
    """Step 2 again from the pay screen (Simon, 30 Oct 2026: choose the package once; pay only shows a summary). Answers are kept."""
    o=ready(token,paid=False)
    if not can_change_pack(o): return RedirectResponse(f"/preview/{token}",303)
    form=o["form"] or "aa"; f=FORMS[form]; cards=""
    for t in ("99","199"):
        n,p,_=f["tiers"][t]; mine=(t==o["tier"])
        cards+=f"""<div class="pkg{' mine' if mine else ''}">{'<p class=pill>Your choice</p>' if mine else ''}<h2>{esc(n)}</h2><p class=pr>£{p//100} <small>one-off</small></p><ul class=ticks>{''.join(f'<li>{esc(x)}</li>' for x in pkg_bullets(form,t))}</ul>{NEED_POST if t=="99" else ""}
<form method=post action=/package/{token}><input type=hidden name=tier value={t}><button class="btn btn-big">{'Keep' if mine else 'Choose'} {esc(n)}</button></form></div>"""
    up=upgrade_box(form,o["tier"])
    return page(prog(2,"Change package")+f"""<p class=caption>{esc(f['short'])}</p><h1>Change your package</h1><p class=one>Your answers are kept. Choose a package, then you go back to pay.</p>
<div class=pkgs>{cards}</div>{more("Compare the packages in detail",up) if up else ""}
<p class=change><a href="/preview/{token}">Back to pay</a></p>""",f"Change package: {f['name']}",minimal=True)
@app.post("/package/{token}")
def set_package(token:str, tier:str=Form("")):
    o=ready(token,paid=False)
    if can_change_pack(o) and tier in ("99","199") and tier!=o["tier"]:
        c0=db(); c0.execute("update orders set tier=?, keep_until=null where token=? and status!='paid'",(tier,token)); c0.commit()
    return RedirectResponse(f"/preview/{token}",303)
def upgrade_box(form,tier):
    """Clear side-by-side comparison of the two packs, with a button to switch."""
    ts=FORMS[form]["tiers"]
    if len(ts)<2 or form=="atw": return ""
    base,plus=list(ts)[0],[t for t in ts if is_premium(t)]
    if not plus: return ""
    plus=plus[0]; (bn,bp,_),(pn,pp,_)=ts[base],ts[plus]
    tr=compare_table_rows(form)
    other=plus if tier==base else base; on,op,_=ts[other]
    return f"""<div class=compare><table><thead><tr><th></th><th>{esc(bn)}<br>£{bp//100}</th><th>{esc(pn)}<br>£{pp//100}</th></tr></thead><tbody>{tr}</tbody></table>{plus_notes(form)}</div>"""
def compare_table_rows(form):
    """£99 vs Plus rows from plus.py. No 'bought separately' or saving line (Simon, 28 Oct 2026: none until SSCS1 and posting are live)."""
    cell=lambda v: "✓" if v==1 else ("–" if not v else esc(v))
    return "".join(f"<tr><td>{esc(l)}{f'<small>{esc(d)}</small>' if d else ''}</td><td>{cell(b)}</td><td>{cell(p)}</td></tr>" for l,d,b,p in PLUS.compare_rows(form) if l not in PLUS.POST_ON.values())
def plus_notes(form): return "".join(f"<p class=hint>{esc(x)}</p>" for x in ui_notes(form)+[PLUS.FOOT])
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
    if is_wf(o) and not json.loads(o["intake"]).get("uploads_done"): return RedirectResponse(f"/uploads/{token}",303)
    f=FORMS[o["form"] or "aa"]; n,p,_=tier_info(o["form"] or "aa",o["tier"]); got,total=INTAKE.coverage(o["form"],json.loads(o["intake"])) if o["intake"] else covered(o)
    choose=(o["form"] or "aa") in PLUS.PLUS_FORMS and o["tier"] in ("99","199")
    facts=[f"Your details cover {got} of {total} sections of the form" if o["intake"] else f"{got} of {total} topics covered in your conversation",f"Prepared for the {esc(f['short'])}"]+[esc(i) for i in pack_items(o["form"] or "aa","99" if choose else o["tier"])]
    extra=more("What happens after you pay",f"""<ol class=howit><li>We write every section from what you told us and check each one against your answers.</li><li>You check every answer and change anything that isn't right.</li><li>You download your form, then sign it and send it yourself.</li></ol>
<figure class=lockprev><img src="/static/preview-placeholder.svg" alt="Example illustration of a filled-in form (not your answers)" width=520 height=360><figcaption>Illustration only. Your own answers appear after payment.</figcaption></figure>{TRUST}
<p class=hint>One-off fee. No success fee. If you don't pay, we delete everything you told us after 7 days.</p>""")
    form=o["form"] or "aa"; bl=[x for x in pkg_bullets(form,o["tier"]) if not x.startswith("Everything in")][:3] if o["tier"] in FORMS[form]["tiers"] else []
    chg=f' <a class=chpk href="/package/{token}">Change package</a>' if choose else ""
    rows=f"""<dl class=order><div><dt>Form</dt><dd>{esc(f['short'])}</dd></div><div><dt>Your answers</dt><dd>{got} of {total} {'sections of the form' if o['intake'] else 'topics'}{f' · <a href="/intake/{token}?s=about">Change</a>' if o['intake'] else ''}</dd></div><div class=pkrow><dt>Your package</dt><dd><strong>{esc(n)}</strong> · £{p//100}{chg}{'<ul class=ticks>'+''.join(f'<li>{esc(x)}</li>' for x in bl)+'</ul>' if bl else ''}</dd></div></dl>"""
    head="<h1>Check your order and pay</h1><p class=one>Nothing is filled in until you pay. Then you check every answer.</p>"
    return page(prog(4)+f"""<div class=summary>{head}{rows}
<form method=post action=/pay/{token}>{KEEP_OPT if is_premium(o["tier"]) else ""}<div class=total><span>Total to pay</span><strong id=paytotal>£{p//100}</strong></div><div class=paybox><label class=cb><input type=checkbox name=waive required><span>Please start preparing my form straight away. I understand that once you start I lose my 14-day right to cancel.</span></label>
<button class="btn btn-big" id=paybtn>Pay £{p//100} and get my form</button><p class=hint>Have a discount code? You can enter it on the next screen, when you add your card.</p></div></form>
{extra}<p class=hint>{esc(DWP_LINE)}</p></div>""","Check your order and pay",minimal=True)
KEEP_OPT="<label class=cb><input type=checkbox name=keep value=1><span>Keep my answers for 3 years, so you can help with a reconsideration or my renewal without asking again. I can delete them at any time. (Optional. Without this we delete them after 90 days.)</span></label>"
THREE_YEARS=3*365*86400
@app.post("/pay/{token}")
def pay(token:str, waive:str=Form(...), keep:str=Form(""), pack:str=Form("")):
    o=ready(token,paid=False)
    if pack in ("99","199") and o["status"]!="paid" and (o["form"] or "aa") in PLUS.PLUS_FORMS and o["tier"] in ("99","199") and pack!=o["tier"]:
        c0=db(); c0.execute("update orders set tier=?, keep_until=null where token=?",(pack,token)); c0.commit(); o=get(token)   # chosen on the finish screen
    if keep and is_premium(o["tier"]) and o["status"]!="paid": c0=db(); c0.execute("update orders set keep_until=? where token=?",(time.time()+THREE_YEARS,token)); c0.commit()
    if o["status"]=="paid": return RedirectResponse(f"/start/{token}",303)
    if not o["interview_done_at"]: return RedirectResponse(chat_url(o),303)
    c=db()
    if DEV or tier_info(o["form"] or "aa",o["tier"])[1]==0:   # £0: only for items included with Plus (tiers created server-side, never at checkout)
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
        save_pay_ids(c,session_id,s)
        return RedirectResponse(f"/start/{s.get('client_reference_id') or row['token']}",303)
    if row and row["status"]=="paid": return RedirectResponse(f"/start/{row['token']}",303)   # webhook already confirmed it
    if not s and session_id: return page("<h1>We're confirming your payment</h1><p>This can take a minute. <a href='/success?session_id="+urllib.parse.quote(session_id)+"'>Refresh this page</a>. If you were charged, email <a href=mailto:hello@formsorted.com>hello@formsorted.com</a>.</p>","Confirming payment")
    back=f"/preview/{row['token']}" if row else "/"
    return page(f"<h1>Payment not completed</h1><p>You have not been charged. <a href={back}>Go back and try again</a>.</p>","Payment not completed")
def save_pay_ids(c,session_id,s):
    """Payment customer + card fingerprint, kept only to spot many claims from one payer (see fraud.py). Never fatal."""
    try:
        cust=s.get("customer") if isinstance(s.get("customer"),str) else (s.get("customer") or {}).get("id")
        fp=None; pi=s.get("payment_intent")
        if pi and not DEV:
            p=stripe("GET","/payment_intents/"+urllib.parse.quote(pi if isinstance(pi,str) else pi["id"])+"?expand[]=latest_charge")
            fp=(((p.get("latest_charge") or {}).get("payment_method_details") or {}).get("card") or {}).get("fingerprint")
        if cust or fp: c.execute("update orders set stripe_customer=coalesce(?,stripe_customer), card_fp=coalesce(?,card_fp) where stripe_session=?",(cust,fp,session_id)); c.commit()
    except Exception as e: print("payment ids not saved",str(e)[:200])
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
    await run_in_threadpool(save_pay_ids,c,s["id"],s)
    if email:
        subj,txt=orders.link_email(BRAND,FORMS[form]["short"],f"{PUBLIC}/start/{token}")
        try: await run_in_threadpool(mailer.send,email,subj,txt)   # 28 Oct: blocked the whole site for the email call, then 500'd on a mail error
        except Exception as e: print("link email failed",str(e)[:200])
    return {"ok":True}
REFUNDED_PAGE="<h1>Your order has been cancelled</h1><p class=lead>We've cancelled this order and refunded your payment in full. Refunds usually reach your account in 5 to 10 working days. We have deleted your answers.</p>"
DELETED_PAGE="<h1>Your information has been deleted</h1><p>Everything you told us for this order has been deleted. This link no longer works.</p>"
@app.get("/start/{token}")
def start(token:str):
    o=get(token)
    if o["status"]=="deleted": return page(DELETED_PAGE,"Deleted")
    if o["status"]=="refunded": return page(REFUNDED_PAGE,"Order cancelled",minimal=True)
    if o["status"] not in ("paid","free"): raise HTTPException(402)
    if o["consent_at"] and o["form"]=="bb":
        return RedirectResponse(f"/bb/{token}/documents" if o["status"]=="paid" else f"/preview/{token}" if o["interview_done_at"] else f"/bb/{token}",303)
    if o["consent_at"]:
        if o["status"]=="paid" and o["interview_done_at"] and not o["draft"]:
            if o["intake"] and not json.loads(o["intake"]).get("uploads_done"): return RedirectResponse(f"/uploads/{token}",303)
            return RedirectResponse(f"/prepare/{token}",303)
        if o["status"]=="free" and o["interview_done_at"]: return RedirectResponse(f"/preview/{token}",303)
        if o["draft"] and (o["form"] or "aa") in INTAKE.FORMS_V3: return RedirectResponse(f"/{'documents' if o['approved_at'] and o['details_at'] else 'details' if o['approved_at'] else 'approve' if is_wf(o) else 'deadline'}/{token}",303)
        return RedirectResponse(chat_url(o),303)
    lead="Payment received. Please confirm 2 things." if o["status"]=="paid" else "Please confirm 2 things. You only pay at the end, if you want your completed form."
    return page((bbprog(2) if o["form"]=="bb" else prog(3,"Before you start"))+f"""<h1>Before you start</h1><p class=one>{lead}</p><form method=post action=/consent/{token}>
<label class=cb><input type=checkbox name=health required><span>I agree to {BRAND} using the health information I give to prepare this form. If it's about someone else, they agree, or I can act for them.</span></label>
<label class=cb><input type=checkbox name=truth required><span>I'll only give true information and will check everything before sending it.</span></label>
<div class=warning>{"Giving false information on a Blue Badge application is an offence." if o["form"]=="bb" else "Giving false information on a benefit claim is an offence."}</div>
<button class="btn btn-big">Start the questions</button></form>{more("How we look after your information","<p>If you don't pay, we delete your information after 7 days. If you do, after 90 days, or sooner if you ask. <a href='https://formsorted.com/privacy.html'>Privacy notice</a></p>")}""","Before we start")
@app.post("/consent/{token}")
def consent(token:str, health:str=Form(...), truth:str=Form(...), digital:str=Form("")):
    o=get(token)
    if o["status"] not in ("paid","free"): raise HTTPException(403)
    c=db(); c.execute("update orders set consent_at=? where token=?",(time.time(),token)); c.commit()
    return RedirectResponse(chat_url(o),303)
# ---------- Preparing the form (after payment) ----------
# 28 Oct: /prepare used to draft inside the page request (~30s of blank screen) and /approve ran the answer check
# one call after another (~15s+). Now drafting starts in the background the moment the customer finishes,
# the waiting page shows real steps, and the answer check is done ahead of time so approve opens straight away.
import threading
JOBS={}; _JLOCK=threading.Lock()   # token -> {"stage": queued|draft|check|done|error, "t": started}
def _draft_now(token):
    o=get(token)
    if o["draft"]: return
    h=json.loads(o["history"]); I=json.loads(o["intake"] or "{}")
    # Oct 2026: document text is NOT fed to the drafter. Only facts the customer confirmed on /confirm are in the history.
    t=time.time(); form=o["form"] or "aa"; taps=bool(I.get("rows")) and form in INTAKE.FORMS_V3
    if taps and llm.MOCK: d=INTAKE.fallback_draft(form,I)   # local runs: sentences from the taps (the sample case is someone else's story)
    else:
        try: d=llm.draft(h,form)
        except Exception as e:
            if not taps: raise
            # 28 Oct: if every drafting model fails, a tap order still gets plain sentences made only from its taps.
            # The answer check (grounding) still runs on them before the customer approves.
            print("draft fell back to taps",form,str(e)[:200],flush=True); d=INTAKE.fallback_draft(form,I)
    d.setdefault("answers",{}); print(f"timing draft {form} {time.time()-t:.1f}s{' (taps)' if d.get('drafted_from')=='taps' else ''}",flush=True)
    if I: merge_intake(o["form"] or "aa",d,I)
    c=db(); c.execute("update orders set draft=?, approved_at=null where token=? and draft is null",(json.dumps(d),token)); c.commit()
def _job(token):
    try:
        JOBS[token]["stage"]="docs"
        g=gate(token,run=True)
        if g: JOBS[token]["stage"]=g; return
        JOBS[token]["stage"]="draft"; _draft_now(token)
        JOBS[token]["stage"]="check"
        try: ground_ahead(token)
        except Exception as e: print("ground ahead failed (approve will retry)",str(e)[:200])
        JOBS[token]["stage"]="done"
    except Exception as e:
        print("prepare failed",token[:6],str(e)[:300]); JOBS[token]["stage"]="error"
def start_prepare(token):
    """Start drafting (and the answer check) in the background, once per order. Safe to call repeatedly."""
    with _JLOCK:
        j=JOBS.get(token)
        if j and j["stage"] in ("queued","docs","draft","check"): return j
        j=JOBS[token]={"stage":"queued","t":time.time()}
    threading.Thread(target=_job,args=(token,),daemon=True).start(); return j
# ---------- before drafting: review holds, document cross-check, contradictions ----------
def _intake_of(o): return json.loads(o["intake"] or "{}") if o["intake"] else {}
def needs_confirm(o):
    I=_intake_of(o)
    if not I or (o["form"] or "aa") not in INTAKE.FORMS_V3: return False
    if I.get("uploads") and not I.get("docs_checked"): return False   # still being read
    return bool(EVID.mismatches(I) or HONEST.contradictions(o["form"],I))
def gate(token,run=False):
    """'hold' | 'confirm' | None. run=True (background job) also does the slow parts: the review check and reading documents."""
    o=get(token)
    if o["draft"]: return None
    if FRAUD.held(o): return "hold"
    if run and not FRAUD.released(o) and check_hold(token,"before drafting"): return "hold"
    I=_intake_of(o)
    if run and I.get("uploads") and not I.get("docs_checked"): read_documents(token)
    return "confirm" if needs_confirm(get(token)) else None
def check_hold(token,stage):
    """Assess the order; if it should be held, hold it (once) and tell the team. Returns True if held."""
    c=db(); o=get(token)
    if FRAUD.released(o): return False
    if FRAUD.held(o): return True
    reasons=FRAUD.assess(c,o)
    if not reasons: return False
    c.execute("update orders set hold=? where token=? and hold is null",(json.dumps({"reasons":reasons,"at":time.time(),"stage":stage}),token)); c.commit()
    print("order held",token[:6],reasons,flush=True)
    subj,txt=FRAUD.notify_text(PUBLIC,o,reasons)
    def _send():
        try: mailer.send(FRAUD.REVIEW_TO,subj,txt)   # mailer keeps the Resend User-Agent header
        except Exception as e: print("hold email failed",str(e)[:200])
    threading.Thread(target=_send,daemon=True).start()
    return True
def read_documents(token):
    """Conditions and medicines written in the uploaded documents (word lists over PDF text, plus the reader for photos)."""
    o=get(token); I=_intake_of(o); text=I.get("doc_text","")
    f=EVID.read_text(text); imgs=[]
    for u in I.get("uploads") or []:
        if u.get("type") in llm.VISION_TYPES:
            try:
                p=os.path.join(OUT,token,"up",u["key"])   # uploads are stored under the order as their key (see uploads_add)
                b=store.read(token,u["key"]) if store.REMOTE else (open(p,"rb").read() if os.path.exists(p) else None)
                if b: imgs.append((u["type"],b))
            except Exception as e: print("upload read failed",str(e)[:120])
    try: f=EVID.merge_facts(f,llm.extract_evidence(imgs,text))
    except Exception as e: print("document reading fell back to word lists",str(e)[:200])
    I=_intake_of(get(token)); I["doc_facts"]=f; I["docs_checked"]=True
    c=db(); c.execute("update orders set intake=? where token=?",(json.dumps(I),token)); c.commit()
def ground_ahead(token):
    """Run the mandatory answer check now and store it, but only if the answers haven't changed meanwhile."""
    o=get(token); raw=o["draft"]
    if not raw: return
    d=json.loads(raw); h=_ghash(o,d)
    if (d.get("gcache") or {}).get("h")==h: return
    ev=_GRUN.get((token,h))
    if ev: ev.wait(120); return
    ev=_GRUN[(token,h)]=threading.Event()
    try:
        t=time.time(); G=ground(o,d); d["gcache"]={"h":h,"G":G}; print(f"timing check {o['form']} {time.time()-t:.1f}s",flush=True)
        c=db(); c.execute("update orders set draft=? where token=? and draft=?",(json.dumps(d),token,raw)); c.commit()
    finally: ev.set(); _GRUN.pop((token,h),None)
_GRUN={}
PREP_STEPS=[("read","Reading your answers and documents"),("draft","Filling in each section of your form"),("check","Checking every answer against what you told us"),("ready","Getting your form ready to check")]
def _stage(o):
    j=JOBS.get(o["token"]) or {}
    if o["draft"]: return "ready" if j.get("stage")!="check" else "check"
    return "error" if j.get("stage")=="error" else "read" if j.get("stage") in ("queued","docs") else "draft"
@app.get("/prepare/{token}")
def prepare(token:str):
    """After payment: draft from the interview (the only place drafting happens), then continue the paid flow."""
    o=ready(token)
    if not o["draft"]:
        g=gate(token)
        if g: return RedirectResponse(f"/{g}/{token}",303)
        j=start_prepare(token)
        for _ in range(8):   # quick drafts (and tests) go straight on, no waiting page
            if j["stage"] in ("check","done","error","hold","confirm"): break
            time.sleep(0.1)
        o=get(token)
        if j["stage"] in ("hold","confirm"): JOBS.pop(token,None); return RedirectResponse(f"/{j['stage']}/{token}",303)
    if o["draft"]: return RedirectResponse(f"/{'approve' if is_wf(o) else 'deadline'}/{token}",303)
    st=_stage(o)
    if st=="error": JOBS.pop(token,None)   # the next visit tries again
    items="".join(f'<li id="ps_{k}" class="{"pdone" if k=="read" else "pnow" if k=="draft" else ""}">{esc(t)}</li>' for k,t in PREP_STEPS)
    return page(prog(5,"Filling in your form")+f"""<div class=prep><h1>We're filling in your form</h1><p class=one>This usually takes under a minute. Please keep this page open. You'll check every answer before anything is final.</p>
<ol class=prepsteps>{items}</ol><div class="bar slim"><span id=pbar style="width:30%"></span></div>
<p class=small id=pmsg>{'This is taking longer than usual. Your answers are saved. <a href="/prepare/'+token+'">Try again</a>.' if st=="error" else ''}</p></div>
<noscript><meta http-equiv=refresh content="5"></noscript>
<script>(function(){{var n=0,order=["read","draft","check","ready"];function show(s){{var i=order.indexOf(s);order.forEach(function(k,j){{var e=document.getElementById("ps_"+k);e.className=j<i?"pdone":j==i?"pnow":""}});document.getElementById("pbar").style.width=Math.max(30,(i+1)*25)+"%"}}
function poll(){{n++;fetch("/api/{token}/progress",{{cache:"no-store"}}).then(function(r){{return r.json()}}).then(function(j){{if(j.next){{show("ready");location.replace(j.next);return}}
if(j.stage=="error"){{document.getElementById("pmsg").innerHTML='This is taking longer than usual. Your answers are saved. <a href="/prepare/{token}">Try again</a>.';return}}show(j.stage);setTimeout(poll,n<20?1500:4000)}}).catch(function(){{setTimeout(poll,4000)}})}}setTimeout(poll,1200)}})()</script>""","Filling in your form",minimal=True)
@app.get("/api/{token}/progress")
def prepare_progress(token:str):
    o=ready(token)
    if o["draft"]: return {"stage":"ready","next":f"/{'approve' if is_wf(o) else 'deadline'}/{token}"}
    j=JOBS.get(token)
    if j and j["stage"] in ("hold","confirm"): JOBS.pop(token,None); return {"stage":"draft","next":f"/{j['stage']}/{token}"}
    if FRAUD.held(o): return {"stage":"draft","next":f"/hold/{token}"}
    if not j: start_prepare(token)   # e.g. the server restarted mid-way: pick it up again
    st=_stage(get(token))
    return {"stage":st}
def merge_intake(form,d,I):
    """Facts the customer tapped go straight in (numbers, conditions, signing notes, tick boxes); the drafter only writes sentences."""
    d.setdefault("extra",{}).update(INTAKE.extra(form,I))
    if I.get("conds"): d["conditions"]=INTAKE.conditions(I)
    d["notes_for_user"]=INTAKE.notes(form,I)+list(d.get("notes_for_user") or [])
    if I.get("uploads"): d.setdefault("checklist",[]).append("Documents you uploaded to us: "+", ".join(u["name"] for u in I["uploads"])+". Send copies (not originals) with your form.")
    d.setdefault("checklist",[]).extend(EVID.checklist(form,I))
    if (I.get("wf") or {}).get("meds_how")=="photo": d["checklist"].append("A copy of your repeat prescription list. The form says it is sent with it.")   # what to send, or what to get if they have nothing yet
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
    q=await run_in_threadpool(llm.next_question,h,o["form"] or "aa"); h.append({"role":"assistant","content":q})
    c=db(); c.execute("update orders set history=? where token=?",(json.dumps(h),token)); c.commit()
    answered=sum(1 for m in h if m["role"]=="user" and m["content"].strip())
    return {"reply":q,"done":"[[DONE]]" in q,"topic":min(answered+1,total),"total":total}
@app.post("/api/{token}/finish")
def finish(token:str):
    o=ready(token,paid=False)
    c=db(); c.execute("update orders set interview_done_at=coalesce(interview_done_at,?) where token=?",(time.time(),token)); c.commit()
    if o["status"]=="paid" and o["consent_at"] and not o["draft"] and not (o["intake"] and not json.loads(o["intake"]).get("uploads_done")): start_prepare(token)
    return {"next":f"/prepare/{token}" if o["status"]=="paid" else f"/preview/{token}"}
_BLOCKS={}; _BLOCKS_L=threading.Lock()
def build_files(token,o,d):
    """One build per order at a time: a second concurrent build (double submit) used to delete the folder mid-write."""
    with _BLOCKS_L: lk=_BLOCKS.setdefault(token,threading.Lock())
    with lk: return _build_files(token,o,d)
def _build_files(token,o,d):
    form=o["form"] or "aa"; F=FORMS[form]; personal=json.loads(o["personal"] or "{}"); od=os.path.join(OUT,token); os.makedirs(od,exist_ok=True)
    if form=="atw":
        open(os.path.join(od,"answers.html"),"w").write(documents.pack_atw(BRAND,d,o["tier"]))
        documents.atw_docx(BRAND,d,o["tier"],os.path.join(od,"AccessToWork-answers.docx")); files=["answers.html","AccessToWork-answers.docx"]
        store.put_dir(token,od,files); return files
    pf=pack_files(o); off=prefill_off(o)
    open(os.path.join(od,"answers.html"),"w").write(documents.pack_form(BRAND,personal,d,o["tier"],form,prefill_off=bool(off),hand_details=hand_details(o)))
    files=["answers.html"]
    if F.get("pdf_out") in pf:
        tp=tapped(o)
        if tp:   # 'no difficulty' questions stay No with an empty box; aids go in the form's aids table
            d=dict(d); d["no_difficulty"]=tp[2]; d["extra"]={**(d.get("extra") or {}),**({"aids":INTAKE.aids_list(tp[0])} if INTAKE.aids_list(tp[0]) else {})}
        I_=json.loads(o["intake"] or "{}"); xt=WF.pdf_values(form,I_) if I_.get("wf_v") else None
        if xt and not d.get("ticks_confirmed_at"): xt=(xt[0],{},xt[2])   # tick boxes only once the customer has confirmed them
        fill_pdf.fill_form(form,personal,d,os.path.join(od,F["pdf_out"]),ticks=d.get("ticks") if d.get("ticks_confirmed_at") else None,extra=xt); files.append(F["pdf_out"])
        if I_.get("wf_v") and (I_.get("wf") or {}).get("stmt") not in (None,"","noone"):
            open(os.path.join(od,"Note-for-supporter.pdf"),"wb").write(contsheet.supporter_note(form,*WF.statement_note(form,I_,personal))); files.append("Note-for-supporter.pdf")
    if "PIP-extra-sheets.pdf" in pf:
        open(os.path.join(od,"PIP-extra-sheets.pdf"),"wb").write(pip_sheet_pdf(form,personal,d)); files.append("PIP-extra-sheets.pdf")
    if is_premium(o["tier"]):
        I=json.loads(o["intake"] or "{}")
        open(os.path.join(od,"assessment-briefing.html"),"w").write(PREMIUM.briefing(BRAND,form,personal,d)); files.append("assessment-briefing.html")
        open(os.path.join(od,"supporting-letters.html"),"w").write(PREMIUM.supporting_letters(BRAND,form,personal,d,I.get("people"),I)); files.append("supporting-letters.html")
        if o["appeal"]:
            ap=json.loads(o["appeal"]); nm=" ".join(x for x in (personal.get("other_names"),personal.get("surname")) if x)
            addr=", ".join(personal.get(k) for k in ("addr1","addr2","addr3","postcode") if personal.get(k))
            I0=I if I.get("who") or form=="dla" else json.loads((PLUS.root(db(),o) or {"intake":None})["intake"] or "{}")
            txt=letters.mr_letter(form if form in letters.NAMES else "pip",{"for":{"who":I0.get("who"),"signer":I0.get("signer")},"name":nm,"address":addr,"decision_date":datetime_fmt(ap["decision_date"]) if ap.get("decision_date") else "","points":PREMIUM.appeal_letter_points(form,d,ap.get("topics",[])),"evidence":["A copy of the decision letter"]+[u["name"] for u in ap.get("uploads",[])]})
            open(os.path.join(od,"reconsideration-letter.txt"),"w").write(txt); files.append("reconsideration-letter.txt")
    store.put_dir(token,od,files)   # to private Supabase bucket when configured (local temp copy removed)
    return files
def hand_details(o):
    """True when NI number and bank details are not on the filled form: not a whole-form order, or the customer chose Skip."""
    if (o["form"] or "aa") not in ("aa","dla"): return False
    return not is_wf(o) or bool(json.loads(o["draft"] or "{}").get("details_skipped"))
def prefill_off(o):
    """Reason pre-fill is switched off for this order's form (e.g. GOV.UK published a new version), else None."""
    F=FORMS[o["form"] or "aa"]
    return formwatch.disabled_reason(o["form"] or "aa") if (is_full(o["tier"]) and F["pdf"]) else None
def pack_files(o):
    form=o["form"] or "aa"; F=FORMS[form]
    if form=="atw": return ["answers.html","AccessToWork-answers.docx"]
    files=["answers.html"]
    if (is_full(o["tier"]) or is_wf(o)) and F["pdf"] and not prefill_off(o): files.append(F["pdf_out"])
    if is_wf(o) and ((json.loads(o["intake"] or "{}").get("wf") or {}).get("stmt") not in (None,"","noone")): files.append("Note-for-supporter.pdf")
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
    ready(token); p=await req.json()
    p={k:v for k,v in (p if isinstance(p,dict) else {}).items() if k in PERSONAL_KEYS}   # never NI numbers or bank details
    c=db(); c.execute("update orders set personal=? where token=?",(json.dumps(p),token)); c.commit(); return {"ok":True}
@app.get("/download/{token}/{name}")
def download(token:str,name:str):
    o=ready(token)
    if FRAUD.held(o): raise HTTPException(403,"We're checking your order")
    if not o["approved_at"] or not o["details_at"]: raise HTTPException(403,"Approve your answers first")
    if name not in pack_files(o): raise HTTPException(404)
    data=store.read(token,name)
    if data is None: raise HTTPException(404)
    bg=None
    if is_wf(o) and name==FORMS[o["form"]]["pdf_out"]:
        sv=SECURE.get(token)
        if sv:
            data=fill_pdf.overlay(o["form"],data,*SECURE.fields(o["form"],sv))
            if not o["post_pack"]:
                from starlette.background import BackgroundTask
                bg=BackgroundTask(SECURE.wipe,token)   # downloaded: delete them now
    ct={"html":"text/html; charset=utf-8","txt":"text/plain; charset=utf-8","pdf":"application/pdf","docx":"application/vnd.openxmlformats-officedocument.wordprocessingml.document"}[name.rsplit(".",1)[1]]
    disp="inline" if name.endswith(".html") else f'attachment; filename="{name}"'
    return Response(data,media_type=ct,headers={"Content-Disposition":disp,"Cache-Control":"private, no-store"},background=bg)
@app.post("/api/{token}/delete")
def delete(token:str):
    get(token); orders.erase(db(),OUT,token); SECURE.wipe(token); return {"deleted":True}
@app.get("/delete/{token}")
def delete_page(token:str):
    o=get(token)
    if o["status"]=="deleted": return page(DELETED_PAGE,"Deleted")
    return page(f"""<h1>Delete my information</h1><p class=lead>This deletes everything you told us for this order: your answers, your details and your documents. It can't be undone.</p>
<div class=warning>Download your documents first if you want to keep them.</div><form method=post action=/delete/{token}><button class="btn btn-warn">Delete everything now</button></form><p><a href=/start/{token}>Go back</a></p>""","Delete my information")
@app.post("/delete/{token}")
def delete_post(token:str):
    get(token); orders.erase(db(),OUT,token); SECURE.wipe(token); return page(DELETED_PAGE,"Deleted")
DETAIL_FIELDS=[("title","Title (optional)","",False),("other_names","First and middle names","",True),("surname","Surname","",True),("dob","Date of birth","date",True),
 ("addr1","Address line 1","",True),("addr2","Address line 2 (optional)","",False),("addr3","Town or city","",True),("postcode","Postcode","",True),("phone","Phone (optional)","tel",False)]
PERSONAL_KEYS={"title","other_names","surname","dob","addr1","addr2","addr3","postcode","phone","email","parent_title","parent_other_names","parent_surname","parent_dob","relationship","gp_name","gp_addr1","gp_postcode","gp_phone"}
DLA_EXTRA=[("parent_title","Your title (parent or guardian, optional)","",False),("parent_other_names","Your first names","",True),("parent_surname","Your surname","",True),("relationship","Your relationship to the child","",True)]
def detail_fields(form):
    if form=="atw": return [f for f in DETAIL_FIELDS if f[0] in("other_names","surname")]
    return DETAIL_FIELDS+(DLA_EXTRA if form=="dla" else [])
import re as _re
NI_RE=_re.compile(r"^[A-CEGHJ-PR-TW-Z]{2}\d{6}[A-D]$")
POST_OPT="<label class=cb><input type=checkbox name=post_pack value=1><span>Print and post my pack to me at the address above to sign, with a Freepost return envelope. You still check, sign and send the form yourself.</span></label>"
@app.get("/details/{token}")
def details_page(token:str, err:str=""):
    o=ready(token)
    if FRAUD.held(o): return _held_redirect(o)
    if not o["approved_at"]: return RedirectResponse(f"/approve/{token}",303)
    if ticks_pending(o): return RedirectResponse(f"/ticks/{token}",303)
    if is_wf(o): return private_page(o,err)
    p=json.loads(o["personal"] or "{}"); form=o["form"] or "aa"
    if o["intake"] and not o["details_at"]: p={**INTAKE.personal_prefill(form,json.loads(o["intake"])),**p}
    who="the child" if form=="dla" else "the person claiming"
    rows="".join(f"""<div class=field><label class=q for=d_{k}>{esc(l)}</label><input id=d_{k} name={k} {'type='+t if t else ''} value="{esc(p.get(k,''))}" {'required' if req else ''} autocomplete=off></div>""" for k,l,t,req in detail_fields(form))
    return page(prog(5,"Your details")+f"""<h1>Your details</h1><p class=one>We add these to your documents{'' if form=='atw' else f' for {who}'} so you have less to fill in by hand. We only ask now, at the end, so we don't keep them longer than needed.</p>
{f'<div class=warning>{esc(err)}</div>' if err else ''}<form method=post action=/details/{token}>{rows}{POST_OPT if (is_premium(o["tier"]) and printmail.ENABLED) else ""}<button class=btn>Save and make my documents</button></form>
<form method=post action=/details/{token}><input type=hidden name=skip value=1><button class="btn btn-2">Skip. I'll write my details in by hand</button></form>
<p class=small>We delete everything 90 days after your order, or now: <a href=/delete/{token}>delete my information</a>.</p>""","Your details")
@app.post("/details/{token}")
async def details_save(token:str, req:Request):
    o=ready(token)
    if not o["approved_at"]: return RedirectResponse(f"/approve/{token}",303)
    if ticks_pending(o): return RedirectResponse(f"/ticks/{token}",303)
    if FRAUD.held(o): return _held_redirect(o)
    fm=await req.form(); form=o["form"] or "aa"; p={}
    if is_wf(o): return await private_save(o,fm)
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
        pt=PLUS.redeemed_from(db(),token)
        po_=db().execute("select personal from orders where token=?",(pt,)).fetchone() if pt else None
        if po_ and not PLUS.same_person(json.loads(po_[0] or "{}"),p):
            return back("This included form is for the same person as your Done for you Plus order. For someone else, please start a new order. If their name has changed, email hello@formsorted.com.")
    c=db(); c.execute("update orders set personal=?, details_at=?, post_pack=? where token=?",(json.dumps(p),time.time(),1 if (fm.get("post_pack") and is_premium(o["tier"]) and printmail.ENABLED and not fm.get("skip")) else 0,token)); c.commit()
    if p and await run_in_threadpool(check_hold,token,"details"):   # names known now: check again before documents are made
        c.execute("update orders set details_at=null where token=?",(token,)); c.commit(); return RedirectResponse(f"/hold/{token}",303)
    o=get(token); files=await run_in_threadpool(build_files,token,o,json.loads(o["draft"]))
    if o["post_pack"]: printmail.queue(c,token,{k:p.get(k,"") for k in ("title","other_names","surname","addr1","addr2","addr3","postcode")},files)
    return RedirectResponse(f"/documents/{token}",303)

# ---------- Whole-form orders: NI numbers and bank details, for the PDF only ----------
def _priv_fields(o):
    """(name, label, hint, kind, required) for this order."""
    form=o["form"]; I=json.loads(o["intake"] or "{}"); w=I.get("wf") or {}; me=INTAKE.is_me(I,form)
    out=[]
    if form=="aa":
        out.append(("ni","Your National Insurance number" if me else "Their National Insurance number","It's on letters about tax, benefits or your pension. For example QQ 12 34 56 C.","ni",True))
        if I.get("signer") in ("poa","appointee","deputy"): out.append(("h_ni","Your own National Insurance number (you're signing for them)","","ni",False))
    else:
        out.append(("child_ni","The child's National Insurance number (if they have one)","Most children under 16 don't. Leave it blank if not.","ni",False))
        out.append(("ni","Your National Insurance number","","ni",True))
        if w.get("p_his")=="yes": out.append(("his_ni",f"{w.get('p_his_name') or 'Their'}'s National Insurance number" if w.get("p_his_name") else "Their National Insurance number","","ni",False))
    who="you" if (form=="dla" or me) else "them"
    out+=[("holder","Name of the account holder","Exactly as it's shown on the bank statement.","text",True),("bank","Name of the bank or building society","","text",True),
          ("sort","Sort code","6 numbers, for example 12-34-56.","sort",True),("acc","Account number","Usually 8 numbers.","acc",True),
          ("roll","Building society roll or reference number (optional)","Only if your building society gave you one.","text",False)]
    return out
def private_page(o, err=""):
    token=o["token"]; form=o["form"]
    rows="".join(f"""<div class=field><label class=q for=p_{k}>{esc(l)}</label>{f'<p class=hint>{esc(h)}</p>' if h else ''}<input id=p_{k} name={k} {'required' if req else ''} autocomplete=off {'inputmode=numeric' if kind in ('sort','acc') else 'autocapitalize=characters' if kind=='ni' else ''} maxlength=60></div>""" for k,l,h,kind,req in _priv_fields(o))
    other="<label class=cb><input type=checkbox name=other_ben value=1><span>Also pay any other benefits I get into this account (question 51 on the form).</span></label>" if form=="aa" else ""
    again="<div class=panel><p>For your safety we deleted these details after your download. Type them again to download another filled-in copy.</p></div>" if o["details_at"] else ""
    return page(prog(5,"Last details")+f"""<h1>Last details for the form</h1><p class=one>We write these onto your form and nowhere else.</p>
{more("How we keep these safe",f"<p>We never save them with your answers and never email them. They are held encrypted only until you download your form{', or until we post it' if o['post_pack'] else ''}, then deleted.</p><p>We delete everything else 90 days after your order, or now: <a href=/delete/{token}>delete my information</a>.</p>")}{again}
{f'<div class=warning role=alert>{esc(err)}</div>' if err else ''}<form method=post action=/details/{token}>{rows}{other}<button class="btn btn-big">Make my form</button></form>
<form method=post action=/details/{token}><input type=hidden name=skip value=1><button class=linkbtn>Skip. I'll write these in by hand</button></form>""","Last details",minimal=True)
async def private_save(o, fm):
    token=o["token"]; form=o["form"]; sv={}
    if not fm.get("skip"):
        for k,l,h,kind,req in _priv_fields(o):
            raw=str(fm.get(k,"")).strip()[:60]
            if not raw:
                if req: return private_page(o,"Please fill in every box that isn't marked optional, or choose Skip.")
                continue
            v={"ni":SECURE.clean_ni,"sort":SECURE.clean_sort,"acc":SECURE.clean_acc}.get(kind,lambda x:_re.sub(r"[\x00-\x1f<>]"," ",x)[:60])(raw)
            if not v: return private_page(o,{"ni":"That National Insurance number doesn't look right. It's 2 letters, 6 numbers, then A, B, C or D.","sort":"The sort code should be 6 numbers.","acc":"The account number should be 6 to 8 numbers."}[kind])
            sv[k]=v
        if fm.get("other_ben") and form=="aa": sv["other_ben"]=1
        SECURE.put(token,sv,keep_days=14 if o["post_pack"] else None)
    else: SECURE.wipe(token)
    d_=json.loads(o["draft"] or "{}"); d_["details_skipped"]=bool(fm.get("skip"))
    c=db(); c.execute("update orders set details_at=?, draft=? where token=?",(time.time(),json.dumps(d_),token)); c.commit()
    if await run_in_threadpool(check_hold,token,"details"):
        c.execute("update orders set details_at=null where token=?",(token,)); c.commit(); SECURE.wipe(token); return RedirectResponse(f"/hold/{token}",303)
    o=get(token); await run_in_threadpool(build_files,token,o,json.loads(o["draft"]))
    return RedirectResponse(f"/documents/{token}",303)
@app.get("/api/lookup/postcode")
def lookup_postcode(pc:str=""):
    """Town for a UK postcode (postcodes.io: free, no sign-up). Typed address always works if this is down."""
    r=WF.postcode(pc); return {"ok":bool(r),**(r or {})}
# ---------- Intake v3: tap-first questions (AA1, DLA1A, PIP2) ----------
def _intake_order(token):
    o=ready(token,paid=False)
    if (o["form"] or "aa") not in INTAKE.FORMS_V3: raise HTTPException(404)
    return o
def _intake_closed(o):
    """Paid orders that have been drafted can't change their answers here (they edit on the approve page)."""
    return o["status"]=="paid" and o["draft"]
HONEST_LINE="<p class=honest><strong>We only write what you tell us, so please answer honestly about a typical day.</strong></p>"
REFUSED_BOX=f"<div class=warning role=alert>{esc(HONEST.REFUSE_MSG)}</div>"
@app.get("/intake/{token}")
def intake_page(token:str, s:str="", r:str=""):
    o=_intake_order(token)
    if _intake_closed(o): return RedirectResponse(f"/start/{token}",303)
    form=o["form"]; d=json.loads(o["intake"] or "{}")
    if form in ("aa","dla") and WF.on() and "wf_v" not in d and not d.get("rows"): d["wf_v"]=1   # new orders: whole form
    secs=INTAKE.sections(form,d); ids=[k for k,_ in secs]
    sec=s if s in ids else (d.get("at") if d.get("at") in ids else ids[0]); i=ids.index(sec)
    left=WF.minutes_left(form,d,sec) if d.get("wf_v") else max(1,round(10*(len(ids)-i)/len(ids)))
    bar="".join(f'<li class="{"done" if j<i else "now" if j==i else ""}">{esc(l)}</li>' for j,(k,l) in enumerate(secs))
    refused=REFUSED_BOX if r else ""
    reassure="<p class=reassure>It's normal for this to feel hard. You only tap, we do the writing. Skip anything you're not sure about.</p>" if i==0 else ""
    first=(f'<p class=one>About {left} minutes. You only tap, we do the writing. Skip anything you\'re not sure about.</p>'+HONEST_LINE) if i==0 else ''
    return page(prog(3,f"Part {i+1} of {len(secs)}: {secs[i][1]}",f"About {left} minute{'s' if left!=1 else ''} left")+f"""<div class=intake>
{refused}{'<h1>We\'ll fill in your whole form for you</h1>' if i==0 else f'<h1>{esc(secs[i][1])}</h1>'}{first}<p class=qcount id=qcount aria-live=polite hidden></p>
<form method=post action=/intake/{token}><input type=hidden name=sec value={sec}><div class=qs id=qs>{INTAKE.section_body(form,sec,d)}</div>
{QHELP}<div class=navrow>{f'<button class="btn btn-2" name=nav value=back>Back</button>' if i else ''}<button class="btn btn-start" name=nav value=next>{'Finish' if i==len(ids)-1 else 'Next: '+esc(secs[i+1][1])}</button></div>
<p class=saved>Your answers are saved each time you finish a part.</p><button class="linkbtn" name=nav value=save>Save and finish later</button></form></div>{QS_JS}""",secs[i][1],minimal=True)
QHELP=more("Help with this question","""<ul class=tips><li>Think about a normal week, including the bad days.</li><li>If it changes from day to day, pick what happens on most days.</li><li>Not sure? Skip it and carry on. You can go back.</li><li>None of the answers fit? Tap <strong>Something else</strong> and type it in your own words.</li><li>You check every answer before anything is final.</li></ul>""")
# One question per screen: the server still gets the whole part in one POST (nothing else changes). Without JavaScript every question shows at once.
QS_JS="""<script>(function(){var box=document.getElementById('qs');if(!box)return;var form=box.closest('form'),nav=form.querySelector('.navrow'),sub=nav.querySelector('button[value=next]'),sback=nav.querySelector('button[value=back]'),cnt=document.getElementById('qcount');
var kids=[].slice.call(box.children).filter(function(e){return !/^(SCRIPT|STYLE|INPUT)$/.test(e.tagName)}),steps=[],pre=[];
function simple(e){return /^(FIELDSET|DIV)$/.test(e.tagName)&&!e.querySelector('.chips,.card,.cond,textarea,select,input[type=radio],input[type=checkbox],input[type=file],button')&&!!e.querySelector('input')}
kids.forEach(function(e){if(/^(P|H2|H3)$/.test(e.tagName)&&!e.querySelector('input,select,textarea')){e.setAttribute('data-qpre','1');pre.push(e);return}
var last=steps[steps.length-1],sm=simple(e);if(sm&&last&&last.sm&&last.els.length<3&&!pre.length){last.els.push(e);return}steps.push({els:pre.concat([e]),sm:sm});pre=[]});
if(pre.length&&steps.length)steps[steps.length-1].els=steps[steps.length-1].els.concat(pre);
if(steps.length<2)return;
function ok(st){return st.els.some(function(e){return !e.hidden&&!e.hasAttribute('data-qpre')})}
var cur=0,qb=document.createElement('button'),qn=document.createElement('button');qb.type=qn.type='button';qb.className='btn btn-2';qb.textContent='Back';qn.className='btn btn-start';qn.textContent='Next question';
nav.insertBefore(qb,nav.firstChild);nav.appendChild(qn);
function live(){return steps.filter(ok)}
function show(focus){var L=live();if(L.indexOf(steps[cur])<0){for(var j=cur;j<steps.length&&!ok(steps[j]);j++);cur=j<steps.length?j:steps.indexOf(L[L.length-1])}
var k=L.indexOf(steps[cur]);steps.forEach(function(st,j){st.els.forEach(function(e){e.classList.toggle('qoff',j!==cur)})});
cnt.hidden=false;cnt.textContent='Question '+(k+1)+' of '+L.length;var lastq=k===L.length-1;qn.hidden=lastq;sub.hidden=!lastq;qb.hidden=k===0;if(sback)sback.hidden=k>0;
if(focus){var h=steps[cur].els.filter(function(e){return !e.hidden})[0];var t=h&&h.querySelector('legend,h3,.q');if(t){t.setAttribute('tabindex','-1');t.focus({preventScroll:true})}cnt.scrollIntoView({block:'start'})}}
function go(d){var L=live(),k=L.indexOf(steps[cur])+d;if(k<0||k>=L.length)return;cur=steps.indexOf(L[k]);show(true)}
qn.addEventListener('click',function(){go(1)});qb.addEventListener('click',function(){go(-1)});
form.addEventListener('keydown',function(ev){if(ev.key==='Enter'&&ev.target.tagName==='INPUT'&&!qn.hidden){ev.preventDefault();go(1)}});
document.addEventListener('change',function(){setTimeout(function(){show(false)},0)});
window.qsShowAll=function(){steps.forEach(function(st){st.els.forEach(function(e){e.classList.remove('qoff')})});qn.hidden=qb.hidden=cnt.hidden=true;sub.hidden=false;if(sback)sback.hidden=false};
show(false)})();</script>"""
@app.post("/intake/{token}")
async def intake_save(token:str, req:Request):
    o=_intake_order(token)
    if _intake_closed(o): return RedirectResponse(f"/start/{token}",303)
    form=o["form"]; fm=await req.form(); sec=str(fm.get("sec",""))
    d0=json.loads(o["intake"] or "{}")
    if form in ("aa","dla") and WF.on() and "wf_v" not in d0 and not d0.get("rows"): d0["wf_v"]=1
    ids=[k for k,_ in INTAKE.sections(form,d0)]
    if sec not in ids: raise HTTPException(400)
    d=INTAKE.save(form,sec,d0,fm); ids=[k for k,_ in INTAKE.sections(form,d)]; i=ids.index(sec) if sec in ids else 0; nav=fm.get("nav","next")
    if d.get("wf_v"): WF.minutes_left(form,d,ids[min(i+1,len(ids)-1)])
    if HONEST.scrub(d):   # asked us to exaggerate: not saved, same section again with a polite note
        d["at"]=sec; c=db(); c.execute("update orders set intake=?, interview_done_at=null where token=? and status in ('free','paid')",(json.dumps(d),token)); c.commit()
        return RedirectResponse(f"/intake/{token}?s={sec}&r=1",303)
    nxt=ids[max(0,i-1)] if nav=="back" else ids[i] if nav=="save" else (ids[i+1] if i+1<len(ids) else None)
    d["at"]=nxt or sec; c=db()
    if nxt is None:   # finished: build the answers transcript the rest of the pipeline uses
        c.execute("update orders set intake=?, history=?, interview_done_at=? where token=?",(json.dumps(d),json.dumps(INTAKE.history(form,d)),time.time(),token)); c.commit()
        if d.get("wf_v"):   # whole form: their details go on the form; evidence next, then pay
            p={**json.loads(o["personal"] or "{}"),**WF.personal(form,d)}; p={k:v for k,v in p.items() if k in PERSONAL_KEYS}
            c.execute("update orders set personal=? where token=?",(json.dumps(p),token))
            asked=(d.get("wf") or {}).get("asked")
            if asked and not json.loads(o["deadline"] or "{}").get("requested"): c.execute("update orders set deadline=? where token=?",(json.dumps({"how":"phone","requested":asked,"received":""}),token))
            c.commit()
            if not d.get("uploads_done"): return RedirectResponse(f"/uploads/{token}",303)
        return RedirectResponse(f"/start/{token}" if o["status"]=="paid" else f"/preview/{token}",303)
    c.execute("update orders set intake=?, interview_done_at=null where token=? and status in ('free','paid')",(json.dumps(d),token)); c.commit()
    if nav=="save":
        return page(f"""<h1>Your answers are saved</h1><p class=lead>Come back any time in the next 7 days with this private link. Keep it safe: anyone with the link can see your answers.</p>
<p class=savelink><code>{esc(PUBLIC)}/intake/{token}</code></p><button class=btn onclick="navigator.clipboard.writeText('{esc(PUBLIC)}/intake/{token}')">Copy link</button>
<p><a href="/intake/{token}?s={nxt}">Carry on now</a></p>""","Saved",minimal=True)
    return RedirectResponse(f"/intake/{token}?s={nxt}",303)
UP_MAX=10*1024*1024; UP_TYPES={"application/pdf":"pdf","image/jpeg":"jpg","image/png":"png","image/heic":"heic","image/webp":"webp"}
def _up_order(token):
    """Paid orders; whole-form orders also before payment (evidence is a question, nothing is produced until paid)."""
    o=ready(token,paid=False)
    if o["status"]!="paid" and not (is_wf(o) and o["interview_done_at"]): raise HTTPException(402)
    return o
@app.get("/uploads/{token}")
def uploads_page(token:str, err:str=""):
    o=_up_order(token)
    if o["draft"]: return RedirectResponse(f"/start/{token}",303)
    I=json.loads(o["intake"] or "{}"); ups=I.get("uploads") or []; form=o["form"] or "aa"
    lst="".join(f"<li>{esc(u['name'])}</li>" for u in ups)
    chips=INTAKE._checks("evidence",EVID.options(form),I.get("evidence"),INTAKE.X(I,"evidence"))
    paid_=o["status"]=="paid"
    return page(prog(5 if paid_ else 3,"Your evidence","last part" if not paid_ else "")+f"""<h1>What do you have that shows this?</h1><p class=one>{'Payment received, thank you. ' if paid_ else ''}Tap what you have. Add a photo if you can.</p>
{f'<div class=warning>{esc(err)}</div>' if err else ''}{'<div class=promise><strong>Your repeat prescription list:</strong> you said you\'d add a photo of it. Add it below, or send a copy with your form. The form says it is enclosed.</div>' if (I.get('wf') or {}).get('meds_how')=='photo' else ''}<form method=post action=/uploads/{token}/done enctype=multipart/form-data>
<fieldset class=iq><legend>Tap all you have</legend>{chips}</fieldset>
{f'<h2 class=h3>Added</h2><ul class=ticks>{lst}</ul>' if ups else ''}<div class=field><label class=q for=up>{'Add more photos or PDFs' if ups else 'Add a photo or PDF'} (optional, up to 10MB each)</label><p class=hint>A photo of a letter or your repeat prescription list is fine.</p><input id=up type=file name=files multiple accept="image/*,application/pdf" capture=environment></div>
<div class=navrow><button class="btn btn-start" name=nav value=next>Continue</button></div><button class=linkbtn name=nav value=add>Add more files first</button></form>
{more("Why we ask, and what if I have nothing yet?","<p>Evidence makes your form much stronger. We check it against your answers, and you'll still check everything before it's final.</p><p>Nothing yet? That's fine. Tap \"Nothing yet\" or just continue. We'll tell you what to ask your GP surgery for. Your documents are deleted with the rest of your order after 90 days, or sooner if you ask.</p>")}""","Your evidence",minimal=True)
@app.post("/uploads/{token}")
async def uploads_add(token:str, req:Request):
    o=_up_order(token)
    if o["draft"]: return RedirectResponse(f"/start/{token}",303)
    fm=await req.form(); I=json.loads(o["intake"] or "{}"); err=await _take_files(token,I,fm)
    c=db(); c.execute("update orders set intake=? where token=?",(json.dumps(I),token)); c.commit()
    return RedirectResponse(f"/uploads/{token}"+("?err="+urllib.parse.quote(err) if err else ""),303)
async def _take_files(token,I,fm):
    ups=I.setdefault("uploads",[]); err=""
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
        I["docs_checked"]=False   # new document: read it again before drafting
    if not ups: I.pop("uploads",None)
    return err
@app.post("/uploads/{token}/done")
async def uploads_done(token:str, req:Request):
    o=_up_order(token)
    if o["draft"]: return RedirectResponse(f"/start/{token}",303)
    I=json.loads(o["intake"] or "{}"); form=o["form"] or "aa"
    try: fm=await req.form()
    except Exception: fm=None
    err=""
    if fm is not None:
        if fm.get("evidence_on") or fm.getlist("evidence") or fm.get("evidence_xon") or "nav" in fm:
            ok=dict(EVID.options(form)); I["evidence"]=[x for x in fm.getlist("evidence") if x in ok]
            x=INTAKE.other_txt(fm,"evidence")
            if HONEST.refuse(x): x=""; I["refused"]=int(I.get("refused") or 0)+1; err=HONEST.REFUSE_MSG
            I.setdefault("else",{})["evidence"]=x
        e2=await _take_files(token,I,fm); err=err or e2
    if err or (fm is not None and fm.get("nav")=="add"):
        c=db(); c.execute("update orders set intake=? where token=?",(json.dumps(I),token)); c.commit()
        return RedirectResponse(f"/uploads/{token}"+("?err="+urllib.parse.quote(err) if err else ""),303)
    I["uploads_done"]=True
    c=db(); c.execute("update orders set intake=? where token=?",(json.dumps(I),token)); c.commit()
    if o["status"]!="paid": return RedirectResponse(f"/preview/{token}",303)
    if o["interview_done_at"] and not o["draft"]: start_prepare(token)
    return RedirectResponse(f"/prepare/{token}",303)

# ---------- Before drafting: check documents and answers that don't match (max 3 tap questions) ----------
def _confirm_items(o):
    I=_intake_of(o); return I,EVID.mismatches(I),HONEST.contradictions(o["form"],I)
@app.get("/confirm/{token}")
def confirm_page(token:str, err:str=""):
    o=ready(token)
    if o["draft"] or FRAUD.held(o): return RedirectResponse(f"/start/{token}",303)
    I,M,Q=_confirm_items(o)
    if not (M or Q): return RedirectResponse(f"/prepare/{token}",303)
    form=o["form"]; me=INTAKE.is_me(I,form); my="my" if me else ("my child's" if form=="dla" else "their")
    body=""
    dc=[m for m in M if m["kind"]=="doc_cond"]; dm=[m for m in M if m["kind"]=="doc_meds"]; sc=[m for m in M if m["kind"]=="said_cond"]
    if dc: body+=INTAKE._q("Your documents also mention these. Tick any you want on the form:",'<div class=chips>'+"".join(INTAKE._chk("addc",m["id"],m["text"],False) for m in dc)+'</div>',"Only tick what's right. We leave the rest out.")
    for m in dm: body+=INTAKE._q(f"Your documents list these medicines: {m['text']}. Add them to {my} form?",INTAKE._radios(m["id"],[("yes","Yes, add them"),("no","No, leave them out")],"")+INTAKE._else(m["id"],""))
    if sc: body+=INTAKE._q("You told us about these, but we didn't see them in your documents. That's fine, most letters only cover one thing. Untick any that aren't right:",'<div class=chips>'+"".join(INTAKE._chk("keepc",m["id"],m["text"],True) for m in sc)+'</div>')
    for q in Q:
        body+=INTAKE._q(q["q"],INTAKE._radios("q_"+q["id"],q["opts"],"",' nums' if q.get("nums") else '')+INTAKE._else("q_"+q["id"],""),"Or tap Something else and tell us in your own words.")
    n=len(Q)+len(dm)
    return page(prog(5,"Quick check")+f"""<h1>Quick check before we write</h1><p class=one>{'A few things' if n+bool(dc)+bool(sc)>1 else 'One thing'} didn't quite match. Tap what's right, so your form is accurate. We only write what you confirm.</p>
{f'<div class=warning role=alert>{esc(err)}</div>' if err else ''}<form method=post action=/confirm/{token}>{body}<div class=navrow><button class="btn btn-start">Continue</button></div></form>""","Quick check",minimal=True)
@app.post("/confirm/{token}")
async def confirm_save(token:str, req:Request):
    o=ready(token)
    if o["draft"] or FRAUD.held(o): return RedirectResponse(f"/start/{token}",303)
    fm=await req.form(); I,M,Q=_confirm_items(o); form=o["form"]
    missing=[q for q in Q if str(fm.get("q_"+q["id"]) or "") not in dict(q["opts"]) and not INTAKE.other_txt(fm,"q_"+q["id"])]
    if missing: return RedirectResponse(f"/confirm/{token}?err="+urllib.parse.quote("Please answer each question (or tap Something else)."),303)
    res=I.setdefault("doc_resolved",{}); add=set(fm.getlist("addc")); keep=set(fm.getlist("keepc"))
    for m in M:
        if m["kind"]=="doc_cond":
            if m["id"] in add: I.setdefault("conds",[]).append({"name":m["text"],"since":"","treat":[],"tx":"","from_doc":True})
            res[m["id"]]="add" if m["id"] in add else "no"
        elif m["kind"]=="doc_meds":
            v=str(fm.get(m["id"]) or ""); x=INTAKE.other_txt(fm,m["id"])
            if HONEST.refuse(x): x=""; I["refused"]=int(I.get("refused") or 0)+1
            if v=="yes": I["meds_confirmed"]=list(dict.fromkeys((I.get("meds_confirmed") or [])+m["items"]))
            if x: I["meds_confirmed"]=(I.get("meds_confirmed") or [])+[x]
            res[m["id"]]=v or ("else" if x else "skip")
        elif m["kind"]=="said_cond":
            if m["id"] not in keep: I["conds"]=[c for c in I.get("conds") or [] if c.get("name")!=m["text"]]
            res[m["id"]]="keep" if m["id"] in keep else "removed"
    for q in Q: HONEST.apply(form,I,q,str(fm.get("q_"+q["id"]) or ""),INTAKE.other_txt(fm,"q_"+q["id"]))
    c=db(); c.execute("update orders set intake=?, history=? where token=?",(json.dumps(I),json.dumps(INTAKE.history(form,I)),token)); c.commit()
    return RedirectResponse(f"/prepare/{token}",303)
HOLD_PAGE="""<div class=prep><h1>We're checking your order</h1><p class=lead>Thank you. We're checking a few details on your order before we fill in your form. We'll email you shortly.</p><p>You don't need to do anything now. Your answers are saved.</p></div>"""
@app.get("/hold/{token}")
def hold_page(token:str):
    o=get(token)
    if not FRAUD.held(o): return RedirectResponse(f"/start/{token}",303)
    return page(HOLD_PAGE,"We're checking your order",minimal=True)
def _held_redirect(o):
    return RedirectResponse(f"/hold/{o['token']}",303) if FRAUD.held(o) else None
# ---------- Admin: held orders (release or refund). Key: ADMIN_SECRET, or CRON_SECRET if that isn't set ----------
ADMIN_SECRET=os.getenv("ADMIN_SECRET","") or CRON_SECRET
def _admin_ok(key):
    if not ADMIN_SECRET or not hmac.compare_digest(str(key or ""),ADMIN_SECRET): raise HTTPException(403)
def admin_page(body):
    return HTMLResponse(f"""<!doctype html><html lang=en-GB><head><meta charset=utf-8><meta name=viewport content='width=device-width,initial-scale=1'><link rel=stylesheet href=/static/app.css?v={CSS_V}><title>Held orders | Admin</title><meta name=robots content=noindex></head><body><main id=main><div class=wrap>{body}</div></main></body></html>""",headers={"Cache-Control":"no-store"})
@app.get("/admin")
def admin_home():
    if not ADMIN_SECRET: raise HTTPException(404)
    return admin_page("""<h1>Held orders</h1><form method=post action=/admin/held><div class=field><label class=q for=k>Admin key</label><input id=k type=password name=key autocomplete=off required></div><button class=btn>Show held orders</button></form>""")
def _held_rows(c):
    out=[]
    for r in c.execute("select * from orders where hold is not null and status='paid' order by created desc limit 200").fetchall():
        if FRAUD.held(r): out.append(r)
    return out
@app.post("/admin/held")
def admin_held(key:str=Form("")):
    _admin_ok(key); c=db(); rows=_held_rows(c); ke=esc(key)
    def card(r):
        h=FRAUD.hold_info(r); I=_intake_of(r); _,T=INTAKE.topic_texts(r["form"],I) if I and r["form"] in INTAKE.FORMS_V3 else ("",{})
        said="".join(f"<li><strong>{esc(t)}</strong>: {esc(v[:300])}</li>" for t,v in T.items() if v)
        return f"""<div class=trace><h3>{esc(r['token'][:8])} · {esc(r['form'])} · {esc(r['tier'])} · {time.strftime('%d %b %H:%M',time.localtime(r['created'] or 0))}</h3>
<p><strong>Why held:</strong></p><ul>{''.join(f'<li>{esc(x)}</li>' for x in h.get('reasons',[]))}{"<li>asked us to exaggerate once (refused)</li>" if int(I.get('refused') or 0)==1 else ''}</ul>
<p>Claimant: {esc(FRAUD.claimant(r) or 'not given yet')} · Email: {esc(r['email'] or '-')} · IP: {esc(r['ip'] or '-')}</p><details><summary>Their answers</summary><ul>{said}</ul></details>
<form method=post action=/admin/release/{r['token']} style="display:inline"><input type=hidden name=key value="{ke}"><button class=btn>Release (carry on)</button></form>
<form method=post action=/admin/refund/{r['token']} style="display:inline" onsubmit="return confirm('Refund in full and delete their answers?')"><input type=hidden name=key value="{ke}"><button class="btn btn-warn">Refund and delete</button></form></div>"""
    return admin_page(f"<h1>Held orders ({len(rows)})</h1>"+("".join(card(r) for r in rows) or "<p>Nothing is held.</p>"))
def _mail_customer(o,subj,txt):
    if not o["email"]: return
    def _s():
        try: mailer.send(o["email"],subj,txt)
        except Exception as e: print("customer email failed",str(e)[:200])
    threading.Thread(target=_s,daemon=True).start()
@app.post("/admin/release/{token}")
def admin_release(token:str, key:str=Form("")):
    _admin_ok(key); o=get(token)
    if not FRAUD.held(o): raise HTTPException(409,"Not held")
    h=FRAUD.hold_info(o); h["released_at"]=time.time()
    c=db(); c.execute("update orders set hold=? where token=?",(json.dumps(h),token)); c.commit()
    if o["interview_done_at"] and not o["draft"] and (_intake_of(o).get("uploads_done") or not o["intake"]): start_prepare(token)
    _mail_customer(o,f"{BRAND}: your form is being prepared",f"Thank you for waiting. We've checked your order and you can carry on now.\n\nCarry on here: {PUBLIC}/start/{token}\n\nKeep this link private.\n\n{BRAND}")
    return admin_page(f"<h1>Released</h1><p>Order {esc(token[:8])} is carrying on. The customer has been emailed.</p><form method=post action=/admin/held><input type=hidden name=key value='{esc(key)}'><button class=btn>Back to held orders</button></form>")
@app.post("/admin/refund/{token}")
def admin_refund(token:str, key:str=Form("")):
    _admin_ok(key); o=get(token)
    if o["status"]!="paid": raise HTTPException(409,"Not a paid order")
    if not DEV:
        s=stripe("GET","/checkout/sessions/"+urllib.parse.quote(o["stripe_session"])) if o["stripe_session"] else {}
        pi=s.get("payment_intent")
        if not pi: raise HTTPException(409,"No payment found to refund. Refund it in the payment dashboard instead.")
        stripe("POST","/refunds",{"payment_intent":pi if isinstance(pi,str) else pi["id"],"reason":"requested_by_customer","metadata[token]":token})
    email=o["email"]; orders.erase(db(),OUT,token)
    c=db(); c.execute("update orders set status='refunded' where token=?",(token,)); c.commit()
    if email: _mail_customer({"email":email},f"{BRAND}: your order has been cancelled and refunded",f"We've cancelled your order and refunded your payment in full. Refunds usually reach your account in 5 to 10 working days.\n\nWe have deleted the answers you gave us.\n\n{BRAND}")
    return admin_page(f"<h1>Refunded</h1><p>Order {esc(token[:8])} was refunded and its answers deleted.</p><form method=post action=/admin/held><input type=hidden name=key value='{esc(key)}'><button class=btn>Back to held orders</button></form>")

# ---------- Deadline tracker, strength check, approval, saved answers, review mode, MR letter ----------
PROMISE="<div class=promise><strong>Your words only.</strong> We only use what you told us. You approve every word before you send.</div>"
def ordered(token):
    o=ready(token)
    if FRAUD.held(o): return _held_redirect(o),None,None
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
    return page(prog(5,"Timing")+(f"""<h1>Timing</h1><p class=lead>When you apply can affect who pays for equipment. Tell us when you started (or will start) this job.</p>""" if form=='atw' else f"""<h1>Your deadline</h1><p class=lead>Tell us when you asked for the form, and we'll show the date to send it back by, so you don't lose money.</p>""")+f"""
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
def check_page(token:str, r:str=""):
    refused=REFUSED_BOX if r else ""
    r,o,d=ordered(token)
    if r: return r
    mode,G,I=_strength(o,d); skip=f'<a class="btn btn-2" href="/approve/{token}">Skip, my form is ready</a>'
    if not G:
        return page(prog(5,"Strength check")+f"""<h1>Your answers look complete</h1><p class=lead>We've got what we need to fill in your form.</p><p><a class=btn href="/approve/{token}">Continue to check your form</a></p>""","Strength check")
    if mode=="v4":
        rows="".join(f"""<fieldset class="sc iq"><legend><strong>{esc(g['label'])}</strong>: {esc(g['q'])}</legend><div class="chips{' nums' if g['kind']=='days' else ''}">{''.join(f'<label class=chip><input type=radio name="g_{g["rid"]}_{g["kind"]}" value="{v}"><span>{esc(t)}</span></label>' for v,t in g['opts'])}</div>
{'' if g.get('noelse') else f'<label class=hint for="g_{g["rid"]}_{g["kind"]}_x">Something else, or add a detail (optional)</label><input type=text id="g_{g["rid"]}_{g["kind"]}_x" name="g_{g["rid"]}_{g["kind"]}_x" maxlength=500>'}</fieldset>""" for g in G)
    else:
        rows="".join(f"""<div class="sc"><h3>{esc(x['label'])}</h3><p class=ans>{esc(x['answer'])}</p>{''.join(f'<p class=hint>{esc(f)}</p>' for f in x['flags'])}<label class=hint for="add_{x['id']}">Add detail in your own words (optional)</label><textarea id="add_{x['id']}" name="add_{x['id']}" rows=2></textarea></div>""" for x in G)
    n=len(G); qs=f"{n} quick question{'s' if n>1 else ''}"
    return page(prog(5,"Strength check")+refused+f"""<h1>We can make these stronger</h1><p class=lead>{qs} to make your form stronger (optional). Only add what's true.</p>
<form method=post action=/check/{token}>{rows}<p><button class=btn>Save and continue</button> {skip}</p></form>""","Strength check")
@app.post("/check/{token}")
async def check_save(token:str, req:Request):
    r,o,d=ordered(token)
    if r: return r
    fm=await req.form(); a=d["answers"]; extra=d.setdefault("user_added",{})
    if any(HONEST.refuse(str(v)) for k,v in fm.items() if k.endswith("_x") or k.startswith("add_")):
        I0=_intake_of(o)
        if I0:
            I0["refused"]=int(I0.get("refused") or 0)+1; c=db(); c.execute("update orders set intake=? where token=?",(json.dumps(I0),token)); c.commit()
            if check_hold(token,"check"): return RedirectResponse(f"/hold/{token}",303)
        return RedirectResponse(f"/check/{token}?r=1",303)
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
    threading.Thread(target=_safe_ground_ahead,args=(token,),daemon=True).start()
    return RedirectResponse(f"/approve/{token}",303)
def _safe_ground_ahead(token):
    try: ground_ahead(token)
    except Exception as e: print("ground ahead failed (approve will retry)",str(e)[:200])
def BUSY(token):
    return page(f"""<h1>We're still checking your answers</h1><p class=lead>We check every answer against what you told us before you approve it. That check is taking longer than usual. Your answers are saved. Please try again in a few minutes.</p><a class="btn btn-start" href="/approve/{token}">Try again</a>""","Checking your answers")
def source_text(o,d):
    h=json.loads(o["history"] or "[]"); parts=[m["content"] for m in h if m["role"]=="user"]
    parts+=list((d.get("user_added") or {}).values())+[v for v in (d.get("said") or {}).values()]
    return "\n".join(parts)
def ground(o,d):
    if os.getenv("MOCK_GROUND_SLOW"): time.sleep(float(os.getenv("MOCK_GROUND_SLOW")))   # test hook: simulate a slow AI provider
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
HONEST_TICK="I confirm everything is true. I understand giving false information to DWP is an offence, and I could be prosecuted or have to pay money back."
def render_approve(token,o,d,G,fm=None,need_ok=(),need_res=(),need_honest=False):
    F=FORMS[o["form"] or "aa"]; sm=said_map(o); added=d.get("user_added",{}); labels={t:l for t,l,_ in F["topics"]}; its=flag_items(o,d,G)
    ans=lambda t: str(fm.get(f"ans_{t}")) if fm and fm.get(f"ans_{t}") is not None else d['answers'].get(t,'')
    rows="".join(f"""<div class="trace{' needs' if t in need_ok else ''}" id="topic_{t}"><h3>{esc(l)}</h3><div class=cols><div><p class=lbl>What you told us</p><p class=you>{esc(sm.get(t,'')) or '<em>Nothing for this topic</em>'}{f'<br><strong>You added:</strong> {esc(added[t])}' if t in added else ''}</p></div>
<div><p class=lbl>What goes on the form (edit if needed)</p><textarea name="ans_{t}" rows=4>{esc(ans(t))}</textarea></div></div>
{flag_html(t,its,fm,need_res,labels)}{'<p class=err>Please tick to approve this answer</p>' if t in need_ok else ''}<label class=cb><input type=checkbox id="ok_{t}" name="ok_{t}" required {'checked' if fm and fm.get(f'ok_{t}') else ''}><span>I approve this answer. It is true and in my words.</span></label></div>""" for t,l,_ in F["topics"])
    n=len(need_ok)+len(need_res)+bool(need_honest); summary=""
    if n:
        links=[f'<li><a href="#topic_{t}">Approve: {esc(labels[t])}</a></li>' for t in need_ok]+(['<li><a href="#honest">Confirm everything is true</a></li>'] if need_honest else [])+[f'<li><a href="#res_{i["key"]}">Choose keep, edit or remove: "{esc(i["sentence"][:80])}{"…" if len(i["sentence"])>80 else ""}"</a></li>' for i in its if i["key"] in need_res]
        summary=f"""<div class=errsum role=alert tabindex=-1 id=errsum><h2>{n} answer{'s' if n!=1 else ''} still need{'' if n!=1 else 's'} a choice</h2><ul>{''.join(links)}</ul></div>"""
    pending=[i for i in its if not (fm and fm.get(f"res_{i['key']}") in ("keep","edit","remove"))]
    keepall=f"""<p><button class="btn btn-2" name=keepall value=1 formnovalidate>Keep all remaining ({len(pending)}) as true</button> <span class=hint>Only if every one of them is true.</span></p>""" if pending else ""
    facts_=wf_facts(o) if is_wf(o) else ""
    return page(prog(5,"Check and approve")+f"""{summary}<h1>Check and approve every answer</h1><p class=one>Change anything that isn't right, then tick to approve each answer.</p>{more("How this works",PROMISE+"<p>Each answer is shown next to what you told us. Nothing is ready to download until you approve each answer.</p>")}
<form method=post action=/approve/{token}>{facts_}{rows}{keepall}
<label class=cb><input type=checkbox name=save {'checked' if fm and fm.get('save') else ''}><span>Save my answers for next time (for a review or renewal). We'll give you a save code. Saved answers are kept for 90 days unless you delete them.</span></label>
{'<p class=err>Please tick to confirm everything is true</p>' if need_honest else ''}<label class="cb honest{' needs' if need_honest else ''}" id=honest><input type=checkbox name=honest required {'checked' if fm and fm.get('honest') else ''}><span>{esc(HONEST_TICK)}</span></label>
<button class="btn btn-big">I approve. Make my documents</button></form>""","Approve your answers")
_TU={}
def _tooltips(form):
    if form not in _TU:
        from pypdf import PdfReader
        r=PdfReader(os.path.join(HERE,{"aa":"aa1.pdf","dla":"dla1a.pdf"}[form])); t={}
        for f,v in (r.get_fields() or {}).items(): t[f]=str(v.get("/TU") or f)
        _TU[form]=t
    return _TU[form]
def wf_facts(o):
    """Read-only list of the boxes filled straight from their answers (names, dates, doctors, times), to check before approving."""
    form=o["form"]; I=json.loads(o["intake"] or "{}"); V,_,notes=WF.pdf_values(form,I); P=json.loads(o["personal"] or "{}")
    tu=_tooltips(form); m=fill_pdf._personal(P,fill_pdf.PERSONAL_FIELDS if form=="aa" else fill_pdf.DLA_PERSONAL)
    items=[(tu.get(f,f),v) for f,v in list(m.items())+[(k,v) for k,v in V.items() if not k.startswith("_")]]
    lis="".join(f"<li><span class=hint>{esc(_short(l))}</span><br><strong>{esc(v)}</strong></li>" for l,v in items)
    return f"""<details class="trace facts"><summary><strong>Facts we copied onto the form ({len(items)} boxes)</strong></summary><p class=hint>These come straight from your answers. If one is wrong, correct it on the printed form before you sign, or tell us at hello@formsorted.com.</p><ul class=factlist>{lis}</ul>{''.join(f'<p>{esc(n)}</p>' for n in notes)}</details>"""
def _short(l):
    l=_re.sub(r"^(Your care needs during the day|About you|About the child) - ","",l); return l[:140]
@app.get("/approve/{token}")
def approve_page(token:str):
    r,o,d=ordered(token)
    if r: return r
    ev=_GRUN.get((token,_ghash(o,d)))
    if ev: ev.wait(60); r,o,d=ordered(token)   # the check started after the last step is nearly done: use it
    try: G=ground_cached(o,d,token)
    except grounding.GroundingUnavailable as e: print("grounding unavailable",e); return BUSY(token)
    return render_approve(token,o,d,G)
@app.post("/approve/{token}")
async def approve_save(token:str, req:Request):
    r,o,d=ordered(token)
    if r: return r
    fm=dict((await req.form()).items()); F=FORMS[o["form"] or "aa"]
    ev=_GRUN.get((token,_ghash(o,d)))
    if ev: await run_in_threadpool(ev.wait,60); r,o,d=ordered(token)   # a check for these exact answers is already running
    try: G=await run_in_threadpool(ground_cached,o,d,token)   # blocking AI call: never on the event loop (502 outage 27 Oct)
    except grounding.GroundingUnavailable as e: print("grounding unavailable",e); return BUSY(token)
    its=flag_items(o,d,G)
    if fm.get("keepall"):
        for i in its:
            if fm.get(f"res_{i['key']}") not in ("keep","edit","remove"): fm[f"res_{i['key']}"]="keep"
    need_ok=[t for t,_,_ in F["topics"] if not fm.get(f"ok_{t}")]
    need_res=[i["key"] for i in its if fm.get(f"res_{i['key']}") not in ("keep","edit","remove")]
    need_honest=not fm.get("honest")
    if need_ok or need_res or need_honest: return render_approve(token,o,d,G,fm,need_ok,need_res,need_honest)
    d.pop("gcache",None); d["honest_at"]=time.time()
    res=d.setdefault("grounding_resolved",[]); removed=[]
    for i in its:
        ch=fm.get(f"res_{i['key']}"); res.append({"topics":i["topics"],"phrase":i["sentence"],"choice":ch,"at":time.time()})
        if ch=="remove": removed.append(i["sentence"])
    for t,_,_ in F["topics"]:
        a=str(fm.get(f"ans_{t}",d["answers"].get(t,"")))[:4000]
        for snt in removed: a=grounding.remove_sentence(a,snt)
        d["answers"][t]=a
    files=await run_in_threadpool(build_files,token,o,d); c=db(); code=o["save_code"]
    if fm.get("save") or (is_premium(o["tier"]) and o["keep_until"]):
        code=code or secrets.token_urlsafe(9); sm=said_map(o)
        c.execute("insert into saved(code,form,answers,personal,created) values(?,?,?,?,?) on conflict(code) do update set form=excluded.form, answers=excluded.answers, personal=excluded.personal, created=excluded.created",(code,o["form"] or "aa",json.dumps({"answers":d["answers"],"said":{t:sm.get(t,"") for t,_,_ in F["topics"]}}),o["personal"],time.time()))
    d.pop("ticks_confirmed_at",None)   # answers changed: ticks must be checked again
    c.execute("update orders set draft=?, approved_at=?, save_code=? where token=?",(json.dumps(d),time.time(),code,token)); c.commit()
    PLUS.grant(c,get(token))   # Plus: record 'next form included' (and Blue Badge) for this order
    return RedirectResponse(f"/ticks/{token}" if needs_ticks(o) else f"/details/{token}",303)
def tapped(o):
    """(intake, tick states from the taps, 'no difficulty' topic ids) for orders that used the tap questions, else None.
    Recomputed from the stored taps so orders drafted before the 28 Oct fix get the corrected ticks too."""
    I=json.loads(o["intake"] or "{}"); form=o["form"] or "aa"
    if not I.get("rows") or form not in INTAKE.FORMS_V3: return None
    return I,INTAKE.ticks(form,I),INTAKE.no_difficulty(form,I)
def ticks_pending(o):
    return needs_ticks(o) and not json.loads(o["draft"] or "{}").get("ticks_confirmed_at")
@app.get("/ticks/{token}")
def ticks_page(token:str, err:str=""):
    r,o,d=ordered(token)
    if r: return r
    if not o["approved_at"]: return RedirectResponse(f"/approve/{token}",303)
    form=o["form"] or "aa"
    if not needs_ticks(o): return RedirectResponse(f"/details/{token}",303)
    saved=d.get("ticks") if d.get("ticks_confirmed_at") else None; F=FORMS[form]; rows=""; last=None; nset=0
    tp=tapped(o); it=tp[1] if tp else (d.get("intake_ticks") or {})
    props=TICKS.propose_tapped(form,d.get("answers",{}),tp[1],tp[2]) if tp else TICKS.propose(form,d.get("answers",{}))
    for i,x in enumerate(props):
        if not tp and x["field"] in it and it[x["field"]] in x["options"]: x["proposed"]=it[x["field"]]; x["why"]="From what you tapped in the questions."
        cur=saved.get(x["field"],"") if saved is not None else x["proposed"]; nset+=bool(cur)
        q=x["question"].split(":")[0]
        if q!=last: rows+=f"<h2 class=tickq>{esc(q)} <span class=hint>(page {x['page']} of the form)</span></h2>"; last=q
        opts="".join(f'<label><input type=radio name="t_{esc(x["field"])}" value="{esc(s)}" {"checked" if s==cur else ""}> Tick “{esc(TICKS.label(s))}”</label>' for s in x["options"])
        opts+=f'<label><input type=radio name="t_{esc(x["field"])}" value="" {"checked" if not cur else ""}> Leave blank</label>'
        rows+=f"""<div class=trace><p><strong>{esc(x['question'].split(':',1)[1].strip())}</strong></p><p class=hint>{esc(x['why'])}</p><div class=resopts>{opts}</div></div>"""
    return page(prog(5,"Tick boxes")+f"""<h1>Check the tick boxes on your {esc(F['form'])}</h1><p class=one>{f"We have already set {nset} tick boxes from your answers, so you don't need to answer anything again. Open the list if you want to check or change one." if it else "These are the tick boxes we will mark on the official form. We have suggested each one from the answers you approved. Change anything that isn't right. We only tick what you confirm here."}</p>
{f'<div class=warning>{esc(err)}</div>' if err else ''}<form method=post action=/ticks/{token}>{f'<details class=tickall><summary>See or change the tick boxes</summary>{rows}</details>' if it else rows}
<p class=small>{'We never tick the consent or declaration boxes, and never sign anything. You do those yourself.' if is_wf(o) else 'We never tick the consent, declaration, bank or "signing for someone else" boxes. You do those yourself.'}</p>
<label class=cb><input type=checkbox name=confirm required><span>I have checked every tick box above. They are true.</span></label>
<button class="btn btn-big">Confirm tick boxes</button></form>""","Check the tick boxes")
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
def documents_page(token:str, req:Request=None):
    o=ready(token); _acct_req.set(req)
    if FRAUD.held(o): return _held_redirect(o)
    if not o["approved_at"]: return RedirectResponse(f"/approve/{token}",303)
    if ticks_pending(o): return RedirectResponse(f"/ticks/{token}",303)
    if not o["details_at"]: return RedirectResponse(f"/details/{token}",303)
    F=FORMS[o["form"] or "aa"]; lab={'assessment-briefing.html':'Assessment and phone-call briefing','supporting-letters.html':'Request letters for your GP, carer, school or family','reconsideration-letter.txt':'Your reconsideration letter, ready to sign and send','PIP-extra-sheets.pdf':'Printable extra sheets, one per question (PDF), to send with your form','answers.html':'Your approved answers, checklist and letters','AA1-filled.pdf':'Official AA1 form, filled in (PDF)','DLA1A-filled.pdf':'Official DLA1A form, filled in (PDF)','AccessToWork-answers.docx':'Your answers as a Word document (DOCX), in application order','Note-for-supporter.pdf':'A note for the person who writes the statement box (we leave that box for them)'}
    files=pack_files(o)
    if is_wf(o): files=[f for f in files if f!="answers.html"]+["answers.html"]
    gone=f"<div class=panel><p>Your National Insurance number and bank details have been deleted from our system for safety. Need another copy with them filled in? <a href=/details/{token}>Type them again</a>.</p></div>" if is_wf(o) and not SECURE.has(token) else ""
    dl=json.loads(o["deadline"] or "{}"); res=deadlines.compute(o["form"] or "aa",dl.get("how","phone"),dl.get("requested"),dl.get("received")) if dl.get("requested") else None
    saved=f"<div class=panel><p><strong>Your save code: <code>{o['save_code']}</code></strong><br>Keep it safe. {'Keep a copy of your answers too. They will help when your grant is due for renewal (you can apply to renew 12 weeks before it ends).' if o['form']=='atw' else "Use it at <a href=/review>/review</a> when your review form arrives, and we'll only ask what has changed."}</p></div>" if o["save_code"] else ""
    if is_premium(o["tier"]) and o["save_code"]:
        saved+=plus_panel(o)
    main=next((x for x in (F.get("pdf_out"),"PIP-extra-sheets.pdf","AccessToWork-answers.docx") if x and x in files),files[0] if files else None)
    mlab={"PIP-extra-sheets.pdf":"Download your extra sheets (PDF)","AccessToWork-answers.docx":"Download your answers (Word)","answers.html":"Download your answers"}.get(main,"Download your form (PDF)")
    others="".join(f'<li><span>{lab.get(f,f)}</span><a href="/download/{token}/{f}" download>Download</a></li>' for f in files if f!=main)
    when=f"<p class=deadline>Send it back by <strong>{datetime_fmt(res['deadline'])}</strong></p>" if res and res.get('deadline') else ''
    form=o["form"] or "aa"
    nxt=ATW_NEXT if form=="atw" else f"<h2>What to do next</h2>{next_steps(form,files,hand_details(o))}"
    guide="" if form=="atw" else more("Full print, sign and post guide",PSP.html_section(form,filled=(F.get('pdf_out') in files),hand_details=hand_details(o),h="h3"))
    extras=(f'<h3>Your other documents</h3><ul class=also>{others}</ul>' if others else '')+guide+f"{saved}{account_box(o)}{bb_addon_box(o)}"
    return page(prog(5,"Download")+f"""<div class=ready><h1>{"Your answers are ready" if form=="atw" else "Your form is ready"}</h1><p>You approved every answer.</p></div>
{f'<a class="btn btn-big" href="/download/{token}/{main}" download>{mlab}</a>' if main else ''}{when}{gone}
{nxt}
{f'<div class=extras><h2>For later</h2>{extras}</div>' if extras.strip() else ''}
<p class=small>We delete everything 90 days after your order. <a href=/delete/{token}>Delete my information now</a>.</p>""","Your documents")
def next_steps(form,files,hand):
    """Short numbered print-sign-post checklist for the documents page. The full guide (psp.py) is behind 'More info'."""
    handl=" Also write in the National Insurance number and bank details." if hand else ""
    sup=(" Also print the supporter note and give it to the person who writes the statement. They fill in that part themselves." if "Note-for-supporter.pdf" in files else "")
    if form=="aa": st=[("Print it","at actual size (100%) on plain A4."),("Sign and date by hand in black ink",f"at question 20 (page 9) and question 64 (page 30).{handl}"),("Post it",f"to {PSP.AA_FREEPOST}. No stamp needed.")]
    elif form=="dla": st=[("Print it","at actual size (100%) on plain A4."),("Sign and date by hand in black ink",f"at question 39 (page 12) and the Declaration (page 38).{handl}"),("Post it",f"in DWP's envelope, or to {PSP.DLA_FREEPOST}. No stamp needed.")]
    elif form in ("pip","pipr"):
        code="PIP2" if form=="pip" else "AR1"
        st=[("Copy your answers",f"onto the paper {code} DWP sent you, in black ink, and print the extra sheets."),("Sign and date by hand in black ink","in the Declaration." if form=="pip" else "in Section 1 (Read and sign) and Section 3."),("Post it",f"with the extra sheets, in the envelope DWP sent you.")]
    else: return ""
    li="".join(f"<li><strong>{esc(t)}</strong> {esc(x)}{sup if j==0 else ''}</li>" for j,(t,x) in enumerate(st))   # always 4 steps: the supporter note rides on step 1
    return f"<ol class=howit>{li}<li><strong>Keep a copy</strong> and note the date you posted it.</li></ol>"
ATW_NEXT=f"""<h2>What to do next</h2><ol class=steps><li><strong>Read it once more</strong> and change anything that isn't right.</li><li><strong>Apply online or by phone</strong> at GOV.UK (search 'Access to Work apply'), or call {facts.v('atw_helpline')} (Mon–Fri 9am–5pm). Paste or read out each answer.</li><li><strong>Add your own details</strong>: workplace address, workplace contact, NI number (or UTR if self-employed).</li><li><strong>Disagree with the decision?</strong> Call the helpline and ask for it to be reconsidered.</li></ol>"""
NEXT_LABEL={"aa":"Next Attendance Allowance form","dla":"Your child's DLA renewal form","pip":"Your PIP review form","pipr":"Your next PIP review form"}
def plus_panel(o):
    """What's included with this Plus order, and whether the included next form has been used."""
    form=o["form"] or "aa"; c=db(); st=PLUS.status(c,o,PLUS.NEXT)
    nxt=(f"<p><strong>{esc(NEXT_LABEL.get(form,'Your next form'))}: included.</strong> When the renewal or review form arrives{', or if you want to ask for the higher rate' if form=='aa' else ''}, <a href=\"/review/{o['save_code']}\">start it here</a>. We fill it in from your saved answers and only ask what has changed. No charge.</p>" if st=="available"
         else f"<p><strong>{esc(NEXT_LABEL.get(form,'Your next form'))}:</strong> already used. A new form is £99.</p>" if st=="used" else "")
    post=('<p>We will print your pack and post it to you to sign'+(', with a Freepost return envelope' if form in ('aa','dla') else '')+'.</p>') if o['post_pack'] else ''
    return f"""<div class=panel><h2 class=h3>Included with Done for you Plus</h2><p><strong>Turned down?</strong> You usually have 1 month from the date on the decision letter to ask DWP to look again. <a href="/appeal/{o['save_code']}">Send us the decision letter</a> and we prepare your reconsideration letter from your answers, for you to check, sign and send. No charge.</p>
{nxt}{post}<p class=hint>{esc(PLUS.FOOT)}</p></div>"""
NEXT_USED="<h1>Your included form has been used</h1><p class=lead>Done for you Plus includes one next form for the same person and benefit, and it has already been used. You can start a new form for £99.</p><p><a class=btn href=/>Start a new form</a></p>"
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
    po=plus_order(code)
    if po and PLUS.status(db(),po,PLUS.NEXT)!="available": return page(NEXT_USED,"Already used")
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
    token=orders.new_token(); c=db(); po=plus_order(code)
    if po and not PLUS.redeem(c,po,PLUS.NEXT,token,target): return page(NEXT_USED,"Already used")   # one next form per Plus order, same benefit
    c.execute("insert into orders(token,tier,status,created,form,consent_at,draft,personal,review_of) values(?,?,?,?,?,?,?,?,?)",(token,("199" if po else default_tier(target)) if target!="atw" else "49","paid",time.time(),target,time.time(),json.dumps(d),s["personal"] or "{}",code)); c.commit()
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
# ---------------- Customer accounts (off unless ACCOUNTS_ENABLED=1; see accounts.py) ----------------
import contextvars as _cv
_acct_req=_cv.ContextVar("_acct_req",default=None)
def _https(): return PUBLIC.startswith("https://")
def _me(req):
    if not ACCT.ENABLED or req is None: return None
    return ACCT.session_account(db(),req.cookies.get(ACCT.COOKIE,""))
def _signed_in(resp,sid):
    resp.set_cookie(ACCT.COOKIE,sid,max_age=ACCT.SESSION_DAYS*86400,httponly=True,secure=_https(),samesite="lax",path="/"); return resp
def _need_acct():
    if not ACCT.ENABLED: raise HTTPException(404)
def account_box(o):
    """Documents page: one tap to save the answers to an account with the order's email."""
    if not ACCT.ENABLED or o["status"]!="paid" or (o["form"] or "aa") not in ("aa","dla","pip","pipr","atw"): return ""
    me=_me(_acct_req.get())
    if o["account_id"] and me and me["id"]==o["account_id"]:
        return "<div class=panel><h2 class=h3>Saved to your account</h2><p>Your answers are saved, so you won't be asked them again for a renewal or another form. <a href=/account>Go to your account</a>.</p></div>"
    em=ACCT.norm_email(o["email"] or "")
    if not em: return ""
    return f"""<div class=panel><h2 class=h3>Save your answers for next time</h2><p>Renewing, or filling in another form? Save your answers to an account with <strong>{esc(em)}</strong> and you won't be asked them again. There is no password: we email you a sign-in link.</p>
<p class=hint>We never keep your National Insurance number or bank details. You'd type those again.</p>
<form method=post action=/account/save/{o['token']}><button class="btn btn-2">Save my answers</button></form></div>"""
CHECK_EMAIL="<h1>Check your email</h1><p class=lead>If there's an account for that email address, we've sent it a sign-in link. It works once and stops working after {m} minutes.</p><p>No email? Check your junk folder, or <a href=/account/signin>ask for another link</a>.</p>"
SAVED_BOX="<div class=panel><h2 class=h3>Saved to your account</h2><p>Your answers are saved, so you won't be asked them again for a renewal or another form. We've emailed you a sign-in link for next time.</p><p><a href=/account>Go to your account</a></p></div>"
SAVED_EXISTING="<h1>Saved to your account</h1><p class=lead>There's already an account for this email address, so we've added this order and its answers to it.</p><p>To see them, sign in with the link we've just emailed you. It works once and stops working after {m} minutes.</p><p><a href=/documents/{t}>Back to your documents</a></p>"
LINK_GONE="<h1>This link has expired</h1><p class=lead>Sign-in links work once and stop working after {m} minutes.</p><p><a class=btn href=/account/signin>Email me a new link</a></p>"
TOO_MANY="<h1>Please wait a few minutes</h1><p class=lead>We've sent a few sign-in links already. Check your inbox and junk folder, or try again in 15 minutes.</p>"
def _acct_page(body,title): return page(body,title,minimal=True)
def _send(to,mail):
    try: mailer.send(to,*mail); return True
    except Exception as e: print("account mail failed:",type(e).__name__); return False
def _link_url(c,email,ip,aid):
    t=ACCT.new_link(c,email,ip,aid); return f"{PUBLIC}/account/link/{t}" if t else None
@app.post("/account/save/{token}")
def account_save(token:str, req:Request):
    _need_acct(); o=get(token); c=db()
    if o["status"]!="paid" or not o["approved_at"]: raise HTTPException(400)
    me=_me(req); em=ACCT.norm_email(o["email"] or "")
    if me: acct=me
    else:
        if not em: raise HTTPException(400)
        acct=ACCT.by_email(c,em)
        if acct:   # someone else may hold this order link: add the order, but only a sign-in link opens the account
            ACCT.link_order(c,acct["id"],token); ACCT.save(c,acct["id"],get(token))
            if ACCT.can_send(c,em,client_ip(req)):
                u=_link_url(c,em,client_ip(req),acct["id"]); _send(em,ACCT.added_email(BRAND,u))
            return _acct_page(SAVED_EXISTING.format(m=ACCT.LINK_MIN,t=token),"Saved to your account")
        acct=ACCT.create(c,em)
        _send(em,ACCT.welcome_email(BRAND,f"{PUBLIC}/account/signin"))
    ACCT.link_order(c,acct["id"],token); ACCT.save(c,acct["id"],get(token))
    r=RedirectResponse(f"/documents/{token}#account",303)
    return r if me else _signed_in(r,ACCT.new_session(c,acct["id"]))
@app.get("/account/signin")
def account_signin_page(err:str=""):
    _need_acct()
    e="<p class=error role=alert>Please type the email address you used when you paid.</p>" if err else ""
    return _acct_page(f"""<h1>Sign in to your account</h1><p class=lead>Type the email address you used when you paid. We'll email you a link to sign in. There is no password.</p>{e}
<form method=post action=/account/signin><div class=field><label class=q for=em>Email address</label><input id=em type=email name=email autocomplete=email required></div><button class=btn>Email me a sign-in link</button></form>""","Sign in")
@app.post("/account/signin")
def account_signin(req:Request, email:str=Form("")):
    _need_acct(); em=ACCT.norm_email(email)
    if not em: return RedirectResponse("/account/signin?err=1",303)
    c=db(); ip=client_ip(req)
    if not ACCT.can_send(c,em,ip): return _acct_page(TOO_MANY,"Please wait")
    a=ACCT.by_email(c,em); u=_link_url(c,em,ip,a["id"] if a else None)
    if u: _send(em,ACCT.link_email(BRAND,u))
    return _acct_page(CHECK_EMAIL.format(m=ACCT.LINK_MIN),"Check your email")   # same page whether or not there's an account
@app.get("/account/link/{t}")
def account_link_page(t:str):
    """A button, not an automatic sign-in, so email link scanners can't use up the link."""
    _need_acct()
    if not ACCT.link_ok(db(),t): return _acct_page(LINK_GONE.format(m=ACCT.LINK_MIN),"Link expired")
    return _acct_page(f"<h1>Sign in to your account</h1><form method=post action=/account/link/{esc(t)}><button class=btn>Sign in</button></form>","Sign in")
@app.post("/account/link/{t}")
def account_link(t:str):
    _need_acct(); c=db(); aid=ACCT.use_link(c,t)
    if not aid or not ACCT.by_id(c,aid): return _acct_page(LINK_GONE.format(m=ACCT.LINK_MIN),"Link expired")
    return _signed_in(RedirectResponse("/account",303),ACCT.new_session(c,aid))
ACCT_NEXT={"aa":("aa",),"dla":("dla",),"pip":("pip","pipr"),"pipr":("pipr","pip"),"atw":("atw",)}
def _when(t): return time.strftime("%d %B %Y",time.localtime(t or 0)).lstrip("0")
@app.get("/account")
def account_home(req:Request):
    _need_acct(); me=_me(req)
    if not me: return RedirectResponse("/account/signin",303)
    c=db(); rows=ACCT.orders_of(c,me["id"]); sv=ACCT.saved(c,me["id"])
    ol="".join(f"<li><strong>{esc(FORMS.get(o['form'] or 'aa',{}).get('name','Form'))}</strong>, {_when(o['created'])}"+(f" · <a href=/documents/{o['token']}>Your documents</a>" if o["status"]=="paid" and o["approved_at"] else "")+"</li>" for o in rows) or "<li>No orders yet.</li>"
    def card(s):
        f=s["form"]; nm=esc(FORMS.get(f,{}).get("name",f))
        starts="".join(f"<form method=post action=/account/start style='display:inline'><input type=hidden name=src value={f}><input type=hidden name=form value={t}><button class=btn>{'Start a new '+nm+' form' if t==f else 'Start a '+esc(FORMS[t]['name'])+' form'}</button></form> " for t in ACCT_NEXT.get(f,(f,)) if t in FORMS)
        return f"""<div class=panel><h3>{nm}</h3><p>Saved {_when(s['saved_at'])}. Your answers are filled in for you to check and change.</p>{starts}
<form method=post action=/account/forget/{f} onsubmit="return confirm('Delete these saved answers?')"><button class=linkbtn>Delete these saved answers</button></form></div>"""
    cards="".join(card(s) for s in sv) or "<p>No saved answers.</p>"
    return _acct_page(f"""<h1>Your account</h1><p class=lead>Signed in as <strong>{esc(me['email'])}</strong>.</p>
<h2>Saved answers</h2>{cards}<p class=hint>We never keep your National Insurance number or bank details. You'd type those again.</p>
<h2>Your orders</h2><ul>{ol}</ul>
<form method=post action=/account/signout><button class="btn btn-2">Sign out</button></form>
<h2>Delete your account</h2><p>This deletes your account, every saved answer in it and every order in it, with their documents, straight away. Download anything you still need first.</p>
<form method=post action=/account/delete onsubmit="return confirm('Delete your account, all saved answers and all your orders?')"><label class=cb><input type=checkbox name=sure value=1 required><span>Yes, delete my account</span></label><button class="btn btn-warn">Delete my account</button></form>
<p class=small>Accounts not used for 3 years are deleted automatically.</p>""","Your account")
@app.post("/account/start")
def account_start(req:Request, src:str=Form(""), form:str=Form("")):
    _need_acct(); me=_me(req)
    if not me: return RedirectResponse("/account/signin",303)
    c=db(); s=ACCT.saved_for(c,me["id"],src)
    if not s or form not in ACCT_NEXT.get(src,()) or form not in FORMS: raise HTTPException(400)
    I,P=ACCT.carry(json.loads(s["data"] or "{}"),src,form)
    tier=default_tier(form) if form!="atw" else "49"; token=orders.new_token()
    c.execute("insert into orders(token,tier,status,created,form,ip,intake,personal,email,account_id) values(?,?,?,?,?,?,?,?,?,?)",
              (token,tier,"free",time.time(),form,client_ip(req),json.dumps(I) if I else None,json.dumps(P),me["email"],me["id"])); c.commit()
    ACCT.touch(c,me["id"]); return RedirectResponse(f"/start/{token}",303)
@app.post("/account/forget/{form}")
def account_forget(form:str, req:Request):
    _need_acct(); me=_me(req)
    if not me: return RedirectResponse("/account/signin",303)
    ACCT.forget(db(),me["id"],form); return RedirectResponse("/account",303)
@app.post("/account/signout")
def account_signout(req:Request):
    _need_acct(); ACCT.end_session(db(),req.cookies.get(ACCT.COOKIE,""))
    r=_acct_page("<h1>You're signed out</h1><p><a href=/account/signin>Sign in again</a></p>","Signed out"); r.delete_cookie(ACCT.COOKIE,path="/"); return r
@app.post("/account/delete")
def account_delete(req:Request, sure:str=Form("")):
    _need_acct(); me=_me(req)
    if not me: return RedirectResponse("/account/signin",303)
    if sure!="1": return RedirectResponse("/account",303)
    c=db()
    for o in ACCT.orders_of(c,me["id"]): orders.erase(c,OUT,o["token"]); SECURE.wipe(o["token"])   # every order in it, with its documents
    ACCT.delete_account(c,me["id"])
    r=_acct_page("<h1>Your account is deleted</h1><p class=lead>Your account, every saved answer in it and every order in it have been deleted.</p>","Account deleted"); r.delete_cookie(ACCT.COOKIE,path="/"); return r
@app.get("/healthz")
def healthz(): return {"ok":True}
@app.post("/cron/retention")
def cron_retention(req:Request):
    got=req.headers.get("x-cron-secret","")
    if not CRON_SECRET or not hmac.compare_digest(got,CRON_SECRET): raise HTTPException(403)
    return {"ok":True,"purged":orders.purge(db(),OUT),"private":SECURE.purge(),"accounts":ACCT.purge(db())}
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
            try: print("retention purge",orders.purge(db(),OUT),SECURE.purge())
            except Exception as e: print("retention error",e)
            await asyncio.sleep(86400)
    asyncio.create_task(loop())

# ---------------- Blue Badge answers (add-on £15 after an AA / DLA / PIP order, or £29 on its own) ----------------
BB_ADDON_LINE="<p class=hint>Applying for a Blue Badge too? After you pay, you can add Blue Badge application answers for £15, made from the answers you give here.</p>"
BB_TRUST="<div class=trust><h2 class=h3>Our promise</h2><ul class=ticks><li><strong>Fixed price.</strong> You pay this once. No subscription, nothing more to pay us.</li><li><strong>Only your words.</strong> Every answer is built from what you told us. You check and change anything before you use it.</li><li><strong>You stay in control.</strong> You apply yourself, and we never contact your council for you.</li><li><strong>Yours to keep.</strong> Download your answers and checklist to use now, or later if you need to ask the council to look again.</li></ul></div>"
BB_ITEMS=["Answers for each health and walking question on the online Blue Badge application, ready to copy and paste","A hidden-disability write-up in your own words, if journeys are hard for reasons other than walking","A checklist of what to upload, and the photo and proof you need","If the council says no: a letter asking them to look at the decision again","You check every word. You apply yourself"]
BB_BULLETS=["Answers for each health and walking question, ready to copy and paste","A checklist of what to upload, and the photo and proof you need","A letter asking the council to look again, if they say no","You check every word. You apply yourself"]
def bb_summary(pv=""):
    n,p,_=FORMS["bb"]["tiers"][BB.SOLO_TIER]
    return page(bbprog(1)+pv+f"""<p class=caption>Blue Badge application</p><h1>Your package</h1><p class=one>Nothing to pay now. You pay once, at the end, after the questions. About 3 minutes, mostly taps.</p>
<div class=pkgs><div class="pkg one"><h2>{esc(n)}</h2><p class=pr>£{p//100} <small>one-off</small></p><ul class=ticks>{''.join(f'<li>{esc(i)}</li>' for i in BB_BULLETS)}</ul>
<form method=post action=/checkout><input type=hidden name=form value=bb><input type=hidden name=tier value={BB.SOLO_TIER}><button class="btn btn-big">Start my answers</button></form></div></div>
{more("Everything that's included",f"<ul class=ticks>{''.join(f'<li>{esc(i)}</li>' for i in BB_ITEMS)}</ul>")}
<p class=hint>{esc(BB.NOT_ELIG)}</p><p class=hint>Already ordered an Attendance Allowance, DLA or PIP form with us? Add Blue Badge answers for £15 from your documents page instead.</p><p class=change><a href="/">Choose a different form</a></p>""","Blue Badge answers",minimal=True)
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
<div class=total><span>{esc(n)}</span><strong>{'Included' if p==0 else f'£{p//100}'}</strong></div>
<form method=post action=/pay/{token}><label class=cb><input type=checkbox name=waive required><span>Please prepare my answers straight away. I understand that once you start I lose my 14-day right to cancel.</span></label>
<button class="btn btn-wide">{'Get my answers (included with Done for you Plus)' if p==0 else f'Pay £{p//100} to get your answers'}</button></form>{BB_TRUST}<p class=change><a href="/bb/{token}">Change my answers</a></p>
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
    tier=BB_INCLUDED if PLUS.redeem(c,p,PLUS.BB,token,p["form"] or "aa") else BB.ADDON_TIER   # included once with Plus, else £15
    c.execute("insert into orders(token,tier,status,created,form,ip,review_of,consent_at,intake,email) values(?,?,?,?,?,?,?,?,?,?)",(token,tier,"free",time.time(),"bb",p["ip"],parent,time.time(),json.dumps(d),p["email"])); c.commit()
    return RedirectResponse(f"/bb/{token}",303)
BB_INCLUDED="0"
def bb_addon_box(o):
    if (o["form"] or "aa") not in BB.PARENT_FORMS: return ""
    if PLUS.status(db(),o,PLUS.BB)=="available":
        return f"""<div class=panel><h2 class=h3>Applying for a Blue Badge too?</h2><p>Included with Done for you Plus: we turn the answers you've already given us into answers for the online Blue Badge application, with a checklist of what to upload. No charge.</p>
<form method=post action=/bb/addon/{o['token']}><button class="btn btn-2">Get my Blue Badge answers</button></form><p class=hint>{esc(BB.NOT_ELIG)}</p></div>"""
    return f"""<div class=panel><h2 class=h3>Applying for a Blue Badge too?</h2><p>We can turn the answers you've already given us into answers for the online Blue Badge application, with a checklist of what to upload. £15, and you only pay once you've checked your answers.</p>
<form method=post action=/bb/addon/{o['token']}><button class="btn btn-2">Add Blue Badge answers, £15</button></form><p class=hint>{esc(BB.NOT_ELIG)}</p></div>"""

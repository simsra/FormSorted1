"""Untitled UI rebuild of formsorted.com (Simon, 16 Nov 2026). TEST COPY: python3 site_build.py <live_mirror_dir> <out_dir>
Every page gets a fresh shell: a minimal top bar (logo + a few text links), the page's own content in an Untitled UI content layout,
and a new footer that keeps the same disclaimer words and links. The old stylesheet, navy header, 'Independent' strip, hero,
stepper and cards are gone. The homepage is a plain landing page (16 Nov steering: 'we need a clear landing page'): headline, Start your form,
form cards, How it works, price, FAQ. No chat on the site: the FormSorted assistant lives in the app journey. Guide, Terms and Privacy text is unchanged."""
import re, os, sys, shutil, hashlib, json
from html import escape as esc
SRC,OUT=sys.argv[1],sys.argv[2]
HERE=os.path.dirname(os.path.abspath(__file__))
APPDIR=os.getenv("APP_DIR","/workspace/butter/apps/untitled_wt"); sys.path.insert(0,APPDIR)
import uikit as UI
APP="https://app.formsorted.com"
FORMS=[("aa","Attendance Allowance","/attendance-allowance-form-help","heart","c2","For people over State Pension age who need help with care, day or night."),
       ("pip","PIP","/pip-form-help","user","c1","For people aged 16 to State Pension age with a health condition or disability."),
       ("pipr","PIP review","/pip-review-form-help","fcheck","c3","Already get PIP and DWP has sent a review form (AR1)."),
       ("dla","DLA for a child","/dla-form-help","baby","c2","For a child under 16 who needs more care or watching than other children their age."),
       ("bb","Blue Badge","/blue-badge-help","car","c3","For a parking badge if walking or getting around is hard."),
       ("atw","Access to Work","/access-to-work-help","brief","c4","For help at work, for people in or starting a job.")]
NOT_SURE=[("Is it for a child under 16?","dla"),("Are they State Pension age or over, and need help with care?","aa"),
 ("Aged 16 to State Pension age, with a health condition or disability?","pip"),("Already get PIP, and got a review form?","pipr"),("Need a parking badge?","bb")]
ROUTES=[("bb",["blue badge","parking","badge"]),("pipr",["ar1","pip review","review form","renew"]),("dla",["dla","child","son","daughter","kid","baby","under 16"]),
 ("atw",["access to work","at work","my job","employer"]),("pip",["pip","pip2","personal independence"]),("aa",["attendance","aa1","aa","pension age","elderly","older","care at home","help with care","mum","dad","gran","nan","grandma","grandad"])]
F={k:(n,u,ic,c,w) for k,n,u,ic,c,w in FORMS}
def bot(h): return f'<div class="turn bot new">{UI.ORB}<div class="bub">{h}</div></div>'
def me(t): return f'<div class="turn me"><div class="bub">{t}</div></div>'
def chip(k,label=None): n,u,ic,c,w=F[k]; return f'<a class="qchip {c}" href="{APP}/?form={k}">{UI.icon(ic,16)}{esc(label or n)}</a>'
if os.path.exists(OUT): shutil.rmtree(OUT)
shutil.copytree(SRC,OUT)
for f in ("styles.css",): 
    if os.path.exists(os.path.join(OUT,f)): os.remove(os.path.join(OUT,f))   # the old template stylesheet is not served any more
shutil.rmtree(os.path.join(OUT,"fonts"),ignore_errors=True)
open(os.path.join(OUT,"ui.css"),"w").write(open(os.path.join(APPDIR,"static","ui.css")).read()+"\n"+open(os.path.join(HERE,"site.css")).read())
for f in ("chat.js","inter-var.woff2","inter-OFL.txt"): shutil.copy(os.path.join(APPDIR,"static",f),os.path.join(OUT,f))
V={f:hashlib.sha256(open(os.path.join(OUT,f),"rb").read()).hexdigest()[:10] for f in ("ui.css","chat.js")}
LINKS=[("Attendance Allowance","/attendance-allowance-form-help"),("PIP","/pip-form-help"),("Child DLA","/dla-form-help"),("Access to Work","/access-to-work-help"),("Help","/#faq")]
def topbar(cur):
    la="".join(f'<a href="{u}"{" aria-current=page" if u==cur else ""}>{t}</a>' for t,u in LINKS)
    return (f'<header class="tbar"><div class="tin">{UI.logo("/")}<nav class="tlinks" aria-label="Main">{la}</nav>'
            f'<details class="tmenu"><summary aria-label="Menu">{UI.icon("chev",20)}<span>Menu</span></summary><nav aria-label="Main">{la}</nav></details></div></header>')
def footer(old):
    """Same footer words as before (disclaimer, services, Privacy/Terms/Contact), laid out as an Untitled UI footer."""
    ps=re.findall(r'<p>(.*?)</p>',old,flags=re.S)
    text=[p for p in ps if not p.startswith("Services:") and '<a href="/privacy' not in p and 'href="privacy' not in p]
    serv=next((p for p in ps if p.startswith("Services:")),"")
    sl="".join(f'<li>{a}</li>' for a in re.findall(r'<a [^>]+>[^<]+</a>',serv))
    legal=next((p for p in ps if 'privacy' in p and 'terms' in p),'')
    ll="".join(f'<li>{a}</li>' for a in re.findall(r'<a [^>]+>[^<]+</a>',legal))
    return (f'<footer class="sfoot"><div class="fin"><div class="fbrand">{UI.logo("/")}{"".join(f"<p>{p}</p>" for p in text)}</div>'
            + (f'<div class="fcol"><h2>Forms</h2><ul>{sl}</ul></div>' if sl else '')
            + f'<div class="fcol"><h2>Legal</h2><ul>{ll}</ul></div></div></footer>')
def stepbadge(s):
    """The old 5-step bar on guide pages becomes one small badge: 'Step 2 of 5 · Choose your package'."""
    m=re.search(r'<p class="stepnow">Step (\d) of 5: <strong>([^<]+)</strong></p>',s)
    s=re.sub(r'<nav aria-label="Your progress">.*?</nav><p class="stepnow">.*?</p>','',s,flags=re.S)
    return s,(f'<p class="sbadge"><span class="sdotb"></span>Step {m.group(1)} of 5 · {m.group(2)}</p>' if m else "")
def faq_json(s):
    out=[]
    for q,a in re.findall(r'<details class="(?:more|qa)"><summary>([^<]+)</summary>(.*?)</details>',s,flags=re.S):
        t=re.sub(r'<[^>]+>',' ',a); t=re.sub(r'\s+',' ',t).strip()
        if t and q!="Questions people ask": out.append({"q":q.replace("&#x27;","'"),"a":t.replace("&#x27;","'").replace("&amp;","&")})
    return json.dumps(out).replace("</","<\\/")
def landing():
    """formsorted.com home (Simon 16 Nov 2026: 'we need a clear landing page'). No chat here: the FormSorted assistant lives in the app journey."""
    cards="".join(f'<li><a class="fcard" href="{APP}/?form={k}"><span class="otile">{UI.icon(ic,20)}</span><span class="ft">{n}</span><span class="fw">{w}</span><span class="fl">Start {UI.icon("right",16)}</span></a></li>' for k,n,u,ic,c,w in FORMS)
    ns="".join(f'<li><span>{q}</span> <a class="qchip {F[k][3]}" href="{APP}/?form={k}">{UI.icon(F[k][2],16)}{esc(F[k][0])}</a></li>' for q,k in NOT_SURE)
    cards+=(f'<li class="fnot"><details class="fcard notsure"><summary><span class="otile">{UI.icon("question",20)}</span><span class="ft">Not sure which form?</span><span class="fw">Answer yes to one of these.</span></summary>'
            f'<ul class="notsure">{ns}</ul><p class="hint">Still not sure? The form\'s name is on the first page of the letter or form DWP sent you.</p></details></li>')
    steps=[("chat","Answer simple questions","Mostly taps, one question at a time. Stuck? Ask the FormSorted assistant any time."),
           ("edit","We write every answer in plain English","Your whole form, completed in full, only from what you told us."),
           ("pen","Check it, sign it, send it yourself","Change anything you like. You stay in control of your form.")]
    st="".join(f'<li><span class="snum">{i+1}</span><span class="otile">{UI.icon(ic,20)}</span><h3>{t}</h3><p>{d}</p></li>' for i,(ic,t,d) in enumerate(steps))
    return (f'<section class="lhero" aria-labelledby="hh"><div class="lin">'
      f'<p class="sbadge"><span class="sdotb"></span>England and Wales</p>'
      f'<h1 id="hh">Your disability benefit form, completed in full in plain English</h1>'
      f'<p class="lsub">Answer simple questions and we complete your whole form from your answers. You check it, sign it and send it yourself.</p>'
      f'<div class="lcta"><a class="btn btn-start lgo" href="{APP}/">Start your form {UI.icon("right",20)}</a><p class="lpay">{UI.icon("lock",16)} £99 per form · Pay only at the end</p></div></div></section>'
      f'<section class="sec" aria-labelledby="fh"><div class="sechead"><p class="eyebrow">Choose your form</p><h2 id="fh">Which form do you need?</h2></div><ul class="fcards">{cards}</ul></section>'
      f'<section class="sec" aria-labelledby="hw"><div class="sechead"><p class="eyebrow">How it works</p><h2 id="hw">Three simple steps</h2></div><ol class="lsteps">{st}</ol></section>'
      f'<section class="sec" aria-labelledby="ph"><div class="sechead"><p class="eyebrow">Price</p><h2 id="ph">One fixed price. Pay only at the end.</h2><p class="supp">No success fee. Nothing to pay until you have answered the questions.</p></div>'
      f'<div class="lprice"><div class="pcard"><p class="pn">Done for you</p><p class="pp">£99 <span>per form</span></p><p class="pw">Attendance Allowance, PIP, PIP review or DLA for a child. Your official form, completed in full.</p></div>'
      f'<div class="pcard plus"><p class="pn">Done for you Plus</p><p class="pp">£199 <span>per form</span></p><p class="pw">Everything in Done for you, plus an assessment briefing, request letters for your GP, carer, school or family, and one next form for the same benefit.</p></div></div>'
      f'<p class="hint pother">Blue Badge answers £29. Access to Work from £49. <a href="/terms.html">Full prices in our Terms</a>.</p></section>')
def guides():
    li="".join(f'<li><a class="gcard" href="{u}"><span class="otile">{UI.icon(ic,20)}</span><span class="gt">{n}</span><span class="gw">{w}</span><span class="gl">Read about it {UI.icon("right",16)}</span></a></li>' for k,n,u,ic,c,w in FORMS)
    return f'<section class="sec" aria-labelledby="gh"><div class="sechead"><p class="eyebrow">Guides</p><h2 id="gh">Read about each form</h2></div><ul class="gcards">{li}</ul></section>'
n=0
for root,_,files in os.walk(OUT):
    for fn in files:
        if not fn.endswith(".html"): continue
        p=os.path.join(root,fn); s=open(p).read(); rel="/"+os.path.relpath(p,OUT)
        head=re.search(r'<head>(.*?)</head>',s,flags=re.S).group(1)
        head=re.sub(r'<link rel="stylesheet" href="/?styles\.css[^"]*">','',head)
        head=head.replace('<meta name="theme-color" content="#0b1432">','<meta name="theme-color" content="#ffffff">')
        if 'theme-color' not in head: head+='<meta name="theme-color" content="#ffffff">'
        head+=f'<link rel="preload" href="/inter-var.woff2" as="font" type="font/woff2" crossorigin><link rel="stylesheet" href="/ui.css?v={V["ui.css"]}">'
        m=re.search(r'<main id="main"><div class="wrap">(.*)</div></main>',s,flags=re.S); body=m.group(1)
        oldf=re.search(r'<footer class="ftr">(.*?)</footer>',s,flags=re.S); oldf=oldf.group(1) if oldf else ""
        tail=s[s.index('</footer>')+9:s.rindex('</body>')] if '</footer>' in s else ""
        body=re.sub(r'<svg class="dots".*?</svg>','',body,flags=re.S)
        body,badge=stepbadge(body)
        kind="legal" if fn in ("terms.html","privacy.html") else "home" if rel=="/index.html" else "page"
        if kind=="home":
            b=body.index('<h2 class="h3" id="faq">')
            rest=body[b:]
            nh=rest.index('<section class="needhelp"')
            faq=rest[:nh].replace('<h2 class="h3" id="faq">Questions people ask</h2>','')
            needhelp=rest[nh:]
            body=(landing()+f'<section class="sec faqsec" aria-labelledby="faq"><div class="sechead"><p class="eyebrow">Help</p><h2 id="faq">Questions people ask</h2><p class="supp">Quick answers about how FormSorted works.</p></div><div class="faqlist">{faq}</div></section>'
                  +f'<section class="sec">{needhelp}</section>')
            main=f'<main id="main" class="smain home">{body}</main>'
        else:
            # the first heading block becomes the Untitled UI page header
            crumb=re.search(r'^\s*<p class="crumb">.*?</p>',body,flags=re.S)
            if crumb: body=body[crumb.end():]
            cr=(crumb.group(0).replace(" › ",f' {UI.icon("chev",16)} ') if crumb else "")
            if kind=="legal":
                h=re.search(r'<h1>(.*?)</h1>',body); body=body[:h.start()]+body[h.end():]
                hdr=f'<header class="phdr"><p class="eyebrow">Legal</p><h1>{h.group(1)}</h1></header>'
                main=f'<main id="main" class="smain"><div class="swrap legal">{hdr}<div class="prose">{body}</div></div></main>'
            else:
                main=f'<main id="main" class="smain"><div class="swrap guide">{cr}{badge}<div class="prose">{body}</div></div></main>'
        out=(f'<!doctype html><html lang="en-GB"><head>{head}</head><body class="usite">\n<a href="#main" class="skip">Skip to main content</a>\n'
             f'{topbar(rel.replace(".html","") if kind!="home" else "/")}\n{main}\n{footer(oldf) if oldf else footer("<p><a href=\"/privacy.html\">Privacy</a><a href=\"/terms.html\">Terms</a></p>")}{tail}</body></html>')
        open(p,"w").write(out); n+=1
print("rebuilt",n,"pages ->",OUT)

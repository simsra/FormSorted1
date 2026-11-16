"""Nov 2026 pricing (Simon, 16 Nov 2026), applied to a COPY of the built site. Not wired into launch_prep.py and never deployed
by this script. Usage: python3 pricing_edits.py [src_dist] [out_dir] [--marked]
  --marked wraps every new or changed Terms/Privacy sentence in <mark class=simon> so Simon can review them (never publish that copy).
Two options per form for AA1, DLA1A, PIP2 and PIP review, chosen at the pay step, paid at the end:
  £19.99 Download, and £29.99 Posted to you, with support (we print and post it to the customer; the customer signs and posts it)."""
import os, re, shutil, sys, json
SRC=sys.argv[1] if len(sys.argv)>1 and not sys.argv[1].startswith("--") else os.path.join(os.path.dirname(os.path.abspath(__file__)),"dist")
OUT=sys.argv[2] if len(sys.argv)>2 and not sys.argv[2].startswith("--") else "/workspace/butter/pricing_mrr/site_dist"
MARK="--marked" in sys.argv
def M(x): return f'<mark class="simon">{x}</mark>' if MARK else x
APP="https://app.formsorted.com"
DL="Download"; PO="Posted to you, with support"
FORMNAME={"aa":"AA1 form","dla":"DLA1A form","pip":"PIP2 answers","pipr":"AR1 answers"}
DLWHAT={"aa":"The whole AA1 form filled in, as a PDF","dla":"The whole DLA1A form filled in, as a PDF","pip":"Typed answers for every PIP2 activity, with extra sheets","pipr":"Typed answers for every AR1 activity, with extra sheets"}
def options_html(form):
    return f"""<div class="pkgs" id="prices"><div class="pkg"><h2>{DL}</h2><p class="pr">£19.99 <small>one-off</small></p><ul class="ticks"><li>{DLWHAT[form]}</li><li>Print it, sign it and send it yourself</li><li>Evidence checklist and a request letter for your GP</li><li>You check every answer before it&#x27;s final</li></ul></div><div class="pkg"><h2>{PO}</h2><p class="pr">£29.99 <small>one-off</small></p><ul class="ticks"><li>Everything in Download</li><li>We print it and post it to you, with sign-here markers</li><li>A prepaid envelope addressed to the right DWP office. You sign it and post it back yourself</li><li>Support until your decision, for up to 6 months. Paid once, it doesn&#x27;t renew</li></ul></div></div>
<form method="post" action="{APP}/checkout" class="startone"><input type="hidden" name="form" value="{form}"><input type="hidden" name="tier" value="1999"><button class="btn btn-big">Start the questions</button></form>
<p class="hint">You choose Download or Posted to you at the end, when you pay. Fixed fee, paid once. The same price whatever DWP decides. We can&#x27;t guarantee any decision.</p>"""
OFFERS='"offers": [{"@type": "Offer", "name": "Download", "price": "19.99", "priceCurrency": "GBP"}, {"@type": "Offer", "name": "Posted to you, with support", "price": "29.99", "priceCurrency": "GBP"}]'
changed={}
def edit(rel,fn):
    p=os.path.join(OUT,rel); h=open(p,encoding="utf-8").read(); n=fn(h)
    if n!=h: open(p,"w",encoding="utf-8").write(n); changed[rel]=True
def guide(form):
    def f(h):
        i=h.find('<div class="pkgs" id="prices">'); j=h.find('</details>',i)
        assert i>0 and j>0, form
        h=h[:i]+options_html(form)+h[j+len('</details>'):]
        h=re.sub(r'"offers":\s*\[[^\]]*\]',OFFERS,h)
        return h
    return f
def landing(h):
    h=h.replace("£99 per form · Pay only at the end","From £19.99 per form · Pay only at the end")
    i=h.find('<div class="lprice">'); j=h.find('<p class="hint pother">',i); assert i>0 and j>0
    cards=f"""<div class="lprice"><div class="pcard"><p class="pn">{DL}</p><p class="pp">£19.99 <span>per form</span></p><p class="pw">Attendance Allowance, PIP, PIP review or DLA for a child. Your official form, completed in full, as a PDF to print, sign and send yourself.</p></div><div class="pcard plus"><p class="pn">{PO}</p><p class="pp">£29.99 <span>per form</span></p><p class="pw">We print your finished form and post it to you, with sign-here markers and a prepaid envelope to the right DWP office. You sign it and post it. Support until your decision, for up to 6 months.</p></div></div>"""
    h=h[:i]+cards+h[j:]
    h=h.replace("<h2 id=\"ph\">One fixed price. Pay only at the end.</h2>","<h2 id=\"ph\">Two simple options. Pay only at the end.</h2>")
    h=h.replace("You see the price before you start, and you can change package before you pay.","You choose Download (£19.99) or Posted to you (£29.99) when you pay.")
    h=re.sub(r'"offers":\s*\[[^\]]*\]',OFFERS,h)
    return h
SVC=("<ul><li>Attendance Allowance (AA1), child DLA (DLA1A), PIP (PIP2) and PIP review: "+M("Download £19.99, or Posted to you, with support £29.99, one-off")+". No success fee.</li><li>Access to Work: Answers £49 or Form pack £79.</li></ul>"
 "<p><strong>Download</strong> "+M("is your completed form (for PIP and PIP review, typed answers and extra sheets) as a PDF to print, sign and send yourself, with an evidence checklist and a request letter for your GP.")+"</p>"
 "<p><strong>Posted to you, with support</strong> "+M("includes everything in Download, and:")+"</p><ul>"
 "<li>"+M("<strong>Printed and posted to you.</strong> We print your finished form and post it to the address you give us when you pay, usually within 2 working days of you approving your answers. It comes with sign-here markers and a prepaid envelope addressed to the right DWP office (for PIP and PIP review, to send with the form DWP sent you). DWP needs your own handwritten signature, so you check it, sign it and post it yourself. We don't sign it, and we don't send anything to DWP for you.")+"</li>"
 "<li>"+M("<strong>Support until your decision, for up to 6 months from payment.</strong> Help with questions about your form or claim from the FormSorted form helper, reminders about your decision, and plain-English explanations of letters DWP sends you. It is a fixed period, paid once, and does not renew. It isn't legal advice or representation.")+"</li>"
 "<li>"+M("If your printed form doesn't arrive within 10 working days, tell us and we'll post another copy free.")+"</li></ul>"
 "<p>"+M("Orders placed before 17 November 2026 (Done for you £99 and Done for you Plus £199) keep the terms and price they were bought on, including anything included with Done for you Plus.")+"</p>")
def terms(h):
    i=h.find('<h2 id="v3">'); j=h.find('<p>Decisions are made by DWP.',i); assert i>0 and j>0
    head='<h2 id="v3">'+M("Our service and prices (from 17 November 2026)")+'</h2><p>FormSorted is an online form-filling service. We prepare your form and documents from your answers; you check, sign and send them to DWP yourself. We don\'t claim for you or send anything to DWP on your behalf.</p> '
    h=h[:i]+head+SVC+" "+h[j:]
    h=h.replace("Orders placed before 26 October 2026 keep the terms and price they were bought on.","Orders placed before 26 October 2026 keep the terms and price they were bought on.")
    rep={"Attendance Allowance (AA1): Done for you £99 or Done for you Plus £199 (both include the filled-in AA1)":"Attendance Allowance (AA1): "+M("Download £19.99 or Posted to you, with support £29.99 (both include the filled-in AA1)"),
         "Disability Living Allowance for children (DLA1A): Done for you £99 or Done for you Plus £199 (both include the filled-in DLA1A)":"Disability Living Allowance for children (DLA1A): "+M("Download £19.99 or Posted to you, with support £29.99 (both include the filled-in DLA1A)"),
         'PIP "How your disability affects you" (PIP2) or PIP review (AR1): Done for you £99 or Done for you Plus £199.':'PIP "How your disability affects you" (PIP2) or PIP review (AR1): '+M("Download £19.99 or Posted to you, with support £29.99."),
         "(included once with Done for you Plus for those forms)":M("(included once with Done for you Plus orders bought before 17 November 2026)"),
         "When you're ready, we show you the price for your pack. You pay once, at the end.":M("When you're ready, you choose Download or Posted to you and see the price. You pay once, at the end."),}
    for a,b in rep.items():
        assert a in h, a[:60]; h=h.replace(a,b)
    # cancellation: the posted copy is a printed copy of the digital service you asked us to start
    a="Answering our questions before then doesn't start the service."
    assert a in h; h=h.replace(a,a+" "+M("If you choose Posted to you, the printed copy we post is made to your order from your own answers."))
    return h
def privacy(h):
    rep={"<strong>Keeping answers for 3 years (Done for you Plus only, opt-in).</strong>":"<strong>Keeping answers for 3 years ("+M("Done for you Plus orders bought before 17 November 2026 only")+", opt-in).</strong>",
         "<li><strong>Print and post (coming soon).</strong> When available, if you ask us to post your pack to you to sign, we will share your name, address and documents with our print-and-post supplier only to print and send them.</li>":
         "<li><strong>Posted to you (from 17 November 2026).</strong> "+M("If you choose Posted to you, we use the postal address you give us when you pay only to post your printed form to you. If we use a print-and-post supplier, we share your name, address and form with them only to print and post it. National Insurance numbers and bank details on the printed form are kept encrypted only until it is posted (at most 14 days), then deleted. Because support lasts until your decision, we keep your answers for up to 6 months after payment instead of 90 days, then delete them. You can ask us to delete them sooner.")+"</li>"}
    for a,b in rep.items():
        assert a in h, a[:60]; h=h.replace(a,b)
    return h

def common(two):
    """Site-wide: the old package step is gone (step 2 is now 'Before you start')."""
    def f(h):
        h=h.replace("<li><strong>Choose your package.</strong> Nothing to pay yet.</li>","<li><strong>Before you start.</strong> Tick 2 boxes. Nothing to pay yet.</li>")
        h=h.replace("Step 2 of 5 · Choose your package","Step 2 of 5 · Before you start")
        if two:
            h=h.replace("<li><strong>Pay once</strong>, at the end.</li>","<li><strong>Pay once</strong>, at the end: Download £19.99, or Posted to you, with support £29.99.</li>")
            h=h.replace("You see the price before you start, and you can change package before you pay.","You choose Download (£19.99) or Posted to you (£29.99) when you pay.")
        else:
            h=h.replace("You see the price before you start, and you can change package before you pay.","You see the price before you start.")
        return h
    return f
if __name__=="__main__":
    if os.path.exists(OUT): shutil.rmtree(OUT)
    shutil.copytree(SRC,OUT)
    for form,d in (("aa","attendance-allowance-form-help"),("dla","dla-form-help"),("pip","pip-form-help"),("pipr","pip-review-form-help")): edit(f"{d}/index.html",guide(form))
    edit("index.html",landing); edit("terms.html",terms); edit("privacy.html",privacy)
    for rel,two in (("index.html",True),("attendance-allowance-form-help/index.html",True),("dla-form-help/index.html",True),("pip-form-help/index.html",True),("pip-review-form-help/index.html",True),("blue-badge-help/index.html",False)): edit(rel,common(two))
    if MARK:
        for rel in ("terms.html","privacy.html"): edit(rel,lambda h:h.replace("</head>","<style>mark.simon{background:#fff3a3;outline:2px solid #e3b400}</style></head>",1))
    print("edited:",", ".join(sorted(changed)),"->",OUT)

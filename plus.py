"""Done for you Plus (£199): per-form customer copy and the 'next form included' / 'Blue Badge included' entitlements.
Plus = 'covers what comes next' (Simon, 28 Oct 2026). Rules: only what we deliver now; no saving line until the appeal stage (SSCS1)
and print-and-post are live; no outcome promise; fixed fee whatever DWP decides; never 'we claim' / 'we submit'.
The only statistic shown is the PIP reconsideration line (DWP PIP statistics to July 2026), on PIP and PIP review only."""
import json, time, re
import printmail
FAMILY={"aa":"aa","dla":"dla","pip":"pip","pipr":"pip"}
PLUS_FORMS=tuple(FAMILY)
BB_FORMS=("aa","dla","pip")   # Blue Badge prefill works from these (bluebadge.PARENT_FORMS); not from AR1 review orders
INTRO="Everything in Done for you, plus:"
FOOT="Fixed fee, paid once. The same price whatever DWP decides. We can't guarantee any decision. You check, sign and send everything yourself."
PIP_STAT="If you disagree with a PIP decision, you can ask DWP to look again. About 1 in 4 of these requests leads to a change in award (DWP statistics, 2021 to 2026)."
KEEP=("Your answers kept for 3 years, if you choose","So a reconsideration or your next form doesn't start from scratch. You can delete them at any time.")
LETTER_DETAIL="Send us the decision letter. We prepare a reconsideration letter from your approved answers, for you to check, sign and send."
ITEMS={
 "aa":[("Help if the claim is turned down",LETTER_DETAIL+" Also if it's awarded at the lower rate."),
       ("Phone-call briefing","What DWP may ask if they phone you or the person who helps, with your own answers to refer to."),
       ("Request letters for everyone who helps","For the GP, carer, family or nurse. Each asks them to describe what they've seen, in their own words."),
       ("Blue Badge answers","If you think a badge may help, made from the answers you've already given us."),
       ("The next Attendance Allowance form","If DWP sends a renewal form, or you ask for the higher rate, we fill it in from your saved answers. Many awards have no end date, so you may never need this.")],
 "dla":[("Help if the claim is turned down",LETTER_DETAIL+" Also if the award is lower than you expected."),
        ("Assessment prep","What DWP may ask you, the school or the doctor, with your answers to refer to."),
        ("Request letters for everyone who knows your child","School or SENCo, paediatrician, therapists or family. Each asks them to describe what they've seen, in their own words."),
        ("Blue Badge answers","If you think your child may qualify, made from the answers you've already given us."),
        ("Your child's DLA renewal form","Most child awards last for a set time. When the renewal pack arrives, we fill it in from your saved answers, updated for what has changed. This doesn't cover the PIP claim at 16, which is a different form.")],
 "pip":[("Help if you're turned down",LETTER_DETAIL+" Also if you get fewer points than you expected."),
        ("Assessment briefing","What the assessor will usually ask at a phone, video or face-to-face assessment, with your own answers to refer to."),
        ("Request letters for everyone who helps you","GP, consultant, support worker or family. Each asks them to describe what they've seen, in their own words."),
        ("Blue Badge answers","If you think a badge may help, made from the answers you've already given us."),
        ("Your PIP review form","When DWP reviews your award, we fill in the review form from your saved answers, updated for what has changed.")],
 "pipr":[("Help if your award is reduced or stopped",LETTER_DETAIL),
         ("Assessment briefing","What the assessor will usually ask at a phone, video or face-to-face assessment, with your own answers to refer to."),
         ("Request letters for everyone who helps you","GP, consultant, support worker or family. Each asks them to describe what they've seen, in their own words."),
         ("Your next PIP review form","When DWP next reviews your award, we fill in the review form from your saved answers, updated for what has changed.")],
}
POST_ON={"aa":"Printed and posted to you to sign, with a Freepost return envelope","dla":"Printed and posted to you to sign, with a Freepost return envelope",
         "pip":"Printed and posted to you to sign, to send with the form DWP sent you","pipr":"Printed and posted to you to sign, to send with the form DWP sent you"}
def posting():
    """Posting counts as included only once print-and-post is really live (printmail.live() on the Intelliprint branch)."""
    return printmail.live() if hasattr(printmail,"live") else printmail.ENABLED
POST_SOON="Coming soon: printed and posted to you to sign. Not yet part of the service."   # as on the Terms page today
def items(form):
    """[(label, detail)] of what Plus delivers today for this form. Posting only when the print provider is live."""
    out=list(ITEMS.get(form,ITEMS["aa"]))
    if posting(): out.append((POST_ON[form if form in POST_ON else "aa"],""))
    return out+[KEEP]
def notes(form):
    """Plain lines shown under the Plus list (never counted as included)."""
    return ([] if posting() else [POST_SOON])+([PIP_STAT] if form in ("pip","pipr") else [])
def flat(form): return [f"{l}: {d[0].lower()+d[1:]}" if d else l for l,d in items(form)]
RC="(a reconsideration letter from your answers)"
SUMMARY={"aa":f"Everything in Done for you, plus help if the claim is turned down {RC}, a phone-call briefing, request letters for everyone who helps, Blue Badge answers, and the next Attendance Allowance form from your saved answers.",
 "dla":f"Everything in Done for you, plus help if the claim is turned down {RC}, assessment prep, request letters for everyone who knows your child, Blue Badge answers, and your child's DLA renewal form from your saved answers.",
 "pip":f"Everything in Done for you, plus help if you're turned down {RC}, an assessment briefing, request letters for everyone who helps you, Blue Badge answers, and your PIP review form from your saved answers.",
 "pipr":f"Everything in Done for you, plus help if your award is reduced or stopped {RC}, an assessment briefing, request letters for everyone who helps you, and your next PIP review form from your saved answers."}
def summary(form):
    """One-sentence tier description (forms.py and the payment product description)."""
    return SUMMARY[form]+(" Printed and posted to you to sign." if posting() else "")
BASE={"aa":"The whole AA1 form filled in, to download","dla":"The whole DLA1A form filled in, to download","pip":"Typed answers for every PIP2 activity, with extra sheets","pipr":"Typed answers for every AR1 activity, with extra sheets"}
def compare_rows(form):
    """(label, detail, in £99, in Plus). '£15 extra' where the £99 customer can buy it separately today; nothing else is priced."""
    rows=[(BASE[form],"You check, sign and send it",1,1),("Evidence checklist and next steps","",1,1),("A request letter for your GP","",1,1)]
    for l,d in items(form): rows.append((l,d,"£15 extra" if l=="Blue Badge answers" else 0,1))
    return rows

# ---------------- entitlements ----------------
NEXT, BB = "next_form", "blue_badge"
def _table(c):
    import store
    c.execute(f"create table if not exists plus_entitlements(plus_token text, kind text, family text, granted {store._REAL}, used_by text, used_at {store._REAL}, primary key(plus_token, kind))")
def _row(c,sql,args):
    r=c.execute(sql,args).fetchone(); return r
def _is_plus(o): return o is not None and str(o["tier"])=="199" and o["status"]=="paid"
def root(c,o):
    """The original paid Plus order behind o (o itself, or the order whose save code a review / reconsideration came from). None if not Plus."""
    seen=0
    while o is not None and seen<6:
        if not o["review_of"]: return o if _is_plus(o) and (o["form"] or "aa") in FAMILY else None
        o=_row(c,"select * from orders where save_code=?",(o["review_of"],)) or _row(c,"select * from orders where token=?",(o["review_of"],)); seen+=1
    return None
def grant(c,o):
    """Record what a paid Plus order includes. Only the original order grants, never a free order made from it (no chains)."""
    if not _is_plus(o) or o["review_of"] or (o["form"] or "aa") not in FAMILY: return False
    _table(c); now=time.time(); fam=FAMILY[o["form"] or "aa"]
    for k in (NEXT,)+((BB,) if (o["form"] or "aa") in BB_FORMS else ()):
        c.execute("insert into plus_entitlements(plus_token,kind,family,granted) values(?,?,?,?) on conflict do nothing",(o["token"],k,fam,now))
    c.commit(); return True
def status(c,o,kind):
    """'available', 'used' or None (not included) for o's Plus root. Legacy Plus orders get their entitlement on first look."""
    r=root(c,o)
    if not r: return None
    _table(c); grant(c,r)
    e=_row(c,"select used_by from plus_entitlements where plus_token=? and kind=?",(r["token"],kind))
    if not e: return None
    if e[0] and not _row(c,"select token from orders where token=?",(e[0],)):   # the order that used it was deleted unused (unpaid clean-up)
        c.execute("update plus_entitlements set used_by=null, used_at=null where plus_token=? and kind=?",(r["token"],kind)); c.commit(); return "available"
    return "used" if e[0] else "available"
def allows(c,o,kind,target_form):
    """True if o's Plus order still includes `kind` for target_form (same benefit family)."""
    r=root(c,o)
    return bool(r) and FAMILY.get(target_form)==FAMILY.get(r["form"] or "aa") and status(c,o,kind)=="available"
def redeem(c,o,kind,new_token,target_form):
    """Atomically mark the entitlement used by new_token. False if not included, other benefit, or already used."""
    if not allows(c,o,kind,target_form): return False
    r=root(c,o); n=c.execute("update plus_entitlements set used_by=?, used_at=? where plus_token=? and kind=? and used_by is null",(new_token,time.time(),r["token"],kind)).rowcount
    c.commit(); return n==1
def redeemed_from(c,token):
    """The Plus order token whose entitlement this order used, or None."""
    _table(c); r=_row(c,"select plus_token from plus_entitlements where used_by=?",(token,)); return r[0] if r else None
_n=lambda s: re.sub(r"[^a-z]","",(s or "").lower())
def same_person(a,b):
    """A next form is for the same person: surname and date of birth must match where both are given."""
    a,b=a or {},b or {}
    if a.get("surname") and b.get("surname") and _n(a["surname"])!=_n(b["surname"]): return False
    if a.get("dob") and b.get("dob") and a["dob"].strip()!=b["dob"].strip(): return False
    return True

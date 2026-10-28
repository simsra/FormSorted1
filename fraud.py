"""Behind-the-scenes checks (Oct 2026). Orders are HELD for a person to review (drafting and documents wait; the customer
sees a neutral 'we're checking your order' page and hello@ gets an email) when:
  - the same email, connection (IP), payment customer or card has more than MAX_NAMES different claimant names in 30 days, or
  - the tapped answers are near-identical (Jaccard >= SIMILAR over >= MIN_TOKENS tapped facts) to another order for a different claimant.
Nothing is decided automatically: an admin releases (carry on) or refunds the order."""
import json, os, re, time
WINDOW=30*86400
MAX_NAMES=int(os.getenv("FRAUD_MAX_NAMES","2"))          # >2 different claimants from one source in 30 days => hold
MAX_REFUSED=int(os.getenv("FRAUD_MAX_REFUSED","1"))      # more than 1 refused request to exaggerate in one order => hold for review (not a rejection)
SIMILAR=float(os.getenv("FRAUD_SIMILAR","0.9")); MIN_TOKENS=int(os.getenv("FRAUD_MIN_TOKENS","15"))
REVIEW_TO=os.getenv("REVIEW_EMAIL","hello@formsorted.com")
def _j(s):
    try: return json.loads(s or "{}") or {}
    except Exception: return {}
def claimant(o):
    """Normalised name of the person the form is for (None when we don't know it yet)."""
    p=_j(o["personal"]); n=" ".join(x for x in (p.get("other_names"),p.get("surname")) if x)
    if not n:
        I=_j(o["intake"])
        if I.get("name") and (o["form"]=="dla" or I.get("who") not in ("me","",None)): n=I["name"]
    n=re.sub(r"[^a-z ]","",(n or "").lower()); n=" ".join(n.split())
    return n or None
def same_person(a,b):
    """'margaret' and 'margaret smith' are the same claimant; 'john smith' and 'jane smith' are not."""
    if not a or not b: return False
    A,B=set(a.split()),set(b.split()); return A<=B or B<=A
def distinct(names):
    out=[]
    for n in sorted({n for n in names if n},key=len,reverse=True):
        if not any(same_person(n,m) for m in out): out.append(n)
    return out
def signature(o):
    """Set of tapped facts (not free text) used to spot copied answers."""
    I=_j(o["intake"]); t=set()
    for rid,v in (I.get("rows") or {}).items():
        t.add(f"{rid}:lvl={v.get('lvl')}"); t|={f"{rid}:c={x}" for x in v.get("c") or []}
        if v.get("days"): t.add(f"{rid}:days={v['days']}")
    t|={"cond="+c.get("name","").lower() for c in I.get("conds") or []}
    for k in ("bad","falls","lastfall","alone","nights","ntimes","nmins","watch","fits","varies","age"):
        if I.get(k): t.add(f"{k}={I[k]}")
    for k in ("fallx","eye","night","nn","aids","school","people"): t|={f"{k}={x}" for x in I.get(k) or []}
    if (I.get("words") or "").strip(): t.add("words="+" ".join(I["words"].lower().split())[:200])
    return t
def _keys(o):
    out=[]
    for col in ("email","ip","stripe_customer","card_fp"):
        try: v=o[col]
        except (KeyError,IndexError): v=None
        if v: out.append((col,v.strip().lower() if col=="email" else v))
    return out
LABEL={"email":"email address","ip":"internet connection","stripe_customer":"payment customer","card_fp":"card"}
def assess(c,o,now=None):
    """List of plain reasons to hold this order (empty = fine)."""
    now=now or time.time(); since=now-WINDOW; reasons=[]; me=claimant(o)
    for col,v in _keys(o):
        q=f"select * from orders where {'lower(email)' if col=='email' else col}=? and status in ('paid','refunded') and created>? and form!='bb' and review_of is null"
        rows=c.execute(q,(v,since)).fetchall()
        names=distinct([claimant(r) for r in rows if r["token"]!=o["token"]]+[me])
        if len(names)>MAX_NAMES: reasons.append(f"{len(rows)} orders in 30 days from the same {LABEL[col]} for {len(names)} different people")
    nref=int((_j(o["intake"]) or {}).get("refused") or 0)
    if nref>MAX_REFUSED: reasons.append(f"asked us to exaggerate {nref} times (we refused each time)")
    sig=signature(o)
    if len(sig)>=MIN_TOKENS:
        for r in c.execute("select * from orders where form=? and status='paid' and created>? and token!=? and intake is not null order by created desc limit 2000",(o["form"],since,o["token"])).fetchall():
            other=claimant(r)
            if not other or not me or same_person(other,me): continue   # a name not given yet: checked again at the details step
            s2=signature(r)
            if len(s2)<MIN_TOKENS: continue
            j=len(sig&s2)/len(sig|s2)
            if j>=SIMILAR: reasons.append(f"answers {int(j*100)}% the same as order {r['token'][:8]} for a different person"); break
    return reasons
def hold_info(o):
    try: h=o["hold"]
    except (KeyError,IndexError): h=None
    return _j(h) if h else {}
def held(o):
    h=hold_info(o); return bool(h.get("reasons")) and not h.get("released_at")
def released(o): return bool(hold_info(o).get("released_at"))
def notify_text(public,o,reasons):
    I=_j(o["intake"])
    return (f"Order held for review: {o['token'][:8]}",
f"""An order has been held before we fill in the form. Nothing has been drafted or released yet.

Order: {o['token']}
Form: {o['form']}   Tier: {o['tier']}
Reasons:
""" + "\n".join("- "+r for r in reasons) + (f"\n- the customer asked us to exaggerate once (refused)" if int(I.get("refused") or 0)==1 else "") + f"""

Review it at {public}/admin (enter the admin key), then choose Release or Refund.
The customer sees: "We're checking your order. We'll email you shortly."
""")

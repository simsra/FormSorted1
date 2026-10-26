"""Order backend: payment webhook verification, private links, link email, 90-day retention.
Env: STRIPE_WEBHOOK_SECRET (whsec_...), PUBLIC_URL, RETENTION_DAYS (90)."""
import hmac, hashlib, json, time, os, secrets, store
RETENTION_DAYS=int(os.getenv("RETENTION_DAYS","90"))
def new_token(): return secrets.token_urlsafe(32)   # 256-bit, unguessable
def verify_signature(payload:bytes, header:str, secret:str, tolerance=300, now=None):
    """Stripe-Signature: t=..., v1=... ; HMAC-SHA256 over f"{t}.{payload}". Raises ValueError if invalid."""
    if not secret or not header: raise ValueError("missing signature")
    parts={}
    for kv in header.split(","):
        k,_,v=kv.strip().partition("="); parts.setdefault(k,[]).append(v)
    try: t=int(parts["t"][0])
    except Exception: raise ValueError("bad header")
    if abs((now or time.time())-t)>tolerance: raise ValueError("timestamp outside tolerance")
    exp=hmac.new(secret.encode(),f"{t}.".encode()+payload,hashlib.sha256).hexdigest()
    if not any(hmac.compare_digest(exp,v) for v in parts.get("v1",[])): raise ValueError("signature mismatch")
    return json.loads(payload)
def sign(payload:bytes, secret:str, t=None):
    t=int(t or time.time()); return f"t={t},v1="+hmac.new(secret.encode(),f"{t}.".encode()+payload,hashlib.sha256).hexdigest()
def link_email(brand, form_name, url):
    return (f"Your {brand} order: your private link",
f"""Thank you for your order with {brand} ({form_name}).

Start, and come back to, your answers here:
{url}

This link is private. Anyone who has it can see your answers, so please don't share it.
We delete everything you tell us 90 days after your order, or sooner if you ask (there is a delete button on every page of your order).

If you didn't place this order, reply to this email.

{brand}, an independent company, not DWP or GOV.UK.
""")
UNPAID_DAYS=int(os.getenv("UNPAID_RETENTION_DAYS","7"))
def purge(c, out_dir, days=None, now=None):
    """Delete all customer data older than `days` (orders, files, saved answers, webhook log). Returns counts."""
    cut=(now or time.time())-86400*(RETENTION_DAYS if days is None else days)
    toks=[r[0] for r in c.execute("select token from orders where created<?",(cut,))]
    for t in toks: store.delete(t)   # local folder and Supabase Storage files
    n=c.execute("delete from orders where created<?",(cut,)).rowcount
    ucut=(now or time.time())-86400*UNPAID_DAYS   # unpaid (free interview) orders: 7 days
    ut=[r[0] for r in c.execute("select token from orders where status in ('free','pending') and created<?",(ucut,))]
    for t in ut: store.delete(t)
    n+=c.execute("delete from orders where status in ('free','pending') and created<?",(ucut,)).rowcount
    s=c.execute("delete from saved where created<?",(cut,)).rowcount
    c.execute("delete from events where received<?",(cut,)); c.commit()
    return {"orders":n,"saved":s}
def erase(c, out_dir, token):
    """Deletion on request: removes every personal field and file but keeps a bare row so the link shows 'deleted'."""
    o=c.execute("select save_code from orders where token=?",(token,)).fetchone()
    store.delete(token)
    if o and o[0]: c.execute("delete from saved where code=?",(o[0],))
    c.execute("update orders set status='deleted', history='[]', personal='{}', draft=null, email=null, deadline='{}', save_code=null, stripe_session=null where token=?",(token,))
    c.commit()

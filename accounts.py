"""Customer accounts (passwordless). Off unless ACCOUNTS_ENABLED=1.
After payment the customer can save their answers to an account with one tap (the order's email). They sign in later with
a one-time email link (sent by Resend from hello@formsorted.com in production; tests use the console mailer).
  Links: random 256-bit token, only its SHA-256 is stored; single use; expire after ACCOUNT_LINK_MINUTES (default 15);
         rate-limited per email (3 per 15 minutes) and per connection (10 per hour). The sign-in page never says whether
         an account exists.
  Sessions: random cookie value, only its hash is stored; 30 days; deleted on sign-out and account deletion.
  Saved answers: the tap answers, approved answers and personal details (name, date of birth, address, GP) per form, so a
         renewal or another form never asks twice. National Insurance numbers and bank details are NEVER saved: they stay
         write-to-PDF-only (secure.py) and are deleted after download; scrub() removes them again as a second guard.
  Retention: an account and its saved answers are deleted 3 years after it was last used (ACCOUNT_KEEP_DAYS), or now on request.
"""
import os, time, json, re, hashlib, secrets
ENABLED=os.getenv("ACCOUNTS_ENABLED","0")=="1"
LINK_MIN=int(os.getenv("ACCOUNT_LINK_MINUTES","15") or 15)
SESSION_DAYS=int(os.getenv("ACCOUNT_SESSION_DAYS","30") or 30)
KEEP_DAYS=int(os.getenv("ACCOUNT_KEEP_DAYS",str(3*365)) or 3*365)
PER_EMAIL=(3,15*60); PER_IP=(10,3600)
COOKIE="fs_acct"
def _h(s): return hashlib.sha256(s.encode()).hexdigest()
def norm_email(e):
    e=(e or "").strip().lower()
    return e if re.fullmatch(r"[^@\s<>]{1,64}@[^@\s<>]{1,190}\.[a-z]{2,}",e) else ""

# ---------------- never save NI numbers or bank details ----------------
SECRET_KEYS={"ni","h_ni","child_ni","his_ni","nino","holder","bank","sort","sort_code","acc_no","account_number","roll","other_ben"}
_NI=re.compile(r"\b[A-CEGHJ-PR-TW-Z]{2}\s?\d{2}\s?\d{2}\s?\d{2}\s?[A-D]\b",re.I)
_SORT=re.compile(r"\b\d{2}[- ]\d{2}[- ]\d{2}\b")
def scrub(x):
    """Copy of x with NI / bank keys removed and NI-number / sort-code-looking values blanked, at any depth."""
    if isinstance(x,dict):
        return {k:scrub(v) for k,v in x.items() if str(k).lower() not in SECRET_KEYS and not (k=="acc" and isinstance(v,str) and re.fullmatch(r"\d{6,8}",v.strip()))}
    if isinstance(x,list): return [scrub(v) for v in x]
    if isinstance(x,str): return _SORT.sub("",_NI.sub("",x)) if (_NI.search(x) or _SORT.search(x)) else x
    return x

# ---------------- accounts ----------------
def by_email(c,email): return c.execute("select * from accounts where email=?",(norm_email(email),)).fetchone()
def by_id(c,aid): return c.execute("select * from accounts where id=?",(aid,)).fetchone() if aid else None
def create(c,email):
    e=norm_email(email)
    if not e: raise ValueError("email")
    aid=secrets.token_urlsafe(16); now=time.time()
    c.execute("insert into accounts(id,email,created,last_seen) values(?,?,?,?)",(aid,e,now,now)); c.commit(); return by_id(c,aid)
def touch(c,aid): c.execute("update accounts set last_seen=? where id=?",(time.time(),aid)); c.commit()
def link_order(c,aid,token): c.execute("update orders set account_id=? where token=?",(aid,token)); c.commit()
def orders_of(c,aid): return c.execute("select * from orders where account_id=? and status!='deleted' order by created desc",(aid,)).fetchall()

# ---------------- saved answers ----------------
RUN_STATE={"at","uploads_done","refused","scrubbed"}
def saved_from_order(o):
    """What we keep from one order: tap answers, approved answers, personal details. Never NI or bank details."""
    I=json.loads(o["intake"] or "{}") if o["intake"] else {}
    d=json.loads(o["draft"] or "{}") if o["draft"] else {}
    return scrub({"intake":{k:v for k,v in I.items() if k not in RUN_STATE},"answers":d.get("answers") or {},"said":d.get("said") or {},
                  "personal":json.loads(o["personal"] or "{}"),"tier":o["tier"]})
def save(c,aid,o):
    form=o["form"] or "aa"; data=json.dumps(saved_from_order(o)); now=time.time()
    c.execute("delete from account_saved where account_id=? and form=?",(aid,form))
    c.execute("insert into account_saved(account_id,form,data,from_order,saved_at) values(?,?,?,?,?)",(aid,form,data,o["token"],now)); c.commit()
def saved(c,aid): return c.execute("select * from account_saved where account_id=? order by saved_at desc",(aid,)).fetchall()
def saved_for(c,aid,form): return c.execute("select * from account_saved where account_id=? and form=?",(aid,form)).fetchone()
def forget(c,aid,form): c.execute("delete from account_saved where account_id=? and form=?",(aid,form)); c.commit()
PERSONAL_SHARED={"title","other_names","surname","dob","addr1","addr2","addr3","postcode","phone","email","gp_name","gp_addr1","gp_postcode","gp_phone"}
WF_SHARED=("title","title_x","first","surname","dob","addr1","addr2","town","pc","phone","gp_name","gp_doc","gp_addr","gp_pc","gp_tel")
def carry(data,src_form,form):
    """(intake, personal) to start a new `form` order from answers saved for `src_form`.
    Same form (a renewal or a fresh claim): every tap answer. Another form: the person's details, GP and conditions only
    (the questions differ, so the rest is asked fresh). DLA is about a child, so nothing personal crosses to or from it."""
    I=dict(data.get("intake") or {}); P=dict(data.get("personal") or {})
    if src_form==form: return scrub(I),scrub(P)
    if "dla" in (src_form,form): return {},{}
    new={k:v for k,v in I.items() if re.fullmatch(r"cond_\d+(_since|_x)?",k) or k in ("who","name","signer","rel","age","conds")}
    if I.get("wf") and form in ("aa",): new["wf"]={k:I["wf"][k] for k in WF_SHARED if k in I["wf"]}
    return scrub(new),scrub({k:v for k,v in P.items() if k in PERSONAL_SHARED})

# ---------------- sign-in links ----------------
def can_send(c,email,ip,now=None):
    now=now or time.time(); e=norm_email(email)
    ne=c.execute("select count(*) from account_links where email=? and created>?",(e,now-PER_EMAIL[1])).fetchone()[0]
    ni=c.execute("select count(*) from account_links where ip=? and created>?",(ip or "",now-PER_IP[1])).fetchone()[0] if ip else 0
    return ne<PER_EMAIL[0] and ni<PER_IP[0]
def new_link(c,email,ip,aid):
    """Records the request (counted for rate limits even when no account exists) and returns the raw token, or None."""
    t=secrets.token_urlsafe(32); now=time.time()
    c.execute("insert into account_links(tok_hash,account_id,email,created,expires,used_at,ip) values(?,?,?,?,?,?,?)",(_h(t),aid,norm_email(email),now,now+LINK_MIN*60,None,ip or "")); c.commit()
    return t if aid else None
def link_ok(c,t):
    r=c.execute("select * from account_links where tok_hash=?",(_h(t or ""),)).fetchone()
    return bool(r and r["account_id"] and r["used_at"] is None and r["expires"]>time.time())
def use_link(c,t):
    """Single use: marks it used and returns the account id, or None (unknown, used or expired)."""
    now=time.time(); h=_h(t or "")
    n=c.execute("update account_links set used_at=? where tok_hash=? and used_at is null and expires>? and account_id is not null",(now,h,now)).rowcount; c.commit()
    if n!=1: return None
    r=c.execute("select account_id from account_links where tok_hash=?",(h,)).fetchone(); return r[0] if r else None
def link_email(brand,url):
    return (f"Sign in to your {brand} account",
f"""Here is your link to sign in to your {brand} account:
{url}

It works once and stops working after {LINK_MIN} minutes. If it has expired, ask for a new one on the sign-in page.

If you didn't ask for this, you can ignore this email. Nobody can sign in without this link.

{brand}, an independent company, not DWP or GOV.UK.
""")
def welcome_email(brand,url):
    return (f"Your {brand} account",
f"""You saved your answers to a {brand} account with this email address, so you won't be asked them again for a renewal or another form.

Sign in any time here: {url}
We email you a one-time link each time. There is no password.

We never keep your National Insurance number or bank details.
You can delete your account and everything in it at any time from your account page.

If this wasn't you, reply to this email.

{brand}, an independent company, not DWP or GOV.UK.
""")
def added_email(brand,url):
    return (f"An order was added to your {brand} account",
f"""An order paid with this email address was added to your {brand} account, with its answers.

Sign in here: {url}

If this wasn't you, reply to this email and we'll remove it.

{brand}, an independent company, not DWP or GOV.UK.
""")

# ---------------- sessions ----------------
def new_session(c,aid):
    s=secrets.token_urlsafe(32); now=time.time()
    c.execute("insert into account_sessions(sid_hash,account_id,created,expires) values(?,?,?,?)",(_h(s),aid,now,now+SESSION_DAYS*86400)); c.commit(); touch(c,aid); return s
def session_account(c,s):
    if not s: return None
    r=c.execute("select account_id, expires from account_sessions where sid_hash=?",(_h(s),)).fetchone()
    if not r or r["expires"]<time.time(): return None
    return by_id(c,r["account_id"])
def end_session(c,s): c.execute("delete from account_sessions where sid_hash=?",(_h(s or ""),)); c.commit()

# ---------------- deletion and retention ----------------
def delete_account(c,aid):
    """Everything about the account: saved answers, sessions, sign-in links, the account. Orders are erased by the caller."""
    for t in ("account_saved","account_sessions","account_links"): c.execute(f"delete from {t} where account_id=?",(aid,))
    c.execute("update orders set account_id=null where account_id=?",(aid,)); c.execute("delete from accounts where id=?",(aid,)); c.commit()
def on_order_deleted(c,token):
    """/delete/<token>: the answers saved from this order go too; and the account if nothing else is left in it."""
    r=c.execute("select account_id from orders where token=?",(token,)).fetchone(); aid=r[0] if r else None
    c.execute("delete from account_saved where from_order=?",(token,)); c.execute("update orders set account_id=null where token=?",(token,)); c.commit()
    if aid and not c.execute("select 1 from orders where account_id=? and status!='deleted'",(aid,)).fetchone() and not c.execute("select 1 from account_saved where account_id=?",(aid,)).fetchone():
        delete_account(c,aid); return "account"
    return "order" if aid else None
def purge(c,now=None):
    now=now or time.time(); n=0
    for r in c.execute("select id from accounts where last_seen<?",(now-KEEP_DAYS*86400,)).fetchall(): delete_account(c,r[0]); n+=1
    c.execute("delete from account_links where created<?",(now-86400,)); c.execute("delete from account_sessions where expires<?",(now,)); c.commit()
    return n

"""Private details the official form needs (NI numbers, bank details). Written into the PDF only.
They are never stored in orders/personal, never logged, never emailed. Between the details page and the download they sit
here, encrypted (Fernet), and are deleted as soon as the filled PDF has been downloaded (or, for packs we post, once sent,
14 days at most). Key: FIELD_KEY env var (set it in production); without it a random key per process is used, so a restart
simply means the customer types them again."""
import os, json, time, re
from cryptography.fernet import Fernet, InvalidToken
_K=os.getenv("FIELD_KEY","").strip()
_F=Fernet(_K.encode() if _K else Fernet.generate_key())
TTL=24*3600; POST_TTL=14*86400
NI_RE=re.compile(r"^[A-CEGHJ-PR-TW-Z]{2}\d{6}[A-D]$")
def _db(c=None):
    import store; c=c or store.connect()
    c.execute(f"create table if not exists sensitive(token text primary key, blob text, created {store._REAL}, keep_until {store._REAL})"); return c
def put(token, fields, keep_days=None):
    c=_db(); blob=_F.encrypt(json.dumps(fields).encode()).decode(); now=time.time()
    ku=now+(keep_days*86400 if keep_days else TTL)
    c.execute("delete from sensitive where token=?",(token,))
    c.execute("insert into sensitive(token,blob,created,keep_until) values(?,?,?,?)",(token,blob,now,ku)); c.commit()
def get(token):
    r=_db().execute("select blob, keep_until from sensitive where token=?",(token,)).fetchone()
    if not r: return None
    if r[1] and r[1]<time.time(): wipe(token); return None
    try: return json.loads(_F.decrypt(r[0].encode()).decode())
    except (InvalidToken, ValueError): wipe(token); return None   # key changed (restart without FIELD_KEY): ask again
def has(token): return get(token) is not None
def wipe(token, c=None):
    """c: pass the caller's open connection when it is mid-transaction (SQLite opens a fresh connection per call)."""
    own=c is None; c=_db(c); c.execute("delete from sensitive where token=?",(token,))
    if own: c.commit()
def purge(now=None):
    c=_db(); n=c.execute("delete from sensitive where keep_until<?",(now or time.time(),)).rowcount; c.commit(); return n
# ---- the form fields ----
def clean_ni(s):
    s=re.sub(r"\s+","",str(s or "")).upper(); return s if NI_RE.match(s) else None
def clean_sort(s):
    s=re.sub(r"[\s-]","",str(s or "")); return s if re.fullmatch(r"\d{6}",s) else None
def clean_acc(s):
    s=re.sub(r"\s","",str(s or "")); return s if re.fullmatch(r"\d{6,8}",s) else None
def fields(form, s):
    """{pdf field: value}, {tick field: state} for the private details s."""
    v={}; t={}; sc=s.get("sort") or ""
    if form=="aa":
        v.update({"01-02NINO":s.get("ni"),"15_4":s.get("h_ni"),"335":s.get("holder"),"336":s.get("bank"),"337":sc[0:2],"338":sc[2:4],"339":sc[4:6],"340":s.get("acc"),"341":s.get("roll")})
        if s.get("other_ben"): t["342"]="/Yes"
    else:
        v.update({"5":s.get("child_ni"),"76":s.get("ni"),"81_2":s.get("his_ni"),"84":s.get("holder"),"85":s.get("bank"),"86":sc[0:2],"86_1":sc[2:4],"86_2":sc[4:6],"87":s.get("acc"),"88":s.get("roll")})
    return {k:x for k,x in v.items() if x},t

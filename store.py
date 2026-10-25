"""Database + file storage. Nothing the app must keep lives on local disk when these are set:
  DATABASE_URL          Postgres (Supabase pooler string). Unset => SQLite at data/orders.db (local/tests).
  SUPABASE_URL, SUPABASE_SERVICE_KEY, SUPABASE_BUCKET (default 'orders', private)
                        Generated files go to Supabase Storage. Unset => local folder out/<token>/."""
import os, sqlite3, threading, shutil, json, urllib.request, urllib.parse, urllib.error
HERE=os.path.dirname(os.path.abspath(__file__))
DATABASE_URL=os.getenv("DATABASE_URL","").strip()
SQLITE_PATH=os.getenv("SQLITE_PATH",os.path.join(HERE,"data","orders.db"))
PG=bool(DATABASE_URL)
_REAL="double precision" if PG else "real"

class Row(tuple):
    """Tuple that also supports row['col'] (works like sqlite3.Row and compares equal to plain tuples)."""
    def __new__(cls, vals, cols): r=super().__new__(cls,vals); r._c={c:i for i,c in enumerate(cols)}; return r
    def __getitem__(self,k): return tuple.__getitem__(self,self._c[k] if isinstance(k,str) else k)
    def keys(self): return list(self._c)

class _PgCursor:
    def __init__(self,cur): self.cur=cur
    @property
    def rowcount(self): return self.cur.rowcount
    def _row(self,r): return None if r is None else Row(r,[d.name for d in self.cur.description])
    def fetchone(self): return self._row(self.cur.fetchone()) if self.cur.description else None
    def fetchall(self): return [self._row(r) for r in self.cur.fetchall()] if self.cur.description else []
    def __iter__(self): return iter(self.fetchall())

class _PgConn:
    """Minimal sqlite3-style wrapper: '?' placeholders, execute(), commit(). Autocommit (pooler-friendly)."""
    def __init__(self,conn): self.conn=conn
    def execute(self,sql,params=()):
        cur=self.conn.cursor(); cur.execute(sql.replace("?","%s"),tuple(params)); return _PgCursor(cur)
    def commit(self): pass
    def close(self): self.conn.close()

_local=threading.local()
SCHEMA=[f"create table if not exists orders(token text primary key, tier text, status text, stripe_session text, email text, consent_at {_REAL}, history text default '[]', personal text default '{{}}', created {_REAL})",
        f"create table if not exists events(id text primary key, received {_REAL})",   # webhook idempotency
        f"create table if not exists saved(code text primary key, form text, answers text, personal text, created {_REAL})"]
COLS=(("form","text default 'aa'"),("draft","text"),("deadline","text default '{}'"),("approved_at",_REAL),("save_code","text"),("review_of","text"),("details_at",_REAL),("paid_at",_REAL))
_ready=False
def _migrate(c):
    for s in SCHEMA: c.execute(s)
    if PG:
        for col,typ in COLS: c.execute(f"alter table orders add column if not exists {col} {typ}")
    else:
        have=[r[1] for r in c.execute("pragma table_info(orders)")]
        for col,typ in COLS:
            if col not in have: c.execute(f"alter table orders add column {col} {typ}")
    c.commit()

def connect():
    """One connection per thread (reconnects if dropped). Schema is created on first use."""
    global _ready
    c=getattr(_local,"c",None)
    if PG:
        import psycopg
        if c is None or c.conn.closed or c.conn.broken:
            # prepare_threshold=None: Supabase's transaction pooler (port 6543) can't use prepared statements
            c=_PgConn(psycopg.connect(DATABASE_URL,autocommit=True,prepare_threshold=None,connect_timeout=15)); _local.c=c
    else:   # fresh SQLite connection per call (as before)
        os.makedirs(os.path.dirname(SQLITE_PATH),exist_ok=True)
        c=sqlite3.connect(SQLITE_PATH); c.row_factory=lambda cur,r: Row(r,[d[0] for d in cur.description])
    if not _ready: _migrate(c); _ready=True
    return c

# ---------------- files ----------------
OUT=os.getenv("OUT_DIR",os.path.join(HERE,"out"))
SB_URL=os.getenv("SUPABASE_URL","").rstrip("/"); SB_KEY=os.getenv("SUPABASE_SERVICE_KEY","").strip()
BUCKET=os.getenv("SUPABASE_BUCKET","orders"); REMOTE=bool(SB_URL and SB_KEY)

def _sb(method,path,data=None,ctype="application/json",extra=None):
    h={"Authorization":f"Bearer {SB_KEY}","apikey":SB_KEY}
    if data is not None: h["Content-Type"]=ctype
    h.update(extra or {})
    r=urllib.request.Request(f"{SB_URL}/storage/v1/{path}",data,h,method=method)
    with urllib.request.urlopen(r,timeout=60) as resp: return resp.read()

def ensure_bucket():
    if not REMOTE: return
    try: _sb("POST","bucket",json.dumps({"id":BUCKET,"name":BUCKET,"public":False}).encode())
    except urllib.error.HTTPError as e:
        if e.code not in (400,409): raise   # already exists

def _key(token,name): return f"{urllib.parse.quote(token)}/{urllib.parse.quote(name)}"

def put_dir(token,local_dir,names):
    """Upload freshly built files for an order, then remove the local temp copies."""
    if not REMOTE: return
    ensure_bucket()
    for n in names:
        with open(os.path.join(local_dir,n),"rb") as f: data=f.read()
        _sb("POST",f"object/{BUCKET}/{_key(token,n)}",data,"application/octet-stream",{"x-upsert":"true"})
    shutil.rmtree(local_dir,ignore_errors=True)

def read(token,name):
    """Bytes of a stored file, or None if missing."""
    if REMOTE:
        try: return _sb("GET",f"object/authenticated/{BUCKET}/{_key(token,name)}")
        except urllib.error.HTTPError as e:
            if e.code in (400,404): return None
            raise
    p=os.path.join(OUT,token,name)
    return open(p,"rb").read() if os.path.exists(p) else None

def signed_url(token,name,expires=300):
    """Short-lived link (Supabase only); the app streams files itself by default."""
    if not REMOTE: return None
    j=json.loads(_sb("POST",f"object/sign/{BUCKET}/{_key(token,name)}",json.dumps({"expiresIn":expires}).encode()))
    return SB_URL+"/storage/v1"+j["signedURL"]

def delete(token):
    """Delete every stored file for an order (remote and any local copy)."""
    shutil.rmtree(os.path.join(OUT,token),ignore_errors=True)
    if not REMOTE: return
    try: lst=json.loads(_sb("POST",f"object/list/{BUCKET}",json.dumps({"prefix":token+"/","limit":1000}).encode()))
    except urllib.error.HTTPError: lst=[]
    names=[f"{token}/{o['name']}" for o in lst if o.get("name")]
    if names: _sb("DELETE",f"object/{BUCKET}",json.dumps({"prefixes":names}).encode())

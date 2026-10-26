"""Official form version watch for pre-fill (AA1 11/25, DLA1A 10/25).
Finds the current PDF on each GOV.UK publication page and compares its version, page count and field names
with the copy bundled in the app. If GOV.UK has a different version, pre-fill for that form is switched off
(customers still get their approved answers) until we update the bundled form and re-enable it.
  python formwatch.py            check now, update the switch in the database, print a report
  python formwatch.py --enable aa   switch pre-fill back on after updating aa1.pdf
App endpoint: POST /cron/formwatch with X-Cron-Secret (for the weekly routine). Network errors never change the switch."""
import hashlib, io, json, os, re, sys, time, urllib.request
from pypdf import PdfReader
HERE=os.path.dirname(os.path.abspath(__file__))
FORMS={"aa":{"pdf":"aa1.pdf","code":"AA1","page":"https://www.gov.uk/government/publications/attendance-allowance-claim-form","link":r"aa1\.pdf"},
       "dla":{"pdf":"dla1a.pdf","code":"DLA1A","page":"https://www.gov.uk/government/publications/disability-living-allowance-for-children-claim-form","link":r"dla[^\"']*claim-form\.pdf"}}
UA={"User-Agent":"Mozilla/5.0 (FormSorted form version check; contact hello@formsorted.com)"}
def _get(u): return urllib.request.urlopen(urllib.request.Request(u,headers=UA),timeout=45).read()
def fingerprint(b):
    r=PdfReader(io.BytesIO(b)); t="".join((p.extract_text() or "") for p in r.pages[:2])
    m=re.search(r"(\d\d/\d\d)\s*1 of (\d+)",t)
    names=sorted((r.get_fields() or {}).keys())
    return {"version":m.group(1) if m else None,"pages":len(r.pages),"fields":len(names),"fields_sha":hashlib.sha256("\n".join(names).encode()).hexdigest()[:16]}
_EXP={}
def expected(form):
    if form not in _EXP: _EXP[form]=fingerprint(open(os.path.join(HERE,FORMS[form]["pdf"]),"rb").read())
    return _EXP[form]
def check(form, fetch=_get):
    """ok=True same form; ok=False different version (disable); ok=None couldn't check (leave as is)."""
    F=FORMS[form]; exp=expected(form); res={"form":form,"checked":time.strftime("%Y-%m-%d %H:%M UTC",time.gmtime()),"expected":exp}
    try:
        page=fetch(F["page"]).decode("utf-8","replace")
        links=re.findall(r'href="(https://assets\.publishing\.service\.gov\.uk/[^"]+\.pdf)"',page)
        url=next((u for u in links if re.search(F["link"],u,re.I)),None)
        if not url: return {**res,"ok":None,"reason":"form PDF link not found on GOV.UK page"}
        live=fingerprint(fetch(url)); res.update(url=url,live=live)
    except Exception as e: return {**res,"ok":None,"reason":f"{e.__class__.__name__}: {e}"}
    diff=[k for k in ("version","pages","fields","fields_sha") if live.get(k)!=exp.get(k)]
    return {**res,"ok":not diff,"reason":("same version" if not diff else "changed: "+", ".join(f"{k} {exp.get(k)} -> {live.get(k)}" for k in diff))}
def _key(form): return f"prefill_disabled_{form}"
def disabled_reason(form, conn=None):
    env=[x.strip() for x in os.getenv("PREFILL_DISABLED","").split(",") if x.strip()]
    if form in env or "all" in env: return "switched off by PREFILL_DISABLED"
    if form not in FORMS: return None
    try:
        import store; c=conn or store.connect(); r=c.execute("select v from settings where k=?",(_key(form),)).fetchone()
        return json.loads(r[0]).get("reason") if r else None
    except Exception as e: print("prefill switch read failed",e); return None
def prefill_enabled(form, conn=None): return disabled_reason(form,conn) is None
def set_disabled(conn, form, info):
    if info: conn.execute("insert into settings(k,v) values(?,?) on conflict(k) do update set v=excluded.v",(_key(form),json.dumps(info)))
    else: conn.execute("delete from settings where k=?",(_key(form),))
    conn.commit()
def run(conn, fetch=_get):
    out=[]
    for f in FORMS:
        r=check(f,fetch)
        if r["ok"] is False: set_disabled(conn,f,{"reason":r["reason"],"url":r.get("url"),"since":r["checked"]})
        # ok True never auto re-enables: a human re-enables after reviewing the new form (--enable)
        r["prefill_enabled"]=prefill_enabled(f,conn); out.append(r)
    return out
if __name__=="__main__":
    import store; c=store.connect()
    if "--enable" in sys.argv: f=sys.argv[sys.argv.index("--enable")+1]; set_disabled(c,f,None); print("pre-fill enabled for",f); sys.exit(0)
    for r in run(c): print(f"{FORMS[r['form']]['code']}: {'OK' if r['ok'] else 'CHANGED' if r['ok'] is False else 'COULD NOT CHECK'} ({r['reason']}); pre-fill {'ON' if r['prefill_enabled'] else 'OFF'}")

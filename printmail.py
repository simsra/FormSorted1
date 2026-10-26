"""Provider-agnostic print-and-post. DISABLED by default: no provider account exists and nothing is ever sent unless
PRINT_MAIL_ENABLED=1 and PRINT_MAIL_PROVIDER names a configured provider. Jobs are only recorded (queued) otherwise."""
import os, json, time
ENABLED=os.getenv("PRINT_MAIL_ENABLED","0")=="1"
PROVIDER=os.getenv("PRINT_MAIL_PROVIDER","none")
class Provider:
    name="none"
    def quote(self,pages,return_envelope=True): return None
    def send(self,job): raise RuntimeError("print-and-post is not enabled")
class Stannp(Provider):
    name="stannp"   # https://www.stannp.com/uk/direct-mail-api/letters  (API key + POST /letters/create with a PDF); not signed up
    def send(self,job): raise NotImplementedError("Stannp account not set up")
class Docmail(Provider):
    name="docmail"  # CFH Docmail API (SOAP/REST, upload PDF, ProcessMailing); not signed up
    def send(self,job): raise NotImplementedError("Docmail account not set up")
PROVIDERS={"none":Provider,"stannp":Stannp,"docmail":Docmail}
def provider(): return PROVIDERS.get(PROVIDER,Provider)()
def queue(c,token,address,files):
    """Record a print job. Sends only when enabled (never in tests)."""
    job={"token":token,"address":address,"files":files,"at":time.time(),"status":"queued" if not ENABLED else "pending"}
    c.execute("insert into settings(k,v) values(?,?) on conflict(k) do update set v=excluded.v",(f"printjob_{token}",json.dumps(job))); c.commit()
    if ENABLED:
        try: provider().send(job); job["status"]="sent"
        except Exception as ex: job["status"]="failed"; job["error"]=str(ex)[:200]
        c.execute("update settings set v=? where k=?",(json.dumps(job),f"printjob_{token}")); c.commit()
    return job

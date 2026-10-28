"""Print and post (Plus) via Intelliprint, fully mocked: no real API call, nothing printed or charged.
Units run offline. e2e needs a DEV server started with PRINT_MAIL_ENABLED=1 PRINT_PROVIDER=intelliprint
INTELLIPRINT_API_KEY=ip_test_key INTELLIPRINT_API_BASE=http://127.0.0.1:$MOCK_PORT/v1 INTELLIPRINT_INSERT_DLA=ins_dla_test
and its own SQLITE_PATH / MAIL_LOG (shared with this script):  MOCK_PORT=8038 python test_printmail.py http://localhost:8036"""
import os, sys, re, json, io, time, base64, threading, urllib.request, urllib.parse, urllib.error
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pypdf import PdfReader
# ---------------- units (default env: switched off) ----------------
import printmail as P
if not os.getenv("PRINT_MAIL_ENABLED"): assert not P.ENABLED and not P.live()   # off unless switched on
assert P.FREEPOST["aa"]["address"]=="Freepost DWP Attendance Allowance" and P.FREEPOST["dla"]["address"]=="Freepost DWP DLA Child"   # GOV.UK, checked 28 Oct 2026
assert "pip" not in P.FREEPOST and P.return_envelope("pip")==("own","PIP2") and P.return_envelope("pipr")==("own","AR1")
p={"title":"Mrs","other_names":"Margaret","surname":"Tester","addr1":"1 Test St","addr2":"","addr3":"Leeds","postcode":"ls1 1aa"}
assert P.recipient("aa",p)=={"name":"Mrs Margaret Tester","line":"1 Test St, Leeds","postcode":"LS1 1AA","country":"GB"}
assert P.recipient("dla",{**p,"other_names":"Leo","parent_other_names":"Pat","parent_surname":"Tester"})["name"]=="Pat Tester"
assert P.missing_address(P.recipient("aa",{"other_names":"A"}))==["address","postcode"]
def text(pdf): return " ".join(" ".join(pg.extract_text().split()) for pg in PdfReader(io.BytesIO(pdf)).pages)
for form,ret,want in (("aa",("label","Freepost DWP Attendance Allowance"),"Freepost DWP Attendance Allowance"),("dla",("insert","ins_x"),"already addressed to Freepost DWP DLA Child"),("pip",("own","PIP2"),"envelope DWP sent you with your PIP2")):
    cv=P.cover_sheet(form,P.recipient(form,p),ret); t=text(cv); assert len(PdfReader(io.BytesIO(cv)).pages)==2
    assert want in t and "Sign and date the declaration" in t and "We have not sent anything to DWP" in t, (form,t)
    if form!="pip": assert "You do not need a stamp" in t or "You do not need a postcode or a stamp" in t, t
    low=t.lower(); assert "stripe" not in low and " ai " not in low and "we submit" not in low and "we claim" not in low and "intelliprint" not in low
for s in P.sent_email("FormSorted","https://app.formsorted.com",{"form":"aa","token":"t"*20},{"return":"label"}):
    low=s.lower(); assert "stripe" not in low and " ai " not in low and "intelliprint" not in low and "we submit" not in low
# provider payload (documented fields only)
os.environ.update(INTELLIPRINT_API_KEY="k"); ip=P.Intelliprint()
b=ip.payload({"token":"tok12345xyz","form":"aa","pdf":b"%PDF","filename":"AA1-pack.pdf","recipient":P.recipient("aa",p),"insert":None,"reference":"FormSorted tok12345 AA1"})
assert b["testmode"] is True and b["confirmed"] is True and b["type"]=="letter" and b["printing"]=={"double_sided":"yes","black_and_white":True}
assert b["postage"]=={"service":"uk_second_class","ideal_envelope":"c4"} and "insert" not in b and b["confidential"] is True and base64.b64decode(b["file"]["content"])==b"%PDF"
os.environ["INTELLIPRINT_TESTMODE"]="0"; assert P.Intelliprint().payload({**{"token":"t","form":"aa","pdf":b"","filename":"x.pdf","recipient":{},"reference":"r"},"insert":"ins_1"})["insert"]=="ins_1" and P.Intelliprint().testmode is False
os.environ["INTELLIPRINT_TESTMODE"]="1"
print("printmail units ok")
if len(sys.argv)<2: sys.exit(0)

# ---------------- mock Intelliprint API ----------------
MOCK={"posts":[],"gets":[],"fail":None,"status":{},"n":0}
class H(BaseHTTPRequestHandler):
    def log_message(self,*a): pass
    def _send(self,code,obj):
        b=json.dumps(obj).encode(); self.send_response(code); self.send_header("Content-Type","application/json"); self.send_header("Content-Length",str(len(b))); self.end_headers(); self.wfile.write(b)
    def do_POST(self):
        n=int(self.headers.get("Content-Length") or 0); body=json.loads(self.rfile.read(n) or b"{}")
        if self.path!="/v1/prints": return self._send(404,{"error":{"type":"invalid_request_error","code":"not_found","message":"Not found"}})
        if self.headers.get("Authorization")!="Bearer ip_test_key": return self._send(401,{"error":{"type":"authentication_error","code":"invalid_api_key","message":"bad key"}})
        MOCK["posts"].append({"auth":self.headers.get("Authorization"),"body":body})
        if MOCK["fail"]: f=MOCK["fail"]; MOCK["fail"]=None; return self._send(f[0],{"error":f[1]})
        MOCK["n"]+=1; i=MOCK["n"]; pid,lid=f"print_t{i}",f"letter_t{i}"; MOCK["status"][pid]="waiting_to_print"
        self._send(200,{"id":pid,"object":"print","testmode":body.get("testmode"),"confirmed":body.get("confirmed"),"type":"letter","pages":9,"sheets":5,"reference":body.get("reference"),
                        "letters":[{"id":lid,"status":"waiting_to_print","address":body["recipients"][0]["address"]}]})
    def do_GET(self):
        m=re.match(r"^/v1/prints/(print_\w+)$",self.path); MOCK["gets"].append(self.path)
        if not m or m.group(1) not in MOCK["status"]: return self._send(404,{"error":{"type":"invalid_request_error","code":"not_found","message":"Not found"}})
        pid=m.group(1); i=pid.split("_t")[1]; st=MOCK["status"][pid]
        L={"id":f"letter_t{i}","status":st,"shipped_date":1793000000 if st=="sent" else None}
        if st=="returned": L["returned"]={"date":1793100000,"reason":"Addressee gone away"}
        self._send(200,{"id":pid,"object":"print","testmode":True,"confirmed":True,"letters":[L]})
srv=ThreadingHTTPServer(("127.0.0.1",int(os.environ.get("MOCK_PORT","8038"))),H); threading.Thread(target=srv.serve_forever,daemon=True).start()

B=sys.argv[1].rstrip("/"); KEY=os.getenv("CRON_SECRET","cron_test_local"); MAIL=os.environ["MAIL_LOG"]
class NR(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*a,**k): return None
op=urllib.request.build_opener(NR)
def req(p_,data=None,js=None,headers=None):
    if js is not None: r=urllib.request.Request(B+p_,json.dumps(js).encode(),{"Content-Type":"application/json",**(headers or {})})
    else: r=urllib.request.Request(B+p_,urllib.parse.urlencode(data,doseq=True).encode() if data is not None else None,headers or {})
    try: return op.open(r)
    except urllib.error.HTTPError as e: return e
body=lambda p_: req(p_).read().decode(); loc=lambda r: r.headers["location"]
def mails(): return [json.loads(l) for l in open(MAIL)] if os.path.exists(MAIL) else []
def wait(f,secs=15):
    t=time.time()
    while time.time()-t<secs:
        v=f()
        if v: return v
        time.sleep(0.2)
    raise AssertionError("timed out waiting")
import app as A
SAMPLE={"aa":[("about",{"who":"parent","name":"Margaret","signer":"poa"}),("conds",{"cond_0":"1","cond_0_since":"2015"}),("daily",{"bad":"3","r_bed_lvl":"cant","r_bed_c":["out","in"],"r_bed_days":"7"}),("safety",{"falls":"3-5","lastfall":"month"}),("finish",{"people":["GP"]})],
 "dla":[("about",{"rel":"Mum","name":"Leo","age":"5to15"}),("conds",{"cond_0":"1","cond_0_since":"2021"}),("daily",{"bad":"4","r_toilet_lvl":"help","r_toilet_c":["pads"]}),("safety",{"fits":"no","varies":"varies"}),("finish",{"people":["Paediatrician"]})],
 "pip":[("about",{"who":"me"}),("conds",{"cond_0":"1","cond_0_since":"2018"}),("daily",{"bad":"4","r_a1_lvl":"slow","r_a1_c":["hob"]}),("out",{"r_a9_lvl":"help","r_a9_c":["anx"]}),("finish",{"people":["GP"]})]}
DD={"title":"Mrs","other_names":"Margaret","surname":"Tester","dob":"1940-01-02","addr1":"1 Test St","addr3":"Leeds","postcode":"LS1 1AA"}
def to_details(form,tier="199",email=None):
    tok=loc(req("/checkout",{"tier":tier,"form":form})).split("/")[-1]; req(f"/consent/{tok}",{"health":"on","truth":"on"})
    for s,d in SAMPLE[form]: req(f"/intake/{tok}",{"sec":s,"nav":"next",**d})
    assert loc(req(f"/pay/{tok}",{"waive":"on"}))==f"/start/{tok}"; req(f"/start/{tok}"); req(f"/uploads/{tok}/done",{})
    nx=wait(lambda: req(f"/prepare/{tok}").headers.get("location"),30)   # drafting runs in the background
    assert nx==f"/deadline/{tok}", nx
    if email: c=A.db(); c.execute("update orders set email=? where token=?",(email,tok)); c.commit()
    ap=body(f"/approve/{tok}"); ok={f"ok_{t}":"on" for t,_,_ in A.FORMS[form]["topics"]}; ok["honest"]="on"
    for rn in set(re.findall(r'name="(res_[^"]+)"',ap)): ok[rn]="keep"
    nx=loc(req(f"/approve/{tok}",ok))
    if "/ticks/" in nx: th=body(nx); tf=dict(re.findall(r'name="(t_[^"]+)" value="([^"]*)" checked',th)); tf["confirm"]="on"; req(nx,tf)
    return tok
def job(tok): return json.loads(A.get(tok)["print_job"] or "null")

# ---- 1. Plus AA: posts automatically after the final approve + details; double-sided, B&W, C4, test mode, Freepost label
tok=to_details("aa",email="margaret@example.com")
dh=body(f"/details/{tok}"); assert "Print and post my filled-in form to the address above, with the Freepost address to send it back to" in dh and "name=post_pack value=1 checked" in dh
assert loc(req(f"/details/{tok}",{**DD,"post_pack":"1"}))==f"/documents/{tok}"
wait(lambda: len(MOCK["posts"])==1 and (job(tok) or {}).get("letter_id"))
pb=MOCK["posts"][0]["body"]; assert MOCK["posts"][0]["auth"]=="Bearer ip_test_key"
assert pb["testmode"] is True and pb["confirmed"] is True and pb["printing"]=={"double_sided":"yes","black_and_white":True} and pb["postage"]["ideal_envelope"]=="c4" and pb["postage"]["service"]=="uk_second_class"
assert pb["recipients"]==[{"address":{"name":"Mrs Margaret Tester","line":"1 Test St, Leeds","postcode":"LS1 1AA","country":"GB"}}] and "insert" not in pb and pb["metadata"]["order"]==tok
pdf=base64.b64decode(pb["file"]["content"]); R=PdfReader(io.BytesIO(pdf)); t0=" ".join((R.pages[0].extract_text()+" "+R.pages[1].extract_text()).split())
aa1=A.store.read(tok,"AA1-filled.pdf"); assert len(R.pages)==2+len(PdfReader(io.BytesIO(aa1)).pages)   # cover (2 pages) + the filled AA1
assert "Your AA1 pack" in t0 and "Sign and date the declaration" in t0 and "Freepost DWP Attendance Allowance" in t0 and "We have not sent anything to DWP" in t0
j=job(tok); assert j["print_id"]=="print_t1" and j["letter_id"]=="letter_t1" and j["status"]=="waiting_to_print" and j["testmode"] is True and j["return"]=="label"
doc=body(f"/documents/{tok}"); assert "Your printed pack: Being printed" in doc
# re-saving details never posts twice
req(f"/details/{tok}",{**DD,"post_pack":"1"}); time.sleep(1.5); assert len(MOCK["posts"])==1
# webhook (unauthenticated body is only a nudge: status re-read from the API) -> sent -> customer emailed once
MOCK["status"]["print_t1"]="sent"
assert req("/webhooks/print",js={"type":"letter.updated","print_id":"print_t1","id":"letter_t1","status":"sent"}).status==200
wait(lambda: (job(tok) or {}).get("status")=="sent" and job(tok).get("sent_emailed_at"))
assert "/v1/prints/print_t1" in MOCK["gets"]
doc=body(f"/documents/{tok}"); assert "Your printed pack: Posted" in doc and "was posted to you on" in doc
wait(lambda: [m for m in mails() if m["to"]=="margaret@example.com" and "has been posted" in m["subject"]])
req("/webhooks/print",js={"type":"letter.updated","print_id":"print_t1"}); time.sleep(1)
assert len([m for m in mails() if m["to"]=="margaret@example.com" and "has been posted" in m["subject"]])==1
assert req("/webhooks/print",js={"print_id":"print_nope"}).status==200 and req("/webhooks/print",js={"print_id":"x' or 1=1--"}).status==200

# ---- 2. Plus DLA: pack goes to the parent; pre-printed Freepost return envelope insert from env
tk2=to_details("dla")
dh=body(f"/details/{tk2}"); assert "with a return envelope" in dh
req(f"/details/{tk2}",{**DD,"other_names":"Leo","parent_other_names":"Pat","parent_surname":"Tester","relationship":"Mother","post_pack":"1"})
wait(lambda: len(MOCK["posts"])==2); pb=MOCK["posts"][1]["body"]
assert pb["insert"]=="ins_dla_test" and pb["recipients"][0]["address"]["name"]=="Pat Tester"
t=" ".join(PdfReader(io.BytesIO(base64.b64decode(pb["file"]["content"]))).pages[1].extract_text().split()); assert "already addressed to Freepost DWP DLA Child" in t
wait(lambda: (job(tk2) or {}).get("letter_id")=="letter_t2")

# ---- 3. Plus PIP: extra sheets printed; customer uses DWP's own envelope (no Freepost address invented)
tk3=to_details("pip")
assert "Print and post my extra sheets" in body(f"/details/{tk3}") and "the envelope DWP sent with your form" in body(f"/details/{tk3}")
req(f"/details/{tk3}",{**DD,"post_pack":"1"}); wait(lambda: len(MOCK["posts"])==3); pb=MOCK["posts"][2]["body"]
t=text(base64.b64decode(pb["file"]["content"])); assert "envelope DWP sent you with your PIP2" in t and "Freepost" not in t and "insert" not in pb

# ---- 4. provider failure -> held for review: admin page + email to hello@, customer told we're checking; retry works
MOCK["fail"]=(402,{"type":"payment_error","code":"payment_error","message":"Insufficient balance"})
tk4=to_details("aa",email="fail@example.com"); req(f"/details/{tk4}",{**DD,"post_pack":"1"})
wait(lambda: (job(tk4) or {}).get("status")=="held")
assert "payment_error" in job(tk4)["error"] and not job(tk4).get("print_id")
wait(lambda: [m for m in mails() if m["to"]=="hello@formsorted.com" and tk4[:8] in m["subject"] and "Print-and-post held" in m["subject"]])
doc=body(f"/documents/{tk4}"); assert "Your printed pack: Being checked" in doc and "Download" in doc
assert req("/admin/print",{"key":"wrong"}).status==403
ad=body_post=req("/admin/print",{"key":KEY}).read().decode(); assert tk4[:8] in ad and "Insufficient balance" in ad and "Try posting again" in ad and tok[:8] not in ad
r=req(f"/admin/print/{tk4}",{"key":KEY,"do":"retry"}).read().decode(); assert "Sent to print" in r, r
assert job(tk4)["status"]=="waiting_to_print" and job(tk4)["attempts"]==2 and tk4[:8] not in req("/admin/print",{"key":KEY}).read().decode()

# ---- 5. returned letter -> review again (cron poll re-reads statuses)
MOCK["status"][job(tk4)["print_id"]]="returned"
assert req("/cron/print-status",{}).status==403
assert json.loads(urllib.request.urlopen(urllib.request.Request(B+"/cron/print-status",b"",{"X-Cron-Secret":KEY})).read())["checked"]>=1
wait(lambda: job(tk4)["status"]=="returned"); assert "Addressee gone away" in job(tk4)["error"]
assert "Came back to us" in body(f"/documents/{tk4}") and tk4[:8] in req("/admin/print",{"key":KEY}).read().decode()
assert "Marked as handled" in req(f"/admin/print/{tk4}",{"key":KEY,"do":"done"}).read().decode() and tk4[:8] not in req("/admin/print",{"key":KEY}).read().decode()

# ---- 6. opted out / skipped details / £99: nothing posted
n=len(MOCK["posts"])
tk5=to_details("aa"); req(f"/details/{tk5}",{**DD}); tk6=to_details("aa"); req(f"/details/{tk6}",{"skip":"1"})
tk7=to_details("aa",tier="99"); assert "Print and post" not in body(f"/details/{tk7}"); req(f"/details/{tk7}",{**DD,"post_pack":"1"})
time.sleep(2); assert len(MOCK["posts"])==n and not job(tk5) and not job(tk6) and not job(tk7) and A.get(tk7)["post_pack"]==0
assert "Your printed pack" not in body(f"/documents/{tk5}")
print("PRINTMAIL ALL OK")

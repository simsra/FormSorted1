"""'Post it to me to sign' (Plus: included; Done for you: optional paid add-on) via Intelliprint, fully mocked: no real API call, nothing printed or charged.
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
BOX={"aa":"Question 64 on page 30 (Declaration): sign, date and print the name","dla":"Declaration on page 38: sign, print your name and date","pip":"The Declaration on the PIP2 DWP sent you: sign and date it","pipr":"Section 3: sign under"}
for form,ret,want in (("aa",("label","Freepost DWP Attendance Allowance"),"Freepost DWP Attendance Allowance"),("dla",("insert","ins_x"),"already addressed to Freepost DWP DLA Child"),
                      ("pip",("own","PIP2"),"Put the PIP2 and the extra sheets in the envelope DWP sent you. Return it by the date on DWP's letter"),("pipr",("own","AR1"),"Return it by the date on the front of the form")):
    cv=P.cover_sheet(form,P.recipient(form,p),ret,contents=["Your copy of your answers"]); t=text(cv); assert len(PdfReader(io.BytesIO(cv)).pages)==2
    assert want in t and "Sign here and post it back" in t and BOX[form] in t and "We have not sent anything to DWP" in t and "Your copy of your answers" in t, (form,t)
    assert "bank details" not in t and "Print at actual size" not in t, t   # NI / bank details are on the form already (or they chose to write them); we printed it
    if form in ("aa","dla"): assert "You do not need a stamp" in t or "You do not need a postcode or a stamp" in t, t
    else: assert "Freepost" not in t and "copy your answers onto the" in t, t
    low=t.lower(); assert "stripe" not in low and " ai " not in low and "we submit" not in low and "we claim" not in low and "intelliprint" not in low
for s in P.sent_email("FormSorted","https://app.formsorted.com",{"form":"aa","token":"t"*20},{"return":"label"})+P.reminder_email("FormSorted","https://app.formsorted.com",{"form":"dla","token":"t"*20},{"return":"insert","sent_at":time.time()},5):
    low=s.lower(); assert "stripe" not in low and " ai " not in low and "intelliprint" not in low and "we submit" not in low and "we claim" not in low
# reminders: day 5 and day 10 after posting, once each
now=time.time(); D=86400
assert P.reminders_due({"status":"sent","sent_at":now-4*D},now)==[] and P.reminders_due({"status":"sent","sent_at":now-5*D-1},now)==[5]
assert P.reminders_due({"status":"sent","sent_at":now-11*D,"reminded":[5]},now)==[10] and P.reminders_due({"status":"sent","sent_at":now-11*D,"reminded":[5,10]},now)==[]
assert P.reminders_due({"status":"held"},now)==[] and P.reminders_due({"status":"waiting_to_print","submitted_at":now-20*D},now)==[]
sub,txt=P.reminder_email("FormSorted","https://x",{"form":"aa","token":"t"*20},{"return":"label","sent_at":now},10); assert "have you signed and posted your AA1" in sub and "you can ignore this email" in txt
if not os.getenv("POST_ADDON_PENCE"): assert P.ADDON_PENCE==999   # £9.99 for Done for you; Plus includes it
hp=text(P.html_pdf("<html><head><style>p{x}</style></head><body><h1>Your answers</h1><p class=a>Line <a href='https://e.x'>one</a></p><ul><li>two</li></ul></body></html>"))
assert "Your answers" in hp and "Line one" in hp and "two" in hp and "https" not in hp
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
PREVIEW={}
def to_details(form,tier="199",email=None,post=False):
    tok=loc(req("/checkout",{"tier":tier,"form":form})).split("/")[-1]; req(f"/consent/{tok}",{"health":"on","truth":"on"})
    for s,d in SAMPLE[form]: req(f"/intake/{tok}",{"sec":s,"nav":"next",**d})
    PREVIEW[tok]=body(f"/preview/{tok}")
    assert loc(req(f"/pay/{tok}",{"waive":"on",**({"post":"1"} if post else {})}))==f"/start/{tok}"; req(f"/start/{tok}"); req(f"/uploads/{tok}/done",{})
    nx=wait(lambda: req(f"/prepare/{tok}").headers.get("location"),30)   # drafting runs in the background
    assert nx==f"/deadline/{tok}", nx
    if email: c=A.db(); c.execute("update orders set email=? where token=?",(email,tok)); c.commit()
    ap=body(f"/approve/{tok}"); ok={f"ok_{t}":"on" for t,_,_ in A.FORMS[form]["topics"]}; ok["honest"]="on"
    for rn in set(re.findall(r'name="(res_[^"]+)"',ap)): ok[rn]="keep"
    nx=loc(req(f"/approve/{tok}",ok))
    if "/ticks/" in nx: th=body(nx); tf=dict(re.findall(r'name="(t_[^"]+)" value="([^"]*)" checked',th)); tf["confirm"]="on"; req(nx,tf)
    return tok
def job(tok): return json.loads(A.get(tok)["print_job"] or "null")

# ---- 1. Plus AA, 'Post it to me to sign' chosen at checkout (included, never pre-ticked): posted after the final approve + details
tok=to_details("aa",email="margaret@example.com",post=True)
pv=PREVIEW[tok]; assert "Post it to me to sign (included)" in pv and "with the Freepost address to send it back to" in pv and "You can download it either way" in pv
assert re.search(r"<input type=checkbox name=post value=1 id=post_cb data-add=0>",pv) and "id=post_cb data-add=0 checked" not in pv and "post_cb').checked" not in pv
assert A.get(tok)["post_pack"]==1
dh=body(f"/details/{tok}"); assert "we will post your printed AA1 pack to the address above" in dh and "Skip. I'll write my details in by hand" not in dh
assert loc(req(f"/details/{tok}",{**DD}))==f"/documents/{tok}"
wait(lambda: len(MOCK["posts"])==1 and (job(tok) or {}).get("letter_id"))
pb=MOCK["posts"][0]["body"]; assert MOCK["posts"][0]["auth"]=="Bearer ip_test_key"
assert pb["testmode"] is True and pb["confirmed"] is True and pb["printing"]=={"double_sided":"yes","black_and_white":True} and pb["postage"]["ideal_envelope"]=="c4" and pb["postage"]["service"]=="uk_second_class"
assert pb["recipients"]==[{"address":{"name":"Mrs Margaret Tester","line":"1 Test St, Leeds","postcode":"LS1 1AA","country":"GB"}}] and "insert" not in pb and pb["metadata"]["order"]==tok
pdf=base64.b64decode(pb["file"]["content"]); R=PdfReader(io.BytesIO(pdf)); t0=" ".join((R.pages[0].extract_text()+" "+R.pages[1].extract_text()).split()); tall=text(pdf)
aa1=A.store.read(tok,"AA1-filled.pdf"); n1=len(PdfReader(io.BytesIO(aa1)).pages); assert len(R.pages)>2+n1   # cover (2) + the filled AA1 + answers + request letters
assert " ".join(R.pages[2].extract_text().split())[:60]==" ".join(PdfReader(io.BytesIO(aa1)).pages[0].extract_text().split())[:60]   # the form starts on sheet 2
assert "Sign here and post it back" in t0 and "Question 20 on page 9" in t0 and "Question 64 on page 30" in t0 and "Freepost DWP Attendance Allowance" in t0 and "We have not sent anything to DWP" in t0
for part in ("Your filled-in AA1","Your copy of your answers","Request letters for your GP, carer, school or family"): assert part in t0, part
assert "Dear Dr" in tall and "bank details" not in t0
j=job(tok); assert j["print_id"]=="print_t1" and j["letter_id"]=="letter_t1" and j["status"]=="waiting_to_print" and j["testmode"] is True and j["return"]=="label"
doc=body(f"/documents/{tok}"); assert "Your printed pack: Being printed" in doc
# re-saving details never posts twice
req(f"/details/{tok}",{**DD}); time.sleep(1.5); assert len(MOCK["posts"])==1
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
tk2=to_details("dla",post=True)
assert "with a Freepost return envelope" in PREVIEW[tk2]
req(f"/details/{tk2}",{**DD,"other_names":"Leo","parent_other_names":"Pat","parent_surname":"Tester","relationship":"Mother"})
wait(lambda: len(MOCK["posts"])==2); pb=MOCK["posts"][1]["body"]
assert pb["insert"]=="ins_dla_test" and pb["recipients"][0]["address"]["name"]=="Pat Tester"
t=" ".join(PdfReader(io.BytesIO(base64.b64decode(pb["file"]["content"]))).pages[1].extract_text().split()); assert "already addressed to Freepost DWP DLA Child" in t
wait(lambda: (job(tk2) or {}).get("letter_id")=="letter_t2")

# ---- 3. Plus PIP: extra sheets printed; customer uses DWP's own envelope (no Freepost address invented)
tk3=to_details("pip",post=True)
assert "We print your extra sheets and post them to you, to copy onto the PIP2 DWP sent you" in PREVIEW[tk3]
req(f"/details/{tk3}",{**DD}); wait(lambda: len(MOCK["posts"])==3); pb=MOCK["posts"][2]["body"]
t=text(base64.b64decode(pb["file"]["content"])); assert "Put the PIP2 and the extra sheets in the envelope DWP sent you" in t and "Freepost" not in t and "insert" not in pb
assert "Extra sheets for the PIP2 DWP sent you" in t and "Copy each answer onto the paper PIP2" in t

# ---- 4. provider failure -> held for review: admin page + email to hello@, customer told we're checking; retry works
MOCK["fail"]=(402,{"type":"payment_error","code":"payment_error","message":"Insufficient balance"})
tk4=to_details("aa",email="fail@example.com",post=True); req(f"/details/{tk4}",{**DD})
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

# ---- 6. not chosen / skipped details / £99 without the add-on: nothing posted (download only)
n=len(MOCK["posts"])
tk5=to_details("aa"); d5=body(f"/details/{tk5}"); assert "Post it to me to sign (included)" in d5 and "name=post_pack value=1>" in d5 and "Skip." in d5   # Plus can still choose it, unticked
req(f"/details/{tk5}",{**DD}); tk6=to_details("aa"); req(f"/details/{tk6}",{"skip":"1","post_pack":"1"})
tk7=to_details("aa",tier="99"); pv=PREVIEW[tk7]; assert "Post it to me to sign (+£9.99)" in pv and "data-add=999>" in pv and "id=paybtn>Pay £99 to get your completed form" in pv
assert "Post it to me" not in body(f"/details/{tk7}"); req(f"/details/{tk7}",{**DD,"post_pack":"1"})
time.sleep(2); assert len(MOCK["posts"])==n and not job(tk5) and not job(tk6) and not job(tk7) and A.get(tk7)["post_pack"]==0 and A.get(tk6)["post_pack"]==0
assert "Your printed pack" not in body(f"/documents/{tk5}") and "Download" in body(f"/documents/{tk7}")

# ---- 7. £99 with the add-on: an inline £9.99 Checkout line item (no Stripe product or price), discount box kept; then posted
cap=[]; real=A.stripe; A.stripe=lambda m,path,data=None: cap.append((m,path,data)) or {"id":"cs_test_x","url":"https://checkout.invalid/x"}
try:
    tk8=to_details("aa",tier="99",email="addon@example.com",post=True); assert A.get(tk8)["post_pack"]==1
    A.stripe_session(A.get(tk8)); d=cap[-1][2]
    assert cap[-1][1]=="/checkout/sessions" and d["line_items[0][price_data][unit_amount]"]==9900 and d["line_items[1][price_data][unit_amount]"]==999 and d["line_items[1][quantity]"]==1
    assert "price" not in " ".join(k for k in d if "[price]" in k) and d["allow_promotion_codes"]=="true" and "Stripe" not in d["line_items[1][price_data][product_data][name]"]
    A.stripe_session(A.get(tok)); assert "line_items[1][quantity]" not in cap[-1][2]   # Plus: included, no extra line
    A.stripe_session(A.get(tk7)); assert "line_items[1][quantity]" not in cap[-1][2]   # not chosen
    assert all(p_ in ("/checkout/sessions",) for _,p_,_ in cap)   # no product / price objects created
finally: A.stripe=real
assert "we will post your printed AA1 pack" in body(f"/details/{tk8}"); req(f"/details/{tk8}",{**DD})
wait(lambda: len(MOCK["posts"])==n+1 and (job(tk8) or {}).get("letter_id"))
# switched off: no choice shown, nothing charged for it
A.printmail.ENABLED=False
try: assert A.post_choice(A.get(tk7))=="" and not A.can_post(A.get(tk7))
finally: A.printmail.ENABLED=True

# ---- 8. reminders on day 5 and day 10 after posting, once each (cron)
def cron(): return json.loads(urllib.request.urlopen(urllib.request.Request(B+"/cron/print-status",b"",{"X-Cron-Secret":KEY})).read())
rem=lambda: [m for m in mails() if m["to"]=="margaret@example.com" and "have you signed and posted" in m["subject"]]
j=job(tok); j["sent_at"]=time.time()-3*86400; A.printmail.save_job(A.db(),tok,j); cron(); time.sleep(1); assert rem()==[]
j=job(tok); j["sent_at"]=time.time()-5*86400-60; A.printmail.save_job(A.db(),tok,j); cron(); wait(lambda: len(rem())==1); cron(); time.sleep(1); assert len(rem())==1 and job(tok)["reminded"]==[5]
j=job(tok); j["sent_at"]=time.time()-10*86400-60; A.printmail.save_job(A.db(),tok,j); cron(); wait(lambda: len(rem())==2); cron(); time.sleep(1); assert len(rem())==2 and job(tok)["reminded"]==[5,10]
assert "sign and date it in black ink in the boxes listed on the cover sheet" in rem()[0]["text"] if "text" in rem()[0] else True
# ---- 9. whole-form order (NI / bank step): posting shown there, the pack is posted from that step, NI / bank kept only until it is posted
n=len(MOCK["posts"])
tk9=to_details("aa",email="wf@example.com",post=True); c=A.db(); I=json.loads(A.get(tk9)["intake"]); I["wf_v"]=1
c.execute("update orders set intake=?, personal=? where token=?",(json.dumps(I),json.dumps({k:v for k,v in DD.items() if k!="dob"}),tk9)); c.commit()
ph=body(f"/details/{tk9}"); assert "Last details for the form" in ph and "we will post your printed AA1 pack to the address on your form" in ph and "or until we post it" in ph
assert loc(req(f"/details/{tk9}",{"skip":"1"}))==f"/documents/{tk9}"
wait(lambda: len(MOCK["posts"])==n+1 and (job(tk9) or {}).get("letter_id"),30)
assert MOCK["posts"][-1]["body"]["recipients"][0]["address"]["postcode"]=="LS1 1AA" and A.SECURE.get(tk9) in (None,{})
print("PRINTMAIL ALL OK")

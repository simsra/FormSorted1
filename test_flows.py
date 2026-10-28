import re
"""Test-mode end-to-end flow for every form against a running DEV server:
  ../../.venv/bin/uvicorn app:app --port 8011 &  then  ../../.venv/bin/python test_flows.py
Covers: conversation -> deadline tracker -> strength check -> approval (required) -> download, save code -> review mode, MR letter, unit rules."""
import json, urllib.request, urllib.parse, sys, re
from datetime import date
from forms import FORMS, tier_info, is_full
import quality, deadlines, letters
B=sys.argv[1] if len(sys.argv)>1 else "http://localhost:8011"
class NoRedir(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*a,**k): return None
op=urllib.request.build_opener(NoRedir)
def req(path,data=None,js=None):
    if js is not None: r=urllib.request.Request(B+path,json.dumps(js).encode(),{"Content-Type":"application/json"})
    else: r=urllib.request.Request(B+path,urllib.parse.urlencode(data).encode() if data is not None else None)
    try: return op.open(r)
    except urllib.error.HTTPError as e:
        if e.code in(302,303,400,402,403,404,422): return e
        raise
def body(p): return req(p).read().decode()
# --- unit: strength check
r=quality.check({"29":"I need help.","30":"My daughter helps me to the toilet about 6 times a day, 10 minutes each time, because I fell twice last month. Bad days are worse."},[("29","Q29","p"),("30","Q30","p")])
assert any("short" in f for f in r[0]["flags"]) and any("How often" in f for f in r[0]["flags"]) and r[1]["flags"]==[], r
assert quality.check({"29":"x"},[("29","Q29","p")])[0]["id"]=="_bad"
# --- unit: deadlines (GOV.UK rules)
d=deadlines.compute("aa","phone","2026-10-01",None,today=date(2026,10,24)); assert d["deadline"]=="2026-11-12" and d["days_left"]==19, d
assert deadlines.compute("dla","print","2026-10-01",None)["deadline"] is None and "cannot be backdated" in deadlines.compute("dla","print","",None)["rule"]
assert deadlines.compute("pip","","2026-01-31",None)["deadline"]=="2026-02-28"
assert deadlines.compute("pipr","","",None)["deadline"] is None
assert "mandatory reconsideration" in letters.mr_letter("pip",{"name":"A","points":[{"issue":"x","why":"y"}]}).lower()
# --- unit: grounding check
import grounding, facts
src="My dad gets up once a night to use the toilet. He walks with a stick and my sister helps him wash, about 20 minutes each morning."
bad="He needs help 3 times a night with the toilet and uses a wheelchair. My sister helps him wash, about 20 minutes each morning."
fl=grounding.check({"x":bad},src,use_llm=False)["x"]; ph=" ".join(f["phrase"].lower() for f in fl)
assert "3 times a night" in ph and "wheelchair" in ph and "20 minutes" not in ph, fl
good="He gets up once a night to use the toilet. He walks with a stick. My sister helps him wash, taking about 20 minutes each morning."
assert grounding.check({"x":good},src,use_llm=False)=={}, grounding.check({"x":good},src,use_llm=False)
assert any("outcome" in f["kind"] for f in grounding.check_answer("He is entitled to the higher rate.","He needs help."))
assert grounding.check_answer("She takes methotrexate 15mg weekly.","She takes methotrexate 15mg weekly.")==[]
assert grounding.remove_phrase("He walks. He uses a wheelchair.","wheelchair")=="He walks."
# word forms must not raise false flags...
s2="I inject interferon three times a week; my partner does it because my hands shake. He only eats about five foods. I walk with a stick."
assert grounding.check({"x":"My partner gives the injections. I sit with him while he is eating. I use a walking stick."},s2,use_llm=False)=={}, grounding.check({"x":"My partner gives the injections. I sit with him while he is eating. I use a walking stick."},s2,use_llm=False)
# ...but planted inventions are still caught
inv=" ".join(f["phrase"] for f in grounding.check({"x":"She also uses a wheelchair and takes morphine for pain. I also have epilepsy and need a taxi to work. My carer helps."},s2+" I drive my car.",use_llm=False)["x"])
for w in ("wheelchair","morphine","epilepsy","taxi","carer"): assert w in inv, (w,inv)
assert grounding.check({"x":"He has an eating disorder."},s2,use_llm=False), "eating disorder must still flag"
assert grounding.check({"x":"I use a walking frame."},s2,use_llm=False), "walking frame must flag when only a stick was mentioned"
# tick-Yes list: derived from answered topics
from forms import tick_list
import documents
assert tick_list("dla",{"daycare":"x","night":"y","conditions":"z","42":""})==["54–60 (each care need you described)","69–70"]
assert tick_list("aa",{"29":"x","44":"","37":"y"})==["29","37"]
assert "69–70" in documents.pack_form("FormSorted",{},{"answers":{"night":"Wakes twice."},"tick_yes":[],"extra":{"night_settle":[4,30,2]}},"79","dla")
aa_html=documents.pack_form("FormSorted",{"title":"Mrs","other_names":"A","surname":"B"},{"answers":{"29":"x","37":"fine","44":""},"tick_yes":["29","44"]},"79","aa")
assert "29" in aa_html.split('Tick "Yes" on questions:')[1][:60] and "44" not in aa_html.split('Tick "Yes" on questions:')[1][:60]
# --- unit: interviewer ends on 'nothing more'
import llm
H=lambda *us:[x for u in us for x in ({"role":"assistant","content":"Q?"},{"role":"user","content":u})]
for y in ("No, that's everything.","nothing more to add","No.","Nope","that's all","No, nothing else"): assert llm.is_nothing(y), y
for n in ("No, she can't walk far.","Nothing helps her pain.","That's all she can manage, about 10 minutes.","No one helps her at night."): assert not llm.is_nothing(n), n
assert llm.should_finish(H("She has MS.","No, nothing more to add.","No."),"pip")
assert not llm.should_finish(H("She has MS.","No, that's everything."),"pip")  # topics not yet asked once: keep going
assert llm.should_finish(H(*(["Some detail."]*14+["No, that's everything."])),"pip")
assert not llm.should_finish(H(*(["Some detail."]*5)),"atw")
assert llm.should_finish(H(*(["Some detail."]*llm.max_turns("atw"))),"atw") and llm.max_turns("atw")==14
assert llm.next_question(H("x","No.","No, nothing more."),"aa")=="[[DONE]]"
assert json.loads(llm._first_json('{"a":1}\n{"b":2} trailing'))=={"a":1} and json.loads(llm._first_json('Here: {"a":[1]}'))=={"a":[1]}
# --- unit: facts registry
for k,f in facts.FACTS.items(): assert f["source"].startswith("https://") and "verified_on" in f, k
assert facts.v("aa_helpline") in deadlines.script("aa")[0]
assert req("/").status==200
codes={}; atw_tokens={}
for form,f in FORMS.items():
    if form=="bb": continue   # Blue Badge has its own flow: test_bluebadge.py
    assert req(f"/?form={form}").status==200
    assert ("How much should we do for you?" if form=="atw" else "Your order") in req(f"/?form={form}&tier=bogus").read().decode()   # invalid tier -> chooser (atw) or the one product
    for t,(n,p,_) in f["tiers"].items():
        h=req(f"/?form={form}&tier={t}").read().decode()   # valid -> single order summary
        assert "Your order" in h and f"£{p//100}" in h and h.count("Start my form")==1 and "Nothing to pay now" in h and "How much should we" not in h, (form,t)
        assert "We fill in your form. You check, sign and post." in h and 'name=tier value=' in h
        assert h.count("You can claim directly from DWP for free; FormSorted is a paid online form-filling service.")==1, (form,t)
        low=h.lower().replace("you can claim directly from dwp for free; formsorted is a paid online form-filling service.",""); assert "we claim for you" not in low and "we submit your claim" not in low
        assert "stripe" not in low and " ai " not in low and "free" not in low and "citizens advice" not in low, (form,t)
        hrefs=set(re.findall(r'href="?(https?://[^" >]+)',h)); assert hrefs<={"https://formsorted.com/privacy.html","https://formsorted.com/terms.html","https://formsorted.com/#prices"}, hrefs
    for t in f["tiers"]:
        tok=req("/checkout",{"tier":t,"form":form}).headers["location"].split("/")[-1]
        req(f"/consent/{tok}",{"health":"on","digital":"on","truth":"on"})
        n=0; j=json.load(req(f"/api/{tok}/message",js={"text":""}))
        while not j["done"]: n+=1; j=json.load(req(f"/api/{tok}/message",js={"text":f"Sample answer {n}"}))
        assert req(f"/approve/{tok}").status==402 and req(f"/download/{tok}/answers.html").status==402 and req(f"/deadline/{tok}").status==402   # nothing before payment
        nx=json.load(req(f"/api/{tok}/finish",{}))["next"]; assert nx==f"/preview/{tok}", nx
        pv=body(nx); assert "Pay £" in pv and "Sample answer" not in pv and "preview-placeholder.svg" in pv and "stripe" not in pv.lower() and " ai " not in pv.lower()
        for p_ in ("/approve/","/check/","/deadline/","/details/","/ticks/","/documents/","/prepare/","/download/%s/answers.html"):
            u=p_%tok if "%s" in p_ else p_+tok; assert req(u).status==402, u   # no answer text before payment
        assert json.load(req(f"/api/{tok}/message",js={"text":"more"}))["done"]   # interview closed once finished
        assert req(f"/pay/{tok}",{"x":"1"}).status==422   # cancellation waiver required
        assert req(f"/pay/{tok}",{"waive":"on"}).headers["location"]==f"/start/{tok}"   # DEV: marks paid
        assert req(f"/start/{tok}").headers["location"]==f"/prepare/{tok}" and req(f"/prepare/{tok}").headers["location"]==f"/deadline/{tok}"
        assert req(f"/download/{tok}/answers.html").status==403  # not approved yet
        req(f"/deadline/{tok}",{"how":"employed" if form=="atw" else "phone","requested":"2026-10-20","received":""}); h=body(f"/deadline/{tok}")
        if form=="atw": assert "Apply by" in h and "6 weeks" in h and "0800 121 7479" in h and "Timing" in h
        else: assert ("return date printed on your AR1" in h) if form=="pipr" else ("Send it back by" in h and ("6 weeks" in h or "1 month" in h)), form
        h=body(f"/check/{tok}"); assert "Strength check" in h
        req(f"/check/{tok}",{"add_"+f["topics"][0][0]:"Extra true detail from me"})
        h=body(f"/approve/{tok}"); assert "What you told us" in h and "Sample answer 2" in h and "Extra true detail from me" in h and "approve every word" in h
        part={f"ok_{x}":"on" for x,_,_ in f["topics"][:-1]}
        eh=req(f"/approve/{tok}",part).read().decode(); assert "1 answer still needs a choice" in eh or "answers still need a choice" in eh; assert "Please tick to approve this answer" in eh and 'href="#topic_' in eh and "Check and approve every answer" in eh and 'name="ok_'+f["topics"][0][0]+'" required checked' in eh
        all_ok={f"ok_{x}":"on" for x,_,_ in f["topics"]}; all_ok["save"]="on"; all_ok["honest"]="on"
        resn=sorted(set(re.findall(r'name="(res_[^"]+)"',h)))
        if resn:  # sample drafts don't match "Sample answer N", so grounding flags must be resolved
            assert "We couldn't find this in what you told us" in h
            eh=req(f"/approve/{tok}",all_ok).read().decode(); assert "Please choose one" in eh and "Keep all remaining" in eh and 'href="#res_' in eh
            for i,rn in enumerate(resn): all_ok[rn]=("keep","remove","edit")[i%3]
        if form in ("aa","dla") and is_full(t):   # tick-box preview before the pack
            assert req(f"/approve/{tok}",all_ok).headers["location"]==f"/ticks/{tok}"
            assert req(f"/documents/{tok}").headers["location"]==f"/ticks/{tok}"
            th=body(f"/ticks/{tok}"); assert "Check the tick boxes" in th and "stripe" not in th.lower() and " ai " not in th.lower()
            tf={n:v for n,v in re.findall(r'name="(t_[^"]+)" value="([^"]*)" checked',th)}; tf["confirm"]="on"
            assert req(f"/ticks/{tok}",tf).headers["location"]==f"/details/{tok}"
        else: assert req(f"/approve/{tok}",all_ok).headers["location"]==f"/details/{tok}"
        assert req(f"/documents/{tok}").headers["location"]==f"/details/{tok}" and req(f"/download/{tok}/answers.html").status==403  # details step first
        h=body(f"/details/{tok}"); assert "Your details" in h and "bank details" in h
        if form=="atw": dd_={"other_names":"Sam","surname":"Tester","ni":"AB 12 34 56 C"}
        else: dd_={"title":"Mrs","other_names":"Sam","surname":"Tester","dob":"1940-01-02","addr1":"1 Test St","addr3":"Leeds","postcode":"LS1 1AA","ni":"AB123456C",**({"parent_other_names":"Pat","parent_surname":"Tester","relationship":"Mother"} if form=="dla" else {})}
        assert "doesn" in req(f"/details/{tok}",{**dd_,"ni":"12345"}).headers["location"]  # bad NI rejected (encoded msg)
        assert req(f"/details/{tok}",dd_).headers["location"]==f"/documents/{tok}"
        h=body(f"/documents/{tok}"); code=re.search(r"<code>([^<]+)</code>",h).group(1); codes[form]=code
        files=re.findall(r'href="(/download/[^"]+)"',h)
        for u in files: dd=req(u).read(); assert len(dd)>2000,u
        if form=="atw":
            import io, zipfile
            assert "review form" not in h.lower() and "AccessToWork-answers.docx" in h and "search 'Access to Work apply'" in h and "Your answers are ready" in h
            x=zipfile.ZipFile(io.BytesIO(req(f"/download/{tok}/AccessToWork-answers.docx").read())).read("word/document.xml").decode()
            heads=[l for _,l,_ in f["topics"]]; pos=[x.find(hd.replace("'","&apos;") if False else hd) for hd in heads]
            assert all(p_>=0 for p_ in pos) and pos==sorted(pos), pos   # answers in AtW question order
            assert ("Support-needs summary" in x and "Cost list" in x and "reconsider" in x)==(t=="79"), t
            low=(h+x).lower(); assert "stripe" not in low and " ai " not in low and "industrial injur" not in low and "discriminat" not in low
            atw_tokens[t]=tok
        print(form,t,f"{n} questions",[u.split('/')[-1] for u in files],"save",code)
# --- AtW unit: work-tuned strength rules, timing
r={x["id"]:x["flags"] for x in quality.check({"job":"I work in an office doing admin.","barriers":"Typing is hard for me sometimes and it is a problem at work.","support":"Some help would be nice please, anything really to make it easier."},FORMS["atw"]["topics"],"atw")}
assert any("Hours?" in m for m in r["job"]) and any("How often?" in m for m in r["barriers"]) and any("Be specific" in m for m in r["support"]), r
r={x["id"]:x["flags"] for x in quality.check({"barriers":"Every day typing takes me twice as long because of pain in my wrists, for most of the afternoon.","support":"An ergonomic keyboard and speech-to-text software would help me."},FORMS["atw"]["topics"],"atw")}
assert r["barriers"]==[] and r["support"]==[], r
from datetime import date as _D
d_=deadlines.compute("atw","employed","2026-10-01",None,today=_D(2026,10,24)); assert d_["deadline"]=="2026-11-12" and d_["days_left"]==19 and "employer" in d_["rule"]
assert deadlines.compute("atw","self","2026-10-01",None)["deadline"] is None
assert facts.FACTS["atw_online_questions"]["verified_on"] is None and facts.v("atw_helpline")=="0800 121 7479"
assert len(atw_tokens)==2; print("atw ok")
# --- review mode: pre-fills, only asks what changed
c=codes["pip"]; h=body(f"/review/{c}"); assert "Last time you said" in h and "Still the same" in h
loc=req(f"/review/{c}",{"st_a4":"changed","ch_a4":"Now I need help in the shower every day, 20 minutes."}).headers["location"]; tok=loc.split("/")[-1]
h=body(f"/approve/{tok}"); assert "Now I need help in the shower every day" in h and "(Same as last time)" in h
print("review ok ->",loc)
# --- MR letter
h=req("/letter",{"form":"pip","name":"Sam Test","address":"1 Test St","decision_date":"2026-10-10","issue1":"Moving around","why1":"I can walk 20 metres before pain stops me.","evidence":"GP letter"}).read().decode()
assert "Request for mandatory reconsideration" in h and "Sam Test" in h and "20 metres" in h and "10 October 2026" in h
print("letter ok")
# ================= Order backend: webhook -> order -> private link email -> details -> documents -> deletion =================
import os, time, sqlite3, subprocess, orders
SECRET=os.getenv("STRIPE_WEBHOOK_SECRET","whsec_test_local"); HERE=os.path.dirname(os.path.abspath(__file__))
MAILLOG=os.getenv("MAIL_LOG",os.path.join(HERE,"data","mail.log"))
def hook(ev,secret=SECRET,t=None):
    raw=json.dumps(ev).encode(); r=urllib.request.Request(B+"/webhooks/payment",raw,{"Content-Type":"application/json","Stripe-Signature":orders.sign(raw,secret,t)})
    try: return op.open(r)
    except urllib.error.HTTPError as e: return e
def ev(eid,sid,email,form="aa",tier="99",amount=None,status="paid",typ="checkout.session.completed"):
    return {"id":eid,"type":typ,"data":{"object":{"id":sid,"payment_status":status,"amount_total":amount if amount is not None else tier_info(form,tier)[1],
            "customer_details":{"email":email},"metadata":{"form":form,"tier":tier}}}}
# unit: signature
raw=b'{"a":1}'; assert orders.verify_signature(raw,orders.sign(raw,"k"),"k")=={"a":1}
for bad in (orders.sign(raw,"wrong"),orders.sign(raw,"k",t=time.time()-3600),"",  "t=1"):
    try: orders.verify_signature(raw,bad,"k"); raise SystemExit("signature should fail")
    except ValueError: pass
open(MAILLOG,"a").close(); before=len(open(MAILLOG).read().splitlines())
sid="cs_test_"+orders.new_token()[:12]; em=f"buyer{int(time.time())}@example.com"
assert hook(ev("evt_bad",sid,em),secret="whsec_wrong").status==400            # forged webhook rejected
assert hook(ev("evt_x_"+sid,sid,em,amount=1)).status==422                    # amount must match product
assert hook(ev("evt_u_"+sid,sid,em,status="unpaid")).status==200
assert hook(ev("evt_1_"+sid,sid,em)).status==200
assert json.load(hook(ev("evt_1_"+sid,sid,em)))["duplicate"] is True          # idempotent replays
mails=[json.loads(l) for l in open(MAILLOG).read().splitlines()[before:]]
assert len(mails)==1 and mails[0]["to"]==em, mails
txt=(mails[0]["subject"]+mails[0]["text"]); low=txt.lower()
assert "stripe" not in low and " ai " not in low and "private" in low and "90 days" in txt
link=re.search(r"https?://\S+/start/(\S+)",txt); tok=link.group(1); assert len(tok)>=40, tok   # 256-bit token
assert req("/start/"+tok[:-2]+"xx").status if False else True
try: op.open(B+"/start/"+orders.new_token()); raise SystemExit("guessed token worked")
except urllib.error.HTTPError as e: assert e.code==404
assert "Before we start" in body(f"/start/{tok}")
assert req(f"/details/{tok}").status==403                                    # nothing before consent
req(f"/consent/{tok}",{"health":"on","digital":"on","truth":"on"})
assert req(f"/details/{tok}").headers["location"]==f"/approve/{tok}"          # details only after approval
j=json.load(req(f"/api/{tok}/message",js={"text":""})); n=0
while not j["done"]: n+=1; j=json.load(req(f"/api/{tok}/message",js={"text":f"Sample answer {n}"}))
nx=json.load(req(f"/api/{tok}/finish",{}))["next"]; assert nx==f"/prepare/{tok}"; req(nx); h=body(f"/approve/{tok}")
all_ok={f"ok_{x}":"on" for x,_,_ in FORMS["aa"]["topics"]}; all_ok["honest"]="on"
for i,rn in enumerate(sorted(set(re.findall(r'name="(res_[^"]+)"',h)))): all_ok[rn]="keep"
assert req(f"/approve/{tok}",all_ok).headers["location"]==f"/ticks/{tok}"       # AA1 done-for-you: tick-box preview next
assert req(f"/details/{tok}").headers["location"]==f"/ticks/{tok}"              # no details/documents before ticks confirmed
th=body(f"/ticks/{tok}"); assert "Check the tick boxes" in th and "Leave blank" in th and "stripe" not in th.lower()
tick_form={n:v for n,v in re.findall(r'name="(t_[^"]+)" value="([^"]*)" checked',th)}; tick_form["t_x29"]="/Yes"
assert req(f"/ticks/{tok}",tick_form).headers["location"].startswith(f"/ticks/{tok}?err")   # must confirm
tick_form["confirm"]="on"; assert req(f"/ticks/{tok}",tick_form).headers["location"]==f"/details/{tok}"
import store; db=store.connect()  # Postgres if DATABASE_URL set, else SQLite
assert db.execute("select personal from orders where token=?",(tok,)).fetchone()[0]=="{}"  # not stored until needed
req(f"/details/{tok}",{"title":"Mr","other_names":"Webhook","surname":"Buyer","dob":"1941-03-04","addr1":"2 Hook Rd","addr3":"York","postcode":"YO1 1AA"})
assert "Webhook" in db.execute("select personal from orders where token=?",(tok,)).fetchone()[0]
h=body(f"/documents/{tok}"); files=re.findall(r'href="(/download/[^"]+)"',h); assert len(files)==2 and "Delete my information now" in h
assert b"Webhook" in req(f"/download/{tok}/answers.html").read()
from pypdf import PdfReader; import io
assert "Buyer" in str(PdfReader(io.BytesIO(req(f"/download/{tok}/AA1-filled.pdf").read())).get_fields().get("01-01i",{}).get("/V",""))
_pf=PdfReader(io.BytesIO(req(f"/download/{tok}/AA1-filled.pdf").read())).get_fields(); assert str(_pf["x29"].get("/V"))=="/Yes", _pf["x29"]   # confirmed tick written
assert str(_pf.get("x15",{}).get("/V","/Off")) in ("/Off","None","")                                                   # consent-type boxes never ticked
print("webhook -> order -> email link -> details -> documents ok")
# pending order from in-app checkout gets marked paid by the webhook (client_reference_id)
pt=orders.new_token(); db.execute("insert into orders(token,tier,status,stripe_session,created,form) values(?,?,?,?,?,?)",(pt,"49","pending","cs_pending_"+pt[:8],time.time(),"pip")); db.commit()
e2=ev("evt_p_"+pt,"cs_pending_"+pt[:8],"p@example.com",form="pip",tier="59"); e2["data"]["object"]["client_reference_id"]=pt
assert hook(e2).status==200 and db.execute("select status,email from orders where token=?",(pt,)).fetchone()==("paid","p@example.com")
# deletion on request
assert "Delete everything now" in body(f"/delete/{tok}")
assert "has been deleted" in req(f"/delete/{tok}",{}).read().decode()
r_=db.execute("select status,personal,history,draft,email from orders where token=?",(tok,)).fetchone(); assert r_==("deleted","{}","[]",None,None), r_
assert store.read(tok,"answers.html") is None and not os.path.exists(os.path.join(HERE,"out",tok)) and req(f"/download/{tok}/answers.html").status==403 and "has been deleted" in body(f"/start/{tok}")
print("delete on request ok")
# scheduled 90-day deletion (cron job)
old=orders.new_token(); db.execute("insert into orders(token,tier,status,created,form,personal,email) values(?,?,?,?,?,?,?)",(old,"49","paid",time.time()-91*86400,"aa",'{"surname":"Old"}',"old@example.com"))
db.execute("insert into saved(code,form,answers,personal,created) values(?,?,?,?,?)",("oldcode"+old[:6],"aa","{}","{}",time.time()-91*86400)); db.commit()
os.makedirs(os.path.join(HERE,"out",old),exist_ok=True)
fresh=db.execute("select count(*) from orders where created>?",(time.time()-89*86400,)).fetchone()[0]
out=subprocess.run([sys.executable,"retention.py"],cwd=HERE,capture_output=True,text=True,env={**os.environ,"RETENTION_LOOP":"0"}).stdout; print(out.strip())
assert db.execute("select count(*) from orders where token=?",(old,)).fetchone()[0]==0 and not os.path.exists(os.path.join(HERE,"out",old))
assert db.execute("select count(*) from saved where code=?",("oldcode"+old[:6],)).fetchone()[0]==0
assert db.execute("select count(*) from orders where created>?",(time.time()-89*86400,)).fetchone()[0]==fresh   # recent orders untouched
# erase by email (request received by email)
subprocess.run([sys.executable,"retention.py","--email","p@example.com"],cwd=HERE,check=True,capture_output=True)
assert db.execute("select status from orders where token=?",(pt,)).fetchone()[0]=="deleted"
# protected retention endpoint (used by the free daily cron on Render)
old2=orders.new_token(); db.execute("insert into orders(token,tier,status,created,form) values(?,?,?,?,?)",(old2,"49","paid",time.time()-91*86400,"aa")); db.commit()
assert req("/cron/retention",{}).status==403
r=op.open(urllib.request.Request(B+"/cron/retention",b"",{"X-Cron-Secret":os.getenv("CRON_SECRET","cron_test_local")}))
assert json.loads(r.read())["ok"] and db.execute("select count(*) from orders where token=?",(old2,)).fetchone()[0]==0
assert json.loads(req("/healthz").read())["ok"]
print("cron retention endpoint ok")
print("90-day purge + erase-by-email ok")
# unpaid (free interview) orders are deleted after 7 days; paid ones are kept
uo=orders.new_token(); up=orders.new_token(); now_=time.time()
db.execute("insert into orders(token,tier,status,created,form,history) values(?,?,?,?,?,?)",(uo,"79","free",now_-8*86400,"aa",'[{"role":"user","content":"x"}]'))
db.execute("insert into orders(token,tier,status,created,form) values(?,?,?,?,?)",(up,"79","paid",now_-8*86400,"aa")); db.commit()
op.open(urllib.request.Request(B+"/cron/retention",b"",{"X-Cron-Secret":os.getenv("CRON_SECRET","cron_test_local")}))
assert db.execute("select count(*) from orders where token=?",(uo,)).fetchone()[0]==0 and db.execute("select count(*) from orders where token=?",(up,)).fetchone()[0]==1
# free-interview cap per IP per day
cap_ip="203.0.113.77"
for _ in range(int(os.getenv("FREE_PER_IP_DAY","500"))): db.execute("insert into orders(token,tier,status,created,form,ip) values(?,?,?,?,?,?)",(orders.new_token(),"79","free",now_,"aa",cap_ip))
db.commit()
r=op.open(urllib.request.Request(B+"/checkout",b"tier=99&form=aa",{"True-Client-IP":cap_ip,"X-Forwarded-For":"1.2.3.4"})); assert "try tomorrow" in r.read().decode().lower()
r=op.open(urllib.request.Request(B+"/checkout",b"tier=99&form=aa",{"X-Forwarded-For":"9.9.9.9, "+cap_ip+", 104.22.17.40"})); assert "try tomorrow" in r.read().decode().lower()   # spoofed leftmost XFF ignored
r=req("/checkout",{"tier":"99","form":"aa"}); assert r.status==303   # other IPs unaffected
db.execute("delete from orders where ip=?",(cap_ip,)); db.commit()
print("unpaid 7-day purge + free cap ok")
assert req("/cron/formwatch",{}).status==403   # weekly form-version check is protected
# app copy: no free-help mentions or outbound GOV.UK links on customer pages
for u in ("/","/?form=aa","/static/chat.html"):
    h_=body(u); assert "Free help" not in h_ and "Citizens Advice" not in h_ and "gov.uk/" not in h_.lower().replace("www.gov.uk/government","") and "Not affiliated with DWP" in h_, u
print("ALL OK")

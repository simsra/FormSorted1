"""Evidence + honesty + review holds (Oct 2026). Units run offline; e2e needs a DEV server with its own fresh SQLITE_PATH and MAIL_LOG,
real fraud thresholds (defaults) and CRON_SECRET=cron_test_local:  MAIL_LOG=... python test_evidence.py http://localhost:8054
1 evidence question on the uploads screen + checklist   2 document cross-check (/confirm, nothing added unless confirmed)
3 contradiction questions (max 3) + tighter drafting/grounding   4 honesty line + required declaration tick
5 holds (same source / near-identical answers), neutral hold page, hello@ email, refusals, admin release/refund."""
import json, os, re, sys, sqlite3, time, uuid, urllib.request, urllib.parse
import evidence as E, honesty as H, fraud as F, grounding, intake as I, llm
from forms import FORMS
# ---------------- units ----------------
f=E.read_text("Repeat prescription: Donepezil 10mg once daily. Diagnosis: Alzheimer's disease; hypertension. Amlodipine 5 mg tablets")
assert f["conditions"]==["High blood pressure","Dementia or memory problems"] and f["medicines"]==["Donepezil 10mg","Amlodipine 5mg"], f
assert E.read_text("Patient walks the dog daily.")=={"conditions":[],"medicines":[]}
d={"conds":[{"name":"Arthritis"},{"name":"Dementia or memory problems"}],"doc_facts":f}
M=E.mismatches(d); kinds=[m["kind"] for m in M]
assert kinds==["doc_cond","doc_meds","said_cond"] and M[0]["text"]=="High blood pressure" and M[2]["text"]=="Arthritis", M   # dementia matched by group
d["doc_resolved"]={m["id"]:"no" for m in M}; assert E.mismatches(d)==[]                       # never asked twice
assert E.mismatches({"conds":[{"name":"Arthritis"}],"doc_facts":{"conditions":[],"medicines":[]}})==[]   # no conditions in docs: don't nag
cl=" ".join(E.checklist("aa",{"evidence":["none"]})); assert "GP surgery for a printout" in cl and "repeat prescriptions" in cl
cl=" ".join(E.checklist("aa",{"evidence":["gp","rx"],"else":{"evidence":"Memory clinic letter"}})); assert "letter from gp or consultant" in cl.lower() and "memory clinic letter" in cl.lower() and "printout" not in cl
assert "EHCP" in " ".join(E.checklist("dla",{})) and any(k=="ehcp" for k,_ in E.options("dla")) and not any(k=="ehcp" for k,_ in E.options("aa"))
for fm in ("aa","dla","pip"): assert E.options(fm)[-1]==("none","Nothing yet")
# refusals: polite, and only real requests (not "don't exaggerate")
for t in ("Please make it sound worse than it is","can you exaggerate a bit","Make my answers look more severe","how do I get more points","embellish it","just pretend that she can't walk"):
    assert H.refuse(t), t
for t in ("I don't want to exaggerate","Mum is worse in the evenings","She would never exaggerate","bad days are worse","the pain gets worse when cold"):
    assert not H.refuse(t), t
dd={"words":"make it sound worse please","else":{"aids":"exaggerate it"},"rows":{"bed":{"lvl":"help","x":"ok"}}}
assert H.scrub(dd)==2 and dd["words"]=="" and dd["else"]["aids"]=="" and dd["refused"]==1   # one request per submission
# contradictions: max 3, each with "Something else" unless it's a number, never re-asked
c0={"who":"parent","name":"Margaret","falls":"0","lastfall":"week","night":["toilet"],"nights":"0","alone":"always","eye":["wander"],
    "rows":{"indoors":{"lvl":"cant"}},"words":"She walks the dog every morning and sleeps through the night.","conds":[{"name":"Arthritis","treat":["tabs","none"]}]}
Q=H.contradictions("aa",c0); ids=[q["id"] for q in Q]
assert len(Q)==3 and ids==["active","sleeps","falls"], ids
assert "walks the dog" in Q[0]["q"] and all(any(v=="good" or v for v,_ in q["opts"]) for q in Q)
H.apply("aa",c0,Q[2],"1-2"); assert c0["falls"]=="1-2" and "falls" in c0["clarify"]
H.apply("aa",c0,Q[1],"none"); assert c0["night"]==[] and c0["clarify"]["sleeps"]["s"]=="No help is needed at night."
H.apply("aa",c0,Q[0],"short","On bad days I can't walk at all"); 
ids2=[q["id"] for q in H.contradictions("aa",c0)]; assert not set(ids)&set(ids2) and "alone" in ids2 and "treat0" in ids2, ids2
_,T=I.topic_texts("aa",c0); assert "Checked with you: Walking: they can walk a short way" in T["33"] and "On bad days I can't walk at all" in T["33"] and "Checked with you: No help is needed at night." in T["42"], T
assert H.contradictions("aa",{"who":"me","falls":"3-5"})==[]
# drafting / grounding prompts tightened; stronger-than-your-words flags
ds=llm.draft_system("aa"); assert "Never describe a worst day or a bad day as every day" in ds and "Checked with you:" in ds and "more severe, more frequent or more absolute" in ds
assert "more severe, more frequent or more absolute than the SOURCE" in llm.GROUNDING_PROMPT
fl=grounding.check_answer("I am completely unable to cook and it is impossible for me to dress.","I find cooking hard. Dressing takes a long time.")
assert {x["phrase"].lower() for x in fl if x["kind"]=="stronger than your words"}>={"completely","impossible"}, fl
assert not [x for x in grounding.check_answer("I can never cook safely.","I can never cook safely.") if x["kind"]=="stronger than your words"]
# medicines confirmed reach the transcript; documents alone never do
_,T=I.topic_texts("pip",{"who":"me","meds_confirmed":["Sertraline 50mg"]}); assert "Sertraline 50mg" in T["conditions"]
_,T=I.topic_texts("pip",{"who":"me","doc_facts":{"medicines":["Sertraline 50mg"]}}); assert "Sertraline" not in str(T)
# holds
db=sqlite3.connect(":memory:"); db.row_factory=sqlite3.Row
db.execute("create table orders(token text,form text,tier text,status text,created real,email text,ip text,stripe_customer text,card_fp text,personal text,intake text,review_of text,hold text)")
def add(tok,name,ip="1.1.1.1",intake=None,email=None,card=None):
    db.execute("insert into orders values(?,?,?,?,?,?,?,?,?,?,?,?,?)",(tok,"aa","49","paid",time.time(),email,ip,None,card,json.dumps({"other_names":name}) if name else "{}",json.dumps(intake or {}),None,None))
    return db.execute("select * from orders where token=?",(tok,)).fetchone()
add("t1","Margaret"); add("t2","Margaret Smith"); o=add("t3","John")
assert F.assess(db,o)==[]                                                   # 2 different people from one connection: fine
o=add("t4","Ann"); r=F.assess(db,o); assert r and "internet connection" in r[0] and "3 different people" in r[0], r
o=add("c1","Ann",ip="9.9.9.1",card="fp1"); add("c2","Bob",ip="9.9.9.2",card="fp1"); o=add("c3","Cy",ip="9.9.9.3",card="fp1")
assert any("same card" in x for x in F.assess(db,o))
S={"rows":{k:{"lvl":"help","c":["a","b"],"days":"5"} for k in ("bed","toilet","wash","dress","indoors","eat")},"falls":"3-5","alone":"lt1","conds":[{"name":"Arthritis"}]}
add("s1","Peter",ip="8.8.8.1",intake=S); o=add("s2","Paul",ip="8.8.8.2",intake=S)
r=F.assess(db,o); assert r and "answers 100% the same" in r[0], r
db.execute("delete from orders where token='s2'"); o=add("s3","Peter Jones",ip="8.8.8.3",intake=S); assert not [x for x in F.assess(db,o) if "the same as" in x]   # same person
S2=json.loads(json.dumps(S)); S2["rows"]["bed"]={"lvl":"ok"}; S2["rows"]["eat"]={"lvl":"cant"}; S2["falls"]="0"
o=add("s4","Quinn",ip="8.8.8.4",intake=S2); assert not [x for x in F.assess(db,o) if "the same as" in x]
o=add("r1","Rhoda",ip="7.7.7.1",intake={"refused":1}); assert not F.assess(db,o)
o=add("r2","Rhona",ip="7.7.7.2",intake={"refused":2}); r=F.assess(db,o); assert r and "asked us to exaggerate 2 times" in r[0], r
assert all(len(q["opts"]) and "noelse" not in q for q in H.contradictions("aa",{"who":"parent","name":"M","falls":"0","lastfall":"week","night":["toilet"],"nights":"0","alone":"always","eye":["wander"],"conds":[{"name":"Arthritis","treat":["tabs","none"]}]},limit=9))
c1={"who":"parent","name":"M","falls":"0","lastfall":"week","conds":[{"name":"Arthritis","treat":["tabs","none"]}]}
q=[x for x in H.contradictions("aa",c1) if x["id"]=="treat0"][0]; H.apply("aa",c1,q,"","She stopped the tablets in May"); assert c1["conds"][0]["treat"]==["tabs","none"] and c1["clarify"]["treat0"]["s"]=="She stopped the tablets in May." and c1["clarify"]["treat0"]["v"]=="else"
print("evidence/honesty/hold units ok")
if len(sys.argv)<2: sys.exit(0)
# ---------------- e2e ----------------
B=sys.argv[1].rstrip("/"); KEY=os.getenv("CRON_SECRET","cron_test_local"); MAIL=os.environ["MAIL_LOG"]
class NoRedir(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*a,**k): return None
op=urllib.request.build_opener(NoRedir)
def req(path,data=None,raw=None,ctype=None,ip=None):
    h={"true-client-ip":ip} if ip else {}
    if raw is not None: h["Content-Type"]=ctype; r=urllib.request.Request(B+path,raw,h)
    else: r=urllib.request.Request(B+path,urllib.parse.urlencode(data,doseq=True).encode() if data is not None else None,h)
    try: return op.open(r)
    except urllib.error.HTTPError as e:
        if e.code in(302,303,400,402,403,404,409,422): return e
        raise
def body(p): return req(p).read().decode()
def loc(r): return r.headers["location"]
def multipart(fields,files=()):
    b=uuid.uuid4().hex; out=b""
    for n,v in fields: out+=f'--{b}\r\nContent-Disposition: form-data; name="{n}"\r\n\r\n{v}\r\n'.encode()
    for n,(fn,ct,data) in files: out+=f'--{b}\r\nContent-Disposition: form-data; name="{n}"; filename="{fn}"\r\nContent-Type: {ct}\r\n\r\n'.encode()+data+b"\r\n"
    return out+f"--{b}--\r\n".encode(),f"multipart/form-data; boundary={b}"
def tiny_pdf(text):
    from fpdf import FPDF
    p=FPDF(); p.add_page(); p.set_font("Helvetica",size=12); p.cell(0,10,text); return bytes(p.output())
def mails(): return [json.loads(l) for l in open(MAIL)] if os.path.exists(MAIL) else []
def clean(h): return h.replace("&#x27;","'").replace("&#39;","'")
def no_links(h): assert not set(re.findall(r'href="?(https?://[^" >]+)',h))-{"https://formsorted.com/privacy.html","https://formsorted.com/terms.html"}, h[:300]
def no_words(h): low=h.lower(); assert " ai " not in low and "stripe" not in low and "we claim" not in low and "we submit" not in low and "fraud" not in low
DAILY=[{"bad":"3","r_bed_lvl":"cant","r_bed_c":["out"],"r_bed_days":"7","r_wash_lvl":"help","r_wash_c":["in"],"r_wash_days":"5","r_indoors_lvl":"slow","r_indoors_c":["stairs"]},
 {"bad":"5","r_toilet_lvl":"help","r_toilet_c":["onoff"],"r_toilet_days":"4","r_dress_lvl":"slow","r_eat_lvl":"help","r_eat_c":["cut"]},
 {"bad":"1","r_meds_lvl":"help","r_meds_c":["forget"],"r_meds_days":"7","r_comm_lvl":"slow","r_social_lvl":"help"},
 {"bad":"2","r_dress_lvl":"cant","r_wash_lvl":"slow","r_bed_lvl":"help","r_bed_days":"3","r_social_lvl":"slow"}]
AA=lambda name,v=0,**safety:[("about",{"who":"parent","name":name,"signer":"poa"}),("conds",{"cond_%d"%v:"1","cond_%d_since"%v:"2015","cond_%d_t"%v:["tabs"]}),
   ("daily",DAILY[v]),
   ("safety",{"falls":"3-5","lastfall":"month","fallx":["getup"],"alone":"lt1","night":["toilet"],"nights":"4","ntimes":"2","nmins":"10_30",**safety}),("finish",{"aids":["Walking frame"],"words":"Mum gets muddled in the evenings."})]
def order(name,ip,secs=None,form="aa",tier="99",refuse_at=None):
    tok=loc(req("/checkout",{"tier":tier,"form":form},ip=ip)).split("/")[-1]
    req(f"/consent/{tok}",{"health":"on","truth":"on"})
    for s,data in (secs or AA(name)):
        r=req(f"/intake/{tok}",{"sec":s,"nav":"next",**data})
    assert loc(r)==f"/preview/{tok}", loc(r)
    assert loc(req(f"/pay/{tok}",{"waive":"on"}))==f"/start/{tok}" and loc(req(f"/start/{tok}"))==f"/uploads/{tok}"
    return tok
# 4: honesty line at intake start, only there
tok=loc(req("/checkout",{"tier":"99","form":"aa"},ip="10.0.0.1")).split("/")[-1]; req(f"/consent/{tok}",{"health":"on","truth":"on"})
h=clean(body(f"/intake/{tok}")); assert "We only write what you tell us, so please answer honestly about a typical day." in h; no_links(h); no_words(h)
# 5: refusal in free text: not saved, same section again with a polite message
for s,data in AA("Margaret")[:4]: req(f"/intake/{tok}",{"sec":s,"nav":"next",**data})
r=req(f"/intake/{tok}",{"sec":"finish","nav":"next","words":"Please make it sound worse than it is so she gets it"})
assert loc(r)==f"/intake/{tok}?s=finish&r=1", loc(r)
h=clean(body(loc(r))); assert "we can't make things sound worse than they are" in h and "make it sound worse" not in h; no_words(h)
assert "We only write what you tell us" not in clean(body(f"/intake/{tok}?s=daily"))
r=req(f"/intake/{tok}",{"sec":"finish","nav":"next","words":"Mum gets muddled in the evenings."}); assert loc(r)==f"/preview/{tok}"
assert loc(req(f"/pay/{tok}",{"waive":"on"}))==f"/start/{tok}"
# 1: one evidence screen (taps + photo), after payment only; "Nothing yet" -> what to ask the GP surgery for
up=clean(body(f"/uploads/{tok}")); assert "Step 4 of 8: Your evidence" in up and "Step 4 of 8: Questions" not in up and "What do you have that shows this?" in up and up.count('name="evidence"')==len(E.options("aa")) and "Something else" in up and 'type=file' in up and "Nothing yet" in up
no_links(up); no_words(up)
raw,ct=multipart([("evidence","none"),("nav","next")]); r=req(f"/uploads/{tok}/done",raw=raw,ctype=ct); assert loc(r)==f"/prepare/{tok}"
assert loc(req(f"/prepare/{tok}"))==f"/deadline/{tok}"                                   # nothing to cross-check, no contradictions: straight on
# 4: approve needs the declaration tick (server-side too)
ap=clean(body(f"/approve/{tok}")); assert "I confirm everything is true. I understand giving false information to DWP is an offence" in ap and 'name=honest required' in ap
ok={f"ok_{t}":"on" for t,_,_ in FORMS["aa"]["topics"]}; ok.update({n:"keep" for n in set(re.findall(r'name="(res_[^"]+)"',ap))})
e=req(f"/approve/{tok}",ok); assert e.status==200; eh=clean(e.read().decode()); assert "Please tick to confirm everything is true" in eh and 'href="#honest"' in eh
ok["honest"]="on"; assert loc(req(f"/approve/{tok}",ok)) in (f"/ticks/{tok}",f"/details/{tok}")
r=req(f"/details/{tok}")
if r.status==303 and loc(r)==f"/ticks/{tok}":
    th=body(f"/ticks/{tok}"); tf={n:v for n,v in re.findall(r'name="(t_[^"]+)" value="([^"]*)" checked',th)}; tf["confirm"]="on"; req(f"/ticks/{tok}",tf)
assert loc(req(f"/details/{tok}",{"other_names":"Margaret","surname":"Evans","dob":"1940-01-01","addr1":"1 High St","addr3":"Leeds","postcode":"LS1 1AA"}))==f"/documents/{tok}"
ans=clean(body(f"/download/{tok}/answers.html")); assert "GP surgery for a printout" in ans and "repeat prescriptions" in ans, "checklist tells them what to get"
print("e2e: honesty line, refusal, evidence 'Nothing yet' checklist, declaration tick ok")
# 2: document cross-check: found conditions/medicines are offered, only confirmed ones are used
tok=order("Margaret","10.0.0.2")
raw,ct=multipart([("evidence","rx"),("evidence","gp"),("nav","next")],[("files",("letter.pdf","application/pdf",tiny_pdf("Diagnosis: hypertension. Medication: Amlodipine 5mg, Ramipril 2.5mg")))])
assert loc(req(f"/uploads/{tok}/done",raw=raw,ctype=ct))==f"/prepare/{tok}"
assert loc(req(f"/prepare/{tok}"))==f"/confirm/{tok}"
cf=clean(body(f"/confirm/{tok}")); no_links(cf); no_words(cf)
assert "Quick check before we write" in cf and "High blood pressure" in cf and "Amlodipine 5mg, Ramipril 2.5mg" in cf and "Arthritis" in cf and "Something else" in cf
assert 'name="addc"' in cf and 'checked' not in cf.split('name="addc"')[1][:80]                    # unticked by default
dc=re.findall(r'name="addc" value="(\w+)"',cf); dm=re.findall(r'name="(dm_\w+)" value="no"',cf); kc=re.findall(r'name="keepc" value="(\w+)"',cf)
assert loc(req(f"/confirm/{tok}",{"addc":dc,dm[0]:"no","keepc":kc}))==f"/prepare/{tok}"
assert loc(req(f"/prepare/{tok}"))==f"/deadline/{tok}"
def row(t):
    import store; return store.connect().execute("select * from orders where token=?",(t,)).fetchone()   # same DB as the server (SQLite or Postgres)
o=row(tok); hist=" ".join(m["content"] for m in json.loads(o["history"]) if m["role"]=="user"); dr=json.loads(o["draft"])
assert "High blood pressure" in hist and "Arthritis" in hist and "Amlodipine" not in hist and "Ramipril" not in hist, hist   # what drafting saw
assert "High blood pressure" in [c["name"] for c in dr["conditions"]] and "Amlodipine" not in json.dumps(dr["conditions"])
print("e2e: document cross-check ok")
# 3: contradiction questions before drafting (max 3), answers used, never re-asked
secs=AA("Margaret",falls="0",lastfall="week"); secs[-1]=("finish",{"words":"She walks the dog every morning."})
tok=order("Margaret","10.0.0.3",secs)
raw,ct=multipart([("nav","next")]); assert loc(req(f"/uploads/{tok}/done",raw=raw,ctype=ct))==f"/prepare/{tok}"
assert loc(req(f"/prepare/{tok}"))==f"/confirm/{tok}"
cf=clean(body(f"/confirm/{tok}")); assert "You said no falls in the last year, but also told us about a recent fall" in cf and cf.count("<fieldset")<=3 and "Step 4 of 8: Quick check" in cf
assert cf.count('_xon')==cf.count("<fieldset") and 'name="q_falls_xon"' in cf and 'name="q_falls_x"' in cf   # every quick-check question has Something else
e=req(f"/confirm/{tok}",{}); assert "err=" in loc(e)                                                # must answer
assert loc(req(f"/confirm/{tok}",{"q_falls":"1-2"}))==f"/prepare/{tok}" and loc(req(f"/prepare/{tok}"))==f"/deadline/{tok}"
ap=clean(body(f"/approve/{tok}")); assert "1 to 2 falls in the last year" in ap and "No falls in the last year" not in ap
assert json.loads(row(tok)["intake"])["clarify"]["falls"]["v"]=="1-2" and "/confirm/" not in loc(req(f"/start/{tok}"))
# answered only with Something else, in their own words
secs=AA("Margaret",falls="0",lastfall="week"); tok=order("Margaret","10.0.0.4",secs)
raw,ct=multipart([("nav","next")]); req(f"/uploads/{tok}/done",raw=raw,ctype=ct); assert loc(req(f"/prepare/{tok}"))==f"/confirm/{tok}"
assert loc(req(f"/confirm/{tok}",{"q_falls_xon":"1","q_falls_x":"One fall at Christmas, none since"}))==f"/prepare/{tok}" and loc(req(f"/prepare/{tok}"))==f"/deadline/{tok}"
hist=" ".join(m["content"] for m in json.loads(row(tok)["history"]) if m["role"]=="user"); assert "Checked with you: One fall at Christmas, none since." in hist, hist
print("e2e: contradiction check (incl. Something else) ok")
# 5: holds: 3rd different claimant from one connection -> held before drafting, neutral page, hello@ emailed
n0=len(mails()); toks=[]
for v,nm in ((1,"Alice"),(2,"Brenda"),(3,"Carol")):
    t=order(nm,"10.9.9.9",AA(nm,v,falls=["1-2","1-2","6+"][v-1],lastfall=["months","year","week"][v-1],alone=["always","hours","never"][v-1])); raw,ct=multipart([("nav","next")]); req(f"/uploads/{t}/done",raw=raw,ctype=ct); toks.append(t)
    nx=loc(req(f"/prepare/{t}")); assert nx==(f"/hold/{t}" if v==3 else f"/deadline/{t}"), (nm,nx)
held=toks[2]
hp=clean(body(f"/hold/{held}")); assert "We're checking your order" in hp and "We'll email you shortly" in hp; no_links(hp); no_words(hp)
for p in ("/deadline/","/approve/","/details/","/documents/","/check/"): assert loc(req(p+held))==f"/hold/{held}", p
assert loc(req(f"/start/{held}"))==f"/prepare/{held}" and req(f"/download/{held}/answers.html").status==403
assert json.load(req(f"/api/{held}/progress"))["next"]==f"/hold/{held}"
time.sleep(0.5); m=[x for x in mails()[n0:] if x["to"]=="hello@formsorted.com"]; assert m and "held" in m[0]["subject"].lower() and "3 different people" in m[0]["text"] and held in m[0]["text"], m
# admin: key required; release carries on
assert req("/admin").status==200 and req("/admin/held",{"key":"wrong"}).status==403 and req(f"/admin/release/{held}",{"key":"nope"}).status==403
ad=req("/admin/held",{"key":KEY}).read().decode(); assert held in ad and "3 different people" in ad and "Release" in ad and "Refund" in ad
assert "Released" in req(f"/admin/release/{held}",{"key":KEY}).read().decode()
for _ in range(30):
    if loc(req(f"/prepare/{held}"))==f"/deadline/{held}": break
    time.sleep(0.2)
assert loc(req(f"/prepare/{held}"))==f"/deadline/{held}"
# near-identical answers for a different claimant from elsewhere -> held; admin refund -> cancelled page, answers gone
dup=order("Zara","10.7.7.7",AA("Zara",2,falls="1-2",lastfall="year",alone="hours")); raw,ct=multipart([("nav","next")]); req(f"/uploads/{dup}/done",raw=raw,ctype=ct)
assert loc(req(f"/prepare/{dup}"))==f"/hold/{dup}"
time.sleep(0.3); assert any("% the same as order" in x["text"] for x in mails() if x["to"]=="hello@formsorted.com")
assert "Refunded" in req(f"/admin/refund/{dup}",{"key":KEY}).read().decode()
rp=clean(body(f"/start/{dup}")); assert "Your order has been cancelled" in rp and "refunded" in rp; assert req(f"/prepare/{dup}").status==403
# more than one refused request to exaggerate -> held for review (not rejected)
n0=len(mails()); tok=loc(req("/checkout",{"tier":"99","form":"aa"},ip="10.6.6.6")).split("/")[-1]; req(f"/consent/{tok}",{"health":"on","truth":"on"})
for s,data in AA("Edna")[:4]: req(f"/intake/{tok}",{"sec":s,"nav":"next",**data})
assert loc(req(f"/intake/{tok}",{"sec":"finish","nav":"next","words":"Please exaggerate it a bit"})).endswith("&r=1")
assert loc(req(f"/intake/{tok}",{"sec":"finish","nav":"next","words":"Mum gets muddled."}))==f"/preview/{tok}"
assert loc(req(f"/pay/{tok}",{"waive":"on"}))==f"/start/{tok}"; req(f"/start/{tok}")
raw,ct=multipart([("evidence_xon","1"),("evidence_x","make it look more severe please"),("nav","next")]); assert "err=" in loc(req(f"/uploads/{tok}/done",raw=raw,ctype=ct))
raw,ct=multipart([("evidence","none"),("nav","next")]); req(f"/uploads/{tok}/done",raw=raw,ctype=ct)
assert loc(req(f"/prepare/{tok}"))==f"/hold/{tok}"
time.sleep(0.5); assert any("asked us to exaggerate 2 times" in x["text"] and tok in x["text"] for x in mails()[n0:] if x["to"]=="hello@formsorted.com")
assert "Released" in req(f"/admin/release/{tok}",{"key":KEY}).read().decode()
for _ in range(30):
    if loc(req(f"/prepare/{tok}"))==f"/deadline/{tok}": break
    time.sleep(0.2)
assert loc(req(f"/prepare/{tok}"))==f"/deadline/{tok}"
print("e2e: holds, hold page, review email, admin release + refund, refusal hold ok")

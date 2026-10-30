"""'Ask a question?' helper: offline checks (no network). Personal details stripped, do-the-work refused, no key -> graceful,
limits, reply copy rules, logging (no IP), purge, admin top list. Run: python3 test_ask.py"""
import os, tempfile, time
d=tempfile.mkdtemp(); os.environ.update(SQLITE_PATH=os.path.join(d,"t.db"),OUT_DIR=os.path.join(d,"out"),DATABASE_URL="",SUPABASE_URL="")
os.environ.pop("GEMINI_API_KEY",None); os.environ.pop("ASK_MOCK",None)
import store, ask
c=store.connect(); ok=True
def check(name,cond):
    global ok; print(("ok   " if cond else "FAIL ")+name); ok=ok and bool(cond)
s=ask.scrub("NI AB 12 34 56 C, ring 07700 900123 or +44 20 7946 0958, jo.b@example.co.uk, LS6 2RX. My name is Mary Smith. Mrs Jones")
check("scrub NI/phone/email/postcode/name", all(x not in s for x in ("AB 12","07700","7946","jo.b","LS6","Mary","Jones")))
check("scrub keeps prices", ask.scrub("Is it £99 or £199?")=="Is it £99 or £199?")
r=ask.answer(c,"Can you fill in my form for me?","/","ip1"); check("refuse fill in (no model call)", r["status"]=="refused" and r["choose"] and "Choose your form" in r["answer"])
for q in ("Please write my supporting statement","Can you draft an appeal letter","What should I put for washing?","answer the questions for me"):
    check("refuse: "+q, ask.answer(c,q,"/","ip-"+q)["status"]=="refused")
check("no refusal for price question", not ask._WORK.search("Will you answer my questions about price?"))
r=ask.answer(c,"How much is it?","/","ip2"); check("no key -> unavailable, no error", r["status"]=="unavailable" and "hello@formsorted.com" in r["answer"])
check("too long", ask.answer(c,"x"*301,"/","ip3")["status"]=="too_long")
check("empty", ask.answer(c,"  ","/","ip3")["status"]=="empty")
os.environ["ASK_MOCK"]="1"
res=[ask.answer(c,"How much is it?","/","ip9")["status"] for _ in range(ask.PER_MIN+1)]
check("rate limit per IP per minute", res[-1]=="slow" and res[0]=="answered")
check("other IP not limited", ask.answer(c,"How much?","/","ip10")["status"]=="answered")
check("unknown in mock", ask.answer(c,"Can I pay my council tax?","/","ip11")["status"]=="unknown")
ask._set_spend(c,{"day":ask._today(),"usd":ask.BUDGET+1,"n":1}); check("daily cost cap", ask.answer(c,"How much?","/","ip12")["status"]=="busy"); ask._set_spend(c,{"day":ask._today(),"usd":0,"n":0})
cr=ask.clean_reply
check("reply: bans AI/Google/Stripe", cr("This AI answer")is None and cr("Paid via Stripe")is None and cr("Ask Google")is None)
check("reply: bans links", cr("See www.gov.uk for rates") is None and cr("Visit https://x.com") is None)
check("reply: allows our email", cr("Please email hello@formsorted.com.")=="Please email hello@formsorted.com.")
check("reply: 'free' only in DWP line / Freepost", cr("It is free.") is None and cr("You can claim directly from DWP for free.") and cr("With a Freepost envelope."))
check("reply: bans 'we submit'/'we claim'", cr("We submit it to DWP.") is None and cr("We claim for you.") is None)
check("reply: Blue Badge page words", cr("We can't guarantee an award.","/blue-badge-help") is None and cr("We can't guarantee an award.","/"))
check("reply: length cap", len(cr("Short sentence. "*80))<=ask.MAX_REPLY)
ask.answer(c,"My NI is AB123456C, how much?","/pip-form-help","ip13")
rows=c.execute("select * from ask_log").fetchall(); cols=rows[0].keys()
check("log columns: no ip/name/email", set(cols)=={"id","ts","page","question","status","topic"})
check("log stores scrubbed text", not any("AB123456C" in r["question"] for r in rows) and any("[NI number removed]" in r["question"] for r in rows))
check("log rows for refused/answered/unavailable", {"refused","answered","unavailable"}<={r["status"] for r in rows})
c.execute("update ask_log set ts=? where question like ?",(time.time()-91*86400,"%council tax%")); c.commit()
n=ask.purge(c); check("purge after 90 days", n==1 and not c.execute("select 1 from ask_log where question like ?",("%council tax%",)).fetchone())
t=ask.top(c,days=90); check("top questions", t["questions"][0]["n"]>=ask.PER_MIN and t["total"]>0)
print("ALL OK" if ok else "FAILED"); raise SystemExit(0 if ok else 1)

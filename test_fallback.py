"""28 Oct: tap orders get grounded sentences from the taps when drafting fails (and in MOCK runs); 34-4 filled when x34-3 is Yes."""
import os, json, tempfile, time
T=tempfile.mkdtemp(); os.environ.update(SQLITE_PATH=T+"/o.db", OUT_DIR=T+"/out", DATABASE_URL="", SUPABASE_URL="")
import intake as I, grounding as G, fill_pdf, llm
from pypdf import PdfReader
AA={"wf_v":1,"who":"parent","name":"Margaret","signer":"poa","conds":[{"name":"Arthritis","since":"2015","treat":["tabs"]}],
    "rows":{"bed":{"lvl":"ok"},"toilet":{"lvl":"help","c":["onoff","prompt"],"days":"7","std":[],"freq":"","time":"","x":""},
            "comm":{"lvl":"slow","c":["und"],"days":"5","std":[],"freq":"","time":"","x":""}},
    "falls":"3-5","lastfall":"month","fallx":["getup","alarm"],"eye":["confused","danger"],"alone":"lt1","night":["toilet"],"nights":"6","ntimes":"2","nmins":"10_30","watch":"most"}
DLA={"wf_v":1,"name":"Leo","rel":"Mum","age":"5to15","rows":{"superv":{"lvl":"help","c":[],"days":"7","std":[],"freq":"","time":"","x":""},"dev":{"lvl":"ok"}},"fits":"week","varies":"varies","bad":"4"}
for form,d in (("aa",AA),("aa",dict(AA,who="me")),("dla",DLA)):
    src="\n".join(m["content"] for m in I.history(form,d) if m["role"]=="user"); fd=I.fallback_draft(form,d)
    assert fd["drafted_from"]=="taps" and any(fd["answers"].values()), form
    assert G.check(fd["answers"],src,use_llm=False)=={}, (form,G.check(fd["answers"],src,use_llm=False))   # nothing the customer didn't tap
    for t,a in fd["answers"].items(): assert "like this" not in a and ": no difficulty" not in a, (t,a)
    if form=="aa": assert fd["answers"]["29"]=="" and "bad" not in fd["answers"]["30"].lower()
print("fallback sentences grounded ok")
me=I.fallback_draft("aa",dict(AA,who="me"))["answers"]; assert me["30"].startswith("I need help") and "Someone needs to keep an eye on me" in me["40"], me
assert I.extra("aa",AA)["fall_detail"]=="Margaret can't get up after a fall without help. Margaret has a pendant alarm."
assert "fall_detail" not in I.extra("aa",dict(AA,fallx=["alarm"]))   # x34-3 not ticked: box left alone
assert I.ticks("aa",AA).get("x34-3")=="/Yes"
print("34-4 from taps ok")
# 34-4 never empty when x34-3 is Yes and we have the falls answer (e.g. the customer ticked it themselves on /ticks)
out=T+"/f.pdf"; fill_pdf.fill_form("aa",{"surname":"Test"},{"answers":{"34":"I fall about once a month."},"extra":{}},out,ticks={"x34-3":"/Yes"})
F=PdfReader(out).get_fields(); assert (F["34-4"].get("/V") or "").startswith("Please see my answer"), F["34-4"].get("/V")
fill_pdf.fill_form("aa",{"surname":"Test"},{"answers":{"34":"I fall about once a month."},"extra":{}},out)
assert not PdfReader(out).get_fields()["34-4"].get("/V")
print("34-4 guard ok")
# drafting failure on a tap order: plain sentences from the taps, not an error page
import app
c=app.db(); tok="fbtest"+str(int(time.time()))
c.execute("insert into orders(token,tier,status,created,form,consent_at,history,intake) values(?,?,?,?,?,?,?,?)",(tok,"99","paid",time.time(),"aa",time.time(),json.dumps(I.history("aa",AA)),json.dumps(AA))); c.commit()
mock,real=llm.MOCK,llm.draft
def boom(*a,**k): raise llm.LLMUnavailable("all drafting models down (test)")
try:
    llm.MOCK=False; llm.draft=boom; app._draft_now(tok)
finally: llm.MOCK,llm.draft=mock,real
d=json.loads(app.get(tok)["draft"]); assert d["drafted_from"]=="taps" and d["answers"]["30"].startswith("Margaret needs help") and d["extra"]["fall_detail"] and d["intake_ticks"]["x29"]=="/No", d
print("draft fallback ok")

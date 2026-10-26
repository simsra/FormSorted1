"""Unit tests: tick proposals, tick writing, continuation sheets, PIP sheets, form-version switch. No network."""
import io, json, os, tempfile
os.environ.setdefault("SQLITE_PATH",os.path.join(tempfile.mkdtemp(),"t.db"))
from pypdf import PdfReader
import ticks, fill_pdf, contsheet, formwatch, store
HERE=os.path.dirname(os.path.abspath(__file__))
S=json.load(open(os.path.join(HERE,"sample_case.json")))
P={x["field"]:x for x in ticks.propose("aa",S["draft"]["answers"])}
assert P["x29"]["proposed"]=="/Yes" and P["x33-2"]["proposed"]=="/Yes" and P["x34"]["proposed"]=="/Fall" and P["x34-3"]["proposed"]=="/Yes"
assert P["x40-8"]["proposed"]=="", P["x40-8"]            # "I am not confused" is not a tick
assert P["302"]["proposed"]=="" and "Not discussed" in P["302"]["why"]
assert all(f not in P for f in ("x15","x20","x15_1","358","x10"))   # consent/declaration/benefit boxes never in catalogue
# every catalogued field exists in the bundled forms with the expected state
for form in ("aa","dla"):
    o=ticks.options(form)
    for f,_,_,rule in ticks.CATALOG[form]:
        assert f in o, (form,f)
        if isinstance(rule,tuple): assert rule[1] in o[f][1], (form,f,rule[1],o[f][1])
D={x["field"]:x["proposed"] for x in ticks.propose("dla",{"outdoors":"He has no sense of danger and runs off near roads.","daycare":"He still wears nappies and needs help to dress.","42":"It varies, bad days 3 a week."})}
assert D["49"]=="/Yes" and D["49_4"]=="/No" and D["49_5"]=="/No" and D["55_7"]=="/manage nappies or pads" and D["58"]=="/Yes" and D["42"]=="/Changes from day to day" and D["65"]==""
assert ticks.validate("aa",{"x29":"/Yes","x15":"/Yes","x30":"/Bogus"})=={"x29":"/Yes"}   # only catalogued fields + real states
# fill with ticks + continuation sheets (very long answers)
long_=" ".join(f"Sentence {i}: she needs help with this every single day and it takes a long time." for i in range(120))
d=json.loads(json.dumps(S["draft"])); d["answers"]["29"]=long_; d["answers"]["31"]=long_; d["extra"]["extra_info"]=long_
out=tempfile.mktemp(suffix=".pdf")
v=fill_pdf.fill_form("aa",S["personal"],d,out,ticks={"x29":"/Yes","x34":"/Fall","x33-2":"/Yes","x15":"/Yes"})
r=PdfReader(out); f=r.get_fields()
assert str(f["x29"]["/V"])=="/Yes" and str(f["x34"]["/V"])=="/Fall" and str(f["x33-2"]["/V"])=="/Yes" and str(f.get("x15",{}).get("/V","/Off")) in ("/Off","None")
assert v["_continuation_sections"]>=1 and len(r.pages)>32, len(r.pages)
tail="".join(p.extract_text() for p in r.pages[32:])
assert "AA1 (11/25) continuation sheet" in tail and "NI number" in tail and "Sentence 119" in tail and "Mrs" in tail
assert "extra sheet" in str(f["354"]["/V"])
# all of the long text survives somewhere (box + sheets)
alltext="".join(str(f[k].get("/V","")) for k in f)+tail
assert all(f"Sentence {i}:" in alltext.replace("\n"," ") for i in (0,60,119))
# short answers: no continuation sheet
out2=tempfile.mktemp(suffix=".pdf"); v2=fill_pdf.fill_form("aa",S["personal"],S["draft"],out2)
assert len(PdfReader(out2).pages)==32 and v2["_continuation_sections"]==0
# DLA continuation + ticks
out3=tempfile.mktemp(suffix=".pdf")
v3=fill_pdf.fill_form("dla",{"surname":"Fictional","other_names":"Test Child"},{"answers":{"42":long_,"other":long_},"extra":{}},out3,ticks={"42":"/Changes from day to day","49_4":"/No"})
r3=PdfReader(out3); f3=r3.get_fields(); assert str(f3["42"]["/V"])=="/Changes from day to day" and str(f3["49_4"]["/V"])=="/No" and len(r3.pages)>40
assert "DLA1A (10/25) continuation sheet" in "".join(p.extract_text() for p in r3.pages[40:])
# PIP sheets: one page per question
b=contsheet.pip_sheets("Mr Test Fictional",[("Question 3: Preparing food","Short."),("Question 4: Eating","Short too.")])
assert len(PdfReader(io.BytesIO(b)).pages)==2
# form watch: same form -> ok; new version -> pre-fill switched off; network error -> unchanged
c=store.connect(); aa=open(os.path.join(HERE,"aa1.pdf"),"rb").read(); dla=open(os.path.join(HERE,"dla1a.pdf"),"rb").read()
page=lambda u:b'<a href="https://assets.publishing.service.gov.uk/media/x/aa1.pdf">AA1</a><a href="https://assets.publishing.service.gov.uk/media/y/dla-for-children-claim-form.pdf">DLA</a>'
def same(u): return page(u) if "gov.uk/government" in u else (aa if "aa1" in u else dla)
res=formwatch.run(c,fetch=same); assert all(x["ok"] and x["prefill_enabled"] for x in res), res
def newver(u): return page(u) if "gov.uk/government" in u else (dla if "aa1" in u else dla)   # aa1 link now serves a different PDF
res={x["form"]:x for x in formwatch.run(c,fetch=newver)}
assert res["aa"]["ok"] is False and not formwatch.prefill_enabled("aa",c) and formwatch.prefill_enabled("dla",c)
def down(u): raise OSError("offline")
res={x["form"]:x for x in formwatch.run(c,fetch=down)}; assert res["aa"]["ok"] is None and not formwatch.prefill_enabled("aa",c)   # stays off
formwatch.run(c,fetch=same); assert not formwatch.prefill_enabled("aa",c)   # never auto re-enabled
formwatch.set_disabled(c,"aa",None); assert formwatch.prefill_enabled("aa",c)
os.environ["PREFILL_DISABLED"]="dla"; assert not formwatch.prefill_enabled("dla",c); del os.environ["PREFILL_DISABLED"]
# app wiring: switched-off form -> no filled PDF and no tick step; PIP gets extra sheets
import app
o={"form":"aa","tier":"79"}; assert app.pack_files(o)==["answers.html","AA1-filled.pdf"] and app.needs_ticks(o)
formwatch.set_disabled(store.connect(),"aa",{"reason":"test"}); assert app.pack_files(o)==["answers.html"] and not app.needs_ticks(o)
formwatch.set_disabled(store.connect(),"aa",None)
assert app.pack_files({"form":"pip","tier":"59"})==["answers.html","PIP-extra-sheets.pdf"] and not app.needs_ticks({"form":"dla","tier":"49"})
import documents; h=documents.pack_form("FormSorted",{},S["draft"],"79","aa",prefill_off=True); assert "new version" in h and "stripe" not in h.lower()
print("prefill unit tests ok")

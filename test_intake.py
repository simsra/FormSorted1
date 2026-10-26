"""Intake v3 end-to-end (test mode) for AA1, DLA1A and PIP2 against a running DEV server:  python test_intake.py http://localhost:8019
Covers: tap sections -> save/resume -> locked preview (no answer text) -> 402 before payment -> pay -> uploads -> drafting ->
approve (shows taps) -> ticks prefilled from taps -> details prefilled -> documents (tick boxes + number boxes in the PDF)."""
import json, urllib.request, urllib.parse, sys, re, io, uuid
import intake as I
from forms import FORMS
B=sys.argv[1] if len(sys.argv)>1 else "http://localhost:8019"
class NoRedir(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*a,**k): return None
op=urllib.request.build_opener(NoRedir)
def req(path,data=None,raw=None,ctype=None):
    if raw is not None: r=urllib.request.Request(B+path,raw,{"Content-Type":ctype})
    else: r=urllib.request.Request(B+path,urllib.parse.urlencode(data,doseq=True).encode() if data is not None else None)
    try: return op.open(r)
    except urllib.error.HTTPError as e:
        if e.code in(302,303,400,402,403,404,422): return e
        raise
def body(p): return req(p).read().decode()
def loc(r): return r.headers["location"]
# ---- unit: taps -> text, ticks, numbers
d={"who":"parent","name":"Margaret","signer":"poa","rows":{"bed":{"hard":True,"help":True,"c":["out"],"freq":"most","time":"10_30"}},"falls":"3-5","fallx":["getup"],"night":["toilet"],"nights":"5","ntimes":"2","nmins":"10_30","days_help":"7","bad":"3"}
intro,T=I.topic_texts("aa",d)
assert "Power of Attorney" in intro and "Margaret" in intro and "7 days a week" in intro, intro
assert "Margaret finds this hard" in T["29"] and "getting out of bed" in T["29"] and "most days" in T["29"] and "10 to 30 minutes" in T["29"], T["29"]
assert "3 to 5 falls" in T["34"] and "5 nights a week" in T["42"], T
tk=I.ticks("aa",d); assert tk["x29"]=="/Yes" and tk["x29-2"]=="/Yes" and tk["x29-4"]=="/Yes" and "x29-1" not in tk and tk["x34"]=="/Fall" and tk["x34-3"]=="/Yes" and tk["x42"]=="/Yes", tk
ex=I.extra("aa",d); assert ex["days_week_day"]=="7" and ex["nights_week"]=="5" and ex["falls_year"]=="3 to 5", ex
assert I.ticks("aa",{})=={} and I.extra("aa",{})=={}            # nothing tapped -> nothing ticked
assert I.personal_prefill("aa",d)=={"other_names":"Margaret"} and I.personal_prefill("aa",{"who":"parent","name":"Mum"})=={}
h=I.history("aa",d); assert len(h)==2+2*len(FORMS["aa"]["topics"])   # one answer per topic, in order
# every question in every section has a skip/'not sure' route: rendering with no data must work
for f in I.FORMS_V3:
    for s,_ in I.SECTIONS[f]: assert I.section_body(f,s,{})
# 'Something else' on every tap list: stored per question, mapped to the right topic, only when its chip is on
class FM(dict):
    def getlist(self,k): v=self.get(k); return v if isinstance(v,list) else ([] if v is None else [v])
dd=I.save("aa","daily",{},FM({"r_bed_c":[],"r_bed_c_xon":"1","r_bed_c_x":"Needs the bed rail"}))
dd=I.save("aa","safety",dd,FM({"fallx_xon":"1","fallx_x":"Hits her head","eye_x":"typed but chip off"}))
dd=I.save("aa","finish",dd,FM({"aids_xon":"1","aids_x":"Bath lift","people_xon":"1","people_x":"Dementia nurse"}))
dd=I.save("aa","conds",dd,FM({"cond_0":"1","cond_0_t_xon":"1","cond_0_t_x":"Hydrotherapy"}))
_,T=I.topic_texts("aa",dd)
assert dd["rows"]["bed"]["x"]=="Needs the bed rail" and "also: Needs the bed rail" in T["29"], T["29"]
assert "After a fall, also: Hits her head." in T["34"] and "typed but chip off" not in str(T) and dd["else"]["eye"]==""
assert "Other aids used: Bath lift." in T["33"] and "Dementia nurse" in T["40"] and "Hydrotherapy" in str(T)+I.topic_texts("aa",dd)[0]
for f in I.FORMS_V3:
    for sname,_ in I.SECTIONS[f]:
        if sname!="about": assert "Something else" in I.section_body(f,sname,{}), (f,sname)
print("intake units ok")
SAMPLE={
 "aa":[("about",{"who":"parent","name":"Margaret","signer":"poa"}),("conds",{"cond_0":"1","cond_0_since":"2015","cond_0_t":["tabs"],"cond_1":"1","cond_1_since":"2021","oc_0":"Macular degeneration","oc_0_since":"ns"}),
       ("daily",{"bad":"3","days_help":"7","r_bed_hard":"1","r_bed_help":"1","r_bed_c":["out","in"],"r_bed_freq":"every","r_bed_c_xon":"1","r_bed_c_x":"Grips the bed rail for ages","r_bed_time":"10_30","r_wash_help":"1","r_wash_c":["in","fell"],"r_wash_freq":"most","r_indoors_hard":"1","r_indoors_c":["stairs","chair"],"r_meds_help":"1","r_meds_c":["forget"],"r_comm_hard":"1","r_comm_c":["mem","phone"]}),
       ("safety",{"falls":"3-5","lastfall":"month","fallx":["getup","alarm"],"eye":["confused","wander"],"alone":"lt1","night":["toilet","confused"],"nights":"6","ntimes":"2","nmins":"10_30","watch":"some"}),
       ("finish",{"aids":["Walking frame","Shower seat"],"people":["GP","Family carer"],"words":"Mum gets very muddled in the evenings.","aids_xon":"1","aids_x":"Bath lift"})],
 "dla":[("about",{"rel":"Mum","name":"Leo","age":"5to15"}),("conds",{"cond_0":"1","cond_0_since":"2021","cond_1":"1","cond_1_since":"ns"}),
       ("daily",{"bad":"4","r_toilet_help":"1","r_toilet_c":["pads"],"r_dress_help":"1","r_dress_c":["sens"],"r_dress_time":"30_60","r_superv_hard":"1","r_superv_c":["danger","imp","over"],"r_superv_freq":"every","r_speak_hard":"1"}),
       ("safety",{"fits":"no","varies":"varies","nn":["night_settle","night_toilet"],"nn_night_settle_n":"5","nn_night_settle_t":"2","nn_night_settle_m":"30","nn_night_toilet_n":"3","r_out_hard":"1","r_out_c":["road","anx"]}),
       ("finish",{"school":["ehcp","one"],"aids":["Ear defenders"],"people":["Paediatrician","Teacher or SENCo"]})],
 "pip":[("about",{"who":"me"}),("conds",{"cond_0":"1","cond_0_since":"2018","cond_0_t":["talk"],"cond_2":"1","cond_2_since":"2019"}),
       ("daily",{"bad":"4","r_a1_hard":"1","r_a1_c":["hob","prompt"],"r_a1_std":["safe"],"r_a1_freq":"most","r_a4_help":"1","r_a4_c":["in"],"r_a4_time":"30_60"}),
       ("out",{"r_a9_hard":"1","r_a9_c":["anx","someone"],"r_a11_hard":"1","r_a11_c":["alone","panic"],"r_a11_freq":"every","r_a12_hard":"1","r_a12_c":["lt50","pain"]}),
       ("finish",{"aids":["Walking stick"],"people":["GP","Mental health team"]})]}
def multipart(files):
    b=uuid.uuid4().hex; out=b""
    for n,(fn,ct,data) in files: out+=f'--{b}\r\nContent-Disposition: form-data; name="{n}"; filename="{fn}"\r\nContent-Type: {ct}\r\n\r\n'.encode()+data+b"\r\n"
    return out+f"--{b}--\r\n".encode(),f"multipart/form-data; boundary={b}"
def tiny_pdf(text):
    from fpdf import FPDF
    p=FPDF(); p.add_page(); p.set_font("Helvetica",size=12); p.cell(0,10,text); return bytes(p.output())
PNG=bytes.fromhex("89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4890000000d49444154789c6360000002000154a24f5d0000000049454e44ae426082")
from pypdf import PdfReader
for form in I.FORMS_V3:
    for tier in FORMS[form]["tiers"]:
        tok=loc(req("/checkout",{"tier":tier,"form":form})).split("/")[-1]
        assert req(f"/intake/{tok}").status==402                                    # nothing before consent
        assert loc(req(f"/consent/{tok}",{"health":"on","truth":"on"}))==f"/intake/{tok}"
        h=body(f"/intake/{tok}"); assert "About 10 minutes" in h and "You only tap, we do the writing" in h and "Part 1 of 5" in h
        low=h.lower(); assert "stripe" not in low and " ai " not in low and "charity" not in low and "citizens advice" not in low
        assert not set(re.findall(r'href="?(https?://[^" >]+)',h))-{"https://formsorted.com/privacy.html","https://formsorted.com/terms.html"}
        secs=SAMPLE[form]
        for i,(s,data) in enumerate(secs):
            nav="save" if i==1 else "next"
            r=req(f"/intake/{tok}",{"sec":s,"nav":nav,**data})
            if nav=="save":
                t=r.read().decode(); assert "Your answers are saved" in t and f"/intake/{tok}" in t
                assert f'name=sec value={secs[1][0]}' in body(f"/intake/{tok}")             # resume where they left off
                r=req(f"/intake/{tok}",{"sec":s,"nav":"next",**data})
            if i<len(secs)-1:
                assert loc(r)==f"/intake/{tok}?s={secs[i+1][0]}", loc(r)
                pg=body(loc(r)); assert f"Part {i+2} of 5" in pg
                if i==0 and form!="pip": assert ("Leo" if form=="dla" else "Margaret") in pg      # their name used in the questions
        assert loc(r)==f"/preview/{tok}", loc(r)
        back=body(f"/intake/{tok}?s=daily"); assert re.search(r'name="r_\w+_(hard|help)" value="1" checked',back)   # answers kept, not asked again
        req(f"/intake/{tok}",{"sec":"finish","nav":"next",**secs[-1][1]})
        pv=body(f"/preview/{tok}")
        assert "Pay £" in pv and "preview-placeholder.svg" in pv and "Never a percentage" in pv and "approve everything" in pv and "sections of the form" in pv
        for leak in ("Grips the bed rail","Bath lift","Margaret finds","getting out of bed","muddled","Leo finds","no sense of danger","In my own words"): assert leak.lower() not in pv.lower(), leak
        assert "stripe" not in pv.lower() and " ai " not in pv.lower()
        for p_ in ("/approve/","/check/","/deadline/","/details/","/ticks/","/documents/","/prepare/","/uploads/"): assert req(p_+tok).status==402, p_
        assert req(f"/download/{tok}/answers.html").status==402
        assert loc(req(f"/pay/{tok}",{"waive":"on"}))==f"/start/{tok}"
        assert loc(req(f"/start/{tok}"))==f"/uploads/{tok}"
        up=body(f"/uploads/{tok}"); assert "Payment received" in up and "Skip" in up
        raw,ct=multipart([("files",("meds.pdf","application/pdf",tiny_pdf("Repeat prescription: Donepezil 10mg once daily"))),("files",("letter.png","image/png",PNG)),("files",("bad.exe","application/octet-stream",b"MZ"))])
        r=req(f"/uploads/{tok}",raw=raw,ctype=ct); assert "err=" in loc(r)
        up=body(f"/uploads/{tok}"); assert "meds.pdf" in up and "letter.png" in up and "bad.exe" not in up
        assert loc(req(f"/uploads/{tok}/done",{}))==f"/prepare/{tok}"
        assert loc(req(f"/prepare/{tok}"))==f"/deadline/{tok}"
        assert loc(req(f"/intake/{tok}"))==f"/start/{tok}" and loc(req(f"/start/{tok}"))==f"/deadline/{tok}"   # locked once drafted, no redirect loop
        ap=body(f"/approve/{tok}"); assert "What you told us" in ap
        if form=="aa": assert "Grips the bed rail for ages" in ap and "Other aids used: Bath lift." in ap   # 'Something else' reaches what-you-told-us (and so drafting + grounding)
        assert ("Margaret finds this hard" in ap) if form=="aa" else ("Leo" in ap and "night" in ap.lower()) if form=="dla" else ("I find this hard" in ap), form
        ok={f"ok_{x}":"on" for x,_,_ in FORMS[form]["topics"]}
        for i_,rn in enumerate(sorted(set(re.findall(r'name="(res_[^"]+)"',ap)))): ok[rn]="keep"
        r=req(f"/approve/{tok}",ok)
        if form in ("aa","dla") and tier=="99":
            assert loc(r)==f"/ticks/{tok}"
            th=body(f"/ticks/{tok}"); m=re.search(r"We have already set (\d+) tick boxes",th); assert m and int(m.group(1))>=5, th[:400]
            chk=dict(re.findall(r'name="(t_[^"]+)" value="([^"]*)" checked',th))
            want={"aa":{"t_x29":"/Yes","t_x29-2":"/Yes","t_x29-4":"/Yes","t_x34":"/Fall","t_x34-3":"/Yes","t_x40-8":"/Yes","t_302":"/Yes"},"dla":{"t_55":"/Yes","t_66":"/Yes","t_66_1":"/No","t_70":"/Yes","t_68":"/Yes","t_49_3":"/No"}}[form]
            for k,v in want.items(): assert chk.get(k)==v, (k,chk.get(k))
            chk["confirm"]="on"; assert loc(req(f"/ticks/{tok}",chk))==f"/details/{tok}"
        elif "/ticks/" in loc(r):
            th=body(loc(r)); chk=dict(re.findall(r'name="(t_[^"]+)" value="([^"]*)" checked',th)); chk["confirm"]="on"; assert loc(req(loc(r),chk))==f"/details/{tok}"
        else: assert loc(r)==f"/details/{tok}", loc(r)
        dh=body(f"/details/{tok}")
        if form!="pip": assert 'value="'+("Leo" if form=="dla" else "Margaret")+'"' in dh       # name not asked twice
        if form=="dla": assert 'id=d_relationship name=relationship  value="Mum"' in dh or 'value="Mum"' in dh
        dd={"title":"Mrs","other_names":"Sam","surname":"Tester","dob":"1940-01-02","addr1":"1 Test St","addr3":"Leeds","postcode":"LS1 1AA",**({"parent_other_names":"Pat","parent_surname":"Tester","relationship":"Mother"} if form=="dla" else {})}
        assert loc(req(f"/details/{tok}",dd))==f"/documents/{tok}"
        assert loc(req(f"/start/{tok}"))==f"/documents/{tok}" and loc(req(f"/uploads/{tok}"))==f"/start/{tok}"
        doc=body(f"/documents/{tok}"); files=re.findall(r'href="(/download/[^"]+)"',doc)
        for u in files: assert len(req(u).read())>2000, u
        ans=req(f"/download/{tok}/answers.html").read().decode()
        assert "Documents you uploaded" in ans and "meds.pdf" in ans
        if form=="aa": assert "Power of Attorney" in ans
        if tier=="99" and form in("aa","dla"):
            pf=PdfReader(io.BytesIO(req(f"/download/{tok}/{FORMS[form]['pdf_out']}").read())).get_fields()
            v=lambda k:str((pf.get(k) or {}).get("/V",""))
            if form=="aa": assert v("x29")=="/Yes" and v("x34")=="/Fall" and v("38")=="7" and v("43")=="6" and v("34-8")=="3 to 5", (v("x29"),v("38"),v("43"),v("34-8"))
            else: assert v("70")=="/Yes" and v("70_10")=="5" and v("70_11")=="30" and v("70_12")=="2" and v("55")=="/Yes", (v("70"),v("70_10"),v("70_11"),v("70_12"))
            assert v("x15") in ("","/Off","None")
        print(form,tier,"intake e2e ok",[u.split("/")[-1] for u in files])
# atw and pipr still use the chat
t=loc(req("/checkout",{"tier":"49","form":"atw"})).split("/")[-1]; assert loc(req(f"/consent/{t}",{"health":"on","truth":"on"})).startswith("/static/chat.html#")
assert req(f"/intake/{t}").status==404
print("INTAKE ALL OK")

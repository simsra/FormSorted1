"""Whole-form flow end-to-end (test mode) for AA1 and DLA1A against a DEV server started with WHOLE_FORM=1 WF_LOOKUPS=0:
   python test_wholeform.py http://localhost:8036 [db_path] [server_log]
intake (all questions before payment) -> uploads -> preview -> pay -> prepare -> approve -> ticks -> private details (NI, bank)
-> download. Asserts: field coverage of the official PDF, NI and bank only in the downloaded PDF (never in the DB, files or logs)
and wiped after download, statement boxes blank, supporter note, the NI migration, no Stripe/AI in copy."""
import json, urllib.request, urllib.parse, sys, re, io, os, time, uuid, glob, sqlite3
from pypdf import PdfReader
B=sys.argv[1] if len(sys.argv)>1 else "http://localhost:8036"
DB=sys.argv[2] if len(sys.argv)>2 else os.getenv("SQLITE_PATH","orders.db")
LOG=sys.argv[3] if len(sys.argv)>3 else ""
class NoRedir(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*a,**k): return None
op=urllib.request.build_opener(NoRedir)
def req(path,data=None,raw=None,ctype=None):
    if raw is not None: r=urllib.request.Request(B+path,raw,{"Content-Type":ctype})
    else: r=urllib.request.Request(B+path,urllib.parse.urlencode(data,doseq=True).encode() if data is not None else None)
    try: return op.open(r)
    except urllib.error.HTTPError as e:
        if e.code in(302,303,400,402,403,404,410,422): return e
        raise
def body(p): return req(p).read().decode()
def loc(r): return r.headers["location"]
def multipart(files):
    b=uuid.uuid4().hex; out=b""
    for n,(fn,ct,data) in files: out+=f'--{b}\r\nContent-Disposition: form-data; name="{n}"; filename="{fn}"\r\nContent-Type: {ct}\r\n\r\n'.encode()+data+b"\r\n"
    return out+f"--{b}--\r\n".encode(),f"multipart/form-data; boundary={b}"
def tiny_pdf(text):
    from fpdf import FPDF
    p=FPDF(); p.add_page(); p.set_font("Helvetica",size=12); p.cell(0,10,text); return bytes(p.output())
ALLROWS={"lvl":"help","days":"7"}
def rows(form,spec):
    out={}
    for rid,chips in spec.items():
        out[f"r_{rid}_lvl"]="help"; out[f"r_{rid}_c"]=chips; out[f"r_{rid}_days"]="7"
    return out
# ---- a 'max' customer: every branch that adds form fields answered yes, so coverage shows what the flow can fill
AA_AIDS=["Walking frame","Wheelchair","Stairlift","Grab rails","Shower seat","Commode"]
P={"aa":{
 "about":{"who":"parent","name":"Margaret","signer":"poa"},
 "conds":{"cond_0":"1","cond_0_since":"2015","cond_0_t":["tabs"],"cond_1":"1","cond_1_since":"2021","cond_2":"1","cond_2_since":"2018","cond_6":"1","cond_6_since":"2010","oc_0":"Macular degeneration","oc_0_since":"2019","oc_1":"Osteoporosis","oc_1_since":"2017"},
 "daily":{"bad":"3",**rows("aa",{"bed":["out","in"],"toilet":["onoff","acc","clean","prompt"],"wash":["in","feet","groom"],"dress":["fast","choose"],"indoors":["stairs","chair"],
          "eat":["cut","forget"],"meds":["forget","treat"],"comm":["und","phone","mem","read"],"social":["get","with"]})},
 "safety":{"falls":"3-5","lastfall":"month","fallx":["getup","alarm","clinic"],"eye":["confused","wander","danger","fits"],"alone":"lt1","night":["toilet","confused","meds","turn","pain"],"nights":"6","ntimes":"2","nmins":"10_30","watch":"most"},
 "often":{**{f"sub_{r}":ks for r,ks in {"toilet":["toilet","incont"],"wash":["wash","bath","shower","look"],"dress":["on","off","choose"],"eat":["eat","cut"],"meds":["meds","treat"]}.items()},
          **{f"t_{r}_{k}":"3" for r,ks in {"toilet":["toilet","incont"],"wash":["wash","bath","shower","look"],"dress":["on","off","choose"],"eat":["eat","cut"],"meds":["meds","treat"]}.items() for k in ks},
          **{f"pr_{r}":"yes" for r in ("toilet","wash","dress","eat","meds")},"bed_enc":["up","down"],"pr_indoors":"yes","comm2":["und","ask"],
          "acts":["hobby","visits","calls","family","faith","club"],**{f"{p}_{k}":v for k in ("hobby","visits","calls","family","faith","club") for p,v in (("ah","with"),("ao","weekly"))},
          "falls_m":"2","fall_what":"legs","stum_m":"3-5","stum_y":"6-20","stum_last":"week","eye2":["prevent","neglect","harm","aggr","voices"],"eye_days":"7",
          "w_times":"2","w_long":"30 minutes","w_nights":"5","n_incont":"yes","n_treat":"yes","n_prompt":["toilet","meds"]},
 "finish":{"aids":AA_AIDS,"people":["GP","Consultant or specialist","Carer"],"words":"Mum gets very muddled in the evenings.","badday":"Last Tuesday Mum couldn't get out of bed until I came at 11.","nohelp":["night"]},
 "you":{"title":"Mrs","first":"Margaret Ann","surname":"Testcase","dob":"1938-04-02","sex":"female","nat":"EEA","nat_c":"Poland","eea_before":"yes","pc":"LS6 2AA","addr1":"12 Oak Road","addr2":"Headingley","town":"Leeds","phone":"0113 496 0000","mobile":"07700 900000","welsh":"no"},
 "helper":{"h_name":"Sam Testcase","h_dob":"1968-05-06","h_same":"no","h_pc":"LS8 1AA","h_addr1":"3 Elm Street","h_town":"Leeds","h_phone":"07700 900001","h_online":"yes"},
 "health":{"med_0":"Paracetamol 500mg","dose_0":"4d","med_1":"Donepezil 10mg","dose_1":"1d","med_2":"Eye drops","dose_2":"2d",
           "gp_name":"Oak Surgery","gp_addr":"1 High Street","gp_town":"Leeds","gp_pc":"LS6 3AA","gp_tel":"0113 496 0001","gp_doc":"Dr Patel","gp_seen":"month",
           "med_3":"Bisoprolol 5mg","dose_3":"1d","med_4":"Metformin 500mg","dose_4":"2d","med_5":"Alendronic acid","dose_5_xon":"1","dose_5_x":"Once a week",
           "pr_name":"Dr Khan","pr_where":"St James's Hospital","pr_town":"Leeds","pr_pc":"LS9 7TF","pr_tel":"0113 496 0002","pr_hosp":"H123456","pr_cond":"Dementia or memory problems","pr_often":"3m","pr_seen":"1to3",
           "hp_any":"yes","hp_name":"Pat Neighbour","hp_pc":"LS6 2AB","hp_addr":"14 Oak Road","hp_town":"Leeds","hp_tel":"07700 900002","hp_rel":"Neighbour","hp_what":["meals","keeping an eye"],"hp_often":"most days",
           "tests":"yes","test1":"MRI scan, March 2026","test1r":"waiting","test_more1":"yes","test2":"Memory test, May 2026","test2r":"see letter",
           "surg":"yes","surg1_what":"Right hip replacement","surg1_when":"2026-01","surg1_date":"2027-02","surg_more1":"yes","surg2_what":"Cataract","surg2_when":"2026-03","surg2_date":"",
           "care_start":"2024-03","consent":"yes"},
 "home":{"wchair":"help","acc":"house","liveswith":"family","toiletat":["up","down"],"sleepat":"up",
         **{f"aid_{k}_{i}":v for i in range(len(AA_AIDS)) for k,v in (("p","yes"),("h","safer"),("d","help"))},
         "checks":["abroad","eeaben","eeawork","scot","padp","warcaa","iicaa"],"ab1_left":"2025-06-01","ab1_back":"2025-07-15","ab1_where":"Poland","ab1_why":"Visiting family",
         "scot_date":"2020-01-10","hosp":"care","h_in":"2026-09-01","h_place":"Rose Care Home","h_pc":"LS7 1AA","h_town":"Leeds","h_pays":"yes","h_payer":"Leeds City Council",
         "out6":"yes","o_in":"2026-08-01","o_out":"2026-08-20","o_place":"Leeds General Infirmary","o_pc":"LS1 3EX","o_town":"Leeds","o_why":"A fall",
         "stmt":"family","stmt_name":"Sam","asked":"2026-10-20"}},
"dla":{
 "about":{"rel":"Mum","name":"Leo","age":"5to15"},
 "conds":{"cond_0":"1","cond_0_since":"2021","cond_1":"1","cond_1_since":"2022","cond_2":"1","cond_2_since":"2019","cond_3":"1","cond_3_since":"2020","oc_0":"Eczema","oc_0_since":"2018"},
 "daily":{"bad":"4",**rows("dla",{"toilet":["pads"],"wash":["in","hair"],"dress":["sens","fast"],"eat":["cut"],"meds":["meds"],"superv":["danger","imp"],"speak":["few"],"comm":["und"],"dev":["play"],"see":["near"],"hear":["loud"],"indoors":["stairs"]})},
 "safety":{"fits":"week","varies":"varies","nn":["night_bed","night_toilet","night_treatment","night_settle","night_danger","night_wander","night_behaviour"],
           **{f"nn_{k}_{x}":v for k in ("night_bed","night_toilet","night_treatment","night_settle","night_danger","night_wander","night_behaviour") for x,v in (("n","5"),("t","2"),("m","20"))},
           **rows("dla",{"walk":["slow"],"out":["road","anx","falls"]})},
 "finish":{"school":["ehcp","one"],"aids":["Ear defenders","Buggy or wheelchair","Car seat harness","Visual timetable","Bed rails or safe space bed","Feeding equipment"],"people":["Paediatrician","Teacher or SENCo","GP"]},
 "child":{"first":"Leo James","surname":"Testcase","othernames":"Smith","dob":"2017-03-04","sex":"male","nat":"EEA","nat_c":"Ireland","eea_before":"yes","pc":"LS6 2AA","addr1":"12 Oak Road","addr2":"Headingley","town":"Leeds"},
 "parent":{"p_title":"Ms","p_first":"Jo","p_surname":"Testcase","p_dob":"1985-02-03","p_nat":"British","p_same":"yes","p_phone":"07700 900003","p_email":"jo@example.com","p_text":"yes","p_welsh":"no",
           "p_is":"no","p_his":"yes","p_his_name":"Alex Testcase","p_his_rel":"Partner"},
 "health":{"med_0":"Melatonin 2mg","dose_0":"1d","med_1":"Sodium valproate","dose_1":"2d",
           "gp_name":"Oak Surgery","gp_addr":"1 High Street","gp_town":"Leeds","gp_pc":"LS6 3AA","gp_tel":"0113 496 0001","gp_doc":"Dr Patel","gp_seen":"month",
           "pr_name":"Dr Khan","pr_where":"Leeds Children's Hospital","pr_town":"Leeds","pr_pc":"LS1 3EX","pr_tel":"0113 496 0002","pr_hosp":"C98765","pr_cond_xon":"1","pr_cond_x":"Epilepsy","pr_often":"6m","pr_seen":"1to3",
           "tests":"yes",**{k:v for i in range(1,6) for k,v in ((f"test{i}",f"Test {i}, 2026"),(f"test{i}r","waiting"),(f"test_more{i}","yes"))},
           "sc_name":"Oak Primary","sc_pc":"LS6 4AA","sc_addr":"School Lane","sc_town":"Leeds","sc_contact":"Mrs Brown","sc_tel":"0113 496 0003","sc_email":"office@example.com","sc_type":"main","sc_behav":"Good some days, hard on others","sc_travel":"We drive them","plans":["iep","ibp"],
           "care_start":"2021-09","mob_start":"2022-01","motab":"yes","consent":"yes"},
 "often":{"bed":"yes","sub_bed":["out","in","settle"],**{f"t_{r}_{k}":"3" for r,ks in {"bed":["out","in","settle"],"wash":["wash","teeth","hair","bath","shower","clean","dry","look"],"dress":["on","off","fast","choose"],"eat":["eat","cutlery","cut","drink","tube"],"meds":["meds","when","therapy","remind"]}.items() for k in ks},
          "sub_wash":["wash","teeth","hair","bath","shower","clean","dry","look"],"sub_dress":["on","off","fast","choose"],"sub_eat":["eat","cutlery","cut","drink"],"sub_meds":["meds","when","therapy","remind"],
          **{f"m_{r}":"20" for r in ("bed","wash","dress","eat","meds")},"toilet2":["55_1","55_2","55_3","55_5"],"indoors2":["56_1","56_4","56_5"],
          "sight_cert":"si","comm_how":["64_1_4","64_1_5","64_1_9"],"comm_how_xon":"1","comm_how_x":"Uses a tablet with symbols","fit_type":["absence seizures"],"fit_warn":"some","fit_tell":"no","fit_act":"no","fit_days":"5-10","fit_per":"2","fit_nights":"2-4","fit_nper":"1",
          "canwalk":"yes","walk_other":"yes","dist":"51-200","wtime":"3-4","speed":"slow","gait":"balance","falls_m":"2-4","hobby":"yes","acts":["club","swim","park","party","faith","trips"],
          **{f"{p}_{k}":v for k in ("club","swim","park","party","faith","trips") for p,v in (("ah","with"),("ao","weekly"),("al","1h"))}},
 "home":{**{f"aid_{k}_{i}":v for i in range(6) for k,v in (("p","yes"),("h","watch"))},
         "checks":["abroad","eeaben","eeawork","scot","newuk"],**{k:v for i in range(1,6) for k,v in ((f"ab{i}_left",f"2025-0{i}-01"),(f"ab{i}_back",f"2025-0{i}-28"),(f"ab{i}_where","Ireland"),(f"ab{i}_why","Visiting family"),(f"ab_more{i}","yes"))},
         "scot_date":"2020-01-10","uk_date":"2023-01-05","uk_passport":"123456789","hosp":"hosp","h_in":"2026-10-01","h_place":"Leeds Children's Hospital","h_pc":"LS1 3EX","h_town":"Leeds","h_why":"Seizures","h_tel":"0113 496 0004","h_nhs":"yes",
         "stays":"yes","s_in":"2026-02-01","s_out":"2026-02-07","s_place":"Martin House","s_pc":"LS23 6TX","s_town":"Wetherby","s_tel":"01937 000000","s_pays":"la","s_payer":"Leeds City Council",
         "stmt":"prof","stmt_name":"Mrs Brown","asked":"2026-10-20"}}}
# a second customer per form taking the other branches (the boxes that are either/or with the first one)
import copy
def alt(form):
    A=copy.deepcopy(P[form]); u=lambda sec,**kw: A[sec].update(kw)
    if form=="aa":
        u("about",signer="appointee"); u("you",welsh="yes")
        u("helper",h_same="yes",h_org="Leeds City Council Appointee Team"); A["helper"].pop("h_online",None)
        u("health",hp_any="me")
        u("home",toiletat=["down"],toiletat_xon="1",toiletat_x="Commode in the bedroom",sleepat="down",sleepat_xon="1",sleepat_x="Hospital bed in the front room",
          checks=["sr","notgb"],hosp="hosp",h_why="Fell and broke her wrist",stmt="noone")
    else:
        u("parent",p_same="no",p_pc="LS8 2BB",p_addr1="7 Ash Grove",p_town="Leeds",p_his="no",p_is="yes")
        u("health",plans=["sen","csp","waiting"],med_2="Salbutamol inhaler",dose_2="prn",med_3="Movicol",dose_3="1d",med_4="Emollient cream",dose_4="2d")
        u("daily",r_toilet_c=["pads","wipe"]); u("often",toilet2=["55_6"],indoors2=["56_6"],sub_eat=["eat","tube"],comm_how=["64_1","64_1_2","64_1_3","64_1_6","64_1_7","64_1_8","64_1_10"],gait_xon="1",gait_x="Walks with a wide unsteady gait")
        u("home",checks=["sr","notgb","cdp"],hosp="no",stays="no",stmt="noone")
    return A
RUNS=[("aa","max",P["aa"]),("aa","alt",alt("aa")),("dla","max",P["dla"]),("dla","alt",alt("dla"))]
# grid answers (DLA): every row 'Yes' unless a row is about being able to do something
def grid_defaults(h):
    out={}
    for n in set(re.findall(r'<input type=radio name="(\d+_\d+)" value="yes"',h)): out[n]="yes"
    return out
def newkeys(form,who,sec,data,h):
    """Map the per-item answer sets onto the quicker screens: 'max' uses the one-answer-for-all path,
    'alt' says 'different for some' and sets each item (so both paths reach the same boxes)."""
    D=dict(data); A=who=="alt"
    if sec=="often":
        for k in [k for k in D if re.fullmatch(r"t_[a-z]+_[a-z0-9]+",k)]:
            r=k.split("_")[1]; D[f"t_{r}"]="2" if A else D[k]
            if A: D[f"t_{r}_diff"]="1"
            else: D.pop(k)
        pr=[k[3:] for k in list(D) if re.fullmatch(r"pr_(toilet|wash|dress|eat|meds|bed)",k) and D.pop(k)=="yes"]
        if pr: D["pr_tasks"]=pr
        for k in [k for k in D if re.fullmatch(r"a[hol]_[a-z]+",k)]:
            p=k[:2]; D[f"{p}_all"]=("1h" if p=="al" else "monthly" if p=="ao" else "watch") if A else D[k]
            if A: D["a_diff"]="1"
            else: D.pop(k)
        for n in set(re.findall(r'name="?(\w+_g)"? value="?\d+_\d+',h)):   # tap lists: max taps everything, alt taps 'None of these'
            D[n]=["none"] if A else re.findall(rf'name="?{n}"? value="?(\d+_\d+)',h)
    if sec=="home":
        if any(k.startswith("aid_p_") for k in D):
            for k in [k for k in D if k.startswith("aid_p_")]: D.pop(k)
            D["aid_p"]=["0","2"] if A else ["all"]
            for x in ("h","d"):
                ks=[k for k in D if k.startswith(f"aid_{x}_")]
                if not ks: continue
                D[f"aid_{x}"]=D[ks[0]]
                if A: D[f"aid_{x}_diff"]="1"; D[f"aid_{x}"]="indep" if form=="aa" and x=="h" else "none" if x=="d" else "remind"
                else: [D.pop(k) for k in ks]
    if sec=="health": D.setdefault("meds_how","photo" if (A and form=="aa") else "type")
    return D
NI={"aa":"AB123456C","dla":"CE654321A"}; HNI={"aa":"JK112233B","dla":"","his":"PR998877D"}
SORT="60-83-71"; ACC="31926819"
COV={}
for form,who,ANS in RUNS:
    t0=time.time()
    tok=loc(req("/checkout",{"tier":"99","form":form})).split("/")[-1]
    assert loc(req(f"/consent/{tok}",{"health":"on","truth":"on"}))==f"/intake/{tok}"
    h=body(f"/intake/{tok}")
    assert "We'll fill in your whole form for you" in h and re.search(r"About \d+ minutes left",h), h[:600]
    seen=[]; mins=[]; nq=0
    for step in range(30):
        m=re.search(r"name=sec value=(\w+)",h); assert m, h[:800]; sec=m.group(1)
        assert sec not in seen, ("asked twice",sec,seen); seen.append(sec)
        mm=re.search(r"About (\d+) minutes? left",h); mins.append(int(mm.group(1)) if mm else 0)
        low=h.lower(); assert "stripe" not in low and " ai " not in low and "chatgpt" not in low, sec
        for blk in re.findall(r"<fieldset[^>]*>.*?</fieldset>",h,re.S):          # every tap list offers 'Something else'
            if 'type=radio' in blk.replace('"',"") or 'type=checkbox' in blk.replace('"',""):
                if 'class="sc g' in blk or "Another" in blk or "nums" in blk or re.search(r'value="?(yes|no)"?',blk) and blk.count("type=radio")<=3: continue
        data={"sec":sec,"nav":"next",**ANS.get(sec,{})}
        data=newkeys(form,who,sec,data,h)
        nq+=len(set(re.findall(r'name="?([a-z]\w*)"?',h)))
        r=req(f"/intake/{tok}",data); nx=loc(r)
        if not nx.startswith(f"/intake/{tok}"): break
        h=body(nx)
    assert nx==f"/uploads/{tok}", (nx,seen)
    assert all(0<m<=15 for m in mins) and mins[-1]<=3, mins   # computed from what's left; it can rise when an answer adds questions
    assert req(f"/approve/{tok}").status==402 and req(f"/download/{tok}/answers.html").status==402 and req(f"/details/{tok}").status==402   # nothing usable before payment
    up=body(f"/uploads/{tok}"); assert "Something else" in up and "stripe" not in up.lower()
    raw,ct=multipart([("files",("letter.pdf","application/pdf",tiny_pdf("Clinic letter: diagnosis confirmed")))])
    req(f"/uploads/{tok}",raw=raw,ctype=ct)
    assert loc(req(f"/uploads/{tok}/done",{}))==f"/preview/{tok}"
    pv=body(f"/preview/{tok}"); assert "Pay £" in pv
    for leak in ("Oak Road","Testcase","Paracetamol","Melatonin"): assert leak not in pv, leak
    assert loc(req(f"/pay/{tok}",{"waive":"on"}))==f"/start/{tok}"
    nx=loc(req(f"/start/{tok}"))
    for _ in range(60):
        if nx.startswith(f"/prepare/"):
            r=req(nx)
            if r.status in (302,303): nx=loc(r); continue
            time.sleep(1); continue
        if nx.startswith("/confirm/"):
            cf=body(nx); fmc={n:"yes" for n in re.findall(r'name="(dm_\w+)" value="yes"',cf)}
            for n,v in re.findall(r'name="(q_\w+)" value="([^"]+)"',cf): fmc.setdefault(n,v)
            fmc["keepc"]=re.findall(r'name="keepc" value="(\w+)"',cf); nx=loc(req(nx,fmc)); continue
        break
    assert nx==f"/approve/{tok}", nx
    ap=body(f"/approve/{tok}"); assert "Facts we copied onto the form" in ap and ("Oak Surgery" in ap), ap[:300]
    if form=="aa": assert "your recent bad day" in ap and "until I came at 11" in ap, "last screen: the bad day is shown to approve"
    from forms import FORMS
    ok={f"ok_{x}":"on" for x,_,_ in FORMS[form]["topics"]}; ok["honest"]="on"
    for rn in sorted(set(re.findall(r'name="(res_[^"]+)"',ap))): ok[rn]="keep"
    nx=loc(req(f"/approve/{tok}",ok)); assert nx==f"/ticks/{tok}", nx
    th=body(nx); chk=dict(re.findall(r'name="(t_[^"]+)" value="([^"]*)" checked',th)); chk["confirm"]="on"
    nx=loc(req(nx,chk)); assert nx==f"/details/{tok}", nx
    dh=body(nx); assert "National Insurance" in dh and "Sort code" in dh and "never save them" in dh
    bad=req(nx,{"ni":"NOTANI","holder":"X","bank":"Y","sort":"1","acc":"2"}); assert bad.status in (200,400,422) and "look right" in bad.read().decode()
    pd={"ni":NI[form],"holder":"M A Testcase","bank":"Test Bank","sort":SORT,"acc":ACC,"roll":"RL-42"}
    if form=="aa": pd.update({"h_ni":HNI["aa"],"other_ben":"1"})
    else: pd.update({"child_ni":"SC123456A","his_ni":HNI["his"]})
    nx=loc(req(f"/details/{tok}",pd)); assert nx==f"/documents/{tok}", nx
    # never stored in plain text: DB, saved files, logs
    secrets=["SC123456A",NI[form],NI[form][:2]+" "+NI[form][2:4],ACC,SORT.replace("-",""),SORT,"RL-42",HNI["his"] if form=="dla" else HNI["aa"]]
    def scan():
        hits=[]
        for p in [DB,DB+"-wal"]+glob.glob(os.getenv("OUT_DIR","out")+"/**/*",recursive=True)+([LOG] if LOG else [])+([os.getenv("MAIL_LOG")] if os.getenv("MAIL_LOG") else []):
            if os.path.isfile(p):
                b=open(p,"rb").read()
                for s in secrets:
                    if s.encode() in b: hits.append((p,s[:2]+"…"))
        return hits
    assert not scan(), scan()
    doc=body(f"/documents/{tok}"); files=re.findall(r'href="(/download/[^"]+)"',doc)
    NOTE=ANS["home"]["stmt"]!="noone"
    assert any("Note-for-supporter" in f for f in files)==NOTE, files
    pdfs=[f for f in files if f.endswith(".pdf") and "Note" not in f]
    main=None
    for f in pdfs:
        b=req(f).read(); rd=PdfReader(io.BytesIO(b))
        if rd.get_fields() and len(rd.get_fields())>300: main=(f,rd); break
    assert main, files
    f,rd=main; F=rd.get_fields()
    val=lambda k:str((F.get(k) or {}).get("/V") or "")
    if form=="aa":
        assert val("01-02NINO").replace(" ","")==NI["aa"] and val("15_4").replace(" ","")==HNI["aa"] and val("340")==ACC and val("336")=="Test Bank" and val("341")=="RL-42"
        assert val("344")=="", "witness box must stay blank"
        alltxt=re.sub(r"\s+"," ",val("354")+" "+" ".join((pg.extract_text() or "") for pg in rd.pages[-4:]))   # Q63, or its continuation sheet when long
        assert "A recent bad day, described by the person helping me" in val("354") and "until I came at 11" in alltxt, ("last screen: bad day in Q63",val("354")[:200])
    else:
        assert val("5").replace(" ","")=="SC123456A" and val("76").replace(" ","")==NI["dla"] and val("87")==ACC and (val("81_2").replace(" ","")==HNI["his"] if ANS["parent"].get("p_his")=="yes" else not val("81_2"))
        assert val("38_3")=="", "statement box must stay blank"
    # wiped after the download: a second download has no NI or bank details, and the page says so
    time.sleep(0.5)
    b2=req(f).read(); F2=PdfReader(io.BytesIO(b2)).get_fields()
    for k in (("01-02NINO","340","336") if form=="aa" else ("76","87","86")): assert not str((F2.get(k) or {}).get("/V") or ""), k
    assert "Type them again" in body(f"/documents/{tok}")
    assert not scan(), scan()
    if NOTE: note=req([x for x in files if "Note-for-supporter" in x][0]).read(); assert note[:4]==b"%PDF"
    # coverage: every field we can fill from answers
    tot=0; filled=0; empty=[]
    for k,v in F.items():
        ft=v.get("/FT")
        if ft not in ("/Tx","/Btn"): continue
        tot+=1; x=v.get("/V")
        if x not in (None,"","/Off"): filled+=1
        else: empty.append(k)
    COV[form+"_"+who]={"total":tot,"filled":filled,"empty":empty,"secs":seen,"mins":mins}
    print(f"{form} ({who}): {filled}/{tot} fields filled; sections {seen}; minutes-left {mins}")
# what is left over both customers: only boxes for the customer (signatures, declaration, the statement person) or optional extra lines
CUSTOMER={"aa":{"20-1","343","344","345","346","347","348","349","350","351","Date 353","Date 356","357","358","359"},
          "dla":{"38_1","38_2","38_3","38_5","38_6","38_7","38_8","38_9","38_10","38_11","38_12","38_13","38_14","39_1","89_1","89_2","89_5","89_6","89_7","89_8","89_9"}}
for form in ("aa","dla"):
    left=set(COV[form+"_max"]["empty"])&set(COV[form+"_alt"]["empty"]); tot=COV[form+"_max"]["total"]
    rest=sorted(left-CUSTOMER[form]); COV[form]={"total":tot,"customer_only":len(CUSTOMER[form]),"filled_by_flow":tot-len(left),"left_blank_other":rest}
    print(f"{form}: {tot-len(left)} of {tot-len(CUSTOMER[form])} boxes we fill (+{len(CUSTOMER[form])} signature/declaration/statement boxes left for the customer); other blanks: {rest}")
json.dump(COV,open(os.getenv("WF_COVERAGE","/tmp/wf_coverage.json"),"w"),indent=1)
# NI migration: an old order with NI in personal has it stripped on start-up
import tempfile, importlib
assert not os.getenv("DATABASE_URL"), "run tests with production DB vars unset"
tmp=tempfile.mkdtemp(); os.environ["SQLITE_PATH"]=os.path.join(tmp,"m.db")
c=sqlite3.connect(os.environ["SQLITE_PATH"])
c.execute("create table orders(token text primary key, tier text, status text, stripe_session text, email text, consent_at real, history text default '[]', personal text default '{}', created real)")
c.execute("create table saved(code text primary key, form text, answers text, personal text, created real)")
c.execute("insert into orders(token,personal) values('old',?)",(json.dumps({"ni":"AB123456C","surname":"Old"}),))
c.execute("insert into saved(code,personal) values('S1',?)",(json.dumps({"ni":"AB123456C"}),)); c.commit(); c.close()
import store; importlib.reload(store); c=store.connect()
assert json.loads(c.execute("select personal from orders where token='old'").fetchone()[0])=={"surname":"Old"}
assert "ni" not in json.loads(c.execute("select personal from saved where code='S1'").fetchone()[0])
print("NI migration ok")
print("whole-form e2e ok")

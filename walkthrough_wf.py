"""Timed mobile walk-through of the whole-form flow (dev server, WHOLE_FORM=1 WF_LOOKUPS=0), with screenshots.
   python walkthrough_wf.py http://localhost:8037 OUTDIR
Human time is ESTIMATED from what the customer has to do on each screen (taps and typed characters), not measured on a person:
6 s to read a screen + 2 s per tap + 4 s per typed field + 0.35 s per character. Server time is measured."""
import sys, os, re, json, time, subprocess
from playwright.sync_api import sync_playwright
B=sys.argv[1]; OUT=sys.argv[2]; os.makedirs(OUT,exist_ok=True)
src=open(os.path.join(os.path.dirname(os.path.abspath(__file__)),"test_wholeform.py")).read()
g={"__name__":"wf_answers"}; exec(src.split("COV={}")[0].replace("B=sys.argv[1]","B='x'#").replace("DB=sys.argv[2]","DB='x'#").replace("LOG=sys.argv[3]","LOG=''#"),g)
P=g["P"]
FILL="""([data,grid])=>{let taps=0,fields=0,chars=0,missing=[];const f=(document.getElementsByName('sec')[0]||{}).form||document.querySelector('form');
 const ev=el=>{el.dispatchEvent(new Event('input',{bubbles:true}));el.dispatchEvent(new Event('change',{bubbles:true}));el.dispatchEvent(new Event('click',{bubbles:true}))};
 const vis=el=>{const t=(el.type==='radio'||el.type==='checkbox')?(el.closest('label')||el):el; return !!(t.offsetWidth||t.offsetHeight||t.getClientRects().length)};
 const done=[];
 for(const [n,v] of Object.entries(data)){ if(n==='sec'||n==='nav')continue; const els=[...document.getElementsByName(n)];
  if(!els.length){missing.push(n);continue}
  const vals=Array.isArray(v)?v.map(String):[String(v)]; const e0=els[0];
  if(e0.type==='radio'||e0.type==='checkbox'){ for(const el of els){ if(vals.includes(el.value)||(els.length===1&&e0.type==='checkbox'&&v)){ if(!el.checked){el.checked=true;ev(el);done.push(['t',el]);} } } }
  else if(e0.tagName==='SELECT'){e0.value=vals[0];ev(e0);done.push(['s',e0])}
  else {e0.value=vals[0];ev(e0);done.push(['x',e0])}
 }
 if(grid){for(const el of f.querySelectorAll('input[type=radio][value=yes]')){if(/^\\d+_\\d+$/.test(el.name)&&!(el.name in data)&&vis(el)){el.checked=true;ev(el);done.push(['t',el]);}}}
 let hidden=0; for(const [k,el] of done){ if(!vis(el)){hidden++;continue} if(k==='t')taps++; else if(k==='s')taps+=2; else {fields++;chars+=el.value.length} }
 return {taps,fields,chars,missing,hidden}}"""
def est(r): return 6+2*r["taps"]+4*r["fields"]+0.35*r["chars"]
def submit(page,key="sec"):
    with page.expect_navigation(): page.evaluate("""(key)=>{const k=document.getElementsByName(key)[0]; const f=(k&&k.form)||document.querySelector('main form')||document.querySelector('form'); if(!f.querySelector('input[name=nav]')){const i=document.createElement('input');i.type='hidden';i.name='nav';i.value='next';f.appendChild(i)} f.submit()}""",key)
    page.wait_for_load_state("load")
def run(form):
    ans=P[form]; rows=[]; n=[0]
    with sync_playwright() as p:
        br=p.chromium.launch(); ctx=br.new_context(viewport={"width":390,"height":844},device_scale_factor=2,is_mobile=True,has_touch=True)
        page=ctx.new_page()
        def shot(name):
            n[0]+=1; fn=f"{form}_{n[0]:02d}_{name}.png"; page.screenshot(path=os.path.join(OUT,fn),full_page=True); return fn
        page.goto(B+"/"); shot("home")
        t=time.time()
        with page.expect_navigation(): page.evaluate(f"""()=>{{const f=document.createElement('form');f.method='post';f.action='/checkout';
          for(const [k,v] of [['tier','99'],['form','{form}']]){{const i=document.createElement('input');i.type='hidden';i.name=k;i.value=v;f.appendChild(i)}}
          document.body.appendChild(f);f.submit()}}"""); page.wait_for_load_state("load")
        shot("consent"); r={"taps":2,"fields":0,"chars":0}
        page.evaluate("()=>{for(const n of ['health','truth']){const e=document.getElementsByName(n)[0]; if(e) e.checked=true}}"); srv=time.time()-t
        t=time.time(); submit(page,'health'); srv+=time.time()-t; rows.append(("consent",r,srv))
        for _ in range(30):
            if "/intake/" not in page.url: break
            h=page.content(); m=re.search(r'name="?sec"? value="?(\w+)',h); sec=m.group(1)
            mm=re.search(r"About (\d+) minutes? left",h)
            r=page.evaluate(FILL,[ans.get(sec,{}),sec=="often"])
            shot(f"intake_{sec}"); t=time.time(); submit(page); s=time.time()-t
            rows.append((f"intake: {sec} (shows 'about {mm.group(1) if mm else '?'} min left')",r,s))
        assert "/uploads/" in page.url, page.url
        tok=page.url.rstrip("/").split("/")[-1]
        shot("uploads")
        from fpdf import FPDF
        pdf=FPDF(); pdf.add_page(); pdf.set_font("Helvetica",size=12); pdf.cell(0,10,"Clinic letter: diagnosis confirmed"); fp=os.path.join(OUT,"_letter.pdf"); pdf.output(fp)
        t=time.time(); inp=page.locator("input[type=file]").first; inp.set_input_files(fp)
        fm=page.locator("input[type=file]").first.evaluate("e=>e.form && e.form.action")
        with page.expect_navigation(): page.locator("input[type=file]").first.evaluate("e=>e.form.submit()")
        page.goto(B+f"/uploads/{tok}"); shot("uploads_added")
        with page.expect_navigation(): page.evaluate(f"()=>{{const f=document.createElement('form');f.method='post';f.action='/uploads/{tok}/done';document.body.appendChild(f);f.submit()}}")
        rows.append(("uploads (photo of 1 letter)",{"taps":3,"fields":0,"chars":0},time.time()-t))
        assert "/preview/" in page.url, page.url
        shot("preview"); t=time.time()
        page.check("input[name=waive]")
        with page.expect_navigation(): page.locator("form[action^='/pay/'] button").click()
        rows.append(("preview + pay (card entry not included)",{"taps":2,"fields":0,"chars":0},time.time()-t))
        t=time.time(); shot_prep=False
        for _ in range(90):
            u=page.url
            if "/prepare/" in u:
                if not shot_prep: shot("preparing"); shot_prep=True
                time.sleep(1); page.goto(u); continue
            if "/confirm/" in u:
                shot("confirm")
                page.evaluate("""()=>{for(const el of document.querySelectorAll('input[type=radio][value=yes]')) if(/^dm_/.test(el.name)) el.checked=true;
                  const seen={}; for(const el of document.querySelectorAll('input[type=radio]')) if(/^q_/.test(el.name)&&!seen[el.name]){el.checked=true;seen[el.name]=1}
                  for(const el of document.querySelectorAll('input[name=keepc]')) el.checked=true}""")
                submit(page,"keepc"); continue
            if "/start/" in u: page.goto(u); continue
            break
        rows.append(("we prepare the form (waiting)",{"taps":0,"fields":0,"chars":0,"wait":True},time.time()-t))
        assert "/approve/" in page.url, page.url
        shot("approve"); t=time.time()
        k=page.evaluate("""()=>{let n=0;for(const el of document.querySelectorAll('input[type=checkbox]')) if(/^ok_|^honest$/.test(el.name)){el.checked=true;n++}
           const seen={};for(const el of document.querySelectorAll('input[type=radio]')) if(/^res_/.test(el.name)&&el.value==='keep'&&!seen[el.name]){el.checked=true;seen[el.name]=1;n++} return n}""")
        submit(page,"honest"); rows.append(("approve (read + tick each section)",{"taps":k,"fields":0,"chars":0,"read":60},time.time()-t))
        assert "/ticks/" in page.url, page.url
        shot("ticks"); t=time.time(); page.evaluate("()=>{const c=document.getElementsByName('confirm')[0]; if(c) c.checked=true}"); submit(page,'confirm')
        rows.append(("ticks (check the tick boxes)",{"taps":1,"fields":0,"chars":0,"read":20},time.time()-t))
        assert "/details/" in page.url, page.url
        shot("details_private"); t=time.time()
        pd={"ni":"AB123456C" if form=="aa" else "CE654321A","holder":"M A Testcase","bank":"Test Bank","sort":"60-83-71","acc":"31926819","roll":""}
        if form=="aa": pd.update({"h_ni":"JK112233B","other_ben":"1"})
        else: pd.update({"child_ni":"SC123456A","his_ni":"PR998877D"})
        r=page.evaluate(FILL,[pd,False]); shot("details_private_filled_TESTDATA"); submit(page,"ni")
        rows.append(("private details (NI + bank)",r,time.time()-t))
        assert "/documents/" in page.url, page.url
        shot("documents")
        links=page.evaluate("()=>[...document.querySelectorAll('a[href^=\"/download/\"]')].map(a=>a.getAttribute('href'))")
        for l in links:
            b=page.request.get(B+l).body(); fn=os.path.join(OUT,f"{form}_"+l.split("/")[-1])
            if l.endswith(".pdf"): open(fn,"wb").write(b)
        page.goto(B+f"/documents/{tok}"); shot("documents_after_download")
        br.close()
    note=os.path.join(OUT,f"{form}_Note-for-supporter.pdf")
    if os.path.exists(note): subprocess.run(["pdftoppm","-png","-r","70","-f","1","-l","1",note,os.path.join(OUT,f"{form}_zz_supporter_note")])
    for f in os.listdir(OUT):   # the filled PDFs carry test NI/bank values: keep only images
        if f.endswith(".pdf"): os.remove(os.path.join(OUT,f))
    return rows
res={}
for form in ("aa","dla"):
    rows=run(form); tot_h=0; tot_s=0; lines=[]
    for name,r,s in rows:
        h=0 if r.get("wait") else est(r)+r.get("read",0); tot_h+=h; tot_s+=s
        lines.append({"step":name,"taps":r.get("taps",0),"typed_fields":r.get("fields",0),"chars":r.get("chars",0),"est_customer_s":round(h),"server_s":round(s,2),"missing":r.get("missing",[])})
    res[form]={"steps":lines,"est_customer_total_s":round(tot_h),"server_total_s":round(tot_s,1)}
json.dump(res,open(os.path.join(OUT,"timing.json"),"w"),indent=1)
for form,v in res.items():
    print(form, "estimated customer time", v["est_customer_total_s"]//60,"min",v["est_customer_total_s"]%60,"s; server",v["server_total_s"],"s")
    for l in v["steps"]: print("  ",l)

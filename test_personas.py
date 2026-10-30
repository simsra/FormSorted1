"""Made-up test answers and a no-server walk through the intake (shared by the flow and writer tests)."""
import re, html
import intake as I
class FM(dict):
    def getlist(self,k): v=dict.get(self,k); return v if isinstance(v,list) else ([] if v is None else [v])
    def get(self,k,default=None): v=dict.get(self,k,default); return v[0] if isinstance(v,list) and v else v
def rows(spec):
    out={}
    for rid,(lvl,chips,days) in spec.items():
        out[f"r_{rid}_lvl"]=lvl; out[f"r_{rid}_c"]=chips
        if days: out[f"r_{rid}_days"]=days
    return out
AA_STEPS={"conds":{"cond_0":"1"},"daily":{"bad":"3",**rows({"bed":("help",["out","pain"],"7"),"toilet":("help",["onoff"],"5"),"wash":("help",["in","fell"],"7"),"dress":("help",["fast"],""),"meds":("help",["forget"],"7")})},
 "safety":{"falls":"1-2","lastfall":"months","fallx":["getup","alarm"],"eye":["confused"],"alone":"hours","night":["toilet"],"nights":"4","watch":"some"},
 "often":{"t_toilet":"3","t_wash":"1","t_meds":"2","falls_m":"1","eye_days":"7"},"finish":{"aids":["Walking frame"],"people":["GP"]},"home":{"acc":"house"}}
PIP_STEPS={"conds":{"cond_0":"1"},"daily":{"bad":"4",**rows({"a1":("slow",["hob","std_safe"],""),"a4":("help",["in"],"4")})},"out":{**rows({"a11":("cant",["alone"],"")})},"finish":{"aids":["Walking stick"]}}
DLA_STEPS={"about":{"rel":"Mum","name":"Leo","age":"5to15"},"daily":{"bad":"4",**rows({"dress":("help",["sens"],"7"),"superv":("cant",["danger"],"")})},"safety":{**rows({"out":("cant",["road"],"")})},"finish":{"aids":["Ear defenders"]}}
def walk(form,about,steps,stop=None):
    d={"wf_v":1} if form in("aa","dla") else {}; seen=set(); legends=[]
    st={"about":about,**steps}
    while True:
        ids=[k for k,_ in I.sections(form,d)]; nxt=[k for k in ids if k not in seen]
        if not nxt or nxt[0]==stop: break
        sec=nxt[0]; seen.add(sec); body=re.sub(r"<script.*?</script>","",I.section_body(form,sec,d),flags=re.S)
        for m in re.finditer(r'(<div class=wdep data-dep="([^"]*)" data-vals="([^"]*)">)?<fieldset class=iq><legend>(.*?)</legend>',body):
            legends.append((sec,html.unescape(m.group(4)),m.group(2) or "",m.group(3) or "",body))
        for m in re.finditer(r'<label class="?chip[^>]*><input[^>]*><span>(.*?)</span>',body): legends.append((sec,"chip: "+html.unescape(m.group(1)),"","",""))
        d=I.save(form,sec,d,FM(st.get(sec,{})))
    return d,legends

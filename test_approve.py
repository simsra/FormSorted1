"""Approve-page hotfix: sentences, de-duplication, stable flags, inline errors, Keep all remaining.
Units run offline; the e2e part needs a DEV server started with MOCK_GROUND_FLAKY=1:  python test_approve.py http://localhost:8032"""
import sys, re, json, urllib.request, urllib.parse
import grounding as g
S=g.sentences
assert S("She is watched 24/7. If she was not watched, she might hurt herself or get lost.")==["She is watched 24/7.","If she was not watched, she might hurt herself or get lost."]
assert S("I push her wheelchair. for hours and everyday.")==["I push her wheelchair. for hours and everyday."]   # no lower-case fragments
assert S("Dr. Smith saw her. It takes 1.5 hours.")==["Dr. Smith saw her.","It takes 1.5 hours."]
assert S("Line one\nLine two.")==["Line one","Line two."]
assert g.remove_sentence("A b. She is watched 24/7. C d.","She is  watched 24/7.")=="A b. C d."
import app
o={"form":"dla"}; T=[t for t,_,_ in app.FORMS["dla"]["topics"]]
d={"answers":{T[0]:"She is watched 24/7. When we are out, I push her wheelchair.",T[1]:"She is watched 24/7. She needs help everday with dressing."}}
G={T[0]:[{"phrase":"watched 24/7","kind":"x"},{"phrase":"push her","kind":"y"},{"phrase":"not in the answer at all","kind":"z"}],T[1]:[{"phrase":"she is watched 24/7.","kind":"x"},{"phrase":"everday","kind":"x"},{"phrase":"everday","kind":"w"}]}
its=app.flag_items(o,d,G); sents=[i["sentence"] for i in its]
assert sents==["She is watched 24/7.","When we are out, I push her wheelchair.","She needs help everday with dressing."], sents   # deduped, whole sentences, unfound phrase dropped
assert its[0]["topics"]==[T[0],T[1]] and its[2]["kinds"]==["x","w"]
print("approve units ok")
if len(sys.argv)<2: sys.exit()
B=sys.argv[1]
class NR(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*a,**k): return None
op=urllib.request.build_opener(NR)
def req(p,data=None,js=None):
    r=urllib.request.Request(B+p,json.dumps(js).encode(),{"Content-Type":"application/json"}) if js is not None else urllib.request.Request(B+p,urllib.parse.urlencode(data).encode() if data is not None else None)
    try: return op.open(r)
    except urllib.error.HTTPError as e: return e
body=lambda p: req(p).read().decode()
for form,tier in (("dla","99"),("aa","99"),("pip","99")):
    tok=req("/checkout",{"tier":tier,"form":form}).headers["location"].split("/")[-1]
    req(f"/consent/{tok}",{"health":"on","digital":"on","truth":"on"})
    j=json.load(req(f"/api/{tok}/message",js={"text":""})); n=0
    while not j["done"]: n+=1; j=json.load(req(f"/api/{tok}/message",js={"text":f"She needs help {n}"}))
    json.load(req(f"/api/{tok}/finish",{})); req(f"/pay/{tok}",{"waive":"on"}); req(f"/start/{tok}"); req(f"/prepare/{tok}")
    h1=body(f"/approve/{tok}"); h2=body(f"/approve/{tok}")
    r1=sorted(set(re.findall(r'name="(res_[^"]+)"',h1))); assert r1 and r1==sorted(set(re.findall(r'name="(res_[^"]+)"',h2))), "flags must be stable between views"
    topics=[t for t,_,_ in app.FORMS[form]["topics"]]
    fm={f"ok_{t}":"on" for t in topics[:-1]}; fm[r1[0]]="keep"; fm[f"ans_{topics[0]}"]="My edited text."
    e=req(f"/approve/{tok}",fm); assert e.status==200; eh=e.read().decode()
    need=1+len(r1)-1; assert f"{need} answer{'s' if need!=1 else ''} still need" in eh, eh[:600]
    assert f'value=keep required checked' in eh and "My edited text." in eh and f'href="#topic_{topics[-1]}"' in eh and "Please tick to approve this answer" in eh
    assert "Check and approve every answer" in eh and "Go back" not in eh and '","' not in eh
    if len(r1)>1: assert f'href="#{r1[1]}"' in eh and f'id="{r1[1]}" class="needs"' in eh and "Keep all remaining" in eh
    fm[f"ok_{topics[-1]}"]="on"; fm["keepall"]="1"
    r=req(f"/approve/{tok}",fm); assert r.status==303 and r.headers["location"] in (f"/details/{tok}",f"/ticks/{tok}"), (r.status, r.read()[:300])
    print(form,"approve e2e ok",len(r1),"flagged sentences")
print("APPROVE ALL OK")

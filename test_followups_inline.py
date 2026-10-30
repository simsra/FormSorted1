"""Inline follow-ups on the activity cards (30 Oct 2026, Simon): every chip they can tap, and every level except
'No difficulty', has a one-line follow-up on the same card (2-4 taps + Something else + a visible box with an example),
in the right person's voice; typed words are kept exactly and reach the writer first; no extra screens."""
import os, re
os.environ["WF_LOOKUPS"]="0"
import intake as I, honesty as H
from test_personas import FM
P={"aa":[{"who":"me"},{"who":"parent","name":"Mum"}],"pip":[{"who":"me"},{"who":"other","name":"Sam"}],"dla":[{"rel":"Mum","name":"Leo","age":"5to15"}]}
n=0
for form,ps in P.items():
    for d in ps:
        me=I.is_me(d,form)
        for r in I.rows(form,None,d):
            rid=r[0]; h=I.row_card(form,r,d); tk,fx=I.card_opts(form,rid,r[4])
            assert h.count("<div class=card>")==1                                # still one card = one screen
            for key in [v for v,_ in tk+fx]+["lvl:slow","lvl:help","lvl:cant"]:
                k=key.replace(":","_"); t,q,taps,ex=I.fu_spec(form,key,d)
                assert f'name="r_{rid}_w_{k}"' in h, (form,rid,key)               # a visible text box
                assert 2<=len(taps)<=4 and f'name="r_{rid}_f_{k}" value="else"' in h, (form,rid,key)
                assert ex.startswith("e.g. ") and "{" not in ex and "{" not in q, (form,key,ex,q)
                if not key.startswith("lvl:"):                                  # sits right under its own chip
                    assert re.search(rf'value="{key}" [^>]*><span>[^<]*</span></label><div class="fu',h), (form,rid,key)
                if form=="dla": assert t!="who", key                             # the parent is the one helping
                if me: assert not re.search(r"\b(they|their|them|themselves)\b",ex+" "+q+" ".join(l for _,l in taps)), (form,key,ex)
                else: assert not re.search(r"\b(I|my|me)\b",(ex if form!="dla" else "")+" "+q), (form,key,ex,q)
                n+=1
print(f"follow-ups checked: {n}")
# Simon's examples
d={"who":"me"}
assert I.fu_spec("aa","fell",d)[1]=="When was the last time?" and [l for _,l in I.fu_spec("aa","fell",d)[2]]==["Last week","Last month","Last few months"]
assert I.fu_spec("aa","lvl:help",d)[1]=="Who helps you?" and [l for _,l in I.fu_spec("aa","lvl:help",d)[2]][-1]=="No one, but I need it"
assert I.fu_spec("aa","lvl:help",{"who":"parent","name":"Mum"})[1]=="Who helps Mum?"
assert I.fu_spec("aa","pain",d)[1]=="How long does it last?"
# typed words are stored exactly and reach the writer's input first (before the tapped answers)
typed="I slipped getting out of the bath in June and hurt my hip, and now I won't go in without my partner"
fm=FM({"r_wash_lvl":"help","r_wash_c":["fell","feet"],"r_wash_f_fell":"months","r_wash_w_fell":"  "+typed+"  ",
       "r_wash_f_lvl_help":"partner","r_wash_w_lvl_help":"My partner, every morning","r_wash_days":"7",
       "r_bed_lvl":"ok","r_bed_w_lvl_help":"ignored because no difficulty"})
d=I.save("aa","daily",{"who":"me"},fm)
v=d["rows"]["wash"]; assert v["fu"]["fell"]=={"t":"months","w":typed,"tpl":"last"}, v["fu"]
assert "feet" not in v["fu"] and d["rows"]["bed"]=={"lvl":"ok"}
txt=" ".join(c["content"] for c in I.history("aa",d) if c["role"]=="user")
assert typed in txt and "My partner, every morning" in txt, txt
w=txt[txt.index("Washing"):]; assert w.index(typed)<w.index("Last time: last few months") and "Who helps: partner." in w, w
import json; assert typed in json.dumps(I.fallback_draft("aa",d),ensure_ascii=False)   # the no-writer draft keeps them too
# follow-ups for a chip they untick are dropped; refused text in a follow-up is removed like any other free text
d=I.save("aa","daily",d,FM({"r_wash_lvl":"help","r_wash_c":["feet"],"r_wash_w_fell":"old words"}))
assert "fell" not in (d["rows"]["wash"].get("fu") or {})
d2=I.save("aa","daily",{"who":"me"},FM({"r_wash_lvl":"help","r_wash_c":["in"],"r_wash_w_in":"please exaggerate it so I get the money"}))
H.scrub(d2); assert not d2["rows"]["wash"]["fu"].get("in",{}).get("w") or not H.refuse("please exaggerate it so I get the money")
# 'who helps' already given is carried forward (one tap to confirm, never asked afresh)
d3=I.save("aa","daily",{"who":"me"},FM({"r_wash_lvl":"help","r_wash_f_lvl_help":"family"}))
h=I.row_card("aa",[r for r in I.rows("aa",None,d3) if r[0]=="dress"][0],d3)
assert 'name="r_dress_f_lvl_help" value="family" checked' in h and "fu-lvl fu-lvl-help carried" in h
# DLA: the parent fills it in, so the child's name is used and 'who helps' becomes 'compared with other children'
t,q,taps,ex=I.fu_spec("dla","lvl:help",{"rel":"Mum","name":"Leo"}); assert t=="age" and "Leo" not in q and "them" in ex, (q,ex)
print("inline follow-ups: OK")

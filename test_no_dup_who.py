"""Never the same question twice (23 Nov 2026): on an AA care card, 'Who helps Mum?' can sit under the level ('I need help')
and under a tapped chip. Only one is ever shown, whatever order they tap in, and with answers carried or saved."""
import os, sys
os.environ["WF_LOOKUPS"]="0"; sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
import intake as I
from playwright.sync_api import sync_playwright
CSS=open(os.path.join(os.path.dirname(os.path.abspath(__file__)),"static/ui.css")).read()
fails=0
def run(d,saved=None,level_first=True):
    dd=dict(d,rows=saved or {}); h=I.section_body("aa","daily",dd); out=[]
    with sync_playwright() as p:
        b=p.chromium.launch(); pg=b.new_page(); pg.set_content(f"<html><head><style>{CSS}</style></head><body><form>{h}</form></body></html>")
        for ci in range(3):
            c=pg.locator(".card").nth(ci); rid=c.locator("input[name$=_lvl]").first.get_attribute("name")
            def level(answer=True):
                c.locator(f"input[name='{rid}'][value=help]").check(force=True); pg.wait_for_timeout(80)
                if answer: ans()
            def ans():
                vis=[f for f in c.locator(".fu[data-fu=who]").all() if f.is_visible()]
                if vis and not vis[0].locator(".futaps input:checked").count(): vis[0].locator(".futaps input[value=partner]").check(force=True); pg.wait_for_timeout(80)
            def chips():
                ch=c.locator("label.chip input[name$=_c]")
                for i in range(ch.count()):
                    if I.fu_spec("aa",ch.nth(i).get_attribute("value"),dd)[0]=="who": ch.nth(i).check(force=True); pg.wait_for_timeout(80)
            (level(),chips()) if level_first else (level(False),chips(),ans())
            pg.wait_for_timeout(150)
            out.append([q.inner_text() for q in c.locator(".fuq").all() if q.is_visible()])
        b.close()
    return out
for d in ({"who":"parent","name":"Mum"},{"who":"me"}):
    for lf in (True,False):
        for saved in (None,{"bed":{"lvl":"help","c":["every"],"fu":{"lvl:help":{"t":"partner","w":"","tpl":"who"},"every":{"t":"partner","w":"","tpl":"who"}}}}):
            for qs in run(d,saved,lf):
                good=len(qs)==len(set(qs))
                print(("ok  " if good else "FAIL"),d.get("who"),"answer then chips" if lf else "chips then answer","saved" if saved else "new",qs); fails+=0 if good else 1
print("FAILURES:",fails); sys.exit(1 if fails else 0)

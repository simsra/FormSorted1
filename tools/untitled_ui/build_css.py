"""Builds ui.css from ui.css.tpl: Untitled UI icon paths (free set) become small CSS mask/background data URIs."""
import json,sys,urllib.parse,os
H=os.path.dirname(os.path.abspath(__file__))
I=json.load(open(os.path.join(H,"icons.json")) if os.path.exists(os.path.join(H,"icons.json")) else open(os.path.join(H,"..","icons.json")))
def svg(body,stroke="#000",w=2): return "data:image/svg+xml,"+urllib.parse.quote(f"<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='{stroke}' stroke-width='{w}' stroke-linecap='round' stroke-linejoin='round'>{body}</svg>",safe=":/=' ")
M={"CHECK":svg(I["check"],w=2.5),"X":svg(I["x"],w=2.5),
   "PLUSC":svg("<circle cx='12' cy='12' r='10'/><path d='M12 8v8M8 12h8'/>"),"MINUSC":svg("<circle cx='12' cy='12' r='10'/><path d='M8 12h8'/>"),
   "ALERT":svg("<path d='M12 8v4m0 4h.01M22 12c0 5.523-4.477 10-10 10S2 17.523 2 12 6.477 2 12 2s10 4.477 10 10Z'/>"),
   "CHECKG":svg(I["check"],stroke="#079455",w=3),"CHECKW":svg(I["check"],stroke="#fff",w=3.2)}
s=open(os.path.join(H,"ui.css.tpl")).read()
for k,v in M.items(): s=s.replace("%"+k+"%",v.replace('"','%22'))
extra=[open(p).read() for p in sys.argv[2:]]
open(sys.argv[1],"w").write(s+"\n".join(extra))
print("wrote",sys.argv[1],len(s))

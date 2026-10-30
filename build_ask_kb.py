"""Builds ask_kb.txt: the ONLY content the 'Ask a question?' helper may answer from.
Source: the built website (sites/aa-helper/dist) + the app's own help answers. Re-run after the site copy changes:
    python3 build_ask_kb.py /path/to/sites/aa-helper/dist"""
import sys, os, re, html
DIST=sys.argv[1] if len(sys.argv)>1 else "../../sites/aa-helper/dist"
PAGES=[("Home page and FAQ","index.html"),("Attendance Allowance help page","attendance-allowance-form-help/index.html"),
 ("PIP help page","pip-form-help/index.html"),("PIP review help page","pip-review-form-help/index.html"),
 ("DLA for a child help page","dla-form-help/index.html"),("Blue Badge help page","blue-badge-help/index.html"),
 ("Access to Work help page","access-to-work-help/index.html"),("Terms of service","terms.html"),("Privacy notice","privacy.html")]
def text(h):
    m=re.search(r"<main.*?</main>",h,re.S); h=m.group(0) if m else h
    h=re.sub(r"<script.*?</script>|<style.*?</style>|<svg.*?</svg>|<nav.*?</nav>","",h,flags=re.S)
    h=re.sub(r"<(h[1-4]|summary)[^>]*>",r"\n## ",h); h=re.sub(r"</(h[1-4]|summary)>","\n",h)
    h=re.sub(r"<(p|li|tr|div|section|details)[^>]*>","\n",h); h=html.unescape(re.sub(r"<[^>]+>"," ",h))
    lines=[re.sub(r"[ \t]+"," ",l).strip() for l in h.split("\n")]
    out=[]; [out.append(l) for l in lines if l and (not out or out[-1]!=l)]
    return "\n".join(out)
parts=[]
for title,f in PAGES:
    p=os.path.join(DIST,f)
    if os.path.exists(p): parts.append(f"=== {title} ===\n"+text(open(p,encoding="utf-8").read()))
open(os.path.join(os.path.dirname(os.path.abspath(__file__)),"ask_kb.txt"),"w",encoding="utf-8").write("\n\n".join(parts)+"\n")
print("ask_kb.txt", sum(len(x.split()) for x in parts), "words")

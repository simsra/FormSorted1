"""Chat-style customer screens (Simon, 16 Nov 2026: 'chatbot style ... nothing else changes in the work, just design and product flow').
Only the look and the order things are shown in change. Every question, follow-up, form post, saved field, price and payment step
is the same server code as before. CHAT_UI=0 brings back the step-by-step look without a code change."""
import os, re, json
from html import escape as esc
def on(): return os.getenv("CHAT_UI","1")!="0"
NAME="FormSorted assistant"
ORB='<span class=orb aria-hidden=true></span>'
def bot(html,cls=""):
    """An assistant message: the orb, then a bubble. html is trusted server HTML."""
    return f'<div class="turn bot{(" "+cls) if cls else ""}">{ORB}<div class=bub>{html}</div></div>'
def me(text,href=None,label=None):
    """What the customer chose, as their own bubble on the right. text is escaped. href: tap it to change."""
    t=esc(text)
    if href: return f'<div class="turn me"><a class="bub" href="{esc(href)}" aria-label="{esc(label or "Change: "+text)}">{t}<span class=chg>Change</span></a></div>'
    return f'<div class="turn me"><div class=bub>{t}</div></div>'
def note(html): return f'<p class=cnote>{html}</p>'
def prog(n,steps,label=None,sub=""):
    """Subtle progress for the chat header: 'Part 7 of 10 · Your child's details · About 8 minutes left'.
    The full 'Step n of 5' wording stays for screen readers (and the tests)."""
    lab=steps[n-1]+(f": {label}" if label and label!=steps[n-1] else "")
    vis=(label or steps[n-1]).replace(": "," · ",1)
    return (f'<div class=cprog><p class=stepnow><span class=sr>Step {n} of {len(steps)}: <strong>{esc(lab)}</strong>. </span>'
            f'<span aria-hidden=true>{esc(vis)}{" · "+esc(sub) if sub else ""}</span></p>'
            f'<div class=cbar aria-hidden=true><span style="width:{max(6,round(100*(n-1)/len(steps)+ (100/len(steps))*0.5))}%"></span></div></div>')
_PROG=re.compile(r'^\s*(<div class=cprog>.*?</div></div>)',re.S)
def split_prog(body):
    m=_PROG.match(body)
    return (m.group(1),body[m.end():]) if m else ("",body)
FAQ_EXTRA=[("How much does it cost?","Each form has one fixed price, shown when you choose your package. You pay once, at the end, after the questions. No success fee."),
 ("Do you send the form to DWP?","No. You check it, sign it and send it yourself."),
 ("What if I make a mistake?","You can go back and change any answer. After you pay you check every answer before anything is final."),
 ("How long does it take?","About 10 to 15 minutes of questions. Mostly taps."),
 ("Is my information safe?","We only use it to fill in your form. If you don't pay, we delete it after 7 days. National Insurance and bank details go only onto your form.")]
def composer(faq, mode=""):   # returns (bar, help list); the help list goes after the footer
    """The message bar at the bottom: type an answer to the current question, or ask a question.
    Questions are answered from the fixed help list below, in the browser. Nothing typed here is sent anywhere unless it
    becomes your answer to the question on screen (then it is saved with the part, like any typed answer)."""
    data=json.dumps([{"q":q,"a":a} for q,a in faq+FAQ_EXTRA]).replace("</","<\\/")
    return (f'<form class=composer id=composer autocomplete=off data-mode="{esc(mode)}"><label for=cmsg class=sr>Type your answer or a question</label>'
            f'<textarea id=cmsg rows=1 maxlength=600 placeholder="Type an answer or a question"></textarea>'
            f'<button class=send type=submit aria-label=Send><svg viewBox="0 0 24 24" width=22 height=22 aria-hidden=true><path d="M4 12h14M13 6l6 6-6 6" fill=none stroke=currentColor stroke-width=2.4 stroke-linecap=round stroke-linejoin=round /></svg></button></form>'
            ,f'<script id=cfaq type=application/json>{data}</script>')
EXT={"pdf":"PDF","html":"Web page","txt":"Text","docx":"Word"}
def file_chip(href,name,label,main=False):
    ext=name.rsplit(".",1)[-1].lower()
    return (f'<a class="fchip{" main" if main else ""}" href="{esc(href)}" download><span class="fic {esc(ext)}" aria-hidden=true>{esc(EXT.get(ext,ext).split()[0][:4].upper())}</span>'
            f'<span class=fmeta><span class=fname>{esc(name)}</span><span class=fdesc>{esc(label)}</span></span><span class=fdl>Download</span></a>')

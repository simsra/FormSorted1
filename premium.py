"""'Done for you Plus' extras. Everything here is built only from the customer's APPROVED answers (quoted, never reworded),
so nothing new is claimed and the grounding check still holds. No outbound links in any document."""
import html, json
from forms import FORMS
e=lambda s: html.escape(str(s or ""))
PLUS_ITEMS=["Help if you're turned down: send us the decision letter and we prepare your reconsideration letter and revised answers, at no extra charge",
            "Assessment briefing: what DWP may ask, with your own answers to refer to",
            "Supporting letters drafted for your GP, carer, school or family to check and sign",
            "Renewal included: when the review form arrives, we fill it in from your saved answers at no extra charge",
            "Printed and posted to you, with a return envelope (coming soon)",
            "We keep your answers for 3 years if you choose, so all of this is quick"]
ASK={"aa":"DWP may phone you or the person who helps, to check details. They often ask:",
     "dla":"DWP may phone you or write to the school or doctor. They often ask:",
     "pip":"At the assessment (phone, video or face to face) the assessor will usually ask:",
     "pipr":"At the assessment (phone, video or face to face) the assessor will usually ask:"}
Q=["What happens on a typical day, and on a bad day?","How often do you need help, and how long does it take each time?","Who helps, and what exactly do they do?",
   "What happens if nobody helps? Has anything gone wrong (falls, accidents, missed medicines)?","Do you use any aids, and do they fully solve the problem?"]
def _cases(form,d):
    F=FORMS[form]; a=d.get("answers",{})
    return [(l,a.get(t,"").strip()) for t,l,_ in F["topics"] if a.get(t,"").strip()]
def briefing(brand,form,personal,d):
    rows="".join(f"<h3>{e(l)}</h3><p class=you>{e(x)}</p>" for l,x in _cases(form,d))
    return f"""<!doctype html><meta charset=utf-8><title>Assessment briefing</title><style>body{{font:16px/1.5 system-ui;max-width:760px;margin:2em auto;padding:0 1em}}.you{{border-left:4px solid #0b4f6c;padding-left:.8em}}</style>
<h1>Your assessment and phone-call briefing</h1><p>{e(brand)}. Prepared from the answers you approved. Nothing here is new: it's your own words, so you can stay consistent.</p>
<h2>What to expect</h2><p>{e(ASK[form])}</p><ul>{''.join(f'<li>{e(q)}</li>' for q in Q)}</ul>
<h2>Tips</h2><ul><li>Describe a bad day as well as a typical day. Say how often bad days happen.</li><li>Say if you can't do something safely, to a good standard, again when needed, or in a reasonable time.</li><li>You can have someone with you. You can ask for the call to be recorded.</li><li>If you're not sure, say so. Don't guess.</li></ul>
<h2>What you told us, by section</h2>{rows or '<p>No answers yet.</p>'}"""
ROLES={"GP":"GP","Consultant":"consultant","Paediatrician":"paediatrician","Teacher or SENCo":"teacher or SENCo","Family carer":"family carer","Mental health team":"mental health team"}
def supporting_letters(brand,form,personal,d,people):
    nm=" ".join(x for x in (personal.get("other_names"),personal.get("surname")) if x) or "[name]"
    who=[p for p in (people or [])] or ["GP","Family carer"]
    cs=_cases(form,d)[:6]; F=FORMS[form]
    body="".join(f"<li><strong>{e(l)}:</strong> {e(x)}</li>" for l,x in cs)
    out=[]
    for p in who:
        out.append(f"""<section style="page-break-after:always"><h2>Letter for: {e(p)}</h2><p class=hint>Draft for them to check, change and sign. They should only confirm what they know to be true.</p>
<pre style="white-space:pre-wrap;font:inherit">To whom it may concern,

Re: {e(nm)}, {e(F['short'])}

I am {e(nm)}'s {e(ROLES.get(p,p.lower()))}. I have been asked to confirm how their condition affects them day to day.
From what I know, the following is correct:</pre><ul>{body}</ul>
<pre style="white-space:pre-wrap;font:inherit">[Add anything you have seen yourself, and how long you have known them.]

Signed: ____________________   Name: ____________________
Role: {e(p)}   Date: ____________</pre></section>""")
    return f"""<!doctype html><meta charset=utf-8><title>Supporting letters</title><style>body{{font:16px/1.5 system-ui;max-width:760px;margin:2em auto;padding:0 1em}}</style>
<h1>Supporting letters to sign</h1><p>{e(brand)}. Each letter repeats only what you approved. Ask the person to correct anything they can't confirm.</p>{''.join(out)}"""
def appeal_letter_points(form,d,topics):
    F={t:l for t,l,_ in FORMS[form]["topics"]}; a=d.get("answers",{})
    return [{"issue":F[t].split(": ",1)[-1],"why":a.get(t,"")} for t in topics if t in F and a.get(t)]

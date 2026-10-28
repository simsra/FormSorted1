"""'Done for you Plus' extras. Everything here is built only from the customer's APPROVED answers (quoted, never reworded),
so nothing new is claimed and the grounding check still holds. No outbound links in any document."""
import html, json
from forms import FORMS
e=lambda s: html.escape(str(s or ""))
PLUS_ITEMS=["Help if you're turned down: send us the decision letter and we prepare your reconsideration letter and revised answers, at no extra charge",
            "Assessment briefing: what DWP may ask, with your own answers to refer to",
            "Request letters for your GP, carer, school or family, asking them to describe what they've seen",
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
import re as _re
PROF={"GP","Practice nurse","Consultant","Occupational therapist","District nurse","Social worker","Paediatrician","Teacher or SENCo","Speech therapist",
      "Health visitor","CAMHS","Mental health team","Physio","Support worker"}
MED={"GP","Practice nurse","Consultant","District nurse","Paediatrician","Mental health team","CAMHS","Occupational therapist","Speech therapist","Physio","Health visitor"}
SKIP={"conditions","statement","other","contact","support","tried"}
def _topic(l):
    """'Question 30: Toilet needs' / 'Activity 4: Washing and bathing (PIP2 Q6)' / 'Q69–70: Help during the night (from 11pm)' -> 'toilet needs'."""
    l=_re.sub(r"^(Question|Activity)\s*[\d–-]+:\s*|^Q[\d–-]+:\s*","",l); l=_re.sub(r"\s*\((PIP2 Q\d+|from 11pm|age 3\+)\)","",l)
    return l[:1].lower()+l[1:]
def request_topics(form,d):
    """Topic names only (never facts) for the areas where the customer described help in their approved answers."""
    nd=set(d.get("no_difficulty") or []); a=d.get("answers") or {}
    return [_topic(l) for t,l,_ in FORMS[form]["topics"] if t not in SKIP and t not in nd and (a.get(t) or "").strip()]
def supporting_letters(brand,form,personal,d,people,intake=None):
    """Plus: short request letters FROM the customer TO each person, asking them to describe in their own words what they have seen.
    Never a pre-written statement, never the customer's answers for them to sign (Simon, 28 Oct 2026)."""
    I=intake or {}; F=FORMS[form]
    claim={"aa":"Attendance Allowance","dla":"Disability Living Allowance (DLA) for a child","pip":"Personal Independence Payment (PIP)","pipr":"my Personal Independence Payment (PIP) review","atw":"Access to Work"}.get(form,F["name"])
    if form=="dla": claim="Disability Living Allowance (DLA) for children"
    me=form not in ("dla",) and I.get("who") in (None,"","me")
    nm=" ".join(x for x in (personal.get("other_names"),personal.get("surname")) if x) or I.get("name") or ""
    first=personal.get("other_names") or I.get("name") or ""
    obj="me" if me else (first or ("my child" if form=="dla" else "them"))   # who the letter is about
    pos="my" if me else ((first+"'s") if first else ("my child's" if form=="dla" else "their"))
    tops=[t.replace("on them (day)",f"on {obj} during the day").replace("over them (night)",f"over {obj} at night").replace("their needs",f"{pos} needs")
          for t in request_topics(form,d)]
    needs="the help I need" if me else (f"the help {first} needs" if first else ("the help my child needs" if form=="dla" else "the help they need"))
    if form in ("aa","dla"):
        import wholeform as WF
        ref=WF.statement_ref(form)
        where=(f"The {F['short']} form has a box for someone who knows {obj} well to fill in: {ref}. "
               "Only one person can use that box. If we agree you'll use it, I'll give you the form to fill in that part yourself. "
               "Otherwise, a short letter of your own is just as useful, and I'll send it with the form.")
    else:
        where=f"A short letter of your own would help. I'll send it with the {F['form']} form." if form!="atw" else "A short letter of your own would help. I'll send it with my application."
    asks=["how you know "+obj+", and for how long",
          "how often you see "+obj+" or are in touch",
          "what you have seen yourself, on a typical day and on a bad day",
          "how often help is needed and how long it takes, where you know",
          "what happens, or could happen, without help (for example falls, accidents or missed medicines), only if you have seen or been told about it"]
    if any("night" in t for t in tops): asks.append("anything you know about help needed during the night")
    if form=="dla": asks[2]="what you have seen yourself, compared with other children the same age"
    if form=="atw": asks=["how you know me, and for how long","what you have seen at work, or know from your role, about where I need support","what has helped, or what you think would help"]
    who=[p for p in (people or [])] or (["GP","Family carer"] if form!="dla" else ["GP","Teacher or SENCo"])
    out=[]
    for p in who:
        dear="Dear Dr ____," if p=="GP" else ("Dear ____," if p not in PROF else f"Dear {e(ROLES.get(p,p))},")
        verb="am filling in" if form=="pipr" else "am applying for"
        intro=(f"I {verb} {e(claim)} and I would be grateful for your help." if me else
               (f"I am applying for {e(claim)} for {e(nm or obj)}, and I would be grateful for your help." if form=="dla" else
                f"I am helping {e(nm or obj)} apply for {e(claim)}, and I would be grateful for your help."))
        tl=f"<p>It would be most useful to hear about any of these that you have seen yourself:</p><ul>{''.join(f'<li>{e(t)}</li>' for t in tops)}</ul>" if tops else ""
        prof=(f"<p>If it's easier, a short letter on your headed paper confirming {e(pos)} diagnoses and how they affect {e(obj)} day to day would be very helpful.</p>" if p in MED else "")
        out.append(f"""<section class=letter style="page-break-after:always"><p class=hint>For: {e(p)}. A request letter from you. Add your name, then print, email or hand it to them.</p>
<p>{dear}</p><p>{intro} Please could you describe, in your own words, what you have seen yourself of {e(needs)} day to day?</p>
<p>It helps to say:</p><ul>{''.join(f'<li>{e(x)}</li>' for x in asks)}</ul>{tl}{prof}
<p>{e(where)}</p>
<p><strong>Please only write what you know to be true.</strong> Use your own words, and leave out anything you haven't seen or aren't sure about. Please add your name, how you know {e(obj)}, and a phone number or address in case they need to contact you.</p>
<p>Thank you very much for your help.</p><p>Best wishes,<br>[Your name]</p></section>""")
    return f"""<!doctype html><meta charset=utf-8><title>Request letters</title><style>body{{font:16px/1.5 system-ui;max-width:760px;margin:2em auto;padding:0 1em}}.hint{{color:#555;font-size:.9em;border-left:4px solid #0b4f6c;padding-left:.6em}}</style>
<h1>Request letters for your GP, carer, school or family</h1><p>{e(brand)}. Each letter asks the person to describe, in their own words, what they have seen themselves. We don't write anything for them: what they say must come from them.</p>{''.join(out)}"""
def appeal_letter_points(form,d,topics):
    F={t:l for t,l,_ in FORMS[form]["topics"]}; a=d.get("answers",{})
    return [{"issue":F[t].split(": ",1)[-1],"why":a.get(t,"")} for t in topics if t in F and a.get(t)]

"""Mandatory reconsideration (MR) letter draft. Uses only what the customer writes. Source: https://www.gov.uk/mandatory-reconsideration"""
from datetime import date
from html import escape as e
NAMES={"aa":"Attendance Allowance","dla":"Disability Living Allowance (child)","pip":"Personal Independence Payment (PIP)","pipr":"Personal Independence Payment (PIP)"}
AUTH={"poa":"I have Power of Attorney for {n}.","appointee":"I am {n}'s appointee.","deputy":"I am {n}'s deputy (Court of Protection)."}
def _voice(form,d):
    """Who is writing. d['for'] (optional): {'who': intake 'who' ('me' or someone else), 'signer': 'them'/'poa'/'appointee'/'deputy'/'ns'}.
    Child DLA is always written by the parent or carer. Returns (about-the-claim phrase, authority line, signature block)."""
    f=d.get("for") or {}; claimant=(d.get("name") or "").strip()
    if form!="dla" and (f.get("who") in (None,"","me") or f.get("signer")=="them"):   # the claimant signs: their own letter
        helped="" if f.get("who") in (None,"","me") else "\n\n(Written with help from [helper's name], [how they're connected])"
        return f"my {NAMES[form]} claim","",(claimant or "[Your name]")+helped
    n=claimant or ("my child" if form=="dla" else "[their name]")
    if form=="dla":
        about=f"the {NAMES[form]} claim for my child{', '+claimant+',' if claimant else ''}"
        return about,"",f"[Your name]\nParent or guardian of {n}"
    about=f"the {NAMES[form]} claim for {n}"
    auth=AUTH.get(f.get("signer") or "","").format(n=n) or f"I am writing on behalf of {n}. [Say how you're connected, e.g. daughter. If you are not their attorney or appointee, {n} should sign this letter too.]"
    return about,auth,f"[Your name]\n[How you're connected to {n}]"+("" if f.get("signer") in AUTH else "\n\nSigned by "+n+": ______________")
def mr_letter(form, d):
    """d: name, address (the claimant's), ni (optional, user types), decision_date, points (list of {issue, why}), evidence(list), today,
    for (optional, see _voice) when someone writes for another person."""
    today=d.get("today") or date.today().strftime("%d %B %Y")
    about,auth,sig=_voice(form,d); other=not about.startswith("my ")
    pts="\n".join(f"{i+1}. {p['issue'].strip()}\n   {p['why'].strip()}" for i,p in enumerate(d.get("points",[])) if p.get("issue","").strip())
    ev="\n".join(f"- {x.strip()}" for x in d.get("evidence",[]) if x.strip()) or "- (list any letters or reports you're sending)"
    lab="National Insurance number" if not other else ("Reference or National Insurance number (as on the decision letter)")
    ref=f"{lab}: {d['ni']}\n" if d.get("ni") else f"{lab}: [write it here]\n"
    head=(f"{'Child' if form=='dla' else 'Claimant'}: {d.get('name') or '[their name]'}\n{d.get('address') or '[their address]'}" if other else f"{d.get('name') or '[Your name]'}\n{d.get('address') or '[Your address]'}")
    return f"""{head}

{today}

Dear Sir or Madam,

Request for mandatory reconsideration: {NAMES[form]}
{ref}Date of decision letter: {d.get('decision_date') or '[date on your decision letter]'}

I am writing to ask you to look again at the decision about {about} dated {d.get('decision_date') or '[date]'}. {auth+' ' if auth else ''}I disagree with the decision for the reasons below.

{pts or '1. [What part of the decision is wrong]\n   [What actually happens, with how often and how long]'}

I am enclosing the following evidence:
{ev}

Please consider all of the information on the claim form together with this letter and the enclosed evidence. Please send me a copy of the evidence used to make the decision, including any assessment report.

Yours faithfully,

{sig}
"""

"""Mandatory reconsideration (MR) letter draft. Uses only what the customer writes. Source: https://www.gov.uk/mandatory-reconsideration"""
from datetime import date
from html import escape as e
NAMES={"aa":"Attendance Allowance","dla":"Disability Living Allowance (child)","pip":"Personal Independence Payment (PIP)","pipr":"Personal Independence Payment (PIP)"}
def mr_letter(form, d):
    """d: name, address, ni (optional, user types), decision_date, points (list of {issue, why}), evidence(list), today."""
    today=d.get("today") or date.today().strftime("%d %B %Y")
    pts="\n".join(f"{i+1}. {p['issue'].strip()}\n   {p['why'].strip()}" for i,p in enumerate(d.get("points",[])) if p.get("issue","").strip())
    ev="\n".join(f"- {x.strip()}" for x in d.get("evidence",[]) if x.strip()) or "- (list any letters or reports you're sending)"
    ref=f"National Insurance number: {d['ni']}\n" if d.get("ni") else "National Insurance number: [write it here]\n"
    return f"""{d.get('name') or '[Your name]'}
{d.get('address') or '[Your address]'}

{today}

Dear Sir or Madam,

Request for mandatory reconsideration: {NAMES[form]}
{ref}Date of decision letter: {d.get('decision_date') or '[date on your decision letter]'}

I am writing to ask you to look again at the decision about my {NAMES[form]} claim dated {d.get('decision_date') or '[date]'}. I disagree with the decision for the reasons below.

{pts or '1. [What part of the decision is wrong]\n   [What actually happens, with how often and how long]'}

I am enclosing the following evidence:
{ev}

Please consider all of the information on my claim form together with this letter and the enclosed evidence. Please send me a copy of the evidence used to make the decision, including any assessment report.

Yours faithfully,

{d.get('name') or '[Your name]'}
"""

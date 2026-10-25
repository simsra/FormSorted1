"""Deadline & backdating tracker. Facts verified on GOV.UK on 24 Oct 2026:
- AA: https://www.gov.uk/attendance-allowance/how-to-claim  "If you call the helpline to get a form, your claim will start on the date of your call (if you return the form within 6 weeks)." Printed form: starts the date DWP receives it. Helpline 0800 731 0122.
- Child DLA: https://www.gov.uk/disability-living-allowance-children/how-to-claim  claim starts on date received or date you call the enquiry line "if you return the claim pack within 6 weeks". "It cannot be backdated." Helpline 0800 121 4600.
- PIP2: https://www.gov.uk/pip/how-to-claim  "You should return the form ... within 1 month. Contact the PIP enquiry line if you need more time."
- Mandatory reconsideration: https://www.gov.uk/mandatory-reconsideration  usually within one month of the date of the decision; later with a good reason.
AR1 (PIP review): deadline NOT verified -> we only tell users to use the date on their letter."""
from datetime import date, timedelta
from facts import v, src
import calendar
def add_month(d):
    y,m=(d.year+(d.month//12), d.month%12+1); return date(y,m,min(d.day,calendar.monthrange(y,m)[1]))
LINES={"aa":("Attendance Allowance helpline",v("aa_helpline")),"dla":("Disability Living Allowance helpline",v("dla_helpline")),
       "atw":("Access to Work helpline",v("atw_helpline")),"pip":("PIP enquiry line","the number on your PIP letter"),"pipr":("PIP enquiry line","the number on your review letter")}
SRC={"aa":src("aa_phone_window_weeks"),"dla":src("dla_phone_window_weeks"),"pip":src("pip2_return_months"),"pipr":src("ar1_deadline"),"atw":src("atw_cost_share_weeks")}
def parse(s):
    try: return date.fromisoformat(s) if s else None
    except ValueError: return None
def compute(form, how, requested, received, today=None):
    today=today or date.today(); r=parse(requested); rc=parse(received); res={"form":form,"source":SRC[form],"line":LINES[form]}
    if form in("aa","dla"):
        if how=="phone" and r:
            dl=r+timedelta(weeks=v(f"{form}_phone_window_weeks"))
            res.update(deadline=dl.isoformat(),days_left=(dl-today).days,
              rule=f"You asked for the form by phone on {r:%d %B %Y}. If DWP gets it back within 6 weeks, the claim starts from the date of your call.",
              backdate=f"Return by {dl:%d %B %Y} to keep your claim starting from {r:%d %B %Y}.")
        else:
            res.update(deadline=None,days_left=None,rule="You printed or downloaded the form, so your claim starts on the date DWP receives it. There's no 6-week window, so every day you wait is a day less money. Send it as soon as it's ready.",backdate="")
        if form=="dla": res["rule"]+=" DLA cannot be backdated."
    elif form=="pip":
        base=rc or r
        if base:
            dl=add_month(base); res.update(deadline=dl.isoformat(),days_left=(dl-today).days,
              rule=f"GOV.UK says to return the PIP2 form within 1 month. Counting from {base:%d %B %Y}, that's about {dl:%d %B %Y}. If your form or letter gives a different date, use that one.",backdate="")
        else: res.update(deadline=None,days_left=None,rule="GOV.UK says to return the PIP2 form within 1 month. Check the date on your form or letter.",backdate="")
    elif form=="atw":
        if how=="self":
            res.update(deadline=None,days_left=None,rule="You're self-employed, so employer cost sharing doesn't apply. Apply when you're ready.",backdate="")
        elif r:
            dl=r+timedelta(weeks=v("atw_cost_share_weeks")); left=(dl-today).days
            res.update(deadline=dl.isoformat(),days_left=left,rule=f"You started (or will start) this job on {r:%d %B %Y}. If you apply within 6 weeks of starting, by {dl:%d %B %Y}, Access to Work can consider paying up to 100% of approved costs. After 6 weeks, your employer may have to share the cost of special equipment and workplace changes (not support workers or travel).",backdate="")
        else: res.update(deadline=None,days_left=None,rule="If you're starting a new job, applying within 6 weeks of your start date can avoid your employer sharing the cost of equipment or workplace changes. You can apply up to 12 weeks before you start.",backdate="")
    else:
        res.update(deadline=None,days_left=None,rule="Use the return date printed on your AR1 review letter. If you can't meet it, phone before it passes.",backdate="")
    return res
def script(form,name=""):
    line,num=LINES[form]; f={"aa":"Attendance Allowance claim form","dla":"DLA claim form for my child","pip":"PIP2 'How your disability affects you' form","pipr":"PIP review form (AR1)","atw":"Access to Work application"}[form]
    return [f"Call the {line} on {num}. Have the form and any letter in front of you.",
      f"Say: \"Hello, my name is {name or '[your name]'}. I'm calling about my {f}. I'm still working on it and I need more time to send it back.\"",
      "Give the reason in one sentence, e.g. \"I'm waiting for an appointment with an adviser\" or \"I'm waiting for letters from the hospital\" or \"my health has been bad\".",
      "Ask: \"Can you give me more time, and what new date should I send it back by?\"",
      "Write down the date of the call, the name of the person you spoke to and the new date they gave. Keep this with your copy of the form."]

def atw_reconsider_script(name=""):
    return [f"Call the Access to Work helpline on {v('atw_helpline')} (Monday to Friday, 9am to 5pm). Have your decision letter and reference number ready.",
      f"Say: \"Hello, my name is {name or '[your name]'}. I've had a decision on my Access to Work application and I'd like to ask for it to be reconsidered.\"",
      "Explain, in one or two sentences each, which part of the decision you disagree with and why, using your support-needs summary.",
      "Offer any new evidence (quotes, letters from a specialist or assessor) and ask how to send it.",
      "Write down the date, the name of the person you spoke to and what happens next."]

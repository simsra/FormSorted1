"""Form registry: one engine, several government forms. Each form = question topics + delivery (filled PDF or typed answers)."""
import os
from questions import CARE_QUESTIONS
import plus as _plus
def _plus_summary(f): return _plus.summary(f)   # per-form Plus copy lives in plus.py
# Topic tuple: (id, label shown in pack, chat prompt)
AA_TOPICS=[(str(q),f"Question {q}: {t}",p) for q,t,p,_ in CARE_QUESTIONS]
DLA_TOPICS=[
 ("conditions","Q40: Health conditions, treatment and how often","What are the child's conditions or disabilities, since when, what treatment do they have and how often?"),
 ("42","Q42: How their needs change from day to day","How do the child's needs vary day to day or week to week? What is a bad day like and how many bad days a week?"),
 ("walking","Q44–48: Walking and moving around (age 3+)","If the child is 3 or over: how far can they walk before severe discomfort, how fast, do they fall, any pain, breathlessness, tiredness? Compare with a child of the same age without a disability."),
 ("outdoors","Q49–50: Guidance or supervision outdoors, falls","Do they need someone with them outdoors most of the time (e.g. no sense of danger, running off, panic, sight loss)? Do they fall? Compare with other children the same age."),
 ("daycare","Q54–60: Care during the day","During the day, what extra help do they need with toilet, washing, dressing, eating and drinking, moving indoors and stairs, and medicines or treatment, beyond what a child of the same age needs? How often and how long each time?"),
 ("senses","Q61–64: Seeing, hearing, speaking, communicating","Any difficulty seeing, hearing, speaking or understanding and being understood? What help does that need?"),
 ("65","Q65: Fits, blackouts or seizures","Do they have fits, blackouts or seizures? What type, how often, what happens and what do you do?"),
 ("supervision_day","Q66: Supervision during the day","Does the child need watching more than other children the same age (unaware of danger, self-harm, behaviour, wandering)? Give an example of what happens."),
 ("development","Q67: Extra help with development","Do they need extra help with learning, play, understanding or social skills at home?"),
 ("school","Q68: School or nursery","At school or nursery: what extra help do they get with learning (EHCP / IDP, 1:1 support)? What is their behaviour like? How do they get there?"),
 ("night","Q69–70: Help during the night (from 11pm)","At night (when everyone is in bed): what help do they need — settling, toilet, treatment, turning, supervision? How many nights a week, how many times a night, how many minutes each time?"),
 ("statement","Q38: Who could write the statement (they write it themselves)","Who knows the child well (teacher, SENCo, health visitor, therapist, relative) and could write a short statement?"),
]
DLA_FIELDS={"42":"42_1","walking":"48_1","65":"65_1","school_learning":"68_7","school_behaviour":"68_8","school_travel":"68_9",
 "mobility_other":"53","care_other":"72","anything_else":"89","statement":"38_3","reports":"24_1"}
DLA_NIGHT_FIELDS={ # (nights/week, minutes, times a night)
 "night_bed":("70_1","70_2","70_3"),"night_toilet":("70_4","70_5","70_6"),"night_treatment":("70_7","70_8","70_9"),
 "night_settle":("70_10","70_11","70_12"),"night_danger":("70_13","70_14","70_15"),"night_wander":("70_16","70_17","70_18"),"night_behaviour":("70_19","70_20","70_21")}
DLA_PERSONAL={"surname":"2","other_names":"3","dob":"6","addr1":"8","addr2":"8_1","addr3":"8_2","postcode":"8_3",
 "parent_surname":"73","parent_other_names":"74","parent_title":"74_1","relationship":"82","phone":"79_1","email":"79"}
DLA_CONDITION_FIELDS=[(f"40_{4*i+1}",f"40_{4*i+2}",f"40_{4*i+3}",f"40_{4*i+4}") for i in range(5)]
# Never filled on DLA1A: NI numbers (5, 76, 81_2), bank details (84-88), signature/date, tick boxes.

PIP_ACTIVITIES=[ # (activity no., name, PIP2 question, prompt)
 (1,"Preparing food","Q3","Can you prepare and cook a simple meal for one from fresh ingredients? Using a hob or microwave, chopping, lifting pans — what goes wrong, what aids or help do you use?"),
 (2,"Taking nutrition (eating and drinking)","Q4","Cutting food, getting food to your mouth, chewing, swallowing, knowing when to eat or that you've had enough, feeding tube?"),
 (3,"Managing therapy or monitoring a health condition","Q5","Medication, monitoring blood sugar or symptoms, therapies at home (e.g. physio exercises, dialysis) — do you need reminding or help?"),
 (4,"Washing and bathing","Q6","Washing your body and hair, getting in or out of a bath or shower, aids, safety, how long it takes?"),
 (5,"Managing toilet needs or incontinence","Q7","Getting on and off the toilet, cleaning yourself, incontinence, accidents, pads?"),
 (6,"Dressing and undressing","Q8","Fastenings, socks and shoes, choosing suitable clothes, knowing when to change, how long it takes?"),
 (7,"Communicating verbally","Q9","Speaking, hearing and understanding what people say, in your own language?"),
 (8,"Reading and understanding signs, symbols and words","Q10","Reading and understanding basic and complex written information, signs, letters?"),
 (9,"Engaging with other people face to face","Q11","Meeting and mixing with people, anxiety, distress, needing someone with you?"),
 (10,"Making budgeting decisions","Q12","Working out change, paying bills, budgeting, decisions about money?"),
 (11,"Planning and following journeys","Q13","Planning a route, following it on familiar and unfamiliar journeys, going out alone, anxiety or panic, needing someone with you?"),
 (12,"Moving around","Q14","How far can you walk (using any aids) before you need to stop because of pain, breathlessness or exhaustion? How long does it take? What happens afterwards?"),
]
PIP_TOPICS=[("conditions","Q1–2: Conditions, medicines, treatments and professionals","What are your health conditions, medicines and doses, treatments, and which health professionals know you best?")]+\
 [(f"a{n}",f"Activity {n}: {name} (PIP2 {q})",p+" How many days a week is it like this? Can you do it safely, to a good standard, as often as needed and in a reasonable time?") for n,name,q,p in PIP_ACTIVITIES]+\
 [("other","Q15: Additional information","Anything else: how things vary, bad days, side effects, recent hospital stays, what evidence you have.")]

ATW_TOPICS=[
 ("conditions","About your condition","What health condition or disability affects you at work, and roughly since when? (You don't need a diagnosis.)"),
 ("job","Your job and daily tasks","What is your job, how many hours do you work, and where (workplace, home or both)? What are the main tasks you do on a normal day?"),
 ("barriers","Where work gets hard","Which of those tasks are hard because of your condition? What happens, how often, and how long does it affect you?"),
 ("travel","Getting to and from work","How do you get to work? Is there anything that makes public transport or the journey hard? What happens?"),
 ("communication","Meetings, communication and focus","Do you have difficulty with meetings, phone calls, reading, writing, concentrating or managing your mental health at work? Give an example."),
 ("tried","What has been tried already","What changes or support has your employer (or you) already tried, and did they help?"),
 ("support","What would help","What support do you think would help? For example equipment or software, a support worker (how many hours a week), taxis to work, or changes to the workplace. Include any costs or quotes you know."),
 ("contact","Workplace contact","Who at work could confirm you work there (their role, not personal details)? Are you employed or self-employed?"),
]

# Nov 2026 pricing (Simon, 16 Nov 2026): two options per form, chosen at the pay step, paid once at the end.
#   "1999" £19.99  Download: the filled-in form as a PDF to print, sign and send yourself.
#   "2999" £29.99 Posted to you, with support: we print the finished form and post it to the customer with a prepaid
#          envelope addressed to the right DWP office and sign-here markers. The customer signs and posts it themselves.
#          Support until their decision, for up to SUPPORT_DAYS (fixed, no auto-renew).
# £99 "Done for you" and £199 "Done for you Plus" are now legacy_tiers: they only describe orders bought before this change.
SUPPORT_DAYS=183
def gbp(p): return f"£{p//100}" if p%100==0 else f"£{p//100}.{p%100:02d}"   # "up to 6 months" (flagged for Simon to confirm)
_DL_WHAT={"aa":"the whole AA1 form filled in","dla":"the whole DLA1A form filled in","pip":"typed answers for every PIP2 activity, with extra sheets","pipr":"typed answers for every AR1 activity, with extra sheets"}
def DOWNLOAD(form):
    return ("Download",1999,f"Download {_DL_WHAT[form]}, as a PDF to print, sign and send yourself. Plus an evidence checklist and a request letter for your GP.")
def POSTED(form):
    return ("Posted to you, with support",2999,f"Everything in Download, plus we print it and post it to you, with sign-here markers and a prepaid envelope addressed to the right DWP office. You sign it and post it back yourself. Support until your decision, for up to 6 months: help with any question, reminders about your decision, and plain-English help with DWP letters.")
# POSTED_OPTION (Simon, 23 Nov 2026): only the £19.99 Download goes live. "Posted to you, with support" (£29.99) is not
# offered to customers until Simon OKs its Terms and a posting provider. Off: tier "2999" is hidden (kept in hidden_tiers so
# tier_info still describes it), the pay step shows Download only, and /pay ignores pack=2999. Set POSTED_OPTION=1 to offer it.
POSTED_ON=os.getenv("POSTED_OPTION","0")=="1"
def _offer(form): return {"1999":DOWNLOAD(form),"2999":POSTED(form)} if POSTED_ON else {"1999":DOWNLOAD(form)}
def _hidden(form): return {} if POSTED_ON else {"2999":POSTED(form)}
FORMS={
 "aa":{"name":"Attendance Allowance","short":"Attendance Allowance (AA1)","form":"AA1","gov":"https://www.gov.uk/attendance-allowance",
   "who":"State Pension age and over","topics":AA_TOPICS,"pdf":"aa1.pdf","pdf_out":"AA1-filled.pdf",
   "tiers":_offer("aa"),"hidden_tiers":_hidden("aa"),
   "legacy_tiers":{"49":("Claim Answers",4900,""),"79":("Form pack",7900,""),"99":("Done for you",9900,"We fill in the official AA1 form for you, ready to print and sign. Plus answers to every care question in your own words, an evidence checklist, and a request letter for your GP."),"199":("Done for you Plus",19900,_plus_summary("aa"))},
   "subject":"the person claiming"},
 "dla":{"name":"Child DLA","short":"Disability Living Allowance for children (DLA1A)","form":"DLA1A","gov":"https://www.gov.uk/disability-living-allowance-children",
   "who":"children under 16","topics":DLA_TOPICS,"pdf":"dla1a.pdf","pdf_out":"DLA1A-filled.pdf",
   "tiers":_offer("dla"),"hidden_tiers":_hidden("dla"),
   "legacy_tiers":{"49":("Answers",4900,""),"79":("Form pack",7900,""),"99":("Done for you",9900,"We fill in the official DLA1A form for you, ready to check, sign and post free. Plus answers to every question in your own words, mapped to the question numbers, and a school and medical evidence checklist."),"199":("Done for you Plus",19900,_plus_summary("dla"))},
   "subject":"the child"},
 "pip":{"name":"PIP","short":"PIP: How your disability affects you (PIP2)","form":"PIP2","gov":"https://www.gov.uk/pip",
   "who":"16 to State Pension age","topics":PIP_TOPICS,"pdf":None,
   "tiers":_offer("pip"),"hidden_tiers":_hidden("pip"),
   "legacy_tiers":{"59":("PIP Answers",5900,""),"79":("PIP Complete Pack",7900,""),"99":("Done for you",9900,"Typed answers for all 12 activities, mapped to each PIP2 question, PIP extra sheets ready to print and send with your form, an evidence checklist, a phone-call prep sheet, assessment notes and a request letter for your GP."),"199":("Done for you Plus",19900,_plus_summary("pip"))},
   "subject":"you (or the person you help)"},
 "pipr":{"name":"PIP review","short":"PIP review form (AR1)","form":"AR1","gov":"https://www.gov.uk/pip/when-your-pip-claim-is-reviewed",
   "who":"people already getting PIP","topics":PIP_TOPICS,"pdf":None,
   "tiers":_offer("pipr"),"hidden_tiers":_hidden("pipr"),
   "legacy_tiers":{"59":("PIP Answers",5900,""),"79":("PIP Complete Pack",7900,""),"99":("Done for you",9900,"Typed answers for all 12 activities, mapped to each AR1 activity section, extra sheets ready to send, an evidence checklist, a 'what has changed' summary, an assessment-call prep sheet and a request letter for your GP."),"199":("Done for you Plus",19900,_plus_summary("pipr"))},
   "subject":"you (or the person you help)"},
 "atw":{"name":"Access to Work","short":"Access to Work application","form":"AtW","gov":"https://www.gov.uk/access-to-work",
   "who":"people in or starting paid work","topics":ATW_TOPICS,"pdf":None,
   "tiers":{"49":("Access to Work Answers",4900,"Typed answers ready to paste into the online application or read out on the phone, in the order it asks."),
            "79":("Access to Work Complete Pack",7900,"Everything above, plus a support-needs summary and cost list, a call prep sheet, and notes for asking for a reconsideration if you disagree with the decision.")},
   "subject":"you"},
}
FORMS["bb"]={"name":"Blue Badge","short":"Blue Badge application answers","form":"Blue Badge","gov":"",
   "who":"anyone applying for a Blue Badge, or helping someone apply","topics":[],"pdf":None,"kind":"bluebadge",
   "tiers":{"29":("Blue Badge answers",2900,"Answers for the online Blue Badge application, ready to paste, a hidden-disability write-up, a checklist of what to upload, and a letter asking the council to look again if refused"),
            "15":("Blue Badge answers (add-on)",1500,"Answers for the online Blue Badge application, ready to paste, prepared from the answers you already gave us")},
   "included_tiers":{"0":("Blue Badge answers (included with Done for you Plus)",0,"Answers for the online Blue Badge application, ready to paste, prepared from the answers you already gave us")},
   "subject":"the person the badge is for"}


# Tick-"Yes" questions, derived from which topics have an approved answer (the model doesn't know DLA question numbers).
TICK_MAP={"dla":{"42":"42","walking":"44","outdoors":"49","daycare":"54–60 (each care need you described)","senses":"61–64 (the ones you described)",
                 "65":"65","supervision_day":"66","development":"67","school":"68","night":"69–70"}}
def tick_list(form, answers):
    """Question numbers to tick Yes, for topics with a non-empty answer. AA topic ids are the question numbers."""
    a=answers or {}; ids=[t for t,_,_ in FORMS[form]["topics"] if (a.get(t) or "").strip()]
    if form=="aa": return [t for t in ids if t.isdigit()]
    m=TICK_MAP.get(form); return [m[t] for t in ids if t in m] if m else []

# One "done for you" product per form (priced at FULL). A premium tier (e.g. "199") can be added to a form's "tiers" later;
# anything in FULL_TIERS gets the complete pack. "legacy_tiers" only describe orders bought before the price change.
FULL_TIERS={"79","99","199","1999","2999"}
def is_full(tier): return str(tier) in FULL_TIERS
def tier_info(form,tier):
    f=FORMS[form]; return f["tiers"].get(tier) or f.get("included_tiers",{}).get(tier) or f.get("hidden_tiers",{}).get(tier) or f.get("legacy_tiers",{}).get(tier) or next(iter(f["tiers"].values()))
def default_tier(form): return list(FORMS[form]["tiers"])[0]
PREMIUM_TIERS={"199"}
def is_premium(tier): return str(tier) in PREMIUM_TIERS
POSTED_TIERS={"2999"}
def is_posted(tier): return str(tier) in POSTED_TIERS
TWO_OPTION_FORMS=("aa","dla","pip","pipr")
def options(form): return list(FORMS[form]["tiers"]) if (form in TWO_OPTION_FORMS and len(FORMS[form]["tiers"])>1) else []   # [] = nothing to choose at the pay step

# Where the prepaid envelope in the posted pack is addressed. DWP Freepost addresses need no stamp, licence or postcode:
# "Do not write anything except the freepost address" (GOV.UK). None = not confirmed: the fulfilment queue says to check.
RETURN_ADDR={"aa":"Freepost DWP Attendance Allowance",       # gov.uk/attendance-allowance/how-to-claim
             "dla":"Freepost DWP DLA Child",                  # gov.uk/disability-service-centre
             "pip":"Freepost RTEU-HBEC-RGTG\nPersonal Independence Payment\nMail Handling Site A\nWolverhampton\nWV98 1AA",   # PIP2 booklet
             "pipr":None}                                     # AR1: use the return address printed on the customer's review form

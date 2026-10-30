"""Form writer (30 Oct 2026, Claude): writes each box from the customer's own answers and nothing else.
1. facts(): every answer becomes a short numbered fact (F1, F2...) tied to a form box. Taps, the whole-form questions,
   quick checks and the customer's own words all count; nothing else does (no documents unless confirmed, no guesses).
2. Claude writes each box as sentences, and every sentence must name the facts it comes from.
3. Any sentence with no valid fact, or with a number, frequency or strong word ('always', 'never'...) that its facts
   don't have, is dropped (no model needed).
4. A second Claude pass (the verifier) checks each sentence against its facts and removes anything unsupported.
5. The usual answer check (grounding.py) still runs before the customer approves, with these facts in its source.
Voice: the claimant's own first person ('I'), as DWP asks even when someone else fills it in; DLA in the parent's voice
about the child. If Claude can't be reached the tap sentences (intake.fallback_draft) are used, as before."""
import json, re, os
import intake as I, claude as cl, llm
from forms import FORMS
NOT_DRAFTED={"dla":{"statement"}}   # the statement box is for the person who knows the child; we only say who could write it (left blank)
TOPIC_OF={"aa":[("bed_enc","29"),("pr_indoors","33"),("comm2","37"),("falls_m","34"),("fall_what","34"),("stum_","34"),("eye","40"),("w_","44"),("n_","42"),("aid_","33")],
 "dla":[("bed","daycare"),("toilet2","daycare"),("comm_","senses"),("fit_","65"),("superv_g","supervision_day"),("dev_g","development"),("school_g","school"),("sc_behav","school"),("sc_travel","school"),
        ("out_g","outdoors"),("hobby","development"),("acts","development"),("ah_","development"),("ao_","development"),("al_","development"),("a_","development"),("canwalk","walking"),("dist","walking"),("gait","walking"),
        ("walk_","walking"),("aid_","daycare")]}
SKIP_WF=("_diff","aid_p")
LV={"ok":"no difficulty","slow":"struggles (slow, painful or tiring: at least one, not said which)","help":"needs help or someone there (help, prompting or watching: at least one, not said which)","cant":"can't do it safely on their own"}
def _ans(q,w):
    import wholeform as W
    v=w.get(q["id"]); x=w.get(q["id"]+"_x",""); k=q["kind"]; o=dict(q["opts"])
    if k=="tap": parts=[lab for sid,lab,_ in q["rows"] if sid in (v or [])]+(["none of these"] if v==["none"] else [])
    elif k=="grid": parts=[lab for sid,lab in q["rows"] if w.get(sid)=="yes"]
    elif k=="checks": parts=[o.get(t,t) for t in (v or [])]
    elif k=="radio": parts=[o.get(v,v)] if v else []
    else: parts=[str(v)] if v else []
    return "; ".join(p for p in parts+([x] if x else []) if p)
def facts(form,d,history=None):
    """[{id, topic, text}] in form order. topic '*' = can support any box (e.g. 'about the claim')."""
    out=[]; add=lambda t,s: s and s.strip() and out.append({"id":f"F{len(out)+1}","topic":t,"text":" ".join(s.split())})
    if form=="pipr" or not d:   # chat orders: each customer reply is a fact for any box
        for m in history or []:
            if m["role"]=="user": add("*",m["content"][:1500])
        return out
    intro,T=I.topic_texts(form,{**d,"rows":{}}); add("*",intro)   # everything except the task cards...
    me=I.is_me(d,form)
    for r in I.rows(form,None,d):   # ...which become one fact per tap, so the writer composes rather than copies
        v=(d.get("rows") or {}).get(r[0])
        if not v: continue
        rid,t,lab,_,chips=r; lv=v.get("lvl") or ("help" if v.get("help") else "slow" if v.get("hard") else "")
        if lv: add(t,f"{lab}: {LV[lv]}.")
        cm={c[0]:I.pw(c[1],me,form) for c in chips}
        for c in v.get("c") or []:
            if c in cm: add(t,f"{lab}, what's hard: {cm[c]}.")
            elif c in I.FX_T: add(t,f"{lab}: {I.FX_T[c]}.")
        if I._ok(v.get("days")): add(t,f"{lab}: like this {v['days']} days a week.")
        sm=dict(I.PIP_STD); st=[sm[x].lower() for x in v.get("std",[]) if x in sm]
        if st: add(t,f"{lab}: can only be done "+", ".join(st)+".")
        if I._ok(v.get("freq")): add(t,f"{lab}: like this {I.FREQ_T[v['freq']].lower()}.")
        if I.TIME_T.get(v.get("time","")): add(t,f"{lab}: each time takes {I.TIME_T[v['time']]}.")
        if v.get("x"): add(t,f"{lab}, in the customer's own words: {v['x']}")
        if v.get("lvl_x"): add(t,f"{lab}, how it is, typed detail in the customer's own words: {v['lvl_x']}")
        if v.get("days_x"): add(t,f"{lab}, how many days a week, in the customer's own words: {v['days_x']}")
        # inline follow-ups (30 Oct, main 6504e73): v['fu'][chip id or 'lvl:<level>'] = {'t': tapped answer, 'w': typed words, 'tpl'}
        for key,f in (v.get("fu") or {}).items():
            if key.startswith("lvl:"):
                if key[4:]!=v.get("lvl"): continue
                what=dict(I.LVL).get(key[4:],"")
            elif key in (v.get("c") or []): what=cm.get(key) or I.pw(I.FX_ALL.get(key,key),me,form)
            else: continue
            what=what[0].lower()+what[1:] if what else what
            if f.get("w"): add(t,f"{lab}, {what}, typed detail in the customer's own words: {f['w']}")
            _,q,tp,_=I.fu_spec(form,key,d); tl=dict(tp).get(f.get("t"))
            if tl: add(t,f"{lab}, {what}, {q.rstrip('?')}: {tl}.")
    if d.get("words"): add("*","In the customer's own words: "+d["words"])
    for t,_,_ in FORMS[form]["topics"]:
        for s in re.split(r"(?<=\.)\s+(?=[A-Z])",T.get(t) or ""):
            if not s.startswith("In my own words:"): add("*" if t=="other" else t,s)   # PIP 'other' (own words, aids) can back any box
    if d.get("wf_v") and form in TOPIC_OF:
        import wholeform as W
        w=d.get("wf") or {}; row_topic={r[0]:r[1] for r in I.rows(form,None,d)}
        for sec in ("often","home"):
            for q in W.questions(form,sec,d):
                qid=q["id"]
                if not W.dep_ok(q,w) or qid.endswith(SKIP_WF) or (sec=="home" and not qid.startswith("aid_")): continue
                a=_ans(q,w)
                if not a: continue
                m=re.match(r"(?:sub|t|m)_([a-z]+)",qid); top=row_topic.get(m.group(1)) if m else None
                top=top or next((t for p,t in TOPIC_OF[form] if qid.startswith(p)),None)
                if top: add(top,f"{q['label'].rstrip('?:')}: {a}.")
    return out
VOICE={"aa":"Write as the person claiming, in the first person ('I need help...'), even when a relative is filling it in: DWP asks about the claimant, not the helper. Use 'my partner', 'my daughter' etc. only when the facts say who.",
 "dla":"Write as the parent or carer, about the child by name or as 'my child' ('Leo needs help or someone with him to...', 'Leo can't do this safely on his own'). Use 'I' ONLY for the parent's own actions ('I have to stay with him'). Never write 'I need help' or 'I can't' about the child's needs.",
 "pip":"Write as the person claiming, in the first person ('I can't...').","pipr":"Write as the person claiming, in the first person ('I can't...')."}
SYS="""You write answers for a UK benefit form ({short}) from the customer's own answers. The customer reads and approves every word.
FACTS are numbered (F1, F2...). Each belongs to a box (topic) or '*' (any box). They are the ONLY source of truth.
{voice}
RULES (all must hold):
- Every sentence must cite the fact IDs it is based on. A sentence may only say what those facts say. Never add a condition, symptom, medicine, dose, number, frequency, duration, aid, person, place or incident that is not in the cited facts.
- When a fact lists options joined by 'or' (e.g. 'help, prompting or watching', 'pain, breathlessness or exhaustion'), it means one or more of them applies: write it so it stays true (e.g. 'I need help or prompting'), never pick one, never claim all.
- 'Typed detail' facts are the customer's own description of a task. They are the best evidence: build the box around them, keep their specifics (who helps, what happens, when, examples, how long), and use the tap facts only to add what the typed detail doesn't say. Don't repeat a tap fact the typed detail already says better. If a typed detail and a tap disagree, follow the typed detail.
- Keep the customer's own words where they gave them, just clearer. Never make anything sound worse, more often or more certain than the facts ('struggles' stays 'struggles'; no 'always', 'never', 'constantly', 'completely', 'every day' unless a fact says so).
- NEVER ADD ANYTHING. Write only what the facts say. If the facts for a box are thin, write less: one plain true sentence beats a padded paragraph. If a box has no facts, return no sentences for it. Never pad a box to make it look complete.
- Never generalise from a ticked label into new facts. A tick like 'Getting in or out of the bath' supports only 'I have difficulty getting in or out of the bath': not how often, how long, who helps, why, what happened once, what aid is used, or what could go wrong. Add each of those only when its own fact says it.
- For each box, in this order, using ONLY the parts the facts actually give (skip any part with no fact): what I can't do or find hard; how often; how long it takes; what could go wrong without help; good days and bad days; aids used and who helps; a real example.
- Sound like a real person talking about their own day, not a form, but never by adding detail. Lead with the specifics in the facts: WHO helps, WHAT they do, WHEN ('My husband helps me get out of bed and onto my feet'). Use the level wording ('need help or someone with me', 'struggle') at most once per box, and only when no specific fact says it better.
- Never write 'I am like this N days a week', 'X is hard', 'what's hard' or other label-shaped phrases. Say it plainly: 'This happens on 5 days a week', '7 days a week' -> 'every day', 'I find buttons and zips difficult'.
- Write a consequence ('Without help, I could fall') ONLY when a fact says that consequence; otherwise leave it out.
- The facts come from tap answers, so they read like form labels. Write the way the person would say it, naturally, without copying labels word for word and without meta phrases ('In my own words', 'The aid I use is', 'is a professional who knows me', 'the hard part is', 'what's hard').
- Level facts: write 'struggles' as "I struggle with ..." (add slow/painful/tiring only if another fact says which), 'needs help or someone there' as "I need help or someone with me" (or the specific kind of help if another fact says), and 'can't do it safely on their own' as "I can't do this safely on my own".
- Own-words facts can be used in every box they are about (e.g. who helps with cooking goes in the cooking box). Quote them lightly: fix grammar and make them first person, keep the meaning.
- Where a general fact ('needs help, prompting or watching') sits with a more specific one ('needs reminding'), say the specific one; use the general one only if there is nothing more specific, and then keep it vague ('I need help or someone with me').
- State ticked answers plainly, without hedges like 'may', 'might' or 'sometimes' that the facts don't use (a tick 'Runs off or no road sense' becomes 'He runs off or has no road sense', not 'He may run off'). Say each thing once per box: don't repeat a frequency or detail in other words.
- Don't join two facts with 'because', 'so', 'due to', 'which makes', 'which means' or any other cause or link unless a fact gives that reason: state each fact as its own sentence. For 'needs help or someone there' always keep both halves ('help or someone with him'), never just 'someone there' or just 'help'.
- 'Checked with you' facts are the customer's own answers about what could happen without help: always include each one in its box, as the last sentence ('Without help, I could fall.').
- Put each fact in the box it belongs to. Only use '*' facts where they really matter for that box. Don't list doctors or other professionals in the boxes.
- 'Checked with you:' facts are the customer's later answers and win over earlier ones.
- Plain English, short sentences, UK spelling. No medical or legal advice, no points, descriptors, rates or likely outcomes. Never write a statement for anyone else (e.g. a carer or teacher).
- Bad days: say how many a week only as stated. Never present a bad day as every day.
Return JSON matching the schema: boxes = [{{topic, sentences:[{{text, facts:[ids]}}]}}] for these topics only: {topics}."""
SCHEMA={"type":"object","properties":{"boxes":{"type":"array","items":{"type":"object","properties":{"topic":{"type":"string"},
  "sentences":{"type":"array","items":{"type":"object","properties":{"text":{"type":"string"},"facts":{"type":"array","items":{"type":"string"}}},"required":["text","facts"]}}},"required":["topic","sentences"]}}},"required":["boxes"]}
XSYS="""From the customer's FACTS for a UK benefit form ({short}), write short helpful extras for the customer. Use only the facts: never add a condition, symptom, cause, frequency, person, event or feeling they didn't give. Where a fact lists options with 'at least one, not said which', keep the whole 'or' list; never pick one.
Speak to the customer about 'your answers', never 'the facts'.
- checklist: up to 6 kinds of evidence they could include that relate to the facts (e.g. 'A copy of your repeat prescription list'). Never invent a document they have.
- gp_letter: a short polite letter FROM the customer to their GP asking for a letter that confirms their condition and how it affects them. Restate only what the facts say, in the facts' own terms: no causes or links between facts ('which makes', 'because', 'due to'), nothing more specific than the facts. Sign off 'Yours sincerely,' then a blank line for their name.
- notes_for_user: up to 3 short tips about completing or sending the form (no outcomes, no advice on eligibility).
{extra}Never mention AI, models, software, Claude, Anthropic or that anyone has checked the form. Return JSON."""
XSCHEMA={"type":"object","properties":{"checklist":{"type":"array","items":{"type":"string"}},"gp_letter":{"type":"string"},"notes_for_user":{"type":"array","items":{"type":"string"}},
  "call_prep":{"type":"array","items":{"type":"string"}},"changes":{"type":"string"}},"required":["checklist","gp_letter","notes_for_user"]}
VSYS="""You check sentences written for a UK benefit form. For each sentence you get the facts it cites (the customer's own answers).
A sentence is SUPPORTED only if everything in it is stated or plainly implied by its cited facts: no added condition, symptom, medicine, number,
frequency, duration, aid, person, place, incident or outcome, and nothing more severe, frequent or certain than the facts.
Turning an 'or' list into a softer true statement is fine ('I need help or someone with me'), but picking some items from a list marked 'at least one, not said which' is NOT supported (e.g. 'help or prompting' when the fact says 'help, prompting or watching: at least one'). Rewording into first person is fine.
These plain-English renderings of a level fact are ALWAYS supported by it - never mark them unsupported for that reason:
'needs help or someone with me/him/her/them' (for 'needs help or someone there (help, prompting or watching ...)'),
'struggles with' / 'finds it hard' / 'it is slow, painful or tiring' (for 'struggles (slow, painful or tiring ...)'),
'can't do it safely on my/his/her/their own' (for 'can't do it safely on their own'). A 'No' answer to 'Can X do Y' supports 'X can't do Y'.
A sentence that turns a ticked label into something more specific (a frequency, duration, person, event, cause, reason, aid or consequence that its facts don't state) is NOT supported. Generic padding that no fact states ('This affects my daily life', 'I rely on others', 'It makes me feel anxious') is NOT supported. A cause or link between facts ('which makes', 'because', 'so', 'due to') is NOT supported unless a cited fact gives it. If in doubt, mark it NOT supported.
For each sentence write 'problem' FIRST (one short line: what is not supported, or 'none'), THEN 'supported'. Pronoun changes (she -> I) are never a problem. When a carer filled the form in for someone, the carer's 'I' in their own words may be written as 'my family carer', 'my daughter' etc. if a fact names that helper - that is supported.
Return JSON only."""
VSCHEMA={"type":"object","properties":{"verdicts":{"type":"array","items":{"type":"object","properties":{"n":{"type":"integer"},"problem":{"type":"string"},"supported":{"type":"boolean"}},"required":["n","problem","supported"],"propertyOrdering":["n","problem","supported"]}}},"required":["verdicts"]}
APPROVED=re.compile(r"help or someone with (me|him|her|them)|struggles? with|finds? it hard|slow, painful or tiring|safely on (my|his|her|their) own",re.I)
STRONG=("always","never","constantly","completely","every day","every night","at all","impossible","cannot","can't","unable")
BANNED_COPY=re.compile(r"\b(AI|A\.I\.|artificial intelligence|Gemini|Claude|Anthropic|OpenAI|ChatGPT|Google|language model|chatbot|algorithm|our team|reviewed by|checked by)\b",re.I)
NUMW={"once":"1","one":"1","twice":"2","two":"2","three":"3","four":"4","five":"5","six":"6","seven":"7","eight":"8","nine":"9","ten":"10","half":"2"}
def _nums(s): return set(re.findall(r"\d+",s))|{NUMW[w] for w in re.findall(r"\b("+"|".join(NUMW)+r")\b",s.lower())}
CAUSE=re.compile(r"\b(because|due to|caused by|as a result|which (makes|means|causes|leads)|that (makes|means|causes)|this (makes|means|causes)|leads? to|so that|so I|so he|so she|so they|so it|therefore)\b",re.I)
_STOP=set("this that with when what which they them their there have from into about each time times more most very much also just only some other others usually often been being does doing makes means causes leads myself himself herself themselves yourself once twice three four five seven eight nine every".split())
def cut_cause(text,cited):
    """(text, removed clause): a cause or link ('..., which makes dressing difficult') the cited facts don't give is cut;
    if the sentence can't stand without it, text is ''."""
    m=CAUSE.search(text)
    if not m or CAUSE.search(" ".join(cited)): return text,""
    import grounding as G
    src=G._stems(" ".join(cited)); clause=text[m.end():]
    new=[w for w in re.findall(r"[a-z]+",clause.lower()) if len(w)>=4 and w not in _STOP and " "+G.stem(w)+" " not in src]
    if not new: return text,""   # the link only joins things the cited facts say ('because he wanders' when a fact is 'help at night with: wandering'); the checker judges the link
    head=text[:m.start()].rstrip(" ,;-")
    if len(head.split())>=3 and m.start()>0 and text[m.start()-2:m.start()].strip() in (",",""):   # '..., which makes X' / '... because X'
        return head+".",text[len(text[:m.start()]):].strip()
    return "",text
def rule_check(text,cited):
    """Problems a model isn't needed for: numbers or strong words the cited facts don't have."""
    src=" ".join(cited).lower(); t=text.lower(); p=[]
    extra=_nums(text)-_nums(src)
    if extra: p.append("number not in your answers: "+", ".join(sorted(extra)))
    for u in ("day","week","night","month","year"):   # 'twice a week' when the answer was per year
        if re.search(rf"\b(a|per|each|every) {u}\b|\b{u}ly\b",t) and not re.search(rf"\b{u}s?\b|\b{u}ly\b|\b{u[:2] if u=='day' else u}",src) and _nums(text):
            p.append(f"'{u}' period not in your answers")
    for w in STRONG:
        if w in ("every day","every night") and re.search(r"\b7\b|seven|each day|daily",src): continue
        if re.search(r"\b"+re.escape(w)+r"\b",t) and w not in src and not (w in ("cannot","can't","unable") and ("can't" in src or "cannot" in src or "not" in src or "unable" in src or "unsafe" in src or re.search(r"\bcan\b[^:.]*:\s*no\b",src))): p.append(f"'{w}' is stronger than your answers")
    return p
META=re.compile(r"^(what's hard is that|what is hard is that|the hard part is that|the hard part is|in my own words,?|in (his|her|their) own words,?)\s+",re.I)
def tidy(form,d,txt):
    """Cheap fixes a small model sometimes needs: meta openers ('What's hard is that ...') and, on DLA (parent's voice),
    'I struggle with / I need help or someone' that should be about the child."""
    txt=LABEL_NOTE.sub("",txt)
    if re.search(r"\bnot (discussed|mentioned|stated|said|known)\b|\bno information\b|\bwasn't asked\b",txt,re.I): return ""   # never 'Not discussed'
    m=META.match(txt)
    if m and len(txt)>m.end(): txt=txt[m.end()].upper()+txt[m.end()+1:]
    if form=="dla":
        try: import intake as I; nm=I.name(d,form)
        except Exception: nm="My child"
        nm=nm if nm and not nm.lower().startswith(("your","the person")) else "My child"
        txt=re.sub(r"^I need help or someone (with me|there)\b",nm+" needs help or someone with them",txt)   # never the parent on DLA care needs
        txt=re.sub(r"^I can't do (this|it) safely on my own\b",lambda m:f"{nm} can't do {m.group(1)} safely on their own",txt)
        if not re.search(r"\b(him|her|them|my (son|daughter|child))\b",txt,re.I):   # 'I struggle to get him dressed' is the parent
            txt=re.sub(r"^I struggle with\b",nm+" struggles with",txt)
            txt=re.sub(r"^I find (it|\w+ing) hard\b",lambda m:f"{nm} finds {m.group(1)} hard",txt)
    return txt
def write(form,d,history=None):
    """Draft dict in the usual shape (answers, sources, tick_yes, extra, checklist, gp_letter, notes_for_user...) plus
    'facts', 'verifier' (what was removed and why) and 'drafted_from'. Raises cl.Unavailable if Claude can't be reached."""
    F=facts(form,d,history); fx={f["id"]:f for f in F}
    tops=[t for t,_,_ in FORMS[form]["topics"] if t not in NOT_DRAFTED.get(form,())]
    has={t for f in F for t in ([f["topic"]] if f["topic"]!="*" else tops)}
    tops=[t for t in tops if t in has]
    user=json.dumps({"boxes":[{"topic":t,"label":l} for t,l,_ in FORMS[form]["topics"] if t in tops],"facts":F},ensure_ascii=False)
    short=FORMS[form]["short"]
    import concurrent.futures as cf
    with cf.ThreadPoolExecutor(2) as ex:
        j1=ex.submit(cl.call,cl.WRITER,SYS.format(short=short,voice=VOICE.get(form,VOICE["pip"]),topics=", ".join(tops)),user,SCHEMA,"draft")
        xe=("- call_prep: up to 5 short points to prepare for a phone assessment, from the facts.\n" if form in ("pip","pipr") else "")+("- changes: one short plain summary of what the facts say has changed.\n" if form=="pipr" else "")
        j2=ex.submit(cl.call,cl.VERIFY,XSYS.format(short=short,extra=xe),json.dumps({"facts":F},ensure_ascii=False),XSCHEMA,"extras")
        out=j1.result()
        try: xo=j2.result()
        except Exception as e: print("extras failed:",str(e)[:150],flush=True); xo={}
    sents=[]; removed=[]
    xo=ground_extras(xo,F,removed)
    for b in out.get("boxes") or []:
        t=str(b.get("topic"))
        if t not in tops: continue
        for s in b.get("sentences") or []:
            txt=tidy(form,d," ".join(str(s.get("text","")).split())); ids=[i for i in (s.get("facts") or []) if i in fx and fx[i]["topic"] in (t,"*")]
            if not txt: continue
            if not ids: removed.append({"topic":t,"text":txt,"why":"no matching answer"}); continue
            txt,cut=cut_cause(txt,[fx[i]["text"] for i in ids])
            if cut: removed.append({"topic":t,"text":cut,"why":"a cause or link not in your answers"})
            if not txt: continue
            pr=rule_check(txt,[fx[i]["text"] for i in ids])
            if pr: removed.append({"topic":t,"text":txt,"why":"; ".join(pr)}); continue
            sents.append({"topic":t,"text":txt,"facts":ids})
    # second pass: Claude checks each sentence against the facts it cites
    if sents:
        vin=[{"n":i,"sentence":s["text"],"facts":[fx[f]["text"] for f in s["facts"]]} for i,s in enumerate(sents)]
        try:
            v=cl.call(cl.VERIFY,VSYS,json.dumps(vin,ensure_ascii=False),VSCHEMA,"verify")
            bad={int(x["n"]):x.get("problem","") for x in v.get("verdicts") or [] if x.get("supported") is False and str(x.get("problem","")).strip().lower().rstrip(".")!="none"}
            for i in list(bad):
                if not 0<=i<len(sents): bad.pop(i); continue
                why=(bad[i] or "").lower()
                if APPROVED.search(sents[i]["text"]) and re.search(r"at least one|not said which|picks? a specific|prompting or watching",why) and not re.search(r"also|addition|not mention|omit|extra",why): bad.pop(i)
            seen={int(x["n"]) for x in v.get("verdicts") or [] if str(x.get("n","")).lstrip("-").isdigit()}
            for i in range(len(sents)):
                if i not in seen: bad[i]="no verdict from the checker"   # unchecked = not kept
            for i in sorted(bad,reverse=True): removed.append({"topic":sents[i]["topic"],"text":sents[i]["text"],"why":"verifier: "+(bad[i] or "not supported")}); sents.pop(i)
            vstat="checked"
        except cl.Unavailable as e:
            print("verifier unavailable:",str(e)[:150],flush=True); vstat="unavailable (grounding check still runs)"
    else: vstat="nothing to check"
    # third pass: the grounding check (deterministic word lists + the separate grounding model) against the customer's answers;
    # any sentence it flags is removed before the customer sees the draft
    gstat=ground_sentences(sents,F,removed)
    if removed: print(f"writer {form}: removed {len(removed)} sentence(s): "+"; ".join(f"{r['topic']}: {r['why'][:80]}" for r in removed),flush=True)
    base=I.fallback_draft(form,d) if d and form!="pipr" else {"answers":{},"sources":{},"tick_yes":[],"conditions":[],"extra":{},"checklist":[],"notes_for_user":[],"gp_letter":""}
    ans={t:" ".join(s["text"] for s in sents if s["topic"]==t) for t in tops}
    base["answers"]={t:ans.get(t,"") for t,_,_ in FORMS[form]["topics"]}
    for t in NOT_DRAFTED.get(form,()): base["answers"][t]=""
    base["sources"]={t:list(dict.fromkeys(fx[i]["text"] for s in sents if s["topic"]==t for i in s["facts"])) for t in tops if ans.get(t)}
    clean=lambda L:[x for x in (L or []) if isinstance(x,str) and x.strip() and not BANNED_COPY.search(x)][:6]
    base["checklist"]=clean(xo.get("checklist")) or base.get("checklist",[]); base["notes_for_user"]=clean(xo.get("notes_for_user"))[:3]
    gl=xo.get("gp_letter") or ""; base["gp_letter"]="" if BANNED_COPY.search(gl) else gl
    if form in ("pip","pipr"): base["call_prep"]=clean(xo.get("call_prep"))[:5]
    if form=="pipr": base["changes"]="" if BANNED_COPY.search(xo.get("changes") or "") else (xo.get("changes") or "")
    base["facts"]={f["id"]:f["text"] for f in F}; base["cites"]=[{"topic":s["topic"],"text":s["text"],"facts":s["facts"]} for s in sents]
    base["verifier"]={"status":vstat,"grounding":gstat,"removed":removed}; base["drafted_from"]="claude"
    return llm._strip(base)
XKINDS=("condition or symptom","medicine","number or frequency","frequency","stronger than your words","dose","outcome claim (never state eligibility or amounts)")
LABEL_NOTE=re.compile(r"\s*\((?:[^()]*\bat least one\b[^()]*|[^()]*\bnot said which\b[^()]*)\)",re.I)   # our fact labels, never customer copy
def ground_extras(xo,F,removed):
    """Word-list grounding of the extras (checklist, notes, call prep, GP letter): drop any item or letter sentence that names a
    condition, medicine, number, frequency or stronger wording the customer didn't give. Each removal is logged."""
    import grounding as G
    src="\n".join(f["text"] for f in F)
    bad=lambda t:[f for f in G.check_answer(t,src) if f["kind"] in XKINDS or (f["kind"]=="person" and f["phrase"] not in ("doctor","gp"))]
    out=dict(xo or {})
    for k in ("checklist","notes_for_user","call_prep"):
        keep=[]
        for it in out.get(k) or []:
            fl=bad(str(it)) if k!="checklist" else [f for f in bad(str(it)) if f["kind"]!="person"]   # a checklist may suggest a letter from a carer or teacher
            if fl: removed.append({"topic":"extras:"+k,"text":str(it),"why":"grounding: "+", ".join(f"{f['kind']}: {f['phrase']}" for f in fl)})
            else: keep.append(it)
        if k in out: out[k]=keep
    gl=LABEL_NOTE.sub("",str(out.get("gp_letter") or ""))
    for k in ("checklist","notes_for_user","call_prep"):
        if k in out: out[k]=[LABEL_NOTE.sub("",str(x)) for x in out[k]]
    if gl:
        lines=[]
        for ln in gl.split("\n"):
            ss=G.sentences(ln) if ln.strip() else []
            kept=[]
            for snt in ss:
                fl=bad(snt)
                if fl: removed.append({"topic":"extras:gp_letter","text":snt,"why":"grounding: "+", ".join(f"{f['kind']}: {f['phrase']}" for f in fl)})
                else: kept.append(snt)
            lines.append(" ".join(kept) if ss else ln)
        out["gp_letter"]="\n".join(lines)
    return out
def ground_sentences(sents,F,removed):
    """Remove (in place) every sentence the grounding check can't trace to the customer's answers; log each in removed."""
    import grounding as G
    if os.getenv("WRITER_GROUND","1")=="0" or not sents: return "skipped"
    src="\n".join(f["text"] for f in F); tops=list(dict.fromkeys(s["topic"] for s in sents))
    try: flags=G.check({t:" ".join(s["text"] for s in sents if s["topic"]==t) for t in tops},src)
    except G.GroundingUnavailable as e:   # the word-list layer still runs; the model layer runs again before approval
        print("grounding model unavailable in writer:",str(e)[:150],flush=True)
        flags=G.check({t:" ".join(s["text"] for s in sents if s["topic"]==t) for t in tops},src,use_llm=False); st="word lists only (model checked again before approval)"
    else: st="checked"
    norm=lambda x:" ".join(str(x).lower().split())
    for t,fl in flags.items():
        for x in fl:
            ph=norm(x.get("phrase",""))
            if not ph: continue
            for s in [s for s in sents if s["topic"]==t and ph in norm(s["text"])]:
                removed.append({"topic":t,"text":s["text"],"why":f"grounding: {x.get('kind','not in your answers')}: {x.get('phrase')}"}); sents.remove(s)
    return st
def on(): return os.getenv("WRITER","claude")=="claude" and not llm.MOCK and not cl.mock()
def on_mock(): return os.getenv("WRITER","claude")=="claude" and os.getenv("WRITER_MOCK_FACTS","0")=="1"
def mock_write(form,d,history=None):
    """Tests without a key: the same facts and checks, sentences taken straight from the facts (no model)."""
    F=facts(form,d,history); dd=I.fallback_draft(form,d) if d and form!="pipr" else {"answers":{},"sources":{}}
    dd["facts"]={f["id"]:f["text"] for f in F}; dd["verifier"]={"status":"mock","removed":[]}; return dd

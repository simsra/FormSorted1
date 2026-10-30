"""LLM wrapper. OpenAI-compatible chat API (works with OpenAI, Groq, Together, etc.).
Without any API key it runs in MOCK mode (scripted questions + sample answers) for local demos. Multi-form: aa, dla, pip, pipr."""
import os, json, urllib.request, urllib.error
from forms import FORMS
import samples
# Providers (OpenAI-compatible chat API). Drafting: OpenAI primary, Gemini fallback. Grounding: Gemini primary, OpenAI fallback (never skipped).
# Env: LLM_PROVIDER (openai|gemini|custom), LLM_MODEL, LLM_FALLBACKS ("provider:model,..."), GROUNDING_PROVIDER, GROUNDING_MODEL, GROUNDING_FALLBACKS,
#      OPENAI_API_KEY, GEMINI_API_KEY; legacy LLM_API_KEY + LLM_BASE_URL => provider "custom".
PROVIDERS={"openai":(os.getenv("OPENAI_BASE_URL","https://api.openai.com/v1"),os.getenv("OPENAI_API_KEY","")),
 "gemini":(os.getenv("GEMINI_BASE_URL","https://generativelanguage.googleapis.com/v1beta/openai"),os.getenv("GEMINI_API_KEY","")),
 "anthropic":(os.getenv("ANTHROPIC_BASE_URL","https://api.anthropic.com/v1"),os.getenv("ANTHROPIC_API_KEY","")),
 "custom":(os.getenv("LLM_BASE_URL",""),os.getenv("LLM_API_KEY",""))}
def _chain(s): return [tuple(x.strip().split(":",1)) for x in s.split(",") if ":" in x]
_dp=os.getenv("LLM_PROVIDER") or ("custom" if os.getenv("LLM_BASE_URL") and os.getenv("LLM_API_KEY") else "openai" if os.getenv("OPENAI_API_KEY") else "gemini")   # 30 Oct: Anthropic no longer a default (set LLM_PROVIDER=anthropic to use it)
MODEL=os.getenv("LLM_MODEL") or {"anthropic":"claude-opus-5-5","openai":"gpt-5.5","gemini":"gemini-3.8-flash"}.get(_dp,"")
DRAFT_CHAIN=[(_dp,MODEL)]+_chain(os.getenv("LLM_FALLBACKS","openai:gpt-5.4,gemini:gemini-3.8-flash"))
GROUND_CHAIN=[(os.getenv("GROUNDING_PROVIDER","openai"),os.getenv("GROUNDING_MODEL","gpt-5.4-mini"))]+_chain(os.getenv("GROUNDING_FALLBACKS","openai:gpt-5.5,gemini:gemini-3.8-flash"))
# grounding: prefer a different model family than the drafter; same family only as last resort
if not os.getenv("GROUNDING_PROVIDER"): GROUND_CHAIN=[x for x in GROUND_CHAIN if x[0]!=_dp]+[x for x in GROUND_CHAIN if x[0]==_dp]
# An explicitly chosen checker always goes first (28 Oct: reordering put out-of-credit/overloaded providers first, adding seconds to every approve)
def _avail(ch): 
    seen=[]; [seen.append(x) for x in ch if PROVIDERS.get(x[0],("",""))[1] and PROVIDERS[x[0]][0] and x not in seen]; return seen
DRAFT_CHAIN=_avail(DRAFT_CHAIN); GROUND_CHAIN=_avail(GROUND_CHAIN)
KEY="LLM_API_KEY_PLACEHOLDER" if not DRAFT_CHAIN else "set"
MOCK = KEY.endswith("PLACEHOLDER")
EXTRA={"aa":"", "dla":"""Always compare with a child of the same age without a disability. Cover care, supervision by day and night (night starts 11pm, when everyone is in bed),
mobility only if the child is 3 or over, and school/nursery support. For night help ask nights per week, times per night and minutes each time.""",
 "pip":"""Cover all 12 PIP activities. For each, ask what happens on the majority of days (more than half), whether they can do it safely, to an acceptable standard,
repeatedly and in a reasonable time, which aids they use and what help or prompting they need. Ask for a real recent example.""",
 "pipr":"""This is a PIP review (AR1). For each of the 12 activities also ask what has changed since the last award (better, worse or the same)."""}
EXTRA["pipr"]=EXTRA["pip"]+" "+EXTRA["pipr"]
EXTRA["atw"]="""This is an Access to Work application (help with practical support at work). Focus on the job: daily tasks, where work gets hard and why,
travel to work, communication and focus, what has been tried, and what support would help (equipment, software, support worker hours, travel, workplace changes).
Ask how often and how long. Never discuss complaints against an employer, legal claims or discrimination; if raised, say in one sentence that we can't advise on disputes, then continue with the next question."""
WHO_RULE={k:"""FIRST question: is the form for you, or for someone you help (and their first name)? Then follow that answer all the way through:
for the user themself say "you/your"; for someone else use their name or "they/their", never "you" about the claimant. Never ask
other-person questions (their name, who will sign) to someone filling it in for themselves.
""" for k in ("pip","pipr","aa")}
def interview_system(form):
    f=FORMS[form]
    return f"""You are a calm, kind interviewer helping a family prepare the {f['short']} (England & Wales).
Ask ONE short plain-English question at a time about {f['subject']}. Cover, in order:
""" + "\n".join(f"- {t}: {p}" for _,t,p in f["topics"]) + f"""
{EXTRA[form]}
{WHO_RULE.get(form,"")}Ask for frequency, time taken, who helps, safety risks and bad days. Never suggest symptoms or exaggerate; record only what the user says.
Never ask the same question twice: if an earlier answer already covers it (even in passing), use that and move on. Prefer questions with short
answers (e.g. "Most days, some days or rarely?"). Ask at most 2 follow-ups on any one task, and accept "not sure" or "skip".
Never mention points or promise an outcome. If something is unclear, ask. When all topics are covered reply exactly: [[DONE]]
STRICT: you ONLY ask questions. Never give advice, opinions on eligibility, example or suggested answers, wording, summaries, or drafts of any part of the form,
even if asked. If asked for any of these, reply in one sentence that we prepare everything for them at the end, then ask your next question. Keep each reply under 60 words."""
def draft_system(form):
    f=FORMS[form]; ids=", ".join(i for i,_,_ in f["topics"])
    s=f"""From the interview transcript, write truthful first-person answers for the {f['short']}.
STRICT RULES: Use ONLY facts the USER stated in the transcript. Never add, infer or round any fact: no new conditions, symptoms, medicines, doses,
numbers, frequencies, durations, aids, people or places. If the user didn't say how often or how long, don't write one. If a topic wasn't discussed, return "".
Include how often, how long, who helps and what happens without help ONLY where the user said so. Plain English, no exaggeration.
The transcript may be short tapped answers (e.g. "Dressing: finds this hard, needs help or reminding, like this most days, each time takes 10 to 30 minutes"). Turn them into natural sentences without adding facts.
Quoted words after "In my own words:" are what the customer typed themselves: build each answer on those details first, written more clearly in the first person, keeping every fact exactly as they gave it (never add, change or strengthen a detail), then add the tapped details.
Describe what happens on a typical day, then bad days and how many a week, exactly as stated. If the user said there are bad days on more than half the days (4 or more a week), describe bad days as the usual situation; otherwise mention bad days and how many a week, as stated. Never describe a worst day or a bad day as every day, and never present a worst case as typical.
Never make anything sound more severe, more frequent or more absolute than the user's words: no "always", "never", "constantly", "completely", "at all", "impossible" or "every day" unless the user said so; "struggles" stays "struggles", not "cannot".
Lines that start "Checked with you:" are the user's own corrections: they override anything earlier that disagrees. Only use facts from documents where the user confirmed them ("I checked these against my documents").
Never write a statement, letter or words for anyone else to sign or put in the form (the statement from someone who knows the claimant is theirs to write); gp_letter is only the customer's own request to their GP. For a topic about that statement, only say who could write it, never what they would say. Never state or imply eligibility, award rates, amounts, points, descriptors or likely outcomes. Return JSON: {{"answers":{{one key per topic id: {ids}}},"extra":{{}},"conditions":[{{"name","since","meds","dose"}}],
"checklist":[...evidence...],"gp_letter":"...","notes_for_user":[...],
"sources":{{topic id: [short verbatim quotes from the USER's messages each answer is based on]}}"""
    if form=="aa": s+=""","tick_yes":[AA1 question numbers (topic ids) where the user described help or difficulty]"""
    if form=="dla": s+=""","extra" may include night_bed/night_toilet/night_treatment/night_settle/night_danger/night_wander/night_behaviour as [nights per week, minutes, times a night] and care_start"""
    if form in("pip","pipr"): s+=""","call_prep":[...phone/assessment prep points...]"""
    if form=="atw": s+=""","support_summary":[{"item","type","cost"} only items the user asked for; cost "[quote]" unless the user gave one],"call_prep":[...]"""
    if form=="pipr": s+=""","changes":"summary of what changed since the last award\""""
    return s+"}"
class LLMUnavailable(RuntimeError): pass
_DOWN={}  # provider:model -> time it last failed hard (skip for DOWN_SECS so one outage doesn't add minutes per call)
DOWN_SECS=int(os.getenv("LLM_DOWN_SECS","120")); QUOTA_DOWN_SECS=int(os.getenv("LLM_QUOTA_DOWN_SECS","3600"))
def _anthropic_body(model, messages, json_mode):
    sys_="\n\n".join(m["content"] for m in messages if m["role"]=="system")
    if json_mode: sys_+="\n\nReply with ONE valid JSON object only. No prose, no code fences."
    msgs=[{"role":m["role"],"content":_anth_parts(m["content"])} for m in messages if m["role"]!="system"]
    if not msgs or msgs[0]["role"]!="user": msgs=[{"role":"user","content":"Hello, I'm ready to start."}]+msgs
    merged=[]  # Messages API requires alternating roles
    for m in msgs:
        if merged and merged[-1]["role"]==m["role"] and isinstance(m["content"],str) and isinstance(merged[-1]["content"],str): merged[-1]["content"]+="\n\n"+m["content"]
        else: merged.append(dict(m))
    return {"model":model,"max_tokens":int(os.getenv("LLM_MAX_TOKENS","8000")),
            "system":[{"type":"text","text":sys_,"cache_control":{"type":"ephemeral"}}],"messages":merged}
def _anth_parts(c):
    """OpenAI-style content parts (text / image_url data URLs) -> Anthropic content blocks. Strings pass through."""
    if isinstance(c,str): return c
    out=[]
    for p in c:
        if p.get("type")=="text": out.append({"type":"text","text":p["text"]})
        elif p.get("type")=="image_url":
            u=p["image_url"]["url"]; mt,data=u[5:].split(";base64,",1)
            out.append({"type":"image","source":{"type":"base64","media_type":mt,"data":data}})
    return out
def _first_json(t):
    """Return the first complete JSON object in t (models sometimes add trailing text or a second object)."""
    i=t.find("{")
    if i<0: return t
    try: obj,_=json.JSONDecoder().raw_decode(t[i:]); return json.dumps(obj)
    except ValueError: return t
def _strip_fence(t):
    t=t.strip()
    if t.startswith("```"): t=t.split("\n",1)[1] if "\n" in t else t[3:]; t=t.rsplit("```",1)[0]
    return t.strip()
TIMEOUT=int(os.getenv("LLM_TIMEOUT","90")); RETRIES=int(os.getenv("LLM_RETRIES","1"))   # fail fast so a dead provider hands over quickly
def _call_one(provider, model, messages, json_mode=False, retries=None, effort=None):
    retries=RETRIES if retries is None else retries
    import time
    base,key=PROVIDERS[provider]
    if provider=="anthropic":
        body=_anthropic_body(model,messages,json_mode)
        req=urllib.request.Request(base+"/messages",json.dumps(body).encode(),{"x-api-key":key,"anthropic-version":"2023-06-01","content-type":"application/json"})
    else:
        body={"model":model,"messages":messages}
        if not model.startswith(("gpt-5","o")): body["temperature"]=0.3  # gpt-5 family only accepts the default temperature
        if json_mode: body["response_format"]={"type":"json_object"}
        if effort and model.startswith(("gpt-5","o")): body["reasoning_effort"]=effort
        req=urllib.request.Request(base+"/chat/completions",json.dumps(body).encode(),{"Authorization":"Bearer "+key,"Content-Type":"application/json"})
    t0=time.time()
    for attempt in range(retries+1):  # retry transient overload / rate limits / timeouts
        try: r=json.load(urllib.request.urlopen(req,timeout=TIMEOUT)); break
        except urllib.error.HTTPError as e:
            msg=e.read()[:600]; low=msg.lower()
            if (e.code==429 and (b"per day" in low or b"insufficient_quota" in low or b"credit" in low)) or (e.code==400 and b"credit balance" in low): raise LLMUnavailable(f"{provider}:{model} quota/credits exhausted: {msg[:200]!r}") from None
            if e.code in (429,500,502,503,504,529) and attempt<retries: time.sleep(min(2*2**attempt,4)); continue
            raise LLMUnavailable(f"{provider}:{model} HTTP {e.code}: {msg[:200]!r}") from None
        except (urllib.error.URLError, TimeoutError) as e:
            if attempt<retries: time.sleep(min(2*2**attempt,4)); continue
            raise LLMUnavailable(f"{provider}:{model} network: {e}") from None
    u=r.get("usage") or {}; k=f"{provider}:{model}"
    m=USAGE["by_model"].setdefault(k,{"calls":0,"in":0,"cached_in":0,"cache_write":0,"out":0})
    if provider=="anthropic":  # "in" = total prompt tokens incl. cache reads/writes
        cr=u.get("cache_read_input_tokens",0) or 0; cw=u.get("cache_creation_input_tokens",0) or 0
        tin=(u.get("input_tokens",0) or 0)+cr+cw; tout=u.get("output_tokens",0) or 0
        text="".join(b.get("text","") for b in r.get("content",[]) if b.get("type")=="text")
        if r.get("stop_reason")=="max_tokens": print("LLM warning: max_tokens reached",k)
    else:
        cr=(u.get("prompt_tokens_details") or {}).get("cached_tokens",0) or 0; cw=0
        tin=u.get("prompt_tokens",0); tout=u.get("completion_tokens",0); text=r["choices"][0]["message"]["content"]
    for d in (USAGE,m): d["calls"]+=1; d["in"]+=tin; d["out"]+=tout
    m["cached_in"]+=cr; m["cache_write"]+=cw
    print(f"LLM ok {k} {time.time()-t0:.1f}s in={tin} out={tout}",flush=True)
    return _first_json(_strip_fence(text)) if json_mode else text
def _call(messages, json_mode=False, chain=None, effort=None):
    """Try each provider:model in chain (default DRAFT_CHAIN); raise LLMUnavailable if all fail."""
    errs=[]
    import time
    for p,mdl in (chain or DRAFT_CHAIN):
        if time.time()-_DOWN.get((p,mdl),0)<DOWN_SECS: errs.append(f"{p}:{mdl} skipped (recently down)"); continue
        try:
            out=_call_one(p,mdl,messages,json_mode,effort=effort)
            if json_mode: json.loads(out)
            USED.append(("ground" if chain is GROUND_CHAIN else "draft",f"{p}:{mdl}")); return out
        except LLMUnavailable as e:
            # quota/credit errors won't fix themselves in 2 minutes: skip that provider for QUOTA_DOWN_SECS instead
            _DOWN[(p,mdl)]=time.time()+(QUOTA_DOWN_SECS-DOWN_SECS if "exhausted" in str(e) else 0); errs.append(str(e)[:200]); print("LLM fallback:",str(e)[:200])
        except (ValueError, KeyError) as e: errs.append(str(e)[:200]); print("LLM fallback:",str(e)[:200])
    raise LLMUnavailable("all models failed: "+" | ".join(errs))
USAGE={"calls":0,"in":0,"out":0,"by_model":{}}
USED=[]  # (purpose, provider:model) actually used, for reporting  # running token totals (for cost tracking)
import re
def _lab(t):
    t=re.sub(r"\s*\(.*?\)","",t.split(": ",1)[-1]); return t[0].lower()+t[1:]
def mock_qs(form):
    first={"aa":"To start, who is the claim for, and what are their main health conditions?","dla":"To start, how old is the child and what are their main conditions or disabilities?",
      "pip":"To start, who is the PIP claim for, and what are the main health conditions?","pipr":"To start, when was the PIP award and what has changed since then?","atw":"To start, what job are you in (or about to start), and roughly when did you start?"}[form]
    return [first]+[f"Thank you. Now about {_lab(t)}: {p}" for _,t,p in FORMS[form]["topics"]]
NOTHING=re.compile(r"^\W*(?:no+|nope|nah|none|n/a)?\W*(?:i think\W*|i don'?t think so\W*)?(?:(?:that'?s|that is|thats)\W*(?:it|all|everything)|(?:there'?s\W*)?nothing\W*(?:more|else)?(?:\W*to add)?|no\W*(?:more|other)|not really)?\W*(?:for now|really|i think)?\W*(?:,?\W*thanks?|thank you)?\W*$",re.I)
CLEAR_END=re.compile(r"\b(that'?s|that is|thats)\W*(everything|all)\b|\bnothing (more|else) to add\b",re.I)
def is_nothing(t): t=(t or "").strip(); return bool(t) and bool(NOTHING.match(t))
def max_turns(form): return int(os.getenv("MAX_TURNS") or len(FORMS[form]["topics"])+6)
def should_finish(history, form):
    """True when the interview should end: turn cap, two 'nothing more' replies in a row,
    or one clear 'that's everything' once every topic has had a turn."""
    u=[m["content"] for m in history if m["role"]=="user" and m["content"].strip()]
    if len(u)>=max_turns(form): return True
    if len(u)>=2 and is_nothing(u[-1]) and is_nothing(u[-2]): return True
    asked=sum(1 for m in history if m["role"]=="assistant" and m["content"].strip())
    return bool(u) and is_nothing(u[-1]) and CLEAR_END.search(u[-1]) is not None and asked>=len(FORMS[form]["topics"])
def next_question(history, form="aa"):
    if should_finish(history, form): return "[[DONE]]"
    if MOCK:
        n=sum(1 for m in history if m["role"]=="user"); q=mock_qs(form); return q[n] if n<len(q) else "[[DONE]]"
    msgs=[m for m in history if m["content"].strip()]
    if not any(m["role"]=="user" for m in msgs): msgs=[{"role":"user","content":"Hello, I'm ready to start."}]+msgs  # some providers need a user turn
    sysm=interview_system(form)
    u=[m["content"] for m in history if m["role"]=="user" and m["content"].strip()]
    if u and is_nothing(u[-1]): sysm+="\nThe customer just said they have nothing more on that. Do NOT ask about it again. Ask about the next topic that has not been asked yet; if every topic has been asked once, reply exactly: [[DONE]]"
    return _call([{"role":"system","content":sysm}]+msgs)
def draft(history, form="aa"):
    if MOCK:
        if os.getenv("MOCK_DRAFT_SLOW"): import time; time.sleep(float(os.getenv("MOCK_DRAFT_SLOW")))   # tests only: a slow drafter
        if form=="aa": return _strip(json.load(open(os.path.join(os.path.dirname(__file__),"sample_case.json")))["draft"])
        return _strip(json.loads(json.dumps({"dla":samples.DLA,"atw":samples.ATW}.get(form,samples.PIP))))
    t="\n".join(f'{m["role"].upper()}: {m["content"]}' for m in history)
    if DRAFT_PARTS<=1: return _strip(json.loads(_call([{"role":"system","content":draft_system(form)},{"role":"user","content":t}],json_mode=True,effort=DRAFT_EFFORT)))
    return _strip(draft_parallel(t,form))
DRAFT_EFFORT=os.getenv("LLM_DRAFT_EFFORT","low") or None; GROUND_EFFORT=os.getenv("LLM_GROUND_EFFORT","low") or None
DRAFT_PARTS=int(os.getenv("LLM_DRAFT_PARTS","3"))   # answer groups drafted at the same time (+1 call for letters/checklist). 1 = single call
EXTRA_KEYS={"aa":[],"dla":[],"pip":["call_prep"],"pipr":["call_prep","changes"],"atw":["support_summary","call_prep"]}
NOT_OURS=("carer_statement","supporter_statement")   # never our words for the supporter: dropped from any draft
def _strip(d):
    for k in NOT_OURS: d.pop(k,None)
    return d
def draft_parallel(t, form):
    """Same rules and transcript, split into independent parts drafted at once (28 Oct: one big call took ~32s).
    Parts: N groups of topic answers (+ their sources/tick_yes), and one call for conditions/extra/checklist/letters/notes."""
    import concurrent.futures as cf
    ids=[i for i,_,_ in FORMS[form]["topics"]]; n=max(1,min(DRAFT_PARTS,len(ids))); k=-(-len(ids)//n)
    groups=[ids[i:i+k] for i in range(0,len(ids),k)]; sysm=draft_system(form)
    def part(ins): return json.loads(_call([{"role":"system","content":sysm+"\n\nTHIS REQUEST: "+ins},{"role":"user","content":t}],json_mode=True,effort=DRAFT_EFFORT))
    jobs=[f'Return ONLY the keys "answers" and "sources"{" and tick_yes" if form=="aa" else ""}, and only for these topic ids: {", ".join(g)}. Leave everything else out.' for g in groups]
    rests=[["gp_letter"],["conditions","extra","checklist","notes_for_user"]+EXTRA_KEYS.get(form,[])]
    for r_ in rests: jobs.append('Return ONLY these keys: '+", ".join(r_)+'. Do not return "answers", "sources" or "tick_yes". Use only facts the USER stated.')
    with cf.ThreadPoolExecutor(len(jobs)) as ex: res=list(ex.map(part,jobs))   # any part failing raises: never a half draft
    d={"answers":{},"sources":{}}; rest=[k for r_ in rests for k in r_]; extras={}
    for r_,r in zip(rests,res[len(groups):]):
        for key in r_:
            if key in r: extras[key]=r[key]
    for g,r in zip(groups,res[:len(groups)]):
        for i in g:
            d["answers"][i]=(r.get("answers") or {}).get(i,"") or ""
            if (r.get("sources") or {}).get(i): d["sources"][i]=r["sources"][i]
        if form=="aa": d.setdefault("tick_yes",[]).extend(x for x in (r.get("tick_yes") or []) if str(x) in g or x in g)
    d.update(extras)
    for key in ("checklist","notes_for_user","conditions"): d.setdefault(key,[])
    d.setdefault("extra",{})
    return d

GROUNDING_PROMPT="""You check a drafted benefit-form answer against the customer's own words.
List every claim in the DRAFT that is not directly supported by the SOURCE (customer's words): new conditions, symptoms, medicines, doses,
numbers, frequencies, durations, aids or equipment, people, places, or any statement about eligibility or outcome.
Also list anything stated as more severe, more frequent or more absolute than the SOURCE (e.g. "always" where the source says "most days", "cannot" where it says "struggles", a bad day described as every day).
Return JSON only: {"unsupported":[{"phrase":"exact words from the draft","reason":"short reason"}]}. Return {"unsupported":[]} if all supported."""
def grounding(draft_text, source_text):
    """Mandatory grounding check (raises LLMUnavailable if every checker model fails). Returns list of {phrase,reason}. Empty in MOCK mode (deterministic layer still runs)."""
    if MOCK and os.getenv("MOCK_GROUND_FLAKY") and draft_text.strip():   # tests only: mimic a checker that returns different fragments each call
        import random; w=draft_text.split(); n=random.randint(2,4); i=random.randint(0,max(0,len(w)-n))
        return [{"phrase":" ".join(w[i:i+n]).strip(".,").lower(),"reason":"not in your words"}]
    if MOCK or not draft_text.strip(): return []
    out=_call([{"role":"system","content":GROUNDING_PROMPT},{"role":"user","content":f"SOURCE:\n{source_text}\n\nDRAFT:\n{draft_text}"}],json_mode=True,chain=GROUND_CHAIN,effort=GROUND_EFFORT)
    return json.loads(out).get("unsupported",[])

EVIDENCE_PROMPT="""You read photos or text of UK health or care documents (GP or hospital letters, prescription lists, care plans, reports).
List ONLY health conditions or diagnoses and medicines that are actually written in them. Never guess, infer or add anything.
Medicines: name plus strength if written (e.g. "Donepezil 10mg"). Conditions: as written, in plain words.
If a picture is not a health document or can't be read, return empty lists.
Return JSON only: {"conditions":[...],"medicines":[...]}"""
VISION_TYPES={"jpg":"image/jpeg","png":"image/png","webp":"image/webp"}   # HEIC isn't accepted by the readers: PDF text and the other types only
def extract_evidence(images, text):
    """images: [(ext, bytes)], text: PDF text. Returns {"conditions":[],"medicines":[]} (empty in MOCK mode; the word lists still run)."""
    import base64
    if MOCK or not (images or (text or "").strip()): return {"conditions":[],"medicines":[]}
    parts=[{"type":"text","text":"DOCUMENT TEXT:\n"+(text or "")[:12000]}]
    for ext,data in images[:6]:
        if ext in VISION_TYPES: parts.append({"type":"image_url","image_url":{"url":f"data:{VISION_TYPES[ext]};base64,"+base64.b64encode(data).decode()}})
    chain=[x for x in DRAFT_CHAIN if x[0]!="custom"] or DRAFT_CHAIN
    out=json.loads(_call([{"role":"system","content":EVIDENCE_PROMPT},{"role":"user","content":parts}],json_mode=True,chain=chain,effort=DRAFT_EFFORT))
    return {"conditions":[str(x) for x in out.get("conditions") or []][:20],"medicines":[str(x) for x in out.get("medicines") or []][:20]}

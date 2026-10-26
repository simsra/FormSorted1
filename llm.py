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
_dp=os.getenv("LLM_PROVIDER") or ("custom" if os.getenv("LLM_BASE_URL") and os.getenv("LLM_API_KEY") else "anthropic" if os.getenv("ANTHROPIC_API_KEY") else "openai" if os.getenv("OPENAI_API_KEY") else "gemini")
MODEL=os.getenv("LLM_MODEL") or {"anthropic":"claude-opus-5-5","openai":"gpt-5.5","gemini":"gemini-3.8-flash"}.get(_dp,"")
DRAFT_CHAIN=[(_dp,MODEL)]+_chain(os.getenv("LLM_FALLBACKS","anthropic:claude-sonnet-5-5,gemini:gemini-3.8-flash,openai:gpt-5.5,openai:gpt-5.4"))
GROUND_CHAIN=[(os.getenv("GROUNDING_PROVIDER","openai"),os.getenv("GROUNDING_MODEL","gpt-5.4-mini"))]+_chain(os.getenv("GROUNDING_FALLBACKS","openai:gpt-5.4,gemini:gemini-3.8-flash,anthropic:claude-haiku-5-5,anthropic:claude-opus-5-5"))
# grounding: prefer a different model family than the drafter; same family only as last resort
GROUND_CHAIN=[x for x in GROUND_CHAIN if x[0]!=_dp]+[x for x in GROUND_CHAIN if x[0]==_dp]
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
Ask how often and how long. Never discuss complaints against an employer, legal claims or discrimination; if raised, say we can't help with that and suggest Acas or Citizens Advice."""
def interview_system(form):
    f=FORMS[form]
    return f"""You are a calm, kind interviewer helping a family prepare the {f['short']} (England & Wales).
Ask ONE short plain-English question at a time about {f['subject']}. Cover, in order:
""" + "\n".join(f"- {t}: {p}" for _,t,p in f["topics"]) + f"""
{EXTRA[form]}
Ask for frequency, time taken, who helps, safety risks and bad days. Never suggest symptoms or exaggerate; record only what the user says.
Never mention points or promise an outcome. If something is unclear, ask. When all topics are covered reply exactly: [[DONE]]
STRICT: you ONLY ask questions. Never give advice, opinions on eligibility, example or suggested answers, wording, summaries, or drafts of any part of the form,
even if asked. If asked for any of these, reply in one sentence that we prepare everything for them at the end, then ask your next question. Keep each reply under 60 words."""
def draft_system(form):
    f=FORMS[form]; ids=", ".join(i for i,_,_ in f["topics"])
    s=f"""From the interview transcript, write truthful first-person answers for the {f['short']}.
STRICT RULES: Use ONLY facts the USER stated in the transcript. Never add, infer or round any fact: no new conditions, symptoms, medicines, doses,
numbers, frequencies, durations, aids, people or places. If the user didn't say how often or how long, don't write one. If a topic wasn't discussed, return "".
Include how often, how long, who helps and what happens without help ONLY where the user said so. Plain English, no exaggeration.
Never state or imply eligibility, award rates, amounts, points, descriptors or likely outcomes. Return JSON: {{"answers":{{one key per topic id: {ids}}},"extra":{{}},"conditions":[{{"name","since","meds","dose"}}],
"checklist":[...evidence...],"gp_letter":"...","carer_statement":"...","notes_for_user":[...],
"sources":{{topic id: [short verbatim quotes from the USER's messages each answer is based on]}}"""
    if form=="aa": s+=""","tick_yes":[AA1 question numbers (topic ids) where the user described help or difficulty]"""
    if form=="dla": s+=""","extra" may include night_bed/night_toilet/night_treatment/night_settle/night_danger/night_wander/night_behaviour as [nights per week, minutes, times a night] and care_start"""
    if form in("pip","pipr"): s+=""","call_prep":[...phone/assessment prep points...]"""
    if form=="atw": s+=""","support_summary":[{"item","type","cost"} only items the user asked for; cost "[quote]" unless the user gave one],"call_prep":[...]"""
    if form=="pipr": s+=""","changes":"summary of what changed since the last award\""""
    return s+"}"
class LLMUnavailable(RuntimeError): pass
_DOWN={}  # provider:model -> time it last failed hard (skip for DOWN_SECS so one outage doesn't add minutes per call)
DOWN_SECS=int(os.getenv("LLM_DOWN_SECS","120"))
def _anthropic_body(model, messages, json_mode):
    sys_="\n\n".join(m["content"] for m in messages if m["role"]=="system")
    if json_mode: sys_+="\n\nReply with ONE valid JSON object only. No prose, no code fences."
    msgs=[{"role":m["role"],"content":m["content"]} for m in messages if m["role"]!="system"]
    if not msgs or msgs[0]["role"]!="user": msgs=[{"role":"user","content":"Hello, I'm ready to start."}]+msgs
    merged=[]  # Messages API requires alternating roles
    for m in msgs:
        if merged and merged[-1]["role"]==m["role"]: merged[-1]["content"]+="\n\n"+m["content"]
        else: merged.append(dict(m))
    return {"model":model,"max_tokens":int(os.getenv("LLM_MAX_TOKENS","8000")),
            "system":[{"type":"text","text":sys_,"cache_control":{"type":"ephemeral"}}],"messages":merged}
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
def _call_one(provider, model, messages, json_mode=False, retries=4):
    import time
    base,key=PROVIDERS[provider]
    if provider=="anthropic":
        body=_anthropic_body(model,messages,json_mode)
        req=urllib.request.Request(base+"/messages",json.dumps(body).encode(),{"x-api-key":key,"anthropic-version":"2023-06-01","content-type":"application/json"})
    else:
        body={"model":model,"messages":messages}
        if not model.startswith(("gpt-5","o")): body["temperature"]=0.3  # gpt-5 family only accepts the default temperature
        if json_mode: body["response_format"]={"type":"json_object"}
        req=urllib.request.Request(base+"/chat/completions",json.dumps(body).encode(),{"Authorization":"Bearer "+key,"Content-Type":"application/json"})
    for attempt in range(retries+1):  # retry transient overload / rate limits / timeouts
        try: r=json.load(urllib.request.urlopen(req,timeout=180)); break
        except urllib.error.HTTPError as e:
            msg=e.read()[:600]; low=msg.lower()
            if e.code==429 and (b"per day" in low or b"insufficient_quota" in low or b"credit" in low): raise LLMUnavailable(f"{provider}:{model} quota/credits exhausted: {msg[:200]!r}") from None
            if e.code in (429,500,502,503,504,529) and attempt<retries: time.sleep(2*2**attempt); continue
            raise LLMUnavailable(f"{provider}:{model} HTTP {e.code}: {msg[:200]!r}") from None
        except (urllib.error.URLError, TimeoutError) as e:
            if attempt<retries: time.sleep(2*2**attempt); continue
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
    return _first_json(_strip_fence(text)) if json_mode else text
def _call(messages, json_mode=False, chain=None):
    """Try each provider:model in chain (default DRAFT_CHAIN); raise LLMUnavailable if all fail."""
    errs=[]
    import time
    for p,mdl in (chain or DRAFT_CHAIN):
        if time.time()-_DOWN.get((p,mdl),0)<DOWN_SECS: errs.append(f"{p}:{mdl} skipped (recently down)"); continue
        try:
            out=_call_one(p,mdl,messages,json_mode)
            if json_mode: json.loads(out)
            USED.append(("ground" if chain is GROUND_CHAIN else "draft",f"{p}:{mdl}")); return out
        except LLMUnavailable as e: _DOWN[(p,mdl)]=time.time(); errs.append(str(e)[:200]); print("LLM fallback:",str(e)[:200])
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
        if form=="aa": return json.load(open(os.path.join(os.path.dirname(__file__),"sample_case.json")))["draft"]
        return json.loads(json.dumps({"dla":samples.DLA,"atw":samples.ATW}.get(form,samples.PIP)))
    t="\n".join(f'{m["role"].upper()}: {m["content"]}' for m in history)
    return json.loads(_call([{"role":"system","content":draft_system(form)},{"role":"user","content":t}],json_mode=True))

GROUNDING_PROMPT="""You check a drafted benefit-form answer against the customer's own words.
List every claim in the DRAFT that is not directly supported by the SOURCE (customer's words): new conditions, symptoms, medicines, doses,
numbers, frequencies, durations, aids or equipment, people, places, or any statement about eligibility or outcome.
Return JSON only: {"unsupported":[{"phrase":"exact words from the draft","reason":"short reason"}]}. Return {"unsupported":[]} if all supported."""
def grounding(draft_text, source_text):
    """Mandatory grounding check (raises LLMUnavailable if every checker model fails). Returns list of {phrase,reason}. Empty in MOCK mode (deterministic layer still runs)."""
    if MOCK or not draft_text.strip(): return []
    out=_call([{"role":"system","content":GROUNDING_PROMPT},{"role":"user","content":f"SOURCE:\n{source_text}\n\nDRAFT:\n{draft_text}"}],json_mode=True,chain=GROUND_CHAIN)
    return json.loads(out).get("unsupported",[])

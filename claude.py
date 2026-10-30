"""Anthropic Claude client for the form writer, the answer verifier and the quick-check picker (Messages API, JSON outputs).
Env: ANTHROPIC_API_KEY (never logged), WRITER_MODELS / VERIFY_MODELS / FOLLOWUP_MODELS ("model[:effort],..." tried in order),
CLAUDE_MOCK=1 (tests). Token use goes into llm.USAGE so cost per form can be worked out (see COST).
The grounding check stays on a different provider (OpenAI, grounding.py)."""
import os, json, time, urllib.request, urllib.error
import llm
BASE=os.getenv("ANTHROPIC_BASE_URL","https://api.anthropic.com/v1")
def _key(): return os.getenv("ANTHROPIC_API_KEY","")
def _chain(env,default): return [tuple((x.strip()+":").split(":")[:2]) for x in os.getenv(env,default).split(",") if x.strip()]
# Writer: Opus 5.5 (most careful writing and instruction-following; ~4-6p a form), Sonnet 5.5 if Opus is busy.
WRITER=_chain("WRITER_MODELS","claude-opus-5-5,claude-sonnet-5-5")
VERIFY=_chain("VERIFY_MODELS","claude-sonnet-5-5,claude-opus-5-5")      # sentence-by-sentence check + checklist/GP letter
FOLLOW=_chain("FOLLOWUP_MODELS","claude-haiku-5-5")                     # in the page flow: must be quick (rules if not)
def mock(): return os.getenv("CLAUDE_MOCK")=="1" or not _key()
# USD per 1M tokens (input, output incl. thinking), platform.claude.com/docs/en/about-claude/pricing, read 30 Oct 2026 (standard, global).
COST={"claude-opus-5-5":(4.0,20.0),"claude-sonnet-5-5":(2.0,10.0),"claude-haiku-5-5":(0.10,0.50),"claude-opus-5":(5.0,25.0),"claude-sonnet-5":(2.0,10.0)}
class Unavailable(RuntimeError): pass
TIMEOUT=int(os.getenv("CLAUDE_TIMEOUT","120")); RETRIES=int(os.getenv("CLAUDE_RETRIES","1"))
MAX_TOKENS=int(os.getenv("CLAUDE_MAX_TOKENS","16000"))
def strict(s):
    """JSON outputs need additionalProperties:false on every object and don't take propertyOrdering."""
    if isinstance(s,dict):
        s={k:strict(v) for k,v in s.items() if k!="propertyOrdering"}
        if s.get("type")=="object": s["additionalProperties"]=False
        return s
    if isinstance(s,list): return [strict(x) for x in s]
    return s
def _one(model,effort,system,user,schema,timeout=None,retries=None):
    timeout=timeout or TIMEOUT; retries=RETRIES if retries is None else retries
    body={"model":model,"max_tokens":MAX_TOKENS,"system":system,"messages":[{"role":"user","content":user}]}
    oc={}
    if schema: oc["format"]={"type":"json_schema","schema":strict(schema)}
    if effort: oc["effort"]=effort
    if oc: body["output_config"]=oc
    req=urllib.request.Request(f"{BASE}/messages",json.dumps(body).encode(),{"x-api-key":_key(),"anthropic-version":"2023-06-01","content-type":"application/json"})
    t0=time.time()
    for a in range(retries+1):
        try: r=json.load(urllib.request.urlopen(req,timeout=timeout)); break
        except urllib.error.HTTPError as e:
            msg=e.read()[:300]
            if e.code in (429,500,502,503,529) and a<retries:
                time.sleep(min(20,float(e.headers.get("retry-after") or 2*(a+1)))); continue
            raise Unavailable(f"{model} HTTP {e.code}: {msg[:200]!r}") from None
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            if a<retries and "timed out" not in str(e): time.sleep(2); continue
            raise Unavailable(f"{model} network: {e}") from None
    u=r.get("usage") or {}
    tin=(u.get("input_tokens",0) or 0)+(u.get("cache_read_input_tokens",0) or 0)+(u.get("cache_creation_input_tokens",0) or 0); tout=u.get("output_tokens",0) or 0
    m=llm.USAGE["by_model"].setdefault(f"anthropic:{model}",{"calls":0,"in":0,"cached_in":0,"cache_write":0,"out":0})
    for dd in (llm.USAGE,m): dd["calls"]+=1; dd["in"]+=tin; dd["out"]+=tout
    print(f"CLAUDE ok {model} {time.time()-t0:.1f}s in={tin} out={tout} stop={r.get('stop_reason')}",flush=True)
    if r.get("stop_reason") in ("refusal","max_tokens"): raise ValueError(f"stop_reason {r.get('stop_reason')}")
    text="".join(c.get("text","") for c in r.get("content") or [] if c.get("type")=="text")
    return json.loads(llm._first_json(llm._strip_fence(text)))
DOWN={}; DOWN_SECS=int(os.getenv("CLAUDE_DOWN_SECS","300"))
def call(chain,system,user,schema=None,purpose="",temperature=None,timeout=None,retries=None):
    """JSON from the first model in chain that answers. Raises Unavailable if all fail. (temperature ignored: not used with thinking.)"""
    errs=[]; live=[m for m in chain if DOWN.get(m[0],0)<time.time()] or chain[-1:]
    for model,effort in live:
        try:
            out=_one(model,effort or None,system,user,schema,timeout,retries); llm.USED.append((purpose or "claude",f"anthropic:{model}")); return out
        except Unavailable as e:
            errs.append(str(e)[:200]); print("CLAUDE fallback:",str(e)[:200],flush=True)
            if any(x in str(e) for x in ("HTTP 529","HTTP 503","HTTP 429","timed out")): DOWN[model]=time.time()+DOWN_SECS
        except (ValueError,KeyError) as e: errs.append(f"{model}: bad JSON {e}"[:200]); print("CLAUDE fallback: bad JSON",model,flush=True)
    raise Unavailable("all Claude models failed: "+" | ".join(errs))
def cost(usage=None,prices=COST):
    """USD for the token use recorded in usage (llm.USAGE shape)."""
    usage=usage or llm.USAGE; t=0.0
    for k,m in usage["by_model"].items():
        name=k.split(":",1)[1]; p=prices.get(name)
        if p: t+=m["in"]/1e6*p[0]+m["out"]/1e6*p[1]
    return t

"""Gemini client for the form writer, the answer verifier and the quick-check picker (native generateContent API).
Env: GEMINI_API_KEY (never logged), WRITER_MODELS / VERIFY_MODELS / FOLLOWUP_MODELS ("model:thinking,..." tried in order),
GEMINI_MOCK=1 (tests). Token use goes into llm.USAGE so cost per form can be worked out (see COST)."""
import os, json, time, urllib.request, urllib.error
import llm
BASE=os.getenv("GEMINI_NATIVE_BASE","https://generativelanguage.googleapis.com/v1beta")
def _key(): return os.getenv("GEMINI_API_KEY","")
def _chain(env,default): return [tuple((x.strip()+":").split(":")[:2]) for x in os.getenv(env,default).split(",") if x.strip()]
WRITER=_chain("WRITER_MODELS","gemini-3.8-flash:medium,gemini-3.6-flash:medium,gemini-3.5-flash-lite:medium")
VERIFY=_chain("VERIFY_MODELS","gemini-3.8-flash:low,gemini-3.6-flash:low,gemini-3.5-flash-lite:low")
FOLLOW=_chain("FOLLOWUP_MODELS","gemini-3.5-flash-lite:low,gemini-3.6-flash:minimal")   # in the page flow: must be quick (rules if not)
def mock(): return os.getenv("GEMINI_MOCK")=="1" or not _key()
# USD per 1M tokens (input, output incl. thinking) from ai.google.dev/gemini-api/docs/pricing, read 30 Oct 2026 (paid tier, standard).
# gemini-3.8-flash / 3.6-flash: $0.75/$3.75 to 31 Dec 2026, then $1.50/$7.50.
COST={"gemini-3.8-flash":(0.75,3.75),"gemini-3.6-flash":(0.75,3.75),"gemini-3.5-flash-lite":(0.30,2.50),"gemini-4-argon":(2.0,10.0),"gemini-3.1-pro-preview":(2.0,12.0)}
COST_2027={"gemini-3.8-flash":(1.50,7.50),"gemini-3.6-flash":(1.50,7.50),"gemini-3.5-flash-lite":(0.30,2.50),"gemini-4-argon":(4.0,20.0)}
class Unavailable(RuntimeError): pass
TIMEOUT=int(os.getenv("GEMINI_TIMEOUT","45")); RETRIES=int(os.getenv("GEMINI_RETRIES","1"))   # busy model: one quick retry, then the next model
def _one(model,think,system,user,schema,temperature=None,timeout=None,retries=None):
    timeout=timeout or TIMEOUT; retries=RETRIES if retries is None else retries
    gc={"responseMimeType":"application/json"}
    if schema: gc["responseJsonSchema"]=schema
    if think: gc["thinkingConfig"]={"thinkingLevel":think}
    if temperature is not None: gc["temperature"]=temperature
    body={"systemInstruction":{"parts":[{"text":system}]},"contents":[{"role":"user","parts":[{"text":user}]}],"generationConfig":gc}
    req=urllib.request.Request(f"{BASE}/models/{model}:generateContent",json.dumps(body).encode(),{"x-goog-api-key":_key(),"content-type":"application/json"})
    t0=time.time()
    for a in range(retries+1):
        try: r=json.load(urllib.request.urlopen(req,timeout=timeout)); break
        except urllib.error.HTTPError as e:
            msg=e.read()[:300]
            if e.code==429 and b"free_tier" in msg and b"limit: 0" in msg: raise Unavailable(f"{model}: not on this API plan") from None
            if e.code in (500,502,504) and a<retries: time.sleep(2*(a+1)); continue   # 503/429 'high demand': next model straight away
            raise Unavailable(f"{model} HTTP {e.code}: {msg[:160]!r}") from None
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            if a<retries and "timed out" not in str(e): time.sleep(2); continue
            raise Unavailable(f"{model} network: {e}") from None
    u=r.get("usageMetadata") or {}; tin=u.get("promptTokenCount",0) or 0; tout=(u.get("candidatesTokenCount",0) or 0)+(u.get("thoughtsTokenCount",0) or 0)
    m=llm.USAGE["by_model"].setdefault(f"gemini:{model}",{"calls":0,"in":0,"cached_in":0,"cache_write":0,"out":0})
    for dd in (llm.USAGE,m): dd["calls"]+=1; dd["in"]+=tin; dd["out"]+=tout
    m["cached_in"]+=u.get("cachedContentTokenCount",0) or 0
    print(f"GEMINI ok {model} {time.time()-t0:.1f}s in={tin} out={tout}",flush=True)
    c=(r.get("candidates") or [{}])[0]; parts=(c.get("content") or {}).get("parts") or []
    text="".join(p.get("text","") for p in parts if not p.get("thought"))
    return json.loads(llm._first_json(llm._strip_fence(text)))
DOWN={}   # model -> time it can be tried again (a busy or timing-out model is skipped for a while, so customers don't wait)
DOWN_SECS=int(os.getenv("GEMINI_DOWN_SECS","600"))
def call(chain,system,user,schema=None,purpose="",temperature=None,timeout=None,retries=None):
    """JSON from the first model in chain that answers. Raises Unavailable if all fail."""
    errs=[]; live=[m for m in chain if DOWN.get(m[0],0)<time.time()] or chain[-1:]
    for model,think in live:
        try:
            out=_one(model,think or None,system,user,schema,temperature,timeout,retries); llm.USED.append((purpose or "gemini",f"gemini:{model}")); return out
        except Unavailable as e:
            errs.append(str(e)[:160]); print("GEMINI fallback:",str(e)[:160],flush=True)
            if any(x in str(e) for x in ("HTTP 503","HTTP 429","timed out","not on this API plan")): DOWN[model]=time.time()+DOWN_SECS
        except (ValueError,KeyError) as e: errs.append(f"{model}: bad JSON {e}"[:160]); print("GEMINI fallback: bad JSON",model,flush=True)
    if live and errs and "HTTP 503" in errs[-1]:   # last model was busy (not over quota): one more go after a short pause
        time.sleep(float(os.environ.get("GEMINI_BUSY_WAIT","3"))); model,think=live[-1]
        try:
            out=_one(model,think or None,system,user,schema,temperature,timeout,0); llm.USED.append((purpose or "gemini",f"gemini:{model}")); DOWN.pop(model,None); return out
        except (Unavailable,ValueError,KeyError) as e: errs.append(str(e)[:160])
    raise Unavailable("all Gemini models failed: "+" | ".join(errs))
def cost(usage=None,prices=COST):
    """USD for the token use recorded in usage (llm.USAGE shape)."""
    usage=usage or llm.USAGE; t=0.0
    for k,m in usage["by_model"].items():
        name=k.split(":",1)[1]; p=prices.get(name)
        if p: t+=m["in"]/1e6*p[0]+m["out"]/1e6*p[1]
    return t

"""Grounding check: flag drafted details not found in the customer's own words.
Layer 1 (deterministic): numbers, frequency/duration phrases, condition/medication/aid/people/place terms.
Layer 2 (LLM_GROUNDING): llm.grounding() when an API key is set. Set LLM_GROUNDING=0 to disable."""
import re, os
NUMW={"one":1,"two":2,"three":3,"four":4,"five":5,"six":6,"seven":7,"eight":8,"nine":9,"ten":10,"eleven":11,"twelve":12,"fifteen":15,"twenty":20,"thirty":30,"forty":40,"fifty":50,"sixty":60,"hundred":100,"once":1,"twice":2,"half":0.5,"quarter":0.25,"a couple of":2}
CONDITIONS="arthritis|osteoarthritis|rheumatoid|dementia|alzheimer|parkinson|diabetes|epilepsy|seizure|stroke|copd|asthma|heart|angina|cancer|depression|anxiety|ptsd|bipolar|schizophrenia|autism|autistic|adhd|dyspraxia|dyslexia|cerebral palsy|down syndrome|fibromyalgia|ms|multiple sclerosis|sclerosis|incontinence|glaucoma|macular|deafness|deaf|blind|blindness|hearing loss|sight loss|migraine|pain|neuropathy|hip|knee|spine|lupus|crohn|colitis|ibs|kidney|dialysis|amputation|ocd|eating disorder|breathless|breathlessness|dizziness|dizzy|fatigue|tremor".split("|")
MEDS="methotrexate|sertraline|paracetamol|ibuprofen|codeine|morphine|tramadol|gabapentin|pregabalin|insulin|metformin|warfarin|amlodipine|ramipril|omeprazole|levothyroxine|fluoxetine|citalopram|mirtazapine|melatonin|ritalin|methylphenidate|interferon|co-careldopa|inhaler|steroid|antidepressant|painkiller|patch|injection".split("|")
AIDS="wheelchair|walking frame|zimmer|rollator|stick|crutch|walker|commode|hoist|grab rail|shower seat|bath seat|perching stool|raised toilet seat|stairlift|stair lift|pad|catheter|hearing aid|glasses|reins|buggy|pushchair|splint|brace|oxygen|alarm|pendant|adapted cutlery|mobility scooter|taxi".split("|")
PEOPLE="daughter|son|wife|husband|partner|carer|mum|mother|dad|father|sister|brother|neighbour|friend|nurse|doctor|gp|consultant|teacher|senco|therapist|physio|grandson|granddaughter|grandparent|nan|grandma|grandad|paramedic|social worker".split("|")
PLACES="hospital|a&e|school|nursery|care home|hospice|clinic|day centre|bus|train|shop|supermarket|church|park|garden|bathroom|kitchen|stairs|upstairs".split("|")
MULTI=[t for t in CONDITIONS+AIDS+PEOPLE+PLACES]  # handled via phrase search
FREQ=re.compile(r"\b(\d+(?:\.\d+)?|"+"|".join(sorted(NUMW,key=len,reverse=True))+r")\s*(?:to\s*\d+\s*)?(times?|x)?\s*(a|an|per|each|every)?\s*(day|days|night|nights|week|weeks|month|months|year|years|morning|mornings|hour|hours|hrs?|minute|minutes|mins?|seconds?|metres|meters|m|yards|miles|mg|ml|steps|falls?)\b",re.I)
FREQW=re.compile(r"\b(daily|nightly|weekly|monthly|every day|every night|every morning|most days|most nights|all day|all night|always|constantly|hourly)\b",re.I)
EXAGG=re.compile(r"\b(always|never|constantly|completely|totally|entirely|at all|impossible|every single|all the time|unable to do anything|bed-?bound|housebound|severe|extreme(?:ly)?)\b",re.I)
def _num(x):
    x=x.lower(); return float(x) if re.match(r"^\d",x) else float(NUMW.get(x,-1))
def quantities(text):
    """Return set of (number, unit-normalised) plus frequency words."""
    q=set()
    for m in FREQ.finditer(text):
        n=_num(m.group(1)); unit=(m.group(4) or "").lower().rstrip("s")
        unit={"min":"minute","hr":"hour","meter":"metre","m":"metre"}.get(unit,unit); q.add((n,unit,m.group(0).strip()))
    return q
def stem(w):
    """Light, conservative stemmer so word forms match (inject/injection/injections, eat/eats/eating).
    Never strips -er (carer must not match car)."""
    for suf,rep in (("ications","icat"),("ication","icat"),("ions","") ,("ion",""),("ings",""),("ing",""),("ies","y"),("es",""),("ed",""),("s","")):
        if w.endswith(suf) and len(w)-len(suf)>=3: w=w[:len(w)-len(suf)]+rep; break
    if len(w)>3 and w[-1]=="e": w=w[:-1]  # wake/waking, injecte
    if len(w)>3 and w[-1]==w[-2] and w[-1] not in "ls": w=w[:-1]  # running->run
    return w
def _stems(text): return " "+" ".join(stem(w) for w in re.sub(r"[^a-z0-9&-]"," ",text.lower()).replace("-"," ").split())+" "
def terms(text, vocab):
    low=_stems(text)
    return {t for t in vocab if _stems(t) in low}
def check_answer(draft, source):
    """Deterministic: returns list of {phrase, kind}."""
    flags=[]; src=source.lower()
    sq=quantities(source); src_nums={(n,u) for n,u,_ in sq}; src_numbers={n for n,_,_ in sq}|{float(x) for x in re.findall(r"\d+(?:\.\d+)?",source)}|{float(v) for k,v in NUMW.items() if re.search(rf"\b{k}\b",src)}
    for n,u,ph in quantities(draft):
        if (n,u) not in src_nums: flags.append({"phrase":ph,"kind":"number or frequency"})
    for m in FREQW.finditer(draft):
        if m.group(0).lower() not in src: flags.append({"phrase":m.group(0),"kind":"frequency"})
    for kind,vocab in (("condition or symptom",CONDITIONS),("medicine",MEDS),("aid or equipment",AIDS),("person",PEOPLE),("place",PLACES)):
        for t in terms(draft,vocab)-terms(source,vocab): flags.append({"phrase":t,"kind":kind})
    for m in EXAGG.finditer(draft):   # stronger than the customer's words (Oct 2026: never exaggerate)
        if not re.search(r"\b"+re.escape(m.group(0).lower())+r"\b",src): flags.append({"phrase":m.group(0),"kind":"stronger than your words"})
    for m in re.finditer(r"\b\d+(?:\.\d+)?\s*mg\b",draft,re.I):
        if m.group(0).lower().replace(" ","") not in src.replace(" ",""): flags.append({"phrase":m.group(0),"kind":"dose"})
    for m in re.finditer(r"\b(entitled|eligible|qualif\w+|will (get|receive|be awarded)|higher rate|lower rate|middle rate|enhanced rate|standard rate|points?)\b",draft,re.I):
        flags.append({"phrase":m.group(0),"kind":"outcome claim (never state eligibility or amounts)"})
    seen=set(); out=[]
    for f in flags:
        k=f["phrase"].lower()
        if k not in seen: seen.add(k); out.append(f)
    return out
class GroundingUnavailable(RuntimeError): pass
def check(answers, source_text, use_llm=None):
    """answers {tid:text} -> {tid:[{phrase,kind}]} (only non-empty)."""
    import llm
    use_llm=(os.getenv("LLM_GROUNDING","1")!="0") if use_llm is None else use_llm
    res={}; todo=[(tid,a) for tid,a in answers.items() if (a or "").strip()]
    llm_out={}
    if use_llm and todo:   # every answer is still checked by the model; the calls just run at the same time (was ~1-2s each, one after another)
        import concurrent.futures as cf
        with cf.ThreadPoolExecutor(min(8,len(todo))) as ex:
            futs={tid:ex.submit(llm.grounding,a,source_text) for tid,a in todo}
            for tid,fu in futs.items():
                try: llm_out[tid]=fu.result()
                except Exception as e: raise GroundingUnavailable(str(e)[:300]) from None  # mandatory: never silently skip
    for tid,a in todo:
        f=check_answer(a,source_text)
        for x in llm_out.get(tid,[]):
            if x.get("phrase") and x["phrase"].lower() not in {y["phrase"].lower() for y in f}: f.append({"phrase":x["phrase"],"kind":x.get("reason","not in your words")})
        if f: res[tid]=f
    return res
_ABBR=r"(?:Mr|Mrs|Ms|Dr|St|etc|e\.g|i\.e|approx|no|vs)"
def sentences(text):
    """Split into whole sentences: only at . ! ? followed by space and a capital/digit/quote, not after common abbreviations
    or inside 24/7, 1.5 etc. Line breaks also end a sentence."""
    out=[]
    for para in re.split(r"\n+",text or ""):
        for snt in _split(para):
            if snt.strip(): out.append(snt.strip())
    return out
def _split(para):
    parts=[]; cur=""
    for tok in re.split(r"(?<=[.!?])\s+",para):
        cur=(cur+" "+tok).strip() if cur else tok
        prev=re.search(r"(\w+)\.$",cur)
        if prev and re.fullmatch(_ABBR,prev.group(1),re.I): continue
        parts.append(cur); cur=""
    if cur: parts.append(cur)
    # glue lower-case starts back on (a split mid-sentence, e.g. "...lost. for hours")
    out=[]
    for x in parts:
        if out and x[:1].islower(): out[-1]+=" "+x
        else: out.append(x)
    return out
def remove_sentence(answer, sentence):
    """Remove one whole sentence (whitespace-insensitive), keeping the rest."""
    key=" ".join(sentence.lower().split()); out=[]
    for para in re.split(r"(\n+)",answer or ""):
        if para.startswith("\n"): out.append(para); continue
        out.append(" ".join(x for x in _split(para) if " ".join(x.lower().split())!=key))
    return "".join(out).strip()
def remove_phrase(answer, phrase):
    """Remove the sentence(s) containing phrase."""
    parts=re.split(r"(?<=[.!?])\s+",answer)
    return " ".join(p for p in parts if phrase.lower() not in p.lower()).strip()

"""Evidence (Oct 2026): what the customer has that supports the claim, and a cross-check of uploaded documents against
what they told us. Facts found in documents are NEVER added to the form unless the customer confirms them on /confirm.
Extraction: deterministic word lists over PDF text (always), plus llm.extract_evidence() (vision for photos, text for PDFs)
when a provider is configured. Customer copy never mentions how the reading is done."""
import re, hashlib
EVIDENCE=[("gp","Letter from GP or consultant"),("rx","Prescription list"),("hosp","Hospital or clinic letters"),
 ("care","Care plan, or OT or physio report"),("carer","Letter from a carer, friend or family"),("none","Nothing yet")]
EVIDENCE_DLA=[("gp","Letter from GP, paediatrician or consultant"),("rx","Prescription list"),("hosp","Hospital or clinic letters"),
 ("care","Care plan, or OT, physio or speech therapy report"),("ehcp","EHCP or school report"),("carer","Letter from a carer, friend or family"),("none","Nothing yet")]
def options(form): return EVIDENCE_DLA if form=="dla" else EVIDENCE
# condition groups: (label shown, strict words for reading documents, extra words for matching the customer's own condition names)
GROUPS={
 "arthritis":("Arthritis",["arthritis","osteoarthritis","rheumatoid"],[]),
 "dementia":("Dementia or memory problems",["dementia","alzheimer","cognitive impairment"],["memory"]),
 "heart":("Heart condition",["heart failure","angina","atrial fibrillation","cardiac","heart disease","coronary"],["heart"]),
 "breath":("COPD, asthma or breathing problems",["copd","asthma","emphysema","bronchiectasis","pulmonary fibrosis"],["breathing"]),
 "stroke":("Stroke",["stroke","cerebrovascular"],[]),
 "parkinson":("Parkinson's",["parkinson"],[]),
 "diabetes":("Diabetes",["diabetes","diabetic"],[]),
 "sight":("Sight loss",["macular degeneration","glaucoma","visual impairment","sight impaired","severely sight","cataract"],["sight"]),
 "hearing":("Hearing loss",["hearing loss","deafness","hearing impair"],["hearing","deaf"]),
 "depression":("Depression",["depression","depressive"],[]),
 "anxiety":("Anxiety",["anxiety","panic disorder","generalised anxiety"],[]),
 "cancer":("Cancer",["cancer","carcinoma","lymphoma","leukaemia","tumour","malignan"],[]),
 "autism":("Autism",["autism","autistic","asd"],[]),
 "adhd":("ADHD",["adhd","attention deficit"],[]),
 "ld":("Learning disability",["learning disability"],[]),
 "cp":("Cerebral palsy",["cerebral palsy"],[]),
 "epilepsy":("Epilepsy",["epilepsy","epileptic","seizure disorder"],["seizure"]),
 "speech":("Speech and language delay",["speech and language","language delay","speech delay"],["speech"]),
 "gdd":("Global developmental delay",["developmental delay"],[]),
 "downs":("Down's syndrome",["down's syndrome","down syndrome","trisomy 21"],[]),
 "sensory":("Sensory processing difficulties",["sensory processing"],["sensory"]),
 "back":("Back or joint pain",["back pain","lumbar","sciatica","spondyl","disc prolapse","joint pain"],["back","joint"]),
 "fibro":("Fibromyalgia",["fibromyalgia"],[]),
 "me":("ME or chronic fatigue",["chronic fatigue","myalgic encephalomyelitis","me/cfs"],[]),
 "ms":("MS",["multiple sclerosis"],[" ms "]),
 "ptsd":("PTSD",["ptsd","post-traumatic","post traumatic"],[]),
 "bp":("High blood pressure",["hypertension","high blood pressure"],[]),
 "kidney":("Kidney disease",["chronic kidney","renal failure","ckd"],["kidney"]),
 "osteoporosis":("Osteoporosis",["osteoporosis"],[]),
 "neuropathy":("Neuropathy",["neuropathy"],[]),
}
MEDS=("donepezil memantine rivastigmine galantamine atorvastatin simvastatin bisoprolol amlodipine ramipril losartan candesartan furosemide "
 "apixaban rivaroxaban warfarin edoxaban clopidogrel aspirin metformin gliclazide insulin sitagliptin salbutamol beclometasone fostair symbicort seretide tiotropium "
 "omeprazole lansoprazole levothyroxine paracetamol ibuprofen naproxen co-codamol codeine tramadol morphine oxycodone gabapentin pregabalin amitriptyline nortriptyline "
 "duloxetine sertraline fluoxetine citalopram escitalopram mirtazapine venlafaxine quetiapine olanzapine risperidone aripiprazole lithium diazepam lorazepam zopiclone "
 "propranolol levetiracetam lamotrigine carbamazepine valproate methylphenidate lisdexamfetamine atomoxetine melatonin co-careldopa madopar levodopa ropinirole "
 "methotrexate hydroxychloroquine sulfasalazine prednisolone alendronic adcal tamsulosin finasteride mebeverine laxido macrogol senna lactulose").split()
MED_RE=re.compile(r"\b("+"|".join(re.escape(m) for m in sorted(MEDS,key=len,reverse=True))+r")\b(?:[^\S\n]*(?:tablets?|capsules?|inhaler|modified[- ]release|m/r)?[^\S\n]*(\d+(?:\.\d+)?[^\S\n]*(?:mg|mcg|micrograms|ml|units)))?",re.I)
def _low(t): return " "+re.sub(r"\s+"," ",(t or "").lower())+" "
def groups_of(text,broad=True):
    low=_low(text); out=set()
    for g,(lab,strict,extra) in GROUPS.items():
        if any(w in low for w in strict+(extra+[lab.lower()] if broad else [])): out.add(g)
    return out
def read_text(text):
    """Deterministic: {'conditions':[labels], 'medicines':['Name 10mg']} from document text."""
    conds=[GROUPS[g][0] for g in sorted(groups_of(text,broad=False))]
    meds={}
    for m in MED_RE.finditer(text or ""):
        k=m.group(1).lower(); dose=(m.group(2) or "").replace(" ","")
        if k not in meds or (dose and not meds[k].split(" ",1)[1:]): meds[k]=(m.group(1)[0].upper()+m.group(1)[1:].lower())+(" "+dose if dose else "")
    return {"conditions":conds,"medicines":list(meds.values())}
def merge_facts(*fs):
    out={"conditions":[],"medicines":[]}
    for f in fs:
        for k in out:
            for x in (f or {}).get(k) or []:
                x=re.sub(r"\s+"," ",str(x)).strip()[:80]
                if not x: continue
                if k=="conditions" and any(same_condition(x,y) for y in out[k]): continue
                if k=="medicines" and any(x.split()[0].lower()==y.split()[0].lower() for y in out[k]): continue
                out[k].append(x)
    return out
STOP={"or","and","the","of","a","problems","problem","condition","conditions","disease","disorder","chronic","syndrome","difficulties","loss","pain","type","left","right"}
def _words(t): return {w for w in re.findall(r"[a-z']+",t.lower()) if w not in STOP and len(w)>2}
def same_condition(a,b):
    ga,gb=groups_of(a),groups_of(b)
    if ga and gb: return bool(ga&gb)
    return bool(_words(a)&_words(b))
def said_conditions(I):
    return [c.get("name","") for c in I.get("conds") or [] if c.get("name")]
def _id(p,t): return p+hashlib.sha1(t.lower().encode()).hexdigest()[:8]
def mismatches(I):
    """What the documents say vs what the customer said. Never changes anything by itself."""
    f=I.get("doc_facts") or {}; said=said_conditions(I); words=" ".join([I.get("words","")]+[c.get("tx","") for c in I.get("conds") or []])
    done=I.get("doc_resolved") or {}
    new=[c for c in f.get("conditions") or [] if not any(same_condition(c,s) for s in said) and not groups_of(c)&groups_of(words,broad=False)]
    missing=[s for s in said if f.get("conditions") and not any(same_condition(s,c) for c in f["conditions"])]
    meds=list(f.get("medicines") or [])
    out=[]
    for c in new[:5]: out.append({"id":_id("dc_",c),"kind":"doc_cond","text":c})
    if meds: out.append({"id":_id("dm_","|".join(meds)),"kind":"doc_meds","text":", ".join(meds[:10]),"items":meds[:10]})
    for s in missing[:5]: out.append({"id":_id("sc_",s),"kind":"said_cond","text":s})
    return [x for x in out if x["id"] not in done]
def checklist(form,I):
    """Evidence lines for the documents' checklist (what to send, or what to get if they have nothing yet)."""
    ev=I.get("evidence") or []; ups=I.get("uploads") or []; lab=dict(options(form)); out=[]
    have=[lab[k] for k in ev if k in lab and k!="none"]+([I["else"]["evidence"]] if (I.get("else") or {}).get("evidence") else [])
    if have: out.append("Evidence you told us you have: "+"; ".join(x[0].lower()+x[1:] for x in have)+". Send copies (not originals) with your form.")
    if "none" in ev or not (have or ups):
        who="your child's" if form=="dla" else "your"
        out.append(f"You don't have to send evidence, but it helps. Ask {who} GP surgery for a printout of the health conditions and repeat prescriptions (reception can print it, or you may see it in the NHS App), and send a copy with the form.")
        if form=="dla": out.append("If your child has an EHCP, a school or nursery report, or a letter from a paediatrician or therapist, send a copy of that too.")
        else: out.append("A recent letter from a hospital or clinic, a care plan, or a short letter from someone who helps you can also support the form.")
    if ev or ups: out.append("Don't wait for new letters if it would make you miss your deadline. Send the form on time; you can send evidence afterwards with your name and National Insurance number on it.")
    return out

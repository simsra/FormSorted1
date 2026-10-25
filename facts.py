"""Single registry of every fixed fact FormSorted states to customers. Each fact: value, source URL, verified_on.
Re-verify with /workspace/butter/govuk_watch/watch.py whenever a source page changes."""
F=lambda value,source,verified_on="2026-10-24",note="": {"value":value,"source":source,"verified_on":verified_on,"note":note}
FACTS={
 # Deadlines / backdating
 "aa_phone_window_weeks":F(6,"https://www.gov.uk/attendance-allowance/how-to-claim",note="If you call the helpline for a form, claim starts on date of call if form returned within 6 weeks; printed form starts on date DWP receives it."),
 "dla_phone_window_weeks":F(6,"https://www.gov.uk/disability-living-allowance-children/how-to-claim",note="Starts on date received or date of call if claim pack returned within 6 weeks. Cannot be backdated."),
 "pip2_return_months":F(1,"https://www.gov.uk/pip/how-to-claim",note="Return form within 1 month; contact PIP enquiry line for more time. PIP2 posted forms usually arrive within 2 weeks."),
 "mr_months":F(1,"https://www.gov.uk/mandatory-reconsideration",note="Usually within one month of the date of the decision; later with good reason (e.g. hospital, bereavement)."),
 "ar1_deadline":F(None,"https://www.gov.uk/pip/when-your-pip-claim-is-reviewed",verified_on=None,note="NOT verified: tell users to use the date on their AR1 letter."),
 # Phone numbers
 "aa_helpline":F("0800 731 0122","https://www.gov.uk/attendance-allowance/how-to-claim"),
 "dla_helpline":F("0800 121 4600","https://www.gov.uk/disability-living-allowance-children/how-to-claim"),
 "pip_new_claims":F("0800 917 2222","https://www.gov.uk/pip/how-to-claim"),
 "pip_enquiry_line":F(None,"https://www.gov.uk/pip/how-to-claim",verified_on=None,note="Number NOT verified; we say 'the number on your PIP letter'."),
 "age_uk_advice":F("0800 678 1602","https://www.moneysavingexpert.com/news/2026/08/attendance-allowance-claims-warning/"),
 "contact_helpline":F("0808 808 3555","https://contact.org.uk/",verified_on=None,note="Carried over from earlier research; re-verify on contact.org.uk."),
 "scope_helpline":F("0808 800 3333","https://www.moneysavingexpert.com/news/2026/08/attendance-allowance-claims-warning/"),
 # Addresses
 "aa_freepost":F("Freepost DWP Attendance Allowance","https://www.gov.uk/attendance-allowance/how-to-claim"),
 "pip_freepost":F("Freepost DWP PIP 1","https://www.gov.uk/pip/how-to-claim"),
 "dla_freepost":F("Freepost DWP DLA Child","https://www.gov.uk/disability-living-allowance-children/how-to-claim",verified_on=None,note="Not shown on the how-to-claim page fetched 24 Oct; check the DLA1A form notes."),
 # Pricing comparison
 "mse_fee_example":F({"fee_gbp":1033,"share_first_year":"18%","weekly_award_gbp":110},"https://www.moneysavingexpert.com/news/2026/08/attendance-allowance-claims-warning/",note="MSE, 11 Aug 2026: Patricia paid £1,033, equivalent to 18% of first year's AA."),
 # Official forms
 "aa1_form":F("AA1 (Nov 2025)","https://www.gov.uk/government/publications/attendance-allowance-claim-form",verified_on=None),
 "dla1a_form":F("DLA1A (10/25)","https://www.gov.uk/government/publications/disability-living-allowance-for-children-claim-form",verified_on=None),
 "pip2_example":F("PIP2 example (for reference only)","https://www.gov.uk/government/publications/example-pip2-how-your-disability-affects-you"),
 "ar1_example":F("AR1 example","https://www.gov.uk/government/publications/example-personal-independence-payment-review-form-ar1-and-ar2"),
 # Access to Work (AtW)
 "atw_helpline":F("0800 121 7479","https://www.gov.uk/access-to-work/apply"),
 "atw_apply_ways":F("online or by phone","https://www.gov.uk/access-to-work/apply",note="Asks: contact details, workplace address, how condition affects work and what support you need, workplace contact (employed), UTR (self-employed), NI number if you have it."),
 "atw_eligibility":F("16+, paid work or starting/returning within 12 weeks, live and work in England/Scotland/Wales; no diagnosis needed; not voluntary work; self-employed turnover at least £6,500; civil servants get support from employer","https://www.gov.uk/access-to-work/eligibility"),
 "atw_cost_share_weeks":F(6,"https://www.gov.uk/government/publications/access-to-work-guide-for-employers/access-to-work-factsheet-for-employers",note="Employer may share cost only for special aids/equipment and adaptations if employee has worked >6 weeks when applying. Up to 100% for <6 weeks, self-employed, support workers, travel, communication support at interviews. Factsheet updated 7 Oct 2025."),
 "atw_reconsider":F("call the helpline to ask someone to reconsider","https://www.gov.uk/access-to-work/after-you-apply"),
 "atw_renew_weeks":F(12,"https://www.gov.uk/access-to-work/renew",note="Can apply to renew 12 weeks before grant ends."),
 "atw_no_reasonable_adjustments":F("AtW will not pay for reasonable adjustments","https://www.gov.uk/access-to-work"),
 "atw_claim_months":F(9,"https://www.gov.uk/government/publications/access-to-work-guide-for-employers/access-to-work-factsheet-for-employers",note="Employee has 9 months to claim for costs."),
 "atw_online_questions":F(None,"https://www.gov.uk/access-to-work/apply",verified_on=None,note="Exact wording of the online application questions NOT verified (service is behind the apply journey); topics follow the GOV.UK 'you'll need to give' list."),
 # Benefit rates: we deliberately state none.
}
def v(k): return FACTS[k]["value"]
def src(k): return FACTS[k]["source"]

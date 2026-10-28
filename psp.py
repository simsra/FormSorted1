"""'Print, sign, post' guide for whoever prints the form themselves (documents page and answers pack).
Signature boxes come from the official forms: AA1 11/25 (aa1_fields.json) and DLA1 Child 10/25 (dla1a_fields.json);
PIP2 and AR1 are DWP's own personalised forms. Freepost addresses checked against GOV.UK on 28 Oct 2026.
Neutral by design: it says how to print, sign and post, and nothing about what to do next."""
import html
AA_FREEPOST="Freepost DWP Attendance Allowance"
DLA_FREEPOST="Freepost DWP DLA Child"
INK=("Do not type, paste or e-sign a signature, and do not use correction fluid. "
     "If you make a mistake, cross it out with a pen and write the right answer next to it.")
PRINT="Print at actual size: in the print settings choose “Actual size” or 100%, not “Fit to page”. Use plain white A4; one-sided or double-sided are both fine."
def steps(form, filled=True, hand_details=False):
    """[(heading, text)] for this form. filled: the filled-in PDF is in the pack. hand_details: NI/bank were skipped."""
    hd=" You chose to write the National Insurance number and bank details by hand, so add those too." if hand_details else ""
    if form=="aa":
        return [
          ("Print it",("Print the filled-in AA1, including any extra sheets at the end of the PDF. " if filled else "Print the AA1 you copied the answers into. ")+PRINT),
          ("Sign and date in black ink","Sign and date by hand, in black ink, in these boxes: question 20 on page 9 (tick one of the consent options, then sign and date) and question 64 on page 30 (the Declaration: sign, date and print the name). The signatures and dates are the only things to add by hand."+hd),
          ("Sign it yourself, on paper",INK),
          ("Signing for someone else?","Tick the reason at question 15 on page 5, then sign questions 20 and 64 yourself. Enclose the Power of Attorney, deputy or other authority papers the form asks for (the original or a certified copy)."),
          ("Leave the statement for the supporter","Questions 55 to 62 on page 28 are for someone who knows the person claiming to fill in, sign and date themselves. Leave them blank for that person. If you are signing the form for someone else, someone else must fill in this section."),
          ("Extra sheets","Write the full name and National Insurance number of the person claiming on every extra sheet."),
          ("Evidence","Send copies of your evidence, never originals."),
          ("Post it",f"Address the envelope to: {AA_FREEPOST}. Write nothing else on the envelope. You do not need a stamp or a postcode."),
          ("Keep a copy","Keep a copy of everything and note the date you posted it. The claim starts on the date DWP receives the form."),
        ]
    if form=="dla":
        return [
          ("Print it",("Print the filled-in DLA1 Child form, including any extra sheets at the end of the PDF. " if filled else "Print the DLA1 Child form you copied the answers into. ")+PRINT),
          ("Sign and date in black ink","The person in About You (page 35) signs and dates by hand, in black ink, in these boxes: question 39 on page 12 (tick Yes or No, then sign and date under “I have read and understood how DWP uses information”) and the Declaration on page 38 (sign, print your name and date). The signatures and dates are the only things to add by hand."+hd),
          ("Sign it yourself, on paper",INK),
          ("Who signs","You sign as yourself, the person claiming for the child. Nobody else signs the consent or Declaration for you."),
          ("Leave the statement for the supporter","Question 38 on pages 10 and 11 is for someone who knows the child to fill in, then sign and date on page 11 themselves. Leave it blank for that person."),
          ("Extra sheets","Write the child's full name and National Insurance number (if they have one) on every extra sheet, and sign and date each sheet."),
          ("Evidence","Send copies of your evidence, never originals. Add the child's name and National Insurance number (if they have one) to each document."),
          ("Post it",f"Use the envelope DWP sent you, or address an envelope to: {DLA_FREEPOST}. Write nothing else on the envelope. You do not need a stamp or a postcode."),
          ("Keep a copy","Keep a copy of everything and note the date you posted it. The claim starts when DWP receives the form, or from the date you called the helpline if you return it within 6 weeks."),
        ]
    code="PIP2" if form=="pip" else "AR1"
    sign=("Sign and date the Declaration on the PIP2 by hand, in black ink, and any other signature box on the form."
          if form=="pip" else "Sign the Declaration in Section 1 (“Read and sign”) by hand, in black ink, and sign under “I have read and understood how DWP uses information” in Section 3.")
    behalf=("Only sign for the person claiming if you are their appointee, deputy or attorney, or they cannot sign because of their illness or disability. Put a cross in the reason in the “If you are signing the form for someone else” list, and enclose any authority papers the form asks for."
            if form=="pip" else "If you are acting for the person, sign the form on their behalf, as the AR1 says, and enclose any authority papers DWP asks for.")
    return [
      ("Use the form DWP sent you",f"Copy each answer onto the paper {code} DWP sent you, in black ink. Do not print a {code} from anywhere else. Where a box is too small, write “see extra sheet”."),
      ("Print the extra sheets","Print the extra sheets (PDF) to send with the form. "+PRINT),
      ("Sign and date in black ink",sign),
      ("Sign it yourself, on paper",INK),
      ("Signing for someone else?",behalf),
      ("Extra sheets","Write the full name and National Insurance number on every extra sheet."),
      ("Evidence","Send copies of your evidence, never originals."),
      ("Post it",f"Put the {code} and the extra sheets in the envelope DWP sent you."+(" Return it by the date on the front of the form." if form=="pipr" else " Return it by the date on DWP's letter.")),
      ("Keep a copy","Keep a copy of everything and note the date you posted it."),
    ]
def html_section(form, filled=True, hand_details=False, h="h2"):
    if form not in ("aa","dla","pip","pipr"): return ""
    e=html.escape
    li="".join(f"<li><strong>{e(t)}.</strong> {e(x)}</li>" for t,x in steps(form,filled,hand_details))
    return f"<{h}>Print, sign, post: step by step</{h}><p>If you are printing the form yourself:</p><ol class=steps>{li}</ol>"
# The exact boxes to sign, for the printed cover sheet ('Sign here and post it back').
SIGN_BOXES={
 "aa":["Question 20 on page 9: tick one consent option, then sign and date.",
       "Question 64 on page 30 (Declaration): sign, date and print the name.",
       "Signing for someone else? Also tick the reason at question 15 on page 5, and enclose the authority papers."],
 "dla":["Question 39 on page 12: tick Yes or No, then sign and date.",
        "Declaration on page 38: sign, print your name and date.",
        "Every extra sheet at the end of the form: sign and date it."],
 "pip":["The Declaration on the PIP2 DWP sent you: sign and date it.",
        "Signing for someone else? Put a cross in the reason in the list next to the Declaration."],
 "pipr":["Section 1 (Read and sign) on the AR1 DWP sent you: sign the Declaration.",
         "Section 3: sign under “I have read and understood how DWP uses information”."],
}

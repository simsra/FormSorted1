"""Printable extra sheets (PDF): continuation sheets for the official forms, and PIP extra-information sheets.
Each page carries the claimant's name, a space for the NI number, the form and question, and page numbers,
so DWP can match loose sheets to the claim."""
import os
from fpdf import FPDF
HERE=os.path.dirname(os.path.abspath(__file__)); FONTS=os.path.join(HERE,"fonts")
class _Sheet(FPDF):
    def __init__(self,title,name):
        super().__init__(format="A4"); self.t=title; self.n=name or ""; self.sign_each=False
        self.add_font("D","",os.path.join(FONTS,"DejaVuSans.ttf")); self.add_font("D","B",os.path.join(FONTS,"DejaVuSans-Bold.ttf"))
        self.set_auto_page_break(True,22); self.set_margins(18,16,18); self.alias_nb_pages()
    def header(self):
        self.set_font("D","B",12); self.cell(0,7,self.t,new_x="LMARGIN",new_y="NEXT")
        self.set_font("D","",10)
        self.cell(110,7,f"Full name: {self.n}" if self.n else "Full name: ____________________________________")
        self.cell(0,7,"NI number: ______________________",new_x="LMARGIN",new_y="NEXT")
        self.set_draw_color(0); self.line(18,self.get_y()+1,192,self.get_y()+1); self.ln(4)
    def footer(self):
        if self.sign_each:   # DLA1 Child: "sign and date each sheet that you use"
            self.set_y(-24); self.set_font("D","",10); self.cell(0,6,"Signature: ______________________________     Date: ____ / ____ / ________",new_x="LMARGIN",new_y="NEXT")
        self.set_y(-16); self.set_font("D","",9)
        self.cell(0,5,f"{self.t}  ·  Page {self.page_no()} of {{nb}}",align="C")
    def section(self,heading,text,cont_label=" (continued)"):
        self.set_font("D","B",11); self.multi_cell(0,6,heading,new_x="LMARGIN",new_y="NEXT"); self.ln(1)
        self.set_font("D","",11)
        for para in (text or "").split("\n"):
            if para.strip(): self.multi_cell(0,6,para.strip(),new_x="LMARGIN",new_y="NEXT"); self.ln(2)
        self.ln(3)
def continuation(form_code, version, name, sections):
    """sections: [(heading, text)] -> PDF bytes. Used when an answer is too long even for the form's own extra box."""
    p=_Sheet(f"{form_code} ({version}) continuation sheet",name); p.sign_each=form_code.upper().startswith("DLA")
    if p.sign_each: p.set_auto_page_break(True,30)
    p.add_page()
    p.set_font("D","",10); p.multi_cell(0,5,f"These answers did not fit in the boxes on the {form_code} form. Please send this sheet with the form. Write your NI number on every page."+(" Sign and date every page in black ink." if p.sign_each else ""),new_x="LMARGIN",new_y="NEXT"); p.ln(4)
    for h,t in sections: p.section(h,t)
    if not p.sign_each: p.ln(4); p.set_font("D","",10); p.cell(0,8,"Signature: ______________________________     Date: ____ / ____ / ________")
    return bytes(p.output())
def pip_sheets(name, items, form_code="PIP2"):
    """items: [(question heading, text)] -> PDF bytes, one question per page (long answers run onto more pages)."""
    p=_Sheet(f"{form_code}: extra information",name)
    for h,t in items:
        p.add_page(); p.section(h,t or "Not discussed. If this applies, add it in your own words.")
    return bytes(p.output())
def supporter_note(form, who, claimant, question, topics):
    """A note for the person who fills in the supporter statement box (AA Q56 / DLA Q38). Prompts only: never wording."""
    code={"aa":"AA1","dla":"DLA1A"}[form]
    p=_Sheet(f"{code}: a note for {who}",claimant); p.add_page(); p.set_font("D","",11)
    paras=[f"Thank you for helping. The {code} form has a box for someone who knows {claimant} well: {question}.",
           "Please write it yourself, in your own words. We have left it blank on purpose: it must be what you know, not what we wrote.",
           "It helps to say how you know them and for how long, how often you see them, and what you have seen yourself on a typical day and on a bad day."]
    if topics: paras.append("Things you may have seen help with (only write about what you have seen): "+", ".join(topics)+".")
    paras.append("Then add your name, address, phone number, profession or relationship, and sign and date it in the box on the form.")
    for t in paras: p.multi_cell(0,6,t,new_x="LMARGIN",new_y="NEXT"); p.ln(3)
    return bytes(p.output())

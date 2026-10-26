"""Printable extra sheets (PDF): continuation sheets for the official forms, and PIP extra-information sheets.
Each page carries the claimant's name, a space for the NI number, the form and question, and page numbers,
so DWP can match loose sheets to the claim."""
import os
from fpdf import FPDF
HERE=os.path.dirname(os.path.abspath(__file__)); FONTS=os.path.join(HERE,"fonts")
class _Sheet(FPDF):
    def __init__(self,title,name):
        super().__init__(format="A4"); self.t=title; self.n=name or ""
        self.add_font("D","",os.path.join(FONTS,"DejaVuSans.ttf")); self.add_font("D","B",os.path.join(FONTS,"DejaVuSans-Bold.ttf"))
        self.set_auto_page_break(True,22); self.set_margins(18,16,18); self.alias_nb_pages()
    def header(self):
        self.set_font("D","B",12); self.cell(0,7,self.t,new_x="LMARGIN",new_y="NEXT")
        self.set_font("D","",10)
        self.cell(110,7,f"Full name: {self.n}" if self.n else "Full name: ____________________________________")
        self.cell(0,7,"NI number: ______________________",new_x="LMARGIN",new_y="NEXT")
        self.set_draw_color(0); self.line(18,self.get_y()+1,192,self.get_y()+1); self.ln(4)
    def footer(self):
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
    p=_Sheet(f"{form_code} ({version}) continuation sheet",name); p.add_page()
    p.set_font("D","",10); p.multi_cell(0,5,f"These answers did not fit in the boxes on the {form_code} form. Please send this sheet with the form. Write your NI number on every page.",new_x="LMARGIN",new_y="NEXT"); p.ln(4)
    for h,t in sections: p.section(h,t)
    p.ln(4); p.set_font("D","",10); p.cell(0,8,"Signature: ______________________________     Date: ____ / ____ / ________")
    return bytes(p.output())
def pip_sheets(name, items, form_code="PIP2"):
    """items: [(question heading, text)] -> PDF bytes, one question per page (long answers run onto more pages)."""
    p=_Sheet(f"{form_code}: extra information",name)
    for h,t in items:
        p.add_page(); p.section(h,t or "Not discussed. If this applies, add it in your own words.")
    return bytes(p.output())

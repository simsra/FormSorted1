"""Offline demo: run the fictional sample case through documents + AA1 filling (no server, no keys)."""
import json, os
import documents, fill_pdf
s=json.load(open("sample_case.json")); os.makedirs("out/sample",exist_ok=True)
open("out/sample/answers.html","w").write(documents.pack_html("FormSorted",s["personal"],s["draft"],"79",s["filled_by"]))
v=fill_pdf.fill(s["personal"],s["draft"],"out/sample/AA1-filled.pdf"); print("filled",len(v),"fields -> out/sample/")

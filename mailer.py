"""Pluggable mail sender. MAIL_BACKEND = console (default, test mode) | smtp | resend.
console: prints and appends to MAIL_LOG (default data/mail.log). Nothing leaves the machine.
smtp:    SMTP_HOST, SMTP_PORT (587), SMTP_USER, SMTP_PASS, MAIL_FROM.  resend: RESEND_API_KEY, MAIL_FROM."""
import os, json, smtplib, ssl, urllib.request, time
from email.message import EmailMessage
HERE=os.path.dirname(os.path.abspath(__file__))
def _from(): return os.getenv("MAIL_FROM","FormSorted <hello@formsorted.com>")
def send(to, subject, text):
    b=os.getenv("MAIL_BACKEND","console").lower()
    if b=="smtp":
        m=EmailMessage(); m["From"]=_from(); m["To"]=to; m["Subject"]=subject; m.set_content(text)
        with smtplib.SMTP(os.environ["SMTP_HOST"],int(os.getenv("SMTP_PORT","587")),timeout=30) as s:
            s.starttls(context=ssl.create_default_context()); s.login(os.environ["SMTP_USER"],os.environ["SMTP_PASS"]); s.send_message(m)
        return "smtp"
    if b=="resend":
        r=urllib.request.Request("https://api.resend.com/emails",json.dumps({"from":_from(),"to":[to],"subject":subject,"text":text}).encode(),
            {"Authorization":"Bearer "+os.environ["RESEND_API_KEY"],"Content-Type":"application/json","User-Agent":"FormSorted/1.0 (+https://formsorted.com)"})
        urllib.request.urlopen(r,timeout=30).read(); return "resend"
    log=os.getenv("MAIL_LOG",os.path.join(HERE,"data","mail.log")); os.makedirs(os.path.dirname(log),exist_ok=True)
    with open(log,"a") as f: f.write(json.dumps({"at":time.time(),"to":to,"subject":subject,"text":text})+"\n")
    print(f"[mail:console] to={to} subject={subject}"); return "console"

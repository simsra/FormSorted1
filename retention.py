"""Scheduled deletion job. Cron (daily 03:00):  0 3 * * * cd /app && python retention.py
Delete one customer on request:  python retention.py --email someone@example.com   (or --token TOKEN)"""
import sys, app, orders
c=app.db()
if len(sys.argv)>2 and sys.argv[1] in("--email","--token"):
    col="email" if sys.argv[1]=="--email" else "token"
    toks=[r[0] for r in c.execute(f"select token from orders where {col}=?",(sys.argv[2],))]
    for t in toks: orders.erase(c,app.OUT,t)
    print("erased",len(toks))
else: print("purged",orders.purge(c,app.OUT))

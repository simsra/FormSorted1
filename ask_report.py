"""Most common 'Ask a question?' questions, for new FAQs. Uses the same database as the app (DATABASE_URL or SQLITE_PATH).
    python3 ask_report.py [days=30]"""
import sys, ask, store
t=ask.top(store.connect(),days=int(sys.argv[1]) if len(sys.argv)>1 else 30)
print(f"{t['total']} questions", t["status"]); print("Topics:", ", ".join(f"{k} {v}" for k,v in t["topics"]))
for g in t["questions"]: print(f"{g['n']:>4}  [{g['topic']}] {g['q']}  ({', '.join(f'{k} {v}' for k,v in g['status'].items())})")

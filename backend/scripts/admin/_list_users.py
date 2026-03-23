import sqlite3, os

DB = os.path.join(os.path.dirname(__file__), 'backend', 'data', 'local_users.db')
conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row
cur = conn.cursor()
cur.execute("SELECT email, activation_credits, activation_credits_used FROM users ORDER BY created_at DESC")
rows = cur.fetchall()
if not rows:
    print("Nenhum usuário encontrado.")
for r in rows:
    remaining = (r['activation_credits'] or 0) - (r['activation_credits_used'] or 0)
    print(f"Email: {r['email']} | Credits: {r['activation_credits']} | Used: {r['activation_credits_used']} | Remaining: {remaining}")
conn.close()

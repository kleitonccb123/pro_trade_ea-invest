"""Atribui plano black ao usuario kleitonbritocosta@gmail.com"""
import sqlite3, json, os

TARGET_EMAIL = "kleitonbritocosta@gmail.com"
TARGET_PLAN  = "black"

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "backend", "data", "local_users.db")
print(f"DB path: {DB_PATH}")
print(f"Exists: {os.path.exists(DB_PATH)}")

conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

# List tables
cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [r[0] for r in cur.fetchall()]
print("Tables:", tables)

# Show user columns
cur.execute("PRAGMA table_info(users)")
cols = [(r[1], r[2]) for r in cur.fetchall()]
print("User columns:", cols)

# Find user
cur.execute("SELECT * FROM users WHERE email = ?", (TARGET_EMAIL,))
user = cur.fetchone()
if not user:
    print(f"❌ Usuário {TARGET_EMAIL} não encontrado!")
    conn.close()
    exit(1)

print(f"\n✅ Usuário encontrado: {dict(user)}")

# Determine the plan column name
col_names = [c[0] for c in cols]
plan_col = None
for candidate in ["plan", "subscription_plan", "subscription", "tier", "account_type", "role_plan"]:
    if candidate in col_names:
        plan_col = candidate
        break

if not plan_col:
    print("\n⚠️  Coluna 'plan' não existe — adicionando...")
    cur.execute("ALTER TABLE users ADD COLUMN plan TEXT DEFAULT 'starter'")
    conn.commit()
    plan_col = "plan"
    print("   Coluna 'plan' adicionada.")

print(f"\nAtualizando coluna '{plan_col}' → '{TARGET_PLAN}'")
cur.execute(f"UPDATE users SET {plan_col} = ? WHERE email = ?", (TARGET_PLAN, TARGET_EMAIL))
conn.commit()
# Verify
cur.execute(f"SELECT id, email, {plan_col} FROM users WHERE email = ?", (TARGET_EMAIL,))
row = cur.fetchone()
print(f"✅ Sucesso! {dict(row)}")

conn.close()

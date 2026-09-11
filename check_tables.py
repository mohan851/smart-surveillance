"""Quick verification script - lists tables on Supabase."""
from database.db import engine
from sqlalchemy import text

with engine.connect() as conn:
    rows = conn.execute(text(
        "SELECT table_name FROM information_schema.tables "
        "WHERE table_schema='public' ORDER BY table_name"
    )).fetchall()
    print("Tables in Supabase:")
    for r in rows:
        print(" -", r[0])

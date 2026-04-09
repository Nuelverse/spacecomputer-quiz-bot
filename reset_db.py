# reset_db.py
# Run this before testing to wipe all scores and question history.
# Usage: python reset_db.py

import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "quiz_data.db")

if not os.path.exists(DB_PATH):
    print("No database found — nothing to reset.")
else:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM asked_questions")
    cursor.execute("DELETE FROM all_time_scores")
    cursor.execute("DELETE FROM sqlite_sequence WHERE name IN ('asked_questions', 'all_time_scores')")
    conn.commit()

    q_count = cursor.execute("SELECT COUNT(*) FROM asked_questions").fetchone()[0]
    s_count = cursor.execute("SELECT COUNT(*) FROM all_time_scores").fetchone()[0]
    conn.close()

    print(f"✅ Database reset complete.")
    print(f"   asked_questions : {q_count} rows")
    print(f"   all_time_scores : {s_count} rows")

# database.py
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "quiz_data.db")


def init_db():
    """Create the database and tables if they don't exist."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS asked_questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            question TEXT NOT NULL UNIQUE,
            topic TEXT,
            asked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS all_time_scores (
            user_id INTEGER PRIMARY KEY,
            username TEXT NOT NULL,
            total_points INTEGER DEFAULT 0,
            correct_answers INTEGER DEFAULT 0,
            total_attempted INTEGER DEFAULT 0,
            rounds_played INTEGER DEFAULT 0,
            wins INTEGER DEFAULT 0,
            last_played TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()
    print(f"[DB] Database ready at {DB_PATH}")


def save_questions(questions: list, topic: str):
    """Save a list of question texts to the database."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    saved = 0
    for q in questions:
        try:
            cursor.execute(
                "INSERT OR IGNORE INTO asked_questions (question, topic) VALUES (?, ?)",
                (q["question"], topic)
            )
            if cursor.rowcount > 0:
                saved += 1
        except Exception as e:
            print(f"[DB] Error saving question: {e}")
    conn.commit()
    conn.close()
    print(f"[DB] Saved {saved} new questions to database")


def get_asked_questions() -> list:
    """Retrieve all previously asked question texts."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT question FROM asked_questions ORDER BY asked_at DESC")
    rows = cursor.fetchall()
    conn.close()
    return [row[0] for row in rows]


def get_question_count() -> int:
    """Return total number of questions in the database."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM asked_questions")
    count = cursor.fetchone()[0]
    conn.close()
    return count


def update_all_time_scores(scores: dict, winner_ids: set):
    """Upsert cumulative player scores after a completed round."""
    if not scores:
        return
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    for player in scores.values():
        is_winner = 1 if player.user_id in winner_ids else 0
        cursor.execute('''
            INSERT INTO all_time_scores
                (user_id, username, total_points, correct_answers, total_attempted, rounds_played, wins)
            VALUES (?, ?, ?, ?, ?, 1, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                username        = excluded.username,
                total_points    = total_points    + excluded.total_points,
                correct_answers = correct_answers + excluded.correct_answers,
                total_attempted = total_attempted + excluded.total_attempted,
                rounds_played   = rounds_played   + 1,
                wins            = wins            + excluded.wins,
                last_played     = CURRENT_TIMESTAMP
        ''', (
            player.user_id,
            player.username,
            int(player.points),
            player.correct,
            player.attempted,
            is_winner,
        ))
    conn.commit()
    conn.close()
    print(f"[DB] Updated all-time scores for {len(scores)} players")


def get_all_time_leaderboard(limit: int = 10) -> list:
    """Return top players by cumulative points. Each row: (username, total_points, correct_answers, total_attempted, rounds_played, wins)."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT username, total_points, correct_answers, total_attempted, rounds_played, wins
        FROM all_time_scores
        ORDER BY total_points DESC, correct_answers DESC
        LIMIT ?
    ''', (limit,))
    rows = cursor.fetchall()
    conn.close()
    return rows


def get_player_stats(user_id: int) -> dict | None:
    """Return all-time stats for one player, including their rank. None if not found."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        'SELECT username, total_points, correct_answers, total_attempted, rounds_played, wins '
        'FROM all_time_scores WHERE user_id = ?',
        (user_id,)
    )
    row = cursor.fetchone()
    if not row:
        conn.close()
        return None
    cursor.execute(
        'SELECT COUNT(*) + 1 FROM all_time_scores WHERE total_points > ?',
        (row[1],)
    )
    rank = cursor.fetchone()[0]
    conn.close()
    return {
        "username": row[0],
        "total_points": row[1],
        "correct_answers": row[2],
        "total_attempted": row[3],
        "rounds_played": row[4],
        "wins": row[5],
        "rank": rank,
    }

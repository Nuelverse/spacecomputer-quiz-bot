# stress_test.py
# Simulates multiple quiz rounds with 20 users of varying skill levels.
# Tests: scoring, rank arrows, tie-breaking, multi-round accumulation, edge cases.
# No Telegram needed — pure logic test.

import random
import sys
import os

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config
from quiz import QuizSession

# ─────────────────────────────────────────────
# FAKE USERS — with skill profiles
# ─────────────────────────────────────────────

# (user_id, username, correct_rate, speed_range)
# correct_rate: probability of answering correctly
# speed_range: (min_seconds, max_seconds) to answer
FAKE_USERS = [
    # Experts — high accuracy, fast
    (1001, "SatoshiKing",    0.95, (1.0, 5.0)),
    (1002, "Nuelverse",      0.90, (1.5, 6.0)),
    (1003, "OrbitalDev",     0.85, (2.0, 8.0)),
    (1004, "CryptoNerd",     0.80, (2.0, 9.0)),
    # Average — moderate accuracy and speed
    (1005, "SpaceFan",       0.65, (5.0, 18.0)),
    (1006, "CosmicRay",      0.60, (6.0, 20.0)),
    (1007, "BlockWizard",    0.60, (5.0, 17.0)),
    (1008, "DeFiGuru",       0.55, (7.0, 22.0)),
    (1009, "MoonShot",       0.55, (8.0, 21.0)),
    (1010, "ZeroGravity",    0.50, (6.0, 19.0)),
    # Novice — low accuracy, slow
    (1011, "NeutronStar",    0.35, (12.0, 27.0)),
    (1012, "Pulsar99",       0.30, (15.0, 28.0)),
    (1013, "GalacticBob",    0.30, (14.0, 26.0)),
    (1014, "QuantumLeap",    0.25, (16.0, 29.0)),
    (1015, "AstroNaut",      0.25, (18.0, 29.0)),
    # Lurkers — participate ~30% of the time
    (1016, "StarDust",       0.50, (5.0, 25.0)),
    (1017, "VoidWalker",     0.45, (8.0, 25.0)),
    (1018, "DarkMatter",     0.40, (10.0, 27.0)),
    (1019, "EventHorizon",   0.35, (12.0, 28.0)),
    (1020, "NebulaKing",     0.30, (15.0, 29.0)),
]

PARTICIPATION_RATES = {
    uid: 0.95 if uid <= 1004 else (0.85 if uid <= 1010 else (0.85 if uid <= 1015 else 0.30))
    for uid, *_ in FAKE_USERS
}

# ─────────────────────────────────────────────
# FAKE QUESTIONS — varied topics and answers
# ─────────────────────────────────────────────

QUESTION_BANK = [
    {
        "question": "What does cTRNG stand for?",
        "options": {"A": "Cosmic True Random Number Generator", "B": "Crypto Token RNG", "C": "Cloud Transaction Registry Node Gateway", "D": "Cipher Token RNG"},
        "answer": "A",
        "explanation": "cTRNG = Cosmic True Random Number Generator — entropy sourced from cosmic radiation."
    },
    {
        "question": "Where does SpaceComputer's cTRNG source its entropy?",
        "options": {"A": "Mouse movement", "B": "CPU thermal noise", "C": "Cosmic radiation via satellite", "D": "Blockchain block hashes"},
        "answer": "C",
        "explanation": "Entropy comes from cosmic radiation measured by SpaceComputer's orbital satellites."
    },
    {
        "question": "What does KMS stand for in SpaceComputer's stack?",
        "options": {"A": "Key Management Service", "B": "Kernel Memory System", "C": "Kinetic Mesh Satellite", "D": "Knowledge Management Suite"},
        "answer": "A",
        "explanation": "KMS = Key Management Service — manages cryptographic keys in a tamper-proof orbital environment."
    },
    {
        "question": "What is OrbitPort?",
        "options": {"A": "A rocket launch pad", "B": "SpaceComputer's API gateway for orbital services", "C": "A blockchain explorer", "D": "A satellite manufacturer"},
        "answer": "B",
        "explanation": "OrbitPort is SpaceComputer's gateway that exposes orbital computing services to developers."
    },
    {
        "question": "What property of SpaceComputer's cTRNG makes it verifiable?",
        "options": {"A": "It is open source", "B": "Results are published on-chain / via IPFS beacon", "C": "Anyone can audit the satellite hardware", "D": "It uses a public seed"},
        "answer": "B",
        "explanation": "cTRNG outputs are published to an IPFS beacon, making each cosmic draw publicly verifiable."
    },
    {
        "question": "What consensus layer does SpaceComputer integrate with for data availability?",
        "options": {"A": "Solana", "B": "Polkadot", "C": "EigenCloud", "D": "Avalanche"},
        "answer": "C",
        "explanation": "SpaceComputer partnered with EigenCloud for data availability in the orbital world computer."
    },
    {
        "question": "What advantage do orbital TEEs have over cloud-based TEEs?",
        "options": {"A": "Lower latency", "B": "Physical tamper-resistance outside any jurisdiction", "C": "Cheaper to operate", "D": "Easier to scale"},
        "answer": "B",
        "explanation": "Satellites orbit above any national jurisdiction, making physical tampering essentially impossible."
    },
    {
        "question": "What is SpaceComputer's primary value proposition?",
        "options": {"A": "Fastest blockchain", "B": "Cheapest cloud storage", "C": "Trusted execution in orbit with verifiable randomness", "D": "Decentralised social network"},
        "answer": "C",
        "explanation": "SpaceComputer delivers trusted execution environments and verifiable randomness from orbital hardware."
    },
]


def pick_questions(rng: random.Random, count: int) -> list:
    pool = rng.sample(QUESTION_BANK, min(count, len(QUESTION_BANK)))
    if count > len(QUESTION_BANK):
        pool += rng.choices(QUESTION_BANK, k=count - len(QUESTION_BANK))
    return pool


# ─────────────────────────────────────────────
# DISPLAY HELPERS
# ─────────────────────────────────────────────

SEP  = "─" * 48
SEP2 = "═" * 48


def rank_arrow(player, new_rank: int) -> str:
    if player.previous_rank is None:
        return ""
    if new_rank < player.previous_rank:
        return " 🔼"
    elif new_rank > player.previous_rank:
        return " 🔽"
    return ""


def print_mini_leaderboard(session: QuizSession, q_index: int, total: int):
    lb = session.get_leaderboard()
    medals = ["🥇", "🥈", "🥉"]
    print(f"\n  {'─'*40}")
    print(f"  ⏰  Time's up — Q{q_index}/{total}")
    if not lb:
        print("  No scores yet\n")
        return
    for i, p in enumerate(lb[:10]):
        medal = medals[i] if i < 3 else f"{i+1}."
        print(f"  {medal} @{p.username} — {int(p.points)}pts{rank_arrow(p, i+1)}")
    if len(lb) > 10:
        print(f"  ┄┄┄")
        for i, p in enumerate(lb[10:], start=11):
            print(f"  {i}. @{p.username} — {int(p.points)}pts{rank_arrow(p, i)}")
    print()


def print_final_results(session: QuizSession, round_num: int, all_time: dict):
    lb = session.get_leaderboard()
    medals = ["🥇", "🥈", "🥉"]
    winners = session.get_winners()

    print(f"\n{SEP2}")
    print(f"🏁  ROUND {round_num} COMPLETE")
    print(f"{SEP2}")

    if not lb:
        print("  No participants this round.\n")
        return

    if len(winners) == 1:
        w = winners[0]
        print(f"🏆 Winner: @{w.username} — {int(w.points)}pts | {w.correct}/{session.questions_played} correct")
    else:
        print(f"🤝 TIE between: {', '.join(f'@{w.username}' for w in winners)} — cosmic tiebreak needed")

    print(f"\n  {'Player':<18} {'Pts':>6}  {'Correct':>8}  {'Accuracy':>9}  {'All-Time':>9}")
    print(f"  {'─'*18} {'─'*6}  {'─'*8}  {'─'*9}  {'─'*9}")
    for i, p in enumerate(lb):
        medal = medals[i] if i < 3 else f"  {i+1}."
        acc = f"{round(p.correct / p.attempted * 100)}%" if p.attempted else "—"
        at = all_time.get(p.user_id, 0)
        print(f"  {medal} @{p.username:<15} {int(p.points):>6}  {p.correct:>4}/{session.questions_played:<3}  {acc:>9}  {at:>9}")
    print()


def print_all_time(all_time: dict, rounds: int):
    sorted_at = sorted(all_time.items(), key=lambda x: -x[1])
    medals = ["🥇", "🥈", "🥉"]
    print(f"\n{SEP2}")
    print(f"🌟  ALL-TIME STANDINGS after {rounds} rounds")
    print(f"{SEP2}")
    user_map = {uid: name for uid, name, *_ in FAKE_USERS}
    for i, (uid, pts) in enumerate(sorted_at[:10]):
        medal = medals[i] if i < 3 else f"{i+1}."
        print(f"  {medal} @{user_map.get(uid, str(uid))} — {pts} pts total")
    print()


# ─────────────────────────────────────────────
# SCORING ASSERTIONS
# ─────────────────────────────────────────────

def assert_score_integrity(session: QuizSession):
    """Validate that every player's points are non-negative and correct ≤ attempted."""
    errors = []
    for p in session.scores.values():
        if p.points < 0:
            errors.append(f"@{p.username} has negative points: {p.points}")
        if p.correct > p.attempted:
            errors.append(f"@{p.username} correct ({p.correct}) > attempted ({p.attempted})")
        if p.attempted > len(session.questions):
            errors.append(f"@{p.username} attempted ({p.attempted}) > total questions ({len(session.questions)})")
    if errors:
        print(f"  ⚠️  ASSERTION FAILURES:")
        for e in errors:
            print(f"     • {e}")
    else:
        print(f"  ✅  Score integrity OK — all {len(session.scores)} players validated")


# ─────────────────────────────────────────────
# EDGE CASE: EMPTY ROUND
# ─────────────────────────────────────────────

def run_empty_round():
    print(f"\n{SEP}")
    print(f"🧪  EDGE CASE: Zero-participation round")
    print(f"{SEP}")
    rng = random.Random(0)
    questions = pick_questions(rng, config.QUESTIONS_PER_ROUND)
    session = QuizSession(
        chat_id=888888,
        questions=questions,
        cosmic_seed=0,
        cosmic_source="edge case test",
        topic="general"
    )
    for _ in range(len(questions)):
        session.advance()

    winners = session.get_winners()
    assert winners == [], f"Expected no winners, got {winners}"
    print(f"  ✅  No winners declared for empty round — correct")
    print(f"  ✅  get_leaderboard() returned {len(session.get_leaderboard())} players — correct\n")


# ─────────────────────────────────────────────
# EDGE CASE: FORCED TIE
# ─────────────────────────────────────────────

def run_tie_round():
    print(f"{SEP}")
    print(f"🧪  EDGE CASE: Forced tie between two players")
    print(f"{SEP}")
    rng = random.Random(77)
    questions = pick_questions(rng, 2)
    session = QuizSession(
        chat_id=777777,
        questions=questions,
        cosmic_seed=77,
        cosmic_source="tie test",
        topic="cTRNG"
    )

    for q_i in range(2):
        q = session.current_question()
        session.snapshot_ranks()
        # Both users answer correctly at the same time
        session.record_answer(1001, "SatoshiKing", q["answer"], 5.0, config.BASE_POINTS, config.QUESTION_TIMER)
        session.record_answer(1002, "Nuelverse",   q["answer"], 5.0, config.BASE_POINTS, config.QUESTION_TIMER)
        session.advance()

    winners = session.get_winners()
    assert len(winners) == 2, f"Expected 2 tied winners, got {len(winners)}"
    pts = [int(w.points) for w in winners]
    assert pts[0] == pts[1], f"Tied winners have different points: {pts}"
    print(f"  ✅  Tie detected correctly — {len(winners)} winners with {pts[0]}pts each")
    print(f"  ✅  Cosmic tiebreak would now apply in production\n")


# ─────────────────────────────────────────────
# MAIN SIMULATION
# ─────────────────────────────────────────────

def run_simulation(num_rounds: int = 3, questions_per_round: int = None):
    count = questions_per_round or config.QUESTIONS_PER_ROUND

    print(f"\n{SEP2}")
    print(f"🛰️   STRESS TEST — {len(FAKE_USERS)} USERS | {num_rounds} ROUNDS | {count} Q/ROUND")
    print(f"   Base: {config.BASE_POINTS}pts | Timer: {config.QUESTION_TIMER}s | Min: 1pt")
    print(f"{SEP2}\n")

    all_time: dict[int, int] = {}  # user_id -> cumulative points

    for round_num in range(1, num_rounds + 1):
        rng = random.Random(round_num * 1000)
        questions = pick_questions(rng, count)

        print(f"\n{SEP}")
        print(f"🚀  ROUND {round_num} | Topic: {questions[0]['question'][:35]}...")
        print(f"{SEP}")

        session = QuizSession(
            chat_id=999999,
            questions=questions,
            cosmic_seed=round_num * 1000,
            cosmic_source=f"stress test round {round_num}",
            topic="SpaceComputer"
        )

        for q_index in range(1, count + 1):
            q = session.current_question()
            print(f"\n  📌 Q{q_index}: {q['question'][:60]}")
            print(f"     Answer: {q['answer']}. {q['options'][q['answer']][:40]}")

            session.snapshot_ranks()

            # Each user decides whether to participate this round
            answering = [
                (uid, name, cr, sr)
                for uid, name, cr, sr in FAKE_USERS
                if rng.random() < PARTICIPATION_RATES[uid]
            ]
            # Sort by randomised answer time (simulates real-time answering)
            answering = sorted(answering, key=lambda u: rng.uniform(*u[3]))

            for uid, name, correct_rate, speed_range in answering:
                time_taken = round(rng.uniform(*speed_range), 1)
                answer = q["answer"] if rng.random() < correct_rate else rng.choice(
                    [k for k in q["options"] if k != q["answer"]]
                )
                is_correct, pts = session.record_answer(
                    uid, name, answer, time_taken, config.BASE_POINTS, config.QUESTION_TIMER
                )
                status = f"✅ +{pts}pts ({time_taken}s)" if is_correct else f"❌ ({time_taken}s)"
                print(f"     @{name:<16} {status}")

            print_mini_leaderboard(session, q_index, count)
            session.advance()

        # Accumulate all-time scores
        for p in session.scores.values():
            all_time[p.user_id] = all_time.get(p.user_id, 0) + int(p.points)

        assert_score_integrity(session)
        print_final_results(session, round_num, all_time)

    print_all_time(all_time, num_rounds)


# ─────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────

if __name__ == "__main__":
    run_empty_round()
    run_tie_round()
    run_simulation(num_rounds=3)

# quiz.py
import time
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class PlayerScore:
    user_id: int
    username: str
    points: float = 0.0
    correct: int = 0
    attempted: int = 0
    total_time: float = 0.0
    previous_rank: Optional[int] = None  # rank before this question


@dataclass
class QuizSession:
    chat_id: int
    questions: list 
    cosmic_seed: int
    cosmic_source: str
    topic: str
    current_index: int = 0
    scores: dict = field(default_factory=dict)
    active: bool = True
    current_question_message_id: Optional[int] = None
    answered_this_round: set = field(default_factory=set)
    round_results: dict = field(default_factory=dict)
    question_start_time: float = field(default_factory=time.time)
    timer_task: Any = field(default=None)
    bot_message_ids: list = field(default_factory=list)

    @property
    def questions_played(self) -> int:
        """Questions presented so far (including any in-progress question)."""
        return min(self.current_index + 1, len(self.questions))

    def current_question(self) -> Optional[dict]:
        if self.current_index < len(self.questions):
            return self.questions[self.current_index]
        return None

    def is_finished(self) -> bool:
        return self.current_index >= len(self.questions)

    def snapshot_ranks(self):
        """Save current ranks before this question's results are applied."""
        board = self.get_leaderboard()
        for i, player in enumerate(board):
            player.previous_rank = i + 1

    def record_answer(self, user_id: int, username: str, answer: str, time_taken: float, base_points: int, timer: int) -> tuple[bool, int]:
        if user_id in self.answered_this_round:
            return False, 0

        self.answered_this_round.add(user_id)

        if user_id not in self.scores:
            self.scores[user_id] = PlayerScore(user_id=user_id, username=username)

        q = self.current_question()
        is_correct = answer.upper() == q["answer"].upper()

        self.scores[user_id].attempted += 1

        points_earned = 0
        if is_correct:
            time_remaining = max(0, timer - time_taken)
            points_earned = round(base_points * (time_remaining / timer))
            points_earned = max(points_earned, 1)
            self.scores[user_id].correct += 1
            self.scores[user_id].points += points_earned
            self.scores[user_id].total_time += time_taken

        self.round_results[user_id] = {
            "username": username,
            "correct": is_correct,
            "points_earned": points_earned,
            "time_taken": round(time_taken, 1)
        }

        return is_correct, points_earned

    def advance(self):
        self.current_index += 1
        self.answered_this_round = set()
        self.round_results = {}

    def get_leaderboard(self) -> list:
        return sorted(
            self.scores.values(),
            key=lambda p: (-p.points, p.total_time)
        )

    def get_winners(self) -> list:
        board = self.get_leaderboard()
        if not board:
            return []
        top_points = board[0].points
        return [p for p in board if p.points == top_points]

    def get_player_rank(self, user_id: int) -> Optional[int]:
        board = self.get_leaderboard()
        for i, player in enumerate(board):
            if player.user_id == user_id:
                return i + 1
        return None
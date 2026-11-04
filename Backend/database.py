from datetime import datetime
from models import db, User, TrainingSession, Attempt, UserProgress, AIState


class UserDataStore:

    def __init__(self, user_id: int):
        self.user_id = user_id


    def get_history(self) -> list:
        rows = (
            Attempt.query
            .filter_by(user_id=self.user_id)
            .order_by(Attempt.timestamp)
            .all()
        )
        return [
            {
                "target":           a.target_interval,
                "guess":            a.user_answer,
                "error":            a.error,
                "response_time_ms": a.response_time_ms,
            }
            for a in rows
        ]

    def get_session_timeline(self, session_id: int) -> list:
        rows = (
            Attempt.query
            .filter_by(user_id=self.user_id, session_id=session_id)
            .order_by(Attempt.timestamp)
            .all()
        )
        return [
            {
                "attempt_label": f"Attempt {i + 1}",
                "correct_val":   1 if a.is_correct else 0,
                "incorrect_val": 0 if a.is_correct else 1,
            }
            for i, a in enumerate(rows)
        ]

    def log_interaction(
        self,
        session_id: int,
        target: int,
        guess: int,
        error: int,
        response_time: int,
        is_correct: bool,
    ):
        attempt = Attempt(
            session_id=session_id,
            user_id=self.user_id,
            target_interval=int(target) % 12,
            user_answer=int(guess) % 12,
            error=int(error),
            is_correct=is_correct,
            response_time_ms=int(response_time),
        )
        db.session.add(attempt)

        prog = UserProgress.query.filter_by(
            user_id=self.user_id,
            interval_semitone=int(target) % 12,
        ).first()
        if prog is None:
            prog = UserProgress(
                user_id=self.user_id,
                interval_semitone=int(target) % 12,
                total_attempts=0,
                correct_count=0,
                miss_count=0,
            )
            db.session.add(prog)

        prog.total_attempts = (prog.total_attempts or 0) + 1
        if is_correct:
            prog.correct_count = (prog.correct_count or 0) + 1
        else:
            prog.miss_count = (prog.miss_count or 0) + 1

        db.session.commit()


    def get_difficulty(self) -> int:
        user = db.session.get(User, self.user_id)
        return user.current_difficulty if user else 1

    def set_difficulty(self, lvl: int):
        user = db.session.get(User, self.user_id)
        if user:
            user.current_difficulty = max(1, min(3, int(lvl)))
            db.session.commit()

    def get_promotion_marker(self) -> int:
        user = db.session.get(User, self.user_id)
        return (user.attempts_at_last_level_change or 0) if user else 0

    def set_promotion_marker(self, history_len: int):
        user = db.session.get(User, self.user_id)
        if user:
            user.attempts_at_last_level_change = int(history_len)
            db.session.commit()


    def get_or_create_active_session(self) -> int:
        session = TrainingSession.query.filter_by(
            user_id=self.user_id, is_active=True
        ).first()
        if session is None:
            session = TrainingSession(
                user_id=self.user_id,
                difficulty_level=self.get_difficulty(),
            )
            db.session.add(session)
            db.session.commit()
        return session.id

    def end_active_session(self):
        session = TrainingSession.query.filter_by(
            user_id=self.user_id, is_active=True
        ).first()
        if session:
            session.is_active = False
            session.ended_at = datetime.utcnow()
            db.session.commit()


    def save_ai_state(self, state: str):
        ai = AIState.query.filter_by(user_id=self.user_id).first()
        if ai is None:
            ai = AIState(user_id=self.user_id)
            db.session.add(ai)
        ai.behavioral_state = state
        ai.last_updated = datetime.utcnow()
        db.session.commit()


    def get_attention_areas(self) -> list:
        rows = (
            UserProgress.query
            .filter(
                UserProgress.user_id == self.user_id,
                UserProgress.miss_count >= 2,
            )
            .order_by(UserProgress.miss_count.desc())
            .all()
        )
        return [
            {"semitone": p.interval_semitone, "count": p.miss_count}
            for p in rows
        ]


    def reset_all_data(self):
        Attempt.query.filter_by(user_id=self.user_id).delete()
        UserProgress.query.filter_by(user_id=self.user_id).delete()
        TrainingSession.query.filter_by(user_id=self.user_id).delete()
        AIState.query.filter_by(user_id=self.user_id).delete()

        user = db.session.get(User, self.user_id)
        if user:
            user.current_difficulty = 1
            user.attempts_at_last_level_change = 0

        db.session.commit()

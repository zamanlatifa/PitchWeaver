from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

INTERVAL_NAMES = {
    0:  "Perfect Unison",
    1:  "Minor 2nd",
    2:  "Major 2nd",
    3:  "Minor 3rd",
    4:  "Major 3rd",
    5:  "Perfect 4th",
    6:  "Tritone",
    7:  "Perfect 5th",
    8:  "Minor 6th",
    9:  "Major 6th",
    10: "Minor 7th",
    11: "Major 7th",
}


class User(db.Model):
    __tablename__ = "users"

    id               = db.Column(db.Integer, primary_key=True)
    email            = db.Column(db.String(255), unique=True, nullable=False, index=True)
    name             = db.Column(db.String(255), nullable=False)
    password_hash    = db.Column(db.String(255), nullable=False)
    created_at       = db.Column(db.DateTime, default=datetime.utcnow)
    avatar_url       = db.Column(db.String(500), nullable=True)
    current_difficulty = db.Column(db.Integer, default=1)
    attempts_at_last_level_change = db.Column(db.Integer, default=0)


class TrainingSession(db.Model):
    __tablename__ = "sessions"

    id               = db.Column(db.Integer, primary_key=True)
    user_id          = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    started_at       = db.Column(db.DateTime, default=datetime.utcnow)
    ended_at         = db.Column(db.DateTime, nullable=True)
    difficulty_level = db.Column(db.Integer, default=1)
    is_active        = db.Column(db.Boolean, default=True)


class Attempt(db.Model):
    __tablename__ = "attempts"

    id              = db.Column(db.Integer, primary_key=True)
    session_id      = db.Column(db.Integer, db.ForeignKey("sessions.id"), nullable=False)
    user_id         = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    target_interval = db.Column(db.Integer, nullable=False)
    user_answer     = db.Column(db.Integer, nullable=False)
    error           = db.Column(db.Integer, nullable=False)
    is_correct      = db.Column(db.Boolean, nullable=False)
    response_time_ms = db.Column(db.Integer, nullable=False)
    timestamp       = db.Column(db.DateTime, default=datetime.utcnow)


class UserProgress(db.Model):
    __tablename__ = "user_progress"

    id               = db.Column(db.Integer, primary_key=True)
    user_id          = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    interval_semitone = db.Column(db.Integer, nullable=False)
    total_attempts   = db.Column(db.Integer, default=0)
    correct_count    = db.Column(db.Integer, default=0)
    miss_count       = db.Column(db.Integer, default=0)

    __table_args__ = (
        db.UniqueConstraint("user_id", "interval_semitone", name="uq_user_interval"),
    )


class PasswordReset(db.Model):
    __tablename__ = "password_resets"

    id         = db.Column(db.Integer, primary_key=True)
    user_id    = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    code_hash  = db.Column(db.String(255), nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False)
    used       = db.Column(db.Boolean, default=False)
    attempts   = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class AIState(db.Model):
    __tablename__ = "ai_state"

    id               = db.Column(db.Integer, primary_key=True)
    user_id          = db.Column(db.Integer, db.ForeignKey("users.id"), unique=True, nullable=False)
    behavioral_state = db.Column(db.String(50), default="COLLECTING_DATA")
    last_updated     = db.Column(db.DateTime, default=datetime.utcnow)

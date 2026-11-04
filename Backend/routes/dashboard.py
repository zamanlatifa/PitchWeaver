from datetime import datetime

from flask import Blueprint, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity

from database import UserDataStore
from analytics.circular_stats import CircularStatistics
from models import INTERVAL_NAMES, UserProgress, User, AIState, db

dashboard_bp = Blueprint("dashboard", __name__)


@dashboard_bp.route("/api/dashboard/metrics", methods=["GET"])
@jwt_required()
def get_metrics():
    user_store = UserDataStore(int(get_jwt_identity()))
    history    = user_store.get_history()
    errors     = [h["error"] for h in history]

    bias, concentration = CircularStatistics.calculate_metrics(errors)

    readable_logs = [
        {
            "target":          INTERVAL_NAMES.get(h["target"], "Unknown"),
            "guess":           INTERVAL_NAMES.get(h["guess"],  "Unknown"),
            "error_semitones": h["error"],
            "latency_ms":      h["response_time_ms"],
        }
        for h in history[-5:]
    ]

    return jsonify({
        "circular_bias_semitones":     round(bias, 2),
        "concentration_r":             round(concentration, 2),
        "total_exercises_completed":   len(history),
        "recent_logs":                 readable_logs,
        "current_difficulty":          user_store.get_difficulty(),
    })


@dashboard_bp.route("/api/user/attention-areas", methods=["GET"])
@jwt_required()
def get_attention_areas():
    user_store = UserDataStore(int(get_jwt_identity()))
    raw = user_store.get_attention_areas()
    return jsonify([
        {
            "interval_name": INTERVAL_NAMES.get(item["semitone"], "Unknown"),
            "semitone":      item["semitone"],
            "miss_count":    item["count"],
        }
        for item in raw
    ])


@dashboard_bp.route("/api/user/report", methods=["GET"])
@jwt_required()
def get_report():
    user_id    = int(get_jwt_identity())
    user_store = UserDataStore(user_id)
    user       = db.session.get(User, user_id)
    history    = user_store.get_history()

    total    = len(history)
    correct  = sum(1 for h in history if h["error"] == 0)
    accuracy = round(correct / total * 100, 1) if total else 0.0
    avg_rt   = round(sum(h["response_time_ms"] for h in history) / total) if total else 0

    errors  = [h["error"] for h in history]
    bias, _ = CircularStatistics.calculate_metrics(errors)

    ai_row   = AIState.query.filter_by(user_id=user_id).first()
    ai_state = ai_row.behavioral_state if ai_row else "COLLECTING_DATA"

    progress_rows = (
        UserProgress.query
        .filter_by(user_id=user_id)
        .order_by(UserProgress.interval_semitone)
        .all()
    )
    intervals = [
        {
            "interval": INTERVAL_NAMES.get(p.interval_semitone, "Unknown"),
            "semitone": p.interval_semitone,
            "total":    p.total_attempts,
            "correct":  p.correct_count,
            "misses":   p.miss_count,
            "accuracy": round(p.correct_count / p.total_attempts * 100, 1)
                        if p.total_attempts > 0 else 0,
        }
        for p in progress_rows
    ]

    WINDOW = 10
    trend  = []
    for i in range(total):
        window = history[max(0, i - WINDOW + 1): i + 1]
        acc    = sum(1 for h in window if h["error"] == 0) / len(window) * 100
        trend.append({"attempt": i + 1, "rolling_accuracy": round(acc, 1)})

    feedback = _build_feedback(total, accuracy, avg_rt, bias, intervals, history)

    return jsonify({
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "user_name":    user.name if user else "Student",
        "overall": {
            "total_attempts":   total,
            "correct":          correct,
            "accuracy":         accuracy,
            "avg_response_ms":  avg_rt,
            "difficulty_level": user_store.get_difficulty(),
            "ai_state":         ai_state,
            "bias_semitones":   round(bias, 2),
        },
        "intervals": intervals,
        "trend":     trend,
        "feedback":  feedback,
    })


def _build_feedback(total, accuracy, avg_rt, bias, intervals, history):
    if total == 0:
        return {
            "headline": "Nothing here yet",
            "points":   ["Play a few rounds on the Practice page and your tips will appear here."],
        }

    points = []

    if accuracy >= 85:
        headline = "Excellent ear! You are doing really well."
    elif accuracy >= 70:
        headline = "Great progress. Your practice is paying off."
    elif accuracy >= 50:
        headline = "You are getting there. Keep practising regularly."
    else:
        headline = "It is early days. Short, regular practice will help the most."

    if total >= 8:
        half   = total // 2
        first  = sum(1 for h in history[:half] if h["error"] == 0) / half * 100
        second = sum(1 for h in history[half:] if h["error"] == 0) / (total - half) * 100
        delta  = second - first
        if delta >= 10:
            points.append(f"You are improving! Your score went up from {first:.0f}% to {second:.0f}%.")
        elif delta <= -10:
            points.append(f"Your score dropped from {first:.0f}% to {second:.0f}% recently. Try shorter sessions or easier intervals.")
        else:
            points.append(f"Your score has stayed steady at about {accuracy:.0f}%. Nice and consistent.")

    judged     = [i for i in intervals if i["total"] >= 3]
    strengths  = sorted([i for i in judged if i["accuracy"] >= 75], key=lambda x: -x["accuracy"])[:3]
    weaknesses = sorted([i for i in judged if i["accuracy"] < 50],  key=lambda x: x["accuracy"])[:3]
    if strengths:
        points.append("You are best at " + ", ".join(f"{s['interval']} ({s['accuracy']:.0f}%)" for s in strengths) + ".")
    if weaknesses:
        points.append("Practise these next: " + ", ".join(f"{w['interval']} ({w['accuracy']:.0f}%)" for w in weaknesses) + ".")

    if avg_rt and avg_rt < 3000:
        points.append(f"You answer quickly, in about {avg_rt/1000:.1f} seconds on average.")
    elif avg_rt and avg_rt > 6000:
        points.append(f"You take about {avg_rt/1000:.1f} seconds per answer. Try trusting your first instinct.")

    if abs(bias) >= 0.5:
        direction = "wide" if bias > 0 else "narrow"
        points.append(f"You often pick intervals that are a little too {direction}.")

    if not points:
        points.append("Keep practising and more tips will appear here.")

    return {"headline": headline, "points": points}


@dashboard_bp.route("/api/user/reset", methods=["POST"])
@jwt_required()
def reset_user_data():
    UserDataStore(int(get_jwt_identity())).reset_all_data()
    return jsonify({"status": "reset"})


@dashboard_bp.route("/api/user/progress", methods=["GET"])
@jwt_required()
def get_progress():
    user_id  = int(get_jwt_identity())
    progress = (
        UserProgress.query
        .filter_by(user_id=user_id)
        .order_by(UserProgress.interval_semitone)
        .all()
    )
    return jsonify([
        {
            "interval": INTERVAL_NAMES.get(p.interval_semitone, "Unknown"),
            "semitone": p.interval_semitone,
            "total":    p.total_attempts,
            "correct":  p.correct_count,
            "misses":   p.miss_count,
            "accuracy": round(p.correct_count / p.total_attempts * 100, 1)
                        if p.total_attempts > 0 else 0,
        }
        for p in progress
    ])

from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity

from database import UserDataStore
from audio.generator import AudioIntervalGenerator
from adaptive.engine import PitchWeaverAdaptiveEngine
from analytics.error_model import ErrorModel
from analytics.circular_stats import CircularStatistics
from ai.predictor import SequenceClassifier

training_bp = Blueprint("training", __name__)


@training_bp.route("/api/training/next", methods=["GET"])
@jwt_required()
def next_exercise():
    user_store = UserDataStore(int(get_jwt_identity()))

    target  = PitchWeaverAdaptiveEngine.get_next_target_interval(user_store)
    payload = AudioIntervalGenerator.get_frequency_pair(target)
    payload["difficulty_level"] = user_store.get_difficulty()

    return jsonify(payload)


@training_bp.route("/api/training/submit", methods=["POST"])
@jwt_required()
def submit_response():
    try:
        user_store = UserDataStore(int(get_jwt_identity()))

        data       = request.get_json() or {}
        user_guess = int(data.get("guess", 0))
        rt         = int(data.get("response_time_ms", 0))
        target     = int(data.get("target_interval", 0))

        error      = ErrorModel.parse_shortest_cyclic_error(user_guess, target)
        is_correct = (int(error) == 0)

        session_id = user_store.get_or_create_active_session()
        user_store.log_interaction(session_id, target, user_guess, error, rt, is_correct)

        history  = user_store.get_history()
        ai_state, ai_action = SequenceClassifier.classify_behavior(history)
        PitchWeaverAdaptiveEngine.update_pacing_strategy(ai_state, user_store)
        user_store.save_ai_state(ai_state)

        timeline        = user_store.get_session_timeline(session_id)
        frequent_errors = SequenceClassifier.get_frequent_errors(history)

        recent_frequent_errors = SequenceClassifier.get_frequent_errors(history[-10:])

        recent_errors = [h["error"] for h in history[-10:]]
        bias, concentration = CircularStatistics.calculate_metrics(recent_errors)
        recent_correct  = sum(1 for e in recent_errors if e == 0)
        recent_accuracy = recent_correct / len(recent_errors) if recent_errors else 0.0

        return jsonify({
            "status":                  "processed",
            "ai_state":                ai_state,
            "ai_action":               ai_action,
            "is_correct":              is_correct,
            "target_interval":         int(target),
            "frequent_errors":         frequent_errors,
            "recent_frequent_errors":  recent_frequent_errors,
            "timeline":                timeline,
            "circular_bias_semitones": round(bias, 2),
            "bias_concentration":      round(concentration, 2),
            "recent_accuracy":         round(recent_accuracy, 2),
            "total_attempts":          len(history),
            "difficulty_level":        user_store.get_difficulty(),
        })

    except Exception as exc:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(exc)}), 500


@training_bp.route("/api/session/end", methods=["POST"])
@jwt_required()
def end_session():
    UserDataStore(int(get_jwt_identity())).end_active_session()
    return jsonify({"status": "session ended"})

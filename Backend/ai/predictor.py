from analytics.circular_stats import CircularStatistics
from collections import Counter

class SequenceClassifier:
    @staticmethod
    def classify_behavior(history_logs):
        if len(history_logs) < 5:
            return "COLLECTING_DATA", "Keep going. I need a few more answers to get to know your ear."

        recent_window = history_logs[-10:]
        errors = [h["error"] for h in recent_window]
        rts = [h["response_time_ms"] for h in recent_window]

        correct_count = sum(1 for e in errors if e == 0)
        accuracy = correct_count / len(errors)

        bias, concentration = CircularStatistics.calculate_metrics(errors)

        if len(rts) >= 3 and rts[-1] > rts[-2] * 1.45 and concentration < 0.40:
            return "FATIGUE_DETECTED", "I'll give you easier intervals for a while."

        if concentration > 0.65 and abs(bias) >= 1.0:
            return "SYSTEMATIC_SWAP", f"You often pick an interval about {abs(round(bias))} semitone{'' if abs(round(bias)) == 1 else 's'} too {'wide' if bias > 0 else 'narrow'}. Listen closely to the gap between the notes."

        if concentration < 0.22 or accuracy < 0.40:
            return "RANDOM_GUESSING", "I'll go back to easier intervals to help you build confidence."

        if accuracy >= 0.70:
            return "STABLE_LEARNING", "Keep it up and you will move up a level soon."

        return "COLLECTING_DATA", "Keep going. I'm still learning how you hear."

    @staticmethod
    def get_frequent_errors(history_logs):
        incorrect_targets = [h["target"] for h in history_logs if h["error"] != 0]
        if not incorrect_targets:
            return []

        counts = Counter(incorrect_targets)

        error_tracking = []
        for target, count in counts.items():
            if count >= 2:
                error_tracking.append({
                    "semitone": target,
                    "count": count
                })

        error_tracking.sort(key=lambda x: x["count"], reverse=True)
        return error_tracking

import random


class PitchWeaverAdaptiveEngine:

    STREAK_WINDOW        = 10
    STREAK_REQUIRED      = 8
    SUSTAINED_WINDOW     = 15
    SUSTAINED_ACCURACY   = 0.85

    @classmethod
    def should_level_up(cls, history: list, attempts_at_last_level_change: int = 0) -> bool:
        window = history[attempts_at_last_level_change:]
        results = [1 if h["error"] == 0 else 0 for h in window]

        if len(results) >= cls.STREAK_WINDOW:
            recent = results[-cls.STREAK_WINDOW:]
            if sum(recent) >= cls.STREAK_REQUIRED:
                return True

        if len(results) >= cls.SUSTAINED_WINDOW:
            recent = results[-cls.SUSTAINED_WINDOW:]
            if (sum(recent) / len(recent)) > cls.SUSTAINED_ACCURACY:
                return True

        return False

    @classmethod
    def update_pacing_strategy(cls, ai_state: str, user_store) -> int:
        current_lvl = user_store.get_difficulty()
        history     = user_store.get_history()
        marker      = user_store.get_promotion_marker()

        if ai_state in ("FATIGUE_DETECTED", "RANDOM_GUESSING"):
            if current_lvl > 1:
                user_store.set_difficulty(current_lvl - 1)
                user_store.set_promotion_marker(len(history))

        elif ai_state == "STABLE_LEARNING" and current_lvl < 3:
            if cls.should_level_up(history, marker):
                user_store.set_difficulty(current_lvl + 1)
                user_store.set_promotion_marker(len(history))

        return user_store.get_difficulty()

    @staticmethod
    def get_next_target_interval(user_store) -> int:
        lvl     = max(1, min(3, user_store.get_difficulty()))
        history = user_store.get_history()

        if lvl == 1:
            pool = [0, 4, 7, 11]
        elif lvl == 2:
            pool = [0, 3, 4, 5, 6, 7, 9]
        else:
            pool = list(range(12))

        if not history:
            return random.choice(pool)

        last_target   = history[-1]["target"]
        filtered_pool = [i for i in pool if i != last_target]
        return random.choice(filtered_pool if filtered_pool else pool)

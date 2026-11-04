import numpy as np
from ai.dataset_generator import SyntheticDataEngine
from analytics.circular_stats import CircularStatistics

class LocalModelTrainer:
    @staticmethod
    def execute_cross_validation():
        profiles = ["FATIGUE", "SYSTEMATIC_SWAP", "STABLE"]
        results = {}

        for p in profiles:
            simulated_run = SyntheticDataEngine.generate_virtual_profile(p, length=10)
            errors = [x["error"] for x in simulated_run]
            bias, r = CircularStatistics.calculate_metrics(errors)
            results[p] = {"final_calculated_bias": round(bias, 2), "concentration_r": round(r, 2)}

        return results

if __name__ == "__main__":
    validation_metrics = LocalModelTrainer.execute_cross_validation()
    print("AI Pre-Training Cross-Validation Matrix Results:", validation_metrics)

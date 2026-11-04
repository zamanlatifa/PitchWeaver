import numpy as np


class CircularStatistics:

    @staticmethod
    def calculate_metrics(errors_semitones, num_semitones=12):

        if not errors_semitones:
            return 0.0, 0.0


        errors_rad = (np.array(errors_semitones) % num_semitones) * (2.0 * np.pi / num_semitones)


        sin_avg = np.mean(np.sin(errors_rad))
        cos_avg = np.mean(np.cos(errors_rad))


        bias_rad = np.arctan2(sin_avg, cos_avg)

        bias_semitone = (bias_rad * num_semitones / (2.0 * np.pi)) % num_semitones

        if bias_semitone > 6:
            bias_semitone -= 12


        r_magnitude = np.sqrt(sin_avg**2 + cos_avg**2)

        return float(bias_semitone), float(r_magnitude)

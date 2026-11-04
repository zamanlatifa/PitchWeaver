import numpy as np

class AudioIntervalGenerator:
    SEMITONE_RATIOS = {
        0: 1.0,
        1: 1.059463,
        2: 1.122462,
        3: 1.189207,
        4: 1.259921,
        5: 1.334840,
        6: 1.414214,
        7: 1.498307,
        8: 1.587401,
        9: 1.681793,
        10: 1.781797,
        11: 1.887749
    }

    @staticmethod
    def get_frequency_pair(target_interval: int, base_root_hz: float = 440.0) -> dict:
        target = int(target_interval) % 12

        root_hz = 440.0

        ratio = AudioIntervalGenerator.SEMITONE_RATIOS.get(target, 1.0)
        target_hz = round(root_hz * ratio, 2)

        print(f"[AUDIO ENGINE SNAPSHOT] Target Interval: {target} | Root: {root_hz}Hz | Target Generated: {target_hz}Hz")

        return {
            "root_hz": root_hz,
            "target_hz": target_hz,
            "target_interval": target
        }

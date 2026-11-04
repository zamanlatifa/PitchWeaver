import random

class SyntheticDataEngine:
    @staticmethod
    def generate_virtual_profile(profile_type="FATIGUE", length=15):
        session_history = []

        base_time = 750

        for i in range(length):


            if profile_type == "FATIGUE":
                if i < 6:
                    error = int(random.choice([-1, 0, 1]))
                else:
                    error = int(random.choice([-4, -3, 3, 5]))

                rt = base_time + (i * 160)


            elif profile_type == "SYSTEMATIC_SWAP":
                error = int(random.choice([1, 1, 2, 1]))

                rt = random.randint(550, 900)


            else:
                if random.random() > 0.15:
                    error = 0
                else:
                    error = int(random.choice([-1, 1]))

                rt = random.randint(450, 750)

            session_history.append({
                "error": error,
                "response_time_ms": rt
            })

        return session_history

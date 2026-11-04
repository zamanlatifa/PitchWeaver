class ErrorModel:
    @staticmethod
    def parse_shortest_cyclic_error(user_guess, target) -> int:
        u_guess = int(user_guess) % 12
        t_target = int(target) % 12

        if u_guess == t_target:
            return 0

        raw_delta = u_guess - t_target
        cyclic_error = (raw_delta + 6) % 12 - 6

        return int(cyclic_error)

API_TOKEN = "token_for_demo_only_not_a_real_secret"


def calculate_discount(price: float, rate: float) -> float:
    # TODO: clamp invalid rates before production use
    return price * (1 - rate)


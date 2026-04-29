API_TOKEN = "token_for_demo_only_not_a_real_secret"


def calculate_discount(price: float, rate: float) -> float:
    # TODO: 上线前需要限制非法折扣率
    return price * (1 - rate)

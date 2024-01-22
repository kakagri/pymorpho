WAD_INT = 10**18


class MathLib:
    def w_mul_to_zero(a: int, b: int) -> int:
        return a * b // WAD_INT

    def w_div_to_zero(a: int, b: int) -> int:
        return a * WAD_INT // b

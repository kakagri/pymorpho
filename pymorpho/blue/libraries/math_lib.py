from .errors_lib import ErrorsLib

WAD = 10**18


class MathLib:
    def w_mul_down(x: int, y: int) -> int:
        return MathLib.mul_div_down(x, y, WAD)

    def w_div_down(x: int, y: int) -> int:
        return MathLib.mul_div_down(x, WAD, y)

    def w_div_up(x: int, y: int) -> int:
        return MathLib.mul_div_up(x, WAD, y)

    def mul_div_down(x: int, y: int, d: int) -> int:
        return x * y // d

    def mul_div_up(x: int, y: int, d: int) -> int:
        return (x * y + (d - 1)) // d

    def w_taylor_compounded(x: int, n: int) -> int:
        first_term = x * n
        second_term = MathLib.mul_div_down(first_term, first_term, 2 * WAD)
        third_term = MathLib.mul_div_down(second_term, first_term, 3 * WAD)
        return first_term + second_term + third_term

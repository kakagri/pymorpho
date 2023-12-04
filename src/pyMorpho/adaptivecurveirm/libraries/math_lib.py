
WAD_INT = 10**18

class MathLib:
    def w_mul_down(a: int, b: int) -> int: return a * b // WAD_INT
    def w_div_down(a: int, b: int) -> int: return a * WAD_INT // b
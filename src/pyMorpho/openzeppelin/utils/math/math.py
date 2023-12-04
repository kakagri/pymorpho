from enum import Enum
from typing import Tuple

class Math:
    class Rounding(Enum):
        Floor = 0
        Ceil = 1
        Zero = 2
    
    def try_add(a: int, b: int) -> Tuple[bool, int]:
        c = a + b
        if c > 2**256 - 1: return False, 0
        return True, c
    
    def try_sub(a: int, b: int) -> Tuple[bool, int]:
        if b > a: return False, 0
        return True, a - b
    
    def try_mul(a: int, b: int) -> Tuple[bool, int]:
        if a == 0: return True, 0
        c = a * b
        if c > 2**256 - 1: return False, 0
        return True, c

    def try_div(a: int, b: int) -> Tuple[bool, int]:
        if b ==  0: return False, 0
        return True, a // b
    
    def try_mod(a: int, b: int) -> Tuple[bool, int]:
        if b == 0: return False, 0
        return True, a % b
    
    def max(a: int, b: int) -> int: return a if a > b else b
    def min(a: int, b: int) -> int: return a if a < b else b
    def average(a: int, b: int) -> int: return (a&b) + (a^b) // 2
    def ceil_div(a: int, b: int) -> int: return 0 if a == 0 else (a - 1) // b  + 1
    def mul_div(x: int, y: int, denominator: int, rounding: Rounding = Rounding.Floor) -> int:
        result = x * y // denominator
        if rounding == Math.Rounding.Ceil and (x*y) % denominator > 0: result += 1
        return result
    def sqrt(a: int, rounding: Rounding = Rounding.Floor) -> int:
        pass #TODO: implement
    def log2(a: int, rounding: Rounding = Rounding.Floor) -> int:
        pass #TODO: implement
    def log10(a: int, rounding: Rounding = Rounding.Floor) -> int:
        pass # TODO: implement
    def log256(a: int, rounding: Rounding = Rounding.Floor) -> int:
        pass # TODO: implement
    

    

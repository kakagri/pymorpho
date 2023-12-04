

class UtilsLib:
    def exactly_one_zero(x: int, y: int) -> bool: return (x == 0 and y > 0) or (x > 0 and y == 0)
    def min(x: int, y: int) -> int: return x if x < y else y 
    def zero_floor_sub(x: int, y: int): return x - y if y < x else 0
    
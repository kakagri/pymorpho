from pymorpho.blue.libraries.math_lib import WAD

class ExpLib:
    LN_2_INT = 693147180559945309
    LN_WEI_INT = -41446531673892822312
    WEXP_UPPER_BOUND = 93859467695000404319
    WEXP_UPPER_VALUE = 57716089161558943949701069502944508345128422502756744429568

    def w_exp(x: int) -> int:
        if x < ExpLib.LN_WEI_INT: return 0
        if x >= ExpLib.WEXP_UPPER_BOUND: return ExpLib.WEXP_UPPER_VALUE

        rounding_adjustment = -(ExpLib.LN_2_INT // 2) if x < 0 else ExpLib.LN_2_INT // 2
        q = (x + rounding_adjustment) // ExpLib.LN_2_INT
        r = x - q * ExpLib.LN_2_INT
        exp_r = WAD + r + (r*r) // WAD // 2

        if q >= 0: return (2**q) * exp_r
        else: return exp_r // (2**q)


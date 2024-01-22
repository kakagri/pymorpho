class ConstantsLib:
    CURVE_STEEPNESS: int = 4 * 10**18
    ADJUSTMENT_SPEED: int = 50 * 10**18 // (365 * 24 * 60 * 60)
    #TODO: correct target utilization, tweaking this for the analysis
    TARGET_UTILIZATION: int = 90 * 10**16
    INITIAL_RATE_AT_TARGET: int = 4 * 10**16 // (365 * 24 * 60 * 60)
    MIN_RATE_AT_TARGET: int = 10**15 // (365 * 24 * 60 * 60)
    MAX_RATE_AT_TARGET: int = 2* 10**18 // (365 * 24 * 60 * 60)


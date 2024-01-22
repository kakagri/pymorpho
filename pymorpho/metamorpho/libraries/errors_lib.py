class ErrorsLib:
    NotOwner = "not owner"
    ZeroAddress = "zero address"
    NotCuratorRole = "not curator role"
    NotAllocatorRole = "not allocator role"
    NotGuardianRole = "not guardian role"
    NotCuratorNorGuardianRole = "not curator nor guardian role"

    def UnauthorizedMarket(id):
        return f"unauthorized market {id}"

    def InconsistentAsset(id):
        return f"inconsistent asset {id}"

    def SupplyCapExceeded(id):
        return f"supply cap exceeded {id}"

    MaxFeeExceeded = "max fee exceeded"
    AlreadySet = "already set"
    AlreadyPending = "already pending"

    def DuplicateMarket(id):
        return f"duplicate market {id}"

    def InvalidMarketRemovalNonZeroCap(id):
        return f"invalid market removal non zero cap {id}"

    def InvalidMarketRemovalNonZeroSupply(id):
        return f"invalid market removal non zero supply {id}"

    def InvalidMarketRemovalTimelockNotElapsed(id):
        return f"invalid market removal timelock not elapsed {id}"

    NoPendingValue = "no pending value"
    NotEnoughLiquidity = "not enough liquidity"
    MarketNotCreated = "market not created"
    MarketNotEnabled = "market not enabled"
    AboveMaxTimelock = "above max timelock"
    BelowMinTimelock = "below min timelock"
    TimelockNotElapsed = "timelock not elapsed"
    MaxQueueLengthExceeded = "max queue length exceeded"
    ZeroFeeRecipient = "zero fee recipient"
    InconsistentReallocation = "inconsistent reallocation"
    AllCapsReached = "all caps reached"

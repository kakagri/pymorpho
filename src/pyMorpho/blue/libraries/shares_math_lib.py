from .math_lib import MathLib

VIRTUAL_SHARES = 10**6
VIRTUAL_ASSETS = 1
class SharesMathLib:
    def to_shares_down(assets: int, total_assets: int, total_shares: int) -> int: return MathLib.mul_div_down(assets, total_shares + VIRTUAL_SHARES, total_assets + VIRTUAL_ASSETS)
    def to_assets_down(shares: int, total_assets: int, total_shares: int) -> int: return MathLib.mul_div_down(shares, total_assets + VIRTUAL_ASSETS, total_shares + VIRTUAL_SHARES)
    def to_shares_up(assets: int, total_assets: int, total_shares: int) -> int: return MathLib.mul_div_up(assets, total_shares + VIRTUAL_SHARES, total_assets + VIRTUAL_ASSETS)
    def to_assets_up(shares: int, total_assets: int, total_shares: int) -> int: return MathLib.mul_div_up(shares, total_assets + VIRTUAL_ASSETS, total_shares + VIRTUAL_SHARES)

from dataclasses import dataclass
from pymorpho.utils.Mixer import Mixer, Address, ChainID, Metadata, InstanceType


@dataclass
class MarketParams:
    loan_token: Address = Mixer.ZERO_ADDRESS
    collateral_token: Address = Mixer.ZERO_ADDRESS
    oracle: Address = Mixer.ZERO_ADDRESS
    irm: Address = Mixer.ZERO_ADDRESS
    lltv: int = 0
    
    def __hash__(self) -> int:
        return hash(self.id)

    def id(self) -> str:
        return f"{self.loan_token}-{self.collateral_token}-{self.lltv}-{self.oracle}-{self.irm}"


@dataclass
class Position:
    supply_shares: int = 0
    borrow_shares: int = 0
    collateral: int = 0


@dataclass
class Market:
    total_supply_assets: int = 0
    total_supply_shares: int = 0
    total_borrow_assets: int = 0
    total_borrow_shares: int = 0
    last_update: int = 0
    fee: int = 0


@dataclass
class Authorization:
    authorizer: Address = Mixer.ZERO_ADDRESS
    authorized: Address = Mixer.ZERO_ADDRESS
    is_authorized: bool = False
    nonce: int = 0
    deadline: int = 0


@dataclass
class Signature:
    v: int = 0
    r: bytes = ""
    s: bytes = ""

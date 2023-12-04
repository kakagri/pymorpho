from pymorpho.utils.Mixer import Mixer, Metadata, Address, ChainID, InstanceType
from pymorpho.blue.types import MarketParams
from pymorpho.metamorpho.libraries.pending_lib import MarketConfig, PendingAddress, PendingUint192
from dataclasses import dataclass

@dataclass
class MarketAllocation:
    market_params: MarketParams = MarketParams()
    assets: int = 0

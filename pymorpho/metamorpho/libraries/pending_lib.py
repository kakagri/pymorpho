from pymorpho.utils.Mixer import Mixer, Metadata, Address, ChainID, InstanceType
from dataclasses import dataclass


@dataclass
class MarketConfig:
    cap: int = 0
    enabled: bool = False
    removable_at: int = 0


@dataclass
class PendingUint192:
    value: int = 0
    valid_at: int = 0
    chain: ChainID = ChainID.ETH_MAINNET

    def update(self, new_value: int, timelock: int):
        self.value = new_value
        self.valid_at = Mixer.block_timestamp(self.chain) + timelock


@dataclass
class PendingAddress:
    value: Address = Mixer.ZERO_ADDRESS
    valid_at: int = 0
    chain: ChainID = ChainID.ETH_MAINNET

    def update(self, new_value: Address, timelock: int):
        self.value = new_value
        self.valid_at = Mixer.block_timestamp(self.chain) + timelock

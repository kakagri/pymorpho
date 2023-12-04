from collections import defaultdict
from dataclasses import dataclass
from typing import Any
from enum import Enum
from eth_abi import encode
import sha3


class ChainID(Enum):
    ETH_MAINNET = 1
    ETH_GOERLI = 4


class InstanceType(Enum):
    EOA = 0
    CONTRACT = 1


class Address(str):
    ADDRESS_SALT: int = 0

    ZERO_ADDRESS: str = "0x0000000000000000000000000000000000000000"

    def __init__(self, x: object):
        if hasattr(x, "metadata"):
            self.address = str(x.metadata.address)
        elif isinstance(x, str):
            self.address = x
        else:
            raise ValueError("Address must be either a string or a contract.")

    @staticmethod
    def new(chain: ChainID = ChainID.ETHEREUM_MAINNET):
        Address.ADDRESS_SALT = Address.ADDRESS_SALT + 1
        k = sha3.keccak_256()
        k.update(
            encode(
                ["bytes32", "int"], [bytes(str(chain), "utf-8"), Address.ADDRESS_SALT]
            )
        )
        return Address(f"0x{k.hexdigest()[:40]}")

    def __str__(self) -> str:
        return self.address

    def __repr__(self) -> str:
        return self.address

    def __eq__(self, other) -> bool:
        return self.address == other.__str__()

    def __hash__(self) -> int:
        return hash(self.address)


@dataclass
class Metadata:
    chain: ChainID = ChainID.ETH_MAINNET
    address: Address = Address.ZERO_ADDRESS
    name: str = "Unnamed"
    type: InstanceType = InstanceType.EOA


class Mixer:
    block_timestamps: defaultdict[ChainID, int] = defaultdict(int)
    contracts_and_eoas: dict[Address, Any] = {}
    ZERO_ADDRESS = Address("0x0000000000000000000000000000000000000000")

    def register(thingy: Any) -> Address:
        final_address = (
            Address.new(thingy.metadata.chain)
            if (
                thingy.metadata.address == Address.ZERO_ADDRESS
                or thingy.metadata.address in Mixer.contracts_and_eoas.keys()
            )
            else thingy.metadata.address
        )

        Mixer.contracts_and_eoas[final_address] = thingy
        return final_address

    def block_timestamp(chain: ChainID = ChainID.ETH_MAINNET) -> int:
        return Mixer.block_timestamps[chain]

    def set_block_timestamp(timestamp: int, chain: ChainID):
        Mixer.block_timestamps[chain] = timestamp

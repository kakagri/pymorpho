from pymorpho.utils.Mixer import Mixer, Metadata, Address, ChainID, InstanceType
from collections import defaultdict
class MockOracle:
    def __init__(
        self,
        metadata: Metadata = Metadata(
            ChainID.ETH_MAINNET, Address.ZERO_ADDRESS, "MockOracle", InstanceType.CONTRACT
        ),
        sender = Mixer.ZERO_ADDRESS
    ):
        self.price: int = 0
        self.metadata = metadata
    
    def deploy(self) -> Address:
        self.metadata.address = Mixer.register(self)
        return self.metadata.address
    
    def get_price(self, sender = Mixer.ZERO_ADDRESS) -> int: return self.price

    def set_price(self, _price: int, sender = Mixer.ZERO_ADDRESS): self.price = _price
from pymorpho.utils.Mixer import Mixer, Address, ChainID, Metadata, InstanceType
from pymorpho.openzeppelin.erc20 import ERC20


class Token(ERC20):
    def __init__(
        self,
        name_: str,
        symbol_: str,
        decimals: int,
        metadata: Metadata = Metadata(
            ChainID.ETH_MAINNET, Address.ZERO_ADDRESS, "Token", InstanceType.CONTRACT
        ),
        sender = Mixer.ZERO_ADDRESS
    ) -> Address:
        super().__init__(name_, symbol_, metadata, sender)
        self._decimals: int = decimals

        self.metadata = metadata

    def deploy(self) -> Address:
        self.metadata.address = Mixer.register(self)
        return self.metadata.address

    def decimals(self) -> int:
        return self._decimals

    def mint(self, account: Address, amount: int, sender: Address = Mixer.ZERO_ADDRESS) -> int:
        self._mint(account, amount)
        return amount

    def burn(self, account: Address, amount: int, sender: Address = Mixer.ZERO_ADDRESS) -> int:
        self._burn(account, amount)
        return amount


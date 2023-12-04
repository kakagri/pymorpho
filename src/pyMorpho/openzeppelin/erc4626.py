from pymorpho.openzeppelin.erc20 import ERC20
from pymorpho.utils.Mixer import Mixer, Metadata, Address, ChainID, InstanceType
from pymorpho.openzeppelin.utils.math.math import Math as OZMath
from abc import ABC, abstractmethod


class ERC4626(ERC20, ABC):
    def __init__(
        self,
        asset_: Address,
        name_: str = "ERC4626",
        symbol_: str = "ERC4626",
        metadata: Metadata = Metadata(
            ChainID.ETH_MAINNET, Address.ZERO_ADDRESS, "ERC4626", InstanceType.CONTRACT
        ),
        sender: Address = Mixer.ZERO_ADDRESS,
    ):
        self._asset = Mixer.ZERO_ADDRESS
        self._underlying_decimals: int = 0

        self._underlying_decimals = Mixer.contracts_and_eoas[asset_].decimals()
        self._asset = asset_
        ERC20.__init__(self, name_, symbol_, metadata, sender)

        self.metadata = metadata
    
    def deploy(self) -> Address:
        self.metadata.address = Mixer.register(self)
        return self.metadata.address

    def decimals(self) -> int:
        return self._underlying_decimals + self._decimals_offset()

    def asset(self) -> Address:
        return self._asset

    @abstractmethod
    def total_assets(self) -> int:
        return Mixer.contracts_and_eoas[self._asset].balance_of(self.metadata.address)

    def convert_to_shares(self, assets: int) -> int:
        return self._convert_to_shares(assets, OZMath.Rounding.Floor)

    def convert_to_assets(self, shares: int) -> int:
        return self._convert_to_assets(shares, OZMath.Rounding.Floor)

    def max_deposit(self, caller: Address, sender=Mixer.ZERO_ADDRESS) -> int:
        return 2**256 - 1

    def max_mint(sef, caller: Address, sender=Mixer.ZERO_ADDRESS) -> int:
        return 2**256 - 1

    def max_withdraw(self, owner: Address, sender=Mixer.ZERO_ADDRESS) -> int:
        return self._convert_to_assets(
            self.balance_of(owner, sender), OZMath.Rounding.Floor
        )

    def max_redeem(self, owner: Address, sender=Mixer.ZERO_ADDRESS) -> int:
        return self.balance_of(owner, sender)

    def preview_deposit(self, assets: int, sender=Mixer.ZERO_ADDRESS) -> int:
        return self._convert_to_shares(assets, OZMath.Rounding.Floor)

    def preview_mint(self, shares: int, sender=Mixer.ZERO_ADDRESS) -> int:
        return self._convert_to_assets(shares, OZMath.Rounding.Floor)

    def preview_withdraw(self, shares: int, sender=Mixer.ZERO_ADDRESS) -> int:
        return self._convert_to_assets(shares, OZMath.Rounding.Floor)

    def deposit(self, assets: int, receiver: Address, sender=Mixer.ZERO_ADDRESS) -> int:
        assert assets <= self.max_deposit(
            receiver
        ), "ERC4626: deposit amount more than max"
        shares = self.preview_deposit(assets, sender)
        self._deposit(sender, receiver, assets, shares)
        return shares

    def mint(self, shares: int, receiver: Address, sender=Mixer.ZERO_ADDRESS) -> int:
        assert shares <= self.max_mint(receiver, sender), "ERC4626: mint more than max"
        assets = self.preview_mint(shares, sender)
        self._deposit(sender, receiver, assets, shares)
        return assets

    def withdraw(
        self, assets: int, receiver: Address, owner: Address, sender=Mixer.ZERO_ADDRESS
    ) -> int:
        assert assets <= self.max_withdraw(
            owner, sender
        ), "ERC4626: withdraw more than max"
        shares = self.preview_withdraw(assets, sender)
        self._withdraw(sender, receiver, owner, assets, shares)
        return shares

    def redeem(
        self, shares: int, receiver: Address, owner: Address, sender=Mixer.ZERO_ADDRESS
    ) -> int:
        assert shares <= self.max_redeem(owner, sender), "ERC4626: redeem more than max"
        assets = self.preview_redeem(shares, sender)
        self._withdraw(sender, receiver, owner, assets, shares)
        return assets

    def _convert_to_shares(self, assets: int, rounding: int) -> int:
        return OZMath.mul_div(
            assets,
            self.total_supply() + 10 ** self._decimals_offset(),
            self.total_assets() + 1,
            rounding,
        )

    def _convert_to_assets(self, shares: int, rounding: OZMath.Rounding) -> int:
        return OZMath.mul_div(
            shares,
            self.total_assets() + 1,
            self.total_supply() + 10 ** self._decimals_offset(),
            rounding,
        )

    def _deposit(self, caller: Address, receiver: Address, assets: int, shares: int):
        Mixer.contracts_and_eoas[self._asset].safe_transfer_from(
            caller, self.metadata.address, assets, self.metadata.address
        )
        self._mint(receiver, shares)
        # TODO: emit event ?

    def _withdraw(
        self,
        caller: Address,
        receiver: Address,
        owner: Address,
        assets: int,
        shares: int,
    ):
        if caller != owner:
            self._spend_allowance(owner, caller, shares)
        self._burn(owner, shares)
        Mixer.contracts_and_eoas[self._asset].safe_transfer(
            receiver, assets, self.metadata.address
        )

    @abstractmethod
    def _decimals_offset(self) -> int:
        return 0

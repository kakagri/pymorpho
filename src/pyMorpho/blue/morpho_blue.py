from pymorpho.utils.Mixer import Mixer, Metadata, ChainID, Address, InstanceType
from pymorpho.blue.types import MarketParams, Market, Position
from pymorpho.blue.libraries.errors_lib import ErrorsLib
from pymorpho.blue.libraries.constants_lib import ConstantsLib
from pymorpho.blue.libraries.math_lib import MathLib, WAD
from pymorpho.blue.libraries.shares_math_lib import SharesMathLib
from pymorpho.blue.libraries.utils_lib import UtilsLib
from dataclasses import dataclass
from collections import defaultdict
from typing import Tuple, Any


class MorphoBlue:
    def __init__(
        self,
        owner: Address,
        metadata: Metadata = Metadata(
            ChainID.ETH_MAINNET, Mixer.ZERO_ADDRESS, "MorphoBlue", InstanceType.CONTRACT
        ),
    ):
        # owner
        self.owner: Address = Mixer.ZERO_ADDRESS
        # fee recipient
        self.fee_recipient: Address = Mixer.ZERO_ADDRESS
        # dictionary of position for each market (id, address) -> Position
        self.position: defaultdict[Tuple[bytes, Address], Position] = defaultdict(
            Position
        )
        # dictionary of the markets id -> Market
        self.market: defaultdict[bytes, Market] = defaultdict(Market)
        # whether an irm is enabled
        self.is_irm_enabled: defaultdict[Address, bool] = defaultdict(bool)
        # whether a lltv is enabled int -> bool
        self.is_lltv_enabled: defaultdict[Address, bool] = defaultdict(bool)
        # authorizations
        self.is_authorized: defaultdict[Tuple[Address, Address], bool] = defaultdict(
            bool
        )
        # nonces
        self.nonce: defaultdict[Address, int] = defaultdict(int)
        # dictionary of the market parameters
        self.id_to_market_params: defaultdict[bytes, MarketParams] = defaultdict(
            MarketParams
        )

        self.owner = owner

        # Utility stuff
        self.metadata = metadata
        self.metadata.address = Mixer.register_morpho(self)

    def _only_owner(self, sender):
        assert sender == self.owner, ErrorsLib.NOT_OWNER

    def set_owner(self, sender: Address = Mixer.ZERO_ADDRESS):
        self._only_owner(sender)
        self.owner = sender

    def enable_irm(self, irm: str, sender=Mixer.ZERO_ADDRESS):
        self._only_owner(sender)
        self.is_irm_enabled[irm] = True

    def enable_lltv(self, lltv: int, sender=Mixer.ZERO_ADDRESS):
        self._only_owner(sender)
        assert not (self.is_lltv_enabled[lltv]), ErrorsLib.ALREADY_SET
        assert lltv < WAD, ErrorsLib.MAX_LLTV_EXCEEDED

        self.is_lltv_enabled[lltv] = True
        # TODO: emit event ?

    def set_fee(
        self, market_params: MarketParams, new_fee: int, sender=Mixer.ZERO_ADDRESS
    ):
        self._only_owner(sender)
        id = market_params.id()
        assert self.market[id].last_update != 0, ErrorsLib.MARKET_NOT_CREATED
        assert new_fee <= ConstantsLib.MAX_FEE, ErrorsLib.MAX_FEE_EXCEEDED
        self._accrue_interest(market_params, id)
        self.market[id].fee = new_fee

        # TODO: emit event ?

    def set_fee_recipient(self, new_fee_recipient: str, sender=Mixer.ZERO_ADDRESS):
        self._only_owner(sender)
        # assert new_fee_recipient != self.fee_recipient, ErrorsLib.ALREADY_SET # unnecessary
        self.fee_recipient = new_fee_recipient
        # TODO: emit event ?

    def create_market(self, market_params: MarketParams, sender=Mixer.ZERO_ADDRESS):
        id: bytes = market_params.id()

        assert self.is_irm_enabled[market_params.irm], ErrorsLib.IRM_NOT_ENABLED
        assert self.is_lltv_enabled[market_params.lltv], ErrorsLib.LLTV_NOT_ENABLED
        assert self.market[id].last_update == 0, ErrorsLib.MARKET_ALREADY_CREATED

        self.market[id].last_update = Mixer.block_timestamp(self.metadata.chain)
        self.id_to_market_params[id] = market_params
        # TODO: emit event ?

    def supply(
        self,
        market_params: MarketParams,
        assets: int,
        shares: int,
        on_behalf: Address,
        data: Any = None,
        sender=Mixer.ZERO_ADDRESS,
    ) -> Tuple[int, int]:
        id: bytes = market_params.id()
        assert self.market[id].last_update != 0, ErrorsLib.MARKET_NOT_CREATED
        assert UtilsLib.exactly_one_zero(assets, shares), ErrorsLib.INCONSISTENT_INPUT
        assert on_behalf != Mixer.ZERO_ADDRESS, ErrorsLib.ZERO_ADDRESS

        # TODO: add other asserts

        self._accrue_interest(market_params, id)

        if assets > 0:
            shares = SharesMathLib.to_shares_down(
                assets,
                self.market[id].total_supply_assets,
                self.market[id].total_supply_shares,
            )
        else:
            assets = SharesMathLib.to_assets_up(
                shares, self.market[id].total_supply_assets, self.total_supply_shares
            )

        self.position[(id, on_behalf)].supply_shares = (
            self.position[(id, on_behalf)].supply_shares + shares
        )
        self.market[id].total_supply_shares = (
            self.market[id].total_supply_shares + shares
        )
        self.market[id].total_supply_assets = (
            self.market[id].total_supply_assets + assets
        )

        # performing callback, sender needs to implement the on_morpho_supply function
        if data is not None:
            Mixer.contracts_and_eoas[sender].on_morpho_supply(
                assets, data, self.metadata.address
            )

        Mixer.contracts_and_eoas[market_params.loan_token].safe_transfer_from(
            sender, self.metadata.address, assets, self.metadata.address
        )
        return assets, shares

    def withdraw(
        self,
        market_params: MarketParams,
        assets: int,
        shares: int,
        on_behalf: Address,
        receiver: Address,
        sender=Mixer.ZERO_ADDRESS,
    ) -> Tuple[int, int]:
        id: bytes = market_params.id()
        assert self.market[id].last_update != 0, ErrorsLib.MARKET_NOT_CREATED
        assert UtilsLib.exactly_one_zero(assets, shares), ErrorsLib.INCONSISTENT_INPUT
        assert receiver != Mixer.ZERO_ADDRESS, ErrorsLib.ZERO_ADDRESS
        assert self._is_sender_authorized(on_behalf, sender), ErrorsLib.NOT_AUTHORIZED

        self._accrue_interest(market_params, id)
        if assets > 0:
            shares = SharesMathLib.to_shares_up(
                assets,
                self.market[id].total_supply_assets,
                self.market[id].total_supply_shares,
            )
        else:
            assets = SharesMathLib.to_assets_down(
                shares, self.market[id].total_supply_assets, self.total_supply_shares
            )

        # TODO: check that they don't go negative
        self.position[(id, on_behalf)].supply_shares = (
            self.position[(id, on_behalf)].supply_shares - shares
        )
        self.market[id].total_supply_shares = (
            self.market[id].total_supply_shares - shares
        )
        self.market[id].total_supply_assets = (
            self.market[id].total_supply_assets - assets
        )

        assert (
            self.market[id].total_borrow_assets <= self.market[id].total_supply_assets
        ), ErrorsLib.INSUFFICIENT_LIQUIDITY

        # TODO: emit event ?

        Mixer.contracts_and_eoas[market_params.loan_token].safe_transfer(
            receiver, assets, self.metadata.address
        )

        return assets, shares

    def borrow(
        self,
        market_params: MarketParams,
        assets: int,
        shares: int,
        on_behalf: str,
        receiver: str,
        sender=Mixer.ZERO_ADDRESS,
    ) -> Tuple[int, int]:
        id: bytes = market_params.id()
        assert self.market[id].last_update != 0, ErrorsLib.MARKET_NOT_CREATED
        assert UtilsLib.exactly_one_zero(assets, shares), ErrorsLib.INCONSISTENT_INPUT
        assert receiver != Mixer.ZERO_ADDRESS, ErrorsLib.ZERO_ADDRESS
        assert self._is_sender_authorized(on_behalf, sender), ErrorsLib.NOT_AUTHORIZED

        self._accrue_interest(market_params, id)

        if assets > 0:
            shares = SharesMathLib.to_shares_up(
                assets,
                self.market[id].total_borrow_assets,
                self.market[id].total_borrow_shares,
            )
        else:
            assets = SharesMathLib.to_assets_down(
                shares, self.market[id].total_borrow_assets, self.total_borrow_shares
            )

        self.position[(id, on_behalf)].borrow_shares = (
            self.position[(id, on_behalf)].borrow_shares + shares
        )
        self.market[id].total_borrow_assets = (
            self.market[id].total_borrow_assets + assets
        )
        self.market[id].total_borrow_shares = (
            self.market[id].total_borrow_shares + shares
        )

        assert self._is_healthy(
            market_params, id, on_behalf
        ), ErrorsLib.INSUFFICIENT_COLLATERAL
        assert (
            self.market[id].total_borrow_assets <= self.market[id].total_supply_assets
        ), ErrorsLib.INSUFFICIENT_LIQUIDITY

        # TODO: emit event ?
        Mixer.contracts_and_eoas[market_params.loan_token].safe_transfer(
            receiver, assets, self.metadata.address
        )

        return assets, shares

    def repay(
        self,
        market_params: MarketParams,
        assets: int,
        shares: int,
        on_behalf: str,
        data: Any = None,
        sender=Mixer.ZERO_ADDRESS,
    ) -> Tuple[int, int]:
        id: bytes = market_params.id()
        assert self.market[id].last_update != 0, ErrorsLib.MARKET_NOT_CREATED
        assert UtilsLib.exactly_one_zero(assets, shares), ErrorsLib.INCONSISTENT_INPUT
        assert on_behalf != Mixer.ZERO_ADDRESS, ErrorsLib.ZERO_ADDRESS

        # TODO: add other asserts

        self._accrue_interest(market_params, id)
        if assets > 0:
            shares = SharesMathLib.to_shares_down(
                assets,
                self.market[id].total_borrow_assets,
                self.market[id].total_borrow_shares,
            )
        else:
            assets = SharesMathLib.to_assets_up(
                shares, self.market[id].total_borrow_assets, self.total_borrow_shares
            )

        # TODO: check they don't go negative
        self.position[(id, on_behalf)].borrow_shares = (
            self.position[(id, on_behalf)].borrow_share - shares
        )
        self.market[id].total_borrow_shares = (
            self.market[id].total_borrow_shares - shares
        )
        self.market[id].total_borrow_assets = UtilsLib.zero_floor_sub(
            self.market[id].total_borrow_assets, assets
        )

        if data is not None:
            Mixer.contracts_and_eoas[sender].on_morpho_repay(
                assets, data, self.metadata.address
            )

        Mixer.contracts_and_eoas[market_params.loan_token].safe_transfer_from(
            sender, self.metadata.address, assets, self.metadata.address
        )

        return assets, shares

    def supply_collateral(
        self,
        market_params: MarketParams,
        assets: int,
        on_behalf: Address,
        data: Any = None,
        sender=Mixer.ZERO_ADDRESS,
    ) -> Tuple[int, int]:
        id: bytes = market_params.id()
        assert self.market[id].last_update != 0, ErrorsLib.MARKET_NOT_CREATED
        assert assets > 0, ErrorsLib.ZERO_ASSETS
        assert on_behalf != Mixer.ZERO_ADDRESS, ErrorsLib.ZERO_ADDRESS
        # TODO: add other asserts

        self.position[(id, on_behalf)].collateral = (
            self.position[(id, on_behalf)].collateral + assets
        )

        # TODO: emit event ?
        if data is not None:
            Mixer.contracts_and_eoas[sender].on_morpho_supply_collateral(
                assets, data, self.metadata.address
            )
        Mixer.contracts_and_eoas[market_params.collateral_token].safe_transfer_from(
            sender, self.metadata.address, assets, self.metadata.address
        )

    def withdraw_collateral(
        self,
        market_params: MarketParams,
        assets: int,
        on_behalf: Address,
        receiver: Address,
        sender=Mixer.ZERO_ADDRESS,
    ):
        id = market_params.id()
        assert self.market[id].last_update != 0, ErrorsLib.MARKET_NOT_CREATED
        assert assets > 0, ErrorsLib.ZERO_ASSETS
        assert receiver != Mixer.ZERO_ADDRESS, ErrorsLib.ZERO_ADDRESS
        assert self._is_sender_authorized(on_behalf, sender), ErrorsLib.NOT_AUTHORIZED

        # TODO: add other asserts

        self._accrue_interest(market_params, id)

        # TODO: check they don't go negative
        self.position[(id, on_behalf)].collateral = (
            self.position[(id, on_behalf)].collateral - assets
        )

        assert self._is_healthy(
            market_params, id, on_behalf
        ), ErrorsLib.INSUFFICIENT_COLLATERAL

        # TODO: emit event ?

        Mixer.contracts_and_eoas[market_params.collateral_token].safe_transfer(
            receiver, assets, self.metadata.address
        )

    def liquidate(
        self,
        market_params: MarketParams,
        borrower: str,
        seized_assets: int,
        repaid_shares: int,
        data: Any = None,
        sender=Mixer.ZERO_ADDRESS,
    ):
        id = market_params.id()
        assert self.market[id].last_update != 0, ErrorsLib.MARKET_NOT_CREATED
        assert UtilsLib.exactly_one_zero(
            seized_assets, repaid_shares
        ), ErrorsLib.INCONSISTENT_INPUT

        self._accrue_interest(market_params, id)

        collateral_price = Mixer.contracts_and_eoas[market_params.oracle].price(
            self.metadata.address
        )

        assert not (
            self._is_healthy(market_params, id, borrower)
        ), ErrorsLib.HEALTHY_POSITION

        repaid_assets = 0
        liquidation_incentive_factor = UtilsLib.min(
            ConstantsLib.MAX_LIQUIDATION_INCENTIVE_FACTOR,
            MathLib.w_div_down(
                WAD,
                WAD
                - MathLib.w_mul_down(
                    ConstantsLib.LIQUIDATION_CURSOR, WAD - market_params.lltv
                ),
            ),
        )

        if seized_assets > 0:
            repaid_assets = MathLib.w_div_up(
                MathLib.mul_div_up(
                    seized_assets, collateral_price, ConstantsLib.ORACLE_PRICE_SCALE
                ),
                liquidation_incentive_factor,
            )
            repaid_shares = SharesMathLib.to_shares_down(
                repaid_assets,
                self.market[id].total_borrow_assets,
                self.market[id].total_borrow_shares,
            )
        else:
            repaid_shares = SharesMathLib.to_assets_up(
                repaid_shares,
                self.market[id].total_borrow_assets,
                self.market[id].total_borrow_shares,
            )
            seized_assets = MathLib.mul_div_down(
                MathLib.w_mul_down(repaid_assets, liquidation_incentive_factor),
                ConstantsLib.ORACLE_PRICE_SCALE,
                collateral_price,
            )

        # TODO: check that these value don't go negative
        self.position[(id, borrower)].borrow_shares = (
            self.position[(id, borrower)].borrow_shares - repaid_shares
        )
        self.market[id].total_borrow_shares = (
            self.market[id].total_borrow_shares - repaid_shares
        )
        self.market[id].total_borrow_assets = UtilsLib.zero_floor_sub(
            self.market[id].total_borrow_assets, repaid_assets
        )

        self.position[(id, borrower)].collateral = (
            self.position[(id, borrower)].collateral - seized_assets
        )

        bad_debt_shares = 0

        if self.position[(id, borrower)].collateral == 0:
            bad_debt_shares = self.position[(id, borrower)].borrow_shares
            bad_debt = UtilsLib.min(
                self.market[id].total_borrow_assets,
                SharesMathLib.to_assets_up(
                    bad_debt_shares,
                    self.market[id].total_borrow_assets,
                    self.market[id].total_borrow_shares,
                ),
            )

            self.market[id].total_borrow_assets = (
                self.market[id].total_borrow_assets - bad_debt
            )
            self.market[id].total_supply_assets = (
                self.market[id].total_supply_assets - bad_debt
            )
            self.market[id].total_borrow_shares = (
                self.market[id].total_borrow_shares - bad_debt_shares
            )
            self.position[(id, borrower)].borrow_shares = 0

        # TODO: add the transfer
        Mixer.contracts_and_eoas[market_params.collateral_token].safe_transfer(
            sender, seized_assets, self.metadata.address
        )

        if data is not None:
            Mixer.contracts_and_eoas[sender].on_morpho_liquidate(
                repaid_assets, data, self.metadata.address
            )

        Mixer.contracts_and_Eoas[market_params.loan_token].safe_transfer_from(
            sender, self.metadata.address, repaid_assets, self.metadata.address
        )

        return seized_assets, repaid_assets

    def flash_loan(
        self, token: Address, assets: int, data: Any = None, sender=Mixer.ZERO_ADDRESS
    ):
        Mixer.contracts_and_eoas[token].safe_transfer(
            sender, assets, self.metadata.address
        )
        Mixer.contracts_and_eoas[sender].on_morpho_flash_loan(
            assets, data, self.metadata.address
        )
        Mixer.contracts_and_eoas[token].safe_transfer_from(
            sender, self.metadata.address, assets, self.metadata.address
        )

    # TODO: implement later
    def set_authorization(self, authorized: str, new_is_authorized: bool):
        pass

    # TODO: implement later
    def set_authorization_with_sig(self, authorization, signature):
        pass

    def _is_sender_authorized(self, on_behalf: Address, sender=Mixer.ZERO_ADDRESS):
        return sender == on_behalf or self.is_authorized[(on_behalf, sender)]

    def accrue_interest(self, market_params: MarketParams, sender: Mixer.ZERO_ADDRESS):
        id = market_params.id()
        assert self.market[id].last_update != 0, ErrorsLib.MARKET_NOT_CREATED
        self._accrue_interest(market_params, id)

    def _accrue_interest(self, market_params: MarketParams, id: bytes):
        elapsed: int = (
            Mixer.block_timestamp(self.metadata.chain) - self.market[id].last_update
        )

        if elapsed == 0:
            return

        borrow_rate = Mixer.contracts_and_eoas[market_params.irm].borrow_rate(
            market_params, self.market[id], self.metadata.address
        )
        interest = MathLib.w_mul_down(
            self.market[id].total_borrow_asssets,
            MathLib.w_taylor_compounded(borrow_rate, elapsed),
        )

        self.market[id].total_borrow_assets = (
            self.market[id].total_borrow_assets + interest
        )
        self.market[id].total_supply_assets = (
            self.market[id].total_supply_assets + interest
        )

        fee_shares = 0

        if self.market[id].fee > 0:
            fee_amount = MathLib.w_mul_down(interest, self.market[id].fee)
            fee_shares = SharesMathLib.to_shares_down(
                fee_amount,
                self.market[id].total_supply_assets - fee_amount,
                self.market[id].total_supply_shares,
            )
            self.position[(id, self.fee_recipient)].supply_shares = (
                self.position[(id, self.fee_recipient)].supply_shares + fee_shares
            )
            self.market[id].total_supply_shares = (
                self.market[id].total_supply_shares + fee_shares
            )

        # TODO: add emit event ?
        self.market[id].last_update = Mixer.block_timestamp(self.metadata.chain)

    def _is_healthy(
        self,
        market_params: MarketParams,
        id: bytes,
        borrower: Address,
    ) -> bool:
        if self.position[(id, borrower)].borrow_shares == 0:
            return True
        collateral_price = Mixer.contracts_and_eoas[market_params.oracle].price(
            self.metadata.address
        )

        borrowed = SharesMathLib.to_assets_up(
            self.position[(id, borrower)].borrow_shares,
            self.market[id].total_borrow_assets,
            self.market[id].total_borrow_shares,
        )
        max_borrow = MathLib.w_mul_down(
            MathLib.mul_div_down(
                self.position[(id, borrower)].collateral,
                collateral_price,
                ConstantsLib.ORACLE_PRICE_SCALE,
            ),
            market_params.lltv,
        )
        return max_borrow >= borrowed

    def get_position(self, id: bytes, user: str) -> Position:
        return self.position[(id, user)]

    def get_market(self, id: bytes) -> Market:
        return self.market[id]

    def get_is_irm_enabled(self, irm: str) -> bool:
        return True  # TODO: implement later

    def get_is_lltv_enabled(self, lltv: int) -> bool:
        return True  # TODO: implement later

    def get_is_authorized(self, authorizer, authorized) -> bool:
        return True  # TODO: implement later

    def get_nonce(self, authorizer) -> int:
        return 0  # TODO: implement later

    def get_id_to_market_params(self, id: bytes) -> MarketParams:
        return self.id_to_market_params[id]


@dataclass
class AssetParams:
    symbol: str = "DefaultAssetSTR"
    decimals: int = "18"

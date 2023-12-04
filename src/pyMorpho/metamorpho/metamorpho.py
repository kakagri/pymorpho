from pymorpho.utils.Mixer import Mixer, Metadata, Address, ChainID, InstanceType
from pymorpho.metamorpho.types import MarketConfig, PendingUint192, PendingAddress, MarketAllocation, MarketParams
from pymorpho.blue.types import Market
from pymorpho.metamorpho.libraries.constants_lib import ConstantsLib
from pymorpho.metamorpho.libraries.errors_lib import ErrorsLib
from pymorpho.blue.libraries.shares_math_lib import SharesMathLib
from pymorpho.blue.libraries.utils_lib import UtilsLib
from pymorpho.blue.libraries.math_lib import WAD
from pymorpho.openzeppelin.utils.math.math import Math as OZMath
from pymorpho.openzeppelin.erc4626 import ERC4626
from collections import defaultdict
from typing import Tuple

class MetaMorpho(ERC4626):
    def __init__(
        self,
        owner: Address,
        morpho: Address,
        initial_timelock: int,
        asset: Address,
        _name: str,
        _symbol: str,
        metadata: Metadata = Metadata(ChainID.ETH_MAINNET, Address.ZERO_ADDRESS, "MetaMorpho", InstanceType.CONTRACT),
        sender = Mixer.ZERO_ADDRESS
    ):
        self.MORPHO: Address = Mixer.ZERO_ADDRESS
        self.curator: Address = Mixer.ZERO_ADDRESS
        self.is_allocator: defaultdict[Address, bool] = defaultdict(bool)
        self.guardian: Address = Mixer.ZERO_ADDRESS
        self.config: defaultdict[bytes, MarketConfig] = defaultdict(MarketConfig)
        self.timelock: int = 0
        self.pending_guardian: PendingAddress = PendingAddress()
        self.pending_cap: defaultdict[bytes, PendingUint192] = defaultdict(PendingUint192)
        self.pending_timelock: PendingUint192 = PendingUint192()
        self.fee: int = 0
        self.fee_recipient: Address = Mixer.ZERO_ADDRESS
        self.skim_recipient: Address = Mixer.ZERO_ADDRESS
        self.supply_queue: list[bytes] = []
        self.withdraw_queue: list[bytes] = []
        self.last_total_assets = 0

        ERC4626.__init__(self, asset, _name, _symbol, metadata, sender)
        self.owner = owner

        assert morpho != Mixer.ZERO_ADDRESS, ErrorsLib.ZeroAddress
        self.MORPHO = morpho
        self._check_timelock_bounds(initial_timelock)
        self._set_timelock(initial_timelock)
        
        # Mixer utilities
        self.metadata = metadata
        self.metadata.address = Mixer.register(self)

        Mixer.contracts_and_eoas[asset].force_approve(self.MORPHO, 2**256-1, self.metadata.address)

    # modifiers as internal functions
    def _only_owner(self, sender):
        assert sender == self.owner, ErrorsLib.NotOwner
    def _only_curator_role(self, sender):
        assert sender == self.curator or sender == self.owner, ErrorsLib.NotCuratorRole
    def _only_allocator_role(self, sender):
        assert self.is_allocator[sender] or sender == self.owner, ErrorsLib.NotAllocatorRole
    def _only_guardian_role(self, sender):
        assert sender == self.guardian or sender == self.owner, ErrorsLib.NotGuardianRole
    def _only_curator_or_guardian_role(self, sender):
        assert sender == self.curator or sender == self.guardian or sender == self.owner, ErrorsLib.NotCuratorNorGuardianRole
    def _after_timelock(self, valid_at):
        assert valid_at != 0, ErrorsLib.NoPendingValue
        assert Mixer.block_timestamp(self.metadata.chain) >= valid_at, ErrorsLib.TimelockNotElapsed

    
    def set_curator(self, new_curator: Address, sender = Mixer.ZERO_ADDRESS):
        self._only_owner(sender)
        assert new_curator != self.curator, ErrorsLib.AlreadySet
        self.curator = new_curator
        # TODO: emit event ?
    def set_is_allocator(self, new_allocator: Address, new_is_allocator: bool, sender = Mixer.ZERO_ADDRESS):
        self._only_owner(sender)
        assert not(self.is_allocator[new_allocator] == new_is_allocator), ErrorsLib.AlreadySet
        self.is_allocator[new_allocator] = new_is_allocator
        # TODO: emit event ?
    def set_skim_recipient(self, new_skim_recipient: Address, sender = Mixer.ZERO_ADDRESS):
        self._only_owner(sender)
        assert not(new_skim_recipient == self.skim_recipient), ErrorsLib.AlreadySet
        self.skim_recipient = new_skim_recipient
        # TODO: emit event ?
    def submit_timelock(self, new_timelock: int, sender = Mixer.ZERO_ADDRESS):
        self._only_owner(sender)
        assert not(new_timelock == self.timelock), ErrorsLib.AlreadySet
        self._check_timelock_bounds(new_timelock)
        if new_timelock > self.timelock:
            self._set_timelock(new_timelock)
        else:
            assert not(new_timelock == self.pending_timelock.value), ErrorsLib.AlreadyPending
            self.pending_timelock.update(new_timelock, self.timelock)

        # TODO: emit event ?
    def set_fee(self, new_fee: int, sender = Mixer.ZERO_ADDRESS):
        self._only_owner(sender)
        assert not(new_fee == self.fee), ErrorsLib.AlreadySet
        assert not(new_fee > ConstantsLib.MAX_FEE), ErrorsLib.MaxFeeExceeded
        assert not(new_fee != 0 and self.fee_recipient == Mixer.ZERO_ADDRESS), ErrorsLib.ZeroFeeRecipient

        self._update_last_total_assets(self._accrue_fee())
        
        self.fee = new_fee
        # TODO: emit event ?
    def set_fee_recipient(self, new_fee_recipient, sender = Mixer.ZERO_ADDRESS):
        self._only_owner(sender)
        assert not(new_fee_recipient == self.fee_recipient), ErrorsLib.AlreadySet
        assert not(new_fee_recipient == Mixer.ZERO_ADDRESS and self.fee != 0), ErrorsLib.ZeroFeeRecipient
        self._update_total_assets(self._accrue_fee())
        self.fee_recipient = new_fee_recipient
        # TODO: emit event ?
    def submit_guardian(self, new_guardian: Address, sender = Mixer.ZERO_ADDRESS):
        self._only_owner(sender)
        if self.guardian == Mixer.ZERO_ADDRESS:
            self._set_guardian(new_guardian)
        else:
            assert not(self.pending_guardian.valid_at != 0 and new_guardian == self.pending_guardian.value), ErrorsLib.AlreadyPending
            self.pending_guardian.update(new_guardian, self.timelock)
            # TODO: emit event ?
    def submit_cap(self, market_params: MarketParams, new_supply_cap: int, sender = Mixer.ZERO_ADDRESS):
        self._only_curator_role(sender)
        id = market_params.id()
        assert not(market_params.loan_token != self.asset()), ErrorsLib.InconsistentAsset(id)
        assert not(Mixer.contracts_and_eoas[self.MORPHO].last_update(id, self.metadata.address) == 0), ErrorsLib.MarketNotCreated

        supply_cap = self.config[id].cap
        assert not(new_supply_cap == supply_cap), ErrorsLib.AlreadySet

        if new_supply_cap < supply_cap:
            self._set_cap(id, new_supply_cap)
        else:
            assert not(new_supply_cap == self.pending_cap[id].value), ErrorsLib.AlreadyPending
            self.pending_cap[id].update(new_supply_cap, self.timelock)
            # TODO: emit event ?
    def submit_market_removal(self, id: bytes, sender = Mixer.ZERO_ADDRESS):
        self._only_curator_role(sender)
        assert not(self.config[id].removable_at != 0), ErrorsLib.AlreadySet
        assert self.config[id].enabled, ErrorsLib.MarketNotCreated
        self._set_cap(id, 0)
        self.config[id].removable_at = Mixer.block_timestamp(self.metadata.chain) + self.timelock
        # TODO: emit event ?
    def set_supply_queue(self, new_supply_queue: list[bytes], sender = Mixer.ZERO_ADDRESS):
        self._only_allocator_role(sender)
        length = len(new_supply_queue)
        assert not(length > ConstantsLib.MAX_QUEUE_LENGTH), ErrorsLib.MaxQueueLengthExceeded
        for i in range(length):
            assert not(self.config[new_supply_queue[i]].cap == 0), ErrorsLib.MarketNotCreated
        self.supply_queue = new_supply_queue
        # TODO: emit event ?
    def update_withdraw_queue(self, indexes: list[int], sender = Mixer.ZERO_ADDRESS):
        self._only_allocator_role(sender)
        new_length = len(indexes)
        curr_length = len(self.withdraw_queue)

        seen: list[bool] = [False] * curr_length
        new_withdraw_queue = [0] * new_length
        for i in range(new_length):
            prev_index = indexes[i]
            id = self.withdraw_queue[i]
            assert not(seen[prev_index]), ErrorsLib.DuplicateMarket(id)
            seen[prev_index] = True
            new_withdraw_queue[i] = id
        
        for i in range(curr_length):
            if not(seen[i]):
                id = self.withdraw_queue[i]
                assert not(self.config[id].cap != 0), ErrorsLib.InvalidMarketRemovalNonZeroCap(id)

                if Mixer.contracts_and_eoas[self.MORPHO].supply_shares(id, self.metadata.address) != 0:
                    assert not(self.config[id].removable_at == 0), ErrorsLib.InvalidMarketRemovalNonZeroSupply(id)
                    assert not(Mixer.block_timestamp(self.metadata.chain) < self.config[id].removable_at), ErrorsLib.InvalidMarketRemovalTimelockNotElapsed(id)
                self.config[id] = MarketConfig()
        self.withdraw_queue = new_withdraw_queue
    
    def reallocate(self, allocations: list[MarketAllocation], sender = Mixer.ZERO_ADDRESS):
        self._only_allocator_role(sender)
        total_supplied: int = 0
        total_withdrawn: int = 0
        for i in range(len(allocations)):
            allocation: MarketAllocation = allocations[i]
            id = allocation.market_params.id()
            supply_assets, supply_shares, _ = self._accrued_supply_balance(allocation.market_params, id)
            withdrawn = UtilsLib.zero_floor_sub(supply_assets, allocation.assets)

            if withdrawn > 0:
                assert not(allocation.market_params.loan_token != self.asset()), ErrorsLib.InconsistentAsset(id)
                shares: int  = 0

                if allocation.assets == 0:
                    shares = supply_shares
                    withdrawn = 0
                withdrawn_assets, withdrawn_shares = Mixer.contracts_and_eoas[self.MORPHO].withdraw(
                    allocation.market_params,
                    withdrawn,
                    shares,
                    self.metadata.address,
                    self.metadata.address,
                    self.metadata.address
                )
                total_withdrawn += withdrawn_assets
            else:
                supplied_assets = UtilsLib.zero_floor_sub(total_withdrawn, total_supplied) if allocation.assets == 2**256 - 1 else UtilsLib.zero_floor_sub(allocation.assets, supply_assets)
                if supplied_assets == 0: continue
                supply_cap = self.config[id].cap
                assert not(supply_cap == 0), ErrorsLib.UnauthorizedMarket(id)
                assert not(supply_assets + supplied_assets > supply_cap), ErrorsLib.SupplyCapExceeded(id)
                _, supplied_shares = Mixer.contracts_and_eoas[self.MORPHO].supply(
                    allocation.market_params,
                    supplied_assets,
                    0,
                    self.metadata.address,
                    None,
                    self.metadata.address
                )
                total_supplied += supplied_assets
        assert not(total_supplied != total_withdrawn), ErrorsLib.InconsistentReallocation
    
    def revoke_pending_timelock(self, sender = Mixer.ZERO_ADDRESS):
        self._only_guardian_role(sender)
        assert not(self.pending_timelock.valid_at == 0), ErrorsLib.NoPendingValue
        self.pending_timelock = PendingUint192()
    
    def revoke_pending_guardian(self, sender = Mixer.ZERO_ADDRESS):
        self._only_guardian_role(sender)
        self.pending_guardian = PendingAddress()

    def revoke_pending_cap(self, id: bytes, sender = Mixer.ZERO_ADDRESS):
        self._only_curator_or_guardian_role(sender)
        self.pending_cap[id] = PendingUint192()
    
    def revoke_pending_market_removal(self, id: bytes, sender = Mixer.ZERO_ADDRESS):
        self._only_curator_or_guardian_role(sender)
        assert not(self.config[id].removable_at == 0), ErrorsLib.AlreadySet
        self.config[id].removable_at = 0

    def supply_queue_length(self, sender = Mixer.ZERO_ADDRESS) -> int:
        return len(self.supply_queue)
    
    def withdraw_queue_length(self, sender = Mixer.ZERO_ADDRESS) -> int:
        return len(self.withdraw_queue)

    def accept_timelock(self, sender = Mixer.ZERO_ADDRESS):
        self._after_timelock(self.pending_timelock.valid_at)
        self._set_timelock(self.pending_timelock.value)
    
    def accept_guardian(self, sender = Mixer.ZERO_ADDRESS):
        self._after_timelock(self.pending_guardian.valid_at)
        self._set_guardian(self.pending_guardian.value)
    
    def accept_cap(self, id: bytes, sender = Mixer.ZERO_ADDRESS):
        self._after_timelock(self.pending_cap[id].valid_at)
        self._set_cap(id, self.pending_cap[id].value)
    
    def skim(self, token: Address, sender = Mixer.ZERO_ADDRESS):
        assert not(self.skim_recipient == Mixer.ZERO_ADDRESS), ErrorsLib.ZERO_ADDRESS
        amount: int = Mixer.contracts_and_eoas[token].balance_of(self.metadata.address, self.metadata.address)
        Mixer.contracts_and_eoas[token].safe_transfer(self.skim_recipient, amount, self.metadata.address)
    
    def max_deposit(self, thingy: Address, sender = Mixer.ZERO_ADDRESS) -> int:
        return self._max_deposit()
    
    def max_mint(self, thingy: Address, sender = Mixer.ZERO_ADDRESS) -> int:
        suppliable = self._max_deposit()
        return self._convert_to_shares(suppliable, OZMath.Rounding.Floor)

    def max_withdraw(self, owner: Address, sender = Mixer.ZERO_ADDRESS) -> int:
        assets, _, _ = self._max_withdraw(owner)
        return assets
    def max_redeem(self, owner: Address, sender = Mixer.ZERO_ADDRESS) -> int:
        assets, new_total_supply, new_total_assets = self._max_withdraw(owner)
        return self._convert_to_shares_with_totals(assets, new_total_supply, new_total_assets, OZMath.Rounding.Floor)
    def deposit(self, assets: int, receiver: Address, sender = Mixer.ZERO_ADDRESS) -> int:
        new_total_assets = self._accrue_fee()
        self.last_total_assets = new_total_assets
        shares = self._convert_to_shares_with_totals(assets, self.total_supply(), new_total_assets, OZMath.Rounding.Floor)
        self._deposit(sender, receiver, assets, shares)
        return shares
    def mint(self, shares: int, receiver: Address, sender = Mixer.ZERO_ADDRESS) -> int:
        new_total_assets = self._accrue_fee()
        self.last_total_assets = new_total_assets
        assets = self._convert_to_assets_with_totals(shares, self.total_supply(), new_total_assets, OZMath.Rounding.Ceil)
        self._deposit(sender, receiver, assets, shares)
        return assets
    def withdraw(self, assets: int, receiver: Address, owner: Address, sender = Mixer.ZERO_ADDRESS) -> int:
        new_total_assets = self._accrue_fee()
        shares = self._convert_to_shares_with_totals(assets, self.total_supply(), new_total_assets, OZMath.Rounding.Ceil)
        self._update_last_total_assets(UtilsLib.zero_floor_sub(new_total_assets, assets))
        self._withdraw(sender, receiver, owner, assets, shares)
        return shares
    def redeem(self, shares: int, receiver: Address, owner: Address, sender = Mixer.ZERO_ADDRESS) -> int:
        new_total_assets = self._accrue_fee()
        assets = self._convert_to_assets_with_totals(shares, self.total_supply(), new_total_assets, OZMath.Rounding.Floor)
        self._update_last_total_assets(UtilsLib.zero_floor_sub(new_total_assets, assets))
        self._withdraw(sender, receiver, owner, assets, shares)
        return assets
    def total_assets(self) -> int:
        assets = 0
        for i in range(len(self.withdraw_queue)):
            assets += Mixer.contracts_and_eoas[self.MORPHO].expected_supply_assets(self._market_params(self.withdraw_queue[i]), self.metadata.address)
        return assets

    def _decimals_offset(self) -> int:
        return ConstantsLib.DECIMALS_OFFSET
    
    def _max_withdraw(self, owner: Address) -> Tuple[int, int, int]:
        assets, new_total_supply, new_total_assets = 0, 0, 0
        fee_shares = 0
        fee_shares, new_total_assets = self._accrued_fee_shares()
        new_total_supply = self.total_supply() + fee_shares
        assets = self._convert_to_assets_with_totals(self.balance_of(owner), new_total_supply, new_total_assets, OZMath.Rounding.Floor)
        assets -= self._simulate_withdraw_morpho(assets)
        return assets, new_total_supply, new_total_assets
    def _max_deposit(self) -> int:
        total_suppliable = 0
        for i in range(len(self.supply_queue)):
            id = self.supply_queue[i]
            supply_cap = self.config[id].cap
            if supply_cap == 0: continue
            supply_assets = Mixer.contracts_and_eoas[self.MORPHO].expected_supply_assets(self._market_params(id), self.metadata.address)
            total_suppliable += UtilsLib.zero_floor_sub(supply_cap, supply_assets)
        return total_suppliable
    def _convert_to_shares(self, assets: int, rounding: OZMath.Rounding) -> int:
        fee_shares, new_total_assets = self._accrued_fee_shares()
        return self._convert_to_shares_with_totals(assets, self.total_supply() + fee_shares, new_total_assets, rounding)
    def _convert_to_assets(self, shares: int, rounding: OZMath.Rounding) -> int:
        fee_shares, new_total_assets = self._accrued_fee_shares()
        return self._convert_to_assets_with_totals(shares, self.total_supply() + fee_shares, new_total_assets, rounding)
    def _convert_to_shares_with_totals(self, assets: int, new_total_supply: int, new_total_assets: int, rounding: OZMath.Rounding) -> int:
        return OZMath.mul_div(assets, new_total_supply + 10**self._decimals_offset(), new_total_assets + 1, rounding)
    def _convert_to_assets_with_totals(self, shares: int, new_total_supply: int, new_total_assets: int, rounding: OZMath.Rounding) -> int:
        return OZMath.mul_div(shares, new_total_assets + 1, new_total_supply + 10**self._decimals_offset(), rounding)
    def _deposit(self, caller: Address, receiver: Address, assets: int, shares: int):
        super()._deposit(caller, receiver, assets, shares)
        self._supply_morpho(assets)
        self._update_last_total_assets(self.last_total_assets + assets)
    def _withdraw(self, caller: Address, receiver: Address, owner: Address, assets: int, shares: int):
        self._withdraw_morpho(assets)
        super()._withdraw(caller, receiver, owner, assets, shares)
    def _market_params(self, id: bytes) -> MarketParams:
        return Mixer.contracts_and_eoas[self.MORPHO].id_to_market_params(id)
    def _accrued_supply_balance(self, market_params: MarketParams, id: bytes) -> Tuple[int, int, Market]:
        Mixer.contracts_and_eoas[self.MORPHO].accrue_interest(market_params, self.metadata.address)
        market = Mixer.contracts_and_eoas[self.MORPHO].market(id)
        shares = Mixer.contracts_and_eoas[self.MORPHO].supply_shares(id, self.metadata.address)
        assets = SharesMathLib.to_assets_down(shares, market.total_supply_assets, market.total_supply_shares)
        return assets, shares, market
    def _check_timelock_bounds(self, new_timelock: int):
        assert not(new_timelock > ConstantsLib.MAX_TIMELOCK), ErrorsLib.AboveMaxTimelock
        assert not(new_timelock < ConstantsLib.MIN_TIMELOCK), ErrorsLib.BelowMinTimelock
    def _set_timelock(self, new_timelock: int):
        self.timelock = new_timelock
        self.pending_timelock = PendingUint192()
    def _set_guardian(self, new_guardian: Address):
        self.guardian = new_guardian
        self.pending_guardian = PendingAddress()
    def _set_cap(self, id: bytes, supply_cap: int):
        market_config: MarketConfig = self.config[id]
        if supply_cap > 0:
            if not(market_config.enabled):
                self.supply_queue.append(id)
                self.withdraw_queue.appen(id)

                assert not(len(self.supply_queue) > ConstantsLib.MAX_QUEUE_LENGTH), ErrorsLib.MaxQueueLengthExceeded
                self.config[id].enabled = True
            self.config[id].removable_at = 0
        self.config[id].cap = supply_cap
        self.pending_cap[id] = PendingUint192()
        # TODO: emit event ? 
    def _supply_morpho(self, assets: int):
        for i in range(len(self.supply_queue)):
            id = self.supply_queue[i]
            supply_cap = self.config[id].cap
            if supply_cap == 0: continue
            market_params = self._market_params(id)
            supply_assets,_,_ = self._accrued_supply_balance(market_params, id)
            to_supply = UtilsLib.min(UtilsLib.zero_floor_sub(supply_cap, supply_assets), assets)
            if to_supply > 0:
                Mixer.contracts_and_eoas[self.MORPHO].supply(
                    market_params,
                    to_supply,
                    0,
                    self.metadata.address,
                    None,
                    self.metadata.address
                )
                assets -= to_supply
            if assets == 0: return
        assert not(assets != 0), ErrorsLib.AllCapsReached
    
    def _withdraw_morpho(self, assets: int):
        for i in range(len(self.withdraw_queue)):
            id = self.withdraw_queue[i]
            market_params = self._market_params(id)
            supply_assets, _, market = self._accrued_supply_balance(market_params, id)
            to_withdraw = UtilsLib.min(
                self._withdrawble(market_params, market.total_supply_assets, market.total_borrow_assets, supply_assets),
                assets
            )
            if to_withdraw > 0:
                Mixer.contracts_and_eoas[self.MORPHO].withdraw(
                    market_params,
                    to_withdraw,
                    0,
                    self.metadata.address,
                    self.metadata.address,
                    self.metadata.address
                )
                assets -= to_withdraw
            if assets == 0: return
        assert not(assets != 0), ErrorsLib.NotEnoughLiquidity
    def _simulate_withdraw_morpho(self, assets: int) -> int:
        for i in range(len(self.withdraw_queue)):
            id = self.withdraw_queue[i]
            market_params = self._market_params(id)
            supply_shares = Mixer.contracts_and_eoas[self.MORPHO].supply_shares(id, self.metadata.address)
            total_supply_assets, total_supply_shares, total_borrow_assets, _ = Mixer.contracts[self.MORPHO].expected_market_balances(market_params)

            assets = UtilsLib.zero_floor_sub(
                assets,
                self._withdrawable(
                    market_params,
                    total_supply_assets,
                    total_borrow_assets,
                    SharesMathLib.to_assets_down(supply_shares, total_supply_assets, total_supply_shares)
                )
            )
            if assets == 0: break
        return assets
    def _withdrawable(self, market_params: MarketParams, total_supply_assets: int, total_borrow_assets: int, supply_assets: int) -> int:
        available_liquidity = UtilsLib.min(
            total_supply_assets - total_borrow_assets, Mixer.contracts_and_eoas[market_params.loan_token].balance_of(self.MORPHO)
        )
        return UtilsLib.min(supply_assets, available_liquidity)
    def _update_last_total_assets(self, updated_total_assets: int):
        last_total_assets = updated_total_assets
        # TODO: emit event ?
    def _accrue_fee(self) -> int:
        fee_shares = 0
        fee_shares, new_total_assets = self._accrued_fee_shares()
        if fee_shares != 0: self._mint(self.fee_recipient, fee_shares)
        # TODO: emit event ?
    def _accrued_fee_shares(self) -> Tuple[int, int]:
        fee_shares = 0,
        new_total_assets = 0

        new_total_assets = self.total_assets()
        total_interest = UtilsLib.zero_floor_sub(
            new_total_assets,
            self.last_total_assets
        )
        if total_interest != 0 and self.fee != 0:
            fee_assets = OZMath.mul_div(total_interest, self.fee, WAD)
            fee_shares = self._convert_to_shares_with_totals(fee_assets, self.total_supply(), new_total_assets - fee_assets, OZMath.Rounding.Floor)
    

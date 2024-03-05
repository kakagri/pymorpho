from pymorpho.utils.Mixer import Mixer, Metadata, Address, ChainID, InstanceType
from pymorpho.adaptivecurveirm.libraries.adaptivecurve.exp_lib import ExpLib
from pymorpho.adaptivecurveirm.libraries.math_lib import MathLib 
from pymorpho.adaptivecurveirm.libraries.utils_lib import UtilsLib
from pymorpho.blue.libraries.math_lib import MathLib as MorphoMathLib, WAD
from pymorpho.blue.types import MarketParams, Market
from pymorpho.adaptivecurveirm.libraries.errors_lib import ErrorsLib
from pymorpho.adaptivecurveirm.libraries.adaptivecurve.constants_lib import ConstantsLib
from collections import defaultdict
from typing import Tuple


class AdaptiveCurveIRM:
    def __init__(
        self,
        morpho: Address,
        metadata: Metadata = Metadata(
            ChainID.ETH_MAINNET,
            Address.ZERO_ADDRESS,
            "AdaptiveCurveIRM",
            InstanceType.CONTRACT,
        ),
        sender=Mixer.ZERO_ADDRESS,
    ):
        self.MORPHO: Address = Mixer.ZERO_ADDRESS
        self.rate_at_target: defaultdict[bytes, int] = defaultdict(int)

        assert morpho != Mixer.ZERO_ADDRESS, ErrorsLib.ZERO_ADDRESS

        self.MORPHO = morpho

        # utility stuff for simualtion
        self.metadata = metadata
    
    def deploy(self) -> Address:
        self.metadata.address = Mixer.register(self)
        return self.metadata.address

    def borrow_rate_view(
        self, market_params: MarketParams, market: Market, sender=Mixer.ZERO_ADDRESS
    ) -> int:
        avg_rate, _ = self._borrow_rate(market_params.id(), market)
        return avg_rate

    def borrow_rate(
        self, market_params: MarketParams, market: Market, sender=Mixer.ZERO_ADDRESS
    ) -> int:
        assert sender == self.MORPHO, ErrorsLib.NOT_MORPHO

        id = market_params.id()
        avg_rate, end_rate_at_target = self._borrow_rate(id, market)
        self.rate_at_target[id] = end_rate_at_target

        # TODO: emit event ?

        return avg_rate

    def _borrow_rate(self, id: bytes, market: Market) -> Tuple[int, int]:
        utilization = (
            MorphoMathLib.w_div_down(market.total_borrow_assets, market.total_supply_assets)
            if market.total_supply_assets > 0
            else 0
        )
        err_norm_factor = (
            WAD - ConstantsLib.TARGET_UTILIZATION
            if utilization > ConstantsLib.TARGET_UTILIZATION
            else ConstantsLib.TARGET_UTILIZATION
        )
        err = MathLib.w_div_to_zero(utilization - ConstantsLib.TARGET_UTILIZATION, err_norm_factor)
        start_rate_at_target = self.rate_at_target[id]

        avg_rate_at_target = 0
        end_rate_at_target = 0

        if start_rate_at_target == 0:
            avg_rate_at_target = ConstantsLib.INITIAL_RATE_AT_TARGET
            end_rate_at_target = ConstantsLib.INITIAL_RATE_AT_TARGET
        else:
            speed = MathLib.w_mul_to_zero(ConstantsLib.ADJUSTMENT_SPEED, err)
            elapsed = Mixer.block_timestamp(self.metadata.chain) - market.last_update
            linear_adaptation = speed * elapsed

            if linear_adaptation == 0:
                avg_rate_at_target = start_rate_at_target
                end_rate_at_target = start_rate_at_target
            else:
                end_rate_at_target = self._new_rate_at_target(
                    start_rate_at_target, linear_adaptation
                )
                mid_rate_at_target = self._new_rate_at_target(
                    start_rate_at_target, linear_adaptation // 2
                )
                avg_rate_at_target = (
                    start_rate_at_target + end_rate_at_target + 2 * mid_rate_at_target
                ) // 4

        return self._curve(avg_rate_at_target, err), end_rate_at_target

    def _curve(self, _rate_at_target, err) -> int:
        coeff = (
            WAD - MathLib.w_div_to_zero(WAD, ConstantsLib.CURVE_STEEPNESS)
            if err < 0
            else ConstantsLib.CURVE_STEEPNESS - WAD
        )
        return MathLib.w_mul_to_zero(
            MathLib.w_mul_to_zero(coeff, err) + WAD, 
            _rate_at_target
        )

    def _new_rate_at_target(self, start_rate_at_target, linear_adaptation) -> int:
        return UtilsLib.bound(
            MathLib.w_mul_to_zero(start_rate_at_target, ExpLib.w_exp(linear_adaptation)),
            ConstantsLib.MIN_RATE_AT_TARGET,
            ConstantsLib.MAX_RATE_AT_TARGET,
        )




class StaticAdaptiveCurveIRM:

    @staticmethod
    def borrow_rate_view(
        market: Market,
        rate_at_target: int,
        current_timestamp: int
    ) -> int:
        avg_rate, _ = StaticAdaptiveCurveIRM._borrow_rate(
            market, 
            rate_at_target,
            current_timestamp
        )
        return avg_rate

    @staticmethod
    def borrow_rate(
        market_params: MarketParams, 
        market: Market,
        rate_at_target: int,
        current_timestamp: int
    ) -> int:

        id = market_params.id()
        avg_rate, end_rate_at_target = StaticAdaptiveCurveIRM._borrow_rate(
            id, 
            market,
            rate_at_target,
            current_timestamp
        )

        # TODO: emit event ?

        return avg_rate

    @staticmethod
    def _borrow_rate(
        market: Market,
        rate_at_target: int,
        current_timestamp: int
    ) -> Tuple[int, int]:
        utilization = (
            MorphoMathLib.w_div_down(market.total_borrow_assets, market.total_supply_assets)
            if market.total_supply_assets > 0
            else 0
        )
        err_norm_factor = (
            WAD - ConstantsLib.TARGET_UTILIZATION
            if utilization > ConstantsLib.TARGET_UTILIZATION
            else ConstantsLib.TARGET_UTILIZATION
        )
        err = MathLib.w_div_to_zero(utilization - ConstantsLib.TARGET_UTILIZATION, err_norm_factor)
        start_rate_at_target = rate_at_target

        avg_rate_at_target = 0
        end_rate_at_target = 0

        if start_rate_at_target == 0:
            avg_rate_at_target = ConstantsLib.INITIAL_RATE_AT_TARGET
            end_rate_at_target = ConstantsLib.INITIAL_RATE_AT_TARGET
        else:
            speed = MathLib.w_mul_to_zero(ConstantsLib.ADJUSTMENT_SPEED, err)
            elapsed = current_timestamp - market.last_update
            linear_adaptation = speed * elapsed

            if linear_adaptation == 0:
                avg_rate_at_target = start_rate_at_target
                end_rate_at_target = start_rate_at_target
            else:
                end_rate_at_target = StaticAdaptiveCurveIRM._new_rate_at_target(
                    start_rate_at_target, linear_adaptation
                )
                mid_rate_at_target = StaticAdaptiveCurveIRM._new_rate_at_target(
                    start_rate_at_target, linear_adaptation // 2
                )
                avg_rate_at_target = (
                    start_rate_at_target + end_rate_at_target + 2 * mid_rate_at_target
                ) // 4

        return StaticAdaptiveCurveIRM._curve(avg_rate_at_target, err), end_rate_at_target

    @staticmethod
    def _curve(_rate_at_target, err) -> int:
        coeff = (
            WAD - MathLib.w_div_to_zero(WAD, ConstantsLib.CURVE_STEEPNESS)
            if err < 0
            else ConstantsLib.CURVE_STEEPNESS - WAD
        )
        return MathLib.w_mul_to_zero(
            MathLib.w_mul_to_zero(coeff, err) + WAD, 
            _rate_at_target
        )
    
    @staticmethod
    def _new_rate_at_target(
        start_rate_at_target, linear_adaptation
    ) -> int:
        return UtilsLib.bound(
            MathLib.w_mul_to_zero(start_rate_at_target, ExpLib.w_exp(linear_adaptation)),
            ConstantsLib.MIN_RATE_AT_TARGET,
            ConstantsLib.MAX_RATE_AT_TARGET,
        )

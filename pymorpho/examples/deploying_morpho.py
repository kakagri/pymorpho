from pymorpho.utils.Mixer import Mixer, Address, ChainID, Metadata, InstanceType
from pymorpho.blue.morpho_blue import MorphoBlue
from pymorpho.adaptivecurveirm.adaptive_curve_irm import AdaptiveCurveIRM
from pymorpho.mocks.token import Token
from pymorpho.examples.params_morpho import ParamsMorpho
from pymorpho.mocks.mock_oracle import MockOracle
from pymorpho.metamorpho.metamorpho import MetaMorpho
from pymorpho.blue.types import Market, MarketParams
import time


blue_owner: Address = Address.new()
metamorpho_owner: Address = Address.new()
account_1: Address = Address.new()

INITIAL_TIMESTAMP: int = 1701841124

Mixer.set_block_timestamp(INITIAL_TIMESTAMP)

# deploying tokens

usdc = Token(
    "Circle USD",
    "USDC",
    6,
    Metadata(ChainID.ETH_MAINNET, Mixer.ZERO_ADDRESS, "Mock USDC", InstanceType.CONTRACT),
    blue_owner
).deploy()

usdt = Token(
    "Tether USD",
    "USDT",
    6,
    Metadata(ChainID.ETH_MAINNET, Mixer.ZERO_ADDRESS, "Mock USDT", InstanceType.CONTRACT),
    blue_owner
).deploy()

weth = Token("Wrapped Ether", "WETH", 18, Metadata(ChainID.ETH_MAINNET, Mixer.ZERO_ADDRESS, "Mock WETH", InstanceType.CONTRACT), blue_owner).deploy()


# deploying mock oracles
weth_usdc = MockOracle(
    Metadata(ChainID.ETH_MAINNET, Mixer.ZERO_ADDRESS, "Mock WETH/USDC Oracle", InstanceType.CONTRACT),
    blue_owner
).deploy()

usdt_usdc = MockOracle(
    Metadata(ChainID.ETH_MAINNET, Mixer.ZERO_ADDRESS, "Mock USDT/USDC Oracle", InstanceType.CONTRACT),
    blue_owner
).deploy()


# setting the prices in the oracles, ORACLE PRICE_SCALE = 10**36
# meaning if the price of eth in usdc must me be in 10**36 lol

Mixer.contracts_and_eoas[weth_usdc].set_price( 2_320 * 10**36)
Mixer.contracts_and_eoas[usdt_usdc].set_price( 999 * 10**33)


# deploying morpho blue

morpho_blue = MorphoBlue(
    blue_owner,
    Metadata(
        ChainID.ETH_MAINNET,
        Mixer.ZERO_ADDRESS,
        "MorphoBlueExample",
        InstanceType.CONTRACT
    ),
    blue_owner
).deploy()

# deploying adaptive curve irm

adaptive_curve_irm = AdaptiveCurveIRM(
    morpho_blue,
    ParamsMorpho.CURVE_STEEPNESS,
    ParamsMorpho.ADJUSTMENT_SPEED,
    ParamsMorpho.TARGET_UTILIZATION,
    ParamsMorpho.INITIAL_RATE_AT_TARGET,
    Metadata(
        ChainID.ETH_MAINNET,
        Mixer.ZERO_ADDRESS,
        "AdaptiveCurveIRMExample",
        InstanceType.CONTRACT
    )
).deploy()

# LLTVs

LLTVs = [
    90* 10**16, # 90%
    87* 10**16, # 87%
    80* 10**16, # 80%
    70* 10**16, # 70%
    60* 10**16 # 60%
]


# enabling lltvs

for lltv in LLTVs:
    Mixer.contracts_and_eoas[morpho_blue].enable_lltv(
        lltv,
        blue_owner
    )
# enabling irm

Mixer.contracts_and_eoas[morpho_blue].enable_irm(
    adaptive_curve_irm,
    blue_owner
)

# market params
params_usdt_usdc = MarketParams(
    usdc,
    usdt,
    usdt_usdc,
    adaptive_curve_irm,
    LLTVs[0]
)
params_weth_usdc = MarketParams(
    usdc,
    weth,
    weth_usdc,
    adaptive_curve_irm,
    LLTVs[0]
)

# creating markets
Mixer.contracts_and_eoas[morpho_blue].create_market(
    params_usdt_usdc,
    account_1
)


Mixer.contracts_and_eoas[morpho_blue].create_market(
    params_weth_usdc,
    account_1
)


# giving some tokens
Mixer.contracts_and_eoas[usdc].mint(account_1, 1_500 * 10**6)
Mixer.contracts_and_eoas[usdc].mint(blue_owner, 1_500 * 10**6)
Mixer.contracts_and_eoas[usdc].mint(metamorpho_owner, 1_500 * 10**6)

Mixer.contracts_and_eoas[usdt].mint(account_1, 1_500 * 10**6)
Mixer.contracts_and_eoas[usdt].mint(blue_owner, 1_500 * 10**6)
Mixer.contracts_and_eoas[usdt].mint(metamorpho_owner, 1_500 * 10**6)

Mixer.contracts_and_eoas[weth].mint(account_1, 1_500 * 10**18)
Mixer.contracts_and_eoas[weth].mint(blue_owner, 1_500 * 10**18)
Mixer.contracts_and_eoas[weth].mint(metamorpho_owner, 1_500 * 10**18)



# deploying MetaMorpho

metamorpho = MetaMorpho(
    metamorpho_owner,
    morpho_blue,
    ParamsMorpho.TIMELOCK,
    usdc,
    "Flagship USDC",
    "fUSDC",
    Metadata(ChainID.ETH_MAINNET, Mixer.ZERO_ADDRESS, "MetaMorpho USDC Example", InstanceType.CONTRACT),
    metamorpho_owner
).deploy()



# let's visualise addresses

for x, y in Mixer.contracts_and_eoas.items():
    print(f"{x}: {y}")

# approving metamorpho vault

Mixer.contracts_and_eoas[usdc].approve(metamorpho, 2**256 - 1, account_1)
Mixer.contracts_and_eoas[usdc].approve(metamorpho, 2**256 - 1, blue_owner)
Mixer.contracts_and_eoas[usdc].approve(metamorpho, 2**256 - 1, metamorpho_owner)

# submitting 

Mixer.contracts_and_eoas[metamorpho].submit_cap(
    params_usdt_usdc,
    1_000_000 * 10**6,
    metamorpho_owner
)

Mixer.contracts_and_eoas[metamorpho].submit_cap(
    params_weth_usdc,
    1_000_000 * 10**6,
    metamorpho_owner
)
# jumping by timelock

Mixer.set_block_timestamp(Mixer.block_timestamp() + ParamsMorpho.TIMELOCK + 1)
# approving caps

Mixer.contracts_and_eoas[metamorpho].accept_cap(
    params_usdt_usdc.id(),
)

Mixer.contracts_and_eoas[metamorpho].accept_cap(
    params_weth_usdc.id()
)

# updating supply queue ? 

# depositing on MetaMorpho
Mixer.contracts_and_eoas[metamorpho].deposit(
    1_000* 10**6,
    account_1,
    account_1
)

expected_shares = 1_000* 10**6 * (0 + 10**6) // (0 + 1)
assert Mixer.contracts_and_eoas[metamorpho].balance_of(account_1) == expected_shares, f"Deposit failed {Mixer.contracts_and_eoas[metamorpho].balance_of(account_1)}"

Mixer.contracts_and_eoas[metamorpho].deposit(
    1_300* 10**6,
    blue_owner,
    blue_owner
)

new_total_assets = 10**9
total_supply = expected_shares

expected_shares_blue_owner = 1_300 * 10**6 * (expected_shares + 10**6) // (new_total_assets + 1)
print(f"expected_shares_blue_owner: {expected_shares_blue_owner}")
assert Mixer.contracts_and_eoas[metamorpho].balance_of(blue_owner) == expected_shares_blue_owner, "math is wrong ?"

print(Mixer.contracts_and_eoas[morpho_blue].market(
    params_usdt_usdc.id(),
))

print(Mixer.contracts_and_eoas[morpho_blue].market(
    params_weth_usdc.id()
))

# supplying collateral to borrow usdc 
Mixer.contracts_and_eoas[usdt].approve(morpho_blue, 2**256 - 1, account_1)

Mixer.contracts_and_eoas[morpho_blue].supply_collateral(
    params_usdt_usdc,
    1_000 * 10**6,
    account_1, 
    None,
    account_1
)

print(f" account 1 usdc balance before borrow: {Mixer.contracts_and_eoas[usdc].balance_of(account_1)}")

Mixer.contracts_and_eoas[morpho_blue].borrow(
    params_usdt_usdc,
    895 * 10**6,
    0,
    account_1,
    account_1,
    account_1
)

print(f" account 1 usdc balance after borrow: {Mixer.contracts_and_eoas[usdc].balance_of(account_1)}")
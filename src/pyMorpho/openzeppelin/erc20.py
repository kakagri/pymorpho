from pymorpho.utils.Mixer import Mixer, Metadata, Address, ChainID, InstanceType
from collections import defaultdict
from typing import Tuple
from abc import ABC, abstractmethod


class ERC20(ABC):
    def __init__(
        self,
        name_: str,
        symbol_: str,
        metadata: Metadata = Metadata(ChainID.ETH_MAINNET, Address.ZERO_ADDRESS, "ERC20", InstanceType.CONTRACT),
        sender: Address = Mixer.ZERO_ADDRESS
    ):
        self._balances: defaultdict[Address, int] = defaultdict(int)
        self._allowances: defaultdict[Tuple[Address, Address], int] = defaultdict(int)
        self._total_supply: int = 0
        self._name: str = ""
        self._symbol: str = ""

        self._name = name_
        self._symbol = symbol_

        # Mixer utilities
        self.metadata = metadata
        self.metadata.address = Mixer.register(self)

    def name(self) -> str: self._name
    def symbol(self) -> str: self._symbol
    def decimals(self) -> int: return 18
    def total_supply(self) -> int: return self._total_supply
    def balance_of(self, account: Address, sender: Mixer.ZERO_ADDRESS) -> int: return self._balances[account]
    
    def transfer(self, to: Address, amount: int, sender: Address = Mixer.ZERO_ADDRESS) -> bool:
        self._transfer(sender, to, amount)
        return True
    def allowance(self, owner: Address, spender: Address, sender: Mixer.ZERO_ADDRESS) -> int:
        return self._allowances[(owner, spender)]
    def approve(self, spender: Address, amount: int, sender: Address = Mixer.ZERO_ADDRESS) -> bool:
        self._approve(sender, spender, amount)
        return True
    def transfer_from(self, from_: Address, to: Address, amount: int, sender: Address = Mixer.ZERO_ADDRESS) -> bool:
        spender = sender
        self._spend_allowance(from_, sender, amount)
        self._transfer(from_, to, amount)
        return True
    def increase_allowance(self, spender: Address, added_value: int, sender: Address = Mixer.ZERO_ADDRESS) -> bool:
        self._approve(sender, spender, self.allowance(sender, spender) + added_value)
        return True
    def decrease_allowance(self, spender: Address, substracted_value: int, sender: Address = Mixer.ZERO_ADDRESS) -> bool:
        current_allowance = self.allowance(sender, spender)
        assert current_allowance >= substracted_value, "ERC20: decreased allowance below zero"
        self._approve(sender, spender, current_allowance - substracted_value)
        return True
    def _transfer(self, from_: Address, to: Address, amount: int):
        assert from_ != Address.ZERO_ADDRESS, "ERC20: transfer from the zero address"
        assert to != Address.ZERO_ADDRESS, "ERC20: transfer to the zero address"
        self._update(from_, to, amount)
    def _update(self, from_: Address, to: Address, amount: int):
        if from_ == Mixer.ZERO_ADDRESS:
            self._total_supply += amount
        else:
            from_balance = self._balances[from_]
            assert from_balance >= amount, "ERC20: transfer amount exceeds balance"
            self._balances[from_] = from_balance - amount
        
        if to == Mixer.ZERO_ADDRESS:
            self._total_supply -= amount
        else:
            self._balances[to] += amount
        
        # TODO: emit event ? 
    
    def _mint(self, account: Address, amount: int):
        assert account != Address.ZERO_ADDRESS, "ERC20: mint to the zero address"
        self._update(Mixer.ZERO_ADDRESS, account, amount)
    
    def _burn(self, account: Address, amount: int):
        assert account != Address.ZERO_ADDRESS, "ERC20: burn from the zero address"
        self._update(account, Mixer.ZERO_ADDRESS, amount)
    
    def _approve(self, owner: Address, spender: Address, amount: int):
        assert owner != Address.ZERO_ADDRESS, "ERC20: approve from the zero address"
        assert spender != Address.ZERO_ADDRESS, "ERC20: approve to the zero address"
        self._allowances[(owner, spender)] = amount
        # TODO: emit event ?
    
    def _spend_allowance(self, owner: Address, spender: Address, amount: int):
        current_allowance = self.allowance(owner, spender)
        if current_allowance != 2**256 - 1:
            assert current_allowance >= amount, "ERC20: insufficient allowance"
            self._approve(owner, spender, current_allowance - amount)
        
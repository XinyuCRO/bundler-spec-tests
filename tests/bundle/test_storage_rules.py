import collections
import re

import pytest
from tests.types import UserOperation, RPCErrorCode
from tests.utils import (
    assert_ok,
    assert_rpc_error,
    deploy_wallet_contract,
    deploy_state_contract,
    deploy_contract,
    get_sender_address,
    deploy_and_deposit,
    deposit_to_undeployed_sender,
    staked_contract
)


def assert_unstaked_error(response):
    assert_rpc_error(response, response.message, RPCErrorCode.INAVLID_PAYMASTER_STAKE)

def assert_opcode_error(response):
    assert_rpc_error(response, response.message, RPCErrorCode.BANNED_OPCODE)

def deploy_unstaked_factory(w3, entrypoint_contract):
    return deploy_contract(
            w3,
            "TestRulesFactory",
            ctrparams=[entrypoint_contract.address],
        )

def deploy_staked_rule_factory(w3, entrypoint_contract):
    contract = deploy_contract(
        w3,
        "TestRulesAccountFactory",
        ctrparams=[entrypoint_contract.address]
    )
    return staked_contract(w3, entrypoint_contract, contract)

def deploy_staked_factory(w3, entrypoint_contract):
    return deploy_and_deposit(
        w3, entrypoint_contract, "TestRulesFactory", True
    )


def with_initcode(build_userop_func, deploy_factory_func = deploy_unstaked_factory):
    def _with_initcode(w3, entrypoint_contract, contract, rule):
        factory_contract = deploy_factory_func(w3, entrypoint_contract)
        userop = build_userop_func(w3, entrypoint_contract, contract, rule)
        initcode = (
            factory_contract.address
            + factory_contract.functions.create(
                123, "", entrypoint_contract.address
            ).build_transaction()["data"][2:]
        )
        sender = deposit_to_undeployed_sender(w3, entrypoint_contract, initcode)
        userop.sender = sender
        userop.initCode = initcode
        userop.verificationGasLimit = hex(3000000)
        return userop

    return _with_initcode


def build_userop_for_paymaster(w3, _entrypoint_contract, paymaster_contract, rule):
    wallet = deploy_wallet_contract(w3)
    paymaster_and_data = paymaster_contract.address + rule.encode().hex()
    return UserOperation(sender=wallet.address, paymasterAndData=paymaster_and_data)


def build_userop_for_sender(w3, _entrypoint_contract, rules_account_contract, rule):
    call_data = deploy_state_contract(w3).address
    signature = "0x" + rule.encode().hex()
    return UserOperation(
        sender=rules_account_contract.address, callData=call_data, signature=signature
    )


def build_userop_for_factory(w3, entrypoint_contract, factory_contract, rule):
    initcode = (
        factory_contract.address
        + factory_contract.functions.create(
            123, rule, entrypoint_contract.address
        ).build_transaction()["data"][2:]
    )
    sender = get_sender_address(w3, initcode)
    tx_hash = entrypoint_contract.functions.depositTo(sender).transact(
        {"value": 10**18, "from": w3.eth.accounts[0]}
    )
    w3.eth.wait_for_transaction_receipt(tx_hash)
    return UserOperation(sender=sender, initCode=initcode)


STAKED = True
UNSTAKED = False
PAYMASTER = "TestRulesPaymaster"
FACTORY = "TestRulesFactory"
SENDER = "TestRulesAccount"
AGGREGATOR = "TestRulesAggregator"

StorageTestCase = collections.namedtuple(
    "StorageTestCase", ["rule", "staked", "entity", "userop_build_func", "assert_func"]
)
cases = [
    # unstaked paymaster
    StorageTestCase(
        "no_storage", UNSTAKED, PAYMASTER, build_userop_for_paymaster, assert_ok
    ),
    StorageTestCase(
        "storage", UNSTAKED, PAYMASTER, build_userop_for_paymaster, assert_unstaked_error
    ),
    StorageTestCase(
        "reference_storage",
        UNSTAKED,
        PAYMASTER,
        build_userop_for_paymaster,
        assert_unstaked_error,
    ),
    StorageTestCase(
        "reference_storage_struct",
        UNSTAKED,
        PAYMASTER,
        build_userop_for_paymaster,
        assert_unstaked_error,
    ),
    StorageTestCase(
        "account_storage", UNSTAKED, PAYMASTER, build_userop_for_paymaster, assert_ok
    ),
    StorageTestCase(
        "account_reference_storage",
        UNSTAKED,
        PAYMASTER,
        build_userop_for_paymaster,
        assert_ok,
    ),
    StorageTestCase(
        "account_reference_storage_struct",
        UNSTAKED,
        PAYMASTER,
        build_userop_for_paymaster,
        assert_ok,
    ),
    StorageTestCase(
        "account_reference_storage_init_code",
        UNSTAKED,
        PAYMASTER,
        with_initcode(build_userop_for_paymaster),
        assert_unstaked_error,
    ),
    StorageTestCase(
        "context", UNSTAKED, PAYMASTER, build_userop_for_paymaster, assert_unstaked_error
    ),
    StorageTestCase(
        "external_storage",
        UNSTAKED,
        PAYMASTER,
        build_userop_for_paymaster,
        assert_opcode_error,
    ),
    # staked paymaster
    StorageTestCase(
        "no_storage", STAKED, PAYMASTER, build_userop_for_paymaster, assert_ok
    ),
    StorageTestCase(
        "storage", STAKED, PAYMASTER, build_userop_for_paymaster, assert_ok
    ),
    StorageTestCase(
        "reference_storage", STAKED, PAYMASTER, build_userop_for_paymaster, assert_ok
    ),
    StorageTestCase(
        "reference_storage_struct",
        STAKED,
        PAYMASTER,
        build_userop_for_paymaster,
        assert_ok,
    ),
    StorageTestCase(
        "account_storage", STAKED, PAYMASTER, build_userop_for_paymaster, assert_ok
    ),
    StorageTestCase(
        "account_reference_storage",
        STAKED,
        PAYMASTER,
        build_userop_for_paymaster,
        assert_ok,
    ),
    StorageTestCase(
        "account_reference_storage_struct",
        STAKED,
        PAYMASTER,
        build_userop_for_paymaster,
        assert_ok,
    ),
    StorageTestCase(
        "account_reference_storage_init_code",
        STAKED,
        PAYMASTER,
        # FACTORY MUST BE STAKED TO USE ASSOCIATED STORAGE
        with_initcode(build_userop_for_paymaster, deploy_staked_factory),
        assert_ok,
    ),
    StorageTestCase(
        "context", STAKED, PAYMASTER, build_userop_for_paymaster, assert_ok
    ),
    StorageTestCase(
        "external_storage", STAKED, PAYMASTER, build_userop_for_paymaster, assert_opcode_error
    ),
    # unstaked factory
    StorageTestCase(
        "no_storage", UNSTAKED, FACTORY, build_userop_for_factory, assert_ok
    ),
    StorageTestCase(
        "storage", UNSTAKED, FACTORY, build_userop_for_factory, assert_unstaked_error
    ),
    StorageTestCase(
        "reference_storage", UNSTAKED, FACTORY, build_userop_for_factory, assert_unstaked_error
    ),
    StorageTestCase(
        "reference_storage_struct",
        UNSTAKED,
        FACTORY,
        build_userop_for_factory,
        assert_unstaked_error,
    ),
    StorageTestCase(
        "account_storage", UNSTAKED, FACTORY, build_userop_for_factory, assert_ok
    ),
    StorageTestCase(
        "account_reference_storage",
        UNSTAKED,
        FACTORY,
        build_userop_for_factory,
        assert_unstaked_error,
    ),
    StorageTestCase(
        "account_reference_storage_struct",
        UNSTAKED,
        FACTORY,
        build_userop_for_factory,
        assert_unstaked_error,
    ),
    StorageTestCase(
        "external_storage", UNSTAKED, FACTORY, build_userop_for_factory, assert_opcode_error
    ),
    StorageTestCase(
        "EXTCODEx_CALLx_undeployed_sender",
        UNSTAKED,
        FACTORY,
        build_userop_for_factory,
        assert_ok,
    ),
    StorageTestCase(
        "EXTCODESIZE_undeployed_contract",
        UNSTAKED,
        FACTORY,
        build_userop_for_factory,
        assert_opcode_error,
    ),
    StorageTestCase(
        "EXTCODEHASH_undeployed_contract",
        UNSTAKED,
        FACTORY,
        build_userop_for_factory,
        assert_opcode_error,
    ),
    StorageTestCase(
        "EXTCODECOPY_undeployed_contract",
        UNSTAKED,
        FACTORY,
        build_userop_for_factory,
        assert_opcode_error,
    ),
    StorageTestCase(
        "CALL_undeployed_contract",
        UNSTAKED,
        FACTORY,
        build_userop_for_factory,
        assert_opcode_error,
    ),
    StorageTestCase(
        "CALLCODE_undeployed_contract",
        UNSTAKED,
        FACTORY,
        build_userop_for_factory,
        assert_opcode_error,
    ),
    StorageTestCase(
        "DELEGATECALL_undeployed_contract",
        UNSTAKED,
        FACTORY,
        build_userop_for_factory,
        assert_opcode_error,
    ),
    StorageTestCase(
        "STATICCALL_undeployed_contract",
        UNSTAKED,
        FACTORY,
        build_userop_for_factory,
        assert_opcode_error,
    ),
    # staked factory
    StorageTestCase("no_storage", STAKED, FACTORY, build_userop_for_factory, assert_ok),
    StorageTestCase("storage", STAKED, FACTORY, build_userop_for_factory, assert_ok),
    StorageTestCase(
        "reference_storage", STAKED, FACTORY, build_userop_for_factory, assert_ok
    ),
    StorageTestCase(
        "reference_storage_struct", STAKED, FACTORY, build_userop_for_factory, assert_ok
    ),
    StorageTestCase(
        "account_storage", STAKED, FACTORY, build_userop_for_factory, assert_ok
    ),
    StorageTestCase(
        "account_reference_storage",
        STAKED,
        FACTORY,
        build_userop_for_factory,
        assert_ok,
    ),
    StorageTestCase(
        "account_reference_storage_struct",
        STAKED,
        FACTORY,
        build_userop_for_factory,
        assert_ok,
    ),
    StorageTestCase(
        "external_storage", STAKED, FACTORY, build_userop_for_factory, assert_opcode_error
    ),
    # unstaked sender
    StorageTestCase("no_storage", UNSTAKED, SENDER, build_userop_for_sender, assert_ok),
    StorageTestCase(
        "account_storage", UNSTAKED, SENDER, build_userop_for_sender, assert_ok
    ),
    StorageTestCase(
        "account_reference_storage",
        UNSTAKED,
        SENDER,
        build_userop_for_sender,
        assert_ok,
    ),
    StorageTestCase(
        "account_reference_storage_init_code",
        UNSTAKED,
        SENDER,
        with_initcode(build_userop_for_sender),
        assert_unstaked_error,
    ),

    StorageTestCase(
        "account_reference_storage_init_code",
        UNSTAKED,
        SENDER,
        with_initcode(build_userop_for_sender, deploy_staked_rule_factory),
        assert_ok,
    ),
    StorageTestCase(
        "account_reference_storage_init_code",
        UNSTAKED,
        PAYMASTER,
        with_initcode(build_userop_for_paymaster, deploy_staked_rule_factory),
        # Factory is staked, associated storage reference is allowed
        assert_ok,
    ),

    StorageTestCase(
        "account_reference_storage_struct",
        UNSTAKED,
        SENDER,
        build_userop_for_sender,
        assert_ok,
    ),
    StorageTestCase(
        "external_storage", UNSTAKED, SENDER, build_userop_for_sender, assert_opcode_error
    ),
    # staked sender
    StorageTestCase("no_storage", STAKED, SENDER, build_userop_for_sender, assert_ok),
    StorageTestCase(
        "account_storage", STAKED, SENDER, build_userop_for_sender, assert_ok
    ),
    StorageTestCase(
        "account_reference_storage", STAKED, SENDER, build_userop_for_sender, assert_ok
    ),
    StorageTestCase(
        "account_reference_storage_struct",
        STAKED,
        SENDER,
        build_userop_for_sender,
        assert_ok,
    ),
    StorageTestCase(
        "external_storage", STAKED, SENDER, build_userop_for_sender, assert_opcode_error
    ),
    StorageTestCase(
        "entryPoint_call_balanceOf",
        UNSTAKED,
        SENDER,
        build_userop_for_sender,
        assert_opcode_error,
    ),
    StorageTestCase(
        "eth_value_transfer_forbidden",
        UNSTAKED,
        SENDER,
        build_userop_for_sender,
        assert_opcode_error,
    ),
    StorageTestCase(
        "eth_value_transfer_entryPoint",
        UNSTAKED,
        SENDER,
        build_userop_for_sender,
        assert_ok,
    ),
    StorageTestCase(
        "eth_value_transfer_entryPoint_depositTo",
        UNSTAKED,
        SENDER,
        build_userop_for_sender,
        assert_ok,
    ),
    StorageTestCase(
        "EXTCODESIZE_undeployed_contract",
        UNSTAKED,
        SENDER,
        build_userop_for_sender,
        assert_opcode_error,
    ),
    StorageTestCase(
        "EXTCODEHASH_undeployed_contract",
        UNSTAKED,
        SENDER,
        build_userop_for_sender,
        assert_opcode_error,
    ),
    StorageTestCase(
        "EXTCODECOPY_undeployed_contract",
        UNSTAKED,
        SENDER,
        build_userop_for_sender,
        assert_opcode_error,
    ),
    StorageTestCase(
        "EXTCODESIZE_entrypoint",
        UNSTAKED,
        SENDER,
        build_userop_for_sender,
        assert_opcode_error,
    ),
    StorageTestCase(
        "EXTCODEHASH_entrypoint",
        UNSTAKED,
        SENDER,
        build_userop_for_sender,
        assert_opcode_error,
    ),
    StorageTestCase(
        "EXTCODECOPY_entrypoint",
        UNSTAKED,
        SENDER,
        build_userop_for_sender,
        assert_opcode_error,
    ),
    StorageTestCase(
        "CALL_undeployed_contract",
        UNSTAKED,
        SENDER,
        build_userop_for_sender,
        assert_opcode_error,
    ),
    StorageTestCase(
        "CALLCODE_undeployed_contract",
        UNSTAKED,
        SENDER,
        build_userop_for_sender,
        assert_opcode_error,
    ),
    StorageTestCase(
        "DELEGATECALL_undeployed_contract",
        UNSTAKED,
        SENDER,
        build_userop_for_sender,
        assert_opcode_error,
    ),
    StorageTestCase(
        "STATICCALL_undeployed_contract",
        UNSTAKED,
        SENDER,
        build_userop_for_sender,
        assert_opcode_error,
    ),
    StorageTestCase(
        "CALL_undeployed_contract_allowed_precompile",
        UNSTAKED,
        SENDER,
        build_userop_for_sender,
        assert_ok,
    ),
]


def idfunction(case):
    entity = re.match("TestRules(.*)", case.entity).groups()[0].lower()
    result = "ok" if case.assert_func.__name__ == assert_ok.__name__ else "drop"
    return f"{'staked' if case.staked else 'unstaked'}][{entity}][{case.rule}][{result}"


@pytest.mark.usefixtures("clear_state")
@pytest.mark.parametrize("case", cases, ids=idfunction)
def test_rule(w3, entrypoint_contract, case):
    entity_contract = deploy_and_deposit(
        w3, entrypoint_contract, case.entity, case.staked
    )
    userop = case.userop_build_func(w3, entrypoint_contract, entity_contract, case.rule)
    response = userop.send()
    case.assert_func(response)

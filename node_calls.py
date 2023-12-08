"""
{cli_name} utility functions
- query bank balance
- query tx
- node status
- tx bank send
"""

import json
import subprocess
import logging

OUTPUT_TYPE_FLAG = '--output=json'


async def check_address(address: str, node_home: str = '~/.gaia', cli_name: str = 'gaiad'):
    """
    {cli_name} keys parse <address>
    """
    check = subprocess.run([cli_name, "keys", "parse",
                            f"{address}",
                            f'--home={node_home}',
                            OUTPUT_TYPE_FLAG],
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                           text=True)
    try:
        check.check_returncode()
        response = json.loads(check.stdout[:-1])
        return response
    except subprocess.CalledProcessError as cpe:
        output = str(check.stderr).split('\n', maxsplit=1)[0]
        logging.error("Called Process Error: %s, stderr: %s", cpe, output)
        raise cpe
    except IndexError as index_error:
        logging.error('Parsing error on address check: %s', index_error)
        raise index_error


async def get_balance_list(address: str, node: str, node_home: str = '~/.gaia', cli_name: str = 'gaiad'):
    """
    {cli_name} query bank balances <address> <node> <chain-id>
    """
    balance = subprocess.run([cli_name, "query", "bank", "balances",
                              f"{address}",
                              f'--node={node}',
                              f'--home={node_home}',
                              OUTPUT_TYPE_FLAG],
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                             text=True)
    try:
        balance.check_returncode()
        response = json.loads(balance.stdout)
        return response['balances']
    except subprocess.CalledProcessError as cpe:
        output = str(balance.stderr).split('\n', maxsplit=1)[0]
        logging.error("Called Process Error: %s, stderr: %s", cpe, output)
        raise cpe
    except IndexError as index_error:
        logging.error('Parsing error on balance request: %s', index_error)
        raise index_error


async def tx_send(request: dict, cli_name: str = 'gaiad'):
    """
    The request dictionary must include these keys:
    - "sender"
    - "recipient"
    - "amount"
    - "fees"
    - "node"
    - "chain_id"
    {cli_name} tx bank send <from address> <to address> <amount>
                       <fees> <node> <chain-id>
                       --keyring-backend=test -y

    """
    tx_node = subprocess.run([cli_name, 'tx', 'bank', 'send',
                              f'{request["sender"]}',
                              f'{request["recipient"]}',
                              f'{request["amount"]}',
                              f'--fees={request["fees"]}',
                              f'--node={request["node"]}',
                              f'--chain-id={request["chain_id"]}',
                              f'--home={request["node_home"]}',
                              '--keyring-backend=test',
                              OUTPUT_TYPE_FLAG,
                              '-y'],
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        tx_node.check_returncode()
        response = json.loads(tx_node.stdout)
        return response['txhash']
    except subprocess.CalledProcessError as cpe:
        output = str(tx_node.stderr).split('\n', maxsplit=1)[0]
        logging.error("%s[%s]", cpe, output)
        raise cpe
    except (TypeError, KeyError) as err:
        output = tx_node.stderr
        logging.critical(
            'Could not read %s in tx response: %s', err, output)
        raise err

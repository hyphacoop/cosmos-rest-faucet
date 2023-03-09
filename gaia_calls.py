"""
nobled utility functions
- query bank balance
- query tx
- node status
- tx bank send
"""

import json
import subprocess
import logging


async def check_address(address: str, gaia_home: str = '~/.noble'):
    """
    nobled keys parse <address>
    """
    check = subprocess.run(["nobled", "keys", "parse",
                            f"{address}",
                            f'--home=/root/.noble',
                            '--output=json'],
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
    return None


async def get_balance_list(address: str, node: str, gaia_home: str = '~/.noble'):
    """
    nobled query bank balances <address> <node> <chain-id>
    """
    balance = subprocess.run(["nobled", "query", "bank", "balances",
                              f"{address}",
                              f'--node={node}',
                              f'--home=/root/.noble',
                              '--output=json'],
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
    return None


async def tx_send(request: dict):
    """
    The request dictionary must include these keys:
    - "sender"
    - "recipient"
    - "amount"
    - "fees"
    - "node"
    - "chain_id"
    nobled tx bank send <from address> <to address> <amount>
                       <fees> <node> <chain-id>
                       --keyring-backend=test -y

    """

    cmd = ['nobled', 'tx', 'bank', 'send',
                              f'{request["sender"]}',
                              f'{request["recipient"]}',
                              f'{request["amount"]}',
                              f'--node={request["node"]}',
                              f'--chain-id={request["chain_id"]}',
                              f'--home=/root/.noble',
                              '--keyring-backend=test',
                              '--output=json',
                              '-y']
    logging.info(" ".join(cmd))
    print(" ".join(cmd))
    tx_gaia = subprocess.run(cmd,
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        tx_gaia.check_returncode()
        response = json.loads(tx_gaia.stdout)
        return response['txhash']
    except subprocess.CalledProcessError as cpe:
        output = str(tx_gaia.stderr).split('\n', maxsplit=1)[0]
        logging.error("%s[%s]", cpe, output)
        raise cpe
    except (TypeError, KeyError) as err:
        output = tx_gaia.stderr
        logging.critical(
            'Could not read %s in tx response: %s', err, output)
        raise err
    return None

"""
Sets up a REST server to provide balance info and send tokens

"""

import time
import datetime
import logging
import sys
import subprocess
import aiofiles as aiof
import toml
from quart import Quart, json, request
import gaia_calls as gaia

# Configure Logging
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s %(levelname)s %(message)s')

# Load config
config = toml.load('config.toml')

try:
    TX_LOG_PATH = config['transactions_log']
    REQUEST_TIMEOUT = int(config['request_timeout'])
    ADDRESS_PREFIX = config['cosmos']['prefix']
    DENOM = str(config['cosmos']['denomination'])
    testnets = config['testnets']
    for net in testnets:
        testnets[net]['name'] = net
        testnets[net]["active_day"] = datetime.datetime.today().date()
        testnets[net]["day_tally"] = 0
    ACTIVE_REQUESTS = {net: {} for net in testnets}
    TESTNET_OPTIONS = '|'.join(list(testnets.keys()))
except KeyError as key_err:
    logging.critical('Key could not be found: %s', key_err)
    sys.exit()


app = Quart(__name__)


async def save_transaction_statistics(transaction: str):
    """
    Transaction strings are already comma-separated
    """
    async with aiof.open(TX_LOG_PATH, 'a') as csv_file:
        await csv_file.write(f'{transaction}\n')
        await csv_file.flush()


async def get_faucet_balance(testnet: dict):
    """
    Returns the uatom balance
    """
    balances = await gaia.get_balance_list(
        address=testnet['faucet_address'],
        node=testnet['node_url'])
    for balance in balances:
        if balance['denom'] == 'uatom':
            return balance['amount']+'uatom'


async def balance_request(address: str, testnet: dict):
    """
    Provide the balance for a given address and testnet
    """
    try:
        # check address is valid
        await gaia.check_address(address)
        balance = await gaia.get_balance_list(
            address=address,
            node=testnet["node_url"])
        return balance
    except subprocess.CalledProcessError as cpe:
        raise cpe
    return


def check_time_limits(address: str, testnet: dict):
    """
    Returns True, None
    If the given address is not time-blocked for the given testnet

    Returns False, reply
    If the address is still on time-out
    """
    message_timestamp = time.time()

    # Check address allowance
    if address in ACTIVE_REQUESTS[testnet['name']]:
        check_time = ACTIVE_REQUESTS[testnet['name']][address]['next_request']
        if check_time > message_timestamp:
            seconds_left = check_time - message_timestamp
            minutes_left = seconds_left / 60
            if minutes_left > 120:
                wait_time = str(int(minutes_left/60)) + ' hours'
            else:
                wait_time = str(int(minutes_left)) + ' minutes'
            timeout_in_hours = int(REQUEST_TIMEOUT / 60 / 60)
            reply = f'Tokens will only be sent out once every' \
                f' {timeout_in_hours} hours for the same testnet, ' \
                f'please try again in ' \
                f'{wait_time}'
            return False, reply
        del ACTIVE_REQUESTS[testnet['name']][address]

    if address not in ACTIVE_REQUESTS[testnet['name']]:
        ACTIVE_REQUESTS[testnet['name']][address] = {
            'next_request': message_timestamp + REQUEST_TIMEOUT}

    return True, None


def check_daily_cap(testnet: dict):
    """
    Returns True if the faucet has not reached the daily cap
    Returns False otherwise
    """
    delta = int(testnet["amount_to_send"])
    # Check date
    today = datetime.datetime.today().date()
    if today != testnet['active_day']:
        # The date has changed, reset the tally
        testnet['active_day'] = today
        testnet['day_tally'] = delta
        return True

    # Check tally
    if testnet['day_tally'] + delta > int(testnet['daily_cap']):
        return False

    testnet['day_tally'] += delta
    return True


async def token_request(address: str, testnet: dict):
    """
    Send tokens to the specified address
    """

    # Check address
    try:
        # check address is valid
        await gaia.check_address(address)
    except Exception as exc:
        raise exc

    # Check whether the faucet has reached the daily cap
    if check_daily_cap(testnet=testnet):
        # Check whether user or address have received tokens on this testnet
        approved, reply = check_time_limits(
            address=address, testnet=testnet)
        if approved:
            request_dict = {'sender': testnet['faucet_address'],
                            'recipient': address,
                            'amount': testnet['amount_to_send'] + DENOM,
                            'fees': testnet['tx_fees'] + DENOM,
                            'chain_id': testnet['chain_id'],
                            'node': testnet['node_url']}
            try:
                # Make gaia call and send the response back
                transfer = await gaia.tx_send(request_dict)
                logging.info('Tokens were requested for %s in %s',
                             address, testnet['name'])
                now = datetime.datetime.now()
                # Get faucet balance and save to transaction log
                balance = await get_faucet_balance(testnet)
                await save_transaction_statistics(f'{now.isoformat(timespec="seconds")},'
                                                  f'{testnet["name"]},{address},'
                                                  f'{testnet["amount_to_send"] + DENOM},'
                                                  f'{transfer},'
                                                  f'{balance}')
                return testnet['amount_to_send']+DENOM, transfer
            except subprocess.CalledProcessError as cpe:
                del ACTIVE_REQUESTS[testnet['name']][address]
                testnet['day_tally'] -= int(testnet['amount_to_send'])
                raise cpe
        else:
            testnet['day_tally'] -= int(testnet['amount_to_send'])
            logging.info('Tokens were requested for %s in %s and was rejected',
                         address, testnet['name'])
            return False, reply
    else:
        logging.info('Tokens were requested for %s in %s '
                     'but the daily cap has been reached',
                     address, testnet['name'])
        return False, 'The daily cap for this faucet has been reached'


@app.route('/balance', methods=['GET'])
async def get_balance():
    """
    Respond to
    /balance?address=abc&chain=xyz
    """
    request_dict = request.args.to_dict()
    if 'address' not in request_dict or \
            'chain' not in request_dict:
        return json.dumps({'status': 'fail',
                           'message': 'Error: address or chain_id not specified'})
    try:
        address = request_dict['address']
        chain = request_dict['chain']
        if chain not in testnets.keys():
            return json.dumps({'status': 'fail',
                               'message': 'Error: invalid chain; '
                               'specify theta-testnet-001 or theta-devnet'})
        await gaia.check_address(address)
        balance = await balance_request(address=address, testnet=testnets[chain])
        response = {
            'address': address,
            'chain': chain,
            'balance': balance,
            'status': 'success'
        }
        return json.dumps(response)
    except KeyError as key:
        logging.critical('Key could not be found: %s', key)
    except subprocess.CalledProcessError as cpe:
        msg = cpe.stderr.split('\n')[0]
        if 'parse' in cpe.cmd:
            msg = 'Error: invalid address'
        return json.dumps({'status': 'fail', 'message': msg})


@app.route('/request', methods=['GET'])
async def send_tokens():
    """
    Respond to
    /request?address=abc&chain=xyz
    """
    request_dict = request.args.to_dict()
    if 'address' not in request_dict or \
       'chain' not in request_dict:
        return json.dumps({'status': 'fail',
                           'message': 'Error: address or chain_id not specified'})
    try:
        address = request_dict['address']
        chain = request_dict['chain']
        if chain not in testnets.keys():
            return json.dumps({'status': 'fail',
                               'message': 'Error: invalid chain; '
                               'specify theta-testnet-001 or theta-devnet'})
        await gaia.check_address(address)
        amount, transfer = await token_request(address=address, testnet=testnets[chain])
        if amount:
            response = {
                'address': address,
                'chain': chain,
                'amount': amount,
                'hash': transfer,
                'status': 'success'
            }
        else:
            response = {
                'status': 'fail',
                'message': transfer
            }
        return json.dumps(response)
    except KeyError as key_error:
        logging.critical('Key could not be found: %s', key_error)
        return "Missing key"
    except subprocess.CalledProcessError as cpe:
        msg = cpe.stderr.split('\n')[0]
        if 'parse' in cpe.cmd:
            msg = 'Error: invalid address'
        return json.dumps({'status': 'fail', 'message': msg})


if __name__ == '__main__':
    app.run()

import requests
import sys
import json
import time
import subprocess
import uuid
import os

BASE_URL = "http://localhost:8000"
PASSWORD = "nixblitz"

session = requests.Session()

def print_pass(message):
    print(f"✅ PASS: {message}")

def print_fail(message, details=""):
    print(f"❌ FAIL: {message}")
    if details:
        print(f"   Details: {details}")
    sys.exit(1)

def create_cln_invoice(amount_msat, label, description):
    # Using the paths defined in the project structure
    cln_dir = os.path.abspath("test_env_data/cln")
    rpc_file = os.path.join(cln_dir, "regtest/lightning-rpc")
    
    cmd = [
        "lightning-cli",
        "--regtest",
        f"--lightning-dir={cln_dir}",
        f"--rpc-file={rpc_file}",
        "invoice", str(amount_msat), label, description
    ]
    
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return json.loads(res.stdout)["bolt11"]
    except subprocess.CalledProcessError as e:
        print_fail("Failed to create CLN invoice", f"STDOUT: {e.stdout}\nSTDERR: {e.stderr}")
    except Exception as e:
        print_fail("Failed to create CLN invoice", str(e))

def get_cln_node_uri():
    cln_dir = os.path.abspath("test_env_data/cln")
    rpc_file = os.path.join(cln_dir, "regtest/lightning-rpc")
    cmd = ["lightning-cli", "--regtest", f"--lightning-dir={cln_dir}", f"--rpc-file={rpc_file}", "getinfo"]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
        data = json.loads(res.stdout)
        pubkey = data["id"]
        # In devenv.nix, CLN is bound to 9736
        address = "127.0.0.1:9736"
        return f"{pubkey}@{address}"
    except Exception as e:
        print_fail("Failed to get CLN URI", str(e))

def mine_blocks(num_blocks):
    btc_dir = os.path.abspath("test_env_data/bitcoin")
    # Ensure wallet is loaded
    subprocess.run(["bitcoin-cli", "-regtest", f"-datadir={btc_dir}", "loadwallet", "testwallet"], capture_output=True)
    
    # Get a fresh address
    res = subprocess.run(["bitcoin-cli", "-regtest", f"-datadir={btc_dir}", "-rpcwallet=testwallet", "getnewaddress"], capture_output=True, text=True)
    address = res.stdout.strip()
    if not address:
        # Fallback address if getnewaddress fails
        address = "bcrt1qs758pk7pkkyer7kv8v3ch6u90858759v6yzn8f"
    
    cmd = ["bitcoin-cli", "-regtest", f"-datadir={btc_dir}", "-rpcwallet=testwallet", "generatetoaddress", str(num_blocks), address]
    try:
        subprocess.run(cmd, capture_output=True, text=True, check=True)
        print(f"Mined {num_blocks} blocks to {address}.")
    except Exception as e:
        # Try legacy 'generate' just in case, though unlikely for v30
        try:
            subprocess.run(["bitcoin-cli", "-regtest", f"-datadir={btc_dir}", "-rpcwallet=testwallet", "-generate", str(num_blocks)], capture_output=True, check=True)
            print(f"Mined {num_blocks} blocks using -generate.")
        except:
            print(f"Warning: Failed to mine blocks: {e}")

def test_open_channel():
    print("Testing Channel Opening...")
    
    # Check LND sync status
    try:
        resp = session.get(f"{BASE_URL}/lightning/get-info")
        info = resp.json()
        print(f"LND Sync Status: Synced to Chain: {info.get('synced_to_chain')}, Synced to Graph: {info.get('synced_to_graph')}")
    except:
        pass

    cln_uri = get_cln_node_uri()
    print(f"Target CLN URI: {cln_uri}")
    
    # Check if LND has funds, if not, fund it
    try:
        response = session.get(f"{BASE_URL}/lightning/get-balance")
        response.raise_for_status()
        balance = response.json()
        print(f"Debug Balance Response: {balance}")
        # The key in models.py is onchain_total_balance
        onchain_balance = balance.get("onchain_total_balance")
        if onchain_balance is None:
             # Try other possible keys if model changed
             onchain_balance = balance.get("onchain_total", 0)
        
        if onchain_balance < 2000000: # Need ~2M sats
            print(f"LND balance low ({onchain_balance} sats), funding LND...")
            resp = session.post(f"{BASE_URL}/lightning/new-address", json={"type": "p2wkh"})
            addr = resp.json()
            print(f"LND address: {addr}")
            
            btc_dir = os.path.abspath("test_env_data/bitcoin")
            # Try to send funds using a fixed fee rate to avoid estimation issues
            try:
                print(f"Sending 10 BTC to {addr}...")
                subprocess.run([
                    "bitcoin-cli", "-regtest", f"-datadir={btc_dir}", "-rpcwallet=testwallet", 
                    "-named", "sendtoaddress", f"address={addr}", "amount=10", "fee_rate=1000"
                ], check=True, capture_output=True, text=True)
                mine_blocks(6)
                print("Waiting 10 seconds for LND to sync funds...")
                time.sleep(10)
                
                # Check balance again
                response = session.get(f"{BASE_URL}/lightning/get-balance")
                balance = response.json()
                onchain_balance = balance.get("onchain_total_balance", 0)
                print(f"LND New Balance: {onchain_balance} sats")
            except subprocess.CalledProcessError as e:
                print_fail(f"sendtoaddress failed: {e.stderr}")
            
            time.sleep(2) # wait for sync
    except Exception as e:
        print(f"Warning: Could not check/fund balance: {e}")

    try:
        # Reduced amount to 100k sats
        funding_amt = 100000 
        params = {
            "local_funding_amount": funding_amt,
            "node_URI": cln_uri,
            "target_confs": 3
        }
        print(f"Opening {funding_amt} sat channel to {cln_uri}...")
        
        # Before calling API, let's try to connect via lncli to debug
        lnd_dir = os.path.abspath("test_env_data/lnd")
        pubkey = cln_uri.split("@")[0]
        host = cln_uri.split("@")[1]
        
        print(f"DEBUG: Trying manual connect via lncli...")
        subprocess.run([
            "lncli", f"--lnddir={lnd_dir}", "--network=regtest", 
            "connect", cln_uri
        ], capture_output=True)
        
        response = session.post(f"{BASE_URL}/lightning/open-channel", params=params)
        
        if response.status_code != 200:
             print(f"Channel open failed with status {response.status_code}: {response.text}")
             # If it's a 500 with "EOF", let's try to see what lncli openchannel says
             print(f"DEBUG: Trying manual openchannel via lncli...")
             res = subprocess.run([
                 "lncli", f"--lnddir={lnd_dir}", "--network=regtest", 
                 "openchannel", "--node_key", pubkey, "--local_amt", str(funding_amt)
             ], capture_output=True, text=True)
             print(f"DEBUG: lncli output: {res.stdout}")
             print(f"DEBUG: lncli error: {res.stderr}")
             
             if "EOF" in response.text:
                  print("Got EOF, retrying once after 5s...")
                  time.sleep(5)
                  response = session.post(f"{BASE_URL}/lightning/open-channel", params=params)

        response.raise_for_status()
        txid = response.json()
        print_pass(f"POST /lightning/open-channel (TXID: {txid})")
        
        print("Mining 6 blocks to confirm channel...")
        mine_blocks(6)
        
        print("Waiting for channel to become active...")
        max_retries = 30
        for i in range(max_retries):
            resp = session.get(f"{BASE_URL}/lightning/list-channels")
            channels = resp.json()
            # LND channel_id in list-channels is often funding_txid:output_index
            active_channels = [c for c in channels if c.get("active")]
            if active_channels:
                print(f"Channel is active! (Try {i+1})")
                print(f"DEBUG: Channel info: {active_channels[0]}")
                break
            print(f"Channel not active yet, waiting... (Try {i+1}/{max_retries})")
            time.sleep(2)
        else:
            print_fail("Channel never became active")
        
        print("Waiting 5 more seconds for good measure...")
        time.sleep(5)
        
    except Exception as e:
        details = str(e)
        if hasattr(e, 'response') and e.response is not None:
            details += f"\nResponse Body: {e.response.text}"
        print_fail("POST /lightning/open-channel failed", details)

def test_send_payment():
    label = f"test-label-{uuid.uuid4()}"
    description = "test-payment-from-api"
    amount_msat = 4000000 # 4000 sat
    
    print(f"Creating CLN invoice for {amount_msat} msat...")
    bolt11 = create_cln_invoice(amount_msat, label, description)
    print(f"Invoice created: {bolt11[:50]}...")
    
    try:
        # POST /lightning/send-payment
        # Parameters are query parameters according to openapi.json
        params = {"pay_req": bolt11}
        print("Sending payment via API...")
        response = session.post(f"{BASE_URL}/lightning/send-payment", params=params)
        response.raise_for_status()
        
        payment_data = response.json()
        status = payment_data.get("status")
        
        if status == "succeeded":
            print_pass("POST /lightning/send-payment (Payment Succeeded)")
        else:
             print_fail("Payment did not succeed", f"Status: {status}\nResponse: {payment_data}")
             
    except Exception as e:
        # If it's a 400/500, we might get more info from the body
        details = str(e)
        if hasattr(e, 'response') and e.response is not None:
            details += f"\nResponse Body: {e.response.text}"
        print_fail("POST /lightning/send-payment failed", details)

def test_login():
    url = f"{BASE_URL}/system/login"
    payload = {"password": PASSWORD}
    try:
        response = session.post(url, json=payload)
        response.raise_for_status()
        token = response.json()
        
        if not token or not isinstance(token, str):
            print_fail("Login failed", f"Response is not a token string: {token}")
            
        session.headers.update({"Authorization": f"Bearer {token}"})
        print_pass("Login successful")
        return token
    except Exception as e:
        print_fail("Login failed", str(e))

def test_system_info():
    endpoints = [
        "/system/get-system-info",
        "/system/health",
        "/system/connection-info"
    ]
    for ep in endpoints:
        try:
            response = session.get(f"{BASE_URL}{ep}")
            response.raise_for_status()
            print_pass(f"GET {ep}")
        except Exception as e:
            print_fail(f"GET {ep} failed", str(e))

def test_bitcoin_info():
    endpoints = [
        "/bitcoin/btc-info",
        "/bitcoin/get-blockchain-info",
        "/bitcoin/get-network-info",
        "/bitcoin/get-block-count"
    ]
    for ep in endpoints:
        try:
            response = session.get(f"{BASE_URL}{ep}")
            response.raise_for_status()
            
            # The API returns the raw bitcoind RPC response for some endpoints as a string
            if ep == "/bitcoin/get-block-count":
                data = response.json()
                if isinstance(data, str):
                    data = json.loads(data)
                
                if "result" not in data:
                    print_fail(f"{ep} response missing 'result'", str(data))
                
                try:
                    int(data["result"])
                except (ValueError, TypeError):
                    print_fail(f"{ep} result is not an integer", str(data["result"]))
            
            print_pass(f"GET {ep}")
        except Exception as e:
            print_fail(f"GET {ep} failed", str(e))

def test_lightning_info():
    endpoints = [
        "/lightning/get-info",
        "/lightning/get-balance",
        "/lightning/list-channels",
        "/lightning/list-invoices"
    ]
    for ep in endpoints:
        try:
            response = session.get(f"{BASE_URL}{ep}")
            response.raise_for_status()
            print_pass(f"GET {ep}")
        except Exception as e:
            print_fail(f"GET {ep} failed", str(e))

def test_lightning_actions():
    # 1. New Address
    try:
        # Assuming NewAddressInput has 'type' field
        payload = {"type": "p2wkh"} 
        response = session.post(f"{BASE_URL}/lightning/new-address", json=payload)
        response.raise_for_status()
        address = response.json()
        if not isinstance(address, str):
             print_fail("New address response is not a string", str(address))
        print_pass("POST /lightning/new-address")
    except Exception as e:
        print_fail("POST /lightning/new-address failed", str(e))

    # 2. Add Invoice
    pay_req = None
    try:
        # Params are query parameters as per openapi.json
        params = {"value_msat": 1000, "memo": "test_api_script"}
        response = session.post(f"{BASE_URL}/lightning/add-invoice", params=params)
        response.raise_for_status()
        invoice_data = response.json()
        pay_req = invoice_data.get("payment_request")
        if not pay_req:
             print_fail("Add invoice response missing payment_request", str(invoice_data))
        print_pass("POST /lightning/add-invoice")
    except Exception as e:
        print_fail("POST /lightning/add-invoice failed", str(e))

    # 3. Decode Pay Req
    if pay_req:
        try:
            response = session.get(f"{BASE_URL}/lightning/decode-pay-req", params={"pay_req": pay_req})
            response.raise_for_status()
            decoded = response.json()
            # Check basic fields
            if decoded.get("num_msat") != 1000:
                 print_fail("Decoded payment request has wrong amount", str(decoded))
            print_pass("GET /lightning/decode-pay-req")
        except Exception as e:
            print_fail("GET /lightning/decode-pay-req failed", str(e))

def main():
    print(f"Starting API tests against {BASE_URL}")
    print("-" * 40)
    
    test_login()
    
    print("Priming blockchain (mining 101 blocks)...")
    mine_blocks(101)
    
    test_system_info()
    test_bitcoin_info()
    test_lightning_info()
    test_lightning_actions()
    test_open_channel()
    test_send_payment()
    
    print("-" * 40)
    print("🎉 All basic API tests passed!")

if __name__ == "__main__":
    main()

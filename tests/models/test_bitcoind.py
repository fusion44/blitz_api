from app.models.bitcoind import *

blockhain_info = {
    "chain": "main",
    "blocks": 257524,
    "headers": 703160,
    "bestblockhash": "00000000000000182104048e3477ffdfe3b0528f156558e270102d6a557e8843",
    "difficulty": 86933017.77119441,
    "mediantime": 1378985988,
    "verificationprogress": 0.03523320739750064,
    "initialblockdownload": True,
    "chainwork": "0000000000000000000000000000000000000000000000e76a0e37f2b9739cd6",
    "size_on_disk": 12340553639,
    "pruned": False,
    "softforks": {
        "bip34": {"type": "buried", "active": True, "height": 227931},
        "bip66": {"type": "buried", "active": False, "height": 363725},
        "bip65": {"type": "buried", "active": False, "height": 388381},
        "csv": {"type": "buried", "active": False, "height": 419328},
        "segwit": {"type": "buried", "active": False, "height": 481824},
        "taproot": {
            "type": "bip9",
            "bip9": {
                "status": "defined",
                "start_time": 1619222400,
                "timeout": 1628640000,
                "since": 0,
                "min_activation_height": 709632,
                "statistics": {
                    "period": 0,
                    "threshold": 0,
                    "elapsed": 0,
                    "count": 0,
                    "possible": True,
                },
                "height": 0,
                "active": True,
            },
            "active": False,
        },
    },
    "warnings": "",
}

network_info = d = {
    "version": 220000,
    "subversion": "/Satoshi:22.0.0/",
    "protocolversion": 70016,
    "localservices": "000000000000040d",
    "localservicesnames": ["NETWORK", "BLOOM", "WITNESS", "NETWORK_LIMITED"],
    "localrelay": True,
    "timeoffset": -3,
    "networkactive": True,
    "connections": 10,
    "connections_in": 0,
    "connections_out": 10,
    "networks": [
        {
            "name": "ipv4",
            "limited": False,
            "reachable": True,
            "proxy": "",
            "proxy_randomize_credentials": False,
        },
        {
            "name": "ipv6",
            "limited": False,
            "reachable": True,
            "proxy": "",
            "proxy_randomize_credentials": False,
        },
        {
            "name": "onion",
            "limited": False,
            "reachable": True,
            "proxy": "127.0.0.1:9050",
            "proxy_randomize_credentials": True,
        },
        {
            "name": "i2p",
            "limited": True,
            "reachable": False,
            "proxy": "",
            "proxy_randomize_credentials": False,
        },
    ],
    "relayfee": 0.00001000,
    "incrementalfee": 0.00001000,
    "localaddresses": [
        {
            "address": "123.onion",
            "port": 8333,
            "score": 4,
        },
        {
            "address": "1.2.3.6",
            "port": 8334,
            "score": 4,
        },
    ],
    "warnings": "",
}


def test_BtcNetwork():
    d = {
        "name": "ipv4",
        "limited": False,
        "reachable": True,
        "proxy": "",
        "proxy_randomize_credentials": False,
    }

    n = BtcNetwork.from_rpc(d)
    assert n.name == d["name"]
    assert n.limited == d["limited"]
    assert n.reachable == d["reachable"]
    assert n.proxy == d["proxy"]
    assert n.proxy_randomize_credentials == d["proxy_randomize_credentials"]


def test_BtcLocalAddress():
    d = {
        "address": "123.onion",
        "port": 8333,
        "score": 1,
    }

    addr = BtcLocalAddress.from_rpc(local_address=d)
    assert addr.address == d["address"]
    assert addr.port == d["port"]
    assert addr.score == d["score"]


def test_NetworkInfo():
    ni = NetworkInfo.from_rpc(r=network_info)
    assert len(ni.networks) == 4
    assert len(ni.local_addresses) == 2
    assert ni


def test_Bip9Statistics():
    d = {
        "period": 0,
        "threshold": 0,
        "elapsed": 0,
        "count": 0,
        "possible": True,
    }
    s = Bip9Statistics.from_rpc(d)
    assert s


def test_BlockchainInfo():
    i = BlockchainInfo.from_rpc(blockhain_info)
    assert i
    assert len(i.softforks) == 6


def test_BtcInfo():
    s = BtcInfo.from_rpc(
        binfo=BlockchainInfo.from_rpc(blockhain_info),
        ninfo=NetworkInfo.from_rpc(network_info),
    )
    assert s

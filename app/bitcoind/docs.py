blocks_sub_doc = """
Similar to Bitcoin Core getblock

SSE endpoint to receive new block information as soon as it is appended to chain.

If verbosity is 0, returns a string that is serialized, hex-encoded data for block 'hash'.<br>
If verbosity is 1, returns an Object with information about block <hash>.<br>
If verbosity is 2, returns an Object with information about block <hash> and information about each transaction.<br>
"""

estimate_fee_mode_desc = "Whether to return a more conservative estimate which also satisfies a longer history. A conservative estimate potentially returns a higher feerate and is more likely to be sufficient for the desired target, but is not as responsive to short term drops in the prevailing fee market."

get_bitcoin_info_desc = """
This endpoint returns a combination of various Bitcoin Core calls for easy access.
"""

get_bitcoin_info_response_desc = """
A JSON object which combines information from Bitcoin Core RPC calls `getnetworkinfo` and `getblockchaininfo`

```JSON
{
  "version": 210100,
  "subversion": "/Satoshi:0.21.1/",
  "networkactive": true,
  "networks": [
    {
      "name": "ipv4",
      "limited": false,
      "reachable": true,
      "proxy": "",
      "proxy_randomize_credentials": false
    },
    {
      "name": "ipv6",
      "limited": false,
      "reachable": true,
      "proxy": "",
      "proxy_randomize_credentials": false
    },
    {
      "name": "onion",
      "limited": true,
      "reachable": false,
      "proxy": "",
      "proxy_randomize_credentials": false
    }
  ],
  "connections": 3,
  "connections_in": 1,
  "connections_out": 3,
  "chain": "regtest",
  "blocks": 316,
  "headers": 316,
  "initialblockdownload": false,
  "size_on_disk": 102295,
  "verification_progress": 1,
  "pruned":false
}
```
"""

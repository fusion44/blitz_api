blocks_sub_doc = """
Similar to Bitcoin Core getblock

SSE endpoint to receive new block information as soon as it is appended to chain.

If verbosity is 0, returns a string that is serialized, hex-encoded data for block 'hash'.<br>
If verbosity is 1, returns an Object with information about block <hash>.<br>
If verbosity is 2, returns an Object with information about block <hash> and information about each transaction.<br>
"""

get_bitcoin_info_desc = """
This endpoint returns a combination of various Bitcoin Core calls for easy access.
"""

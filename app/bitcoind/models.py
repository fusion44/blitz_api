from argparse import ArgumentError
from enum import Enum
from typing import List, Optional, Union

from fastapi import Query
from pydantic.main import BaseModel


class FeeEstimationMode(str, Enum):
    CONSERVATIVE = "conservative"
    ECONOMICAL = "economical"


class BlockRpcFunc(str, Enum):
    HASHBLOCK = "hashblock"
    RAWBLOCK = "rawblock"

    @classmethod
    def from_string(cls, func: str):
        if func == "hashblock":
            return cls.HASHBLOCK
        elif func == "rawblock":
            return cls.RAWBLOCK
        else:
            raise ArgumentError(
                "Function name must either be 'hashblock' or 'rawblock'"
            )


class BtcNetwork(BaseModel):
    name: str = Query(..., description="Which network is in use (ipv4, ipv6 or onion)")
    limited: bool = Query(..., description="Is the network limited using - onlynet?")
    reachable: bool = Query(..., description="Is the network reachable?")
    proxy: Optional[str] = Query(
        "",
        description="host:port of the proxy that is used for this network, or empty if none",
    )
    proxy_randomize_credentials: bool = Query(
        ..., description="Whether randomized credentials are used"
    )

    @classmethod
    def from_rpc(cls, r):
        return cls(
            name=r["name"],
            limited=r["limited"],
            reachable=r["reachable"],
            proxy=r["proxy"],
            proxy_randomize_credentials=r["proxy_randomize_credentials"],
        )


class BtcLocalAddress(BaseModel):
    address: str = Query(..., description="Network address")
    port: int = Query(..., description="Network port")
    score: int = Query(..., description="Relative score")

    @classmethod
    def from_rpc(cls, local_address):
        return BtcLocalAddress(
            address=local_address["address"],
            port=local_address["port"],
            score=local_address["score"],
        )


class RawTransaction(BaseModel):
    in_active_chain: Union[None, bool] = Query(
        None,
        description='Whether specified block is in the active chain or not (only present with explicit "blockhash" argument)',
    )
    txid: str = Query(..., description="The transaction id (same as provided)")
    hash: str = Query(
        ...,
        description="The transaction hash (differs from txid for witness transactions)",
    )
    size: int = Query(..., description="The serialized transaction size")
    vsize: int = Query(
        ...,
        description="The virtual transaction size (differs from size for witness transactions)",
    )
    weight: int = Query(
        ..., description="The transaction's weight (between vsize*4 - 3 and vsize*4)"
    )
    version: int = Query(..., description="The version")
    locktime: int = Query(..., description="The lock time")
    vin: List[dict] = Query(..., description="The transaction's inputs")
    vout: List[dict] = Query(..., description="The transaction's outputs")
    blockhash: str = Query(..., description="The block hash")
    confirmations: int = Query(..., description="The number of confirmations")
    blocktime: int = Query(
        ..., description="The block time in seconds since epoch (Jan 1 1970 GMT)"
    )

    @classmethod
    def from_rpc(cls, tx):
        return cls(
            in_active_chain=tx["in_active_chain"]
            if "in_active_chain" in tx.keys()
            else None,
            txid=tx["txid"] if "txid" in tx.keys() else "",
            hash=tx["hash"] if "hash" in tx.keys() else "",
            size=tx["size"] if "size" in tx.keys() else 0,
            vsize=tx["vsize"] if "vsize" in tx.keys() else 0,
            weight=tx["weight"] if "weight" in tx.keys() else 0,
            version=tx["version"] if "version" in tx.keys() else 0,
            locktime=tx["locktime"] if "locktime" in tx.keys() else 0,
            vin=tx["vin"] if "vin" in tx.keys() else [],
            vout=tx["vout"] if "vout" in tx.keys() else [],
            blockhash=tx["blockhash"] if "blockhash" in tx.keys() else "",
            confirmations=tx["confirmations"] if "confirmations" in tx.keys() else 0,
            blocktime=tx["blocktime"] if "blocktime" in tx.keys() else 0,
        )


# getnetworkinfo
class NetworkInfo(BaseModel):
    version: int = Query(..., description="The bitcoin core server version")
    subversion: str = Query(..., description="The server subversion string")
    protocol_version: int = Query(..., description="The protocol version")
    local_services: str = Query(
        None, description="The services we offer to the network, hex formatted"
    )
    local_services_names: List[str] = Query(
        [], description="The services we offer to the network, in human-readable form"
    )
    local_relay: bool = Query(
        ..., description="True if transaction relay is requested from peers"
    )
    time_offset: int = Query(..., description="The time offset")
    connections: int = Query(..., description="The total number of connections")
    connections_in: int = Query(..., description="The number of inbound connections")
    connections_out: int = Query(..., description="The number of outbound connections")
    network_active: bool = Query(..., description="Whether p2p networking is enabled")
    networks: List[BtcNetwork] = Query(..., description="Information per network")
    relay_fee: int = Query(
        ..., description="Minimum relay fee for transactions in BTC/kB"
    )
    incremental_fee: int = Query(
        ...,
        description="Minimum fee increment for mempool limiting or BIP 125 replacement in BTC/kB",
    )
    local_addresses: List[BtcLocalAddress] = Query(
        [], description="List of local addresses"
    )
    warnings: str = Query(None, description="Any network and blockchain warnings")

    @classmethod
    def from_rpc(cls, r):
        networks = []
        for n in r["networks"]:
            networks.append(BtcNetwork.from_rpc(n))

        return cls(
            version=r["version"],
            subversion=r["subversion"],
            protocol_version=r["protocolversion"],
            local_services=r["localservices"],
            local_services_names=[name for name in r["localservicesnames"]],
            local_relay=r["localrelay"],
            time_offset=r["timeoffset"],
            connections=r["connections"],
            connections_in=r["connections_in"],
            connections_out=r["connections_out"],
            network_active=r["networkactive"],
            networks=[BtcNetwork.from_rpc(n) for n in r["networks"]],
            relay_fee=r["relayfee"],
            incremental_fee=r["incrementalfee"],
            local_addresses=[BtcLocalAddress.from_rpc(n) for n in r["localaddresses"]],
            warnings=r["warnings"],
        )


class Bip9Statistics(BaseModel):
    period: int = Query(
        ..., description="The length in blocks of the BIP9 signalling period"
    )
    threshold: int = Query(
        ...,
        description="The number of blocks with the version bit set required to activate the feature",
    )
    elapsed: int = Query(
        ...,
        description="The number of blocks elapsed since the beginning of the current period",
    )
    count: int = Query(
        ...,
        description="The number of blocks with the version bit set in the current period",
    )
    possible: bool = Query(
        ...,
        description="False if there are not enough blocks left in this period to pass activation threshold",
    )

    @classmethod
    def from_rpc(cls, r):
        return cls(
            period=r["period"],
            threshold=r["threshold"],
            elapsed=r["elapsed"],
            count=r["count"],
            possible=r["possible"],
        )


class Bip9Data(BaseModel):
    status: str = Query(
        ...,
        description="""One of "defined", "started", "locked_in", "active", "failed" """,
    )
    bit: int = Query(
        None,
        description="the bit(0-28) in the block version field used to signal this softfork(only for `started` status)",
    )
    start_time: int = Query(
        ...,
        description="The minimum median time past of a block at which the bit gains its meaning",
    )
    timeout: int = Query(
        ...,
        description="The median time past of a block at which the deployment is considered failed if not yet locked in",
    )
    since: int = Query(
        ..., description="Height of the first block to which the status applies"
    )
    min_activation_height: int = Query(
        ..., description="Minimum height of blocks for which the rules may be enforced"
    )
    statistics: Bip9Statistics = Query(
        None,
        description="numeric statistics about BIP9 signalling for a softfork(only for `started` status)",
    )
    height: int = Query(
        None,
        description="Height of the first block which the rules are or will be enforced(only for `buried` type, or `bip9` type with `active` status)",
    )
    active: bool = Query(
        None,
        description="True if the rules are enforced for the mempool and the next block",
    )

    @classmethod
    def from_rpc(cls, r):
        return cls(
            status=r["status"],
            bit=r["bit"] if "bit" in r else None,
            start_time=r["start_time"],
            timeout=r["timeout"],
            since=r["since"],
            min_activation_height=r["min_activation_height"],
            statistics=Bip9Statistics.from_rpc(r["statistics"])
            if "statistics" in r
            else None,
            height=r["height"] if "height" in r else None,
            active=r["active"] if "active" in r else None,
        )


class SoftFork(BaseModel):
    name: str = Query(..., description="Name of the softfork")
    type: str = Query(..., description='One of "buried", "bip9"')
    active: bool = Query(
        ...,
        description="True **if** the rules are enforced for the mempool and the next block",
    )
    bip9: Bip9Data = Query(
        None, description='Status of bip9 softforks(only for "bip9" type)'
    )
    height: int = Query(
        None,
        description="Height of the first block which the rules are or will be enforced (only for `buried` type, or `bip9` type with `active` status)",
    )

    @classmethod
    def from_rpc(cls, name: str, r: dict):
        return cls(
            name=name,
            type=r["type"],
            active=r["active"],
            bip9=Bip9Data.from_rpc(r["bip9"]) if "bip9" in r else None,
            height=r["height"] if "height" in r else None,
        )


class BlockchainInfo(BaseModel):
    chain: str = Query(..., description="Current network name(main, test, regtest)")
    blocks: int = Query(
        ...,
        description="The height of the most-work fully-validated chain. The genesis block has height 0",
    )
    headers: int = Query(
        ..., description="The current number of headers we have validated"
    )
    best_block_hash: str = Query(
        ..., description="The hash of the currently best block"
    )
    difficulty: int = Query(..., description="The current difficulty")
    mediantime: int = Query(..., description="Median time for the current best block")
    verification_progress: float = Query(
        ..., description="Estimate of verification progress[0..1]"
    )
    initial_block_download: bool = Query(
        ...,
        description="Estimate of whether this node is in Initial Block Download mode",
    )
    chainwork: str = Query(
        ..., description="total amount of work in active chain, in hexadecimal"
    )
    size_on_disk: int = Query(
        ..., description="The estimated size of the block and undo files on disk"
    )
    pruned: bool = Query(..., description="If the blocks are subject to pruning")
    prune_height: int = Query(
        None,
        description="Lowest-height complete block stored(only present if pruning is enabled)",
    )
    automatic_pruning: bool = Query(
        None,
        description="Whether automatic pruning is enabled(only present if pruning is enabled)",
    )
    prune_target_size: int = Query(
        None,
        description="The target size used by pruning(only present if automatic pruning is enabled)",
    )
    warnings: str = Query(..., description="Any network and blockchain warnings")
    softforks: List[SoftFork] = Query(..., description="Status of softforks")

    @classmethod
    def from_rpc(cls, r):

        # get softfork information if available
        softforks = []
        if "softforks" in r:
            for name in r["softforks"]:
                softforks.append(SoftFork.from_rpc(name, r["softforks"][name]))

        return cls(
            chain=r["chain"],
            blocks=r["blocks"],
            headers=r["headers"],
            best_block_hash=r["bestblockhash"],
            difficulty=r["difficulty"],
            mediantime=r["mediantime"],
            verification_progress=r["verificationprogress"],
            initial_block_download=r["initialblockdownload"],
            chainwork=r["chainwork"],
            size_on_disk=r["size_on_disk"],
            pruned=r["pruned"],
            pruned_height=None if not "pruneheight" in r else r["pruneheight"],
            automatic_pruning=None
            if not "automatic_pruning" in r
            else r["automatic_pruning"],
            prune_target_size=None
            if not "prune_target_size" in r
            else r["prune_target_size"],
            warnings=r["warnings"],
            softforks=softforks,
        )


class BtcInfo(BaseModel):
    # Info regarding bitcoind
    blocks: int = Query(
        ...,
        description="The height of the most-work fully-validated chain. The genesis block has height 0",
    )
    headers: int = Query(
        ..., description="The current number of headers we have validated"
    )
    verification_progress: float = Query(
        ..., description="Estimate of verification progress[0..1]"
    )
    difficulty: int = Query(..., description="The current difficulty")
    size_on_disk: int = Query(
        ..., description="The estimated size of the block and undo files on disk"
    )
    networks: List[BtcNetwork] = Query(
        [], description="Which networks are in use (ipv4, ipv6 or onion)"
    )
    version: int = Query(..., description="The bitcoin core server version")
    subversion: str = Query(..., description="The server subversion string")
    connections_in: int = Query(..., description="The number of inbound connections")
    connections_out: int = Query(..., description="The number of outbound connections")

    @classmethod
    def from_rpc(cls, binfo: BlockchainInfo, ninfo: NetworkInfo):
        return cls(
            blocks=binfo.blocks,
            headers=binfo.headers,
            verification_progress=binfo.verification_progress,
            difficulty=binfo.difficulty,
            size_on_disk=binfo.size_on_disk,
            networks=ninfo.networks,
            version=ninfo.version,
            subversion=ninfo.subversion,
            connections_in=ninfo.connections_in,
            connections_out=ninfo.connections_out,
        )

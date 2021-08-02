from enum import Enum
from typing import List, Optional, Union

from deepdiff import DeepDiff
from pydantic import BaseModel


class InvoiceState(str, Enum):
    open = "open"
    settled = "settled"
    canceled = "canceled"
    accepted = "accepted"


def invoice_settled_from_grpc(id):
    if(id == 0):
        return InvoiceState.open
    elif(id == 1):
        return InvoiceState.settled
    elif(id == 2):
        return InvoiceState.canceled
    elif(id == 3):
        return InvoiceState.accepted
    else:
        raise NotImplementedError(f"InvoiceState {id} is not implemented")


class InvoiceHTLCState(str, Enum):
    accepted = "accepted"
    settled = "settled"
    canceled = "canceled"


def invoice_settled_from_grpc(id):
    if(id == 0):
        return InvoiceHTLCState.accepted
    elif(id == 1):
        return InvoiceHTLCState.settled
    elif(id == 2):
        return InvoiceHTLCState.canceled
    else:
        raise NotImplementedError(f"InvoiceHTLCState {id} is not implemented")


class Feature(BaseModel):
    name: str
    is_required: bool
    is_known: bool


def feature_from_grpc(f):
    return Feature(
        name=f.name,
        is_required=f.is_required,
        is_known=f.is_known,
    )


class FeaturesEntry(BaseModel):
    key: int
    value: Feature


def features_entry_from_grpc(entry_key, feature):
    return FeaturesEntry(
        key=entry_key,
        value=feature_from_grpc(feature),
    )


class AMP(BaseModel):
    # An n-of-n secret share of the root seed from
    # which child payment hashes and preimages are derived.
    root_share: str

    # An identifier for the HTLC set that this HTLC belongs to.
    set_id: str

    # A nonce used to randomize the child preimage and
    # child hash from a given root_share.
    child_index: int

    # The payment hash of the AMP HTLC.
    hash: str

    # The preimage used to settle this AMP htlc.
    # This field will only be populated if the invoice
    # is in InvoiceState_ACCEPTED or InvoiceState_SETTLED.
    preimage: str


def amp_from_grpc(a) -> AMP:
    return AMP(
        root_share=a.root_share.hex(),
        set_id=a.set_id.hex(),
        child_index=a.child_index,
        hash=a.hash.hex(),
        preimage=a.preimage.hex(),
    )


class CustomRecordsEntry(BaseModel):
    key	: int
    value:	str


def custom_record_entry_from_grpc(e) -> CustomRecordsEntry:
    return CustomRecordsEntry(
        key=e.key,
        value=e.value,
    )


class InvoiceHTLC(BaseModel):
    # Short channel id over which the htlc was received.
    chan_id: int

    # Index identifying the htlc on the channel.
    htlc_index:	int

    # The amount of the htlc in msat.
    amt_msat:	int

    # Block height at which this htlc was accepted.
    accept_height: int

    # Time at which this htlc was accepted.
    accept_time: int

    # Time at which this htlc was settled or canceled.
    resolve_time: int

    # Block height at which this htlc expires.
    expiry_height: int

    # Current state the htlc is in.
    state: InvoiceHTLCState

    # Custom tlv records.
    custom_records:	List[CustomRecordsEntry]

    # The total amount of the mpp payment in msat.
    mpp_total_amt_msat: int

    # Details relevant to AMP HTLCs, only populated
    # if this is an AMP HTLC.
    amp: AMP


def invoice_htlc_from_grpc(h) -> InvoiceHTLC:
    def _crecords(recs):
        l = []
        for r in recs:
            l.append(custom_record_entry_from_grpc(r))
        return l

    return InvoiceHTLC(
        chan_id=h.chan_id,
        htlc_index=h.htlc_index,
        amt_msat=h.amt_msat,
        accept_height=h.accept_height,
        accept_time=h.accept_time,
        resolve_time=h.resolve_time,
        expiry_height=h.expiry_height,
        state=invoice_settled_from_grpc(h.state),
        custom_records=_crecords(h.custom_records),
        mpp_total_amt_msat=h.mpp_total_amt_msat,
        amp=amp_from_grpc(h.amp),

    )


class RouteHint(BaseModel):
    # The public key of the node at the start of the channel.
    node_id: str

    # The unique identifier of the channel.
    chan_id: int

    # The base fee of the channel denominated in millisatoshis.
    fee_base_msat: int

    # The fee rate of the channel for sending one satoshi
    # across it denominated in millionths of a satoshi.
    fee_proportional_millionths: int

    # The time-lock delta of the channel.
    cltv_expiry_delta: int


def route_hint_from_grpc(h) -> RouteHint:
    return RouteHint(
        node_id=h.node_id,
        chan_id=h.chan_id,
        fee_base_msat=h.fee_base_msat,
        fee_proportional_millionths=h.fee_proportional_millionths,
        cltv_expiry_delta=h.cltv_expiry_delta,
    )


class Invoice(BaseModel):
    # optional memo to attach along with the invoice.
    # Used for record keeping purposes for the invoice's
    # creator, and will also be set in the description
    # field of the encoded payment request if the
    # description_hash field is not being used.
    memo: Optional[str]

    # The hex-encoded preimage(32 byte) which will allow
    # settling an incoming HTLC payable to this preimage.
    r_preimage: Optional[str]

    # The hash of the preimage.
    r_hash: Optional[str]

    # The value of this invoice in satoshis
    # The fields value and value_msat are mutually exclusive.
    value: Optional[int]
    # The value of this invoice in millisatoshis The
    # fields value and value_msat are mutually exclusive.
    value_msat: Optional[int]

    # Whether this invoice has been fulfilled
    settled: Optional[bool]

    # When this invoice was created
    creation_date: Optional[int]

    # When this invoice was settled
    settle_date: Optional[int]

    # A bare-bones invoice for a payment within the
    # Lightning Network. With the details of the invoice,
    # the sender has all the data necessary to send a
    # payment to the recipient.
    payment_request: Optional[str]

    # Hash(SHA-256) of a description of the payment.
    # Used if the description of payment(memo) is too
    # long to naturally fit within the description field of
    # an encoded payment request.
    description_hash: Optional[str]

    # Payment request expiry time in seconds. Default is 3600 (1 hour).
    expiry: Optional[int]

    # Fallback on-chain address.
    fallback_addr: Optional[str]

    # Delta to use for the time-lock of the CLTV extended to the final hop.
    cltv_expiry	: Optional[int]

    # Route hints that can each be individually used
    # to assist in reaching the invoice's destination.
    route_hints: Optional[List[RouteHint]]

    # Whether this invoice should include routing hints for private channels.
    private: Optional[bool]

    # The "add" index of this invoice. Each newly created invoice
    # will increment this index making it monotonically increasing.
    # Callers to the SubscribeInvoices call can use this to instantly
    # get notified of all added invoices with an add_index greater than this one.
    add_index: Optional[int]

    # The "settle" index of this invoice. Each newly settled invoice will
    # increment this index making it monotonically increasing. Callers to
    # the SubscribeInvoices call can use this to instantly get notified of
    # all settled invoices with an settle_index greater than this one.
    settle_index: Optional[int]

    # The amount that was accepted for this invoice, in satoshis. This
    # will ONLY be set if this invoice has been settled. We provide
    # this field as if the invoice was created with a zero value,
    # then we need to record what amount was ultimately accepted.
    # Additionally, it's possible that the sender paid MORE that
    # was specified in the original invoice. So we'll record that here as well.
    amt_paid_sat: Optional[int]

    # The amount that was accepted for this invoice, in millisatoshis.
    # This will ONLY be set if this invoice has been settled. We
    # provide this field as if the invoice was created with a zero value,
    # then we need to record what amount was ultimately accepted. Additionally,
    # it's possible that the sender paid MORE that was specified in the
    # original invoice. So we'll record that here as well.
    amt_paid_msat: Optional[int]

    # The state the invoice is in.
    state: Optional[InvoiceState]

    # List of HTLCs paying to this invoice[EXPERIMENTAL].
    htlcs: Optional[List[InvoiceHTLC]]

    # List of features advertised on the invoice.
    features: Optional[List[FeaturesEntry]]

    # Indicates if this invoice was a spontaneous payment
    # that arrived via keysend[EXPERIMENTAL].
    is_keysend: Optional[bool]

    # The payment address of this invoice. This value will
    # be used in MPP payments, and also for newer invoices
    # that always require the MPP payload for added end-to-end security.
    payment_addr: Optional[str]

    # Signals whether or not this is an AMP invoice.
    is_amp:	Optional[bool]


def invoice_from_grpc(i) -> Invoice:
    def _route_hints(hints):
        l = []
        for h in hints:
            l.append(route_hint_from_grpc(h))
        return l

    def _htlcs(htlcs):
        l = []
        for h in htlcs:
            l.append(invoice_htlc_from_grpc(h))
        return l

    def _features(features):
        l = []
        for k in features:
            l.append(features_entry_from_grpc(k, features[k]))
        return l

    return Invoice(
        memo=i.memo,
        r_preimage=i.r_preimage.hex(),
        r_hash=i.r_hash.hex(),
        value=i.value,
        value_msat=i.value_msat,
        settled=i.settled,
        creation_date=i.creation_date,
        settle_date=i.settle_date,
        payment_request=i.payment_request,
        description_hash=i.description_hash,
        expiry=i.expiry,
        fallback_addr=i.fallback_addr,
        cltv_expiry=i.cltv_expiry,
        route_hints=_route_hints(i.route_hints),
        private=i.private,
        add_index=i.add_index,
        settle_index=i.settle_index,
        amt_paid_sat=i.amt_paid_sat,
        amt_paid_msat=i.amt_paid_msat,
        state=invoice_settled_from_grpc(i.state),
        htlcs=_htlcs(i.htlcs),
        features=_features(i.features),
        is_keysend=i.is_keysend,
        payment_addr=i.payment_addr.hex(),
        is_amp=i.is_amp,
    )


class PaymentStatus(str, Enum):
    UNKNOWN = "unknown"
    IN_FLIGHT = "in_flight"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


def payment_status_from_grpc(id):
    if id == 0:
        return PaymentStatus.UNKNOWN
    elif id == 1:
        return PaymentStatus.IN_FLIGHT
    elif id == 2:
        return PaymentStatus.SUCCEEDED
    elif id == 3:
        return PaymentStatus.FAILED
    else:
        raise NotImplementedError(f"PaymentStatus {id} is not implemented")


class PaymentFailureReason(str, Enum):
    # Payment isn't failed(yet).
    FAILURE_REASON_NONE = "FAILURE_REASON_NONE"

    # There are more routes to try, but the payment timeout was exceeded.
    FAILURE_REASON_TIMEOUT = "FAILURE_REASON_TIMEOUT"

    # All possible routes were tried and failed permanently.
    # Or were no routes to the destination at all.
    FAILURE_REASON_NO_ROUTE = "FAILURE_REASON_NO_ROUTE"

    # A non-recoverable error has occurred.
    FAILURE_REASON_ERROR = "FAILURE_REASON_ERROR"

    # Payment details incorrect(unknown hash, invalid amt or invalid final cltv delta)
    FAILURE_REASON_INCORRECT_PAYMENT_DETAILS = "FAILURE_REASON_INCORRECT_PAYMENT_DETAILS"

    # Insufficient local balance.
    FAILURE_REASON_INSUFFICIENT_BALANCE = "FAILURE_REASON_INSUFFICIENT_BALANCE"


def payment_failure_reason(f) -> PaymentFailureReason:
    if f == 0:
        return PaymentFailureReason.FAILURE_REASON_NONE
    elif f == 1:
        return PaymentFailureReason.FAILURE_REASON_TIMEOUT
    elif f == 2:
        return PaymentFailureReason.FAILURE_REASON_NO_ROUTE
    elif f == 3:
        return PaymentFailureReason.FAILURE_REASON_ERROR
    elif f == 4:
        return PaymentFailureReason.FAILURE_REASON_INCORRECT_PAYMENT_DETAILS
    elif f == 5:
        return PaymentFailureReason.FAILURE_REASON_INSUFFICIENT_BALANCE
    else:
        raise NotImplementedError(
            f"PaymentFailureReason {id} is not implemented")


class ChannelUpdate(BaseModel):
    # The signature that validates the announced data and proves the ownership of node id.
    signature: str

    # The target chain that this channel was opened within. This value should be the
    # genesis hash of the target chain. Along with the short channel ID, this uniquely
    # identifies the channel globally in a blockchain.
    chain_hash: str

    # The unique description of the funding transaction.
    chan_id: int

    # A timestamp that allows ordering in the case of
    # multiple announcements. We should ignore the message if
    # timestamp is not greater than the last-received.
    timestamp: int

    # The bitfield that describes whether optional fields are present in this update.
    # Currently, the least-significant bit must be set to 1 if the optional field MaxHtlc is present.
    message_flags: int

    # The bitfield that describes additional meta-data concerning how the update is to be interpreted.
    # Currently, the least-significant bit must be set to 0 if the creating node corresponds to the
    # first node in the previously sent channel announcement and 1 otherwise. If the second bit is set,
    # then the channel is set to be disabled.
    channel_flags: int

    # The minimum number of blocks this node requires to be added to the expiry of HTLCs.
    # This is a security parameter determined by the node operator. This value represents the
    # required gap between the time locks of the incoming and outgoing HTLC's set to this node.
    time_lock_delta: int

    # The minimum HTLC value which will be accepted.
    htlc_minimum_msat: int

    # The base fee that must be used for incoming HTLC's to this particular channel.
    # This value will be tacked onto the required for a payment independent of the size of the payment.
    base_fee: int

    # The fee rate that will be charged per millionth of a satoshi.
    fee_rate: int

    # The maximum HTLC value which will be accepted.
    htlc_maximum_msat: int

    # The set of data that was appended to this message, some of which we may not actually know how to
    # iterate or parse. By holding onto this data, we ensure that we're able to properly validate the
    # set of signatures that cover these new fields, and ensure we're able to make upgrades to the
    # network in a forwards compatible manner.
    extra_opaque_data: str


def channel_update_from_grpc(u) -> ChannelUpdate:
    return ChannelUpdate(
        signature=u.signature,
        chain_hash=u.chain_hash,
        chan_id=u.chan_id,
        timestamp=u.timestamp,
        message_flags=u.message_flags,
        channel_flags=u.channel_flags,
        time_lock_delta=u.time_lock_delta,
        htlc_minimum_msat=u.htlc_minimum_msat,
        base_fee=u.base_fee,
        fee_rate=u.fee_rate,
        htlc_maximum_msat=u.htlc_maximum_msat,
        extra_opaque_data=u.extra_opaque_data,
    )


class Hop(BaseModel):
    # The unique channel ID for the channel. The first 3
    # bytes are the block height, the next 3 the index within the
    # block, and the last 2 bytes are the output index for the channel.
    chan_id: int

    chan_capacity: int
    amt_to_forward: int
    fee: int
    expiry: int
    amt_to_forward_msat: int
    fee_msat: int

    # An optional public key of the hop. If the public key is given,
    # the payment can be executed without relying on a copy of the channel graph.
    pub_key: str

    # If set to true, then this hop will be encoded using the new variable length TLV format.
    # Note that if any custom tlv_records below are specified, then this field MUST be set
    # to true for them to be encoded properly.
    tlv_payload: bool


def hop_from_grpc(h) -> Hop:
    return Hop(
        chan_id=h.chan_id,
        chan_capacity=h.chan_capacity,
        amt_to_forward=h.amt_to_forward,
        fee=h.fee,
        expiry=h.expiry,
        amt_to_forward_msat=h.amt_to_forward_msat,
        fee_msat=h.fee_msat,
        pub_key=h.pub_key,
        tlv_payload=h.tlv_payload,
    )


class MPPRecord(BaseModel):
    payment_addr: str
    total_amt_msat: int


def mpp_record_from_grpc(r) -> MPPRecord:
    return MPPRecord(
        payment_addr=r.payment_addr,
        total_amt_msat=r.total_amt_msat,
    )


class AMPRecord(BaseModel):
    root_share: str
    set_id: str
    child_index: int


def amp_record_from_grpc(r) -> AMPRecord:
    return AMPRecord(
        root_share=r.root_share,
        set_id=r.set_id,
        child_index=r.child_index,
    )


class Route(BaseModel):
    total_time_lock: int
    total_fees: int
    total_amt: int
    hops: List[Hop]
    total_fees_msat: int
    total_amt_msat: int
    mpp_record: Union[MPPRecord, None]
    amp_record: Union[AMPRecord, None]
    custom_records:	List[CustomRecordsEntry]


def route_from_grpc(r):
    def _crecords(recs):
        l = []
        for r in recs:
            l.append(custom_record_entry_from_grpc(r))
        return l

    def _get_hops(hops) -> List[Hop]:
        l = []
        for h in hops:
            l.append(hop_from_grpc(h))
        return l

    mpp = None
    if hasattr(r, "mpp_record"):
        mpp = mpp_record_from_grpc(r.mpp_record)

    amp = None
    if hasattr(r, "amp_record"):
        amp = amp_record_from_grpc(r.amp_record)

    crecords = []
    if hasattr(r, "custom_records"):
        crecords = _crecords(r.custom_records)

    return Route(
        total_time_lock=r.total_time_lock,
        total_fees=r.total_fees,
        total_amt=r.total_amt,
        hops=_get_hops(r.hops),
        total_fees_msat=r.total_fees_msat,
        total_amt_msat=r.total_amt_msat,
        mpp_record=mpp,
        amp_record=amp,
        custom_records=crecords
    )


class HTLCAttemptFailure(BaseModel):
    # Failure code as defined in the Lightning spec
    code: int

    # An optional channel update message.
    channel_update: ChannelUpdate

    # A failure type-dependent htlc value.
    htlc_msat: int

    # The sha256 sum of the onion payload.
    onion_sha_256: str

    # A failure type-dependent cltv expiry value.
    cltv_expiry: int

    # A failure type-dependent flags value.
    flags: int

    # The position in the path of the intermediate
    # or final node that generated the failure message.
    # Position zero is the sender node.
    failure_source_index: int

    # A failure type-dependent block height.
    height: int


def htlc_attempt_failure_from_grpc(f) -> HTLCAttemptFailure:
    code = None
    if hasattr(f, "code"):
        code = f.code

    htlc_msat = None
    if hasattr(f, "htlc_msat"):
        htlc_msat = f.htlc_msat

    return HTLCAttemptFailure(
        code=code,
        channel_update=channel_update_from_grpc(f.channel_update),
        htlc_msat=htlc_msat,
        onion_sha_256=f.onion_sha_256,
        cltv_expiry=f.cltv_expiry,
        flags=f.flags,
        failure_source_index=f.failure_source_index,
        height=f.height,
    )


class HTLCStatus(str, Enum):
    IN_FLIGHT = "IN_FLIGHT"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"


def htlc_status_from_grpc(s) -> HTLCStatus:
    if s == 0:
        return HTLCStatus.IN_FLIGHT
    elif s == 1:
        return HTLCStatus.SUCCEEDED
    elif s == 2:
        return HTLCStatus.FAILED
    else:
        raise NotImplementedError(f"HTLCStatus {id} is not implemented")


class HTLCAttempt(BaseModel):
    # The unique ID that is used for this attempt.
    attempt_id: int

    # The status of the HTLC.
    status: HTLCStatus

    # The route taken by this HTLC.
    route: Route

    # The time in UNIX nanoseconds at which this HTLC was sent.
    attempt_time_ns: int

    # The time in UNIX nanoseconds at which this HTLC was settled
    # or failed. This value will not be set if the HTLC is still IN_FLIGHT.
    resolve_time_ns: int

    # Detailed htlc failure info.
    failure: HTLCAttemptFailure

    # The preimage that was used to settle the HTLC.
    preimage: str


def htlc_attempt_from_grpc(a: HTLCAttempt) -> HTLCAttempt:
    return HTLCAttempt(
        attempt_id=a.attempt_id,
        status=htlc_status_from_grpc(a.status),
        route=route_from_grpc(a.route),
        attempt_time_ns=a.attempt_time_ns,
        resolve_time_ns=a.resolve_time_ns,
        failure=htlc_attempt_failure_from_grpc(a.failure),
        preimage=a.preimage.hex(),
    )


class Payment(BaseModel):
    # The payment hash
    payment_hash: str

    # The payment preimage
    payment_preimage: Optional[str]

    # The value of the payment in milli-satoshis
    value_msat: int

    # The optional payment request being fulfilled.
    payment_request: Optional[str]

    # The status of the payment.
    status:	PaymentStatus = PaymentStatus.UNKNOWN

    # The fee paid for this payment in milli-satoshis
    fee_msat: int

    # The time in UNIX nanoseconds at which the payment was created.
    creation_time_ns: int

    # The HTLCs made in attempt to settle the payment.
    htlcs: List[HTLCAttempt] = []

    # The creation index of this payment. Each payment can be uniquely
    # identified by this index, which may not strictly increment by 1
    # for payments made in older versions of lnd.
    payment_index: int

    # The failure reason
    failure_reason:	PaymentFailureReason


def payment_from_grpc(p) -> Payment:
    def _get_attempts(attempts):
        l = []
        for a in attempts:
            l.append(htlc_attempt_from_grpc(a))
        return l

    return Payment(
        payment_hash=p.payment_hash,
        payment_preimage=p.payment_preimage,
        value_msat=p.value_msat,
        payment_request=p.payment_request,
        status=payment_status_from_grpc(p.status),
        fee_msat=p.fee_msat,
        creation_time_ns=p.creation_time_ns,
        htlcs=_get_attempts(p.htlcs),
        payment_index=p.payment_index,
        failure_reason=payment_failure_reason(p.failure_reason),
    )


class Chain(BaseModel):
    # The blockchain the node is on(eg bitcoin, litecoin)
    chain: str

    # The network the node is on(eg regtest, testnet, mainnet)
    network: str


class LnInfo(BaseModel):
    # The version of the LND software that the node is running.
    version: str

    # The SHA1 commit hash that the daemon is compiled with.
    commit_hash: str

    # The identity pubkey of the current node.
    identity_pubkey: str

    # If applicable, the alias of the current node, e.g. "bob"
    alias: str

    # The color of the current node in hex code format
    color: str

    # Number of pending channels
    num_pending_channels: int

    # Number of active channels
    num_active_channels: int

    # Number of inactive channels
    num_inactive_channels: int

    # Number of peers
    num_peers: int

    # The node's current view of the height of the best block
    block_height: int

    # The node's current view of the hash of the best block
    block_hash: str

    # Timestamp of the block best known to the wallet
    best_header_timestamp: int

    # Whether the wallet's view is synced to the main chain
    synced_to_chain: bool

    # Whether we consider ourselves synced with the public channel graph.
    synced_to_graph: bool

    # A list of active chains the node is connected to
    chains: List[Chain]

    # The URIs of the current node.
    uris: List[str]

    # Features that our node has advertised in our init message,
    # node announcements and invoices.
    features: List[FeaturesEntry]

    def __eq__(self, other):
        if isinstance(other, self.__class__):
            diff = DeepDiff(self, other, ignore_order=True)
            return len(diff) == 0
        else:
            return False

    def __ne__(self, other):
        return not self.__eq__(other)


def ln_info_from_grpc(i) -> LnInfo:
    _chains = []
    for c in i.chains:
        _chains.append(Chain(chain=c.chain, network=c.network))

    _features = []
    for f in i.features:
        _features.append(features_entry_from_grpc(f, i.features[f]))

    _uris = [u for u in i.uris]

    return LnInfo(
        version=i.version,
        commit_hash=i.commit_hash,
        identity_pubkey=i.identity_pubkey,
        alias=i.alias,
        color=i.color,
        num_pending_channels=i.num_pending_channels,
        num_active_channels=i.num_active_channels,
        num_inactive_channels=i.num_inactive_channels,
        num_peers=i.num_peers,
        block_height=i.block_height,
        block_hash=i.block_hash,
        best_header_timestamp=i.best_header_timestamp,
        synced_to_chain=i.synced_to_chain,
        synced_to_graph=i.synced_to_graph,
        chains=_chains,
        uris=_uris,
        features=_features,
    )

from enum import Enum
from typing import List, Optional

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

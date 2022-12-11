import logging
from enum import Enum
from typing import List, Optional, Union

from deepdiff import DeepDiff
from fastapi.param_functions import Query
from pydantic import BaseModel, validator
from pydantic.types import conint

import app.lightning.docs as docs
from app.lightning.utils import parse_cln_msat


class LnInitState(str, Enum):
    OFFLINE = "offline"
    BOOTSTRAPPING = "bootstrapping"
    BOOTSTRAPPING_AFTER_UNLOCK = "bootstrapping_after_unlock"
    DONE = "done"
    LOCKED = "locked"


class InitLnRepoUpdate:
    state: LnInitState
    msg: Optional[str]

    def __init__(self, state: LnInitState = LnInitState.OFFLINE, msg: str = ""):
        self.state = state
        self.msg = msg

    def dict(self) -> dict:
        return {
            "state": self.state,
            "msg": self.msg,
        }


class OnchainAddressType(str, Enum):
    P2WKH = "p2wkh"
    NP2WKH = "np2wkh"


class InvoiceState(str, Enum):
    OPEN = "open"
    SETTLED = "settled"
    CANCELED = "canceled"
    ACCEPTED = "accepted"

    @classmethod
    def from_lnd_grpc(cls, id) -> "InvoiceState":
        if id == 0:
            return InvoiceState.OPEN
        elif id == 1:
            return InvoiceState.SETTLED
        elif id == 2:
            return InvoiceState.CANCELED
        elif id == 3:
            return InvoiceState.ACCEPTED
        else:
            raise NotImplementedError(f"InvoiceState {id} is not implemented")

    @classmethod
    def from_cln_json(cls, id) -> "InvoiceState":
        if id == "unpaid":
            return InvoiceState.OPEN
        elif id == "paid":
            return InvoiceState.SETTLED
        elif id == "expired":
            return InvoiceState.CANCELED
        else:
            raise NotImplementedError(f"InvoiceState {id} is not implemented")

    @classmethod
    def from_cln_grpc(cls, i) -> "InvoiceState":
        if i.status == 0:
            return InvoiceState.OPEN
        elif i.status == 1:
            return InvoiceState.SETTLED
        elif i.status == 2:
            return InvoiceState.CANCELED
        else:
            raise NotImplementedError(f"InvoiceState {id} is not implemented")


class InvoiceHTLCState(str, Enum):
    ACCEPTED = "accepted"
    SETTLED = "settled"
    CANCELED = "canceled"

    @classmethod
    def from_lnd_grpc(cls, id) -> "InvoiceHTLCState":
        if id == 0:
            return InvoiceHTLCState.ACCEPTED
        elif id == 1:
            return InvoiceHTLCState.SETTLED
        elif id == 2:
            return InvoiceHTLCState.CANCELED
        else:
            raise NotImplementedError(f"InvoiceHTLCState {id} is not implemented")


class FeeRevenue(BaseModel):
    day: int = Query(..., description="Fee revenue earned in the last 24 hours")
    week: int = Query(..., description="Fee revenue earned in the last 7days")
    month: int = Query(..., description="Fee revenue earned in the last month")
    year: int = Query(
        None,
        description="Fee revenue earned in the last year. Might be null if not implemented by backend.",
    )
    total: int = Query(
        None,
        description="Fee revenue earned in the last year. Might be null if not implemented by backend",
    )

    @classmethod
    def from_lnd_grpc(cls, fee_report) -> "FeeRevenue":
        return cls(
            day=int(fee_report.day_fee_sum),
            week=int(fee_report.week_fee_sum),
            month=int(fee_report.month_fee_sum),
        )

    @classmethod
    def from_cln_json(cls, fee_report) -> "FeeRevenue":
        return cls(
            day=int(fee_report["day_fee_sum"]),
            week=int(fee_report["week_fee_sum"]),
            month=int(fee_report["month_fee_sum"]),
        )


class ForwardSuccessEvent(BaseModel):
    timestamp_ns: int = Query(
        ...,
        description="The number of nanoseconds elapsed since January 1, 1970 UTC when this circuit was completed.",
    )
    chan_id_in: str = Query(
        ...,
        description="The incoming channel ID that carried the HTLC that created the circuit.",
    )
    chan_id_out: str = Query(
        ...,
        description="The outgoing channel ID that carried the preimage that completed the circuit.",
    )
    amt_in_msat: int = Query(
        ...,
        description="The total amount (in millisatoshis) of the incoming HTLC that created half the circuit.",
    )
    amt_out_msat: str = Query(
        ...,
        description="The total amount (in millisatoshis) of the outgoing HTLC that created the second half of the circuit.",
    )
    fee_msat: int = Query(
        ...,
        description="The total fee (in millisatoshis) that this payment circuit carried.",
    )

    @classmethod
    def from_lnd_grpc(cls, evt) -> "ForwardSuccessEvent":
        return cls(
            timestamp=int(evt.timestamp),
            chan_id_in=int(evt.chan_id_in),
            chan_id_out=int(evt.chan_id_out),
            amt_in_msat=int(evt.amt_in_msat),
            amt_out_msat=int(evt.amt_out_msat),
            fee_msat=int(evt.fee_msat),
        )

    @classmethod
    def from_cln_json(cls, fwd) -> "ForwardSuccessEvent":
        return cls(
            timestamp_ns=fwd["resolved_time"],
            chan_id_in=fwd["in_channel"],
            chan_id_out=fwd["out_channel"],
            amt_in_msat=fwd["in_msatoshi"],
            amt_out_msat=fwd["out_msatoshi"],
            fee_msat=fwd["fee"],
        )

    @classmethod
    def from_cln_grpc(cls, fwd) -> "ForwardSuccessEvent":
        return cls(
            timestamp_ns=fwd.received_time,
            chan_id_in=fwd.in_channel,
            chan_id_out=fwd.out_channel,
            amt_in_msat=fwd.in_msat.msat,
            amt_out_msat=fwd.out_msat.msat,
            fee_msat=fwd.fee_msat.msat,
        )


class Feature(BaseModel):
    name: str
    is_required: Optional[bool]
    is_known: Optional[bool]

    @classmethod
    def from_lnd_grpc(cls, f) -> "Feature":
        return cls(
            name=f.name,
            is_required=f.is_required,
            is_known=f.is_known,
        )

    @classmethod
    def from_cln_json(cls, f) -> "Feature":
        return cls(name=f)


class FeaturesEntry(BaseModel):
    key: int
    value: Feature

    @classmethod
    def from_lnd_grpc(cls, entry_key, feature) -> "FeaturesEntry":
        return cls(
            key=entry_key,
            value=Feature.from_lnd_grpc(feature),
        )

    @classmethod
    def from_cln_json(self, entry_key, feature):
        return self(
            key=entry_key,
            value=Feature.from_cln_json(feature),
        )


class Amp(BaseModel):
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

    @classmethod
    def from_lnd_grpc(cls, a) -> "Amp":
        return cls(
            root_share=a.root_share.hex(),
            set_id=a.set_id.hex(),
            child_index=a.child_index,
            hash=a.hash.hex(),
            preimage=a.preimage.hex(),
        )


class CustomRecordsEntry(BaseModel):
    key: int
    value: str

    @classmethod
    def from_lnd_grpc(cls, e) -> "CustomRecordsEntry":
        return cls(
            key=e.key,
            value=e.value,
        )


class InvoiceHTLC(BaseModel):
    chan_id: int = Query(
        ..., description="The channel ID over which the HTLC was received."
    )

    htlc_index: int = Query(..., description="The index of the HTLC on the channel.")

    amt_msat: int = Query(..., description="The amount of the HTLC in msat.")

    accept_height: int = Query(
        ..., description="The block height at which this HTLC was accepted."
    )

    accept_time: int = Query(
        ..., description="The time at which this HTLC was accepted."
    )

    resolve_time: int = Query(
        ..., description="The time at which this HTLC was resolved."
    )

    expiry_height: int = Query(
        ..., description="The block height at which this HTLC expires."
    )

    state: InvoiceHTLCState = Query(..., description="The state of the HTLC.")

    custom_records: List[CustomRecordsEntry] = Query(
        [], description="Custom tlv records."
    )

    mpp_total_amt_msat: int = Query(
        ..., description="The total amount of the mpp payment in msat."
    )

    amp: Amp = Query(
        None,
        description="Details relevant to AMP HTLCs, only populated if this is an AMP HTLC.",
    )

    @classmethod
    def from_lnd_grpc(cls, h) -> "InvoiceHTLC":
        def _crecords(recs):
            l = []
            for r in recs:
                l.append(CustomRecordsEntry.from_lnd_grpc(r))
            return l

        return cls(
            chan_id=h.chan_id,
            htlc_index=h.htlc_index,
            amt_msat=h.amt_msat,
            accept_height=h.accept_height,
            accept_time=h.accept_time,
            resolve_time=h.resolve_time,
            expiry_height=h.expiry_height,
            state=InvoiceHTLCState.from_lnd_grpc(h.state),
            custom_records=_crecords(h.custom_records),
            mpp_total_amt_msat=h.mpp_total_amt_msat,
            amp=Amp.from_lnd_grpc(h.amp),
        )


class HopHint(BaseModel):
    node_id: str = Query(
        ..., description="The public key of the node at the start of the channel."
    )

    chan_id: str = Query(..., description="The unique identifier of the channel.")

    fee_base_msat: int = Query(
        ..., description="The base fee of the channel denominated in msat."
    )

    fee_proportional_millionths: int = Query(
        ...,
        description="The fee rate of the channel for sending one satoshi across it denominated in msat",
    )

    cltv_expiry_delta: int = Query(
        ..., description="The time-lock delta of the channel."
    )

    @classmethod
    def from_lnd_grpc(cls, h) -> "HopHint":
        return cls(
            node_id=h.node_id,
            chan_id=h.chan_id,
            fee_base_msat=h.fee_base_msat,
            fee_proportional_millionths=h.fee_proportional_millionths,
            cltv_expiry_delta=h.cltv_expiry_delta,
        )

    @classmethod
    def from_cln_json(cls, h) -> "HopHint":
        return cls(
            node_id=h["pubkey"],
            chan_id=h["short_channel_id"],
            fee_base_msat=h["fee_base_msat"],
            fee_proportional_millionths=h["fee_proportional_millionths"],
            cltv_expiry_delta=h["cltv_expiry_delta"],
        )


class RouteHint(BaseModel):
    hop_hints: List[HopHint] = Query(
        [],
        description="A list of hop hints that when chained together can assist in reaching a specific destination.",
    )

    @classmethod
    def from_lnd_grpc(cls, h) -> "RouteHint":
        hop_hints = [HopHint.from_lnd_grpc(hh) for hh in h.hop_hints]
        return cls(hop_hints=hop_hints)

    @classmethod
    def from_cln_json(cls, h) -> "RouteHint":
        hop_hints = [HopHint.from_cln_json(hop_hint) for hop_hint in h]
        return cls(hop_hints=hop_hints)


class Channel(BaseModel):

    channel_id: Optional[str]
    active: Optional[bool]

    peer_publickey: Optional[str]
    peer_alias: Optional[str]

    balance_local: Optional[int]
    balance_remote: Optional[int]
    balance_capacity: Optional[int]

    @classmethod
    def from_lnd_grpc(cls, c) -> "Channel":
        return cls(
            active=c.active,
            channel_id=c.channel_point,  # use channel point as id because thats needed for closing the channel with lnd
            peer_publickey=c.remote_pubkey,
            peer_alias="n/a",
            balance_local=c.local_balance,
            balance_remote=c.remote_balance,
            balance_capacity=c.capacity,
        )

    @classmethod
    def from_lnd_grpc_pending(cls, c) -> "Channel":
        return cls(
            active=False,
            channel_id=c.channel_point,  # use channel point as id because thats needed for closing the channel with lnd
            peer_publickey=c.remote_node_pub,
            peer_alias="n/a",
            balance_local=-1,
            balance_remote=-1,
            balance_capacity=c.capacity,
        )

    @classmethod
    def from_cln_grpc(cls, c, peer_alias="n/a") -> "Channel":
        # TODO: get alias and balance of the channel
        return cls(
            active=c.connected,
            channel_id=c.short_channel_id,  # use channel point as id because thats needed for closing the channel with lnd
            peer_publickey=c.peer_id.hex(),
            peer_alias=peer_alias,
            balance_local=c.our_amount_msat.msat,
            balance_remote=c.amount_msat.msat - c.our_amount_msat.msat,
            balance_capacity=c.amount_msat.msat,
        )


class Invoice(BaseModel):
    memo: str = Query(
        None,
        description="""Optional memo to attach along with the invoice. Used for record keeping purposes for the invoice's creator,
        and will also be set in the description field of the encoded payment request if the description_hash field is not being used.""",
    )

    r_preimage: str = Query(
        None,
        description="""The hex-encoded preimage(32 byte) which will allow settling an incoming HTLC payable to this preimage.""",
    )

    r_hash: str = Query(None, description="The hash of the preimage.")

    value_msat: int = Query(
        ..., description="The value of this invoice in milli satoshis."
    )

    settled: bool = Query(False, description="Whether this invoice has been fulfilled")

    creation_date: int = Query(
        None,
        description="When this invoice was created. Not available with CLN.",
    )

    settle_date: int = Query(
        None,
        description="When this invoice was settled. Not available with pending invoices.",
    )

    expiry_date: int = Query(None, description="The time at which this invoice expires")

    payment_request: str = Query(
        None,
        description="""A bare-bones invoice for a payment within the
    Lightning Network. With the details of the invoice, the sender has all the data necessary to
    send a payment to the recipient.
    """,
    )

    description_hash: str = Query(
        None,
        description="""
    Hash(SHA-256) of a description of the payment. Used if the description of payment(memo) is too
    long to naturally fit within the description field of an encoded payment request.
    """,
    )

    expiry: int = Query(
        None,
        description="Payment request expiry time in seconds. Default is 3600 (1 hour).",
    )

    fallback_addr: str = Query(None, description="Fallback on-chain address.")

    cltv_expiry: int = Query(
        None,
        description="Delta to use for the time-lock of the CLTV extended to the final hop.",
    )

    route_hints: List[RouteHint] = Query(
        None,
        description="""
    Route hints that can each be individually used to assist in reaching the invoice's destination.
    """,
    )

    private: bool = Query(
        None,
        description="Whether this invoice should include routing hints for private channels.",
    )

    add_index: str = Query(
        ...,
        description="""
The index of this invoice. Each newly created invoice will increment this index making it monotonically increasing.
CLN and LND handle ids differently. LND will generate an auto incremented integer id, while CLN will use a user supplied string id.
To unify both, we auto generate an id for CLN and use the add_index for LND.

For `LND` this will be an `integer` in string form. This is auto generated by LND.

For `CLN` this will be a `string`. If the invoice was generated by BlitzAPI, this will be a
[Firebase-like PushID](https://firebase.blog/posts/2015/02/the-2120-ways-to-ensure-unique_68).
If generated by some other method, it'll be the string supplied by the user at the time of creation of the invoice.
""",
    )

    settle_index: int = Query(
        None,
        description="""
        The "settle" index of this invoice. Each newly settled invoice will  increment this index making it monotonically increasing.
    """,
    )

    amt_paid_sat: int = Query(
        None,
        description="""
    The amount that was accepted for this invoice, in satoshis. This
    will ONLY be set if this invoice has been settled. We provide
    this field as if the invoice was created with a zero value,
    then we need to record what amount was ultimately accepted.
    Additionally, it's possible that the sender paid MORE that
    was specified in the original invoice. So we'll record that here as well.
    """,
    )

    amt_paid_msat: int = Query(
        None,
        description="""
    The amount that was accepted for this invoice, in millisatoshis.
    This will ONLY be set if this invoice has been settled. We
    provide this field as if the invoice was created with a zero value,
    then we need to record what amount was ultimately accepted. Additionally,
    it's possible that the sender paid MORE that was specified in the
    original invoice. So we'll record that here as well.
    """,
    )

    state: InvoiceState = Query(..., description="The state the invoice is in.")

    htlcs: List[InvoiceHTLC] = Query(
        None, description="List of HTLCs paying to this invoice[EXPERIMENTAL]."
    )

    features: List[FeaturesEntry] = Query(
        None, description="List of features advertised on the invoice."
    )

    is_keysend: bool = Query(
        None,
        description="[LND only] Indicates if this invoice was a spontaneous payment that arrived via keysend[EXPERIMENTAL].",
    )

    payment_addr: str = Query(
        None,
        description=""" The payment address of this invoice. This value will be used in MPP payments,
    and also for newer invoices that always require the MPP payload for added end-to-end security.""",
    )

    is_amp: bool = Query(
        None, description="Signals whether or not this is an AMP invoice."
    )

    @classmethod
    def from_lnd_grpc(cls, i) -> "Invoice":
        def _route_hints(hints):
            l = []
            for h in hints:
                l.append(RouteHint.from_lnd_grpc((h)))
            return l

        def _htlcs(htlcs):
            l = []
            for h in htlcs:
                l.append(InvoiceHTLC.from_lnd_grpc(h))
            return l

        def _features(features):
            l = []
            for k in features:
                l.append(FeaturesEntry.from_lnd_grpc(k, features[k]))
            return l

        return cls(
            memo=i.memo,
            r_preimage=i.r_preimage.hex(),
            r_hash=i.r_hash.hex(),
            value=i.value,
            value_msat=i.value_msat,
            settled=i.settled,
            creation_date=i.creation_date,
            expiry_date=i.creation_date + i.expiry,
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
            state=InvoiceState.from_lnd_grpc(i.state),
            htlcs=_htlcs(i.htlcs),
            features=_features(i.features),
            is_keysend=i.is_keysend,
            payment_addr=i.payment_addr.hex(),
            is_amp=i.is_amp,
        )

    @classmethod
    def from_cln_json(cls, i) -> "Invoice":
        return cls(
            add_index=i["label"],
            memo=i["description"],
            r_preimage=i["payment_preimage"] if "payment_preimage" in i else None,
            r_hash=i["payment_hash"],
            value=i["msatoshi"] / 1000,
            value_msat=i["msatoshi"],
            settled=True if i["status"] == "paid" else False,
            expiry_date=i["expires_at"],
            settle_date=i["paid_at"] if "paid_at" in i else None,
            payment_request=i["bolt11"],
            settle_index=i["pay_index"] if "pay_index" in i else None,
            amt_paid_sat=i["amount_received_msat"] / 1000
            if "amount_received_msat" in i
            else None,
            amt_paid_msat=i["amount_received_msat"]
            if "amount_received_msat" in i
            else None,
            state=InvoiceState.from_cln_json(i["status"]),
        )

    @classmethod
    def from_cln_grpc(cls, i) -> "Invoice":
        state = InvoiceState.from_cln_grpc(i)
        return cls(
            add_index=i.label,
            memo=i.description,
            r_preimage=i.payment_preimage.hex(),
            r_hash=i.payment_hash.hex(),
            value=i.amount_msat.msat / 1000,
            value_msat=i.amount_msat.msat,
            settled=True if state == InvoiceState.SETTLED else False,
            expiry_date=i.expires_at,
            settle_date=i.paid_at,
            payment_request=i.bolt11,
            settle_index=i.pay_index,
            amt_paid_sat=i.amount_received_msat.msat / 1000,
            amt_paid_msat=i.amount_received_msat.msat,
            state=state,
        )


class PaymentStatus(str, Enum):
    UNKNOWN = "unknown"
    IN_FLIGHT = "in_flight"
    SUCCEEDED = "succeeded"
    FAILED = "failed"

    @classmethod
    def from_lnd_grpc(cls, id) -> "PaymentStatus":
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

    @classmethod
    def from_cln_grpc(cls, id) -> "PaymentStatus":
        if id == 0:
            return PaymentStatus.SUCCEEDED
        elif id == 1:
            return PaymentStatus.IN_FLIGHT
        elif id == 2:
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
    FAILURE_REASON_INCORRECT_PAYMENT_DETAILS = (
        "FAILURE_REASON_INCORRECT_PAYMENT_DETAILS"
    )

    # Insufficient local balance.
    FAILURE_REASON_INSUFFICIENT_BALANCE = "FAILURE_REASON_INSUFFICIENT_BALANCE"

    @classmethod
    def from_lnd_grpc(cls, f) -> "PaymentFailureReason":
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
            raise NotImplementedError(f"PaymentFailureReason {id} is not implemented")

    @classmethod
    def from_cln_grpc(cls, p) -> "PaymentFailureReason":
        if p.status == 0 or p.status == 2:
            return PaymentFailureReason.FAILURE_REASON_NONE

        # TODO: find a way to describe the failure reason. CLN currently doesn't
        # seem to provide an API for this.

        return PaymentFailureReason.FAILURE_REASON_ERROR


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

    @classmethod
    def from_lnd_grpc(cls, u) -> "ChannelUpdate":
        return cls(
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

    @classmethod
    def from_lnd_grpc(cls, h) -> "Hop":
        return cls(
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

    @classmethod
    def from_lnd_grpc(cls, r) -> "MPPRecord":
        return cls(
            payment_addr=r.payment_addr,
            total_amt_msat=r.total_amt_msat,
        )


class AMPRecord(BaseModel):
    root_share: str
    set_id: str
    child_index: int

    @classmethod
    def from_lnd_grpc(cls, r) -> "AMPRecord":
        return cls(
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
    custom_records: List[CustomRecordsEntry]

    @classmethod
    def from_lnd_grpc(cls, r):
        def _crecords(recs):
            l = []
            for r in recs:
                l.append(CustomRecordsEntry(r))
            return l

        def _get_hops(hops) -> List[Hop]:
            l = []
            for h in hops:
                l.append(Hop.from_lnd_grpc(h))
            return l

        mpp = None
        if hasattr(r, "mpp_record"):
            mpp = MPPRecord.from_lnd_grpc(r.mpp_record)

        amp = None
        if hasattr(r, "amp_record"):
            amp = AMPRecord.from_lnd_grpc(r.amp_record)

        crecords = []
        if hasattr(r, "custom_records"):
            crecords = _crecords(r.custom_records)

        return cls(
            total_time_lock=r.total_time_lock,
            total_fees=r.total_fees,
            total_amt=r.total_amt,
            hops=_get_hops(r.hops),
            total_fees_msat=r.total_fees_msat,
            total_amt_msat=r.total_amt_msat,
            mpp_record=mpp,
            amp_record=amp,
            custom_records=crecords,
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

    @classmethod
    def from_lnd_grpc(cls, f) -> "HTLCAttemptFailure":
        code = None
        if hasattr(f, "code"):
            code = f.code

        htlc_msat = None
        if hasattr(f, "htlc_msat"):
            htlc_msat = f.htlc_msat

        return cls(
            code=code,
            channel_update=ChannelUpdate.from_lnd_grpc(f.channel_update),
            htlc_msat=htlc_msat,
            onion_sha_256=f.onion_sha_256,
            cltv_expiry=f.cltv_expiry,
            flags=f.flags,
            failure_source_index=f.failure_source_index,
            height=f.height,
        )


class HTLCStatus(str, Enum):
    IN_FLIGHT = "in_flight"
    SUCCEEDED = "succeeded"
    FAILED = "failed"

    @classmethod
    def from_lnd_grpc(cls, s) -> "HTLCStatus":
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

    @classmethod
    def from_lnd_grpc(cls, a) -> "HTLCAttempt":
        return cls(
            attempt_id=a.attempt_id,
            status=HTLCStatus.from_lnd_grpc(a.status),
            route=Route.from_lnd_grpc(a.route),
            attempt_time_ns=a.attempt_time_ns,
            resolve_time_ns=a.resolve_time_ns,
            failure=HTLCAttemptFailure.from_lnd_grpc(a.failure),
            preimage=a.preimage.hex(),
        )


class Payment(BaseModel):
    payment_hash: str = Query(..., description="The payment hash")

    payment_preimage: Optional[str] = Query(None, description="The payment preimage")

    value_msat: int = Query(
        ..., description="The value of the payment in milli-satoshis"
    )

    payment_request: str = Query(
        None, description="The optional payment request being fulfilled."
    )

    status: PaymentStatus = Query(
        PaymentStatus.UNKNOWN, description="The status of the payment."
    )

    fee_msat: int = Query(..., description="The fee paid for this payment in msat")

    creation_time_ns: int = Query(
        ...,
        description="The time in UNIX nanoseconds at which the payment was created.",
    )

    htlcs: List[HTLCAttempt] = Query(
        [], description="The HTLCs made in attempt to settle the payment."
    )

    payment_index: int = Query(
        0, description="The payment index. Only set with LND, 0 otherwise."
    )

    label: str = Query(
        "", description="The payment label. Only set with CLN, empty otherwise."
    )

    failure_reason: PaymentFailureReason = Query(
        PaymentFailureReason.FAILURE_REASON_NONE, description="The failure reason"
    )

    @classmethod
    def from_lnd_grpc(cls, p) -> "Payment":
        def _get_attempts(attempts):
            l = []
            for a in attempts:
                l.append(HTLCAttempt.from_lnd_grpc(a))
            return l

        return cls(
            payment_hash=p.payment_hash,
            payment_preimage=p.payment_preimage,
            value_msat=p.value_msat,
            payment_request=p.payment_request,
            status=PaymentStatus.from_lnd_grpc(p.status),
            fee_msat=p.fee_msat,
            creation_time_ns=p.creation_time_ns,
            htlcs=_get_attempts(p.htlcs),
            payment_index=p.payment_index,
            failure_reason=PaymentFailureReason.from_lnd_grpc(p.failure_reason),
        )

    @classmethod
    def from_cln_grpc(cls, p) -> "Payment":
        return cls(
            payment_hash=p.payment_hash.hex(),
            payment_preimage="",  # CLN currently doesn't return the preimage
            value_msat=p.amount_sent_msat.msat,
            payment_request="" if not hasattr(p, "bolt11") else p.bolt11,
            status=PaymentStatus.from_cln_grpc(p.status),
            fee_msat=p.amount_sent_msat.msat - p.amount_msat.msat,
            creation_time_ns=p.created_at,
            label="" if not hasattr(p, "label") else p.label,
            failure_reason=PaymentFailureReason.from_cln_grpc(p),
        )


class NewAddressInput(BaseModel):
    type: OnchainAddressType = Query(
        ...,
        description="""
Address-types has to be one of:
* p2wkh:  Pay to witness key hash (bech32)
* np2wkh: Pay to nested witness key hash
    """,
    )


class UnlockWalletInput(BaseModel):
    password: str = Query(..., description="The wallet password")


class SendCoinsInput(BaseModel):
    address: str = Query(
        ...,
        description="The base58 or bech32 encoded bitcoin address to send coins to on-chain",
    )
    target_conf: int = Query(
        None,
        description="The number of blocks that the transaction *should* confirm in, will be used for fee estimation",
    )
    sat_per_vbyte: int = Query(
        None,
        description="A manual fee expressed in sat/vbyte that should be used when crafting the transaction (default: 0)",
    )
    min_confs: int = Query(
        1,
        description="The minimum number of confirmations each one of your outputs used for the transaction must satisfy",
    )
    label: str = Query(
        "", description="A label for the transaction. Ignored by CLN backend."
    )
    send_all: bool = Query(
        False,
        description="Send all available on-chain funds from the wallet. Will be executed `amount` is **0**",
    )
    amount: conint(ge=0) = Query(
        0,
        description="The number of bitcoin denominated in satoshis to send. Must not be set when `send_all` is true.",
    )

    @validator("amount", pre=True, always=True)
    def check_amount_or_send_all(cls, amount, values):
        if amount == None:
            amount = 0

        send_all = values.get("send_all") if "send_all" in values else False

        if amount < 0:
            raise ValueError("Amount must not be negative")

        if amount == 0 and not send_all:
            # neither amount nor send_all is set
            raise ValueError(
                "Either amount or send_all must be set. Please review the documentation."
            )

        if amount > 0 and not send_all:
            # amount is set and send_all is false
            return amount

        if amount > 0 and send_all:
            # amount is set and send_all is true
            raise ValueError(
                "Amount and send_all must not be set at the same time. Please review the documentation."
            )

        if amount == 0 and send_all:
            # amount is not set and send_all is true
            return amount

        # normally this should never be reached
        raise ValueError(f"Unknown input.")


class SendCoinsResponse(BaseModel):
    txid: str = Query(..., description="The transaction ID for this onchain payment")
    address: str = Query(
        ...,
        description="The base58 or bech32 encoded bitcoin address where the onchain funds where sent to",
    )
    amount: conint(gt=0) = Query(
        ...,
        description="The number of bitcoin denominated in satoshis which where sent",
    )
    fees: conint(ge=0) = Query(
        None,
        description="The number of bitcoin denominated in satoshis which where paid as fees",
    )
    label: str = Query(
        "", description="The label used for the transaction. Ignored by CLN backend."
    )

    @classmethod
    def from_lnd_grpc(cls, r, input: SendCoinsInput):
        amount = input.amount if input.send_all == False else r.amount
        return cls(
            txid=r.tx_hash,
            address=input.address,
            amount=abs(amount),
            fees=r.total_fees,
            label=input.label,
        )

    @classmethod
    def from_cln_grpc(cls, r, input: SendCoinsInput):
        return cls(
            txid=r.txid,
            address=input.address,
            amount=input.amount,
            label=input.label,
        )


class Chain(BaseModel):
    # The blockchain the node is on(eg bitcoin, litecoin)
    chain: str

    # The network the node is on(eg regtest, testnet, mainnet)
    network: str


class LnInfo(BaseModel):
    implementation: str = Query(
        ..., description="Lightning software implementation (LND, CLN)"
    )

    version: str = Query(
        ..., description="The version of the software that the node is running."
    )

    commit_hash: str = Query(
        ..., description="The SHA1 commit hash that the daemon is compiled with."
    )

    identity_pubkey: str = Query("The identity pubkey of the current node.")

    identity_uri: str = Query(
        "The complete URI (pubkey@physicaladdress:port) the current node."
    )

    alias: str = Query(..., description="The alias of the node.")

    color: str = Query(
        ..., description="The color of the current node in hex code format."
    )

    num_pending_channels: int = Query(..., description="Number of pending channels.")

    num_active_channels: int = Query(..., description="Number of active channels.")

    num_inactive_channels: int = Query(..., description="Number of inactive channels.")

    num_peers: int = Query(..., description="Number of peers.")

    block_height: int = Query(
        ...,
        description="The node's current view of the height of the best block. Only available with LND.",
    )

    block_hash: str = Query(
        "",
        description="The node's current view of the hash of the best block. Only available with LND.",
    )

    best_header_timestamp: int = Query(
        None,
        description="Timestamp of the block best known to the wallet. Only available with LND.",
    )

    synced_to_chain: bool = Query(
        None,
        description="Whether the wallet's view is synced to the main chain. Only available with LND.",
    )

    synced_to_graph: bool = Query(
        None,
        description="Whether we consider ourselves synced with the public channel graph. Only available with LND.",
    )

    chains: List[Chain] = Query(
        [], description="A list of active chains the node is connected to"
    )

    uris: List[str] = Query([], description="The URIs of the current node.")

    features: List[FeaturesEntry] = Query(
        [],
        description="Features that our node has advertised in our init message node announcements and invoices. Not yet implemented with CLN",
    )

    def __eq__(self, other):
        if isinstance(other, self.__class__):
            diff = DeepDiff(self, other, ignore_order=True)
            return len(diff) == 0
        else:
            return False

    def __ne__(self, other):
        return not self.__eq__(other)

    @classmethod
    def from_lnd_grpc(cls, implementation, i) -> "LnInfo":
        _chains = []
        for c in i.chains:
            _chains.append(Chain(chain=c.chain, network=c.network))

        _features = []
        for f in i.features:
            _features.append(FeaturesEntry.from_lnd_grpc(f, i.features[f]))

        _uris = [u for u in i.uris]

        return LnInfo(
            implementation=implementation,
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

    @classmethod
    def from_cln_json(cls, implementation, i) -> "LnInfo":
        _chains = [Chain(chain="bitcoin", network=i["network"])]

        _features = []
        # TODO: Map CLN's feature advertisements to LND's
        # for k in i["our_features"].keys():
        #     _features.append(FeaturesEntry.from_cln_json(i["our_features"][k], k))

        _uris = []
        for b in i["binding"]:
            _uris.append(f"{b['address']}:{b['port']}")

        return LnInfo(
            implementation=implementation,
            version=i["version"],
            commit_hash=i["version"].split("-")[-1],
            identity_pubkey=i["id"],
            alias=i["alias"],
            color=i["color"],
            num_pending_channels=i["num_pending_channels"],
            num_active_channels=i["num_active_channels"],
            num_inactive_channels=i["num_inactive_channels"],
            num_peers=i["num_peers"],
            block_height=i["blockheight"],
            chains=_chains,
            uris=_uris,
            features=_features,
        )

    @classmethod
    def from_cln_grpc(cls, implementation, i) -> "LnInfo":
        _chains = [Chain(chain="bitcoin", network=i.network)]

        _features = []
        # TODO: Map CLN's feature advertisements to LND's
        # for k in i["our_features"].keys():
        #     _features.append(FeaturesEntry.from_cln_json(i["our_features"][k], k))

        _uris = []
        for b in i.binding:
            _uris.append(f"{b.address}:{b.port}")

        return LnInfo(
            implementation=implementation,
            version=i.version,
            commit_hash=i.version.split("-")[-1],
            identity_pubkey=i.id.hex(),
            alias=i.alias,
            color=i.color.hex(),
            num_pending_channels=i.num_pending_channels,
            num_active_channels=i.num_active_channels,
            num_inactive_channels=i.num_inactive_channels,
            num_peers=i.num_peers,
            block_height=i.blockheight,
            chains=_chains,
            uris=_uris,
            features=_features,
        )


class LightningInfoLite(BaseModel):
    implementation: str = Query(
        ..., description="Lightning software implementation (LND, c-lightning)"
    )
    version: str = Query(..., description="Version of the implementation")
    identity_pubkey: str = Query(
        ..., description="The identity pubkey of the current node"
    )
    num_pending_channels: int = Query(..., description="Number of pending channels")
    num_active_channels: int = Query(..., description="Number of active channels")
    num_inactive_channels: int = Query(..., description="Number of inactive channels")
    num_peers: int = Query(..., description="Number of peers")
    block_height: int = Query(
        ..., description="The node's current view of the height of the best block"
    )
    synced_to_chain: bool = Query(
        None, description="Whether the wallet's view is synced to the main chain"
    )
    synced_to_graph: bool = Query(
        None,
        description="Whether we consider ourselves synced with the public channel graph.",
    )

    @classmethod
    def from_lninfo(cls, info: LnInfo):
        return cls(
            implementation=info.implementation,
            version=info.version,
            identity_pubkey=info.identity_pubkey,
            num_pending_channels=info.num_pending_channels,
            num_active_channels=info.num_active_channels,
            num_inactive_channels=info.num_inactive_channels,
            num_peers=info.num_peers,
            block_height=info.block_height,
            synced_to_chain=info.synced_to_chain,
            synced_to_graph=info.synced_to_graph,
        )


class WalletBalance(BaseModel):
    onchain_confirmed_balance: int = Query(
        ...,
        description="Confirmed onchain balance (more than three confirmations) in sat",
    )
    onchain_total_balance: int = Query(
        ..., description="Total combined onchain balance in sat"
    )
    onchain_unconfirmed_balance: int = Query(
        ...,
        description="Unconfirmed onchain balance (less than three confirmations) in sat",
    )
    channel_local_balance: int = Query(
        ..., description="Sum of channels local balances in msat"
    )
    channel_remote_balance: int = Query(
        ..., description="Sum of channels remote balances in msat."
    )
    channel_unsettled_local_balance: int = Query(
        ..., description="Sum of channels local unsettled balances in msat."
    )
    channel_unsettled_remote_balance: int = Query(
        ..., description="Sum of channels remote unsettled balances in msat."
    )
    channel_pending_open_local_balance: int = Query(
        ..., description="Sum of channels pending local balances in msat."
    )
    channel_pending_open_remote_balance: int = Query(
        ..., description="Sum of channels pending remote balances in msat."
    )

    @classmethod
    def from_lnd_grpc(cls, onchain, channel) -> "WalletBalance":
        return cls(
            onchain_confirmed_balance=onchain.confirmed_balance,
            onchain_total_balance=onchain.total_balance,
            onchain_unconfirmed_balance=onchain.unconfirmed_balance,
            channel_local_balance=channel.local_balance.msat,
            channel_remote_balance=channel.remote_balance.msat,
            channel_unsettled_local_balance=channel.unsettled_local_balance.msat,
            channel_unsettled_remote_balance=channel.unsettled_remote_balance.msat,
            channel_pending_open_local_balance=channel.pending_open_local_balance.msat,
            channel_pending_open_remote_balance=channel.pending_open_remote_balance.msat,
        )


class PaymentRequest(BaseModel):
    destination: str
    payment_hash: str
    num_satoshis: int = Query(
        None, description="Deprecated. User num_msat instead", deprecated=True
    )
    timestamp: int
    expiry: int
    description: str
    description_hash: Optional[str]
    fallback_addr: Optional[str]
    cltv_expiry: int
    route_hints: List[RouteHint] = Query(
        [], description="A list of [HopHint] for the RouteHint"
    )
    payment_addr: str = Query("", description="The payment address in hex format")
    num_msat: Optional[int]
    features: List[FeaturesEntry] = Query([])
    currency: Optional[str] = Query(
        "", description="Optional requested currency of the payment. "
    )

    @classmethod
    def from_lnd_grpc(cls, r):
        return cls(
            destination=r.destination,
            payment_hash=r.payment_hash,
            num_satoshis=r.num_satoshis,
            timestamp=r.timestamp,
            expiry=r.expiry,
            description=r.description,
            description_hash=r.description_hash,
            fallback_addr=r.fallback_addr,
            cltv_expiry=r.cltv_expiry,
            route_hints=[RouteHint.from_lnd_grpc(rh) for rh in r.route_hints],
            payment_addr=r.payment_addr.hex(),
            num_msat=r.num_msat,
            features=[
                FeaturesEntry.from_lnd_grpc(k, r.features[k]) for k in r.features
            ],
        )

    @classmethod
    def from_cln_json(cls, r):
        routes = []
        if "routes" in r.keys():
            routes = [RouteHint.from_cln_json(rh) for rh in r["routes"]]

        msat = 0
        if "msatoshi" in r:
            msat = r["msatoshi"]

        features = []
        # TODO: Map CLN's feature advertisements to LND's
        # if "features" in r:
        #     features = [
        #         FeaturesEntry.from_cln_json(k, r["features"][k]) for k in r["features"]
        #     ]

        return cls(
            currency="" if "currency" not in r else r["currency"],
            destination=r["payee"],
            payment_hash=r["payment_hash"],
            num_satoshis=msat / 1000,
            timestamp=r["created_at"],
            expiry=0 if "expiry" not in r else r["expiry"],
            description="" if "description" not in r else r["description"],
            description_hash=""
            if "description_hash" not in r
            else r["description_hash"],
            fallback_addr="" if "fallbacks" not in r else r["fallbacks"][0],
            cltv_expiry=r["min_final_cltv_expiry"],
            route_hints=routes,
            num_msat=msat,
            payment_addr=r["payment_secret"],
            features=features,
        )

    @classmethod
    def from_cln_grpc(cls, r):
        routes = []
        if "routes" in r.keys():
            routes = [RouteHint.from_cln_json(rh) for rh in r["routes"]]

        msat = 0
        if "amount_msat" in r:
            msat = r["amount_msat"]

        features = []
        # TODO: Map CLN's feature advertisements to LND's
        # if "features" in r:
        #     features = [
        #         FeaturesEntry.from_cln_json(k, r["features"][k]) for k in r["features"]
        #     ]

        dhash = ""
        if hasattr(r, "payment_hash"):
            dhash = r.payment_hash.hex()

        fback = []
        if hasattr(r, "fallbacks"):
            fback = r["fallbacks"][0]

        return cls(
            destination=r.payee,
            payment_hash=r.payment_hash.hex(),
            num_satoshis=msat / 1000,
            timestamp=r.created_at,
            expiry=r.expiry,
            description=r.description,
            description_hash=dhash,
            fallback_addr=fback,
            cltv_expiry=r.min_final_cltv_expiry,
            route_hints=routes,
            num_msat=msat,
            payment_addr=r.payment_secret,
            features=features,
        )


class OnChainTransaction(BaseModel):
    tx_hash: str = Query(..., description="The transaction hash")
    amount: int = Query(
        ..., description="The transaction amount, denominated in satoshis"
    )
    num_confirmations: int = Query(..., description="The number of confirmations")
    block_height: int = Query(
        ..., description="The height of the block this transaction was included in"
    )
    time_stamp: int = Query(..., description="Timestamp of this transaction")
    total_fees: int = Query(..., description="Fees paid for this transaction")
    dest_addresses: List[str] = Query(
        [], description="Addresses that received funds for this transaction"
    )
    label: str = Query(
        "", description="An optional label that was set on transaction broadcast."
    )

    @classmethod
    def from_lnd_grpc(cls, t):
        addrs = [a for a in t.dest_addresses]
        return cls(
            tx_hash=t.tx_hash,
            amount=t.amount,
            num_confirmations=t.num_confirmations,
            block_height=t.block_height,
            time_stamp=t.time_stamp,
            total_fees=t.total_fees,
            dest_addresses=addrs,
            label=t.label,
        )

    @classmethod
    def from_cln_bkpr(cls, t):
        amount = None
        if t["tag"] == "deposit":
            amount = parse_cln_msat(t["credit_msat"]) / 1000
        elif t["tag"] == "withdrawal":
            amount = -parse_cln_msat(t["debit_msat"]) / 1000

        return cls(
            tx_hash=t["outpoint"].split(":")[0],
            amount=amount,
            num_confirmations=0,  # block_height - t["blockheight"],
            block_height=0,  # Block height must be set later in CLN ...
            time_stamp=t["timestamp"],
            total_fees=0,  # Fees are an extra event in CLN, must be set later
            dest_addresses=[],
        )


class TxCategory(str, Enum):
    ONCHAIN = "onchain"
    LIGHTNING = "ln"


class TxType(str, Enum):
    UNKNOWN = "unknown"
    SEND = "send"
    RECEIVE = "receive"


class TxStatus(str, Enum):
    UNKNOWN = "unknown"
    IN_FLIGHT = "in_flight"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class GenericTx(BaseModel):
    index: int = Query(0, description="The index of the transaction.")
    id: str = Query(..., description=docs.tx_id_desc)
    category: TxCategory = Query(
        ...,
        description="Whether this is an onchain (**onchain**) or lightning (**ln**) transaction.",
    )
    type: TxType = Query(
        ...,
        description="Whether this is an outgoing (**send**) transaction or an incoming (**receive**) transaction.",
    )
    amount: int = Query(..., description=docs.tx_amount_desc)
    time_stamp: int = Query(..., description=docs.tx_time_stamp_desc)
    comment: str = Query("", description="Optional comment for this transaction")
    status: TxStatus = Query(..., description=docs.tx_status_desc)
    block_height: int = Query(
        None,
        description="Block height, if included in a block. Only applicable for category **onchain**.",
    )
    num_confs: Union[int, None] = Query(
        ge=0,
        description="Number of confirmations. Only applicable for category **onchain**.",
    )
    total_fees: int = Query(None, description="Total fees paid for this transaction")

    @classmethod
    def from_lnd_grpc_invoice(cls, i) -> "GenericTx":
        status = TxStatus.UNKNOWN
        time_stamp = i.creation_date
        amount = i.value_msat
        if i.settled:
            status = TxStatus.SUCCEEDED
            time_stamp = i.settle_date
            amount = i.amt_paid_msat
        elif i.state == 0 or i.state == 3:  # state is OPEN or ACCEPTED
            status = TxStatus.IN_FLIGHT
        elif i.state == 2:  # state is CANCELED
            status = TxStatus.FAILED

        return cls(
            id=i.payment_request,
            category=TxCategory.LIGHTNING,
            type=TxType.RECEIVE,
            amount=amount,
            time_stamp=time_stamp,
            comment=i.memo,
            status=status,
        )

    @classmethod
    def from_lnd_grpc_onchain_tx(cls, tx) -> "GenericTx":
        if tx.num_confirmations < 0:
            logging.warning(
                f"Got negative confirmation count of from LND {tx.num_confirmations}"
            )

        s = TxStatus.SUCCEEDED if tx.num_confirmations > 0 else TxStatus.IN_FLIGHT

        t = TxType.UNKNOWN
        if tx.amount > 0:
            t = TxType.RECEIVE
        elif tx.amount < 0:
            t = TxType.SEND
        # else == 0 => unknown

        return cls(
            id=tx.tx_hash,
            category=TxCategory.ONCHAIN,
            type=t,
            amount=tx.amount,
            time_stamp=tx.time_stamp,
            status=s,
            comment=tx.label,
            block_height=tx.block_height,
            num_confs=tx.num_confirmations,
        )

    @classmethod
    def from_lnd_grpc_payment(cls, payment, comment: str = "") -> "GenericTx":
        status = TxStatus.UNKNOWN
        if payment.status == 1:
            status = TxStatus.IN_FLIGHT
        elif payment.status == 2:
            status = TxStatus.SUCCEEDED
        elif payment.status == 3:
            status = TxStatus.FAILED

        return cls(
            id=payment.payment_request,
            category=TxCategory.LIGHTNING,
            type=TxType.SEND,
            time_stamp=payment.creation_date,
            amount=-payment.value_msat,
            status=status,
            total_fees=payment.fee_msat,
            comment=comment,
        )

    @classmethod
    def from_cln_json_invoice(cls, i) -> "GenericTx":
        status = TxStatus.UNKNOWN
        time_stamp = i["expires_at"]
        amount = i["msatoshi"]
        if i["status"] == "paid":
            status = TxStatus.SUCCEEDED
            time_stamp = i["paid_at"]
            amount = i["amount_received_msat"]
        elif i["status"] == "unpaid":
            status = TxStatus.IN_FLIGHT
        elif i["status"] == "expired":
            status = TxStatus.FAILED

        return cls(
            id=i["bolt11"],
            category=TxCategory.LIGHTNING,
            type=TxType.RECEIVE,
            amount=amount,
            time_stamp=time_stamp,
            comment=i["description"],
            status=status,
        )

    @classmethod
    def from_cln_json_onchain_tx(cls, tx, current_block_height: int) -> "GenericTx":
        confs = current_block_height - tx["blockheight"]
        if confs < 0:
            confs = 0
            logging.warning(
                f"Got negative confirmation count of for {tx.tx_hash}\nCalc:{current_block_height} - {tx['blockheight']} = {confs}"
            )

        s = TxStatus.SUCCEEDED if confs > 0 else TxStatus.IN_FLIGHT

        print(tx["hash"])

        for ins in tx["inputs"]:
            print(f"i:  {ins['index']}")

        amount = 0
        for out in tx["outputs"]:
            amount += out["msat"].millisatoshis

        t = TxType.UNKNOWN
        if amount > 0:
            t = TxType.RECEIVE
        elif amount < 0:
            t = TxType.SEND

        return cls(
            id=tx["hash"],
            category=TxCategory.ONCHAIN,
            type=t,
            amount=amount,
            time_stamp=0,
            status=s,
            comment="",
            block_height=tx["blockheight"],
            num_confs=confs,
        )

    @classmethod
    def from_cln_json_payment(cls, payment, comment: str = "") -> "GenericTx":
        status = TxStatus.UNKNOWN  #  “pending”, “failed”, “complete”
        if payment["status"] == "pending":
            status = TxStatus.IN_FLIGHT
        elif payment["status"] == "complete":
            status = TxStatus.SUCCEEDED
        elif payment["status"] == "failed":
            status = TxStatus.FAILED

        return cls(
            id=payment["bolt11"],
            category=TxCategory.LIGHTNING,
            type=TxType.SEND,
            time_stamp=payment["created_at"],
            amount=-payment["amount_msat"].millisatoshis,
            status=status,
            total_fees=payment["amount_sent_msat"].millisatoshis
            - payment["amount_msat"].millisatoshis,
            comment=comment,
        )

    @classmethod
    def from_cln_grpc_invoice(cls, i) -> "GenericTx":
        status = TxStatus.UNKNOWN
        time_stamp = i.expires_at
        amount = i.amount_msat.msat
        if i.status == 0:  # unpaid
            status = TxStatus.IN_FLIGHT
        elif i.status == 1:  # paid
            status = TxStatus.SUCCEEDED
            time_stamp = i.paid_at
            amount = i.amount_received_msat.msat
        elif i.status == 2:  # expired
            status = TxStatus.FAILED

        return cls(
            id=i.bolt11,
            category=TxCategory.LIGHTNING,
            type=TxType.RECEIVE,
            amount=amount,
            time_stamp=time_stamp,
            comment=i.description,
            status=status,
        )

    @classmethod
    def from_cln_grpc_onchain_tx(
        cls, tx: OnChainTransaction, current_block_height: int
    ) -> "GenericTx":
        confs = current_block_height - tx.block_height
        if confs < 0:
            confs = 0
            logging.warning(
                f"Got negative confirmation count of for {tx.tx_hash}\nCalc:{current_block_height} - {tx.block_height} = {confs}"
            )

        s = TxStatus.SUCCEEDED if confs > 0 else TxStatus.IN_FLIGHT

        t = TxType.SEND
        if tx.total_fees == 0:
            t = TxType.RECEIVE

        return cls(
            id=tx.tx_hash,
            category=TxCategory.ONCHAIN,
            type=t,
            amount=tx.amount,
            time_stamp=0,
            status=s,
            comment="",
            block_height=tx.block_height,
            num_confs=confs,
        )

    @classmethod
    def from_cln_grpc_payment(cls, payment, comment: str = "") -> "GenericTx":
        status = TxStatus.UNKNOWN
        if payment.status == 0:  # pending
            status = TxStatus.IN_FLIGHT
        elif payment.status == 1:  # failed
            status = TxStatus.FAILED
        elif payment.status == 2:  # complete
            status = TxStatus.SUCCEEDED

        return cls(
            id=payment.bolt11,
            category=TxCategory.LIGHTNING,
            type=TxType.SEND,
            time_stamp=payment.created_at,
            amount=-payment.amount_msat.msat,
            status=status,
            total_fees=payment.amount_sent_msat.msat - payment.amount_msat.msat,
            comment=comment,
        )

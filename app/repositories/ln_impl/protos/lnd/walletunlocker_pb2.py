# -*- coding: utf-8 -*-
# Generated by the protocol buffer compiler.  DO NOT EDIT!
# source: walletunlocker.proto
"""Generated protocol buffer code."""
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from google.protobuf import reflection as _reflection
from google.protobuf import symbol_database as _symbol_database

# @@protoc_insertion_point(imports)

_sym_db = _symbol_database.Default()


import app.repositories.ln_impl.protos.lnd.lightning_pb2 as lightning__pb2

DESCRIPTOR = _descriptor.FileDescriptor(
    name="walletunlocker.proto",
    package="lnrpc",
    syntax="proto3",
    serialized_options=b"Z%github.com/lightningnetwork/lnd/lnrpc",
    create_key=_descriptor._internal_create_key,
    serialized_pb=b'\n\x14walletunlocker.proto\x12\x05lnrpc\x1a\x0flightning.proto"A\n\x0eGenSeedRequest\x12\x19\n\x11\x61\x65zeed_passphrase\x18\x01 \x01(\x0c\x12\x14\n\x0cseed_entropy\x18\x02 \x01(\x0c"H\n\x0fGenSeedResponse\x12\x1c\n\x14\x63ipher_seed_mnemonic\x18\x01 \x03(\t\x12\x17\n\x0f\x65nciphered_seed\x18\x02 \x01(\x0c"\xbd\x02\n\x11InitWalletRequest\x12\x17\n\x0fwallet_password\x18\x01 \x01(\x0c\x12\x1c\n\x14\x63ipher_seed_mnemonic\x18\x02 \x03(\t\x12\x19\n\x11\x61\x65zeed_passphrase\x18\x03 \x01(\x0c\x12\x17\n\x0frecovery_window\x18\x04 \x01(\x05\x12\x32\n\x0f\x63hannel_backups\x18\x05 \x01(\x0b\x32\x19.lnrpc.ChanBackupSnapshot\x12\x16\n\x0estateless_init\x18\x06 \x01(\x08\x12\x1b\n\x13\x65xtended_master_key\x18\x07 \x01(\t\x12.\n&extended_master_key_birthday_timestamp\x18\x08 \x01(\x04\x12$\n\nwatch_only\x18\t \x01(\x0b\x32\x10.lnrpc.WatchOnly",\n\x12InitWalletResponse\x12\x16\n\x0e\x61\x64min_macaroon\x18\x01 \x01(\x0c"}\n\tWatchOnly\x12%\n\x1dmaster_key_birthday_timestamp\x18\x01 \x01(\x04\x12\x1e\n\x16master_key_fingerprint\x18\x02 \x01(\x0c\x12)\n\x08\x61\x63\x63ounts\x18\x03 \x03(\x0b\x32\x17.lnrpc.WatchOnlyAccount"U\n\x10WatchOnlyAccount\x12\x0f\n\x07purpose\x18\x01 \x01(\r\x12\x11\n\tcoin_type\x18\x02 \x01(\r\x12\x0f\n\x07\x61\x63\x63ount\x18\x03 \x01(\r\x12\x0c\n\x04xpub\x18\x04 \x01(\t"\x93\x01\n\x13UnlockWalletRequest\x12\x17\n\x0fwallet_password\x18\x01 \x01(\x0c\x12\x17\n\x0frecovery_window\x18\x02 \x01(\x05\x12\x32\n\x0f\x63hannel_backups\x18\x03 \x01(\x0b\x32\x19.lnrpc.ChanBackupSnapshot\x12\x16\n\x0estateless_init\x18\x04 \x01(\x08"\x16\n\x14UnlockWalletResponse"~\n\x15\x43hangePasswordRequest\x12\x18\n\x10\x63urrent_password\x18\x01 \x01(\x0c\x12\x14\n\x0cnew_password\x18\x02 \x01(\x0c\x12\x16\n\x0estateless_init\x18\x03 \x01(\x08\x12\x1d\n\x15new_macaroon_root_key\x18\x04 \x01(\x08"0\n\x16\x43hangePasswordResponse\x12\x16\n\x0e\x61\x64min_macaroon\x18\x01 \x01(\x0c\x32\xa5\x02\n\x0eWalletUnlocker\x12\x38\n\x07GenSeed\x12\x15.lnrpc.GenSeedRequest\x1a\x16.lnrpc.GenSeedResponse\x12\x41\n\nInitWallet\x12\x18.lnrpc.InitWalletRequest\x1a\x19.lnrpc.InitWalletResponse\x12G\n\x0cUnlockWallet\x12\x1a.lnrpc.UnlockWalletRequest\x1a\x1b.lnrpc.UnlockWalletResponse\x12M\n\x0e\x43hangePassword\x12\x1c.lnrpc.ChangePasswordRequest\x1a\x1d.lnrpc.ChangePasswordResponseB\'Z%github.com/lightningnetwork/lnd/lnrpcb\x06proto3',
    dependencies=[
        lightning__pb2.DESCRIPTOR,
    ],
)


_GENSEEDREQUEST = _descriptor.Descriptor(
    name="GenSeedRequest",
    full_name="lnrpc.GenSeedRequest",
    filename=None,
    file=DESCRIPTOR,
    containing_type=None,
    create_key=_descriptor._internal_create_key,
    fields=[
        _descriptor.FieldDescriptor(
            name="aezeed_passphrase",
            full_name="lnrpc.GenSeedRequest.aezeed_passphrase",
            index=0,
            number=1,
            type=12,
            cpp_type=9,
            label=1,
            has_default_value=False,
            default_value=b"",
            message_type=None,
            enum_type=None,
            containing_type=None,
            is_extension=False,
            extension_scope=None,
            serialized_options=None,
            file=DESCRIPTOR,
            create_key=_descriptor._internal_create_key,
        ),
        _descriptor.FieldDescriptor(
            name="seed_entropy",
            full_name="lnrpc.GenSeedRequest.seed_entropy",
            index=1,
            number=2,
            type=12,
            cpp_type=9,
            label=1,
            has_default_value=False,
            default_value=b"",
            message_type=None,
            enum_type=None,
            containing_type=None,
            is_extension=False,
            extension_scope=None,
            serialized_options=None,
            file=DESCRIPTOR,
            create_key=_descriptor._internal_create_key,
        ),
    ],
    extensions=[],
    nested_types=[],
    enum_types=[],
    serialized_options=None,
    is_extendable=False,
    syntax="proto3",
    extension_ranges=[],
    oneofs=[],
    serialized_start=48,
    serialized_end=113,
)


_GENSEEDRESPONSE = _descriptor.Descriptor(
    name="GenSeedResponse",
    full_name="lnrpc.GenSeedResponse",
    filename=None,
    file=DESCRIPTOR,
    containing_type=None,
    create_key=_descriptor._internal_create_key,
    fields=[
        _descriptor.FieldDescriptor(
            name="cipher_seed_mnemonic",
            full_name="lnrpc.GenSeedResponse.cipher_seed_mnemonic",
            index=0,
            number=1,
            type=9,
            cpp_type=9,
            label=3,
            has_default_value=False,
            default_value=[],
            message_type=None,
            enum_type=None,
            containing_type=None,
            is_extension=False,
            extension_scope=None,
            serialized_options=None,
            file=DESCRIPTOR,
            create_key=_descriptor._internal_create_key,
        ),
        _descriptor.FieldDescriptor(
            name="enciphered_seed",
            full_name="lnrpc.GenSeedResponse.enciphered_seed",
            index=1,
            number=2,
            type=12,
            cpp_type=9,
            label=1,
            has_default_value=False,
            default_value=b"",
            message_type=None,
            enum_type=None,
            containing_type=None,
            is_extension=False,
            extension_scope=None,
            serialized_options=None,
            file=DESCRIPTOR,
            create_key=_descriptor._internal_create_key,
        ),
    ],
    extensions=[],
    nested_types=[],
    enum_types=[],
    serialized_options=None,
    is_extendable=False,
    syntax="proto3",
    extension_ranges=[],
    oneofs=[],
    serialized_start=115,
    serialized_end=187,
)


_INITWALLETREQUEST = _descriptor.Descriptor(
    name="InitWalletRequest",
    full_name="lnrpc.InitWalletRequest",
    filename=None,
    file=DESCRIPTOR,
    containing_type=None,
    create_key=_descriptor._internal_create_key,
    fields=[
        _descriptor.FieldDescriptor(
            name="wallet_password",
            full_name="lnrpc.InitWalletRequest.wallet_password",
            index=0,
            number=1,
            type=12,
            cpp_type=9,
            label=1,
            has_default_value=False,
            default_value=b"",
            message_type=None,
            enum_type=None,
            containing_type=None,
            is_extension=False,
            extension_scope=None,
            serialized_options=None,
            file=DESCRIPTOR,
            create_key=_descriptor._internal_create_key,
        ),
        _descriptor.FieldDescriptor(
            name="cipher_seed_mnemonic",
            full_name="lnrpc.InitWalletRequest.cipher_seed_mnemonic",
            index=1,
            number=2,
            type=9,
            cpp_type=9,
            label=3,
            has_default_value=False,
            default_value=[],
            message_type=None,
            enum_type=None,
            containing_type=None,
            is_extension=False,
            extension_scope=None,
            serialized_options=None,
            file=DESCRIPTOR,
            create_key=_descriptor._internal_create_key,
        ),
        _descriptor.FieldDescriptor(
            name="aezeed_passphrase",
            full_name="lnrpc.InitWalletRequest.aezeed_passphrase",
            index=2,
            number=3,
            type=12,
            cpp_type=9,
            label=1,
            has_default_value=False,
            default_value=b"",
            message_type=None,
            enum_type=None,
            containing_type=None,
            is_extension=False,
            extension_scope=None,
            serialized_options=None,
            file=DESCRIPTOR,
            create_key=_descriptor._internal_create_key,
        ),
        _descriptor.FieldDescriptor(
            name="recovery_window",
            full_name="lnrpc.InitWalletRequest.recovery_window",
            index=3,
            number=4,
            type=5,
            cpp_type=1,
            label=1,
            has_default_value=False,
            default_value=0,
            message_type=None,
            enum_type=None,
            containing_type=None,
            is_extension=False,
            extension_scope=None,
            serialized_options=None,
            file=DESCRIPTOR,
            create_key=_descriptor._internal_create_key,
        ),
        _descriptor.FieldDescriptor(
            name="channel_backups",
            full_name="lnrpc.InitWalletRequest.channel_backups",
            index=4,
            number=5,
            type=11,
            cpp_type=10,
            label=1,
            has_default_value=False,
            default_value=None,
            message_type=None,
            enum_type=None,
            containing_type=None,
            is_extension=False,
            extension_scope=None,
            serialized_options=None,
            file=DESCRIPTOR,
            create_key=_descriptor._internal_create_key,
        ),
        _descriptor.FieldDescriptor(
            name="stateless_init",
            full_name="lnrpc.InitWalletRequest.stateless_init",
            index=5,
            number=6,
            type=8,
            cpp_type=7,
            label=1,
            has_default_value=False,
            default_value=False,
            message_type=None,
            enum_type=None,
            containing_type=None,
            is_extension=False,
            extension_scope=None,
            serialized_options=None,
            file=DESCRIPTOR,
            create_key=_descriptor._internal_create_key,
        ),
        _descriptor.FieldDescriptor(
            name="extended_master_key",
            full_name="lnrpc.InitWalletRequest.extended_master_key",
            index=6,
            number=7,
            type=9,
            cpp_type=9,
            label=1,
            has_default_value=False,
            default_value=b"".decode("utf-8"),
            message_type=None,
            enum_type=None,
            containing_type=None,
            is_extension=False,
            extension_scope=None,
            serialized_options=None,
            file=DESCRIPTOR,
            create_key=_descriptor._internal_create_key,
        ),
        _descriptor.FieldDescriptor(
            name="extended_master_key_birthday_timestamp",
            full_name="lnrpc.InitWalletRequest.extended_master_key_birthday_timestamp",
            index=7,
            number=8,
            type=4,
            cpp_type=4,
            label=1,
            has_default_value=False,
            default_value=0,
            message_type=None,
            enum_type=None,
            containing_type=None,
            is_extension=False,
            extension_scope=None,
            serialized_options=None,
            file=DESCRIPTOR,
            create_key=_descriptor._internal_create_key,
        ),
        _descriptor.FieldDescriptor(
            name="watch_only",
            full_name="lnrpc.InitWalletRequest.watch_only",
            index=8,
            number=9,
            type=11,
            cpp_type=10,
            label=1,
            has_default_value=False,
            default_value=None,
            message_type=None,
            enum_type=None,
            containing_type=None,
            is_extension=False,
            extension_scope=None,
            serialized_options=None,
            file=DESCRIPTOR,
            create_key=_descriptor._internal_create_key,
        ),
    ],
    extensions=[],
    nested_types=[],
    enum_types=[],
    serialized_options=None,
    is_extendable=False,
    syntax="proto3",
    extension_ranges=[],
    oneofs=[],
    serialized_start=190,
    serialized_end=507,
)


_INITWALLETRESPONSE = _descriptor.Descriptor(
    name="InitWalletResponse",
    full_name="lnrpc.InitWalletResponse",
    filename=None,
    file=DESCRIPTOR,
    containing_type=None,
    create_key=_descriptor._internal_create_key,
    fields=[
        _descriptor.FieldDescriptor(
            name="admin_macaroon",
            full_name="lnrpc.InitWalletResponse.admin_macaroon",
            index=0,
            number=1,
            type=12,
            cpp_type=9,
            label=1,
            has_default_value=False,
            default_value=b"",
            message_type=None,
            enum_type=None,
            containing_type=None,
            is_extension=False,
            extension_scope=None,
            serialized_options=None,
            file=DESCRIPTOR,
            create_key=_descriptor._internal_create_key,
        ),
    ],
    extensions=[],
    nested_types=[],
    enum_types=[],
    serialized_options=None,
    is_extendable=False,
    syntax="proto3",
    extension_ranges=[],
    oneofs=[],
    serialized_start=509,
    serialized_end=553,
)


_WATCHONLY = _descriptor.Descriptor(
    name="WatchOnly",
    full_name="lnrpc.WatchOnly",
    filename=None,
    file=DESCRIPTOR,
    containing_type=None,
    create_key=_descriptor._internal_create_key,
    fields=[
        _descriptor.FieldDescriptor(
            name="master_key_birthday_timestamp",
            full_name="lnrpc.WatchOnly.master_key_birthday_timestamp",
            index=0,
            number=1,
            type=4,
            cpp_type=4,
            label=1,
            has_default_value=False,
            default_value=0,
            message_type=None,
            enum_type=None,
            containing_type=None,
            is_extension=False,
            extension_scope=None,
            serialized_options=None,
            file=DESCRIPTOR,
            create_key=_descriptor._internal_create_key,
        ),
        _descriptor.FieldDescriptor(
            name="master_key_fingerprint",
            full_name="lnrpc.WatchOnly.master_key_fingerprint",
            index=1,
            number=2,
            type=12,
            cpp_type=9,
            label=1,
            has_default_value=False,
            default_value=b"",
            message_type=None,
            enum_type=None,
            containing_type=None,
            is_extension=False,
            extension_scope=None,
            serialized_options=None,
            file=DESCRIPTOR,
            create_key=_descriptor._internal_create_key,
        ),
        _descriptor.FieldDescriptor(
            name="accounts",
            full_name="lnrpc.WatchOnly.accounts",
            index=2,
            number=3,
            type=11,
            cpp_type=10,
            label=3,
            has_default_value=False,
            default_value=[],
            message_type=None,
            enum_type=None,
            containing_type=None,
            is_extension=False,
            extension_scope=None,
            serialized_options=None,
            file=DESCRIPTOR,
            create_key=_descriptor._internal_create_key,
        ),
    ],
    extensions=[],
    nested_types=[],
    enum_types=[],
    serialized_options=None,
    is_extendable=False,
    syntax="proto3",
    extension_ranges=[],
    oneofs=[],
    serialized_start=555,
    serialized_end=680,
)


_WATCHONLYACCOUNT = _descriptor.Descriptor(
    name="WatchOnlyAccount",
    full_name="lnrpc.WatchOnlyAccount",
    filename=None,
    file=DESCRIPTOR,
    containing_type=None,
    create_key=_descriptor._internal_create_key,
    fields=[
        _descriptor.FieldDescriptor(
            name="purpose",
            full_name="lnrpc.WatchOnlyAccount.purpose",
            index=0,
            number=1,
            type=13,
            cpp_type=3,
            label=1,
            has_default_value=False,
            default_value=0,
            message_type=None,
            enum_type=None,
            containing_type=None,
            is_extension=False,
            extension_scope=None,
            serialized_options=None,
            file=DESCRIPTOR,
            create_key=_descriptor._internal_create_key,
        ),
        _descriptor.FieldDescriptor(
            name="coin_type",
            full_name="lnrpc.WatchOnlyAccount.coin_type",
            index=1,
            number=2,
            type=13,
            cpp_type=3,
            label=1,
            has_default_value=False,
            default_value=0,
            message_type=None,
            enum_type=None,
            containing_type=None,
            is_extension=False,
            extension_scope=None,
            serialized_options=None,
            file=DESCRIPTOR,
            create_key=_descriptor._internal_create_key,
        ),
        _descriptor.FieldDescriptor(
            name="account",
            full_name="lnrpc.WatchOnlyAccount.account",
            index=2,
            number=3,
            type=13,
            cpp_type=3,
            label=1,
            has_default_value=False,
            default_value=0,
            message_type=None,
            enum_type=None,
            containing_type=None,
            is_extension=False,
            extension_scope=None,
            serialized_options=None,
            file=DESCRIPTOR,
            create_key=_descriptor._internal_create_key,
        ),
        _descriptor.FieldDescriptor(
            name="xpub",
            full_name="lnrpc.WatchOnlyAccount.xpub",
            index=3,
            number=4,
            type=9,
            cpp_type=9,
            label=1,
            has_default_value=False,
            default_value=b"".decode("utf-8"),
            message_type=None,
            enum_type=None,
            containing_type=None,
            is_extension=False,
            extension_scope=None,
            serialized_options=None,
            file=DESCRIPTOR,
            create_key=_descriptor._internal_create_key,
        ),
    ],
    extensions=[],
    nested_types=[],
    enum_types=[],
    serialized_options=None,
    is_extendable=False,
    syntax="proto3",
    extension_ranges=[],
    oneofs=[],
    serialized_start=682,
    serialized_end=767,
)


_UNLOCKWALLETREQUEST = _descriptor.Descriptor(
    name="UnlockWalletRequest",
    full_name="lnrpc.UnlockWalletRequest",
    filename=None,
    file=DESCRIPTOR,
    containing_type=None,
    create_key=_descriptor._internal_create_key,
    fields=[
        _descriptor.FieldDescriptor(
            name="wallet_password",
            full_name="lnrpc.UnlockWalletRequest.wallet_password",
            index=0,
            number=1,
            type=12,
            cpp_type=9,
            label=1,
            has_default_value=False,
            default_value=b"",
            message_type=None,
            enum_type=None,
            containing_type=None,
            is_extension=False,
            extension_scope=None,
            serialized_options=None,
            file=DESCRIPTOR,
            create_key=_descriptor._internal_create_key,
        ),
        _descriptor.FieldDescriptor(
            name="recovery_window",
            full_name="lnrpc.UnlockWalletRequest.recovery_window",
            index=1,
            number=2,
            type=5,
            cpp_type=1,
            label=1,
            has_default_value=False,
            default_value=0,
            message_type=None,
            enum_type=None,
            containing_type=None,
            is_extension=False,
            extension_scope=None,
            serialized_options=None,
            file=DESCRIPTOR,
            create_key=_descriptor._internal_create_key,
        ),
        _descriptor.FieldDescriptor(
            name="channel_backups",
            full_name="lnrpc.UnlockWalletRequest.channel_backups",
            index=2,
            number=3,
            type=11,
            cpp_type=10,
            label=1,
            has_default_value=False,
            default_value=None,
            message_type=None,
            enum_type=None,
            containing_type=None,
            is_extension=False,
            extension_scope=None,
            serialized_options=None,
            file=DESCRIPTOR,
            create_key=_descriptor._internal_create_key,
        ),
        _descriptor.FieldDescriptor(
            name="stateless_init",
            full_name="lnrpc.UnlockWalletRequest.stateless_init",
            index=3,
            number=4,
            type=8,
            cpp_type=7,
            label=1,
            has_default_value=False,
            default_value=False,
            message_type=None,
            enum_type=None,
            containing_type=None,
            is_extension=False,
            extension_scope=None,
            serialized_options=None,
            file=DESCRIPTOR,
            create_key=_descriptor._internal_create_key,
        ),
    ],
    extensions=[],
    nested_types=[],
    enum_types=[],
    serialized_options=None,
    is_extendable=False,
    syntax="proto3",
    extension_ranges=[],
    oneofs=[],
    serialized_start=770,
    serialized_end=917,
)


_UNLOCKWALLETRESPONSE = _descriptor.Descriptor(
    name="UnlockWalletResponse",
    full_name="lnrpc.UnlockWalletResponse",
    filename=None,
    file=DESCRIPTOR,
    containing_type=None,
    create_key=_descriptor._internal_create_key,
    fields=[],
    extensions=[],
    nested_types=[],
    enum_types=[],
    serialized_options=None,
    is_extendable=False,
    syntax="proto3",
    extension_ranges=[],
    oneofs=[],
    serialized_start=919,
    serialized_end=941,
)


_CHANGEPASSWORDREQUEST = _descriptor.Descriptor(
    name="ChangePasswordRequest",
    full_name="lnrpc.ChangePasswordRequest",
    filename=None,
    file=DESCRIPTOR,
    containing_type=None,
    create_key=_descriptor._internal_create_key,
    fields=[
        _descriptor.FieldDescriptor(
            name="current_password",
            full_name="lnrpc.ChangePasswordRequest.current_password",
            index=0,
            number=1,
            type=12,
            cpp_type=9,
            label=1,
            has_default_value=False,
            default_value=b"",
            message_type=None,
            enum_type=None,
            containing_type=None,
            is_extension=False,
            extension_scope=None,
            serialized_options=None,
            file=DESCRIPTOR,
            create_key=_descriptor._internal_create_key,
        ),
        _descriptor.FieldDescriptor(
            name="new_password",
            full_name="lnrpc.ChangePasswordRequest.new_password",
            index=1,
            number=2,
            type=12,
            cpp_type=9,
            label=1,
            has_default_value=False,
            default_value=b"",
            message_type=None,
            enum_type=None,
            containing_type=None,
            is_extension=False,
            extension_scope=None,
            serialized_options=None,
            file=DESCRIPTOR,
            create_key=_descriptor._internal_create_key,
        ),
        _descriptor.FieldDescriptor(
            name="stateless_init",
            full_name="lnrpc.ChangePasswordRequest.stateless_init",
            index=2,
            number=3,
            type=8,
            cpp_type=7,
            label=1,
            has_default_value=False,
            default_value=False,
            message_type=None,
            enum_type=None,
            containing_type=None,
            is_extension=False,
            extension_scope=None,
            serialized_options=None,
            file=DESCRIPTOR,
            create_key=_descriptor._internal_create_key,
        ),
        _descriptor.FieldDescriptor(
            name="new_macaroon_root_key",
            full_name="lnrpc.ChangePasswordRequest.new_macaroon_root_key",
            index=3,
            number=4,
            type=8,
            cpp_type=7,
            label=1,
            has_default_value=False,
            default_value=False,
            message_type=None,
            enum_type=None,
            containing_type=None,
            is_extension=False,
            extension_scope=None,
            serialized_options=None,
            file=DESCRIPTOR,
            create_key=_descriptor._internal_create_key,
        ),
    ],
    extensions=[],
    nested_types=[],
    enum_types=[],
    serialized_options=None,
    is_extendable=False,
    syntax="proto3",
    extension_ranges=[],
    oneofs=[],
    serialized_start=943,
    serialized_end=1069,
)


_CHANGEPASSWORDRESPONSE = _descriptor.Descriptor(
    name="ChangePasswordResponse",
    full_name="lnrpc.ChangePasswordResponse",
    filename=None,
    file=DESCRIPTOR,
    containing_type=None,
    create_key=_descriptor._internal_create_key,
    fields=[
        _descriptor.FieldDescriptor(
            name="admin_macaroon",
            full_name="lnrpc.ChangePasswordResponse.admin_macaroon",
            index=0,
            number=1,
            type=12,
            cpp_type=9,
            label=1,
            has_default_value=False,
            default_value=b"",
            message_type=None,
            enum_type=None,
            containing_type=None,
            is_extension=False,
            extension_scope=None,
            serialized_options=None,
            file=DESCRIPTOR,
            create_key=_descriptor._internal_create_key,
        ),
    ],
    extensions=[],
    nested_types=[],
    enum_types=[],
    serialized_options=None,
    is_extendable=False,
    syntax="proto3",
    extension_ranges=[],
    oneofs=[],
    serialized_start=1071,
    serialized_end=1119,
)

_INITWALLETREQUEST.fields_by_name[
    "channel_backups"
].message_type = lightning__pb2._CHANBACKUPSNAPSHOT
_INITWALLETREQUEST.fields_by_name["watch_only"].message_type = _WATCHONLY
_WATCHONLY.fields_by_name["accounts"].message_type = _WATCHONLYACCOUNT
_UNLOCKWALLETREQUEST.fields_by_name[
    "channel_backups"
].message_type = lightning__pb2._CHANBACKUPSNAPSHOT
DESCRIPTOR.message_types_by_name["GenSeedRequest"] = _GENSEEDREQUEST
DESCRIPTOR.message_types_by_name["GenSeedResponse"] = _GENSEEDRESPONSE
DESCRIPTOR.message_types_by_name["InitWalletRequest"] = _INITWALLETREQUEST
DESCRIPTOR.message_types_by_name["InitWalletResponse"] = _INITWALLETRESPONSE
DESCRIPTOR.message_types_by_name["WatchOnly"] = _WATCHONLY
DESCRIPTOR.message_types_by_name["WatchOnlyAccount"] = _WATCHONLYACCOUNT
DESCRIPTOR.message_types_by_name["UnlockWalletRequest"] = _UNLOCKWALLETREQUEST
DESCRIPTOR.message_types_by_name["UnlockWalletResponse"] = _UNLOCKWALLETRESPONSE
DESCRIPTOR.message_types_by_name["ChangePasswordRequest"] = _CHANGEPASSWORDREQUEST
DESCRIPTOR.message_types_by_name["ChangePasswordResponse"] = _CHANGEPASSWORDRESPONSE
_sym_db.RegisterFileDescriptor(DESCRIPTOR)

GenSeedRequest = _reflection.GeneratedProtocolMessageType(
    "GenSeedRequest",
    (_message.Message,),
    {
        "DESCRIPTOR": _GENSEEDREQUEST,
        "__module__": "walletunlocker_pb2"
        # @@protoc_insertion_point(class_scope:lnrpc.GenSeedRequest)
    },
)
_sym_db.RegisterMessage(GenSeedRequest)

GenSeedResponse = _reflection.GeneratedProtocolMessageType(
    "GenSeedResponse",
    (_message.Message,),
    {
        "DESCRIPTOR": _GENSEEDRESPONSE,
        "__module__": "walletunlocker_pb2"
        # @@protoc_insertion_point(class_scope:lnrpc.GenSeedResponse)
    },
)
_sym_db.RegisterMessage(GenSeedResponse)

InitWalletRequest = _reflection.GeneratedProtocolMessageType(
    "InitWalletRequest",
    (_message.Message,),
    {
        "DESCRIPTOR": _INITWALLETREQUEST,
        "__module__": "walletunlocker_pb2"
        # @@protoc_insertion_point(class_scope:lnrpc.InitWalletRequest)
    },
)
_sym_db.RegisterMessage(InitWalletRequest)

InitWalletResponse = _reflection.GeneratedProtocolMessageType(
    "InitWalletResponse",
    (_message.Message,),
    {
        "DESCRIPTOR": _INITWALLETRESPONSE,
        "__module__": "walletunlocker_pb2"
        # @@protoc_insertion_point(class_scope:lnrpc.InitWalletResponse)
    },
)
_sym_db.RegisterMessage(InitWalletResponse)

WatchOnly = _reflection.GeneratedProtocolMessageType(
    "WatchOnly",
    (_message.Message,),
    {
        "DESCRIPTOR": _WATCHONLY,
        "__module__": "walletunlocker_pb2"
        # @@protoc_insertion_point(class_scope:lnrpc.WatchOnly)
    },
)
_sym_db.RegisterMessage(WatchOnly)

WatchOnlyAccount = _reflection.GeneratedProtocolMessageType(
    "WatchOnlyAccount",
    (_message.Message,),
    {
        "DESCRIPTOR": _WATCHONLYACCOUNT,
        "__module__": "walletunlocker_pb2"
        # @@protoc_insertion_point(class_scope:lnrpc.WatchOnlyAccount)
    },
)
_sym_db.RegisterMessage(WatchOnlyAccount)

UnlockWalletRequest = _reflection.GeneratedProtocolMessageType(
    "UnlockWalletRequest",
    (_message.Message,),
    {
        "DESCRIPTOR": _UNLOCKWALLETREQUEST,
        "__module__": "walletunlocker_pb2"
        # @@protoc_insertion_point(class_scope:lnrpc.UnlockWalletRequest)
    },
)
_sym_db.RegisterMessage(UnlockWalletRequest)

UnlockWalletResponse = _reflection.GeneratedProtocolMessageType(
    "UnlockWalletResponse",
    (_message.Message,),
    {
        "DESCRIPTOR": _UNLOCKWALLETRESPONSE,
        "__module__": "walletunlocker_pb2"
        # @@protoc_insertion_point(class_scope:lnrpc.UnlockWalletResponse)
    },
)
_sym_db.RegisterMessage(UnlockWalletResponse)

ChangePasswordRequest = _reflection.GeneratedProtocolMessageType(
    "ChangePasswordRequest",
    (_message.Message,),
    {
        "DESCRIPTOR": _CHANGEPASSWORDREQUEST,
        "__module__": "walletunlocker_pb2"
        # @@protoc_insertion_point(class_scope:lnrpc.ChangePasswordRequest)
    },
)
_sym_db.RegisterMessage(ChangePasswordRequest)

ChangePasswordResponse = _reflection.GeneratedProtocolMessageType(
    "ChangePasswordResponse",
    (_message.Message,),
    {
        "DESCRIPTOR": _CHANGEPASSWORDRESPONSE,
        "__module__": "walletunlocker_pb2"
        # @@protoc_insertion_point(class_scope:lnrpc.ChangePasswordResponse)
    },
)
_sym_db.RegisterMessage(ChangePasswordResponse)


DESCRIPTOR._options = None

_WALLETUNLOCKER = _descriptor.ServiceDescriptor(
    name="WalletUnlocker",
    full_name="lnrpc.WalletUnlocker",
    file=DESCRIPTOR,
    index=0,
    serialized_options=None,
    create_key=_descriptor._internal_create_key,
    serialized_start=1122,
    serialized_end=1415,
    methods=[
        _descriptor.MethodDescriptor(
            name="GenSeed",
            full_name="lnrpc.WalletUnlocker.GenSeed",
            index=0,
            containing_service=None,
            input_type=_GENSEEDREQUEST,
            output_type=_GENSEEDRESPONSE,
            serialized_options=None,
            create_key=_descriptor._internal_create_key,
        ),
        _descriptor.MethodDescriptor(
            name="InitWallet",
            full_name="lnrpc.WalletUnlocker.InitWallet",
            index=1,
            containing_service=None,
            input_type=_INITWALLETREQUEST,
            output_type=_INITWALLETRESPONSE,
            serialized_options=None,
            create_key=_descriptor._internal_create_key,
        ),
        _descriptor.MethodDescriptor(
            name="UnlockWallet",
            full_name="lnrpc.WalletUnlocker.UnlockWallet",
            index=2,
            containing_service=None,
            input_type=_UNLOCKWALLETREQUEST,
            output_type=_UNLOCKWALLETRESPONSE,
            serialized_options=None,
            create_key=_descriptor._internal_create_key,
        ),
        _descriptor.MethodDescriptor(
            name="ChangePassword",
            full_name="lnrpc.WalletUnlocker.ChangePassword",
            index=3,
            containing_service=None,
            input_type=_CHANGEPASSWORDREQUEST,
            output_type=_CHANGEPASSWORDRESPONSE,
            serialized_options=None,
            create_key=_descriptor._internal_create_key,
        ),
    ],
)
_sym_db.RegisterServiceDescriptor(_WALLETUNLOCKER)

DESCRIPTOR.services_by_name["WalletUnlocker"] = _WALLETUNLOCKER

# @@protoc_insertion_point(module_scope)

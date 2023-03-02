from enum import Enum


class CashuReceiveFailReason(str, Enum):
    NONE = "none"
    MINT_OFFLINE = "mint_offline"
    MINT_ERROR = "mint_error"
    MINT_UNTRUSTED = "mint_untrusted"
    MINT_KEYSET_MISMATCH = "mint_keyset_mismatch"
    MINT_KEYSET_INVALID = "mint_keyset_invalid"
    FORMAT_ERROR = "format_error"
    LOCK_ERROR = "lock_error"
    PROOF_ERROR = "proof_error"
    UNKNOWN = "unknown"


class CashuException(Exception):
    def __init__(self, message: str, reason: CashuReceiveFailReason) -> None:
        super().__init__()
        self.message: str = message
        self.reason: CashuReceiveFailReason = reason


class UntrustedMintException(CashuException):
    def __init__(self, mint_url: str, mint_keyset: str) -> None:
        super().__init__(
            message="Mint is untrusted",
            reason=CashuReceiveFailReason.MINT_UNTRUSTED,
        )

        self.mint_url: str = mint_url
        self.mint_keyset: str = mint_keyset

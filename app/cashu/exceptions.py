from fastapi import HTTPException, status


class LockNotFoundException(HTTPException):
    def __init__(self):
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Lock not found.",
        )


class LockFormatException(HTTPException):
    def __init__(self):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Lock has wrong format. Expected P2SH:<address>.",
        )


class TokensSpentException(HTTPException):
    def __init__(self, secret: str):
        self.secret = secret
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Mint Error: tokens already spent.",
        )


class IsDefaultMintException(HTTPException):
    def __init__(self):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Default mint is already added.",
        )


class MintExistsException(HTTPException):
    def __init__(self, mint_name: str):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Mint with name {mint_name} was already added.",
        )


class WalletExistsException(HTTPException):
    def __init__(self, wallet_name: str):
        super().__init__(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Wallet {wallet_name} exists.",
        )


class WalletNotFoundException(HTTPException):
    def __init__(self, wallet_name: str):
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Wallet {wallet_name} not found.",
        )


class ZeroInvoiceException(HTTPException):
    def __init__(self):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Zero invoices not allowed. Amount must be positive.",
        )

from pydantic import BaseModel


class Invoice(BaseModel):
    r_hash: str
    payment_request: str
    add_index: int
    payment_addr: str

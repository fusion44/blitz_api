from fastapi import HTTPException, status


class OpenChannelPushAmountError(HTTPException):
    """Raised when a the push amount is lower than the channel size."""

    def __init__(self, local_funding, push_amt):
        self.status_code = status.HTTP_400_BAD_REQUEST
        self.detail = (
            f"Push amount {push_amt} must be lower than "
            f"local funding amount {local_funding}"
        )


class NodeNotFoundError(HTTPException):
    """Raised when a node is not found in the graph."""

    node_pub: str = ""

    def __init__(self, node_pub=""):
        self.status_code = status.HTTP_404_NOT_FOUND
        self.detail = f"Node {node_pub} not found"
        self.node_pub = node_pub

from fastapi import HTTPException, status


class NodeNotFoundError(HTTPException):
    """Raised when a node is not found in the graph."""

    node_pub: str = ""

    def __init__(self, node_pub=""):
        self.status_code = status.HTTP_404_NOT_FOUND
        self.detail = f"Node {node_pub} not found"
        self.node_pub = node_pub

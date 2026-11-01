"""Cliente MCP por HTTP, com token quando o servidor exige (o gateway exige)."""

from mcp.client.client import Client
from mcp.client.streamable_http import create_mcp_http_client, streamable_http_client


def conectar(url: str, token: str | None = None, timeout_s: float = 30) -> Client:
    """Uso: `async with conectar(url, token) as cliente: ...`."""
    if not token:
        return Client(url, read_timeout_seconds=timeout_s)
    http = create_mcp_http_client(headers={"Authorization": f"Bearer {token}"})
    return Client(streamable_http_client(url, http_client=http), read_timeout_seconds=timeout_s)

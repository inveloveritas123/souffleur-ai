"""adapters/mcp — stdio-Client für packages/coaching-mcp (Welle 13)."""
from __future__ import annotations

from souffleur.adapters.mcp.coaching_mcp_client import (
    DEFAULT_MCP_COMMAND,
    TOOL_NAME_GET_COACHING_KNOWLEDGE,
    CoachingMcpError,
    CoachingMcpStdioClient,
)

__all__ = [
    "DEFAULT_MCP_COMMAND",
    "TOOL_NAME_GET_COACHING_KNOWLEDGE",
    "CoachingMcpError",
    "CoachingMcpStdioClient",
]

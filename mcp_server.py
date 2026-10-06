#!/usr/bin/env python3
"""
Convenience entry point for running the pbip-doc-skill MCP Server.
Provides native Model Context Protocol (MCP) JSON-RPC 2.0 stdio server.
Zero external dependencies - runs on Python 3.8+ standard library.

Usage:
    python mcp_server.py
"""

from pbip_doc.mcp_server import main

if __name__ == "__main__":
    main()

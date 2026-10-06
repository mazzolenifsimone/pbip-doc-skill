#!/usr/bin/env python3
"""
Convenience entry point for extracting PBIP semantic model documentation JSON.

"""

import sys
from pbip_doc.cli import main

if __name__ == "__main__":
    # If called without subcommands, prepend 'extract' as default
    if len(sys.argv) == 1:
        sys.argv.extend(["extract", "-h"])
    elif sys.argv[1] in ("-h", "--help"):
        sys.argv = [sys.argv[0], "extract", "--help"]
    elif sys.argv[1] not in ("extract", "inspect", "docgen", "config"):
        sys.argv.insert(1, "extract")
    main()

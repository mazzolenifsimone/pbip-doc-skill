#!/usr/bin/env python3
"""
Convenience entry point for generating modular Markdown documentation
for tables and measures from PBIP models or JSON output.
Usage:
    python generate_docs.py ./samples/adventureworks_pbip -o ./docs
    python generate_docs.py ./semantic_model_docs.json -o ./docs
"""

import sys
from pbip_doc.cli import main

if __name__ == "__main__":
    if len(sys.argv) == 1:
        sys.argv.extend(["docgen", "-h"])
    elif sys.argv[1] in ("-h", "--help"):
        sys.argv = [sys.argv[0], "docgen", "--help"]
    elif sys.argv[1] not in ("docgen", "extract", "inspect", "config"):
        sys.argv.insert(1, "docgen")
    main()

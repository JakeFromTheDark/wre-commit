#!/usr/bin/env python3
"""Wrapper for pre-commit, so wre-commit."""

import sys
from wre_commit.main import main


if __name__ == "__main__":
    sys.exit(main())

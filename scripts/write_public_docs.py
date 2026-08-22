"""Retired public-doc writer.

Public documentation is now maintained in version-controlled source files and
validated by ``scripts/check_public_metadata.py``. This module remains as a
compatibility stub so old local references fail safely instead of reintroducing
stale v2.3-era content.
"""

from __future__ import annotations


def main() -> None:
    print(
        "Public docs are maintained directly; run scripts/check_public_metadata.py to validate them."
    )


if __name__ == "__main__":
    main()

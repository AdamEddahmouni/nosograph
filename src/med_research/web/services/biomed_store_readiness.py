"""API helpers for uninitialized or empty canonical biomedical store responses."""

from __future__ import annotations

from typing import Any, TypeVar, cast

from med_research.biomed.store_readiness import BIOMED_STORE_INIT_HINT
from med_research.web.models.universal import (
    BiomedicalStoreStateView,
    PagedResponse,
    ResearchDisclaimer,
)

T = TypeVar("T")

_DISCLAIMER = ResearchDisclaimer()


def uninitialized_store_state() -> BiomedicalStoreStateView:
    return BiomedicalStoreStateView(
        status="uninitialized",
        initialization_hint=BIOMED_STORE_INIT_HINT,
    )


def ready_store_state() -> BiomedicalStoreStateView:
    return BiomedicalStoreStateView(status="ready", initialization_hint="")


def empty_paged_response(
    *,
    limit: int,
    offset: int,
) -> PagedResponse[Any]:
    return cast(
        PagedResponse[Any],
        PagedResponse(
            items=[],
            total=0,
            limit=limit,
            offset=offset,
            disclaimer=_DISCLAIMER,
            store_state=uninitialized_store_state(),
        ),
    )

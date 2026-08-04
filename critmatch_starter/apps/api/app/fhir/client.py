"""Minimal FHIR R4 client.

Only the functionality CritMatch actually uses is implemented:

- Bearer-token authenticated GETs against ``${FHIR_BASE_URL}``
- Search with automatic pagination by following ``Bundle.link[rel=next]``
- Whole-resource fetch by reference (e.g. ``Patient/123``)

The client is intentionally synchronous; the worker process is a single
poller and we want stack traces to be straightforward. Switch to ``httpx.AsyncClient``
if/when we move to a concurrent worker.

PATCHED (audit fix): ``search()`` used to silently stop (a bare ``return``)
once ``page_limit`` pages were fetched, with no way for the caller to tell
"the server had nothing else" apart from "we gave up early." Any consumer
combining results across rules (see ``services/query_runner.py``) could
silently treat a truncated, incomplete result set as the complete one.
``search()`` now raises ``FHIRSearchTruncated`` by default when the limit is
hit. Callers that genuinely only want a best-effort single-page peek (e.g.
``services/edc_fhir.py``'s single-value pull) opt into the old silent
behavior explicitly via ``on_limit="truncate"``.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import httpx


class FHIRError(RuntimeError):
    pass


class FHIRSearchTruncated(FHIRError):
    """Raised when a search hit ``page_limit`` before exhausting results.

    This means the yielded resources are an incomplete view of everything
    matching the search - treat any correctness-sensitive computation (patient
    counts, match sets, etc.) as invalid rather than partially correct.
    """


class FHIRClient:
    def __init__(
        self,
        base_url: str,
        access_token: str | None = None,
        *,
        timeout: float = 30.0,
        user_agent: str = "CritMatch/0.1",
    ) -> None:
        if not base_url:
            raise FHIRError("FHIR base URL required")
        self._base_url = base_url.rstrip("/")
        headers = {"Accept": "application/fhir+json", "User-Agent": user_agent}
        if access_token:
            headers["Authorization"] = f"Bearer {access_token}"
        self._client = httpx.Client(
            base_url=self._base_url,
            headers=headers,
            timeout=timeout,
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "FHIRClient":
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()

    # ------------------------------------------------------------------
    # Core operations
    # ------------------------------------------------------------------

    def read(self, reference: str) -> dict[str, Any]:
        resp = self._client.get(f"/{reference.lstrip('/')}" )
        if resp.status_code != 200:
            raise FHIRError(f"FHIR read {reference} -> {resp.status_code}: {resp.text[:200]}")
        return resp.json()

    def search(
        self,
        resource_type: str,
        params: dict[str, str | int | list[str]] | None = None,
        *,
        page_limit: int = 20,
        on_limit: str = "raise",
    ) -> Iterator[dict[str, Any]]:
        """Yield each entry resource across paginated search results.

        ``page_limit`` caps how many ``Bundle`` pages we follow per call,
        which prevents runaway requests on overly broad queries.

        ``on_limit`` controls what happens if there are still more pages
        (a ``Bundle.link[rel=next]``) once ``page_limit`` is reached:

        - ``"raise"`` (default): raise ``FHIRSearchTruncated``. Use this for
          anything where an incomplete result set would silently corrupt a
          downstream computation (matching, counting, aggregating).
        - ``"truncate"``: return what's been fetched so far and stop, same
          as this method's old behavior. Only appropriate when the caller
          explicitly wants "at most N pages, and that's fine" - e.g. a
          single opportunistic value pull that already scopes the search
          tightly (``_count=1``).
        """

        if on_limit not in ("raise", "truncate"):
            raise ValueError("on_limit must be 'raise' or 'truncate'")

        url: str | None = f"/{resource_type}"
        flat_params = self._flatten(params or {})
        pages = 0
        while url:
            if pages >= page_limit:
                if on_limit == "raise":
                    raise FHIRSearchTruncated(
                        f"FHIR search {resource_type} exceeded page_limit={page_limit} "
                        "pages without exhausting results; the yielded resources are "
                        "an incomplete view. Pass on_limit='truncate' if a partial "
                        "result set is acceptable for this call site."
                    )
                return
            resp = self._client.get(url, params=flat_params if pages == 0 else None)
            if resp.status_code != 200:
                raise FHIRError(
                    f"FHIR search {resource_type} -> {resp.status_code}: {resp.text[:200]}"
                )
            bundle = resp.json()
            for entry in bundle.get("entry", []) or []:
                resource = entry.get("resource")
                if resource:
                    yield resource
            url = self._next_link(bundle)
            pages += 1

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _flatten(params: dict[str, str | int | list[str]]) -> list[tuple[str, str]]:
        flat: list[tuple[str, str]] = []
        for key, value in params.items():
            if isinstance(value, list):
                for v in value:
                    flat.append((key, str(v)))
            else:
                flat.append((key, str(value)))
        return flat

    @staticmethod
    def _next_link(bundle: dict[str, Any]) -> str | None:
        for link in bundle.get("link", []) or []:
            if link.get("relation") == "next":
                return link.get("url")
        return None

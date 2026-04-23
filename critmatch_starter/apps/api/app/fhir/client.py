"""Minimal FHIR R4 client.

Only the functionality CritMatch actually uses is implemented:

- Bearer-token authenticated GETs against ``${FHIR_BASE_URL}``
- Search with automatic pagination by following ``Bundle.link[rel=next]``
- Whole-resource fetch by reference (e.g. ``Patient/123``)

The client is intentionally synchronous; the worker process is a single
poller and we want stack traces to be straightforward. Switch to ``httpx.AsyncClient``
if/when we move to a concurrent worker.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import httpx


class FHIRError(RuntimeError):
    pass


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
        resp = self._client.get(f"/{reference.lstrip('/')}")
        if resp.status_code != 200:
            raise FHIRError(f"FHIR read {reference} -> {resp.status_code}: {resp.text[:200]}")
        return resp.json()

    def search(
        self,
        resource_type: str,
        params: dict[str, str | int | list[str]] | None = None,
        *,
        page_limit: int = 20,
    ) -> Iterator[dict[str, Any]]:
        """Yield each entry resource across paginated search results.

        ``page_limit`` caps how many ``Bundle`` pages we follow per call,
        which prevents runaway requests on overly broad queries.
        """

        url: str | None = f"/{resource_type}"
        flat_params = self._flatten(params or {})
        pages = 0
        while url:
            if pages >= page_limit:
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

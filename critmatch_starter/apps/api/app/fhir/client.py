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
    """Base error for any non-2xx FHIR response.

    ``status_code`` and ``operation_outcome`` (the server's parsed FHIR
    ``OperationOutcome``, when it returned one) are attached so callers can
    react to *why* a call failed instead of just logging raw response text.
    """

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        operation_outcome: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.operation_outcome = operation_outcome


class FHIRSearchTruncated(FHIRError):
    """Raised when a search hit ``page_limit`` before exhausting results.

    This means the yielded resources are an incomplete view of everything
    matching the search - treat any correctness-sensitive computation (patient
    counts, match sets, etc.) as invalid rather than partially correct.
    """


class FHIRUnauthorizedError(FHIRError):
    """401: the access token is missing, expired, or otherwise rejected."""


class FHIRForbiddenError(FHIRError):
    """403: the token is valid but lacks the scope/consent for this resource."""


class FHIRRateLimitedError(FHIRError):
    """429: the server is rate-limiting us.

    ``retry_after`` mirrors the response's ``Retry-After`` header - an ``int``
    number of seconds if the header was numeric, the raw header string if it
    was an HTTP-date, or ``None`` if the header was absent.
    """

    def __init__(
        self,
        message: str,
        *,
        status_code: int = 429,
        retry_after: int | str | None = None,
        operation_outcome: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, status_code=status_code, operation_outcome=operation_outcome)
        self.retry_after = retry_after


def _parse_operation_outcome(resp: httpx.Response) -> dict[str, Any] | None:
    """Return ``{"issues": [{"severity", "code", "diagnostics"}, ...]}`` if
    ``resp``'s body is a FHIR ``OperationOutcome``, else ``None``.
    """
    try:
        body = resp.json()
    except ValueError:
        return None
    if not isinstance(body, dict) or body.get("resourceType") != "OperationOutcome":
        return None
    issues = [
        {
            "severity": issue.get("severity"),
            "code": issue.get("code"),
            "diagnostics": issue.get("diagnostics"),
        }
        for issue in body.get("issue", []) or []
    ]
    return {"issues": issues}


def _retry_after(resp: httpx.Response) -> int | str | None:
    raw = resp.headers.get("Retry-After")
    if raw is None:
        return None
    try:
        return int(raw)
    except ValueError:
        return raw


def _raise_for_error(resp: httpx.Response, context: str) -> None:
    """Raise the ``FHIRError`` subclass matching ``resp``'s status code.

    Called only for non-2xx responses. Prefers OperationOutcome
    severity/diagnostics over raw response text when the server provided one.
    """
    operation_outcome = _parse_operation_outcome(resp)
    if operation_outcome and operation_outcome["issues"]:
        detail = "; ".join(
            f"{issue.get('severity') or 'error'}: "
            f"{issue.get('diagnostics') or issue.get('code') or 'no diagnostics'}"
            for issue in operation_outcome["issues"]
        )
    else:
        detail = resp.text[:200]
    message = f"{context} -> {resp.status_code}: {detail}"

    if resp.status_code == 401:
        raise FHIRUnauthorizedError(
            message, status_code=401, operation_outcome=operation_outcome
        )
    if resp.status_code == 403:
        raise FHIRForbiddenError(message, status_code=403, operation_outcome=operation_outcome)
    if resp.status_code == 429:
        raise FHIRRateLimitedError(
            message,
            retry_after=_retry_after(resp),
            operation_outcome=operation_outcome,
        )
    raise FHIRError(message, status_code=resp.status_code, operation_outcome=operation_outcome)


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
            _raise_for_error(resp, f"FHIR read {reference}")
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
                _raise_for_error(resp, f"FHIR search {resource_type}")
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

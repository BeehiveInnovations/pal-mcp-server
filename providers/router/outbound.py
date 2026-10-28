"""Single outbound pipeline for provider send paths.

build payload -> guardrail.mask_outbound -> headroom compress (eligible
tool-result content only) -> size_guard on POST-compression size -> caller's
resilience/fallback (call_with_fallback handles the 413 we raise) -> send.
"""

from __future__ import annotations

from typing import Any


def prepare(payload: Any, model: str, *, compress: bool = True) -> tuple[Any, Any]:
    """Return (payload, mask_ctx); mask_ctx feeds guardrail.guard_response."""
    from providers.router import guardrail, headroom_adapter, size_guard

    payload, ctx = guardrail.mask_outbound(payload)
    if compress:
        payload = headroom_adapter.compress_payload(payload)
    ok, hint = size_guard.check_payload(model, payload)
    if not ok:
        raise size_guard.PayloadTooLarge(model, len(size_guard.payload_text(payload)) // 4, hint)
    return payload, ctx

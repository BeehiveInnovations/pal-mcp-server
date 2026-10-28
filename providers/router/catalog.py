"""Capability-aware model catalog.

One record per (service, model). ``service`` is who you pay / authenticate
with (groq, openrouter, gemini, openai, xai, ...); ``adapter`` is the PAL
provider class that serves it (ProviderType). The two differ: Groq is reached
through the ``custom`` adapter, so adapter alone cannot say which vendor a
model belongs to.

Sources merged:
    static      conf/*_models.json manifests (curated capabilities, trusted)
    discovered  live ``/models`` listing per service, cached on disk with a TTL

Only services with a real adapter AND real credentials are exposed by default.
Keys that exist in ~/.pal/keys.env for vendors with no adapter (deepseek,
mistral, zai, ...) never appear here.

Routing consumes ``select()`` / ``order_for_category()``: eligibility is a hard
filter on capability flags (tools, structured output, context, quality);
operator name lists are demoted to a tie-break prior. Routing reads the cache
only -- it never touches the network. Only ``pal models`` (build(discover=True))
does.

Env:
    PAL_CATALOG_TTL_S          discovery cache TTL, default 21600
    PAL_CATALOG_FAIL_TTL_S     negative-cache TTL after a failed fetch, default 300
    PAL_CATALOG_CACHE          cache file, default ~/.pal/model_catalog.json
    PAL_CATALOG_ROUTING        0 disables catalog routing (legacy name lists)
    PAL_MODEL_PROFILES_PATH    cost overlay, default conf/model_profiles.json
    PAL_CATALOG_SMART_MIN_Q    min intelligence for the smart tier, default 12
    PAL_CATALOG_BULK_CTX       min context for long_context_bulk, default 200000
"""

from __future__ import annotations

import json
import logging
import os
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlparse

log = logging.getLogger(__name__)

_ROOT = Path(__file__).resolve().parents[2]
CACHE_PATH = Path(os.getenv("PAL_CATALOG_CACHE", str(Path.home() / ".pal/model_catalog.json")))
PROFILES_PATH = Path(os.getenv("PAL_MODEL_PROFILES_PATH", str(_ROOT / "conf" / "model_profiles.json")))
CACHE_VERSION = 1
FETCH_TIMEOUT_S = 8.0

COST_RANK = {"free": 0, "low": 1, "mid": 2, "unknown": 2, "high": 3}
AVAILABLE = "available"


def _ttl() -> float:
    return float(os.getenv("PAL_CATALOG_TTL_S", "21600"))


def _fail_ttl() -> float:
    return float(os.getenv("PAL_CATALOG_FAIL_TTL_S", "300"))


def is_routing_enabled() -> bool:
    return os.getenv("PAL_CATALOG_ROUTING", "1") not in ("0", "false", "no")


# --------------------------------------------------------------------------
# Data model
# --------------------------------------------------------------------------
@dataclass
class CatalogEntry:
    provider: str  # service identity: groq / openrouter / gemini / openai / xai / ...
    adapter: str  # ProviderType value that serves it
    model: str  # canonical wire id
    display: str
    aliases: list[str] = field(default_factory=list)
    chat: bool | None = True
    tools: bool | None = None  # None = unknown (never treated as True)
    vision: bool | None = None
    structured_output: bool | None = None
    reasoning: bool | None = None
    context_limit: int = 0
    availability: str = AVAILABLE  # available|no_auth|unhealthy|stale|discovered
    quality_profile: dict = field(default_factory=dict)  # {intelligence, rank}
    cost_profile: dict = field(default_factory=dict)  # {tier, basis, input_per_mtok, output_per_mtok}
    source: str = "static"  # static | discovered | static+discovered

    @property
    def routable(self) -> bool:
        return self.availability == AVAILABLE

    @property
    def intelligence(self) -> int:
        return int(self.quality_profile.get("intelligence") or 0)

    @property
    def cost_rank(self) -> int:
        return COST_RANK.get(self.cost_profile.get("tier", "unknown"), 2)

    def names(self) -> set[str]:
        return {self.model.lower(), *(a.lower() for a in self.aliases)}

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Catalog:
    entries: list[CatalogEntry]
    discovery: dict[str, dict]  # service -> {status, age_s, count, error}
    generated_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {
            "generated_at": self.generated_at,
            "discovery": self.discovery,
            "models": [e.to_dict() for e in self.entries],
        }


# --------------------------------------------------------------------------
# Auth / service identity
# --------------------------------------------------------------------------
def _env(name: str) -> str:
    try:
        from utils.env import get_env

        return (get_env(name, "") or "").strip()
    except Exception:
        return os.getenv(name, "").strip()


def _real(value: str) -> bool:
    v = (value or "").strip().lower()
    return bool(v) and not v.startswith("your_") and not v.endswith("_here")


def _is_local(url: str) -> bool:
    host = (urlparse(url).hostname or "").lower()
    return host in ("localhost", "127.0.0.1", "::1", "host.docker.internal") or host.endswith(".local")


def _custom_service(url: str) -> str:
    host = (urlparse(url).hostname or "").lower()
    if host.endswith("groq.com"):
        return "groq"
    if _is_local(url):
        return "local"
    return host or "custom"


# --------------------------------------------------------------------------
# Adapter specs: one row per adapter that PAL can really talk to
# --------------------------------------------------------------------------
def _registry(adapter: str):
    from providers import registries as r

    return {
        "google": r.GeminiModelRegistry,
        "openai": r.OpenAIModelRegistry,
        "xai": r.XAIModelRegistry,
        "openrouter": r.OpenRouterModelRegistry,
        "custom": r.CustomEndpointModelRegistry,
        "dial": r.DialModelRegistry,
        "azure": r.AzureModelRegistry,
    }[adapter]()


def _auth(adapter: str) -> tuple[bool, str]:
    """(has_real_credentials, service_name)."""
    if adapter == "google":
        return _real(_env("GEMINI_API_KEY")), "gemini"
    if adapter == "openai":
        return _real(_env("OPENAI_API_KEY")), "openai"
    if adapter == "xai":
        return _real(_env("XAI_API_KEY")), "xai"
    if adapter == "openrouter":
        return _real(_env("OPENROUTER_API_KEY")), "openrouter"
    if adapter == "dial":
        return _real(_env("DIAL_API_KEY")), "dial"
    if adapter == "azure":
        return _real(_env("AZURE_OPENAI_API_KEY")) and bool(_env("AZURE_OPENAI_ENDPOINT")), "azure"
    if adapter == "custom":
        url = _env("CUSTOM_API_URL")
        if not url:
            return False, "custom"
        # keyless is legitimate only for local runtimes (ollama, vLLM, LM Studio)
        return _real(_env("CUSTOM_API_KEY")) or _is_local(url), _custom_service(url)
    return False, adapter


ADAPTERS = ("google", "openai", "xai", "openrouter", "custom", "dial", "azure")


def _discovery_request(adapter: str) -> tuple[str, dict] | None:
    """(url, headers) for the live model listing, or None if the adapter has none."""
    if adapter == "google":
        return (
            "https://generativelanguage.googleapis.com/v1beta/models?pageSize=200",
            {"x-goog-api-key": _env("GEMINI_API_KEY")},
        )
    if adapter == "openai":
        return "https://api.openai.com/v1/models", {"Authorization": f"Bearer {_env('OPENAI_API_KEY')}"}
    if adapter == "xai":
        return "https://api.x.ai/v1/models", {"Authorization": f"Bearer {_env('XAI_API_KEY')}"}
    if adapter == "openrouter":
        return (
            "https://openrouter.ai/api/v1/models",
            {"Authorization": f"Bearer {_env('OPENROUTER_API_KEY')}"},
        )
    if adapter == "custom":
        url = _env("CUSTOM_API_URL").rstrip("/")
        headers = {"Authorization": f"Bearer {_env('CUSTOM_API_KEY')}"} if _env("CUSTOM_API_KEY") else {}
        return url + "/models", headers
    return None  # azure deployments / DIAL: static manifest is the source of truth


# --------------------------------------------------------------------------
# Discovery parsing: raw /models JSON -> normalised dicts. Unknown stays None.
# --------------------------------------------------------------------------
def _per_mtok(value: Any) -> float | None:
    try:
        return round(float(value) * 1_000_000, 4)
    except (TypeError, ValueError):
        return None


def _parse_openrouter(data: dict) -> list[dict]:
    out = []
    for m in data.get("data", []):
        mid = m.get("id")
        if not mid:
            continue
        params = set(m.get("supported_parameters") or [])
        arch = m.get("architecture") or {}
        pricing = m.get("pricing") or {}
        out.append(
            {
                "id": mid,
                "chat": "text" in (arch.get("output_modalities") or ["text"]),
                "tools": "tools" in params if params else None,
                "vision": "image" in (arch.get("input_modalities") or []),
                "structured_output": bool(params & {"structured_outputs", "response_format"}) if params else None,
                "reasoning": bool(params & {"reasoning", "include_reasoning"}) if params else None,
                "context_limit": int(m.get("context_length") or 0),
                "input_per_mtok": _per_mtok(pricing.get("prompt")),
                "output_per_mtok": _per_mtok(pricing.get("completion")),
            }
        )
    return out


def _parse_gemini(data: dict) -> list[dict]:
    out = []
    for m in data.get("models", []):
        name = (m.get("name") or "").removeprefix("models/")
        if not name:
            continue
        methods = m.get("supportedGenerationMethods") or []
        out.append(
            {
                "id": name,
                "chat": "generateContent" in methods,
                "context_limit": int(m.get("inputTokenLimit") or 0),
                "reasoning": m.get("thinking"),
            }
        )
    return out


def _parse_openai_style(data: dict) -> list[dict]:
    out = []
    for m in data.get("data", []):
        mid = m.get("id")
        if not mid:
            continue
        # Bare OpenAI-style listings carry no capability info: chat stays
        # unknown (None) rather than guessed from the name.
        out.append(
            {
                "id": mid,
                "chat": None,
                "context_limit": int(m.get("context_window") or m.get("context_length") or 0),
            }
        )
    return out


_PARSERS: dict[str, Callable[[dict], list[dict]]] = {
    "google": _parse_gemini,
    "openrouter": _parse_openrouter,
    "openai": _parse_openai_style,
    "xai": _parse_openai_style,
    "custom": _parse_openai_style,
}


def _http_json(url: str, headers: dict, timeout: float = FETCH_TIMEOUT_S) -> dict:
    """Injectable in tests. Never logs headers (they carry credentials)."""
    req = urllib.request.Request(
        url, headers={"Accept": "application/json", "User-Agent": "pal-mcp-server/catalog", **headers}
    )  # noqa: S310
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
        return json.loads(resp.read().decode("utf-8"))


def _fetch_models(adapter: str, fetcher: Callable) -> list[dict]:
    req = _discovery_request(adapter)
    if req is None:
        raise LookupError("no discovery endpoint")
    url, headers = req
    models: list[dict] = []
    for _ in range(5):  # gemini paginates; cap pages
        data = fetcher(url, headers)
        models.extend(_PARSERS[adapter](data))
        token = data.get("nextPageToken") if adapter == "google" else None
        if not token:
            break
        sep = "&" if "?" in url else "?"
        url = f"{url.split('&pageToken=')[0]}{sep}pageToken={token}"
    return models


# --------------------------------------------------------------------------
# Discovery cache (TTL, atomic, negative-cached)
# --------------------------------------------------------------------------
def _read_cache() -> dict:
    try:
        data = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
        if data.get("version") == CACHE_VERSION and isinstance(data.get("services"), dict):
            return data
    except (OSError, ValueError):
        pass
    return {"version": CACHE_VERSION, "services": {}}


def _write_cache(data: dict) -> None:
    try:
        CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        tmp = CACHE_PATH.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=1, sort_keys=True), encoding="utf-8")
        os.chmod(tmp, 0o600)
        os.replace(tmp, CACHE_PATH)
    except OSError as exc:  # cache is an optimisation; never fatal
        log.debug("catalog cache write failed: %s", exc)


def _discover(
    adapter: str, service: str, cache: dict, *, refresh: bool, network: bool, fetcher: Callable
) -> tuple[list[dict] | None, dict, bool]:
    """Return (models_or_None, status, cache_dirty). Models None = no listing available."""
    if _discovery_request(adapter) is None:
        return None, {"status": "off", "reason": "static-only adapter"}, False
    now = time.time()
    rec = cache["services"].get(service)
    if rec:
        age = now - rec.get("fetched_at", 0)
        fresh = age < (_ttl() if rec.get("ok") else _fail_ttl())
        if fresh and not refresh:
            st = {"status": "cached" if rec.get("ok") else "failed", "age_s": int(age), "error": rec.get("error")}
            return (rec.get("models") if rec.get("ok") else None), {**st, "count": len(rec.get("models", []))}, False
    if not network:
        if rec and rec.get("ok"):
            age = int(now - rec.get("fetched_at", 0))
            return rec["models"], {"status": "stale", "age_s": age, "count": len(rec["models"])}, False
        return None, {"status": "none", "reason": "no cache (offline)"}, False
    try:
        models = _fetch_models(adapter, fetcher)
        cache["services"][service] = {"fetched_at": now, "ok": True, "error": None, "models": models}
        return models, {"status": "fresh", "age_s": 0, "count": len(models)}, True
    except Exception as exc:  # noqa: BLE001 - any transport/parse failure degrades to static
        err = f"{type(exc).__name__}: {str(exc)[:120]}"
        prior = (rec or {}).get("models", [])
        # keep the last good listing on disk but mark the attempt failed
        cache["services"][service] = {"fetched_at": now, "ok": False, "error": err, "models": prior}
        return None, {"status": "failed", "age_s": 0, "error": err, "count": len(prior)}, True


# --------------------------------------------------------------------------
# Cost / quality profile
# --------------------------------------------------------------------------
def _load_profiles() -> dict:
    try:
        return json.loads(PROFILES_PATH.read_text(encoding="utf-8")).get("profiles", {})
    except (OSError, ValueError):
        return {}


def _tier_from_price(input_per_mtok: float | None, output_per_mtok: float | None) -> str | None:
    if input_per_mtok is None and output_per_mtok is None:
        return None
    i, o = input_per_mtok or 0.0, output_per_mtok or 0.0
    if i == 0 and o == 0:
        return "free"
    blended = (3 * i + o) / 4
    return "low" if blended < 1.0 else "mid" if blended < 8.0 else "high"


def _cost_profile(service: str, model: str, intelligence: int, disc: dict | None, profiles: dict) -> dict:
    ipm = (disc or {}).get("input_per_mtok")
    opm = (disc or {}).get("output_per_mtok")
    tier = _tier_from_price(ipm, opm)
    if tier:
        return {"tier": tier, "basis": "pricing", "input_per_mtok": ipm, "output_per_mtok": opm}
    overlay = profiles.get(f"{service}/{model}")
    if overlay and overlay.get("cost_tier") in COST_RANK:
        return {"tier": overlay["cost_tier"], "basis": "overlay", "input_per_mtok": None, "output_per_mtok": None}
    if intelligence:
        est = "low" if intelligence <= 9 else "mid" if intelligence <= 14 else "high"
        return {"tier": est, "basis": "estimated", "input_per_mtok": None, "output_per_mtok": None}
    return {"tier": "unknown", "basis": "unknown", "input_per_mtok": None, "output_per_mtok": None}


# --------------------------------------------------------------------------
# Build + merge
# --------------------------------------------------------------------------
def _health_ok(service: str) -> bool:
    try:
        from providers.router import quota_probe

        return quota_probe.is_available(service)
    except Exception:
        return True  # unknown -> optimistic, same policy as quota_probe


def _static_entries(adapter: str, service: str) -> list[CatalogEntry]:
    try:
        reg = _registry(adapter)
        reg.reload()
        rows = list(reg.iter_entries())
    except Exception as exc:  # noqa: BLE001
        log.debug("static registry %s unavailable: %s", adapter, exc)
        return []
    out = []
    for name, caps, _extra in rows:
        # openrouter manifests may embed custom-provider rows; those belong to the custom service
        if getattr(caps.provider, "value", caps.provider) != adapter:
            continue
        out.append(
            CatalogEntry(
                provider=service,
                adapter=adapter,
                model=name,
                display=caps.friendly_name or name,
                aliases=list(caps.aliases or []),
                chat=True,
                tools=bool(caps.supports_function_calling),
                vision=bool(caps.supports_images),
                structured_output=bool(caps.supports_json_mode),
                reasoning=bool(caps.supports_extended_thinking),
                context_limit=int(caps.context_window or 0),
                quality_profile={
                    "intelligence": int(caps.intelligence_score or 0),
                    "rank": int(caps.get_effective_capability_rank()),
                },
                source="static",
            )
        )
    return out


def build(
    *,
    refresh: bool = False,
    discover: bool = True,
    include_unavailable: bool = False,
    fetcher: Callable | None = None,
) -> Catalog:
    """Merge static manifests with discovery for every real, authenticated service.

    discover=False reads the cache only (routing path, no network).
    refresh=True bypasses the TTL. include_unavailable also returns services
    lacking credentials (availability=no_auth) for diagnostics.
    """
    fetcher = fetcher or _http_json
    profiles = _load_profiles()
    cache = _read_cache()
    dirty = False
    entries: list[CatalogEntry] = []
    status: dict[str, dict] = {}

    for adapter in ADAPTERS:
        authed, service = _auth(adapter)
        if not authed and not include_unavailable:
            continue
        static = _static_entries(adapter, service)
        live: list[dict] | None = None
        if authed:
            live, st, d = _discover(adapter, service, cache, refresh=refresh, network=discover, fetcher=fetcher)
            dirty |= d
            status[service] = st
        else:
            status[service] = {"status": "no_auth"}

        live_by_id = {m["id"].lower(): m for m in (live or [])}
        healthy = _health_ok(service) if authed else True
        seen: set[str] = set()

        for e in static:
            key = e.model.lower()
            seen.add(key)
            disc = live_by_id.get(key)
            if not authed:
                e.availability = "no_auth"
            elif not healthy:
                e.availability = "unhealthy"
            elif live_by_id and disc is None:
                e.availability = "stale"  # provider no longer lists it: drifted/deprecated
            if disc:
                e.source = "static+discovered"
                if not e.context_limit and disc.get("context_limit"):
                    e.context_limit = disc["context_limit"]
            e.cost_profile = _cost_profile(service, e.model, e.intelligence, disc, profiles)
            entries.append(e)

        for mid, m in live_by_id.items():
            if mid in seen:
                continue
            ent = CatalogEntry(
                provider=service,
                adapter=adapter,
                model=m["id"],
                display=m["id"],
                chat=m.get("chat"),
                tools=m.get("tools"),
                vision=m.get("vision"),
                structured_output=m.get("structured_output"),
                reasoning=m.get("reasoning"),
                context_limit=int(m.get("context_limit") or 0),
                availability="discovered",  # listed by the vendor but not curated: never auto-routed
                source="discovered",
            )
            ent.cost_profile = _cost_profile(service, ent.model, 0, m, profiles)
            entries.append(ent)

    if dirty:
        _write_cache(cache)
    entries.sort(key=lambda e: (e.provider, -e.intelligence, e.model))
    return Catalog(entries=entries, discovery=status)


_MEMO: dict[str, Any] = {"at": 0.0, "cat": None}


def routing_catalog(max_age_s: float = 60.0) -> Catalog:
    """Cache-only catalog for the routing hot path (no network, memoised)."""
    now = time.time()
    if _MEMO["cat"] is None or now - _MEMO["at"] > max_age_s:
        _MEMO["cat"] = build(discover=False)
        _MEMO["at"] = now
    return _MEMO["cat"]


def reset_memo() -> None:
    _MEMO.update(at=0.0, cat=None)


# --------------------------------------------------------------------------
# Capability-based selection
# --------------------------------------------------------------------------
@dataclass
class Need:
    tier: str | None = None  # "cheap" | "smart" | None
    tools: bool = False
    vision: bool = False
    structured_output: bool = False
    reasoning: bool = False
    min_context: int = 0
    min_intelligence: int = 0
    providers: set[str] | None = None  # allow-list of services
    # Free-tier routes (pricing == 0) commonly log prompts and rotate the
    # underlying model, so they are excluded unless a category opts in.
    allow_free_tier: bool = False


def _smart_min() -> int:
    return int(os.getenv("PAL_CATALOG_SMART_MIN_Q", "12"))


def eligible(e: CatalogEntry, need: Need) -> bool:
    """Hard capability filter. Unknown (None) never satisfies a requirement."""
    if not e.routable or e.chat is not True:
        return False
    if need.providers is not None and e.provider not in need.providers:
        return False
    if e.cost_profile.get("tier") == "free" and not need.allow_free_tier:
        return False
    if need.tools and e.tools is not True:
        return False
    if need.vision and e.vision is not True:
        return False
    if need.structured_output and e.structured_output is not True:
        return False
    if need.reasoning and e.reasoning is not True:
        return False
    if e.context_limit < need.min_context:
        return False
    floor = max(need.min_intelligence, _smart_min() if need.tier == "smart" else 0)
    return e.intelligence >= floor


def _prior_index(e: CatalogEntry, priors: tuple[str, ...]) -> int:
    names = e.names() | {f"{e.provider}/{e.model}".lower()}
    for i, p in enumerate(priors):
        if p.lower() in names:
            return i
    return len(priors)


def select(need: Need, entries: list[CatalogEntry] | None = None, priors: tuple[str, ...] = ()) -> list[CatalogEntry]:
    """Eligible entries, best first.

    Capabilities decide *who may run*; the operator prior (legacy name list)
    never admits a model that fails the filter, it only orders the survivors:
        cheap / untiered   cost tier, then prior, then intelligence
        smart              prior, then cost tier, then intelligence
    """
    pool = entries if entries is not None else routing_catalog().entries
    ok = [e for e in pool if eligible(e, need)]
    if need.tier == "smart":
        ok.sort(key=lambda e: (_prior_index(e, priors), e.cost_rank, -e.intelligence, e.provider, e.model))
    else:
        ok.sort(key=lambda e: (e.cost_rank, _prior_index(e, priors), -e.intelligence, e.provider, e.model))
    return ok


def _bulk_ctx() -> int:
    return int(os.getenv("PAL_CATALOG_BULK_CTX", "200000"))


def category_need(category: str) -> Need | None:
    """Capability requirements per classifier category."""
    if category == "long_context_bulk":
        return Need(min_context=_bulk_ctx(), allow_free_tier=True)  # bulk read of non-sensitive files
    if category == "structured_extract":
        return Need(structured_output=True)
    if category == "long_form_prose":
        return Need(min_intelligence=12, min_context=64_000)
    if category == "security_permissive":
        return Need(min_intelligence=10)
    return None


def order_for_category(category: str, priors: list[str]) -> list[str]:
    """Candidate model ids for a classifier category, capability-filtered.

    ``priors`` (legacy CATEGORY_PREFERENCES names) only order ties. Returns []
    when the catalog has nothing eligible so callers fall back to the legacy list.
    """
    need = category_need(category)
    if need is None or not is_routing_enabled():
        return []
    from providers.router.chat_router import SMART_TIER

    # category priors first, then the general smart-tier preference as a
    # secondary prior so leftovers are not ordered by raw intelligence alone
    order = tuple(priors) + tuple(SMART_TIER)
    ranked = select(need, priors=order)
    ranked.sort(key=lambda e: _prior_index(e, order))  # stable: cost/quality order kept within a prior slot
    out: list[str] = []
    for e in ranked:
        if e.model not in out:
            out.append(e.model)
    return out


def pick_tier(tier: str, is_available: Callable[[str], bool], priors: tuple[str, ...] = ()) -> str | None:
    """Best model id for the chat tier ('cheap' | 'smart') from the catalog.

    ``is_available`` is the live registry check, applied to the model id and
    each alias so catalog and registry can never disagree about reachability.
    """
    if not is_routing_enabled():
        return None
    try:
        ranked = select(Need(tier=tier), priors=priors)
    except Exception as exc:  # noqa: BLE001
        log.debug("catalog pick_tier degraded: %s", exc)
        return None
    for e in ranked:
        for name in (e.model, *e.aliases):
            if is_available(name):
                return name
    return None

"""Minimal Jev client. Standard library only.

Two routes, same request and response shape:
  - TypeSafe directly, if TYPESAFE_API_KEY is set (env or ~/.config/typesafe/.env)
  - Vercel AI Gateway otherwise, with AI_GATEWAY_API_KEY (env or ~/.config/ai-gateway/.env)
Keys are never printed, logged, or written anywhere else.
"""
import hashlib, json, os, random, time, urllib.error, urllib.request
from pathlib import Path

PRICE_PER_M_INPUT = 0.042     # USD per million input tokens; output tokens are free
ROUTES = [  # first route with a key wins
    ("TYPESAFE_API_KEY", Path("~/.config/typesafe/.env"), "https://api.typesafe.ai/v1/systemone", "jev-latest"),
    ("AI_GATEWAY_API_KEY", Path("~/.config/ai-gateway/.env"), "https://ai-gateway.vercel.sh/typesafe/v1/systemone", "typesafe-ai/jev"),
]
ENDPOINT = None


def _read(name, path):
    if os.environ.get(name):
        return os.environ[name].strip()
    path = path.expanduser()
    if path.is_file():
        for line in path.read_text().splitlines():
            if line.startswith(f"{name}="):
                value = line.split("=", 1)[1].strip().strip("'\"")
                if value and "paste" not in value:
                    return value
    return None


def api_key():
    """Pick the route, set ENDPOINT, and return (key, model id for that route)."""
    global ENDPOINT
    for name, path, endpoint, model in ROUTES:
        key = _read(name, path)
        if key:
            ENDPOINT = endpoint
            return key, model
    raise SystemExit("No Jev key. Set TYPESAFE_API_KEY or AI_GATEWAY_API_KEY in the environment, "
                     "or in ~/.config/typesafe/.env or ~/.config/ai-gateway/.env.")


def state_for(posting, context):
    """What Jev may read. IDs, URLs, and anything used to grade it stay out."""
    return {"goal": context, "company": posting["company"], "title": posting["title"],
            "location": posting["location"], "remote": posting["remote"], "pay": posting["pay"],
            "description": posting["body"]}


def cache_key(model, questions, state):
    blob = json.dumps([model, questions, state], sort_keys=True)
    return hashlib.sha256(blob.encode()).hexdigest()[:24]


def ask(key, model, questions, state, timeout=60):
    body = json.dumps({"model": model, "state": state, "questions": questions}).encode()
    req = urllib.request.Request(ENDPOINT, data=body, method="POST", headers={
        "Authorization": f"Bearer {key}", "Content-Type": "application/json",
        "User-Agent": "ai-pm-job-radar"})
    for attempt in range(4):
        start = time.monotonic()
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                out = json.load(r)
            out["latency_ms"] = round((time.monotonic() - start) * 1000)
            return out
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 529) and attempt < 3:
                wait = e.headers.get("Retry-After")
                wait = float(wait) if wait and wait.replace(".", "", 1).isdigit() else 5 * 3 ** attempt
                time.sleep(min(wait, 60) + random.random())   # 5s, 15s, 45s: back off, don't hammer
                continue
            raise RuntimeError(f"HTTP {e.code}: {e.read().decode(errors='replace')[:300]}") from None
        except (urllib.error.URLError, TimeoutError) as e:
            if attempt < 3:
                time.sleep(min(2 ** attempt, 20))
                continue
            raise RuntimeError(f"network: {e}") from None


def cost(response):
    """Prefer the gateway's own billed cost; fall back to tokens x list price."""
    gw = (response.get("provider_metadata") or {}).get("gateway") or {}
    if gw.get("cost") is not None:
        return float(gw["cost"])
    return response.get("usage", {}).get("input_tokens", 0) * PRICE_PER_M_INPUT / 1e6

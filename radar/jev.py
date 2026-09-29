"""Minimal Jev client over Vercel AI Gateway's TypeSafe-compatible endpoint. Standard library only.

The key is read from AI_GATEWAY_API_KEY, or from ~/.config/ai-gateway/.env. It is never
printed, logged, or written anywhere else.
"""
import hashlib, json, os, random, time, urllib.error, urllib.request
from pathlib import Path

ENDPOINT = "https://ai-gateway.vercel.sh/typesafe/v1/systemone"
PRICE_PER_M_INPUT = 0.042     # USD per million input tokens; output tokens are free
KEY_FILE = Path("~/.config/ai-gateway/.env").expanduser()


def api_key():
    if os.environ.get("AI_GATEWAY_API_KEY"):
        return os.environ["AI_GATEWAY_API_KEY"].strip()
    if KEY_FILE.is_file():
        for line in KEY_FILE.read_text().splitlines():
            if line.startswith("AI_GATEWAY_API_KEY="):
                value = line.split("=", 1)[1].strip().strip("'\"")
                if value:
                    return value
    raise SystemExit(f"No AI_GATEWAY_API_KEY. Set it in the environment or in {KEY_FILE}.")


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
    for attempt in range(6):
        start = time.monotonic()
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                out = json.load(r)
            out["latency_ms"] = round((time.monotonic() - start) * 1000)
            return out
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 529) and attempt < 5:
                time.sleep(min(2 ** attempt, 20) + random.random())
                continue
            raise RuntimeError(f"HTTP {e.code}: {e.read().decode(errors='replace')[:300]}") from None
        except (urllib.error.URLError, TimeoutError) as e:
            if attempt < 5:
                time.sleep(min(2 ** attempt, 20))
                continue
            raise RuntimeError(f"network: {e}") from None


def cost(response):
    """Prefer the gateway's own billed cost; fall back to tokens x list price."""
    gw = (response.get("provider_metadata") or {}).get("gateway") or {}
    if gw.get("cost") is not None:
        return float(gw["cost"])
    return response.get("usage", {}).get("input_tokens", 0) * PRICE_PER_M_INPUT / 1e6

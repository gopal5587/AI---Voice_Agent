"""Create or update the three Vapi assistants from configs/assistants/*.json.

Usage (from backend/):
  python scripts/sync_vapi.py               # dry run: prints the payloads that would be sent
  python scripts/sync_vapi.py --apply       # creates/updates assistants, prints IDs for .env

Requires VAPI_API_KEY and PUBLIC_BASE_URL (a public HTTPS URL of the backend, e.g. Railway or an ngrok tunnel).
If WEBHOOK_SECRET is set it is attached to every server/tool URL and sent by Vapi as the X-Vapi-Secret header.
"""
import argparse
import copy
import json
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.config import settings  # noqa: E402

API = "https://api.vapi.ai"
ENV_KEYS = {"business_loan": "VAPI_ASSISTANT_BUSINESS_LOAN", "ph_life_insurance": "VAPI_ASSISTANT_PH",
            "id_consumer_finance": "VAPI_ASSISTANT_ID"}


def build_payload(key: str, base_url: str, secret: str | None) -> dict:
    cfg = json.loads((settings.configs_dir / "assistants" / f"{key}.json").read_text(encoding="utf-8"))
    vapi = json.loads(json.dumps(cfg["vapi"]).replace("{{PUBLIC_BASE_URL}}", base_url.rstrip("/")))
    payload = copy.deepcopy(vapi)
    model = payload["model"]
    model["messages"] = [{"role": "system", "content": model.pop("systemPrompt")}]
    for tool in model.get("tools", []):
        if secret and "server" in tool:
            tool["server"]["secret"] = secret
    server_url = payload.pop("serverUrl", None)
    if server_url:
        payload["server"] = {"url": server_url, **({"secret": secret} if secret else {})}
    recording = payload.pop("recordingEnabled", None)
    if recording is not None:
        payload["artifactPlan"] = {"recordingEnabled": recording}
    payload["metadata"] = {"assistant_key": key, "kb_version": "see /api/kb/report", "demo": True}
    return payload


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--only", choices=list(ENV_KEYS))
    args = ap.parse_args()

    base = settings.public_base_url
    if not base or "localhost" in base:
        print("WARNING: PUBLIC_BASE_URL is not a public URL; Vapi cannot reach localhost tool endpoints.")
    keys = [args.only] if args.only else list(ENV_KEYS)

    if not args.apply:
        for key in keys:
            print(f"--- {key} ---")
            print(json.dumps(build_payload(key, base or "https://YOUR-BACKEND", "***" if settings.webhook_secret else None),
                             indent=2, ensure_ascii=False)[:4000])
        print("\nDry run only. Re-run with --apply to create/update assistants.")
        return

    if not settings.vapi_api_key:
        sys.exit("VAPI_API_KEY is not set")
    headers = {"Authorization": f"Bearer {settings.vapi_api_key}"}
    with httpx.Client(base_url=API, headers=headers, timeout=30) as client:
        for key in keys:
            payload = build_payload(key, base, settings.webhook_secret)
            existing = settings.vapi_assistants.get(key)
            if existing:
                r = client.patch(f"/assistant/{existing}", json=payload)
            else:
                r = client.post("/assistant", json=payload)
            if r.status_code >= 300:
                print(f"{key}: FAILED {r.status_code} {r.text[:500]}")
                continue
            print(f"{ENV_KEYS[key]}={r.json()['id']}   # {'updated' if existing else 'created'}")
    print("\nCopy the IDs above into .env (backend) and restart; the web UI then enables 'Vapi web call' mode.")


if __name__ == "__main__":
    main()

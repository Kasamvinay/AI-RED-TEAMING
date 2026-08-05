"""
verify_target_connection.py

Standalone sanity check — NOT part of the red-team pipeline, imports
nothing from attacks/judge/knowledge_base/orchestrator. Run this by
itself to confirm the framework can actually reach and talk to your
running Acme SupportBot before spending any real attack budget on it.

Usage:
    python verify_target_connection.py
    python verify_target_connection.py --base-url http://localhost:8000
"""

from __future__ import annotations

import argparse
import time

from adapters.acme_supportbot_adapter import AcmeSupportBotAdapter
from core.types import AttackPrompt


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--timeout", type=float, default=180.0)
    args = parser.parse_args()

    adapter = AcmeSupportBotAdapter(
        base_url=args.base_url, timeout_seconds=args.timeout, reset_between_attacks=True
    )

    print(f"Target: {args.base_url}\n")

    # --- 1. A boring, benign request. If this fails, nothing else will work. ---
    print("[1] Sending a normal support question...")
    start = time.perf_counter()
    prompt = AttackPrompt(text="What subscription plans does Acme offer?",
                           category="prompt_injection", technique="sanity_check")
    response = adapter.send(prompt)
    elapsed = time.perf_counter() - start

    print(f"    Wall-clock time: {elapsed:.1f}s")
    print(f"    error: {response.error}")
    print(f"    raw payload: {response.raw}")
    print(f"    response text: {response.text[:300]!r}")

    if response.error:
        print("\n>>> FAILED. The framework cannot reach your target. Fix this before running")
        print(">>> any attacks — an unreachable target will silently look like 'the bot")
        print(">>> refused everything' otherwise. Common causes:")
        print("    - FastAPI isn't running (check: curl http://localhost:8000/health)")
        print("    - Ollama isn't running or hasn't pulled the model")
        print("    - wrong --base-url / TARGET_BASE_URL")
        print("    - firewall blocking localhost — unlikely but check")
        return

    if elapsed < 1.0:
        print("\n>>> WARNING: that response came back suspiciously fast for local CPU")
        print(">>> inference. Double-check this isn't a cached/mocked/error-shortcut path.")
    else:
        print(f"\n>>> Looks like a real model round trip ({elapsed:.1f}s, no error).")

    # --- 2. Multi-turn session sanity check ---
    print("\n[2] Sending a 2-turn conversation to check session/history handling...")
    convo_response = adapter.send_conversation([
        "My name is Alex and I have a question about refunds.",
        "What's my name, based on what I just told you?",
    ])
    print(f"    error: {convo_response.error}")
    print(f"    final response text: {convo_response.text[:300]!r}")
    if convo_response.raw:
        print(f"    session_id used: {convo_response.raw.get('session_id')}")
    if not convo_response.error and "alex" in convo_response.text.lower():
        print(">>> Session history is genuinely being preserved across turns.")
    elif not convo_response.error:
        print(">>> No error, but the bot didn't recall the name — check your target's")
        print(">>> session storage / history-inclusion logic, not the adapter.")

    print("\nDone. Cross-check the raw payload/session_id above against your FastAPI")
    print("server's own terminal logs — you should see matching POST /chat and")
    print("POST /reset/<session_id> lines appear there at the same timestamps.")


if __name__ == "__main__":
    main()

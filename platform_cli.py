"""CLI: chat and watch (.platform_snapshot.json). Commands: /help /new /quit."""

from __future__ import annotations

import sys
from utils.config import get_settings

from langchain_anthropic import ChatAnthropic
from state.sa_state import get_state
from utils.cmd_input_output import apply_feedback, send_message

print("RUNNING FROM:", sys.executable)
import argparse
import asyncio
import json
import os
import time
import uuid
from pathlib import Path

from dotenv import load_dotenv

_ROOT = Path(__file__).resolve().parent
_SNAPSHOT = _ROOT / ".platform_snapshot.json"
_SESSION_FILE = _ROOT / ".platform_session"

for _env_path in [_ROOT.parent / ".env", _ROOT / ".env"]:
    if _env_path.exists():
        load_dotenv(_env_path)
        break

from graphs.sa_graph import build_graph


def _load_session_id() -> str | None:
    if not _SESSION_FILE.is_file():
        return None
    return _SESSION_FILE.read_text(encoding="utf-8").strip() or None


def _save_session_id(sid: str) -> None:
    _SESSION_FILE.write_text(sid, encoding="utf-8")


def _extract_agent_reply(raw_state: dict) -> str:
    messages = raw_state.get("messages") or []
    for msg in reversed(messages):
        if getattr(msg, "type", "") == "ai":
            return getattr(msg, "content", "")
    return ""


def _sa_only_payload(session_id: str, raw_state: dict) -> dict:
    return {
        "updated_at": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime()),
        "session_id": session_id,
        "next_agent": raw_state.get("next_agent") or "",
        "session_goal": raw_state.get("session_goal") or "",
        "goal_progress": raw_state.get("goal_progress") or "",
        "inferred_domain": raw_state.get("sa_inferred_domain") or "",
        "inferred_task": raw_state.get("sa_inferred_task") or "",
        "phase": raw_state.get("sa_phase") or "",
        "thoughts": raw_state.get("sa_thoughts") or [],
        "checklist": raw_state.get("sa_checklist") or [],
        "card": raw_state.get("sa_card"),
        "buffer_pending": [
            b
            for b in (raw_state.get("sa_readiness_buffer") or [])
            if not b.get("fired")
        ],
        "context_for_agents": raw_state.get("sa_context_for_agent") or {},
        "sa_feedback": raw_state.get("sa_feedback"),
    }


def _write_sa_snapshot(session_id: str, raw_state: dict) -> None:
    payload = _sa_only_payload(session_id, raw_state)
    _SNAPSHOT.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )


def _empty_sa_payload(session_id: str) -> dict:
    return _sa_only_payload(session_id, {})


def _print_watch_screen(payload: dict) -> None:
    os.system("cls" if os.name == "nt" else "clear")
    print("Super Agent (snapshot)\n")
    print(json.dumps(payload, indent=2, ensure_ascii=False, default=str))
    print("\nCtrl+C to stop.")


async def chat_async() -> None:

    cfg = get_settings()
    llm = ChatAnthropic(
        model=cfg.anthropic_model,
        api_key=cfg.anthropic_api_key,
        max_tokens=4096,
        temperature=0.2,
    )

    graph = build_graph(llm, checkpointer=None)
    session_id = _load_session_id() or str(uuid.uuid4())
    _save_session_id(session_id)

    print()
    print("agent_platform — session:", session_id)
    print("Type /help for commands.\n")

    st = await get_state(graph, session_id)
    _write_sa_snapshot(session_id, st)

    loop = asyncio.get_event_loop()

    while True:
        try:
            line = await loop.run_in_executor(None, lambda: input("You> ").strip())
        except (EOFError, KeyboardInterrupt):
            print("\nBye.")
            break

        if not line:
            continue

        if line.startswith("/"):
            parts = line.split(maxsplit=1)
            cmd = parts[0].lower()

            if cmd in ("/quit", "/exit", "/q"):
                print("Bye.")
                break
            if cmd == "/help":
                print(
                    "/help /new /quit\n"
                    "  /new — new session\n"
                    "  agent_1 replies; SA runs after each turn — see watch for goals, checklist, next_agent.\n"
                    "  If SA shows a card after your message, you’ll be asked proceed/decline.\n"
                )
                continue
            if cmd == "/new":
                session_id = str(uuid.uuid4())
                _save_session_id(session_id)
                print("New session:", session_id)
                _SNAPSHOT.write_text(
                    json.dumps(
                        _empty_sa_payload(session_id), indent=2, ensure_ascii=False
                    ),
                    encoding="utf-8",
                )
                continue

            print("Unknown command. /help")
            continue

        await send_message(graph, session_id, line)
        final_state = await get_state(graph, session_id)

        reply = _extract_agent_reply(final_state)
        active = final_state.get("active_agent") or "?"
        print()
        print(f"[{active}]")
        print(reply)
        print()
        _write_sa_snapshot(session_id, final_state)

        card = final_state.get("sa_card")
        if card:
            print("SA card")
            print(card.get("title", ""))
            print(card.get("body", ""))
            ans = await loop.run_in_executor(
                None,
                lambda: input("Card: type proceed / decline / Enter skip: ")
                .strip()
                .lower(),
            )
            if ans in ("proceed", "p"):
                await apply_feedback(
                    graph, session_id, "proceed", card.get("suggestion_id")
                )
                final_state = await get_state(graph, session_id)
                _write_sa_snapshot(session_id, final_state)
            elif ans in ("decline", "d"):
                await apply_feedback(
                    graph, session_id, "decline", card.get("suggestion_id")
                )
                final_state = await get_state(graph, session_id)
                _write_sa_snapshot(session_id, final_state)


async def watch_async(interval: float) -> None:
    last_mtime = 0.0
    last_text = ""
    print("Waiting for", _SNAPSHOT, "...")
    try:
        while True:
            if _SNAPSHOT.is_file():
                mtime = _SNAPSHOT.stat().st_mtime
                text = _SNAPSHOT.read_text(encoding="utf-8")
                if mtime != last_mtime or text != last_text:
                    last_mtime = mtime
                    last_text = text
                    try:
                        payload = json.loads(text)
                    except json.JSONDecodeError:
                        continue
                    _print_watch_screen(payload)
            await asyncio.sleep(interval)
    except KeyboardInterrupt:
        print("\nStopped.")


def main() -> None:
    p = argparse.ArgumentParser(description="Super Agent")
    sub = p.add_subparsers(dest="command", required=True)

    sub.add_parser(
        "chat", help="Chat with agent_1 + SA observer; watch for SA snapshot"
    )
    w = sub.add_parser("watch", help="Poll .platform_snapshot.json")
    w.add_argument("-i", "--interval", type=float, default=0.5)

    args = p.parse_args()
    if args.command == "chat":
        asyncio.run(chat_async())
    else:
        asyncio.run(watch_async(args.interval))


if __name__ == "__main__":
    main()

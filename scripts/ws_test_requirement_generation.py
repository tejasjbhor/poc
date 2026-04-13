

""" Test ..."""

from __future__ import annotations

import asyncio
import json
import sys
import uuid
from pathlib import Path



from typing import Optional

REPO_ROOT = Path(__file__).resolve().parent.parent

try:
    import websockets
except ImportError:
    print("Install: pip install websockets")
    sys.exit(1)

HOST = "127.0.0.1"
PORT = 8000
SESSION = f"test-{uuid.uuid4().hex[:8]}"
URL = f"ws://{HOST}:{PORT}/ws/requirement_generation/{SESSION}"

START = {
    "type": "start",
    "payload": {
        "system_description": (
            "Battery cell manufacturing line: active material preparation, electrode coating "
            "and drying, cell stacking and electrolyte fill, formation and aging, end-of-line "
            "electrical test, grading, and finished-goods storage. Scope is one production hall "
            "with buffer storage; utilities at battery limits."
        ),
        "system_functions": [
            {
                "id": "f1",
                "name": "Material intake and preparation",
                "description": (
                    "Receipt, storage, and preparation of active materials and foils for coating."
                ),
                "surface_area": None,
                "category": "",
                "interfaces_in": [],
                "interfaces_out": [
                    {"function_id": "f2", "materials": ["electrode_slurry", "foil"]},
                ],
            },
            {
                "id": "f2",
                "name": "Electrode coating",
                "description": "Apply slurry to foil and dry before downstream assembly.",
                "surface_area": None,
                "category": "",
                "interfaces_in": [
                    {"function_id": "f1", "materials": ["electrode_slurry", "foil"]},
                ],
                "interfaces_out": [],
            },
        ],
        "assumptions": [
            "Single production hall; no multi-site logistics.",
            "Surface areas not specified until user provides them.",
        ],
    },
}


def _print(msg: dict) -> None:
    print(json.dumps(msg, indent=2))


def _first_interrupt_id(msg: dict) -> Optional[str]:
    if msg.get("type") != "interrupt":
        return None
    data = msg.get("data") or []
    if not data:
        return None
    return data[0].get("id")


async def main() -> None:
    print(f"Connecting: {URL}\n")
    try:
        async with websockets.connect(URL) as ws:
            await ws.send(json.dumps(START))
            print("Sent start.\n")

            while True:
                raw = await ws.recv()
                msg = json.loads(raw)
                _print(msg)



                if msg.get("type") == "finished":
                    print("\nDone.")
                    return

                if msg.get("type") == "interrupt":
                    iid = _first_interrupt_id(msg)
                    if not iid:
                        print("No interrupt id in message; exiting.")
                        return
                    val = input(
                        '\nType resume "value" (function id e.g. f1, or "done", or feedback): '
                    ).strip()
                    out = {"type": "resume", "interrupt_id": iid, "value": val}
                    await ws.send(json.dumps(out))
                    print("Sent resume.\n")
    
    
    
    
    except (ConnectionRefusedError, OSError) as e:
        print(
            "Connection refused — nothing is listening on this host/port.\n"
            "Start the API first in a separate terminal, then run this script again:\n"
            f"  cd /d {REPO_ROOT}\n"
            "  python run_graph.py\n"
            f"\n(Default port is {PORT}; if you use APP_PORT in .env, change PORT in this script.)\n"
            f"Detail: {e!r}"
        )
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())

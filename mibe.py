#!/usr/bin/env python3
"""Monitor Codex session JSONL logs and notify via XiaoAi (miservice)."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import signal
import sys
from pathlib import Path

from aiohttp import ClientSession
from miservice import MiAccount, MiNAService

SESSIONS_DIR = Path.home() / ".codex" / "sessions"
POLL_INTERVAL = 0.5
TOKEN_STORE = str(Path.home() / ".mi.token")

# How often (seconds) to send silent TTS to keep XiaoAi's light on.
KEEPALIVE_INTERVAL = 5.0
KEEPALIVE_TEXT = "。"

# TTS messages for each event type.
MESSAGES: dict[str, str] = {
    "task_started": "vibe启动",
    "task_complete": "任务完成",
    "turn_aborted": "任务中断",
}

WATCHED_EVENTS = frozenset(MESSAGES)


# ---------------------------------------------------------------------------
# miservice helpers
# ---------------------------------------------------------------------------

class XiaoAiNotifier:
    """Wraps miservice login and TTS via MiNAService."""

    def __init__(self, verbose: bool = False) -> None:
        self.verbose = verbose
        self._session: ClientSession | None = None
        self._account: MiAccount | None = None
        self._mina: MiNAService | None = None
        self._device_id: str | None = None
        self._saved_volume: int | None = None
        self._keepalive_task: asyncio.Task | None = None

    async def login(self) -> None:
        mi_user = os.environ.get("MI_USER", "")
        mi_pass = os.environ.get("MI_PASS", "")
        mi_did = os.environ.get("MI_DID", "")

        if not mi_user or not mi_pass:
            print("[mibe] error: MI_USER and MI_PASS environment variables required", file=sys.stderr)
            raise SystemExit(1)

        self._session = ClientSession()
        self._account = MiAccount(self._session, mi_user, mi_pass, TOKEN_STORE)
        await self._account.login("micoapi")

        self._mina = MiNAService(self._account)
        devices = await self._mina.device_list()

        if mi_did:
            for d in devices:
                if d.get("miotDID", "") == str(mi_did):
                    self._device_id = d.get("deviceID")
                    break
            if not self._device_id:
                print(f"[mibe] warning: MI_DID={mi_did} not found, using first device", file=sys.stderr)

        if not self._device_id and devices:
            self._device_id = devices[0].get("deviceID")

        if not self._device_id:
            print("[mibe] error: no XiaoAi device found", file=sys.stderr)
            raise SystemExit(1)

        if self.verbose:
            print(f"[mibe] logged in, device_id={self._device_id}")

    async def get_volume(self) -> int | None:
        """Get current volume (0-100) or None on failure."""
        if not self._mina or not self._device_id:
            return None
        try:
            status = await self._mina.player_get_status(self._device_id)
            info = json.loads(status.get("data", {}).get("info", "{}"))
            return info.get("volume")
        except Exception:  # noqa: BLE001
            return None

    async def set_volume(self, volume: int) -> None:
        if not self._mina or not self._device_id:
            return
        try:
            await self._mina.player_set_volume(self._device_id, volume)
            if self.verbose:
                print(f"[mibe] volume -> {volume}")
        except Exception as exc:  # noqa: BLE001
            print(f"[mibe] set_volume error: {exc}", file=sys.stderr)

    async def save_and_mute(self) -> None:
        """Save current volume then mute."""
        vol = await self.get_volume()
        if vol is not None:
            self._saved_volume = vol
            if self.verbose:
                print(f"[mibe] saved volume={vol}, muting")
        await self.set_volume(0)

    async def restore_volume(self) -> None:
        """Restore previously saved volume."""
        vol = self._saved_volume
        if vol is not None:
            await self.set_volume(vol)
            self._saved_volume = None

    async def speak(self, text: str) -> None:
        if not self._mina or not self._device_id:
            return
        try:
            await self._mina.text_to_speech(self._device_id, text)
            if self.verbose:
                print(f"[mibe] tts: {text}")
        except Exception as exc:  # noqa: BLE001
            print(f"[mibe] tts error: {exc}", file=sys.stderr)

    # -- keepalive: periodically send silent TTS to keep the light on --

    async def _keepalive_loop(self) -> None:
        """Send silent TTS at regular intervals so XiaoAi stays lit."""
        try:
            while True:
                await asyncio.sleep(KEEPALIVE_INTERVAL)
                if self.verbose:
                    print("[mibe] keepalive tts")
                await self.speak(KEEPALIVE_TEXT)
        except asyncio.CancelledError:
            pass

    def start_keepalive(self) -> None:
        if self._keepalive_task is None or self._keepalive_task.done():
            self._keepalive_task = asyncio.ensure_future(self._keepalive_loop())
            if self.verbose:
                print("[mibe] keepalive started")

    async def stop_keepalive(self) -> None:
        if self._keepalive_task and not self._keepalive_task.done():
            self._keepalive_task.cancel()
            try:
                await self._keepalive_task
            except asyncio.CancelledError:
                pass
            self._keepalive_task = None
            if self.verbose:
                print("[mibe] keepalive stopped")

    async def close(self) -> None:
        await self.stop_keepalive()
        if self._session:
            await self._session.close()


# ---------------------------------------------------------------------------
# File monitoring
# ---------------------------------------------------------------------------

def list_session_files(sessions_dir: Path) -> list[Path]:
    if not sessions_dir.exists():
        return []
    return sorted(sessions_dir.rglob("*.jsonl"))


# Delay (seconds) after TTS to let it finish before muting.
TTS_SETTLE_DELAY = 3.0


async def process_event(event: dict, notifier: XiaoAiNotifier) -> None:
    if event.get("type") != "event_msg":
        return
    payload = event.get("payload")
    if not isinstance(payload, dict):
        return

    event_type = payload.get("type")
    if event_type not in WATCHED_EVENTS:
        return

    turn_id = payload.get("turn_id")
    print(f"[mibe] {event_type} turn_id={turn_id}", flush=True)

    if event_type == "task_started":
        # Announce start, wait for TTS to finish, mute, then keep light on.
        await notifier.speak(MESSAGES[event_type])
        await asyncio.sleep(TTS_SETTLE_DELAY)
        await notifier.save_and_mute()
        notifier.start_keepalive()
    elif event_type in ("task_complete", "turn_aborted"):
        # Stop keepalive, restore volume, then announce.
        await notifier.stop_keepalive()
        await notifier.restore_volume()
        await notifier.speak(MESSAGES[event_type])
    else:
        await notifier.speak(MESSAGES[event_type])


async def read_new_lines(
    path: Path,
    offsets: dict[Path, int],
    notifier: XiaoAiNotifier,
) -> None:
    old_offset = offsets.get(path, 0)
    try:
        file_size = path.stat().st_size
    except OSError:
        return
    if file_size < old_offset:
        old_offset = 0

    with path.open("r", encoding="utf-8", errors="replace") as fh:
        fh.seek(old_offset)
        while True:
            line_start = fh.tell()
            line = fh.readline()
            if not line:
                break
            if not line.endswith("\n"):
                fh.seek(line_start)  # incomplete line, retry next poll
                break
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(event, dict):
                await process_event(event, notifier)
        offsets[path] = fh.tell()


def init_offsets(
    sessions_dir: Path, replay: str,
) -> dict[Path, int]:
    """Build initial file-offset map based on replay strategy."""
    files = list_session_files(sessions_dir)
    offsets: dict[Path, int] = {}

    if replay == "all":
        for p in files:
            offsets[p] = 0
    elif replay == "latest" and files:
        latest = max(files, key=lambda p: p.stat().st_mtime_ns)
        for p in files:
            offsets[p] = 0 if p == latest else p.stat().st_size
    else:
        for p in files:
            offsets[p] = p.stat().st_size

    return offsets


# ---------------------------------------------------------------------------
# CLI: subcommands
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="mibe",
        description="Monitor Codex session logs and notify via XiaoAi.",
    )
    sub = parser.add_subparsers(dest="command")

    # --- login ---
    sub.add_parser("login", help="Test miservice login and list devices.")

    # --- monitor ---
    mon = sub.add_parser("monitor", help="Watch Codex session logs and send TTS notifications.")
    mon.add_argument(
        "--replay-existing",
        choices=("none", "latest", "all"),
        default="none",
        help="Replay events on startup (default: none).",
    )
    mon.add_argument(
        "--verbose", action="store_true", help="Print event and command details.",
    )

    return parser


async def cmd_login() -> int:
    """Test login and print device list."""
    mi_user = os.environ.get("MI_USER", "")
    mi_pass = os.environ.get("MI_PASS", "")

    if not mi_user or not mi_pass:
        print("[mibe] error: set MI_USER and MI_PASS environment variables", file=sys.stderr)
        return 1

    async with ClientSession() as session:
        account = MiAccount(session, mi_user, mi_pass, TOKEN_STORE)
        await account.login("micoapi")
        print("[mibe] login successful!")

        mina = MiNAService(account)
        devices = await mina.device_list()

        if not devices:
            print("[mibe] no devices found")
            return 0

        mi_did = os.environ.get("MI_DID", "")
        print(f"\n{'#':<4} {'Name':<20} {'Hardware':<12} {'miotDID':<16} {'Selected'}")
        print("-" * 70)
        for i, d in enumerate(devices, 1):
            did = d.get("miotDID", "")
            selected = " <--" if (mi_did and did == mi_did) else ("" if mi_did else (" <-- (default)" if i == 1 else ""))
            print(f"{i:<4} {d.get('name', '?'):<20} {d.get('hardware', '?'):<12} {did:<16} {selected}")

        if not mi_did:
            print(f"\n[mibe] tip: set MI_DID={devices[0].get('miotDID', '')} to choose a device")

    return 0


async def cmd_monitor(args: argparse.Namespace) -> int:
    """Main monitoring loop."""
    sessions_dir = Path(os.path.expanduser(str(SESSIONS_DIR)))

    notifier = XiaoAiNotifier(verbose=args.verbose)
    await notifier.login()

    offsets = init_offsets(sessions_dir, args.replay_existing)

    print(f"[mibe] watching: {sessions_dir}")
    print("[mibe] press Ctrl+C to stop")

    loop = asyncio.get_running_loop()
    stop_event = asyncio.Event()

    def _handle_signal() -> None:
        print("\n[mibe] signal received, restoring volume and exiting...")
        stop_event.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, _handle_signal)

    try:
        while not stop_event.is_set():
            for path in list_session_files(sessions_dir):
                if path not in offsets:
                    offsets[path] = 0  # new session file, read from start
                await read_new_lines(path, offsets, notifier)
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=POLL_INTERVAL)
            except asyncio.TimeoutError:
                pass
    finally:
        await notifier.restore_volume()
        await notifier.close()
        print("[mibe] stopped")

    return 0


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "login":
        return asyncio.run(cmd_login())
    elif args.command == "monitor":
        return asyncio.run(cmd_monitor(args))
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

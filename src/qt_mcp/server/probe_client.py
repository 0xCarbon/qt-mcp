"""Async TCP client for communicating with the probe's JSON-RPC server."""

from __future__ import annotations

import asyncio
import json
from typing import Any

DEFAULT_PROBE_PORT = 9142
SCREENSHOT_STREAM_LIMIT_BYTES = 16 * 1024 * 1024
DEFAULT_RESPONSE_TIMEOUT_SECONDS = 30.0


class ProbeConnectionError(Exception):
    """Raised when connection to the probe fails."""


class ProbeClient:
    """Connects to the probe's JSON-RPC TCP server and sends requests."""

    def __init__(self, host: str = "localhost", port: int = DEFAULT_PROBE_PORT) -> None:
        self._host = host
        self._port = port
        self._reader = None
        self._writer = None
        self._request_id = 0
        self._lock = asyncio.Lock()

    async def connect(self, retries: int = 5, delay: float = 1.0) -> None:
        """Connect to the probe with retries."""
        last_err: Exception | None = None
        for attempt in range(retries):
            try:
                # 16MB limit to handle large base64-encoded screenshots
                self._reader, self._writer = await asyncio.open_connection(
                    self._host,
                    self._port,
                    limit=SCREENSHOT_STREAM_LIMIT_BYTES,
                )
                return
            except (OSError, ConnectionRefusedError) as exc:
                last_err = exc
                if attempt < retries - 1:
                    await asyncio.sleep(delay)
        raise ProbeConnectionError(
            f"Failed to connect to probe at {self._host}:{self._port} "
            f"after {retries} attempts: {last_err}"
        )

    @property
    def connected(self) -> bool:
        return self._writer is not None and not self._writer.is_closing()

    async def call(self, method: str, params: dict[str, Any] | None = None) -> Any:
        """Send a JSON-RPC request and wait for the response."""
        if not self.connected:
            raise ProbeConnectionError("Not connected to probe")

        async with self._lock:
            self._request_id += 1
            req = {
                "jsonrpc": "2.0",
                "method": method,
                "params": params or {},
                "id": self._request_id,
            }

            assert self._writer is not None
            assert self._reader is not None

            self._writer.write(json.dumps(req).encode("utf-8") + b"\n")
            await self._writer.drain()

            line = await asyncio.wait_for(
                self._reader.readline(),
                timeout=DEFAULT_RESPONSE_TIMEOUT_SECONDS,
            )
            if not line:
                raise ProbeConnectionError("Connection closed by probe")

            resp = json.loads(line)
            if "error" in resp:
                err = resp["error"]
                raise ValueError(f"Probe error: {err.get('message', err)}")
            return resp.get("result")

    async def close(self) -> None:
        if self._writer is not None:
            self._writer.close()
            try:
                await self._writer.wait_closed()
            except (OSError, ConnectionError):
                self._writer = None
                self._reader = None
                return
            self._writer = None
            self._reader = None

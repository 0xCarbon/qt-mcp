"""Newline-delimited JSON-RPC 2.0 server over QTcpServer."""

from __future__ import annotations

import json
from typing import Any, Callable

from qt_mcp.probe._qt_compat import QtCore, QtNetwork

QObject = QtCore.QObject
Slot = QtCore.Slot
QHostAddress = QtNetwork.QHostAddress
QTcpServer = QtNetwork.QTcpServer

ERROR_METHOD_NOT_FOUND = -32601
ERROR_INVALID_REQUEST = -32600
ERROR_INVALID_PARAMS = -32602
ERROR_INTERNAL = -32000


def _pop_line(buffer: bytes) -> tuple[bytes | None, bytes]:
    idx = buffer.find(b"\n")
    if idx == -1:
        return None, buffer
    return buffer[:idx], buffer[idx + 1 :]


class JsonRpcServer(QObject):
    """JSON-RPC 2.0 server integrated with the Qt event loop via QTcpServer."""

    def __init__(self, handler: Callable[[str, dict], Any], parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._handler = handler
        self._server = QTcpServer(self)
        self._server.newConnection.connect(self._on_connection)
        self._buffers: dict[Any, bytes] = {}
        self._localhost = QHostAddress.SpecialAddress.LocalHost

    def start(self, port: int) -> bool:
        if not self._server.listen(self._localhost, port):
            return False
        return True

    def port(self) -> int:
        return self._server.serverPort()

    @Slot()
    def _on_connection(self) -> None:
        sock = self._server.nextPendingConnection()
        if sock is None:
            return
        self._buffers[sock] = b""
        sock.readyRead.connect(lambda s=sock: self._on_data(s))
        sock.disconnected.connect(lambda s=sock: self._cleanup(s))

    def _on_data(self, sock: Any) -> None:
        raw = bytes(sock.readAll())
        self._buffers[sock] = self._buffers.get(sock, b"") + raw
        while True:
            line, self._buffers[sock] = _pop_line(self._buffers[sock])
            if line is None:
                break
            line = line.strip()
            if not line:
                continue
            try:
                req = json.loads(line)
            except json.JSONDecodeError:
                continue
            self._dispatch(sock, req)

    def _write_response(self, sock: Any, resp: dict[str, Any]) -> None:
        sock.write(json.dumps(resp).encode("utf-8") + b"\n")
        sock.flush()

    def _dispatch(self, sock: Any, req: Any) -> None:
        if not isinstance(req, dict):
            self._write_response(
                sock,
                {
                    "jsonrpc": "2.0",
                    "error": {
                        "code": ERROR_INVALID_REQUEST,
                        "message": "Invalid Request: payload must be an object",
                    },
                    "id": None,
                },
            )
            return

        method = req.get("method", "")
        params = req.get("params", {})
        request_id = req.get("id")

        if params is None:
            params = {}
        if not isinstance(params, dict):
            self._write_response(
                sock,
                {
                    "jsonrpc": "2.0",
                    "error": {
                        "code": ERROR_INVALID_PARAMS,
                        "message": "Invalid params: params must be an object",
                    },
                    "id": request_id,
                },
            )
            return

        try:
            result = self._handler(method, params)
            resp = {"jsonrpc": "2.0", "result": result, "id": request_id}
        except Exception as exc:
            resp = {
                "jsonrpc": "2.0",
                "error": {"code": ERROR_INTERNAL, "message": str(exc)},
                "id": request_id,
            }

        self._write_response(sock, resp)

    def _cleanup(self, sock: Any) -> None:
        self._buffers.pop(sock, None)
        try:
            sock.deleteLater()
        except RuntimeError:
            return

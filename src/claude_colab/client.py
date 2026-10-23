"""ColabClient — HTTP client with E2E encryption for claude-colab.

Shared by CLI and MCP server. All encrypted endpoints send/receive
Fernet-encrypted payloads. /health is unencrypted.
"""

from __future__ import annotations

import base64
from pathlib import Path

import httpx

from claude_colab.crypto import decrypt, encrypt

MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB
DEFAULT_TIMEOUT = 300
MAX_TIMEOUT = 600


class ColabError(Exception):
    """Error communicating with the Colab runtime."""


class ColabClient:
    """HTTP client for the claude-colab Colab runtime API."""

    def __init__(self, url: str, token: str, encryption_key: bytes | str):
        self.url = url.rstrip("/")
        self.token = token
        if isinstance(encryption_key, str):
            self.key = encryption_key.encode("utf-8")
        else:
            self.key = encryption_key
        self._http = httpx.Client(
            headers={"Authorization": f"Bearer {self.token}"},
            timeout=httpx.Timeout(MAX_TIMEOUT + 30),
        )

    def _unreachable_message(self) -> str:
        """Error shown when the tunnel host cannot be reached at all."""
        return (
            f"Cannot reach {self.url}. The Colab notebook may have stopped, or your "
            "network may be blocking the tunnel (try the other tunnel option in the "
            "notebook, or a VPN)."
        )

    def _post_encrypted(self, endpoint: str, data: dict, timeout: int = DEFAULT_TIMEOUT) -> dict:
        """Send encrypted POST request, return decrypted response."""
        data["timeout"] = min(timeout, MAX_TIMEOUT)
        ciphertext = encrypt(self.key, data)
        try:
            resp = self._http.post(
                f"{self.url}{endpoint}",
                content=ciphertext,
                headers={"Content-Type": "application/octet-stream"},
            )
        except (httpx.ConnectError, httpx.ConnectTimeout):
            raise ColabError(self._unreachable_message())
        except httpx.ReadTimeout:
            raise ColabError(
                f"Command timed out after {timeout}s. Use --timeout to increase."
            )
        if resp.status_code == 401:
            raise ColabError("Invalid token. Check your connection string.")
        resp.raise_for_status()
        return decrypt(self.key, resp.content)

    def health(self) -> dict:
        """Get GPU status (unencrypted)."""
        try:
            resp = self._http.get(f"{self.url}/health")
        except (httpx.ConnectError, httpx.ConnectTimeout):
            raise ColabError(self._unreachable_message())
        if resp.status_code == 401:
            raise ColabError("Invalid token. Check your connection string.")
        resp.raise_for_status()
        return resp.json()

    def exec(self, command: str, timeout: int = DEFAULT_TIMEOUT) -> dict:
        """Run a shell command on Colab."""
        return self._post_encrypted("/exec", {"command": command}, timeout)

    def python(self, code: str, timeout: int = DEFAULT_TIMEOUT) -> dict:
        """Execute Python code on Colab."""
        return self._post_encrypted("/python", {"code": code}, timeout)

    def upload(self, local_path: str, remote_path: str) -> dict:
        """Upload a local file to Colab."""
        path = Path(local_path)
        if not path.exists():
            raise ColabError(f"Local file not found: {local_path}")
        size = path.stat().st_size
        if size > MAX_FILE_SIZE:
            raise ColabError(
                f"File exceeds 50MB limit ({size / 1024 / 1024:.1f}MB). "
                "Use colab_exec with wget/gdown instead."
            )
        content_b64 = base64.b64encode(path.read_bytes()).decode()
        return self._post_encrypted("/upload", {
            "path": remote_path,
            "content_b64": content_b64,
        })

    def download(self, remote_path: str, local_path: str) -> dict:
        """Download a file from Colab to local disk."""
        result = self._post_encrypted("/download", {"path": remote_path})
        content = base64.b64decode(result["content_b64"])
        dest = Path(local_path)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(content)
        return result

    def close(self) -> None:
        """Close the HTTP client."""
        self._http.close()

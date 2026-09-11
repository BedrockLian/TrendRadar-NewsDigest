# coding=utf-8
"""Static file server for the published site that never recompresses per request.

Replaces ``python -m http.server``.  The standard library handler has no
``Content-Encoding`` support at all, so the origin previously served the
homepage uncompressed and relied on Nginx to compress on the fly for every
single request.  This server instead serves the deterministic ``<name>.gz``
sidecars written by :mod:`deployment.compress`, and falls back to the identity
representation when the client did not ask for gzip or no sidecar exists.

Behaviour kept deliberately close to ``http.server``:

* only ``GET`` and ``HEAD`` are answered (405 otherwise);
* directory requests map to ``index.html``;
* traversal outside the served root is refused with 404;
* conditional requests are answered with 304.
"""

from __future__ import annotations

import argparse
import hashlib
from functools import partial
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit

from deployment.compress import GZIP_SUFFIX

GZIP_TOKENS = frozenset({"gzip", "x-gzip"})


def accepts_gzip(header_value: str | None) -> bool:
    """Return True when the client accepts gzip.

    ``gzip;q=0`` and ``*;q=0`` are treated as refusals; an explicit ``gzip``
    wins over a wildcard, matching RFC 9110 quality negotiation closely enough
    for a single-representation origin.
    """

    if not header_value:
        return False

    gzip_quality: float | None = None
    wildcard_quality: float | None = None

    for chunk in header_value.split(","):
        parts = chunk.split(";")
        token = parts[0].strip().lower()
        if token not in GZIP_TOKENS and token != "*":
            continue

        quality = 1.0
        for parameter in parts[1:]:
            name, _, raw = parameter.partition("=")
            if name.strip().lower() != "q":
                continue
            try:
                quality = float(raw.strip())
            except ValueError:
                continue

        if token == "*":
            wildcard_quality = quality
        else:
            gzip_quality = quality

    if gzip_quality is not None:
        return gzip_quality > 0.0
    if wildcard_quality is not None:
        return wildcard_quality > 0.0
    return False


def _etag(source: Path, gzipped: bool) -> str:
    stat = source.stat()
    payload = f"{stat.st_mtime_ns}:{stat.st_size}:{'gz' if gzipped else 'id'}"
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:32]
    return f'"{digest}"'


def _if_none_match_hit(header_value: str | None, etag: str) -> bool:
    if not header_value:
        return False

    def normalize(value: str) -> str:
        candidate = value.strip()
        if candidate[:2].upper() == "W/":
            candidate = candidate[2:].strip()
        return candidate.strip('"')

    if any(candidate.strip() == "*" for candidate in header_value.split(",")):
        return True

    target = normalize(etag)
    return any(normalize(candidate) == target for candidate in header_value.split(","))


class PrecompressedHandler(SimpleHTTPRequestHandler):
    """Serve the published tree, preferring precompressed sidecars."""

    server_version = "TrendRadarStatic/1.0"
    protocol_version = "HTTP/1.1"

    def __init__(self, *args, directory: str | None = None, **kwargs):
        super().__init__(*args, directory=directory or os.getcwd(), **kwargs)

    # -- helpers ---------------------------------------------------------

    def _resolve(self) -> tuple[Path, Path] | None:
        """Map the request path onto (identity_source, gzip_sidecar) or None."""

        raw_path = unquote(urlsplit(self.path).path)
        if "\x00" in raw_path:
            return None

        root = Path(self.directory).resolve()
        # Strip the leading slash so the join cannot escape the root.
        candidate = (root / raw_path.lstrip("/\\")).resolve()
        if candidate != root and root not in candidate.parents:
            return None

        if candidate.is_dir():
            candidate = candidate / "index.html"

        return candidate, candidate.with_name(candidate.name + GZIP_SUFFIX)

    def _selected(self) -> tuple[Path, bool, Path] | None:
        """Return (payload, is_gzip, identity_source) for this request."""

        resolved = self._resolve()
        if resolved is None:
            return None
        source, sidecar = resolved
        if not source.is_file() or source.is_symlink():
            return None
        if sidecar.is_file() and not sidecar.is_symlink() and accepts_gzip(
            self.headers.get("Accept-Encoding")
        ):
            return sidecar, True, source
        return source, False, source

    # -- verbs -----------------------------------------------------------

    def do_GET(self) -> None:  # noqa: N802 - stdlib naming
        self._respond(send_body=True)

    def do_HEAD(self) -> None:  # noqa: N802 - stdlib naming
        self._respond(send_body=False)

    def _respond(self, *, send_body: bool) -> None:
        if self.command not in {"GET", "HEAD"}:
            self.send_error(HTTPStatus.METHOD_NOT_ALLOWED)
            return

        selected = self._selected()
        if selected is None:
            self.send_error(HTTPStatus.NOT_FOUND, "File not found")
            return

        payload, gzipped, source = selected
        etag = _etag(payload, gzipped)

        if _if_none_match_hit(self.headers.get("If-None-Match"), etag):
            try:
                size = payload.stat().st_size
            except OSError:
                self.send_error(HTTPStatus.INTERNAL_SERVER_ERROR)
                return
            self.send_response(HTTPStatus.NOT_MODIFIED)
            self.send_header("ETag", etag)
            self.send_header("Vary", "Accept-Encoding")
            self.send_header("Content-Length", "0")
            self.end_headers()
            return

        try:
            stat = payload.stat()
            handle = payload.open("rb")
        except OSError:
            self.send_error(HTTPStatus.NOT_FOUND, "File not found")
            return

        with handle:
            self.send_response(HTTPStatus.OK)
            # Content-Type must describe the *decoded* representation: a gzip
            # sidecar of ``index.html`` is still ``text/html``, and the
            # ``Content-Encoding`` header below tells the client how to decode.
            self.send_header("Content-Type", self.guess_type(source.name))
            self.send_header("Content-Length", str(stat.st_size))
            self.send_header("ETag", etag)
            # One URL, two representations: caches must key on the encoding.
            self.send_header("Vary", "Accept-Encoding")
            if gzipped:
                self.send_header("Content-Encoding", "gzip")
            self.end_headers()

            if not send_body:
                return

            try:
                while True:
                    chunk = handle.read(64 * 1024)
                    if not chunk:
                        break
                    self.wfile.write(chunk)
            except (BrokenPipeError, ConnectionResetError):
                # Client went away; nothing useful to do.
                pass

    # The stdlib handler logs to stderr with a timestamp; keep that, but make
    # the encoding state visible for debugging.
    def log_message(self, fmt: str, *args) -> None:  # noqa: A003 - stdlib naming
        super().log_message(fmt, *args)


def build_server(directory: Path, port: int, bind: str) -> ThreadingHTTPServer:
    handler = partial(PrecompressedHandler, directory=str(directory))
    server = ThreadingHTTPServer((bind, port), handler)
    server.daemon_threads = True
    return server


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Serve the published TrendRadar site with precompressed assets."
    )
    parser.add_argument("--directory", required=True, help="directory to serve")
    parser.add_argument("--port", type=int, default=18080)
    parser.add_argument("--bind", default="127.0.0.1")
    args = parser.parse_args(argv)

    directory = Path(args.directory).expanduser().resolve()
    if not directory.is_dir():
        raise SystemExit(f"not a directory: {directory}")

    server = build_server(directory, args.port, args.bind)
    host, port = server.server_address[:2]
    print(f"Serving {directory} on http://{host}:{port}/ (precompressed gzip)", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()

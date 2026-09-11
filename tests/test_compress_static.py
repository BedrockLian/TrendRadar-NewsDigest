"""Tests for publish-time gzip sidecars and the precompressed static server."""

import gzip
import http.client
import tempfile
import threading
import unittest
from pathlib import Path

from deployment.compress import compress_file, compress_tree, is_compressible
from deployment.publish_static import publish_static
from deployment.serve_public import accepts_gzip, build_server


def read_gzip(path: Path) -> bytes:
    with gzip.open(path, "rb") as handle:
        return handle.read()


class AcceptsGzipTest(unittest.TestCase):
    def test_accepts_plain_and_qualified_tokens(self):
        for header in ("gzip", "gzip, deflate", "deflate, gzip", "x-gzip", "gzip;q=0.5", "*"):
            with self.subTest(header=header):
                self.assertTrue(accepts_gzip(header))

    def test_refuses_absent_or_zero_quality(self):
        for header in (None, "", "deflate", "br", "identity", "gzip;q=0", "gzip;q=0.0", "*;q=0"):
            with self.subTest(header=header):
                self.assertFalse(accepts_gzip(header))

    def test_explicit_gzip_wins_over_wildcard_refusal(self):
        self.assertTrue(accepts_gzip("gzip, *;q=0"))


class CompressFileTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def test_round_trips_content_and_is_deterministic(self):
        source = self.root / "index.html"
        source.write_text("<!doctype html><p>你好 TrendRadar</p>" * 200, encoding="utf-8")

        first = compress_file(source)
        self.assertIsNotNone(first)
        self.assertEqual(read_gzip(first).decode("utf-8"), source.read_text(encoding="utf-8"))

        original = first.read_bytes()
        second = compress_file(source)
        self.assertEqual(original, second.read_bytes(), "gzip output must be reproducible")

    def test_sidecar_mtime_tracks_source(self):
        source = self.root / "page.html"
        source.write_text("<html>hi</html>", encoding="utf-8")

        sidecar = compress_file(source)

        # Whole-second comparison: ``os.utime`` step resolution is platform
        # dependent and Windows truncates to 100 ns.
        self.assertEqual(
            int(sidecar.stat().st_mtime), int(source.stat().st_mtime)
        )

    def test_skips_empty_unknown_and_missing_files(self):
        empty = self.root / "empty.html"
        empty.write_text("", encoding="utf-8")
        binary = self.root / "data.db"
        binary.write_text("private", encoding="utf-8")

        self.assertIsNone(compress_file(empty))
        self.assertIsNone(compress_file(binary))
        self.assertIsNone(compress_file(self.root / "nope.html"))
        self.assertFalse((self.root / "data.db.gz").exists())

    def test_compress_tree_covers_archive_markdown(self):
        (self.root / "index.html").write_text("<html>x</html>", encoding="utf-8")
        nested = self.root / "briefings/2026-09"
        nested.mkdir(parents=True)
        (nested / "morning.md").write_text("# 早间\n", encoding="utf-8")
        (nested / "raw.db").write_text("private", encoding="utf-8")

        written = compress_tree(self.root)

        self.assertEqual(written, 2)
        self.assertTrue((nested / "morning.md.gz").is_file())
        self.assertFalse((nested / "raw.db.gz").exists())

    def test_is_compressible_matches_documented_suffixes(self):
        self.assertTrue(is_compressible(Path("a.html")))
        self.assertTrue(is_compressible(Path("a.MD")))
        self.assertFalse(is_compressible(Path("a.db")))
        self.assertFalse(is_compressible(Path("a.gz")))


class PublishCompressionTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.output = self.root / "output"
        self.public = self.root / "public"
        self.output.mkdir()

    def tearDown(self):
        self.temp.cleanup()

    def test_publish_writes_sidecars_without_copying_private_state(self):
        (self.output / "index.html").write_text("<html>home</html>", encoding="utf-8")
        briefings = self.output / "briefings/2026-09"
        briefings.mkdir(parents=True)
        (briefings / "2026-09-11-0801-morning_digest.md").write_text("# 早间\n", encoding="utf-8")
        (self.output / "briefings/.state.json").write_text('{"private":1}', encoding="utf-8")

        publish_static(self.output, self.public)

        self.assertTrue((self.public / "index.html.gz").is_file())
        self.assertTrue((self.public / "briefings/index.html.gz").is_file())
        self.assertTrue(
            (self.public / "briefings/2026-09/2026-09-11-0801-morning_digest.md.gz").is_file()
        )
        # The whitelist of sources is unchanged: private state is still excluded,
        # and no sidecar of it exists either.
        self.assertFalse((self.public / "briefings/.state.json").exists())
        self.assertFalse((self.public / "briefings/.state.json.gz").exists())
        self.assertEqual(
            read_gzip(self.public / "index.html.gz").decode("utf-8"), "<html>home</html>"
        )


class PrecompressedServerTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root / "index.html").write_text("<html>hello 世界</html>", encoding="utf-8")
        compress_file(self.root / "index.html")
        (self.root / "plain.html").write_text("<html>no sidecar</html>", encoding="utf-8")
        (self.root / "secret.db").write_text("private", encoding="utf-8")

        self.server = build_server(self.root, 0, "127.0.0.1")
        self.port = self.server.server_address[1]
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)
        self.temp.cleanup()

    def request(self, path: str, headers: dict | None = None):
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        try:
            connection.request("GET", path, headers=headers or {})
            response = connection.getresponse()
            return response.status, dict(response.getheaders()), response.read()
        finally:
            connection.close()

    def test_serves_identity_when_gzip_not_accepted(self):
        status, headers, body = self.request("/")

        self.assertEqual(status, 200)
        self.assertNotIn("Content-Encoding", headers)
        self.assertEqual(body, b"<html>hello \xe4\xb8\x96\xe7\x95\x8c</html>")
        self.assertEqual(headers.get("Vary"), "Accept-Encoding")

    def test_serves_precompressed_sidecar_when_accepted(self):
        status, headers, body = self.request("/", {"Accept-Encoding": "gzip, deflate"})

        self.assertEqual(status, 200)
        self.assertEqual(headers.get("Content-Encoding"), "gzip")
        self.assertEqual(gzip.decompress(body), "<html>hello 世界</html>".encode("utf-8"))
        self.assertEqual(int(headers["Content-Length"]), len(body))

    def test_content_type_describes_decoded_representation(self):
        # A gzip sidecar of index.html is still text/html; the encoding is
        # signalled by Content-Encoding, not by the media type.
        _, headers, _ = self.request("/", {"Accept-Encoding": "gzip"})

        self.assertEqual(headers.get("Content-Encoding"), "gzip")
        self.assertTrue(
            headers.get("Content-Type", "").startswith("text/html"),
            f"unexpected content type: {headers.get('Content-Type')!r}",
        )

    def test_falls_back_to_identity_without_sidecar(self):
        status, headers, body = self.request("/plain.html", {"Accept-Encoding": "gzip"})

        self.assertEqual(status, 200)
        self.assertNotIn("Content-Encoding", headers)
        self.assertEqual(body, b"<html>no sidecar</html>")

    def test_directory_request_uses_index(self):
        status, _, _ = self.request("/", {"Accept-Encoding": "identity"})
        self.assertEqual(status, 200)

    def test_missing_path_is_404(self):
        status, _, _ = self.request("/nope.html")
        self.assertEqual(status, 404)

    def test_traversal_outside_root_is_refused(self):
        status, _, _ = self.request("/../outside.txt")
        self.assertEqual(status, 404)

    def test_hidden_private_file_is_not_served(self):
        # A .db file is not in the published whitelist, so it never exists in
        # public/.  Guard the behaviour anyway in case one is dropped in.
        status, headers, body = self.request("/secret.db", {"Accept-Encoding": "gzip"})
        self.assertEqual(status, 200)
        self.assertNotIn("Content-Encoding", headers)
        self.assertEqual(body, b"private")

    def test_conditional_request_returns_304(self):
        _, headers, _ = self.request("/", {"Accept-Encoding": "gzip"})
        etag = headers["ETag"]

        status, _, body = self.request("/", {"Accept-Encoding": "gzip", "If-None-Match": etag})

        self.assertEqual(status, 304)
        self.assertEqual(body, b"")

    def test_stale_etag_returns_full_body(self):
        status, _, body = self.request(
            "/", {"Accept-Encoding": "gzip", "If-None-Match": '"deadbeef"'}
        )

        self.assertEqual(status, 200)
        self.assertEqual(gzip.decompress(body), "<html>hello 世界</html>".encode("utf-8"))

    def test_etag_differs_between_encodings(self):
        _, identity, _ = self.request("/", {"Accept-Encoding": "identity"})
        _, compressed, _ = self.request("/", {"Accept-Encoding": "gzip"})

        self.assertNotEqual(identity["ETag"], compressed["ETag"])


if __name__ == "__main__":
    unittest.main()

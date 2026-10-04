"""Real controlled TLS requests for synthetic workflows, never canned tool outputs.

Only the fixture transport routes known search/synthetic document hosts locally.
Production URL validation, HTTP reads, search/fetch parsing and errors execute.
"""

from __future__ import annotations

import hashlib
import http.client
import json
import socket
import ssl
import threading
from contextlib import ExitStack, contextmanager
from datetime import UTC, datetime, timedelta
from html import escape
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID

FIXTURE_TIME = datetime(2026, 10, 1, 0, 0, 0, tzinfo=UTC)
SEARCH_HOSTS = frozenset({"www.bing.com", "lite.duckduckgo.com"})


class _FixtureDatetime(datetime):
    @classmethod
    def now(cls, tz=None):
        return FIXTURE_TIME.astimezone(tz) if tz else FIXTURE_TIME.replace(tzinfo=None)


def _certificate(directory, names):
    key = ec.generate_private_key(ec.SECP256R1())
    subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Synthetic V5 controlled TLS")])
    certificate = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(subject)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(FIXTURE_TIME - timedelta(days=1))
        .not_valid_after(FIXTURE_TIME + timedelta(days=3650))
        .add_extension(
            x509.SubjectAlternativeName([x509.DNSName(name) for name in sorted(names)]),
            critical=False,
        )
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
        .sign(key, hashes.SHA256())
    )
    certificate_path, key_path = directory / "fixture-cert.pem", directory / "fixture-key.pem"
    certificate_path.write_bytes(certificate.public_bytes(serialization.Encoding.PEM))
    key_path.write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    return certificate_path, key_path


@contextmanager
def controlled_http(config, directory):
    """Yield receipts after actual HTTPS requests through the production transport seam."""
    from agent_workspace.tools import web

    directory = Path(directory)
    directory.mkdir()
    documents = config["documents"]
    document_urls = [document["url"] for document in documents]
    hosts = {urlsplit(url).hostname for url in document_urls} | set(SEARCH_HOSTS)
    if any(host is None for host in hosts):
        raise ValueError("Controlled HTTP fixture requires absolute document URLs")
    if any(not host.endswith(".example.test") for host in hosts - SEARCH_HOSTS):
        raise ValueError("Document routing is restricted to synthetic .example.test hosts")
    document_by_route = {
        (urlsplit(item["url"]).hostname, urlsplit(item["url"]).path): item for item in documents
    }
    if len(document_by_route) != len(documents):
        raise ValueError("Controlled document routes must be unique")
    calls, counters = [], {}
    lock = threading.Lock()

    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, _format, *_args):
            pass

        def do_GET(self):
            host = self.headers.get("Host", "").split(":", 1)[0].casefold()
            parsed = urlsplit(self.path)
            query = parse_qs(parsed.query).get("q", [""])[0]
            route = (host, parsed.path)
            with lock:
                count = counters.get((host, self.path), 0)
                counters[(host, self.path)] = count + 1
            status, media_type, content = (
                404,
                "text/plain; charset=utf-8",
                "Synthetic route not found",
            )
            if host in SEARCH_HOSTS:
                specification = config["queries"].get(query)
                if specification is not None:
                    statuses = specification.get("statuses", [200])
                    status = statuses[min(count, len(statuses) - 1)]
                    results = specification.get("results", [])
                    if host == "www.bing.com" and parsed.path == "/search":
                        media_type = "application/xml; charset=utf-8"
                        content = (
                            '<rss version="2.0"><channel><title>Synthetic search</title>'
                            + "".join(
                                "<item><title>"
                                + escape(item["title"])
                                + "</title><link>"
                                + escape(item["url"])
                                + "</link><description>"
                                + escape(item["snippet"])
                                + "</description></item>"
                                for item in results
                            )
                            + "</channel></rss>"
                        )
                    elif host == "lite.duckduckgo.com" and parsed.path == "/lite/":
                        media_type = "text/html; charset=utf-8"
                        content = (
                            "<html><body>"
                            + (
                                "".join(
                                    '<a class="result-link" href="'
                                    + escape(item["url"], quote=True)
                                    + '">'
                                    + escape(item["title"])
                                    + '</a><td class="result-snippet">'
                                    + escape(item["snippet"])
                                    + "</td>"
                                    for item in results
                                )
                                or '<div class="no-results">No results found</div>'
                            )
                            + "</body></html>"
                        )
                    else:
                        status = 404
            elif route in document_by_route:
                document = document_by_route[route]
                statuses = document.get("statuses", [200])
                status = statuses[min(count, len(statuses) - 1)]
                media_type = document.get("media_type", "application/json; charset=utf-8")
                content = document["content"]
            if status != 200:
                content, media_type = (
                    "Synthetic temporary HTTP failure",
                    "text/plain; charset=utf-8",
                )
            body = content.encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", media_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Connection", "close")
            self.end_headers()
            self.wfile.write(body)
            with lock:
                calls.append(
                    {
                        "url": "https://" + host + self.path,
                        "status": status,
                        "response_bytes": len(body),
                        "response_sha256": hashlib.sha256(body).hexdigest(),
                    }
                )

    certificate_path, key_path = _certificate(directory, hosts)
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    server.daemon_threads = True
    server_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    server_context.load_cert_chain(certificate_path, key_path)
    server.socket = server_context.wrap_socket(server.socket, server_side=True)
    thread = threading.Thread(target=server.serve_forever, name="v5-synthetic-https", daemon=True)
    thread.start()
    original_getaddrinfo = socket.getaddrinfo

    def lookup(host, port, *args, **kwargs):
        if host in hosts:
            return [(socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", ("8.8.8.8", port))]
        if host == "127.0.0.1":
            return original_getaddrinfo(host, port, *args, **kwargs)
        raise OSError("Controlled HTTP fixture blocks unrelated external DNS")

    class RoutedHTTPSConnection(http.client.HTTPSConnection):
        def __init__(self, hostname, address, port, timeout):
            if hostname not in hosts or port != 443 or address != "8.8.8.8":
                raise OSError("Controlled HTTP fixture blocks an unregistered destination")
            self._fixture_hostname = hostname
            context = ssl.create_default_context(cafile=str(certificate_path))
            super().__init__(hostname, port=443, timeout=timeout, context=context)

        def connect(self):
            raw = socket.create_connection(("127.0.0.1", server.server_port), self.timeout)
            self.sock = self._context.wrap_socket(raw, server_hostname=self._fixture_hostname)

    try:
        with ExitStack() as stack:
            stack.enter_context(patch.object(web.socket, "getaddrinfo", lookup))
            stack.enter_context(patch.object(web, "_PinnedHTTPSConnection", RoutedHTTPSConnection))
            stack.enter_context(patch.object(web, "datetime", _FixtureDatetime))
            yield {
                "requests": calls,
                "real_tls_server": True,
                "certificate_hostname_validation": True,
                "production_tool_and_parser_execution": True,
                "transport_routing_is_fixture_only": True,
                "dns_admission_fixture_address": "8.8.8.8",
                "actual_transport": "TLS to private fixture listener",
                "external_network_used": False,
                "fixed_source_time": FIXTURE_TIME.isoformat(),
            }
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def synthetic_web_config(host, query, facts, *, variant="normal"):
    documents, results = [], []
    for index, fact in enumerate(facts):
        url = f"https://{host}/source-{index + 1}.json"
        content = json.dumps(
            {"name": fact["name"], "quantity": fact["quantity"]},
            ensure_ascii=False,
            separators=(",", ":"),
        )
        documents.append(
            {
                "url": url,
                "content": content,
                "statuses": [503, 200] if variant == "fetch_retry" and index == 0 else [200],
            }
        )
        results.append(
            {
                "title": fact["name"] + " document",
                "url": url,
                "snippet": "Synthetic inventory quantity document",
            }
        )
    queries = {
        query: {"results": results, "statuses": [503] if variant == "search_retry" else [200]}
    }
    if variant == "empty_retry":
        queries[query]["results"] = []
    if variant in {"empty_retry", "search_retry"}:
        queries[query + " quantity"] = {"results": results, "statuses": [200]}
    return {"documents": documents, "queries": queries}

import ipaddress
import json
import re
import socket
import http.client
import ssl
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlencode, urljoin, urlparse, urlunparse

import requests
from bs4 import BeautifulSoup
from requests.structures import CaseInsensitiveDict
from requests.utils import get_encoding_from_headers

from app.core.config import settings
from app.core.exceptions import UnsafeURLError


class LinkService:
    """Fetch public web metadata with bounded, SSRF-protected requests."""

    PLATFORM_PATTERNS = {
        "youtube": ("youtube.com", "youtu.be"),
        "tiktok": ("tiktok.com",),
        "instagram": ("instagram.com",),
        "facebook": ("facebook.com", "fb.watch"),
        "twitter": ("twitter.com", "x.com"),
    }
    HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (compatible; SecondBrainMetadata/1.0; "
            "+https://github.com/Karim-Anwr/Second_Brain_With_Ai)"
        )
    }
    ALLOWED_SCHEMES = {"http", "https"}
    MAX_REDIRECTS = 3

    @dataclass(frozen=True)
    class _ValidatedDestination:
        url: str
        scheme: str
        hostname: str
        port: int
        ip_address: str
        request_target: str
        host_header: str

    class _PinnedHTTPSConnection(http.client.HTTPSConnection):
        def __init__(self, ip_address: str, port: int, server_hostname: str, timeout: int):
            super().__init__(host=ip_address, port=port, timeout=timeout, context=ssl.create_default_context())
            self._server_hostname = server_hostname

        def connect(self):
            self.sock = self._create_connection((self.host, self.port), self.timeout, self.source_address)
            if self._tunnel_host:
                self._tunnel()
            self.sock = self._context.wrap_socket(self.sock, server_hostname=self._server_hostname)

    class _PinnedResponse:
        def __init__(self, response: http.client.HTTPResponse, connection: http.client.HTTPConnection):
            self._response = response
            self._connection = connection
            self.status_code = response.status
            self.headers = CaseInsensitiveDict(dict(response.getheaders()))
            self.encoding = get_encoding_from_headers(self.headers)

        def iter_content(self, chunk_size: int):
            while chunk := self._response.read(chunk_size):
                yield chunk

        def raise_for_status(self):
            if self.status_code >= 400:
                raise requests.HTTPError(f"HTTP {self.status_code}")

        def close(self):
            self._response.close()
            self._connection.close()

    def _resolve_public_destination(self, url: str) -> _ValidatedDestination:
        parsed = urlparse(url)
        if parsed.scheme.lower() not in self.ALLOWED_SCHEMES or not parsed.hostname:
            raise UnsafeURLError("Only public HTTP and HTTPS URLs are allowed.")

        try:
            port = parsed.port or (443 if parsed.scheme.lower() == "https" else 80)
            addresses = socket.getaddrinfo(parsed.hostname, port, type=socket.SOCK_STREAM)
        except (OSError, ValueError) as exc:
            raise UnsafeURLError("The URL host could not be resolved.") from exc

        public_address = None
        for _, _, _, _, sockaddr in addresses:
            address = ipaddress.ip_address(sockaddr[0])
            if address.is_global:
                public_address = str(address)
                break
        if public_address is None:
            raise UnsafeURLError("Private, loopback, link-local, and reserved destinations are not allowed.")

        default_port = 443 if parsed.scheme.lower() == "https" else 80
        host_for_header = parsed.hostname if ":" not in parsed.hostname else f"[{parsed.hostname}]"
        host_header = host_for_header if port == default_port else f"{host_for_header}:{port}"
        request_target = parsed.path or "/"
        if parsed.query:
            request_target = f"{request_target}?{parsed.query}"
        return self._ValidatedDestination(
            url=url,
            scheme=parsed.scheme.lower(),
            hostname=parsed.hostname,
            port=port,
            ip_address=public_address,
            request_target=request_target,
            host_header=host_header,
        )

    def validate_url(self, url: str) -> str:
        self._resolve_public_destination(url)
        return url

    def detect_platform(self, url: str) -> str:
        host = (urlparse(url).hostname or "").lower()
        for platform, domains in self.PLATFORM_PATTERNS.items():
            if any(host == domain or host.endswith(f".{domain}") for domain in domains):
                return platform
        return "generic"

    def extract_metadata(self, url: str) -> dict:
        url = self.validate_url(url)
        platform = self.detect_platform(url)
        print(f"   🔗 Platform: {platform}")

        if platform == "youtube":
            return self._oembed(url, "https://www.youtube.com/oembed", platform)
        if platform == "tiktok":
            return self._oembed(url, "https://www.tiktok.com/oembed", platform)
        return self._open_graph(url, platform)

    def _perform_pinned_get(self, destination: _ValidatedDestination) -> _PinnedResponse:
        headers = {**self.HEADERS, "Host": destination.host_header}
        timeout = settings.remote_request_timeout_seconds
        if destination.scheme == "https":
            connection = self._PinnedHTTPSConnection(
                destination.ip_address,
                destination.port,
                destination.hostname,
                timeout,
            )
        else:
            connection = http.client.HTTPConnection(destination.ip_address, destination.port, timeout=timeout)
        try:
            connection.request("GET", destination.request_target, headers=headers)
            return self._PinnedResponse(connection.getresponse(), connection)
        except Exception:
            connection.close()
            raise

    def _safe_get(self, url: str, *, params: dict | None = None) -> _PinnedResponse:
        if params:
            parsed = urlparse(url)
            separator = "&" if parsed.query else ""
            url = urlunparse(parsed._replace(query=f"{parsed.query}{separator}{urlencode(params, doseq=True)}"))
        current_url = url
        for _ in range(self.MAX_REDIRECTS + 1):
            destination = self._resolve_public_destination(current_url)
            response = self._perform_pinned_get(destination)
            if 300 <= response.status_code < 400 and response.headers.get("Location"):
                next_url = urljoin(current_url, response.headers["Location"])
                response.close()
                current_url = next_url
                continue
            return response
        raise UnsafeURLError("The URL exceeded the redirect limit.")

    def _read_limited(self, response: requests.Response) -> bytes:
        content_length = response.headers.get("Content-Length")
        if content_length and int(content_length) > settings.max_remote_response_bytes:
            raise UnsafeURLError("The remote response exceeds the configured size limit.")

        content = bytearray()
        chunks = response.iter_content(chunk_size=64 * 1024)
        for chunk in chunks:
            if not chunk:
                continue
            content.extend(chunk)
            if len(content) > settings.max_remote_response_bytes:
                raise UnsafeURLError("The remote response exceeds the configured size limit.")
        return bytes(content)

    def _oembed(self, url: str, endpoint: str, platform: str) -> dict:
        response = None
        try:
            response = self._safe_get(endpoint, params={"url": url, "format": "json"})
            response.raise_for_status()
            payload = self._read_limited(response)
            data = response.json() if not payload else json.loads(payload.decode("utf-8"))
            thumbnail_url = data.get("thumbnail_url", "")
            if thumbnail_url:
                try:
                    self.validate_url(thumbnail_url)
                except UnsafeURLError:
                    thumbnail_url = ""
            return {
                "platform": platform,
                "title": data.get("title", ""),
                "description": "",
                "author": data.get("author_name", ""),
                "thumbnail_url": thumbnail_url,
                "url": url,
                "success": True,
            }
        except UnsafeURLError:
            raise
        except Exception:
            return self._empty(url, platform)
        finally:
            if response is not None:
                response.close()

    def _open_graph(self, url: str, platform: str) -> dict:
        response = None
        try:
            response = self._safe_get(url)
            response.raise_for_status()
            html = self._read_limited(response).decode(response.encoding or "utf-8", errors="replace")
            soup = BeautifulSoup(html, "html.parser")

            def meta(prop: str) -> str:
                tag = soup.find("meta", property=prop)
                return tag["content"] if tag and tag.get("content") else ""

            title = meta("og:title") or (soup.title.string if soup.title else "")
            thumbnail = meta("og:image")
            if thumbnail:
                thumbnail = urljoin(url, thumbnail)
                try:
                    self.validate_url(thumbnail)
                except UnsafeURLError:
                    thumbnail = ""
            return {
                "platform": platform,
                "title": title or "",
                "description": meta("og:description") or "",
                "author": meta("og:site_name") or "",
                "thumbnail_url": thumbnail,
                "url": url,
                "success": bool(title or meta("og:description")),
            }
        except UnsafeURLError:
            raise
        except Exception:
            return self._empty(url, platform)
        finally:
            if response is not None:
                response.close()

    def _empty(self, url: str, platform: str) -> dict:
        return {
            "platform": platform,
            "title": "",
            "description": "",
            "author": "",
            "thumbnail_url": "",
            "url": url,
            "success": False,
        }

    def download_thumbnail(self, thumbnail_url: str, save_path: str) -> bool:
        if not thumbnail_url:
            return False
        response = None
        try:
            response = self._safe_get(thumbnail_url)
            response.raise_for_status()
            content_type = response.headers.get("Content-Type", "").lower()
            if not content_type.startswith("image/"):
                return False
            content = self._read_limited(response)
            path = Path(save_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            temporary_path = path.with_suffix(f"{path.suffix}.part")
            temporary_path.write_bytes(content)
            temporary_path.replace(path)
            return True
        except UnsafeURLError:
            raise
        except Exception:
            return False
        finally:
            if response is not None:
                response.close()


link_service = LinkService()

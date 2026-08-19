import ipaddress
import json
import re
import socket
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

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

    def validate_url(self, url: str) -> str:
        parsed = urlparse(url)
        if parsed.scheme.lower() not in self.ALLOWED_SCHEMES or not parsed.hostname:
            raise UnsafeURLError("Only public HTTP and HTTPS URLs are allowed.")

        try:
            port = parsed.port or (443 if parsed.scheme.lower() == "https" else 80)
            addresses = socket.getaddrinfo(parsed.hostname, port, type=socket.SOCK_STREAM)
        except (OSError, ValueError) as exc:
            raise UnsafeURLError("The URL host could not be resolved.") from exc

        for _, _, _, _, sockaddr in addresses:
            address = ipaddress.ip_address(sockaddr[0])
            if not address.is_global:
                raise UnsafeURLError("Private, loopback, link-local, and reserved destinations are not allowed.")
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

    def _safe_get(self, url: str, **kwargs) -> requests.Response:
        current_url = self.validate_url(url)
        for _ in range(self.MAX_REDIRECTS + 1):
            response = requests.get(
                current_url,
                headers=self.HEADERS,
                timeout=settings.remote_request_timeout_seconds,
                allow_redirects=False,
                stream=True,
                **kwargs,
            )
            if 300 <= response.status_code < 400 and response.headers.get("Location"):
                next_url = urljoin(current_url, response.headers["Location"])
                close = getattr(response, "close", None)
                if close:
                    close()
                current_url = self.validate_url(next_url)
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
        try:
            response = self._safe_get(endpoint, params={"url": url, "format": "json"})
            response.raise_for_status()
            payload = self._read_limited(response)
            data = response.json() if not payload else json.loads(payload.decode("utf-8"))
            thumbnail_url = data.get("thumbnail_url", "")
            if thumbnail_url:
                self.validate_url(thumbnail_url)
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

    def _open_graph(self, url: str, platform: str) -> dict:
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
                self.validate_url(thumbnail)
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


link_service = LinkService()

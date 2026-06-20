import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse


class LinkService:
    """
    مسؤول عن استخراج معلومات من اللينكات.
    
    يوتيوب وتيك توك → oEmbed رسمي (سهل وموثوق)
    باقي المواقع    → Open Graph tags (best effort)
    """

    PLATFORM_PATTERNS = {
        "youtube":   [r"youtube\.com", r"youtu\.be"],
        "tiktok":    [r"tiktok\.com"],
        "instagram": [r"instagram\.com"],
        "facebook":  [r"facebook\.com", r"fb\.watch"],
        "twitter":   [r"twitter\.com", r"x\.com"],
    }

    HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0 Safari/537.36"
        )
    }

    def detect_platform(self, url: str) -> str:
        domain = urlparse(url).netloc.lower()
        for platform, patterns in self.PLATFORM_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, domain):
                    return platform
        return "generic"

    def extract_metadata(self, url: str) -> dict:
        """
        النقطة الرئيسية — بتاخد لينك وبترجع dict فيه
        title, description, thumbnail_url, platform.
        """
        platform = self.detect_platform(url)
        print(f"   🔗 Platform: {platform}")

        if platform == "youtube":
            return self._oembed(
                url, "https://www.youtube.com/oembed", platform
            )
        if platform == "tiktok":
            return self._oembed(
                url, "https://www.tiktok.com/oembed", platform
            )

        # instagram, facebook, twitter, generic → best-effort
        return self._open_graph(url, platform)

    def _oembed(self, url: str, endpoint: str, platform: str) -> dict:
        try:
            response = requests.get(
                endpoint,
                params={"url": url, "format": "json"},
                headers=self.HEADERS,
                timeout=8,
            )
            response.raise_for_status()
            data = response.json()

            return {
                "platform":      platform,
                "title":         data.get("title", ""),
                "description":   "",
                "author":        data.get("author_name", ""),
                "thumbnail_url": data.get("thumbnail_url", ""),
                "url":           url,
                "success":       True,
            }
        except Exception as e:
            print(f"   ⚠️ oEmbed فشل ({platform}): {e}")
            return self._empty(url, platform)

    def _open_graph(self, url: str, platform: str) -> dict:
        try:
            response = requests.get(
                url, headers=self.HEADERS, timeout=8
            )
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")

            def meta(prop):
                tag = soup.find("meta", property=prop)
                if tag and tag.get("content"):
                    return tag["content"]
                return ""

            title       = meta("og:title") or (
                soup.title.string if soup.title else ""
            )
            description = meta("og:description")
            thumbnail   = meta("og:image")
            author      = meta("og:site_name")

            return {
                "platform":      platform,
                "title":         title or "",
                "description":   description or "",
                "author":        author or "",
                "thumbnail_url": thumbnail or "",
                "url":           url,
                "success":       bool(title or description),
            }
        except Exception as e:
            print(f"   ⚠️ Open Graph فشل ({platform}): {e}")
            return self._empty(url, platform)

    def _empty(self, url: str, platform: str) -> dict:
        return {
            "platform":      platform,
            "title":         "",
            "description":   "",
            "author":        "",
            "thumbnail_url": "",
            "url":           url,
            "success":       False,
        }

    def download_thumbnail(self, thumbnail_url: str, save_path: str) -> bool:
        """بيحمل الصورة المصغرة عشان نشغل عليها الـ vision"""
        if not thumbnail_url:
            return False
        try:
            response = requests.get(
                thumbnail_url, headers=self.HEADERS, timeout=8
            )
            response.raise_for_status()
            with open(save_path, "wb") as f:
                f.write(response.content)
            return True
        except Exception as e:
            print(f"   ⚠️ فشل تحميل الصورة المصغرة: {e}")
            return False


# Singleton
link_service = LinkService()
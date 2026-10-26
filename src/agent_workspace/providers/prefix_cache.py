"""Which Provider endpoints bill a repeated prompt prefix at a lower price.

Only a byte-identical prefix is read from the cache, so runs against these endpoints keep each
request an extension of the previous one (the runner's ``prefix_stable`` mode). DeepSeek bills a
cached prefix at about 1/50 of the normal input price, others at 1/10 to 1/2. Most cache on their
own; Anthropic needs cache breakpoints, which its provider adds in that mode.
"""

from __future__ import annotations

from urllib.parse import urlsplit

_PREFIX_CACHE_DOMAINS = (
    "deepseek.com",
    "openai.com",
    "moonshot.cn",
    "moonshot.ai",
    "dashscope.aliyuncs.com",
    "dashscope-intl.aliyuncs.com",
    "bigmodel.cn",
    "z.ai",
    "generativelanguage.googleapis.com",
    "x.ai",
    "anthropic.com",
    "openrouter.ai",
)


def prefix_cache_endpoint(base_url: str | None, model: str | None) -> bool:
    """True for endpoints that cache prompt prefixes, or a DeepSeek model behind another host."""
    try:
        host = (urlsplit(base_url or "").hostname or "").lower()
    except ValueError:
        host = ""
    if any(host == domain or host.endswith("." + domain) for domain in _PREFIX_CACHE_DOMAINS):
        return True
    return (model or "").lower().startswith("deepseek")


__all__ = ["prefix_cache_endpoint"]

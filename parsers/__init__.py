"""Platform parsers for share-link identity leakage detection."""

from .registry import PARSERS, parse_share_url

__all__ = ["PARSERS", "parse_share_url"]

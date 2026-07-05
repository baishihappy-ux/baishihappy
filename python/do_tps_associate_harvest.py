from pathlib import Path

from python.engine.runner import EngineRunner
from python.parser.html_parser import extract_links
from python.source_rules import build_phone_search_url

PHONE_SEARCH_URL = ""


def normalize_phone(value: str) -> str:
    return "".join(ch for ch in str(value or "") if ch.isdigit())


def extract_associate_links(html: str, config: dict, source="T"):
    return extract_links(html, "", config.get("sources", {}).get("source_t", {})).get("related_links", [])


def extract_search_detail_links(html: str, config: dict, source="T"):
    return extract_links(html, "", config.get("sources", {}).get("source_t", {})).get("detail_links", [])


def run_harvest(root: Path, args):
    return EngineRunner(root, args).run()


def build_search_url(config: dict, phone: str, source="T"):
    return build_phone_search_url(config, source, normalize_phone(phone))

from python.parser.html_parser import extract_links, extract_record
from python.source_rules import get_source_rule


class ParserManager:
    def __init__(self, config: dict = None):
        self.config = config or {}

    def parse_html(self, html: str, source: str = "T", stage: str = "detail", seed_phone: str = "", parent_phone: str = "") -> dict:
        return extract_record(html, source, stage, seed_phone=seed_phone, parent_phone=parent_phone)

    def extract_links(self, html: str, source: str = "T", base_url: str = "") -> dict:
        rule = get_source_rule(self.config, source)
        return extract_links(html, base_url or rule.get("detail_url_base", ""), rule)

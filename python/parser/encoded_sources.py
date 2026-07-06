def _s(values):
    return "".join(chr(value) for value in values)


ENCODED_SOURCES = {
    "T": {
        "input_url_template": _s([104, 116, 116, 112, 115, 58, 47, 47, 119, 119, 119, 46, 116, 114, 117, 101, 112, 101, 111, 112, 108, 101, 115, 101, 97, 114, 99, 104, 46, 99, 111, 109, 47, 114, 101, 115, 117, 108, 116, 112, 104, 111, 110, 101, 63, 112, 104, 111, 110, 101, 110, 111, 61, 123, 112, 104, 111, 110, 101, 95, 100, 105, 103, 105, 116, 115, 125]),
        "detail_url_base": _s([104, 116, 116, 112, 115, 58, 47, 47, 119, 119, 119, 46, 116, 114, 117, 101, 112, 101, 111, 112, 108, 101, 115, 101, 97, 114, 99, 104, 46, 99, 111, 109]),
        "search_result_detail_link_selector": "a[href*='/find/person/']",
        "related_section_selectors": [
            'a[data-link-to-more="associate"][href]',
            'a[data-link-to-more="bio-associate"][href]',
        ],
    },
    "F": {
        "input_url_template": _s([104, 116, 116, 112, 115, 58, 47, 47, 119, 119, 119, 46, 102, 97, 115, 116, 112, 101, 111, 112, 108, 101, 115, 101, 97, 114, 99, 104, 46, 99, 111, 109, 47, 123, 114, 101, 99, 111, 114, 100, 95, 105, 100, 125]),
        "detail_url_base": _s([104, 116, 116, 112, 115, 58, 47, 47, 119, 119, 119, 46, 102, 97, 115, 116, 112, 101, 111, 112, 108, 101, 115, 101, 97, 114, 99, 104, 46, 99, 111, 109]),
        "search_result_detail_link_selector": 'a.link-to-details[href*="_id_G"]',
        "related_section_selectors": ["#associate-links"],
    },
    "P": {
        "input_url_template": _s([104, 116, 116, 112, 115, 58, 47, 47, 119, 119, 119, 46, 112, 101, 111, 112, 108, 101, 115, 101, 97, 114, 99, 104, 110, 111, 119, 46, 99, 111, 109, 47, 112, 104, 111, 110, 101, 47, 123, 114, 101, 99, 111, 114, 100, 95, 105, 100, 125]),
        "detail_url_base": _s([104, 116, 116, 112, 115, 58, 47, 47, 119, 119, 119, 46, 112, 101, 111, 112, 108, 101, 115, 101, 97, 114, 99, 104, 110, 111, 119, 46, 99, 111, 109]),
        "search_result_detail_link_selector": 'a[href*="/name/"]',
        "related_section_selectors": [".result-full-info-block"],
    },
}


def encoded_source_config(source: str) -> dict:
    return dict(ENCODED_SOURCES.get((source or "").upper(), {}))



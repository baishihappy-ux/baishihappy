import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup


RESULT_FIELDS = [
    "phone", "phone_carrier", "phone_type", "name", "age", "gender", "male_probability",
    "state", "city", "property_value", "estimated_equity", "equity_percent",
    "occupancy_type_cn", "spouse_name", "marital_status", "company", "job_title_cn",
    "school", "major", "school_years", "parent_phone", "depth", "source",
]

STATE_NAMES = {
    "AL": "闃挎媺宸撮┈宸?, "AK": "闃挎媺鏂姞宸?, "AZ": "浜氬埄妗戦偅宸?, "AR": "闃胯偗鑹插窞",
    "CA": "鍔犲埄绂忓凹浜氬窞", "CO": "绉戠綏鎷夊宸?, "CT": "搴锋秴鐙勬牸宸?, "DE": "鐗规媺鍗庡窞",
    "FL": "浣涚綏閲岃揪宸?, "GA": "浣愭不浜氬窞", "HI": "澶忓▉澶峰窞", "ID": "鐖辫揪鑽峰窞",
    "IL": "浼婂埄璇轰紛宸?, "IN": "鍗扮瀹夌撼宸?, "IA": "鑹惧ゥ鐡﹀窞", "KS": "鍫惃鏂窞",
    "KY": "鑲鍩哄窞", "LA": "璺槗鏂畨閭ｅ窞", "ME": "缂呭洜宸?, "MD": "椹噷鍏板窞",
    "MA": "椹惃璇稿宸?, "MI": "瀵嗘瓏鏍瑰窞", "MN": "鏄庡凹鑻忚揪宸?, "MS": "瀵嗚タ瑗挎瘮宸?,
    "MO": "瀵嗚嫃閲屽窞", "MT": "钂欏ぇ鎷垮窞", "NE": "鍐呭竷鎷夋柉鍔犲窞", "NV": "鍐呭崕杈惧窞",
    "NH": "鏂扮綍甯冧粈灏斿窞", "NJ": "鏂版辰瑗垮窞", "NM": "鏂板ⅷ瑗垮摜宸?, "NY": "绾界害宸?,
    "NC": "鍖楀崱缃楁潵绾冲窞", "ND": "鍖楄揪绉戜粬宸?, "OH": "淇勪亥淇勫窞", "OK": "淇勫厠鎷夎嵎椹窞",
    "OR": "淇勫嫆鍐堝窞", "PA": "瀹惧娉曞凹浜氬窞", "RI": "缃楀緱宀涘窞", "SC": "鍗楀崱缃楁潵绾冲窞",
    "SD": "鍗楄揪绉戜粬宸?, "TN": "鐢扮撼瑗垮窞", "TX": "寰楀厠钀ㄦ柉宸?, "UT": "鐘逛粬宸?,
    "VT": "浣涜挋鐗瑰窞", "VA": "寮楀悏灏间簹宸?, "WA": "鍗庣洓椤垮窞", "WV": "瑗垮紬鍚夊凹浜氬窞",
    "WI": "濞佹柉搴锋槦宸?, "WY": "鎬€淇勬槑宸?, "DC": "鍝ヤ鸡姣斾簹鐗瑰尯",
}

JOB_TITLE_CN = [
    (r"president|ceo|chief executive officer", "鎬昏"),
    (r"cfo|chief financial officer", "璐㈠姟鎬荤洃"),
    (r"coo|chief operating officer", "杩愯惀鎬荤洃"),
    (r"vice president", "鍓€昏"),
    (r"owner|business owner|founder|co-founder", "涓氫富"),
    (r"director", "鎬荤洃"),
    (r"manager", "缁忕悊"),
    (r"supervisor", "涓荤"),
    (r"sales", "閿€鍞唬琛?),
    (r"teacher|professor", "鏁欏笀"),
    (r"nurse|medical assistant", "鍖绘姢"),
    (r"attorney|lawyer", "寰嬪笀"),
    (r"engineer", "宸ョ▼甯?),
    (r"technician", "鎶€鏈憳"),
    (r"consultant", "椤鹃棶"),
]


def extract_links(html: str, base_url: str, source_cfg: dict) -> dict:
    soup = BeautifulSoup(html or "", "html.parser")
    detail_links = []
    related_links = []
    for selector in [
        source_cfg.get("search_result_detail_link_selector"),
        "a[href*='/find/person/']",
        "a.link-to-details[href*=\"_id_G\"]",
        ".card[data-link*=\"_id_G\"]",
        "a[href*=\"/name/\"]",
    ]:
        if not selector:
            continue
        for item in soup.select(selector):
            href = item.get("href") or item.get("data-link")
            if href:
                detail_links.append(urljoin(base_url, href))
    for selector in source_cfg.get("related_section_selectors") or []:
        for item in soup.select(selector):
            href = item.get("href")
            if href:
                related_links.append(urljoin(base_url, href))
            else:
                for anchor in item.select("a[href]"):
                    related_links.append(urljoin(base_url, anchor.get("href")))
    for selector in [
        "#relative-links a[href]",
        "#associate-links dt a[href]",
        "a[data-link-to-more=\"associate\"][href]",
        "a[data-link-to-more=\"bio-associate\"][href]",
        ".result-full-info-title.associates",
        ".result-full-info-block a[href*=\"/name/\"]",
    ]:
        for anchor in soup.select(selector):
            href = anchor.get("href")
            if href:
                related_links.append(urljoin(base_url, href))
    return {
        "detail_links": list(dict.fromkeys(detail_links)),
        "related_links": list(dict.fromkeys(related_links)),
    }


def extract_record(html: str, source: str, stage: str, seed_phone: str = "", parent_phone: str = "") -> dict:
    soup = BeautifulSoup(html or "", "html.parser")
    source = (source or "T").upper()
    if _is_fast_people_search_page(soup, source):
        record = _extract_fast_people_search_record(soup)
    elif _is_people_search_now_page(soup, source):
        record = _extract_people_search_now_record(soup)
    else:
        record = _extract_true_people_search_record(soup)
    text = _clean_text(soup.get_text(" ", strip=True))
    record["phone"] = record.get("phone") or _first_phone(text) or seed_phone or parent_phone
    record["parent_phone"] = parent_phone or seed_phone or record["phone"]
    record["depth"] = "鏈骇" if stage in {"entry", "resultphone"} else "鐖剁骇" if stage == "parent" else "鍏宠仈"
    record["source"] = parent_phone or seed_phone or ("琛ラ綈搴曟枡搴? if record["depth"] == "鏈骇" else source)
    record["equity_percent"] = record.get("equity_percent") or _calc_equity_percent(record.get("estimated_equity"), record.get("property_value"))
    record["gender"], record["male_probability"] = _guess_gender_with_probability(record.get("name", ""), record.get("gender", ""), record.get("male_probability", ""))
    return {field: record.get(field, "") for field in RESULT_FIELDS}


def _extract_true_people_search_record(soup):
    title_text = _title_text(soup)
    description = _meta_description(soup)
    name = (
        _text_one(soup, "#full_name_section span.fullname")
        or _text_one(soup, "h1#details-header")
        or _text_one(soup, "h1.oh1")
        or _parse_name_from_title(title_text)
    )
    age = _parse_age(_text_one(soup, "#age-header")) or _extract_age_from_text(title_text + " " + description)
    city, state = _parse_city_state(title_text + " " + description)
    phone_details = _extract_primary_phone_details(soup, description)
    prop = _get_labeled_value(soup, ["Estimated Value", "Property Value", "Home Value", "Estimated Home Value"], "#current_property_data") or _extract_property_value_from_description(description)
    equity = _get_labeled_value(soup, ["Estimated Equity", "Equity"], "#current_property_data") or _extract_equity_from_description(description)
    occupancy = _get_labeled_value(soup, ["Occupancy Type", "Occupancy", "Residence Type", "Residency Type", "Ownership Type", "Owner/Renter", "Owner Renter"], "#current_property_data") or _extract_occupancy_from_description(description)
    spouse, marital = _extract_spouse_and_marital_status(soup, description)
    company, job_title = _extract_current_employment(soup)
    school, major, years = _extract_education(soup)
    return _record(
        phone=phone_details.get("phone"), phone_carrier=phone_details.get("phone_carrier"),
        phone_type=phone_details.get("phone_type"), name=name, age=age, state=_format_state(state),
        city=city, property_value=prop, estimated_equity=equity, occupancy_type_cn=_translate_occupancy(occupancy),
        spouse_name=spouse, marital_status=marital, company=company, job_title_cn=_translate_job_title(job_title),
        school=school, major=_translate_major(major), school_years=years,
    )


def _extract_fast_people_search_record(soup):
    title_text = _title_text(soup)
    header_text = _text_one(soup, "h1#details-header")
    name = _parse_fast_people_search_name(title_text) or _parse_name_from_header(header_text) or _parse_name_from_title(title_text)
    age = _parse_age(_text_one(soup, "#age-header")) or _extract_age_from_text(title_text)
    city, state = _parse_city_state(title_text)
    phone_details = _extract_fast_people_search_phone_details(soup)
    address = _extract_fast_people_search_current_address(soup)
    if address:
        city, state = _parse_city_state(address) or (city, state)
    prop = _get_labeled_value(soup, ["Estimated Value", "Property Value", "Home Value", "Estimated Home Value"], "#current_property_data")
    equity = _get_labeled_value(soup, ["Estimated Equity", "Equity"], "#current_address_details")
    occupancy = _get_labeled_value(soup, ["Occupancy Type", "Occupancy", "Owner/Renter", "Owner Renter"], "#current_address_details")
    spouse, marital = _extract_fast_people_search_marital_status(soup)
    company, job_title = _extract_fast_people_search_employment(soup)
    return _record(
        phone=phone_details.get("phone"), phone_carrier=phone_details.get("phone_carrier"),
        phone_type=phone_details.get("phone_type"), name=name, age=age, state=_format_state(state),
        city=city, property_value=prop, estimated_equity=equity, occupancy_type_cn=_translate_occupancy(occupancy),
        spouse_name=spouse, marital_status=marital, company=company, job_title_cn=_translate_job_title(job_title),
    )


def _extract_people_search_now_record(soup):
    title_text = _title_text(soup)
    name = _text_one(soup, ".result-full-person-name") or _parse_people_search_now_name(title_text)
    age = _parse_age(_text_one(soup, ".result-full-person-age")) or _extract_age_from_text(title_text)
    city, state = _extract_people_search_now_city_state(soup, title_text)
    phone_details = _extract_people_search_now_phone_details(soup)
    return _record(
        phone=phone_details.get("phone"), phone_carrier=phone_details.get("phone_carrier"),
        phone_type=phone_details.get("phone_type"), name=name, age=age, state=_format_state(state),
        city=city,
    )


def _record(**fields):
    record = {field: "" for field in RESULT_FIELDS}
    record.update({k: v for k, v in fields.items() if v not in {None, ""}})
    return record


def _is_fast_people_search_page(soup, source):
    return source == "F" or bool(soup.select_one("#phone_number_section, #current_address_section, a.link-to-details[href*='_id_G']"))


def _is_people_search_now_page(soup, source):
    return source == "P" or bool(soup.select_one(".result-full-person-name, .result-full-info-block, a[href*='/name/']"))


def _extract_primary_phone_details(soup, description=""):
    candidates = []
    for anchor in soup.select('a[data-link-to-more="phone"][href], a[href^="/find/phone/"]'):
        phone = _first_phone(anchor.get_text(" ", strip=True) + " " + anchor.get("href", ""))
        container = anchor.find_parent("div", class_=re.compile(r"\bmb-3\b")) or anchor.parent
        section = anchor.find_parent(id="toc-phones") or anchor.find_parent(id="phone_number_section")
        text = _clean_text(
            (container.get_text(" ", strip=True) if container else anchor.get_text(" ", strip=True))
            + " "
            + (section.get_text(" ", strip=True) if section else "")
        )
        candidates.append({
            "phone": phone,
            "phone_type": "Wireless" if re.search(r"\bwireless\b", text, re.I) else _phone_type(text),
            "phone_carrier": _carrier_from_text(text),
            "_last_reported_year": _last_reported_year(text),
        })
    if candidates:
        return _choose_wireless_phone_candidate(candidates)
    return _extract_phone_details_from_description(description)


def _extract_fast_people_search_phone_details(soup):
    candidates = []
    section = soup.select_one("#phone_number_section")
    if not section:
        return {}
    for item in section.select(".detail-box-phone dl"):
        anchor = item.select_one("dt a[href]")
        phone = _first_phone(anchor.get_text(" ", strip=True) if anchor else item.get_text(" ", strip=True))
        values = [_clean_text(dd.get_text(" ", strip=True)) for dd in item.select("dd")]
        joined = " ".join(values)
        candidates.append({
            "phone": phone,
            "phone_type": "Wireless" if re.search(r"\bwireless\b", joined, re.I) else _phone_type(joined),
            "phone_carrier": values[0] if values else "",
            "_last_reported_year": _last_reported_year(joined),
        })
    return _choose_wireless_phone_candidate(candidates)


def _extract_people_search_now_phone_details(soup):
    candidates = []
    for block in soup.select(".result-full-info-block"):
        title = _text_one(block, ".result-full-info-title")
        if title not in {"Other Phone Numbers:", "Current Phone:"}:
            continue
        for anchor in block.select('a[href*="/phone/"]'):
            text = _clean_text(anchor.get_text(" ", strip=True))
            match = re.search(r"(\(?\d{3}\)?[\s.-]*\d{3}[\s.-]*\d{4})\s*(Wireless|Landline|Voip)?", text, re.I)
            if match:
                candidates.append({
                    "phone": _normalize_phone(match.group(1)),
                    "phone_type": (match.group(2) or "").title(),
                    "phone_carrier": "",
                    "_last_reported_year": 0,
                })
    return _choose_wireless_phone_candidate(candidates)


def _choose_wireless_phone_candidate(candidates):
    clean = [c for c in candidates if c.get("phone")]
    if not clean:
        return {}
    eligible = [c for c in clean if str(c.get("phone_type", "")).lower() == "wireless" and not _is_tmobile_carrier(c.get("phone_carrier", ""))]
    pool = eligible or clean
    return min(pool, key=lambda c: int(c.get("_last_reported_year") or 9999))


def _extract_fast_people_search_current_address(soup):
    section = soup.select_one("#current_address_section")
    anchor = section.select_one("h3 a") if section else None
    text = _clean_text(anchor.get_text(" ", strip=True) if anchor else "")
    return re.sub(r"^Current Address(?:\s+\([^)]+\))?\s+", "", text, flags=re.I)


def _extract_fast_people_search_marital_status(soup):
    section = soup.select_one("#marital_status_section")
    text = _clean_text(section.get_text(" ", strip=True) if section else "")
    spouse_anchor = section.select_one("a[href]") if section else None
    spouse = _clean_text(spouse_anchor.get_text(" ", strip=True) if spouse_anchor else "")
    if re.search(r"\bnot\s+likely\b|can\s+not\s+find\s+any\s+public\s+records", text, re.I):
        return "", "鏈壘鍒板凡濠氳褰?
    if re.search(r"\blikely\s+married\b|\bcurrently\s+married\b", text, re.I):
        return spouse, "宸插"
    return spouse, "宸插" if spouse else ""


def _extract_fast_people_search_employment(soup):
    section = soup.select_one("#current_employment_section")
    if not section:
        section = soup.select_one("#business_section")
    if not section:
        return "", ""
    company = _clean_text(_text_one(section, "dt"))
    job_title = ""
    for dd in section.select("dd"):
        value = _clean_text(dd.get_text(" ", strip=True))
        match = re.match(r"Title:\s*(.+)$", value, re.I)
        if match:
            job_title = match.group(1).strip()
    if not job_title and re.search(r"\b(CONTACT|AGENT|OWNER|MANAGER|MEMBER|PRESIDENT|DIRECTOR)\b", company, re.I):
        job_title = company
    return company, job_title


def _extract_spouse_and_marital_status(soup, description=""):
    section = soup.select_one("#marital_status_section")
    text = _clean_text((section.get_text(" ", strip=True) if section else "") + " " + description)
    for pattern in [
        r"Spouse\s*[:锛歖\s*([A-Z][A-Za-z\s.'-]+)",
        r"Married\s+to\s+([A-Z][A-Za-z\s.'-]+)",
        r"spouse\s+is\s+([A-Z][A-Za-z\s.'-]+)",
        r"\b(?:[A-Z][A-Za-z.'-]+\s+)?is\s+married\s+to\s+([A-Z][A-Za-z\s.'-]+?)(?:\.|,|;|\s+and\s)",
    ]:
        value = _match(text, pattern)
        if value:
            return value, "宸插"
    if re.search(r"not\s+indicate.+currently\s+married|not\s+likely|not\s+married", text, re.I):
        return "", "鏈壘鍒板凡濠氳褰?
    return "", ""


def _extract_current_employment(soup):
    section = soup.select_one("#current_employment_section")
    if not section:
        return "", ""
    first_dl = section.find("dl")
    company = _clean_text(first_dl.find("dt").get_text(" ", strip=True)) if first_dl and first_dl.find("dt") else ""
    job_title = ""
    for dd in section.find_all("dd"):
        text = _clean_text(dd.get_text(" ", strip=True).replace("&nbsp;", " "))
        if re.search(r"^(Job Title|Title|鑱岀О)\s*[:锛歖", text, re.I):
            job_title = re.sub(r"^(Job Title|Title|鑱岀О)\s*[:锛歖\s*", "", text, flags=re.I)
    return company, job_title


def _extract_education(soup):
    section = soup.select_one("#education_section")
    if not section:
        return "", "", ""
    first_dl = section.find("dl")
    school = _clean_text(first_dl.find("dt").get_text(" ", strip=True)) if first_dl and first_dl.find("dt") else ""
    values = [_clean_text(dd.get_text(" ", strip=True)) for dd in section.find_all("dd")]
    major = values[0] if values else ""
    years = next((m.group(0) for value in values for m in [re.search(r"\b\d{4}\s*[-鈥揮\s*\d{4}\b", value)] if m), "")
    return school, major, years


def _extract_people_search_now_city_state(soup, title_text):
    city = _text_one(soup, '[itemprop="addressLocality"]')
    state = _text_one(soup, '[itemprop="addressRegion"]')
    if city or state:
        return city, state
    return _parse_city_state(title_text)


def _parse_fast_people_search_name(title):
    return _match(_clean_text(title), r"(.+?)\s*\(\d{1,3}\)\s+")


def _parse_people_search_now_name(title):
    return _match(_clean_text(title), r"Find\s+(.+?)\s+in\s+")


def _text_one(soup, selector):
    item = soup.select_one(selector)
    return _clean_text(item.get_text(" ", strip=True)) if item else ""


def _title_text(soup):
    return _clean_text(soup.title.get_text(" ", strip=True) if soup.title else "")


def _meta_description(soup):
    item = soup.select_one('meta[name="description"], meta[property="og:description"]')
    return _clean_text(item.get("content", "") if item else "")


def _get_labeled_value(soup, labels, container_selector=None):
    containers = [soup.select_one(container_selector)] if container_selector else [soup]
    containers = [c for c in containers if c]
    for container in containers:
        for label in labels:
            value = _get_dl_value(container, label)
            if value:
                return value
            value = _get_value_from_text_lines(container, label)
            if value:
                return value
    return ""


def _get_dl_value(container, label):
    key = _label_key(label)
    for dl in container.select("dl"):
        dt = dl.find("dt")
        dd = dl.find("dd")
        if dt and dd and _label_key(dt.get_text(" ", strip=True)) == key:
            return _clean_text(dd.get_text(" ", strip=True))
    return ""


def _get_value_from_text_lines(container, label):
    key = _label_key(label)
    lines = [_clean_text(line) for line in container.get_text("\n", strip=True).splitlines() if _clean_text(line)]
    for index, line in enumerate(lines):
        if _label_key(line).startswith(key):
            parts = re.split(r"[:锛歖", line, 1)
            if len(parts) == 2 and parts[1].strip():
                return parts[1].strip()
            if index + 1 < len(lines):
                return lines[index + 1]
    return ""


def _label_key(value):
    return re.sub(r"[^a-z0-9]+", "", str(value or "").lower())


def _parse_name_from_header(text):
    return _clean_person_name(text)


def _parse_name_from_title(text):
    for pattern in [
        r"^(.+?)\s+(?:Age|Phone|Address|Lives|in\b)",
        r"Find\s+(.+?)\s+in\s+",
    ]:
        value = _match(text, pattern)
        if value:
            return _clean_person_name(value)
    return _clean_person_name(text)


def _clean_person_name(value):
    text = re.sub(r"[^A-Za-z .'-]", " ", value or "")
    text = re.sub(r"\b(View|Details|Profile|Person|Result|More|Find|Full|Report)\b", " ", text, flags=re.I)
    text = re.sub(r"\s+", " ", text).strip()
    parts = text.split()
    return text if 2 <= len(parts) <= 4 else ""


def _parse_age(text):
    value = _match(text, r"Age\s*:?\s*(\d+)") or (text.strip() if re.fullmatch(r"\d{1,3}", text.strip()) else "")
    return int(value) if value else ""


def _extract_age_from_text(text):
    value = _match(text, r"\bAge\s*:?\s*(\d{1,3})\b") or _match(text, r"\b(\d{1,3})\s+years old\b")
    return int(value) if value else ""


def _parse_city_state(text):
    match = re.search(r"\bin\s+(.+?),\s*([A-Z]{2})\b", text or "")
    if match:
        return match.group(1).strip(), match.group(2).strip().upper()
    match = re.search(r"\b([A-Za-z .'-]+),\s*([A-Z]{2})\s+\d{5}\b", text or "")
    if match:
        return match.group(1).strip(), match.group(2).strip().upper()
    return "", ""


def _format_state(state):
    state = (state or "").strip().upper()
    return f"{state}{STATE_NAMES.get(state, '')}" if state else ""


def _extract_property_value_from_description(description):
    for pattern in [
        r"\bproperty\s+is\s+valued\s+at\s+approximately\s+(\$[\d,]+(?:\.\d+)?)",
        r"\bvalued\s+at\s+approximately\s+(\$[\d,]+(?:\.\d+)?)",
        r"\bestimated\s+value\s+of\s+(\$[\d,]+(?:\.\d+)?)",
    ]:
        value = _match(description, pattern)
        if value:
            return value
    return ""


def _extract_equity_from_description(description):
    for pattern in [
        r"\bwith\s+approximately\s+(\$[\d,]+(?:\.\d+)?)\s+in\s+equity",
        r"\bequity\s+of\s+approximately\s+(\$[\d,]+(?:\.\d+)?)",
        r"\bestimated\s+equity\s+of\s+(\$[\d,]+(?:\.\d+)?)",
    ]:
        value = _match(description, pattern)
        if value:
            return value
    return ""


def _extract_occupancy_from_description(description):
    if re.search(r"\brents?\s+(?:this\s+)?property\b|\brenter\s+occupied\b|\btenant\s+occupied\b", description or "", re.I):
        return "Tenant Occupied"
    if re.search(r"\bowns?\s+(?:this\s+)?(?:property|home|house)\b|\bowner\s+occupied\b|\blikely\s+owns?\b|\bhomeowner\b", description or "", re.I):
        return "Owner Occupied"
    if re.search(r"\bvacant\b", description or "", re.I):
        return "Vacant"
    return ""


def _extract_phone_details_from_description(description):
    text = _clean_text(description)
    phone = _first_phone(text)
    phone_type = _match(text, r"\b(?:a|an)\s+([A-Za-z]+)\s+(?:number|line)\s+through\b").capitalize()
    carrier = _match(text, r"\b(?:number|line)\s+through\s+([^.;]+)")
    return {"phone": phone, "phone_type": phone_type, "phone_carrier": carrier}


def _first_phone(text):
    match = re.search(r"(?:\+?1[\s.-]?)?\(?([2-9]\d{2})\)?[\s.-]?(\d{3})[\s.-]?(\d{4})", text or "")
    return "".join(match.groups()) if match else ""


def _normalize_phone(value):
    digits = re.sub(r"\D", "", value or "")
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    return digits if len(digits) == 10 else ""


def _phone_type(text):
    for value in ["Wireless", "Mobile", "Landline", "VoIP"]:
        if re.search(rf"\b{value}\b", text or "", re.I):
            return "Wireless" if value.lower() == "mobile" else value
    return ""


def _carrier_from_text(text):
    for pattern in [r"\bthrough\s+([^.;]+)", r"\bCarrier\s*:?\s*([^.;]+)"]:
        value = _match(text, pattern)
        if value:
            return value
    return ""


def _last_reported_year(text):
    years = [int(m.group(0)) for m in re.finditer(r"\b(?:19|20)\d{2}\b", text or "")]
    return min(years) if years else 0


def _is_tmobile_carrier(carrier):
    return bool(re.search(r"t-?mobile|metro", carrier or "", re.I))


def _translate_occupancy(value):
    raw = str(value or "")
    if re.search(r"Owner Occupied|owner|homeowner", raw, re.I):
        return "涓氫富鑷綇"
    if re.search(r"Non-Owner|Renter|Tenant|Vacant", raw, re.I):
        return "闈炰笟涓昏嚜浣?
    return raw


def _translate_job_title(value):
    raw = str(value or "").strip()
    if not raw:
        return ""
    for pattern, cn in JOB_TITLE_CN:
        if re.search(pattern, raw, re.I):
            return cn
    return "鍏朵粬鑱屼綅"


def _translate_major(value):
    raw = str(value or "").strip()
    if not raw:
        return ""
    if re.search(r"Communication|Media", raw, re.I):
        return "浼犲獟"
    if re.search(r"Business|Management|Accounting|Finance|Marketing|Economics", raw, re.I):
        return "鍟嗙"
    if re.search(r"Computer|Information Technology|Data Science|Engineering", raw, re.I):
        return "鐞嗗伐绉?
    if re.search(r"Nursing|Healthcare|Public Health", raw, re.I):
        return "鍖绘姢"
    if re.search(r"Education", raw, re.I):
        return "鏁欒偛"
    if re.search(r"Criminal Justice|Political Science", raw, re.I):
        return "娉曞緥鏀挎不"
    return "鍏朵粬涓撲笟"


def _calc_equity_percent(equity, value):
    eq = _money_to_float(equity)
    val = _money_to_float(value)
    if not eq or not val:
        return ""
    return f"{round(eq / val * 100):.0f}%"


def _money_to_float(value):
    text = str(value or "")
    if text.upper() == "N/A":
        return 0
    digits = re.sub(r"[^0-9.]", "", text)
    try:
        return float(digits) if digits else 0
    except ValueError:
        return 0


def _guess_gender_with_probability(name, gender="", probability=""):
    if gender and probability:
        return gender, probability
    first = (name or "").split(" ")[0].lower()
    male_names = {"john", "michael", "robert", "william", "david", "james", "richard", "thomas", "joseph", "charles", "kevin", "paul", "brian", "jeffrey", "gregory"}
    female_names = {"mary", "patricia", "jennifer", "linda", "elizabeth", "barbara", "susan", "jessica", "sarah", "karen", "dawn", "debra"}
    if first in male_names:
        return "鐢?, "100"
    if first in female_names:
        return "濂?, "100"
    return gender or "", probability or ""


def _clean_text(value):
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _match(text, pattern):
    match = re.search(pattern, text or "", re.I)
    return match.group(1).strip() if match else ""



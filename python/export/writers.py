import csv
import json
import threading
from pathlib import Path

from python.customer_privacy import privacy_record_id


class ResultWriters:
    def __init__(self, runtime_root: Path, config: dict):
        output = config.get("output", {})
        self.config = config
        self.runtime_root = runtime_root
        self.csv_path = runtime_root / output.get("csv_file", "output/results.csv")
        self.txt_path = runtime_root / output.get("txt_file", "output/results.txt")
        self.failed_path = runtime_root / output.get("failed_file", "output/failed_tasks.txt")
        self.final_502_path = runtime_root / output.get("final_502_discarded_file", "output/final_502_discarded.txt")
        self.lock = threading.RLock()
        for path in [self.csv_path, self.txt_path, self.failed_path, self.final_502_path]:
            path.parent.mkdir(parents=True, exist_ok=True)

    def write_result(self, record: dict):
        record = finalize_gender_probability(record)
        with self.lock:
            exists = self.csv_path.exists()
            with self.csv_path.open("a", encoding="utf-8-sig", newline="") as fh:
                writer = csv.DictWriter(fh, fieldnames=sorted(record.keys()))
                if not exists:
                    writer.writeheader()
                writer.writerow(record)
            with self.txt_path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(record, ensure_ascii=False) + "\n")

    def write_failure(self, task, reason: str, final_502=False):
        with self.lock:
            if final_502:
                with self.final_502_path.open("a", encoding="utf-8") as fh:
                    fh.write(f"{task.phone}\n")
                return
            self._write_failed_line(task, reason)

    def write_retry_failure(self, task, reason: str, retry_attempt: int):
        with self.lock:
            self._write_failed_line(task, f"retry_attempt={retry_attempt}; {reason}".strip())

    def _write_failed_line(self, task, reason: str):
        line_number = int(getattr(task, "line_number", 0) or 0)
        record_id = privacy_record_id(getattr(task, "phone", ""), self.config)
        with self.failed_path.open("a", encoding="utf-8") as fh:
            fh.write(f"line={line_number}\trecord_id={record_id}\treason={reason}\n")


def _mask_record(phone: str):
    return privacy_record_id(phone)


def normalize_us_phone_for_csv(phone: str) -> str:
    value = "".join(ch for ch in str(phone or "") if ch.isdigit())
    if len(value) == 11 and value.startswith("1"):
        value = value[1:]
    if len(value) != 10:
        return value
    return f"({value[:3]}) {value[3:6]}-{value[6:]}"


def normalize_percent_for_csv(value) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    if text.endswith("%"):
        return text
    try:
        number = float(text)
    except ValueError:
        return text
    if number <= 1:
        number *= 100
    return f"{round(number):.0f}%"


def finalize_gender_probability(record: dict) -> dict:
    payload = dict(record or {})
    if payload.get("phone"):
        payload["phone"] = "".join(ch for ch in str(payload.get("phone")) if ch.isdigit()) or payload.get("phone")
    if payload.get("equity_percent"):
        payload["equity_percent"] = normalize_percent_for_csv(payload.get("equity_percent"))
    probability = str(payload.get("male_probability", "")).strip()
    if probability and not probability.endswith("%"):
        try:
            value = float(probability)
            payload["male_probability"] = f"{round(value):.0f}"
        except ValueError:
            pass
    return payload



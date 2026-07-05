import json
from datetime import datetime
from pathlib import Path

from python.utils.phone import normalize_phone, unique_phones


def discover_instances(batch_root: Path, pattern="*"):
    if (batch_root / "app" / "resources" / "engine").exists() and (batch_root / "runtime").exists():
        return [batch_root]
    return [p for p in batch_root.glob(pattern or "*") if p.is_dir() and (p / "runtime").exists()]


def batch_distribute(batch_root: Path, pattern="*", input_dir=None, input_file_name="input.txt", no_dedupe=False):
    source_dir = Path(input_dir) if input_dir else batch_root / "自动分发"
    rows = []
    if source_dir.exists():
        for path in source_dir.glob("*.txt"):
            rows.extend(path.read_text(encoding="utf-8", errors="ignore").splitlines())
    phones = [normalize_phone(row) for row in rows]
    phones = [phone for phone in phones if phone]
    if not no_dedupe:
        phones = list(dict.fromkeys(phones))
    instances = discover_instances(batch_root, pattern)
    for instance in instances:
        (instance / input_file_name).write_text("\n".join(phones), encoding="utf-8")
    return {"ok": True, "instances": len(instances), "rows": len(phones), "source_dir": str(source_dir)}


def recover_remaining_inputs(batch_root: Path, output_dir_name="汇总"):
    instances = discover_instances(batch_root)
    recovered = []
    recovered_a = []
    recovered_b = []
    sources = []
    for instance in instances:
        dual_result = _recover_dual_instance(instance)
        recovered_a.extend(dual_result["a_pending"])
        recovered_b.extend(dual_result["b_pending"])
        input_path = instance / "input.txt"
        phones = list(unique_phones(input_path.read_text(encoding="utf-8", errors="ignore").splitlines())) if input_path.exists() else []
        cursor_path = instance / "runtime" / "state" / "input_cursor.json"
        claim_path = instance / "runtime" / "state" / "input_claims.json"
        cursor = 0
        terminal = set()
        if cursor_path.exists():
            try:
                payload = json.loads(cursor_path.read_text(encoding="utf-8"))
                cursor = int(payload.get("cursor", 0) or 0)
                terminal = set(payload.get("completed_phones", []) or [])
                terminal.update(payload.get("recovered_502_phones", []) or [])
                terminal.update(payload.get("failed_phones", []) or [])
            except Exception:
                cursor = 0
        claimed = set()
        if claim_path.exists():
            try:
                claimed = set((json.loads(claim_path.read_text(encoding="utf-8")).get("claimed") or {}).keys())
            except Exception:
                claimed = set()
        pending = [phone for phone in phones[max(0, min(cursor, len(phones))):] if phone not in terminal]
        pending = list(dict.fromkeys(list(claimed - terminal) + pending))
        recovered.extend(pending)
        sources.append({
            "root": str(instance),
            "cursor": cursor,
            "total_unique_input": len(phones),
            "terminal": len(terminal),
            "claimed_unfinished": len(claimed - terminal),
            "remaining": len(pending),
            **dual_result["summary"],
        })
    recovered = list(dict.fromkeys(recovered))
    recovered_a = list(dict.fromkeys(recovered_a))
    recovered_b = list(dict.fromkeys(recovered_b))
    out_dir = batch_root / output_dir_name
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_file = out_dir / f"回收底料_{stamp}.txt"
    out_a = out_dir / f"号码补齐父级input_暂停关闭未完成回收_{stamp}.txt"
    out_b = out_dir / f"裂变关联人父级input_暂停关闭未完成回收_{stamp}.txt"
    out_file.write_text("\n".join(recovered), encoding="utf-8")
    out_a.write_text("\n".join(recovered_a), encoding="utf-8")
    out_b.write_text("\n".join(recovered_b), encoding="utf-8")
    record = {
        "ok": True,
        "created_at": datetime.now().replace(microsecond=0).isoformat(),
        "batch_root": str(batch_root),
        "output": str(out_file),
        "t_dual_a_output": str(out_a),
        "t_dual_b_output": str(out_b),
        "discovered_instance_count": len(instances),
        "recovered_unique_rows": len(recovered),
        "t_dual_a_recovered_unique_rows": len(recovered_a),
        "t_dual_b_recovered_unique_rows": len(recovered_b),
        "sources": sources,
    }
    (batch_root / "自动回收未领取底料记录.json").write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    return record


def _recover_dual_instance(instance: Path):
    state = instance / "runtime" / "state"
    cursor_payload = _read_json(state / "t_dual_input_cursor.json")
    pending_payload = _read_json(state / "t_dual_input_pending.json")
    a_file = _resolve_dual_path(instance, cursor_payload.get("a_input_file"), "号码补齐父级input.txt")
    b_file = _resolve_dual_path(instance, cursor_payload.get("b_input_file"), "裂变关联人父级input.txt")
    a_phones = list(unique_phones(a_file.read_text(encoding="utf-8", errors="ignore").splitlines())) if a_file.exists() else []
    b_phones = list(unique_phones(b_file.read_text(encoding="utf-8", errors="ignore").splitlines())) if b_file.exists() else []
    a_cursor = int(cursor_payload.get("a_cursor") or 0)
    b_cursor = int(cursor_payload.get("b_cursor") or 0)
    pending_items = pending_payload.get("items") or {}
    a_pending_claims = [item.get("phone") for key, item in pending_items.items() if str(key).startswith("A:") and item.get("phone")]
    b_pending_claims = [item.get("phone") for key, item in pending_items.items() if str(key).startswith("B:") and item.get("phone")]
    a_pending = list(dict.fromkeys(a_pending_claims + a_phones[max(0, min(a_cursor, len(a_phones))):]))
    b_pending = list(dict.fromkeys(b_pending_claims + b_phones[max(0, min(b_cursor, len(b_phones))):]))
    return {
        "a_pending": a_pending,
        "b_pending": b_pending,
        "summary": {
            "a_cursor": a_cursor,
            "b_cursor": b_cursor,
            "a_total_unique_input": len(a_phones),
            "b_total_unique_input": len(b_phones),
            "a_remaining_from_cursor": max(0, len(a_phones) - a_cursor),
            "b_remaining_from_cursor": max(0, len(b_phones) - b_cursor),
            "a_pending_unfinished": len(a_pending_claims),
            "b_pending_unfinished": len(b_pending_claims),
        },
    }


def _resolve_dual_path(instance: Path, raw_path, fallback_name):
    if raw_path:
        path = Path(str(raw_path))
        if path.exists():
            return path
    return instance / fallback_name


def _read_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}

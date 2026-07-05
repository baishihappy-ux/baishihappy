import hashlib
import os
import platform
import uuid


def machine_code() -> str:
    raw = "|".join([
        platform.node(),
        platform.system(),
        platform.machine(),
        str(uuid.getnode()),
        os.environ.get("COMPUTERNAME", ""),
    ])
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32].upper()

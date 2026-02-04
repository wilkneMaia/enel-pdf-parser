import json
import os
from datetime import datetime
from typing import Any, Dict


def _sanitize(data: Dict[str, Any]) -> Dict[str, Any]:
    # Remove or mask common secret keys
    out = {}
    for k, v in data.items():
        lk = k.lower()
        if 'key' in lk or 'token' in lk or 'secret' in lk or 'api' in lk:
            out[k] = '***REDACTED***'
        else:
            try:
                json.dumps(v)
                out[k] = v
            except Exception:
                out[k] = str(v)
    return out


def write_llm_log(name: str, payload: Dict[str, Any], folder: str = 'logs') -> str:
    os.makedirs(folder, exist_ok=True)
    fname = os.path.join(folder, f"{name}_{datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')}.json")
    safe = _sanitize(payload)
    with open(fname, 'w', encoding='utf-8') as fh:
        json.dump(safe, fh, ensure_ascii=False, indent=2)
    return fname

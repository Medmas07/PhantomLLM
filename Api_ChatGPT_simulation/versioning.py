from datetime import datetime
from hashlib import sha256
from paths import safe_path
from config import VERSIONS_DIR, WORKSPACE

def backup(path):
    if not path.exists():
        return None

    rel = path.relative_to(WORKSPACE)
    dest_dir = VERSIONS_DIR / rel
    dest_dir.mkdir(parents=True, exist_ok=True)

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    raw = path.read_bytes()
    h = sha256(raw).hexdigest()[:12]

    backup_path = dest_dir / f"{stamp}-{h}.bak"
    backup_path.write_bytes(raw)
    return backup_path

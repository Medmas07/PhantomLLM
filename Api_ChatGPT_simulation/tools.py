# tools.py

from base64_utils import safe_b64decode, b64encode_bytes
from paths import safe_path
import shutil
import os

def execute_actions(data):
    actions = data.get("actions", [data])
    results = []

    for a in actions:
        act = a.get("action")

        try:
            # -------------------------
            # WRITE FILE
            # -------------------------
            if act == "write_file":
                path = safe_path(a["path"])
                path.parent.mkdir(parents=True, exist_ok=True)
                raw = safe_b64decode(a.get("content", ""))
                path.write_bytes(raw)
                results.append(f"✅ write_file {path.as_posix()} ({len(raw)} bytes)")

            # -------------------------
            # APPEND FILE
            # -------------------------
            elif act == "append_file":
                path = safe_path(a["path"])
                path.parent.mkdir(parents=True, exist_ok=True)
                raw = safe_b64decode(a.get("content", ""))
                with open(path, "ab") as f:
                    f.write(raw)
                results.append(f"✅ append_file {path.as_posix()} (+{len(raw)} bytes)")

            # -------------------------
            # READ FILE
            # -------------------------
            elif act == "read_file":
                path = safe_path(a["path"])
                raw = path.read_bytes()
                results.append({
                    "action": "read_file",
                    "path": path.as_posix(),
                    "content": b64encode_bytes(raw),
                    "size": len(raw)
                })

            # -------------------------
            # LIST FILES
            # -------------------------
            elif act == "list_files":
                base = safe_path(a.get("path", "."))
                recursive = a.get("recursive", False)
                files = []

                if recursive:
                    for p in base.rglob("*"):
                        if p.is_file():
                            files.append(p.relative_to(base).as_posix())
                else:
                    for p in base.iterdir():
                        if p.is_file():
                            files.append(p.name)

                results.append({
                    "action": "list_files",
                    "path": base.as_posix(),
                    "files": files
                })

            # -------------------------
            # DELETE FILE
            # -------------------------
            elif act == "delete_file":
                path = safe_path(a["path"])
                path.unlink(missing_ok=True)
                results.append(f"🗑️ delete_file {path.as_posix()}")

            # -------------------------
            # MAKE DIR
            # -------------------------
            elif act == "make_dir":
                path = safe_path(a["path"])
                path.mkdir(parents=True, exist_ok=True)
                results.append(f"📁 make_dir {path.as_posix()}")

            # -------------------------
            # DELETE DIR
            # -------------------------
            elif act == "delete_dir":
                path = safe_path(a["path"])
                shutil.rmtree(path, ignore_errors=True)
                results.append(f"🗑️ delete_dir {path.as_posix()}")

            # -------------------------
            # REPLACE TEXT
            # -------------------------
            elif act == "replace_text":
                path = safe_path(a["path"])
                old = a["old"]
                new = a["new"]

                text = path.read_text(encoding="utf-8", errors="replace")
                text = text.replace(old, new)
                path.write_text(text, encoding="utf-8")

                results.append(f"✏️ replace_text {path.as_posix()}")

            else:
                results.append(f"⚠️ action inconnue: {act}")

        except Exception as e:
            results.append(f"❌ {act} failed: {e}")

    return results

# patcher.py
import re

class PatchError(Exception):
    pass

def apply_unified_diff(original_text: str, diff_text: str) -> str:
    orig_lines = original_text.splitlines(keepends=True)
    diff_lines = diff_text.splitlines(keepends=True)

    out = []
    i = 0
    d = 0

    # skip file headers
    while d < len(diff_lines) and (
        diff_lines[d].startswith("---") or diff_lines[d].startswith("+++")
    ):
        d += 1

    hunk_re = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")

    while d < len(diff_lines):
        line = diff_lines[d]
        m = hunk_re.match(line)
        if not m:
            raise PatchError(f"Invalid patch hunk: {line}")

        orig_start = int(m.group(1))
        target_index = orig_start - 1

        if target_index < i:
            raise PatchError("Overlapping hunks")

        out.extend(orig_lines[i:target_index])
        i = target_index
        d += 1

        while d < len(diff_lines) and not diff_lines[d].startswith("@@"):
            hline = diff_lines[d]

            if hline.startswith(" "):
                expected = hline[1:]
                if i >= len(orig_lines) or orig_lines[i] != expected:
                    raise PatchError("Context mismatch")
                out.append(orig_lines[i])
                i += 1

            elif hline.startswith("-"):
                expected = hline[1:]
                if i >= len(orig_lines) or orig_lines[i] != expected:
                    raise PatchError("Removal mismatch")
                i += 1

            elif hline.startswith("+"):
                out.append(hline[1:])

            elif hline.startswith("\\"):
                pass

            d += 1

    out.extend(orig_lines[i:])
    return "".join(out)

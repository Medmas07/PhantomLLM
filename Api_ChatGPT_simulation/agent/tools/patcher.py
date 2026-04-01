"""
patcher.py – Apply unified diff patches to text files.

Parses the standard unified diff format (as produced by `diff -u` or git)
and applies it to an in-memory string.

Used by the agent when the model emits a patch instead of a full file rewrite,
which is more token-efficient for large file edits.

Raises PatchError with a descriptive message on any mismatch so the model
can be informed and asked to re-generate the patch.
"""

import re


class PatchError(Exception):
    """Raised when a unified diff cannot be applied cleanly."""


def apply_unified_diff(original_text: str, diff_text: str) -> str:
    """
    Apply a unified diff string to original_text.

    Args:
        original_text: The current file content as a string.
        diff_text:     A unified diff (--- / +++ / @@ hunks).

    Returns:
        The patched text as a string.

    Raises:
        PatchError: If any hunk header is invalid, context doesn't match,
                    or removal lines don't match the original.
    """
    orig_lines = original_text.splitlines(keepends=True)
    diff_lines = diff_text.splitlines(keepends=True)

    out: list[str] = []
    i = 0   # cursor into orig_lines
    d = 0   # cursor into diff_lines

    # Skip file header lines (--- original / +++ patched)
    while d < len(diff_lines) and (
        diff_lines[d].startswith("---") or diff_lines[d].startswith("+++")
    ):
        d += 1

    # Pattern: @@ -<start>[,<count>] +<start>[,<count>] @@
    hunk_re = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")

    while d < len(diff_lines):
        line = diff_lines[d]
        m = hunk_re.match(line)
        if not m:
            raise PatchError(f"Invalid hunk header: {line!r}")

        # orig_start is 1-based; convert to 0-based index
        orig_start = int(m.group(1))
        target_index = orig_start - 1

        if target_index < i:
            raise PatchError(
                f"Overlapping hunks: hunk starts at line {orig_start} "
                f"but cursor is already at {i + 1}"
            )

        # Copy all untouched lines before this hunk
        out.extend(orig_lines[i:target_index])
        i = target_index
        d += 1

        # Process individual hunk lines
        while d < len(diff_lines) and not diff_lines[d].startswith("@@"):
            hline = diff_lines[d]

            if hline.startswith(" "):
                # Context line: must match original exactly
                expected = hline[1:]
                if i >= len(orig_lines) or orig_lines[i] != expected:
                    raise PatchError(
                        f"Context mismatch at original line {i + 1}: "
                        f"expected {expected!r}, got {orig_lines[i] if i < len(orig_lines) else '<EOF>'!r}"
                    )
                out.append(orig_lines[i])
                i += 1

            elif hline.startswith("-"):
                # Removal: must match original exactly (then skip it)
                expected = hline[1:]
                if i >= len(orig_lines) or orig_lines[i] != expected:
                    raise PatchError(
                        f"Removal mismatch at original line {i + 1}: "
                        f"expected {expected!r}, got {orig_lines[i] if i < len(orig_lines) else '<EOF>'!r}"
                    )
                i += 1  # consume the line without emitting it

            elif hline.startswith("+"):
                # Addition: emit new line, don't advance orig cursor
                out.append(hline[1:])

            elif hline.startswith("\\"):
                # "\ No newline at end of file" marker – safe to ignore
                pass

            d += 1

    # Copy any remaining lines after the last hunk
    out.extend(orig_lines[i:])
    return "".join(out)
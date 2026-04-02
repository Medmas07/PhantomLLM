"""
base64_utils.py – Base64 encode/decode helpers for the ACTION protocol.

All file content exchanged with the model MUST be base64-encoded.
This ensures binary files survive JSON serialisation without corruption
and avoids prompt-injection via raw file content.
"""

import base64


def safe_b64decode(data: str) -> bytes:
    """
    Decode a base64 string to raw bytes.

    Handles missing padding automatically (common with model output).
    Strips surrounding whitespace before decoding.

    Args:
        data: Base64-encoded ASCII string (may be un-padded).

    Returns:
        Decoded bytes.

    Raises:
        binascii.Error if the input is not valid base64.
    """
    data = data.strip()
    # Re-pad to a multiple of 4 if necessary
    missing = len(data) % 4
    if missing:
        data += "=" * (4 - missing)
    return base64.b64decode(data)


def b64encode_bytes(b: bytes) -> str:
    """
    Encode raw bytes to a base64 ASCII string (no padding issues).

    Args:
        b: Arbitrary bytes.

    Returns:
        URL-safe base64 string (standard alphabet, with '=' padding).
    """
    return base64.b64encode(b).decode("ascii")
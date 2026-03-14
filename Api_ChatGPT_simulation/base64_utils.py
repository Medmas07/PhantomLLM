import base64

def safe_b64decode(data: str) -> bytes:
    data = data.strip()
    missing = len(data) % 4
    if missing:
        data += "=" * (4 - missing)
    return base64.b64decode(data)

def b64encode_bytes(b: bytes) -> str:
    return base64.b64encode(b).decode("ascii")

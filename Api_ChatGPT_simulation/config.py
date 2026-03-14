from pathlib import Path

CHATGPT_URL = "https://chat.openai.com"
PROFILE_DIR = r"C:\Users\medte\AppData\Local\PlaywrightProfile"
CHROME_EXE = r"C:\Program Files\Google\Chrome\Application\chrome.exe"

BASE_DIR = Path(__file__).resolve().parent
WORKSPACE = BASE_DIR / "workspace"
VERSIONS_DIR = WORKSPACE / ".versions"

WORKSPACE.mkdir(exist_ok=True)
VERSIONS_DIR.mkdir(exist_ok=True)

TYPE_DELAY_BASE = 18

POLL_INTERVAL = 0.25
STABLE_ROUNDS = 4
RESPONSE_TIMEOUT = 240

MAX_TOOL_RESULT_CHARS = 12000
MAX_FILE_READ_BYTES = 2_000_000

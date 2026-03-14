from playwright.sync_api import sync_playwright
from config import *
from protocol import SYSTEM_CONTEXT, try_extract_action
from playwright_io import send_message, wait_for_response_bundle
from tools import execute_actions
import time
def main():
    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=PROFILE_DIR,
            executable_path=r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            headless=False,
            slow_mo=100,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--start-maximized",
                "--no-first-run",
                "--no-default-browser-check"
            ]
        )

        page = context.new_page()

        page.add_init_script("""
        Object.defineProperty(navigator, 'webdriver', {
            get: () => undefined
        });
        """)

        page.goto("https://chat.openai.com", timeout=60000)

        print("⏳ Attente Cloudflare...")
        time.sleep(20)

        page.wait_for_selector(
            'div.ProseMirror#prompt-textarea[contenteditable="true"]',
            timeout=60000
        )

        print("🤖 ChatGPT CLI prêt. Tape 'exit' pour quitter.\n")

        prev = page.locator('div[data-message-author-role="assistant"]').count()
        send_message(page, SYSTEM_CONTEXT)
        wait_for_response_bundle(page, prev)

        while True:
            msg = input(">> ").strip()
            if not msg:
                continue
            if msg.lower() in ("exit", "quit"):
                break

            prev_count = page.locator('div[data-message-author-role="assistant"]').count()
            send_message(page, msg)

            response = wait_for_response_bundle(page, prev_count)
            action = try_extract_action(response)

            if action:
                result = execute_actions(action)
                print(result)

                prev = page.locator('div[data-message-author-role="assistant"]').count()
                send_message(page, f"TOOL_RESULT:\n{result}")
                wait_for_response_bundle(page, prev)

if __name__ == "__main__":
    main()
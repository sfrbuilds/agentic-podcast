#!/usr/bin/env python3
"""
spotify_upload.py — Headless Playwright uploader for Spotify for Creators
Called automatically by sharp_money_brief.py after MP3 generation.

Requires:
  pip install playwright --break-system-packages
  playwright install chromium
  playwright install-deps chromium

Session file must exist at /home/ec2-user/spotify_session.json
Run save_spotify_session.py on your Mac once to generate it.
"""

import sys, time, os
from pathlib import Path
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

SHOW_ID      = "YOUR_SHOW_ID"
SESSION_FILE = Path(os.environ.get("SPOTIFY_SESSION_FILE",
    str(Path(__file__).parent / "spotify_session.json")))
SHOW_HOME    = f"https://creators.spotify.com/pod/show/{SHOW_ID}/home"
NEW_EP_URL   = f"https://creators.spotify.com/pod/show/{SHOW_ID}/episodes/new"


def upload_episode(mp3_path: str, title: str, description: str) -> None:
    mp3 = Path(mp3_path)
    if not mp3.exists():
        raise FileNotFoundError(f"MP3 not found: {mp3}")
    if not SESSION_FILE.exists():
        raise RuntimeError("No session file. Run save_spotify_session.py on your Mac first.")

    print(f"  Launching headless browser...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, slow_mo=300)
        context = browser.new_context(
            storage_state=str(SESSION_FILE),
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                       "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        )
        page = context.new_page()

        # ── Step 1: Navigate, handle landing page, reach dashboard ───────────
        print(f"  Navigating to show dashboard...")
        page.goto(SHOW_HOME, wait_until="domcontentloaded", timeout=30_000)
        page.wait_for_load_state("networkidle", timeout=20_000)
        page.wait_for_timeout(2_000)

        # Landing page — click Log In (session persists, no password prompt)
        if page.url.rstrip("/") in ("https://creators.spotify.com",
                                     "https://creators.spotify.com/pod"):
            print("  On landing page — clicking Log In...")
            page.locator('a:has-text("Log in"), button:has-text("Log in"), '
                         'a:has-text("Log In"), button:has-text("Log In")').first.click(timeout=10_000)
            page.wait_for_load_state("networkidle", timeout=20_000)
            page.wait_for_timeout(2_000)

        # Full login form — session truly expired
        if "accounts.spotify.com" in page.url or "login" in page.url.lower():
            browser.close()
            raise RuntimeError("Spotify session expired. Re-run save_spotify_session.py.")

        print(f"  Dashboard ready. Clicking '+ New episode' in sidebar...")
        new_ep_btn = page.locator('a[href*="episodes/new"], a:has-text("New episode"), button:has-text("New episode")').first
        new_ep_btn.wait_for(state="visible", timeout=10_000)
        new_ep_btn.click()
        page.wait_for_load_state("networkidle", timeout=15_000)
        page.wait_for_timeout(2_000)

        # ── Step 2: Upload MP3 ────────────────────────────────────────────────
        print(f"  Uploading {mp3.name} ({mp3.stat().st_size // 1024} KB)...")
        # Wait for page to fully settle before looking for file input
        page.wait_for_load_state("networkidle", timeout=15_000)
        page.wait_for_timeout(2000)

        # Screenshot for debugging if needed
        screenshot = Path(__file__).parent / "spotify_debug.png"

        try:
            # Try visible input first
            file_input = page.locator('input[type="file"]').first
            file_input.wait_for(state="attached", timeout=15_000)
            file_input.set_input_files(str(mp3), timeout=15_000)
        except Exception:
            # Fallback: force on hidden input (Spotify may hide it behind the button)
            try:
                page.locator('input[type="file"]').first.set_input_files(
                    str(mp3), timeout=10_000
                )
            except Exception:
                page.screenshot(path=str(screenshot))
                raise RuntimeError(
                    f"Could not find file input. Screenshot saved to {screenshot}\n"
                    "Check the screenshot to see what the page looks like."
                )

        # Wait for upload to finish — Details section appears
        print("  Waiting for upload to complete (up to 3 min)...")
        page.wait_for_selector(
            'input[placeholder="Give your episode a name"]',
            timeout=180_000
        )
        print("  Upload complete.")
        time.sleep(1)

        # ── Step 3: Title ─────────────────────────────────────────────────────
        print("  Filling title...")
        title_input = page.locator('input[placeholder="Give your episode a name"]').first
        title_input.click()
        title_input.fill(title[:200])

        # ── Step 4: Description (via HTML toggle) ─────────────────────────────
        print("  Filling description...")
        try:
            html_toggle = page.locator('label:has-text("HTML"), button:has-text("HTML"), [aria-label="HTML"]').first
            html_toggle.click(timeout=5_000)
            time.sleep(0.5)
            # Now a textarea should be visible
            desc = page.locator('textarea').last
            desc.fill(description)
        except PWTimeout:
            # Fallback: type directly into the contenteditable editor
            editor = page.locator('[contenteditable="true"]').last
            editor.click()
            editor.fill(description)

        time.sleep(0.5)

        # ── Step 5: Next ──────────────────────────────────────────────────────
        print("  Clicking Next...")
        next_btn = page.locator('button:has-text("Next")').last
        next_btn.click(timeout=10_000)

        # ── Step 6: Review & publish ──────────────────────────────────────────
        print("  On review page — selecting 'Now'...")
        page.wait_for_selector('text=Publish date', timeout=15_000)
        time.sleep(0.5)

        now_label = page.locator('label:has-text("Now")').first
        now_label.click()
        time.sleep(0.5)

        print("  Publishing...")
        publish_btn = page.locator('button:has-text("Publish")').last
        publish_btn.click(timeout=10_000)

        # Wait for confirmation
        page.wait_for_timeout(4_000)
        print(f"  Published: {title}")

        # Persist updated session cookies
        context.storage_state(path=str(SESSION_FILE))
        browser.close()


if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("Usage: python3 spotify_upload.py <mp3_path> <title> <description>")
        sys.exit(1)
    upload_episode(sys.argv[1], sys.argv[2], sys.argv[3])

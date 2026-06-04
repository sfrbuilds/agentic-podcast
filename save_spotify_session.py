#!/usr/bin/env python3
"""
save_spotify_session.py — Run ONCE on your Mac to log into Spotify for Creators
and save the session cookies. Then copy the session file to EC2.

Run on your Mac:
  pip install playwright
  playwright install chromium
  python3 save_spotify_session.py

Then copy to EC2:
  scp -i ~/Desktop/sfrnewnew_0426.pem spotify_session.json \
    ec2-user@54.234.247.10:/home/ec2-user/spotify_session.json
"""

import os
from pathlib import Path
from playwright.sync_api import sync_playwright

SESSION_FILE = Path("spotify_session.json")

SPOTIFY_EMAIL    = "your@email.com"
SPOTIFY_PASSWORD = os.environ.get("SPOTIFY_PASSWORD", "")

if not SPOTIFY_PASSWORD:
    import getpass
    SPOTIFY_PASSWORD = getpass.getpass("Spotify password: ")

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, slow_mo=400)
    context = browser.new_context()
    page    = context.new_page()

    SHOW_URL = "https://creators.spotify.com/pod/show/YOUR_SHOW_ID/home"

    print(f"Navigating to show dashboard...")
    page.goto(SHOW_URL, wait_until="domcontentloaded", timeout=30_000)
    page.wait_for_load_state("networkidle", timeout=20_000)
    page.wait_for_timeout(2_000)

    # Case 1: landed on marketing/landing page — click Log In (session likely persists)
    if page.url.rstrip("/") == "https://creators.spotify.com":
        print("On landing page — clicking Log In...")
        page.locator('a:has-text("Log in"), button:has-text("Log in"), a:has-text("Log In"), button:has-text("Log In")').first.click(timeout=10_000)
        page.wait_for_load_state("networkidle", timeout=20_000)
        page.wait_for_timeout(2_000)
        print(f"After login click URL: {page.url}")

    # Case 2: redirected to Spotify accounts login — fill credentials
    if "accounts.spotify.com" in page.url or "login" in page.url.lower():
        print("Login form shown — filling credentials...")
        page.locator('input[data-testid="login-username"], input[name="username"], input[id="login-username"]').first.fill(SPOTIFY_EMAIL)
        page.locator('input[data-testid="login-password"], input[name="password"], input[id="login-password"]').first.fill(SPOTIFY_PASSWORD)
        page.locator('button[data-testid="login-button"], button[id="login-button"], button:has-text("Log in")').first.click()
        print("(Complete any verification in the browser window if prompted)")
        page.wait_for_url("**/pod/show/**", timeout=60_000)
        page.wait_for_load_state("networkidle", timeout=20_000)
        page.wait_for_timeout(2_000)

    print(f"Session active. URL: {page.url}")
    context.storage_state(path=str(SESSION_FILE))
    browser.close()

print(f"\nSession saved to {SESSION_FILE.resolve()}")
print("\nNow copy it to EC2:")
print(f"  scp -i ~/Desktop/sfrnewnew_0426.pem spotify_session.json \\")
print(f"    ec2-user@54.234.247.10:/home/ec2-user/spotify_session.json")

"""
Naukri.com Auto Apply Script — Playwright (Python)
====================================================
Author  : Built for Raju Kumar
Stack   : MERN / Full Stack Developer
Usage   : python naukri_auto_apply.py

Setup:
  pip install playwright
  playwright install chromium
"""

import asyncio
import csv
import os
import random
import time
from datetime import datetime
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout

# ─────────────────────────────────────────────
#  CONFIG — Edit these before running
# ─────────────────────────────────────────────
NAUKRI_EMAIL    = "rajukumar957259@gmail.com"   # Your Naukri login email
NAUKRI_PASSWORD = "R0011121@naukari.com"           # Your Naukri password

SEARCH_KEYWORDS = "MERN Stack Developer"         # Job search query
SEARCH_LOCATION = "India"                         # City (leave "" for all India)
EXPERIENCE      = "2"                             # Years of experience (min)

MAX_APPLIES_PER_RUN = 10                          # Max jobs to apply per session
RESUME_PATH     = r"C:\document wgera\Raju_kumar_sde_resume (5).pdf" # Full path to your resume PDF

LOG_FILE        = "apply_log.csv"                 # Log of all applied jobs

# ─────────────────────────────────────────────
#  HELPERS
# ─────────────────────────────────────────────

def human_delay(min_sec=1.5, max_sec=3.5):
    time.sleep(random.uniform(min_sec, max_sec))

def log_application(company, role, status, url):
    file_exists = os.path.isfile(LOG_FILE)
    with open(LOG_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["Date", "Company", "Role", "Status", "URL"])
        writer.writerow([datetime.now().strftime("%Y-%m-%d %H:%M"), company, role, status, url])
    icon = "✅" if "APPLIED" in status else "⚠️" if "SKIP" in status else "❌"
    print(f"  {icon} [{status}] {company} — {role}")

async def fill_input_robust(page, value, selectors):
    """Try multiple selectors to fill an input — returns True if any works."""
    for selector in selectors:
        try:
            el = page.locator(selector).first
            await el.wait_for(state="visible", timeout=5000)
            await el.fill(value)
            return True
        except Exception:
            continue
    return False

# ─────────────────────────────────────────────
#  LOGIN  (robust — handles Naukri UI changes)
# ─────────────────────────────────────────────

async def login(page):
    print("🔐 Opening Naukri login page...")
    await page.goto("https://www.naukri.com/nlogin/login", wait_until="domcontentloaded")
    human_delay(2, 3)

    email_selectors = [
        "input#usernameField",
        "input[name='username']",
        "input[type='email']",
        "input[placeholder*='Email']",
        "input[placeholder*='email']",
        "input[placeholder*='Username']",
        "input[placeholder*='active Email']",
    ]
    password_selectors = [
        "input#passwordField",
        "input[name='password']",
        "input[type='password']",
        "input[placeholder*='Password']",
        "input[placeholder*='password']",
    ]

    print("  Filling email...")
    if not await fill_input_robust(page, NAUKRI_EMAIL, email_selectors):
        await page.screenshot(path="debug_login.png")
        print("  ❌ Email field not found. Screenshot saved: debug_login.png")
        print("     Open debug_login.png to see what the page looks like, then update selectors.")
        return False

    human_delay(0.5, 1)

    print("  Filling password...")
    if not await fill_input_robust(page, NAUKRI_PASSWORD, password_selectors):
        await page.screenshot(path="debug_login.png")
        print("  ❌ Password field not found. Screenshot saved: debug_login.png")
        return False

    human_delay(0.5, 1)

    # Submit
    submit_selectors = [
        "button[type='submit']",
        "input[type='submit']",
        "button:has-text('Login')",
        "button:has-text('Sign in')",
        ".loginButton",
        "#loginBtn",
    ]
    submitted = False
    for sel in submit_selectors:
        try:
            btn = page.locator(sel).first
            await btn.wait_for(state="visible", timeout=3000)
            await btn.click()
            submitted = True
            break
        except Exception:
            continue

    if not submitted:
        await page.screenshot(path="debug_login.png")
        print("  ❌ Submit button not found. Screenshot saved: debug_login.png")
        return False

    # Wait for redirect
    try:
        await page.wait_for_url("**/mnjuser/homepage**", timeout=15000)
        print("✅ Login successful!\n")
        return True
    except PlaywrightTimeout:
        if "naukri.com" in page.url and "login" not in page.url:
            print("✅ Login successful!\n")
            return True
        await page.screenshot(path="debug_after_login.png")
        print("❌ Login failed — wrong credentials or CAPTCHA appeared.")
        print("   Screenshot saved: debug_after_login.png")
        return False

# ─────────────────────────────────────────────
#  APPLY TO JOBS
# ─────────────────────────────────────────────

async def apply_to_jobs(page, context):
    keyword_slug  = SEARCH_KEYWORDS.lower().replace(" ", "-")
    location_part = f"-in-{SEARCH_LOCATION.lower()}" if SEARCH_LOCATION else ""
    search_url    = (
        f"https://www.naukri.com/{keyword_slug}-jobs"
        f"{location_part}"
        f"?experience={EXPERIENCE}"
    )

    print(f"🔍 Searching: {search_url}\n")
    await page.goto(search_url, wait_until="domcontentloaded")
    human_delay(2, 4)

    # Collect job links
    job_links = []
    link_selectors = [
        "article.jobTuple a.title",
        "div.srp-jobtuple-wrapper a.title",
        "a.jobTitle",
        "div.job-title a",
        "a[href*='/job-listings-']",
    ]
    for sel in link_selectors:
        elements = await page.query_selector_all(sel)
        if elements:
            for el in elements:
                href  = await el.get_attribute("href")
                title = (await el.inner_text()).strip()
                if href and href not in [j["url"] for j in job_links]:
                    job_links.append({"title": title, "url": href})
            break

    if not job_links:
        await page.screenshot(path="debug_search.png")
        print("⚠️  No job listings found. Screenshot saved: debug_search.png")
        return

    print(f"📋 Found {len(job_links)} jobs. Applying to max {MAX_APPLIES_PER_RUN}...\n")
    applied_count = 0

    for job in job_links:
        if applied_count >= MAX_APPLIES_PER_RUN:
            print(f"\n🎯 Reached daily limit of {MAX_APPLIES_PER_RUN}.")
            break

        job_url   = job["url"]
        job_title = job["title"]
        print(f"\n➡️  {job_title}")

        job_page     = await context.new_page()
        company_name = "Unknown"

        try:
            await job_page.goto(job_url, wait_until="domcontentloaded")
            human_delay(2, 3)

            # Get company name
            for sel in ["a.comp-name", ".company-name a", "span.comp-name", ".jd-header-comp-name"]:
                el = await job_page.query_selector(sel)
                if el:
                    company_name = (await el.inner_text()).strip()
                    break

            # Already applied?
            already = await job_page.query_selector(
                "div.already-applied, span.alreadyApplied, .applied-text"
            )
            if already:
                log_application(company_name, job_title, "ALREADY APPLIED", job_url)
                await job_page.close()
                continue

            # Find Apply button
            apply_btn = None
            for sel in [
                "button#apply-button", "button.apply-button", "div#apply-button",
                "button:has-text('Apply')", "button:has-text('Apply Now')",
                "button:has-text('Easy Apply')", "#applyButton",
            ]:
                try:
                    btn = job_page.locator(sel).first
                    await btn.wait_for(state="visible", timeout=3000)
                    apply_btn = btn
                    break
                except Exception:
                    continue

            if not apply_btn:
                log_application(company_name, job_title, "SKIPPED - No Apply button", job_url)
                await job_page.close()
                continue

            await apply_btn.click()
            human_delay(2, 3)

            # Confirm modal
            for confirm_sel in ["button.confirm-btn", "button#confirm-apply", "button:has-text('Submit')"]:
                try:
                    confirm = job_page.locator(confirm_sel).first
                    await confirm.wait_for(state="visible", timeout=3000)
                    await confirm.click()
                    human_delay(1.5, 2.5)
                    break
                except Exception:
                    continue

            log_application(company_name, job_title, "APPLIED ✅", job_url)
            applied_count += 1
            await job_page.close()
            human_delay(4, 7)

        except Exception as e:
            print(f"  ❌ Error: {e}")
            log_application(company_name, job_title, f"ERROR: {str(e)[:80]}", job_url)
            try:
                await job_page.close()
            except Exception:
                pass

    print(f"\n🎉 Done! Applied to {applied_count} jobs.")
    print(f"📄 Log saved: {os.path.abspath(LOG_FILE)}")

# ─────────────────────────────────────────────
#  MAIN
# ─────────────────────────────────────────────

async def run():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False, slow_mo=60)
        context = await browser.new_context(
            viewport={"width": 1280, "height": 800},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/122.0.0.0 Safari/537.36"
            )
        )
        page = await context.new_page()

        login_ok = await login(page)
        if not login_ok:
            print("\n⛔ Stopping — login failed.")
            await browser.close()
            return

        human_delay(2, 3)
        await apply_to_jobs(page, context)

        print("\nPress Enter to close browser...")
        input()
        await browser.close()


if __name__ == "__main__":
    asyncio.run(run())
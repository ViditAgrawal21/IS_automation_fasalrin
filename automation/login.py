"""
Login automation for the Fasal Rin portal (IS Claim Automation).

Flow:
  1. Open /login page
  2. Instantly fill username & password via JavaScript
  3. Wait for user to manually enter captcha and click Login in the browser
  4. Poll for redirect to /welcome URL
  5. Immediately navigate to /claim-application-list
"""

from utils.constants import LOGIN_URL, CLAIM_LIST_URL
from automation.browser import save_session


def perform_login(page, context, profile: dict, profile_name: str,
                  captcha_callback=None, log_callback=None):
    """
    Perform portal login.
    Auto-fills username & password instantly.
    User manually enters captcha and clicks Login in the browser.
    Detects /welcome redirect and proceeds to claim application list.
    """
    def log(msg):
        if log_callback:
            log_callback(msg)

    # ── Already logged in? Skip entirely ──
    current_url = page.url
    if "/welcome" in current_url or "/dashboard" in current_url or "/claim-application" in current_url:
        log("Already logged in — skipping login")
        page.goto(CLAIM_LIST_URL, wait_until="domcontentloaded")
        return True

    # ── Navigate to login page ──
    log("Opening login page...")
    page.goto(LOGIN_URL, wait_until="domcontentloaded")
    page.wait_for_timeout(300)

    # Check if session cookies made us already logged in
    if "/welcome" in page.url or "/dashboard" in page.url:
        log("Session active — already logged in")
        page.goto(CLAIM_LIST_URL, wait_until="domcontentloaded")
        return True

    # Server may redirect /login → / (SPA routing issue).
    if "/login" not in page.url:
        log("Server redirected to homepage — triggering client-side /login route...")
        page.evaluate("""() => {
            window.history.pushState({}, '', '/login');
            window.dispatchEvent(new PopStateEvent('popstate'));
        }""")
        page.wait_for_timeout(500)

        if "/login" not in page.url:
            page.evaluate("window.location.hash = '#/login'")
            page.wait_for_timeout(400)

    log("On login page")

    # ── Instant-fill username via JavaScript ──
    try:
        page.evaluate("""(username) => {
            const el = document.querySelector("input[name='username']")
                     || document.querySelector("input[name='userName']")
                     || document.querySelector("input[type='text']");
            if (el) {
                const setter = Object.getOwnPropertyDescriptor(
                    window.HTMLInputElement.prototype, 'value').set;
                setter.call(el, username);
                el.dispatchEvent(new Event('input', { bubbles: true }));
                el.dispatchEvent(new Event('change', { bubbles: true }));
            }
        }""", profile["username"])
        log("Username filled")
    except Exception as e:
        raise Exception(f"Could not fill username: {e}")

    # ── Instant-fill password via JavaScript ──
    try:
        page.evaluate("""(password) => {
            const el = document.querySelector("input[name='password']")
                     || document.querySelector("input[type='password']");
            if (el) {
                const setter = Object.getOwnPropertyDescriptor(
                    window.HTMLInputElement.prototype, 'value').set;
                setter.call(el, password);
                el.dispatchEvent(new Event('input', { bubbles: true }));
                el.dispatchEvent(new Event('change', { bubbles: true }));
            }
        }""", profile["password"])
        log("Password filled")
    except Exception as e:
        raise Exception(f"Could not fill password: {e}")

    # ── Wait for user to enter captcha + click Login manually ──
    log("Waiting for manual captcha entry & login click in browser...")

    try:
        page.wait_for_url("**/welcome**", timeout=120000)
    except Exception:
        if "/welcome" not in page.url and "/dashboard" not in page.url and "/claim-application" not in page.url:
            raise Exception(
                "Login timed out (2 min). Please enter captcha and click Login in the browser."
            )

    log("Login successful!")

    # ── Save session & navigate to claim application list ──
    save_session(context, profile_name)
    log("Navigating to Claim Application List...")
    page.goto(CLAIM_LIST_URL, wait_until="domcontentloaded")
    log("Ready — on Claim Application List page")
    return True

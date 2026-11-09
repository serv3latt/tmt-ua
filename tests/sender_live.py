"""Runs dev sessions against the REAL receiver (tasks T0.3, T0.5, T0.6).

Not part of the automatic test run: it writes rows into the PILOT storage
(mode=dev). Prints the session ids; then compare the pilot spreadsheet with
the expectations printed at the end. Run from the app/ folder:

    ../.venv/bin/python tests/sender_live.py
"""

import functools
import http.server
import threading

from playwright.sync_api import sync_playwright

from harness import APP_DIR, RECEIVER_GLOB, QuietHandler


def click_through(page, count):
    for _ in range(count):
        page.locator(".placeholder").wait_for()
        text = page.locator(".placeholder").text_content()
        page.get_by_role("button", name="Далі").click()
        page.wait_for_function("t => document.querySelector('.placeholder')?.textContent !== t", arg=text)


def calibrate(page, card_px=380):
    handle = page.locator("#jspsych-resize-handle")
    box = handle.bounding_box()
    x, y = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
    page.mouse.move(x, y)
    page.mouse.down()
    page.mouse.move(x + (card_px - 250) / 2, y, steps=5)
    page.mouse.up()
    page.get_by_role("button", name="Готово: розмір збігається").click()


def wait_delivered(page):
    page.wait_for_function("() => window.tmtua.sender.pending() === 0", timeout=120_000)


def main():
    handler = functools.partial(QuietHandler, directory=APP_DIR)
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{server.server_port}/"
    report = []

    with sync_playwright() as pw:
        for browser_type in (pw.chromium, pw.webkit):
            browser = browser_type.launch()
            name = browser_type.name

            # 1. Whole session, connection drops after 7 messages and comes
            # back. device_check shows no screen on a desktop and sends nothing.
            context = browser.new_context()
            page = context.new_page()
            page.goto(base + "?mode=dev&start=device_check")
            session_id = page.evaluate("window.tmtua.ids.session_id")
            click_through(page, 4)  # consent .. conditions
            calibrate(page)
            page.locator(".dev-square").wait_for()  # the 100 mm square, dev only
            page.get_by_role("button", name="Далі").click()
            page.get_by_role("button", name="Увімкнути повноекранний режим").click()
            click_through(page, 1)  # tmt_a
            wait_delivered(page)
            context.set_offline(True)
            click_through(page, 7)  # tmt_b .. retest_invite
            page.get_by_role("button", name="Далі").click()  # last block
            page.locator(".dev-end").wait_for()
            queued = page.evaluate("window.tmtua.sender.pending()")
            context.set_offline(False)
            wait_delivered(page)
            report.append(f"{name}: full session {session_id} (8 blocks queued offline: {queued == 8})")
            context.close()

            # 2. fetch blocked, page left: only the beacon can deliver.
            context = browser.new_context()
            context.route(RECEIVER_GLOB, lambda route: route.abort()
                          if route.request.resource_type == "fetch" else route.continue_())
            page = context.new_page()
            page.goto(base + "?mode=dev&only=tmt_a")
            session_id = page.evaluate("window.tmtua.ids.session_id")
            page.get_by_role("button", name="Далі").click()
            page.locator(".dev-end").wait_for()
            page.goto("about:blank")
            page.wait_for_timeout(8000)  # the receiver needs a few seconds
            report.append(f"{name}: beacon only {session_id}")
            context.close()
            browser.close()

    server.shutdown()
    print("\n".join(report))
    print("""
Expected in the pilot sessions sheet:
- each "full session" id: one row, 13 *_placeholder columns equal to 1,
  px_per_mm 4.4393, calibration_card_px 380, calibration_attempts 1,
  calibration_suspect 0, screen_w_mm 288.3, screen_h_mm 162.2,
  fullscreen_status "entered", fullscreen_view_w_mm / _h_mm filled,
  fullscreen_window_checks 0, no status column value, device_* columns filled (device_any_pointer_fine
  among them), session_type "first", last_block "thanks"; for each of tmt_a,
  tmt_b, coding, stroop, sart nine columns <task>_hidden_n, _hidden_ms,
  _blur_n, _blur_ms, _fs_exit_n, _fs_exit_ms, _resize_n, _zoom_n, _touch_n,
  all 0 (a headless browser has nothing to leave); in the session's log
  folder calibration.json with the attempts and a JSON file per task with "env" inside
- each "beacon only" id: one row with tmt_a_placeholder = 1 and tmt_a_* env columns""")


if __name__ == "__main__":
    main()

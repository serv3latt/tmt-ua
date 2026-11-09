"""Checks of task T0.6 in Chromium and WebKit: screen calibration with a card
(virtual-chinrest), the redo of a suspect result (decision 100), the check
that the screen and then the window hold the task area (decision 101), the
early end with screen_too_small, and the zoom check against the calibration.
How true the 100 mm square is on real screens is measured by hand.
"""

import unittest

from playwright.sync_api import expect

from harness import AppTestCase

FAST = "&set.send.retryBaseMs=100&set.send.retryMaxMs=500"
DONE = "Готово: розмір збігається"
ENTER = "Увімкнути повноекранний режим"
RECHECK = "Перевірити ще раз"
PX_PER_MM = 380 / 85.6  # the harness's default card


class CalibrationTestCase(AppTestCase):
    def texts(self, page):
        return self.module(page, "texts.uk.js")["texts"]

    def message(self, receiver, block):
        [message] = [m for m in receiver.accepted if m["block"] == block]
        return message

    def next(self, page):
        page.get_by_role("button", name="Далі").click()


class CalibrationTest(CalibrationTestCase):
    def test_rules(self):
        page, _ = self.open(self.browsers[0], "?mode=dev")
        params = {"screenWidthMinMm": 180, "screenWidthMaxMm": 900}
        cases = [
            (380, 1470, None),  # 15" MacBook Air
            (250, 1470, "unchanged"),
            (1000, 1280, "implausible_screen"),  # implies a 110 mm wide screen
            (90, 1920, "implausible_screen"),  # implies 1.8 m
            (320, 1920, None),  # 24" monitor, 3.74 px/mm
        ]
        for card_px, screen_px, expected in cases:
            got = page.evaluate(
                "([c, s, p]) => import('./src/tasks/calibration.js').then(m => m.calibrationProblem(c, s, p))",
                [card_px, screen_px, params])
            self.assertEqual(got, expected, (card_px, screen_px))
        screen = {"minWidthMm": 240, "minHeightMm": 150}
        for w, h, expected in [(1470, 923, True), (1066, 666, True), (1065, 666, False), (1280, 665, False)]:
            got = page.evaluate(
                "([w, h, k, s]) => import('./src/tasks/calibration.js').then(m => m.holdsTasks(w, h, k, s))",
                [w, h, 4.44, screen])
            self.assertEqual(got, expected, (w, h))

    def test_card_sets_the_scale_and_the_square(self):
        for browser in self.browsers:
            with self.subTest(browser=browser.browser_type.name):
                context, receiver = self.new_context(browser)
                page, errors = self.open(browser, "?mode=dev&start=calibration" + FAST, context=context)
                self.calibrate(page, 380)
                square = page.locator(".dev-square")
                expect(square).to_be_visible()
                box = square.bounding_box()
                self.assertAlmostEqual(box["width"], 100 * PX_PER_MM, delta=1)
                self.assertAlmostEqual(box["height"], 100 * PX_PER_MM, delta=1)
                self.next(page)
                page.get_by_role("button", name=ENTER).click()
                page.locator(".placeholder", has_text="TMT, частина A").wait_for()
                self.next(page)
                page.locator(".placeholder", has_text="TMT, частина B").wait_for()
                self.wait_delivered(page)

                calibration = self.message(receiver, "calibration")
                summary = calibration["summary"]
                self.assertEqual(summary["px_per_mm"], round(PX_PER_MM, 4))
                self.assertEqual(summary["calibration_card_px"], 380)
                self.assertEqual(summary["calibration_attempts"], 1)
                self.assertEqual(summary["calibration_suspect"], 0)
                self.assertEqual(summary["calibration_dpr"], 1)
                self.assertEqual(summary["screen_w_mm"], round(1280 / PX_PER_MM, 1))
                self.assertEqual(summary["screen_h_mm"], round(720 / PX_PER_MM, 1))
                self.assertNotIn("status", summary)
                self.assertEqual(calibration["log"]["attempts"][0]["card_px"], 380)
                fullscreen = self.message(receiver, "fullscreen")["summary"]
                self.assertEqual(fullscreen["fullscreen_view_w_mm"], round(1280 / PX_PER_MM, 1))
                self.assertEqual(fullscreen["fullscreen_window_checks"], 0)
                self.assertEqual(self.message(receiver, "tmt_a")["summary"]["tmt_a_zoom_n"], 0)
                self.assert_valid_for_receiver(context, receiver.accepted)
                self.assertEqual(errors, [])

    def test_untouched_card_is_asked_again_then_marked(self):
        for browser in self.browsers:
            with self.subTest(browser=browser.browser_type.name):
                context, receiver = self.new_context(browser)
                page, errors = self.open(browser, "?mode=dev&only=calibration" + FAST, context=context)
                texts = self.texts(page)
                warning = page.locator(".screen-warning")
                expect(page.get_by_role("button", name=DONE)).to_be_visible()
                self.assertEqual(warning.count(), 0)
                page.get_by_role("button", name=DONE).click()  # without touching the card
                expect(warning).to_be_visible()
                self.assertIn(warning.inner_text(), texts["calibration"]["retry"])
                page.get_by_role("button", name=DONE).click()  # again: the session goes on, marked
                page.locator(".dev-square").wait_for()
                self.next(page)
                self.wait_delivered(page)
                summary = self.message(receiver, "calibration")["summary"]
                self.assertEqual(summary["calibration_attempts"], 2)
                self.assertEqual(summary["calibration_suspect"], 1)
                self.assertEqual(summary["calibration_card_px"], 250)
                self.assertEqual(errors, [])

    def test_redone_card_is_accepted(self):
        for browser in self.browsers:
            with self.subTest(browser=browser.browser_type.name):
                context, receiver = self.new_context(browser)
                page, errors = self.open(browser, "?mode=dev&only=calibration" + FAST, context=context)
                self.calibrate(page, 1000)  # implies a 110 mm wide screen
                expect(page.locator(".screen-warning")).to_be_visible()
                self.calibrate(page, 380)
                page.locator(".dev-square").wait_for()
                self.next(page)
                self.wait_delivered(page)
                message = self.message(receiver, "calibration")
                self.assertEqual(message["summary"]["calibration_attempts"], 2)
                self.assertEqual(message["summary"]["calibration_suspect"], 0)
                self.assertEqual(message["summary"]["calibration_card_px"], 380)
                self.assertEqual([a["problem"] for a in message["log"]["attempts"]],
                                 ["implausible_screen", None])
                self.assertEqual(errors, [])


class ScreenSizeTest(CalibrationTestCase):
    def test_small_screen_ends_the_session(self):
        # A pilot session as a participant sees it, on a 180 x 113 mm screen.
        for browser in self.browsers:
            with self.subTest(browser=browser.browser_type.name):
                context, receiver = self.new_context(browser, viewport={"width": 800, "height": 500})
                page, errors = self.open(browser, "?mode=pilot", context=context)
                texts = self.texts(page)
                for block in self.session_blocks(page)[:6]:  # device check .. calibration
                    self.pass_block(page, *block)
                expect(page.locator(".message")).to_have_text(texts["end"]["screen_too_small"],
                                                              timeout=15000)
                self.assertEqual(receiver.blocks(), ["consent", "criteria", "demographics",
                                                     "conditions", "calibration"])
                summary = self.message(receiver, "calibration")["summary"]
                self.assertEqual(summary["status"], "screen_too_small")
                self.assertEqual(summary["screen_w_mm"], round(800 / PX_PER_MM, 1))
                self.assertEqual(errors, [])

    def test_too_small_in_dev_shows_the_status(self):
        for browser in self.browsers:
            with self.subTest(browser=browser.browser_type.name):
                context, receiver = self.new_context(browser)
                page, errors = self.open(
                    browser, "?mode=dev&start=calibration&set.screen.minWidthMm=400" + FAST, context=context)
                self.calibrate(page)
                expect(page.locator(".dev-status")).to_have_text("screen_too_small")
                self.assertEqual(page.locator(".dev-square").count(), 0)
                self.wait_delivered(page)
                self.assertEqual(receiver.blocks(), ["calibration"])
                self.assertEqual(errors, [])

    def window_without_fullscreen(self, browser):
        """Fullscreen refused; the screen holds the task area, the window
        (288 x 135 mm at the default card) does not."""
        refuse = "Element.prototype.requestFullscreen = () => Promise.reject(new TypeError('refused'));"
        context, receiver = self.new_context(browser, init_script=refuse,
                                             viewport={"width": 1280, "height": 600},
                                             screen={"width": 1920, "height": 1080})
        page, errors = self.open(browser, "?mode=dev&start=calibration" + FAST, context=context)
        self.calibrate(page)
        self.next(page)  # the 100 mm square
        page.get_by_role("button", name=ENTER).click()
        expect(page.locator(".screen")).to_contain_text("не дав увімкнути")
        self.next(page)
        expect(page.locator(".screen")).to_contain_text("Вікно браузера замале")
        return context, receiver, page, errors

    def test_window_made_bigger_goes_on(self):
        for browser in self.browsers:
            with self.subTest(browser=browser.browser_type.name):
                context, receiver, page, errors = self.window_without_fullscreen(browser)
                page.get_by_role("button", name=RECHECK).click()  # still too small
                expect(page.locator(".screen")).to_contain_text("Вікно браузера замале")
                page.set_viewport_size({"width": 1280, "height": 720})
                page.get_by_role("button", name=RECHECK).click()
                page.locator(".placeholder", has_text="TMT, частина A").wait_for()
                self.wait_delivered(page)
                summary = self.message(receiver, "fullscreen")["summary"]
                self.assertEqual(summary["fullscreen_status"], "failed")
                self.assertEqual(summary["fullscreen_window_checks"], 2)
                self.assertEqual(summary["fullscreen_view_h_mm"], round(720 / PX_PER_MM, 1))
                self.assertNotIn("status", summary)
                self.assertEqual(errors, [])

    def test_window_still_too_small_ends_after_three_checks(self):
        for browser in self.browsers:
            with self.subTest(browser=browser.browser_type.name):
                context, receiver, page, errors = self.window_without_fullscreen(browser)
                for _ in range(3):
                    page.get_by_role("button", name=RECHECK).click()
                expect(page.locator(".dev-status")).to_have_text("screen_too_small")
                self.wait_delivered(page)
                summary = self.message(receiver, "fullscreen")["summary"]
                self.assertEqual(summary["status"], "screen_too_small")
                self.assertEqual(summary["fullscreen_window_checks"], 3)
                self.assertNotIn("tmt_a", receiver.blocks())
                self.assertEqual(errors, [])


class ZoomSinceCalibrationTest(CalibrationTestCase):
    def test_task_started_at_another_scale_counts_a_zoom(self):
        zoom = "Object.defineProperty(window, 'devicePixelRatio', { configurable: true, get: () => 2 });"
        for browser in self.browsers:
            with self.subTest(browser=browser.browser_type.name):
                context, receiver = self.new_context(browser)
                page, errors = self.open(browser, "?mode=dev&start=calibration" + FAST, context=context)
                self.calibrate(page)
                self.next(page)
                page.evaluate(zoom)  # zoomed between calibration and the first task
                page.get_by_role("button", name=ENTER).click()
                page.locator(".placeholder", has_text="TMT, частина A").wait_for()
                self.next(page)
                page.locator(".placeholder", has_text="TMT, частина B").wait_for()
                self.wait_delivered(page)
                a = self.message(receiver, "tmt_a")
                self.assertEqual(a["summary"]["tmt_a_zoom_n"], 1)
                [event] = [e for e in a["log"]["env"]["events"] if e["type"] == "zoom"]
                self.assertTrue(event["at_start"] and event["since_calibration"])
                self.assertEqual(event["dpr"], 2)
                self.assertEqual(errors, [])


if __name__ == "__main__":
    unittest.main()

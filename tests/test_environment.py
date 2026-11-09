"""Checks of task T0.5 in Chromium and WebKit: turning phones and tablets
away, fullscreen with its banner and gate, and the monitor that records what
happens around each task (leaving the tab, focus, fullscreen, resizing, zoom,
touch). Leaving the tab and focus are simulated with synthetic events: a
headless browser has no other windows to switch to. Real switching, Safari's
fullscreen and its keyboard are checked by hand on the dev page
?mode=dev&tool=env.
"""

import unittest

from playwright.sync_api import expect

from harness import AppTestCase

FAST = "&set.send.retryBaseMs=100&set.send.retryMaxMs=500"
ENTER = "Увімкнути повноекранний режим"
RETURN = "Повернутися в повноекранний режим"
TASK_IDS = ["tmt_a", "tmt_b", "coding", "stroop", "sart"]
MAC_SAFARI_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
                 "(KHTML, like Gecko) Version/26.0 Safari/605.1.15")

SET_VISIBILITY = """hidden => {
    Object.defineProperty(document, 'visibilityState', {
        configurable: true, get: () => hidden ? 'hidden' : 'visible' });
    Object.defineProperty(document, 'hidden', { configurable: true, get: () => hidden });
    document.dispatchEvent(new Event('visibilitychange'));
}"""
IS_FULLSCREEN = "() => document.fullscreenElement !== null"


class EnvironmentTestCase(AppTestCase):
    def texts(self, page):
        return self.module(page, "texts.uk.js")["texts"]

    def summary_of(self, receiver, block):
        [message] = [m for m in receiver.accepted if m["block"] == block]
        return message["summary"], message.get("log")

    def placeholder(self, page, label):
        page.locator(".placeholder", has_text=label).wait_for()

    def next(self, page):
        page.get_by_role("button", name="Далі").click()


class DeviceCheckTest(EnvironmentTestCase):
    def test_rules(self):
        page, _ = self.open(self.browsers[0], "?mode=dev")
        cases = [
            ("macOS", 1, None),
            ("Windows", 1, None),  # also a touchscreen laptop: it has a touchpad
            ("Linux", 1, None),
            ("ChromeOS", 1, None),
            ("Windows", 0, "no_cursor"),  # tablet without keyboard
            ("Linux", 0, "no_cursor"),  # Android tablet asking for the desktop site
            ("iOS", 0, "mobile_os"),
            ("iPadOS", 1, "mobile_os"),  # iPad with a trackpad
            ("Android", 1, "mobile_os"),  # phone with a mouse
        ]
        for os_name, fine, expected in cases:
            info = {"device_os": os_name, "device_any_pointer_fine": fine}
            got = page.evaluate(
                "info => import('./src/data/device.js').then(m => m.deviceRejection(info))", info)
            self.assertEqual(got, expected, info)

    def test_phones_and_tablets_are_turned_away(self):
        ipad_as_mac = {"user_agent": MAC_SAFARI_UA, "has_touch": True,
                       "viewport": {"width": 1180, "height": 820}}
        touch_points = "Object.defineProperty(Navigator.prototype, 'maxTouchPoints', { get: () => 5 });"
        for browser in self.browsers:
            for name in ["iPhone 13", "iPad Pro 11", "Pixel 5", "iPad that says it is a Mac"]:
                with self.subTest(browser=browser.browser_type.name, device=name):
                    if name in self.pw.devices:
                        context, receiver = self.new_context(browser, **self.pw.devices[name])
                    else:
                        context, receiver = self.new_context(browser, init_script=touch_points, **ipad_as_mac)
                    page, errors = self.open(browser, "?mode=pilot", context=context)
                    texts = self.texts(page)
                    expect(page.locator(".screen")).to_be_visible()
                    self.assertEqual(page.locator(".screen").inner_html(), texts["device"]["rejected"])
                    self.assertEqual(page.get_by_role("button").count(), 0)
                    page.wait_for_timeout(500)
                    self.assertEqual(receiver.requests, [])  # nothing recorded (decision 97)
                    self.assertEqual(errors, [])

    def test_desktop_goes_straight_to_consent(self):
        for browser in self.browsers:
            with self.subTest(browser=browser.browser_type.name):
                page, errors = self.open(browser, "?mode=pilot")
                self.placeholder(page, "Згода")
                self.assertEqual(page.locator(".screen").count(), 0)
                self.assertEqual(errors, [])


class FullscreenTest(EnvironmentTestCase):
    def test_banner_gate_and_exit_at_the_end(self):
        for browser in self.browsers:
            with self.subTest(browser=browser.browser_type.name):
                context, receiver = self.new_context(browser)
                page, errors = self.open(browser, "?mode=dev&start=fullscreen" + FAST, context=context)
                banner = page.locator(".fs-banner")
                page.get_by_role("button", name=ENTER).click()
                self.placeholder(page, "TMT, частина A")
                self.assertTrue(page.evaluate(IS_FULLSCREEN))
                expect(banner).to_be_hidden()

                # Leaving fullscreen mid-task: the task goes on, the banner brings it back.
                page.evaluate("document.exitFullscreen()")
                expect(banner).to_be_visible()
                page.wait_for_timeout(300)
                banner.get_by_role("button", name=RETURN).click()
                expect(banner).to_be_hidden()
                self.assertTrue(page.evaluate(IS_FULLSCREEN))
                self.placeholder(page, "TMT, частина A")  # the click did not end the task

                # Leaving it again: the next task waits behind the gate.
                page.evaluate("document.exitFullscreen()")
                expect(banner).to_be_visible()
                self.next(page)
                expect(page.locator(".screen")).to_contain_text("Повноекранний режим вимкнувся")
                expect(banner).to_be_hidden()  # the gate is between tasks, not in one
                page.get_by_role("button", name=RETURN).click()
                self.placeholder(page, "TMT, частина B")
                self.assertTrue(page.evaluate(IS_FULLSCREEN))

                for label in ["TMT, частина B", "Кодування символів", "Stroop", "SART", "PSS-10",
                              "Питання після тесту", "Запрошення на ретест", "Подяка"]:
                    self.placeholder(page, label)
                    self.next(page)
                expect(page.locator(".dev-end")).to_be_visible()
                page.wait_for_function("() => document.fullscreenElement === null")
                self.wait_delivered(page)

                summary, _ = self.summary_of(receiver, "fullscreen")
                self.assertEqual(summary["fullscreen_status"], "entered")
                a, log = self.summary_of(receiver, "tmt_a")
                self.assertEqual(a["tmt_a_fs_exit_n"], 2)
                self.assertGreater(a["tmt_a_fs_exit_ms"], 200)
                self.assertEqual(a["tmt_a_resize_n"], 0)  # resizes caused by fullscreen do not count
                self.assertEqual(a["tmt_a_zoom_n"], 0)
                self.assertEqual([e["type"] for e in log["env"]["events"] if e["type"].startswith("fs")],
                                 ["fs_exit", "fs_enter", "fs_exit"])
                b, _ = self.summary_of(receiver, "tmt_b")
                self.assertEqual(b["tmt_b_fs_exit_n"], 0)  # the gate's time is outside the task
                for task in TASK_IDS:
                    task_summary, task_log = self.summary_of(receiver, task)
                    self.assertEqual(task_summary[f"{task}_placeholder"], 1)
                    self.assertIn("events", task_log["env"])
                post, post_log = self.summary_of(receiver, "post")
                self.assertEqual(post, {"post_placeholder": 1})  # questionnaires are not monitored
                self.assertIsNone(post_log)
                self.assert_valid_for_receiver(context, receiver.accepted)
                self.assertEqual(errors, [])

    def test_resizes_caused_by_fullscreen_do_not_count(self):
        # Headless browsers keep the window size when fullscreen changes, so
        # the resize a real browser makes is faked here.
        fake_resize = """([w, h]) => {
            for (const [key, value] of [['innerWidth', w], ['innerHeight', h], ['outerWidth', w],
                                        ['outerHeight', h + 80]])
                Object.defineProperty(window, key, { configurable: true, get: () => value });
            window.dispatchEvent(new Event('resize'));
        }"""
        for browser in self.browsers:
            with self.subTest(browser=browser.browser_type.name):
                context, receiver = self.new_context(browser)
                page, errors = self.open(browser, "?mode=dev&start=fullscreen" + FAST, context=context)
                page.get_by_role("button", name=ENTER).click()
                self.placeholder(page, "TMT, частина A")
                banner = page.locator(".fs-banner")

                # The window shrinks as fullscreen ends, and grows back as it returns.
                page.evaluate(fake_resize, [1200, 700])
                page.evaluate("document.exitFullscreen()")
                page.wait_for_timeout(600)
                banner.get_by_role("button", name=RETURN).click()
                page.evaluate(fake_resize, [1280, 720])
                page.wait_for_timeout(2500)
                # The window settles before the browser reports leaving fullscreen.
                page.evaluate(fake_resize, [1100, 650])
                page.wait_for_timeout(600)
                page.evaluate("document.exitFullscreen()")
                page.wait_for_timeout(2500)
                # An ordinary resize, far from any fullscreen change.
                page.evaluate(fake_resize, [1000, 600])
                page.wait_for_timeout(600)

                self.next(page)
                page.get_by_role("button", name=RETURN).click()
                self.placeholder(page, "TMT, частина B")
                self.wait_delivered(page)
                summary, log = self.summary_of(receiver, "tmt_a")
                resizes = [e for e in log["env"]["events"] if e["type"] == "resize"]
                self.assertEqual([(e["w"], e.get("by_fullscreen", False)) for e in resizes],
                                 [(1200, True), (1280, True), (1100, True), (1000, False)], resizes)
                self.assertEqual(summary["tmt_a_resize_n"], 1)
                self.assertEqual(summary["tmt_a_zoom_n"], 0)
                self.assertEqual(errors, [])

    def test_refused_fullscreen_goes_on_with_a_mark(self):
        refuse = "Element.prototype.requestFullscreen = () => Promise.reject(new TypeError('refused'));"
        for browser in self.browsers:
            with self.subTest(browser=browser.browser_type.name):
                context, receiver = self.new_context(browser, init_script=refuse)
                page, errors = self.open(browser, "?mode=dev&start=fullscreen" + FAST, context=context)
                page.get_by_role("button", name=ENTER).click()
                expect(page.locator(".screen")).to_contain_text("не дав увімкнути")
                self.next(page)
                self.placeholder(page, "TMT, частина A")  # no gate
                self.next(page)
                self.placeholder(page, "TMT, частина B")
                expect(page.locator(".fs-banner")).to_be_hidden()
                self.wait_delivered(page)
                summary, _ = self.summary_of(receiver, "fullscreen")
                self.assertEqual(summary["fullscreen_status"], "failed")
                a, _ = self.summary_of(receiver, "tmt_a")
                self.assertEqual(a["tmt_a_fs_exit_n"], 0)
                self.assertEqual(errors, [])

    def test_browser_without_fullscreen_skips_the_button(self):
        unsupported = """for (const name of ['fullscreenEnabled', 'webkitFullscreenEnabled'])
            Object.defineProperty(Document.prototype, name, { configurable: true, get: () => false });"""
        for browser in self.browsers:
            with self.subTest(browser=browser.browser_type.name):
                context, receiver = self.new_context(browser, init_script=unsupported)
                page, errors = self.open(browser, "?mode=dev&start=fullscreen" + FAST, context=context)
                expect(page.locator(".screen")).to_contain_text("не дав увімкнути")
                self.assertEqual(page.get_by_role("button", name=ENTER).count(), 0)
                self.next(page)
                self.placeholder(page, "TMT, частина A")
                self.wait_delivered(page)
                summary, _ = self.summary_of(receiver, "fullscreen")
                self.assertEqual(summary["fullscreen_status"], "unsupported")
                self.assertEqual(errors, [])


class MonitorTest(EnvironmentTestCase):
    def test_leaving_the_tab_and_losing_focus(self):
        for browser in self.browsers:
            with self.subTest(browser=browser.browser_type.name):
                context, receiver = self.new_context(browser)
                page, errors = self.open(browser, "?mode=dev&only=tmt_a" + FAST, context=context)
                self.placeholder(page, "TMT, частина A")
                page.evaluate("() => window.dispatchEvent(new Event('blur'))")
                page.evaluate(SET_VISIBILITY, True)
                page.wait_for_timeout(400)
                page.evaluate(SET_VISIBILITY, False)
                page.evaluate("() => window.dispatchEvent(new Event('focus'))")
                page.wait_for_timeout(200)
                page.evaluate("() => window.dispatchEvent(new Event('blur'))")
                page.wait_for_timeout(200)
                page.evaluate("() => window.dispatchEvent(new Event('focus'))")
                self.next(page)
                self.wait_delivered(page)

                summary, log = self.summary_of(receiver, "tmt_a")
                self.assertEqual(summary["tmt_a_hidden_n"], 1)
                self.assertGreaterEqual(summary["tmt_a_hidden_ms"], 350)
                self.assertLess(summary["tmt_a_hidden_ms"], 3000)
                self.assertEqual(summary["tmt_a_blur_n"], 2)
                self.assertGreaterEqual(summary["tmt_a_blur_ms"], 550)
                self.assertEqual(summary["tmt_a_fs_exit_n"], 0)
                self.assertEqual(summary["tmt_a_touch_n"], 0)
                self.assertEqual([e["type"] for e in log["env"]["events"]],
                                 ["blur", "hidden", "visible", "focus", "blur", "focus"])
                self.assertEqual(log["env"]["pointer"], {"mouse": 1})  # the click on "Далі"
                self.assert_valid_for_receiver(context, receiver.accepted)
                self.assertEqual(errors, [])

    def test_exit_still_going_when_the_task_ends(self):
        for browser in self.browsers:
            with self.subTest(browser=browser.browser_type.name):
                context, receiver = self.new_context(browser)
                page, errors = self.open(browser, "?mode=dev&start=tmt_a" + FAST, context=context)
                self.placeholder(page, "TMT, частина A")
                page.evaluate("() => window.dispatchEvent(new Event('blur'))")
                page.wait_for_timeout(300)
                # A time limit ends the task while the participant is away.
                page.evaluate("() => window.tmtua.jsPsych.finishTrial()")
                self.placeholder(page, "TMT, частина B")
                page.wait_for_timeout(300)
                page.evaluate("() => window.dispatchEvent(new Event('focus'))")
                self.next(page)
                self.wait_delivered(page)
                a, _ = self.summary_of(receiver, "tmt_a")
                b, b_log = self.summary_of(receiver, "tmt_b")
                self.assertEqual(a["tmt_a_blur_n"], 1)
                self.assertGreaterEqual(a["tmt_a_blur_ms"], 250)
                self.assertEqual(b["tmt_b_blur_n"], 1)  # still away when B started
                self.assertGreaterEqual(b["tmt_b_blur_ms"], 250)
                self.assertTrue(b_log["env"]["events"][0]["at_start"])
                self.assertEqual(errors, [])

    def test_resize_and_zoom(self):
        zoom = """() => {
            Object.defineProperty(window, 'devicePixelRatio', { configurable: true, get: () => 3 });
            window.dispatchEvent(new Event('resize'));
        }"""
        for browser in self.browsers:
            with self.subTest(browser=browser.browser_type.name):
                context, receiver = self.new_context(browser)
                page, errors = self.open(browser, "?mode=dev&only=tmt_a" + FAST, context=context)
                self.placeholder(page, "TMT, частина A")
                page.set_viewport_size({"width": 1000, "height": 650})
                page.wait_for_timeout(700)
                page.evaluate(zoom)
                page.wait_for_timeout(700)
                self.next(page)
                self.wait_delivered(page)
                summary, log = self.summary_of(receiver, "tmt_a")
                events = log["env"]["events"]
                self.assertEqual([e["type"] for e in events], ["resize", "zoom"], events)
                self.assertEqual((events[0]["w"], events[0]["h"]), (1000, 650))
                self.assertEqual(events[1]["dpr"], 3)
                self.assertEqual(summary["tmt_a_resize_n"], 1)
                self.assertEqual(summary["tmt_a_zoom_n"], 1)
                self.assertEqual(errors, [])

    def test_scale_rules(self):
        page, _ = self.open(self.browsers[0], "?mode=dev")
        base = {"w": 1440, "h": 800, "ow": 1440, "oh": 900, "dpr": 2, "scale": 1}
        cases = [
            ({}, False),
            ({"w": 1200, "ow": 1200}, False),  # window made narrower
            ({"h": 760}, False),  # a bar appeared, the window did not change
            ({"w": 1309, "h": 727}, True),  # Safari zoom: page area shrinks, window stays
            ({"dpr": 2.2}, True),  # Chrome or Firefox zoom
            ({"dpr": 1, "w": 1440, "ow": 1440}, True),  # moved to an ordinary screen
            ({"scale": 1.5}, True),  # pinch zoom
        ]
        for change, expected in cases:
            got = page.evaluate("([a, b]) => import('./src/data/monitor.js').then(m => m.scaleChanged(a, b))",
                                [base, {**base, **change}])
            self.assertEqual(got, expected, change)

    def test_touch_is_told_from_cursor(self):
        for browser in self.browsers:
            with self.subTest(browser=browser.browser_type.name):
                context, receiver = self.new_context(browser, has_touch=True)
                page, errors = self.open(browser, "?mode=dev&only=tmt_a" + FAST, context=context)
                self.placeholder(page, "TMT, частина A")
                page.get_by_role("button", name="Далі").tap()
                self.wait_delivered(page)
                summary, log = self.summary_of(receiver, "tmt_a")
                self.assertEqual(summary["tmt_a_touch_n"], 1)
                self.assertEqual(log["env"]["pointer"], {"touch": 1})
                self.assertEqual(errors, [])


class EnvCheckPageTest(EnvironmentTestCase):
    def test_keys_in_fullscreen_and_events(self):
        for browser in self.browsers:
            with self.subTest(browser=browser.browser_type.name):
                context, receiver = self.new_context(browser)
                page, errors = self.open(browser, "?mode=dev&tool=env", context=context)
                page.keyboard.press("Digit1")  # not in fullscreen: logged, not marked
                expect(page.locator(".env-key-log li")).to_have_count(1)
                self.assertEqual(page.locator(".env-key-ok").count(), 0)
                page.get_by_role("button", name=ENTER).click()
                expect(page.locator(".env-fs-state")).to_have_text("повноекранний режим")
                for key in [f"Digit{d}" for d in range(1, 10)] + ["Space"]:
                    page.keyboard.press(key)
                expect(page.locator(".env-key-ok")).to_have_count(10)
                page.evaluate("document.exitFullscreen()")
                expect(page.locator(".env-events")).to_contain_text("вихід із повноекранного режиму")
                self.assertEqual(receiver.requests, [])
                self.assertEqual(errors, [])

    def test_unknown_tool_fails_loudly(self):
        page, _ = self.open(self.browsers[0], "?mode=dev&tool=nope")
        expect(page.locator(".message")).to_contain_text("nope")


if __name__ == "__main__":
    unittest.main()

"""Checks of data delivery (task T0.3): src/data/sender.js against a fake
receiver, in Chromium and WebKit. The real receiver is checked separately by
tests/sender_live.py.
"""

import re
import unittest

from playwright.sync_api import expect

from harness import AppTestCase

LAST_FOUR = ["PSS-10", "Питання після тесту", "Запрошення на ретест", "Подяка"]
LAST_FOUR_IDS = ["pss10", "post", "retest_invite", "thanks"]
FAST = "&set.send.retryBaseMs=100&set.send.retryMaxMs=500"
CODE_RE = re.compile(r"^[2-9a-hjkmnp-z]+$")


class SenderTest(AppTestCase):
    def outbox_keys(self, page):
        return page.evaluate("Object.keys(localStorage).filter(k => k.startsWith('tmtua.outbox.'))")

    def test_each_block_is_delivered_once_in_order(self):
        for browser in self.browsers:
            with self.subTest(browser=browser.browser_type.name):
                context, receiver = self.new_context(browser)
                page, errors = self.open(browser, "?mode=dev&start=pss10" + FAST, context=context)
                self.click_through(page, LAST_FOUR)
                self.wait_delivered(page)

                self.assertEqual(receiver.blocks(), LAST_FOUR_IDS)
                first, *rest = receiver.accepted
                self.assertEqual(first["summary"]["session_type"], "first")
                for key in ["started_at", "device_browser", "device_os", "device_screen_w",
                            "device_pixel_ratio", "device_pointer_fine"]:
                    self.assertIn(key, first["summary"])
                for message in rest:
                    self.assertNotIn("device_os", message["summary"])
                self.assertEqual(len({m["session_id"] for m in receiver.accepted}), 1)
                self.assertEqual(len({m["participant_code"] for m in receiver.accepted}), 1)
                self.assertRegex(first["session_id"], CODE_RE)
                self.assertEqual(len(first["session_id"]), 16)
                self.assertRegex(first["participant_code"], CODE_RE)
                self.assertEqual(len(first["participant_code"]), 10)
                self.assertEqual(rest[0]["summary"], {"post_placeholder": 1})
                self.assertEqual([m["seq"] for m in receiver.accepted], [1, 2, 3, 4])
                self.assertEqual(self.outbox_keys(page), [])
                self.assert_valid_for_receiver(context, receiver.accepted)
                self.assertEqual(errors, [])

    def test_offline_session_is_delivered_when_back_online(self):
        for browser in self.browsers:
            with self.subTest(browser=browser.browser_type.name):
                context, receiver = self.new_context(browser)
                page, errors = self.open(browser, "?mode=dev&start=pss10" + FAST, context=context)
                self.set_offline(context, receiver, True)
                self.click_through(page, LAST_FOUR)
                expect(page.locator(".dev-badge")).to_contain_text("у черзі 4")
                self.assertEqual(receiver.accepted, [])
                self.assertEqual(len(self.outbox_keys(page)), 1)

                self.set_offline(context, receiver, False)
                self.wait_delivered(page)
                self.assertEqual(receiver.blocks(), LAST_FOUR_IDS)
                self.assertEqual(self.outbox_keys(page), [])

    def test_failed_sends_are_retried(self):
        for browser in self.browsers:
            with self.subTest(browser=browser.browser_type.name):
                context, receiver = self.new_context(browser)
                calls = []

                def flaky(body):
                    calls.append(body)
                    if len(calls) <= 3:
                        return None  # connection dropped
                    if len(calls) <= 5:
                        return {"ok": False, "error": "busy"}
                    return {"ok": True}

                receiver.reply = flaky
                page, _ = self.open(browser, "?mode=dev&start=pss10" + FAST, context=context)
                self.click_through(page, LAST_FOUR)
                self.wait_delivered(page)
                self.assertEqual(receiver.blocks(), LAST_FOUR_IDS)
                self.assertGreater(len(calls), 4)

    def test_rejected_message_is_dropped_and_flagged(self):
        for browser in self.browsers:
            with self.subTest(browser=browser.browser_type.name):
                context, receiver = self.new_context(browser)
                receiver.reply = lambda body: (
                    {"ok": False, "error": "invalid", "detail": "test", "permanent": True}
                    if '"block":"post"' in body else {"ok": True}
                )
                page, _ = self.open(browser, "?mode=dev&start=pss10" + FAST, context=context)
                self.click_through(page, LAST_FOUR)
                self.wait_delivered(page)
                self.assertEqual(receiver.blocks(), ["pss10", "retest_invite", "thanks"])
                expect(page.locator(".dev-badge")).to_contain_text("відхилено 1")
                expect(page.locator(".dev-badge")).to_have_class(re.compile("dev-badge-alert"))

    def test_leftovers_from_an_earlier_visit_are_delivered(self):
        for browser in self.browsers:
            with self.subTest(browser=browser.browser_type.name):
                context, receiver = self.new_context(browser)
                receiver.reply = lambda body: None  # nothing gets through
                page, _ = self.open(browser, "?mode=dev&only=tmt_a" + FAST, context=context)
                self.click_through(page, ["TMT, частина A"])
                expect(page.locator(".dev-badge")).to_contain_text("у черзі 1")
                page.close()

                page, _ = self.open(browser, "?mode=dev&only=tmt_b" + FAST, context=context)
                # the leftover is counted from the very start, before any new message
                expect(page.locator(".dev-badge")).to_contain_text("у черзі 1")
                receiver.reply = lambda body: {"ok": True}
                self.wait_delivered(page)
                self.click_through(page, ["TMT, частина B"])
                self.wait_delivered(page)
                self.assertEqual(receiver.blocks(), ["tmt_a", "tmt_b"])
                self.assertNotEqual(receiver.accepted[0]["session_id"], receiver.accepted[1]["session_id"])
                self.assertEqual(self.outbox_keys(page), [])

    def test_pending_messages_are_beaconed_when_page_is_left(self):
        # In checks sendBeacon only records into window.__beacons (harness.py);
        # actual delivery by beacon is checked by tests/sender_live.py.
        hide = """Object.defineProperty(document, 'visibilityState', {
            configurable: true, get: () => 'hidden' });
            document.dispatchEvent(new Event('visibilitychange'));"""
        for browser in self.browsers:
            with self.subTest(browser=browser.browser_type.name):
                context, receiver = self.new_context(browser)
                receiver.reply = lambda body: None  # only a beacon can deliver now
                page, _ = self.open(browser, "?mode=dev&only=tmt_a" + FAST, context=context)
                self.click_through(page, ["TMT, частина A"])
                expect(page.locator(".dev-badge")).to_contain_text("у черзі 1")

                page.evaluate(hide)  # tab hidden...
                page.evaluate("window.dispatchEvent(new Event('pagehide'))")  # ...then closed
                page.wait_for_function("() => window.__beacons.length > 0")
                page.wait_for_timeout(300)
                beacons = page.evaluate("window.__beacons")
                self.assertEqual(len(beacons), 1)  # not repeated on pagehide
                self.assertIn('"block":"tmt_a"', beacons[0])
                # still queued: a beacon is never confirmed, so it stays for retries
                self.assertEqual(page.evaluate("window.tmtua.sender.pending()"), 1)

    def test_participant_sees_thanks_only_after_delivery(self):
        for browser in self.browsers:
            with self.subTest(browser=browser.browser_type.name):
                context, receiver = self.new_context(browser)
                page, errors = self.open(browser, "?mode=pilot", context=context)
                texts = self.module(page, "texts.uk.js")["texts"]
                blocks = self.session_blocks(page)
                self.set_offline(context, receiver, True)
                for block in blocks:
                    self.pass_block(page, *block)
                expect(page.locator(".message")).to_have_text(texts["data"]["offline"])

                self.set_offline(context, receiver, False)
                expect(page.locator(".message")).to_have_text(texts["common"]["sessionEnd"], timeout=15000)
                # every block but device_check, which sends nothing (decision 97)
                self.assertEqual(receiver.blocks(), [b[0] for b in blocks[1:]])
                self.assertEqual({m["mode"] for m in receiver.accepted}, {"pilot"})

    def test_blocked_storage_still_delivers(self):
        blocked = """Object.defineProperty(window, 'localStorage', {
            configurable: true, get() { throw new DOMException('blocked', 'SecurityError'); } });"""
        for browser in self.browsers:
            with self.subTest(browser=browser.browser_type.name):
                context, receiver = self.new_context(browser, init_script=blocked)
                page, errors = self.open(browser, "?mode=dev&start=pss10" + FAST, context=context)
                self.click_through(page, LAST_FOUR)
                self.wait_delivered(page)
                self.assertEqual(receiver.blocks(), LAST_FOUR_IDS)
                self.assertEqual(errors, [])

    def test_codes_and_device_detection(self):
        page, _ = self.open(self.browsers[0], "?mode=dev")
        codes = page.evaluate("import('./src/data/ids.js').then(m => "
                              "Array.from({length: 2000}, () => m.randomCode(16)))")
        self.assertEqual(len(set(codes)), 2000)
        self.assertTrue(all(CODE_RE.match(c) and len(c) == 16 for c in codes))

        cases = [
            ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
             "Chrome/141.0.0.0 Safari/537.36", 0, "Chrome", "141.0.0.0", "Windows"),
            ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
             "Chrome/141.0.0.0 Safari/537.36 Edg/141.0.3537.57", 0, "Edge", "141.0.3537.57", "Windows"),
            ("Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:144.0) Gecko/20100101 Firefox/144.0",
             0, "Firefox", "144.0", "Windows"),
            ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) "
             "Version/26.0 Safari/605.1.15", 0, "Safari", "26.0", "macOS"),
            ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) "
             "Version/26.0 Safari/605.1.15", 5, "Safari", "26.0", "iPadOS"),
            ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) "
             "Chrome/141.0.0.0 Safari/537.36 OPR/124.0.0.0", 0, "Opera", "124.0.0.0", "macOS"),
            ("Mozilla/5.0 (iPhone; CPU iPhone OS 18_6 like Mac OS X) AppleWebKit/605.1.15 "
             "(KHTML, like Gecko) Version/18.6 Mobile/15E148 Safari/604.1", 5, "Safari", "18.6", "iOS"),
            ("Mozilla/5.0 (iPhone; CPU iPhone OS 18_6 like Mac OS X) AppleWebKit/605.1.15 "
             "(KHTML, like Gecko) CriOS/141.0.7390.41 Mobile/15E148 Safari/604.1", 5, "Chrome",
             "141.0.7390.41", "iOS"),
            ("Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) "
             "Chrome/141.0.0.0 Mobile Safari/537.36", 5, "Chrome", "141.0.0.0", "Android"),
            ("Mozilla/5.0 (X11; CrOS x86_64 14541.0.0) AppleWebKit/537.36 (KHTML, like Gecko) "
             "Chrome/141.0.0.0 Safari/537.36", 0, "Chrome", "141.0.0.0", "ChromeOS"),
            ("Mozilla/5.0 (X11; Linux x86_64; rv:144.0) Gecko/20100101 Firefox/144.0",
             0, "Firefox", "144.0", "Linux"),
        ]
        for ua, touch, name, version, os_name in cases:
            with self.subTest(ua=ua[:60], touch=touch):
                result = page.evaluate(
                    "([ua, touch]) => import('./src/data/device.js').then(m => "
                    "[m.detectBrowser(ua), m.detectOs(ua, touch)])", [ua, touch])
                self.assertEqual(result, [{"name": name, "version": version}, os_name])


if __name__ == "__main__":
    unittest.main()

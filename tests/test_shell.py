"""Checks of the app shell (task T0.1) in Chromium and WebKit via Playwright.

Run from the app/ folder in an environment with Playwright installed
(in the research repo: ../.venv/bin/python -m unittest discover -s tests -v).
Needs internet access: jsPsych is loaded from the CDN. To check the published
site instead of the local files, set TMTUA_BASE_URL, e.g.
TMTUA_BASE_URL=https://serv3latt.github.io/tmt-ua/
"""

import json
import unittest

from playwright.sync_api import expect

from harness import AppTestCase


class AppShellTest(AppTestCase):
    def test_main_mode_runs_all_blocks_in_order(self):
        for browser in self.browsers:
            with self.subTest(browser=browser.browser_type.name):
                context, receiver = self.new_context(browser)
                page, errors = self.open(browser, "", context=context)
                blocks = self.session_blocks(page)
                self.assertEqual(len(blocks), 16)
                for block in blocks:
                    self.pass_block(page, *block)
                texts = self.module(page, "texts.uk.js")["texts"]
                expect(page.locator(".message")).to_have_text(texts["common"]["sessionEnd"])
                self.assertEqual(page.locator(".dev-badge").count(), 0)
                # While some blocks are placeholders, main mode sends nothing,
                # so the main spreadsheet stays empty until data collection.
                self.assertEqual(receiver.requests, [])
                self.assertEqual(errors, [])

    def test_unknown_mode_is_rejected(self):
        for browser in self.browsers:
            with self.subTest(browser=browser.browser_type.name):
                page, errors = self.open(browser, "?mode=pliot")
                texts = self.module(page, "texts.uk.js")["texts"]
                expect(page.locator(".message")).to_have_text(texts["errors"]["badLink"])
                self.assertEqual(errors, [])

    def test_dev_menu_lists_every_block(self):
        for browser in self.browsers:
            with self.subTest(browser=browser.browser_type.name):
                page, errors = self.open(browser, "?mode=dev")
                config = self.module(page, "config.js")
                expect(page.locator(".dev-version")).to_have_text(config["APP_VERSION"])
                ids = [block_id for block_id, _ in self.blocks(page)]
                self.assertEqual(page.locator(".dev-menu tr").evaluate_all(
                    "rows => rows.map(r => r.dataset.block)"), ids)
                self.assertEqual(errors, [])

    def test_dev_only_runs_one_block_and_dumps_data(self):
        for browser in self.browsers:
            with self.subTest(browser=browser.browser_type.name):
                page, errors = self.open(browser, "?mode=dev&only=tmt_a")
                expect(page.locator(".placeholder")).to_contain_text("TMT, частина A")
                expect(page.locator(".dev-badge")).to_be_visible()
                page.get_by_role("button", name="Далі").click()
                data = json.loads(page.locator(".dev-end pre").text_content())
                self.assertEqual([row["block"] for row in data], ["tmt_a"])
                self.assertEqual(data[0]["mode"], "dev")
                self.assertEqual(data[0]["app_version"], self.module(page, "config.js")["APP_VERSION"])
                self.assertEqual(errors, [])

    def test_dev_start_runs_from_block_to_end(self):
        for browser in self.browsers:
            with self.subTest(browser=browser.browser_type.name):
                page, errors = self.open(browser, "?mode=dev&start=pss10")
                for label in ["PSS-10", "Питання після тесту", "Запрошення на ретест", "Подяка"]:
                    expect(page.locator(".placeholder")).to_contain_text(label)
                    page.get_by_role("button", name="Далі").click()
                expect(page.locator(".dev-end")).to_be_visible()
                self.assertEqual(errors, [])

    def test_dev_override_changes_parameter(self):
        for browser in self.browsers:
            with self.subTest(browser=browser.browser_type.name):
                page, errors = self.open(browser, "?mode=dev&only=tmt_a&set.tmt.timeLimitMs=20000")
                expect(page.locator(".placeholder")).to_be_visible()
                self.assertEqual(page.evaluate("window.tmtua.params.tmt.timeLimitMs"), 20000)
                self.assertEqual(errors, [])

    def test_override_is_ignored_outside_dev(self):
        for browser in self.browsers:
            with self.subTest(browser=browser.browser_type.name):
                for mode in ["main", "pilot"]:
                    page, errors = self.open(browser, f"?mode={mode}&set.tmt.timeLimitMs=20000")
                    session = page.evaluate(
                        "import('./src/session.js').then(m => m.parseUrl(location.search))")
                    self.assertEqual(session["overrides"], {})
                    self.assertFalse(page.evaluate("'tmtua' in window"))
                    self.assertEqual(errors, [])

    def test_mistyped_override_or_block_fails_loudly(self):
        for browser in self.browsers:
            with self.subTest(browser=browser.browser_type.name):
                for query, needle in [
                    ("?mode=dev&only=tmt_a&set.tmt.timeLimitMS=1", "timeLimitMS"),
                    ("?mode=dev&only=tmt_a&set.tmt.timeLimitMs=abc", "abc"),
                    ("?mode=dev&only=tmt_c", "tmt_c"),
                ]:
                    page, _ = self.open(browser, query)
                    expect(page.locator(".message")).to_contain_text(needle)

    def test_cdn_failure_shows_message(self):
        for browser in self.browsers:
            with self.subTest(browser=browser.browser_type.name):
                page, _ = self.open(browser, "", block_cdn=True)
                texts = self.module(page, "texts.uk.js")["texts"]
                expect(page.locator(".message")).to_have_text(texts["errors"]["loadFailed"])

    def test_changed_cdn_file_is_refused(self):
        # The integrity hash in index.html must stop a modified library file.
        for browser in self.browsers:
            with self.subTest(browser=browser.browser_type.name):
                page, _ = self.open(browser, "", tamper_cdn=True)
                texts = self.module(page, "texts.uk.js")["texts"]
                expect(page.locator(".message")).to_have_text(texts["errors"]["loadFailed"])


if __name__ == "__main__":
    unittest.main()

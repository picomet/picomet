import os

from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from faker import Faker
from playwright.sync_api import sync_playwright

fake = Faker()


class HomeTest(StaticLiveServerTestCase):
    @classmethod
    def setUpClass(cls):
        os.environ["DJANGO_ALLOW_ASYNC_UNSAFE"] = "true"
        super().setUpClass()
        cls.playwright = sync_playwright().start()
        cls.browser = cls.playwright.chromium.launch()

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        cls.browser.close()
        cls.playwright.stop()

    def test_home(self):
        page = self.browser.new_page()
        response = page.goto(self.live_server_url)
        self.assertEqual(response.status, 200)
        page.close()

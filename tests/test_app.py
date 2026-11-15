import unittest

from roomsplit import create_app
from roomsplit.models import AccountRecord
from roomsplit.storage import RuntimeStorage


TEST_SECRET_KEY = "phase-one-test-secret"


class AppFoundationTests(unittest.TestCase):
    def setUp(self):
        self.config = {"TESTING": True, "SECRET_KEY": TEST_SECRET_KEY}
        self.app = create_app(self.config)
        self.client = self.app.test_client()

    def test_app_creation_returns_a_basic_page(self):
        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"RoomSplit", response.data)
        self.assertTrue(response.content_type.startswith("text/html"))

    def test_fresh_runtime_storage_starts_empty(self):
        self.assertEqual(RuntimeStorage().accounts, {})
        self.assertEqual(RuntimeStorage().rooms, {})
        self.assertEqual(RuntimeStorage().categories, {})
        self.assertEqual(RuntimeStorage().expenses, {})
        self.app.extensions["roomsplit_storage"].accounts["user"] = AccountRecord(
            id="user",
            username="synthetic-user",
            password_hash="synthetic-hash",
        )

        fresh_app = create_app(self.config)

        self.assertEqual(
            fresh_app.extensions["roomsplit_storage"].accounts,
            {},
        )
        self.assertEqual(fresh_app.extensions["roomsplit_storage"].rooms, {})
        self.assertEqual(fresh_app.extensions["roomsplit_storage"].categories, {})
        self.assertEqual(fresh_app.extensions["roomsplit_storage"].expenses, {})

    def test_app_uses_the_test_only_secret(self):
        self.assertEqual(self.app.config["SECRET_KEY"], TEST_SECRET_KEY)


if __name__ == "__main__":
    unittest.main()

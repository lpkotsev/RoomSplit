import unittest

from roomsplit import create_app


class CategorySuggestionsTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app(
            {"TESTING": True, "SECRET_KEY": "category-suggestions-test-secret"}
        )
        self.storage = self.app.extensions["roomsplit_storage"]
        self.client = self.app.test_client()
        credentials = {"username": "owner", "password": "test-password"}
        self.client.post("/register", data=credentials)
        self.client.post("/sign-in", data=credentials)
        self.client.post(
            "/rooms/create", data={"name": "Picnic", "password": "event-password"}
        )
        self.room = next(iter(self.storage.rooms.values()))
        self.owner_id = self.room.owner_id
        self.path = f"/rooms/{self.room.id}/expenses/new"

    def expense_data(self, category):
        return {
            "item": "Lunch",
            "amount": "10.00",
            "date": "2026-08-03",
            "category_name": category,
            "split_type": "equal",
            f"payer_{self.owner_id}": "10.00",
            "remainder_payer_id": self.owner_id,
        }

    def test_expense_form_offers_defaults_without_category_setup(self):
        page = self.client.get(self.path)
        self.assertEqual(page.status_code, 200)
        self.assertIn(b'name="category_name"', page.data)
        self.assertIn(b'<option value="Restaurant"', page.data)
        self.assertIn(b'<option value="Entertainment"', page.data)
        self.assertNotIn(b"Manage categories", page.data)
        room_page = self.client.get(f"/rooms/{self.room.id}")
        self.assertNotIn(b"Manage categories", room_page.data)
        self.assertNotIn(b"Create your first category", room_page.data)

    def test_new_category_saved_only_with_valid_expense_and_reused(self):
        invalid = self.expense_data("Board games")
        invalid["amount"] = "invalid"
        response = self.client.post(self.path, data=invalid)
        self.assertEqual(response.status_code, 400)
        self.assertIn(b'Board games', response.data)
        self.assertEqual(self.storage.categories, {})

        self.assertEqual(
            self.client.post(self.path, data=self.expense_data("  Board games  ")).status_code,
            302,
        )
        category = next(iter(self.storage.categories.values()))
        self.assertEqual(category.name, "Board games")
        self.assertEqual(category.room_id, self.room.id)
        self.assertIn(b'<option value="Board games"', self.client.get(self.path).data)

        self.assertEqual(
            self.client.post(self.path, data=self.expense_data("board GAMES")).status_code,
            302,
        )
        self.assertEqual(len(self.storage.categories), 1)
        self.assertEqual(
            {expense.category_id for expense in self.storage.expenses.values()},
            {category.id},
        )
        dashboard = self.client.get(f"/rooms/{self.room.id}/dashboard")
        self.assertIn(b"Board games", dashboard.data)
        self.assertIn(b"EUR 20.00", dashboard.data)

    def test_default_category_is_canonical_and_empty_category_rejected(self):
        missing = self.client.post(self.path, data=self.expense_data("   "))
        self.assertEqual(missing.status_code, 400)
        self.assertIn(b"Enter a category.", missing.data)
        self.assertEqual(self.storage.categories, {})
        self.assertEqual(
            self.client.post(self.path, data=self.expense_data("restaurant")).status_code,
            302,
        )
        self.assertEqual(next(iter(self.storage.categories.values())).name, "Restaurant")

    def test_custom_suggestions_stay_within_the_event(self):
        self.client.post(self.path, data=self.expense_data("Private category"))
        self.client.post(
            "/rooms/create", data={"name": "Other", "password": "event-password"}
        )
        other = next(room for room in self.storage.rooms.values() if room.id != self.room.id)
        page = self.client.get(f"/rooms/{other.id}/expenses/new")
        self.assertNotIn(b"Private category", page.data)


if __name__ == "__main__":
    unittest.main()

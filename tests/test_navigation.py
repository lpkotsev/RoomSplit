import unittest

from roomsplit import create_app


TEST_SECRET_KEY = "navigation-test-secret"


class NavigationTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app(
            {"TESTING": True, "SECRET_KEY": TEST_SECRET_KEY}
        )
        self.storage = self.app.extensions["roomsplit_storage"]

    def create_signed_in_user(self, username):
        client = self.app.test_client()
        password = f"{username}-password"
        registration = client.post(
            "/register",
            data={"username": username, "password": password},
        )
        self.assertEqual(registration.status_code, 302)
        sign_in = client.post(
            "/sign-in",
            data={"username": username, "password": password},
        )
        self.assertEqual(sign_in.status_code, 302)
        return client

    def test_home_page_links_to_registration_and_sign_in(self):
        client = self.app.test_client()

        response = client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b'href="/register"', response.data)
        self.assertIn(b'href="/sign-in"', response.data)
        self.assertEqual(client.get("/register").status_code, 200)
        self.assertEqual(client.get("/sign-in").status_code, 200)

    def test_signed_in_member_can_navigate_from_home_to_room_forms(self):
        client = self.create_signed_in_user("member")

        home = client.get("/")
        self.assertIn(b'href="/rooms"', home.data)

        rooms_page = client.get("/rooms")
        self.assertEqual(rooms_page.status_code, 200)
        self.assertIn(b"You have not joined a room yet.", rooms_page.data)
        created = client.post(
            "/rooms/create",
            data={"password": "room-password"},
        )
        self.assertEqual(created.status_code, 302)
        room = next(iter(self.storage.rooms.values()))

        room_page = client.get(f"/rooms/{room.id}")
        self.assertEqual(room_page.status_code, 200)
        self.assertIn(
            f'href="/rooms/{room.id}/categories"'.encode(),
            room_page.data,
        )
        self.assertIn(
            f'href="/rooms/{room.id}/expenses/new"'.encode(),
            room_page.data,
        )
        self.assertIn(b"Create your first category", room_page.data)
        self.assertIn(b"Record your first expense", room_page.data)

        categories_page = client.get(f"/rooms/{room.id}/categories")
        self.assertEqual(categories_page.status_code, 200)
        self.assertIn(b"No categories have been created yet.", categories_page.data)

        empty_expense_form = client.get(
            f"/rooms/{room.id}/expenses/new"
        )
        self.assertEqual(empty_expense_form.status_code, 200)
        self.assertIn(b"Create a category before recording an expense.", empty_expense_form.data)
        self.assertIn(
            f'href="/rooms/{room.id}/categories"'.encode(),
            empty_expense_form.data,
        )

        category = client.post(
            f"/rooms/{room.id}/categories",
            data={"name": "Shared costs"},
        )
        self.assertEqual(category.status_code, 302)
        expense_form = client.get(f"/rooms/{room.id}/expenses/new")
        self.assertEqual(expense_form.status_code, 200)
        self.assertIn(b'name="item"', expense_form.data)


if __name__ == "__main__":
    unittest.main()

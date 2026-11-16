import unittest

from roomsplit import create_app


class EventTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app(
            {"TESTING": True, "SECRET_KEY": "event-test-secret"}
        )
        self.storage = self.app.extensions["roomsplit_storage"]
        self.owner = self.make_user("event-owner")
        self.member = self.make_user("event-member")

    def make_user(self, username):
        client = self.app.test_client()
        credentials = {"username": username, "password": "test-password"}
        self.assertEqual(client.post("/register", data=credentials).status_code, 302)
        self.assertEqual(client.post("/sign-in", data=credentials).status_code, 302)
        return client

    def test_creation_requires_a_name_and_a_password(self):
        for data, error in (
            ({"name": "  ", "password": "password"}, b"Enter an event name."),
            ({"name": "Picnic", "password": ""}, b"Enter an event password."),
        ):
            with self.subTest(data=data):
                response = self.owner.post("/rooms/create", data=data)
                self.assertEqual(response.status_code, 400)
                self.assertIn(error, response.data)
                self.assertEqual(self.storage.rooms, {})

    def test_named_event_hashcode_password_and_invite_join(self):
        response = self.owner.post(
            "/rooms/create",
            data={"name": "  Summer picnic  ", "password": "event-password"},
        )
        self.assertEqual(response.status_code, 302)
        event = next(iter(self.storage.rooms.values()))
        self.assertEqual(event.name, "Summer picnic")
        self.assertTrue(event.code)
        self.assertNotEqual(event.password_hash, "event-password")

        page = self.owner.get(response.location)
        self.assertIn(b"Summer picnic", page.data)
        self.assertIn(b"Event hashcode:", page.data)
        self.assertIn(event.code.encode(), page.data)
        self.assertIn(b"Summer picnic", self.owner.get("/rooms").data)
        self.assertIn(b"My events", self.owner.get("/rooms").data)

        wrong_code = self.member.post(
            "/rooms/join",
            data={"room_code": "wrong", "password": "event-password"},
        )
        wrong_password = self.member.post(
            "/rooms/join",
            data={"room_code": event.code, "password": "wrong"},
        )
        self.assertEqual(wrong_code.status_code, 401)
        self.assertEqual(wrong_password.status_code, 401)
        self.assertEqual(len(event.member_ids), 1)

        joined = self.member.post(
            "/rooms/join",
            data={"room_code": event.code, "password": "event-password"},
        )
        self.assertEqual(joined.status_code, 302)
        self.assertEqual(len(event.member_ids), 2)
        self.assertIn(b"Summer picnic", self.member.get("/rooms").data)

        invitee = self.make_user("invitee")
        invite_url = f"/join/{event.invite_token}"
        self.assertIn(b"Summer picnic", invitee.get(invite_url).data)
        self.assertEqual(
            invitee.post(invite_url, data={"password": "wrong"}).status_code,
            401,
        )
        self.assertEqual(
            invitee.post(invite_url, data={"password": "event-password"}).status_code,
            302,
        )

        other = self.owner.post(
            "/rooms/create",
            data={"name": "Summer picnic", "password": "event-password"},
        )
        self.assertEqual(other.status_code, 302)
        self.assertEqual(len({room.code for room in self.storage.rooms.values()}), 2)

    def test_event_name_is_escaped_on_pages(self):
        self.owner.post(
            "/rooms/create",
            data={"name": "<script>alert(1)</script>", "password": "password"},
        )
        event = next(iter(self.storage.rooms.values()))
        for path in ("/rooms", f"/rooms/{event.id}", f"/rooms/{event.id}/dashboard"):
            with self.subTest(path=path):
                response = self.owner.get(path)
                self.assertEqual(response.status_code, 200)
                self.assertNotIn(b"<script>alert(1)</script>", response.data)
                self.assertIn(b"&lt;script&gt;", response.data)


if __name__ == "__main__":
    unittest.main()

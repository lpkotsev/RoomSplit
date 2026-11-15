import unittest

from werkzeug.security import check_password_hash

from roomsplit import create_app


TEST_SECRET_KEY = "phase-two-test-secret"


class PhaseTwoTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app(
            {"TESTING": True, "SECRET_KEY": TEST_SECRET_KEY}
        )
        self.storage = self.app.extensions["roomsplit_storage"]

    def new_client(self, username, password):
        client = self.app.test_client()
        response = client.post(
            "/register",
            data={"username": username, "password": password},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.location, "/sign-in")
        return client

    def sign_in(self, client, username, password):
        return client.post(
            "/sign-in",
            data={"username": username, "password": password},
        )

    def create_room(self, client, password="room-password"):
        response = client.post(
            "/rooms/create",
            data={"password": password},
        )
        self.assertEqual(response.status_code, 302)
        room = next(iter(self.storage.rooms.values()))
        return room, password

    def test_registration_hashes_password_without_signing_in(self):
        password = "account-password"
        client = self.app.test_client()

        response = client.post(
            "/register",
            data={"username": "alex", "password": password},
        )

        self.assertEqual(response.status_code, 302)
        account = next(iter(self.storage.accounts.values()))
        self.assertNotEqual(account.password_hash, password)
        self.assertTrue(check_password_hash(account.password_hash, password))
        with client.session_transaction() as user_session:
            self.assertEqual(dict(user_session), {})

    def test_sign_in_uses_only_user_id_in_the_session(self):
        password = "account-password"
        client = self.new_client("alex", password)

        response = self.sign_in(client, "alex", password)

        self.assertEqual(response.status_code, 302)
        account = next(iter(self.storage.accounts.values()))
        with client.session_transaction() as user_session:
            self.assertEqual(dict(user_session), {"user_id": account.id})
            user_session["unexpected"] = "value"

        self.assertEqual(client.get("/rooms").status_code, 200)
        with client.session_transaction() as user_session:
            self.assertEqual(dict(user_session), {"user_id": account.id})

    def test_invalid_credentials_do_not_authenticate(self):
        client = self.new_client("alex", "account-password")

        response = self.sign_in(client, "alex", "wrong-password")

        self.assertEqual(response.status_code, 401)
        with client.session_transaction() as user_session:
            self.assertEqual(dict(user_session), {})

    def test_anonymous_user_cannot_access_room_pages_or_actions(self):
        client = self.app.test_client()

        page = client.get("/rooms")
        action = client.post(
            "/rooms/create",
            data={"password": "room-password"},
        )

        self.assertEqual(page.status_code, 302)
        self.assertEqual(page.location, "/sign-in")
        self.assertEqual(action.status_code, 302)
        self.assertEqual(action.location, "/sign-in")
        self.assertEqual(self.storage.rooms, {})

    def test_stale_session_does_not_authenticate_without_runtime_account(self):
        password = "account-password"
        client = self.new_client("alex", password)
        self.sign_in(client, "alex", password)
        cookie = client.get_cookie(self.app.config["SESSION_COOKIE_NAME"])
        fresh_app = create_app(
            {"TESTING": True, "SECRET_KEY": TEST_SECRET_KEY}
        )
        fresh_client = fresh_app.test_client()
        fresh_client.set_cookie(self.app.config["SESSION_COOKIE_NAME"], cookie.value)

        response = fresh_client.get("/rooms")

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.location, "/sign-in")
        with fresh_client.session_transaction() as user_session:
            self.assertEqual(dict(user_session), {})

    def test_room_creation_assigns_creator_as_owner_and_hashes_room_password(self):
        owner = self.new_client("owner", "owner-password")
        self.sign_in(owner, "owner", "owner-password")

        room, password = self.create_room(owner)

        owner_id = next(
            account.id
            for account in self.storage.accounts.values()
            if account.username == "owner"
        )
        self.assertEqual(room.owner_id, owner_id)
        self.assertIn(owner_id, room.member_ids)
        self.assertIsNone(room.administrator_id)
        self.assertNotEqual(room.password_hash, password)
        self.assertTrue(check_password_hash(room.password_hash, password))

    def test_join_by_room_code_requires_the_room_password(self):
        owner = self.new_client("owner", "owner-password")
        self.sign_in(owner, "owner", "owner-password")
        room, password = self.create_room(owner)
        member = self.new_client("member", "member-password")
        self.sign_in(member, "member", "member-password")

        rejected = member.post(
            "/rooms/join",
            data={"room_code": room.code, "password": "wrong-password"},
        )
        self.assertEqual(rejected.status_code, 401)

        joined = member.post(
            "/rooms/join",
            data={"room_code": room.code, "password": password},
        )

        self.assertEqual(joined.status_code, 302)
        member_id = next(
            account.id
            for account in self.storage.accounts.values()
            if account.username == "member"
        )
        self.assertIn(member_id, room.member_ids)
        room_page = member.get(f"/rooms/{room.id}")
        self.assertEqual(room_page.status_code, 200)
        self.assertIn(b"Invite link:", room_page.data)

    def test_join_by_invite_link_and_password(self):
        owner = self.new_client("owner", "owner-password")
        self.sign_in(owner, "owner", "owner-password")
        room, password = self.create_room(owner)
        invite = self.new_client("invitee", "invitee-password")
        self.sign_in(invite, "invitee", "invitee-password")

        page = invite.get(f"/join/{room.invite_token}")
        self.assertEqual(page.status_code, 200)
        response = invite.post(
            f"/join/{room.invite_token}",
            data={"password": password},
        )

        self.assertEqual(response.status_code, 302)
        invitee_id = next(
            account.id
            for account in self.storage.accounts.values()
            if account.username == "invitee"
        )
        self.assertIn(invitee_id, room.member_ids)

    def test_only_a_room_member_can_read_room_details(self):
        owner = self.new_client("owner", "owner-password")
        self.sign_in(owner, "owner", "owner-password")
        room, _ = self.create_room(owner)
        outsider = self.new_client("outsider", "outsider-password")
        self.sign_in(outsider, "outsider", "outsider-password")

        response = outsider.get(f"/rooms/{room.id}")

        self.assertEqual(response.status_code, 403)

    def test_owner_can_appoint_a_joined_member_as_administrator(self):
        owner = self.new_client("owner", "owner-password")
        self.sign_in(owner, "owner", "owner-password")
        room, password = self.create_room(owner)
        member = self.new_client("member", "member-password")
        self.sign_in(member, "member", "member-password")
        member_id = next(
            account.id
            for account in self.storage.accounts.values()
            if account.username == "member"
        )
        member.post(
            "/rooms/join",
            data={"room_code": room.code, "password": password},
        )

        response = owner.post(
            f"/rooms/{room.id}/administrator",
            data={"member_id": member_id},
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(room.administrator_id, member_id)
        room_page = owner.get(f"/rooms/{room.id}")
        self.assertEqual(room_page.status_code, 200)
        self.assertIn(b"(administrator)", room_page.data)

    def test_nonmember_cannot_appoint_an_administrator(self):
        owner = self.new_client("owner", "owner-password")
        self.sign_in(owner, "owner", "owner-password")
        room, _ = self.create_room(owner)
        outsider = self.new_client("outsider", "outsider-password")
        self.sign_in(outsider, "outsider", "outsider-password")

        response = outsider.post(
            f"/rooms/{room.id}/administrator",
            data={"member_id": next(iter(self.storage.accounts))},
        )

        self.assertEqual(response.status_code, 403)
        self.assertIsNone(room.administrator_id)

    def test_admin_can_remove_an_ordinary_member_but_member_cannot(self):
        owner = self.new_client("owner", "owner-password")
        self.sign_in(owner, "owner", "owner-password")
        room, password = self.create_room(owner)
        admin = self.new_client("admin", "admin-password")
        self.sign_in(admin, "admin", "admin-password")
        admin_id = next(
            account.id
            for account in self.storage.accounts.values()
            if account.username == "admin"
        )
        admin.post(
            "/rooms/join",
            data={"room_code": room.code, "password": password},
        )
        owner.post(
            f"/rooms/{room.id}/administrator",
            data={"member_id": admin_id},
        )
        member = self.new_client("member", "member-password")
        self.sign_in(member, "member", "member-password")
        member_id = next(
            account.id
            for account in self.storage.accounts.values()
            if account.username == "member"
        )
        member.post(
            "/rooms/join",
            data={"room_code": room.code, "password": password},
        )

        denied = member.post(
            f"/rooms/{room.id}/members/{admin_id}/remove"
        )
        self.assertEqual(denied.status_code, 403)

        removed = admin.post(
            f"/rooms/{room.id}/members/{member_id}/remove"
        )
        self.assertEqual(removed.status_code, 302)
        self.assertNotIn(member_id, room.member_ids)

    def test_ordinary_member_can_leave_but_owner_and_admin_cannot(self):
        owner = self.new_client("owner", "owner-password")
        self.sign_in(owner, "owner", "owner-password")
        room, password = self.create_room(owner)
        admin = self.new_client("admin", "admin-password")
        self.sign_in(admin, "admin", "admin-password")
        admin_id = next(
            account.id
            for account in self.storage.accounts.values()
            if account.username == "admin"
        )
        admin.post(
            "/rooms/join",
            data={"room_code": room.code, "password": password},
        )
        owner.post(
            f"/rooms/{room.id}/administrator",
            data={"member_id": admin_id},
        )
        member = self.new_client("member", "member-password")
        self.sign_in(member, "member", "member-password")
        member_id = next(
            account.id
            for account in self.storage.accounts.values()
            if account.username == "member"
        )
        member.post(
            "/rooms/join",
            data={"room_code": room.code, "password": password},
        )
        owner_id = next(
            account.id
            for account in self.storage.accounts.values()
            if account.username == "owner"
        )

        owner_response = owner.post(f"/rooms/{room.id}/leave")
        admin_response = admin.post(f"/rooms/{room.id}/leave")
        member_response = member.post(f"/rooms/{room.id}/leave")

        self.assertEqual(owner_response.status_code, 403)
        self.assertEqual(admin_response.status_code, 403)
        self.assertEqual(member_response.status_code, 302)
        self.assertIn(owner_id, room.member_ids)
        self.assertIn(admin_id, room.member_ids)
        self.assertNotIn(member_id, room.member_ids)


if __name__ == "__main__":
    unittest.main()

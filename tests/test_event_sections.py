import unittest

from roomsplit import create_app


class EventSectionTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app({"TESTING": True, "SECRET_KEY": "section-test"})
        self.storage = self.app.extensions["roomsplit_storage"]
        self.owner, self.owner_id = self.user("owner")
        self.owner.post("/rooms/create", data={"name": "Event", "password": "room"})
        self.room = next(iter(self.storage.rooms.values()))
        self.member, self.member_id = self.user("member")
        self.member.post("/rooms/join", data={"room_code": self.room.code, "password": "room"})
        self.base = f"/rooms/{self.room.id}"

    def user(self, username):
        client = self.app.test_client()
        data = {"username": username, "password": "synthetic-password"}
        self.assertEqual(client.post("/register", data=data).status_code, 302)
        self.assertEqual(client.post("/sign-in", data=data).status_code, 302)
        account = next(a for a in self.storage.accounts.values() if a.username == username)
        return client, account.id

    def test_section_navigation_and_membership(self):
        outsider, _ = self.user("outsider")
        for section in ("members", "expenses", "repayments", "balances"):
            path = f"{self.base}/{section}"
            with self.subTest(section=section):
                self.assertEqual(self.owner.get(path).status_code, 200)
                self.assertEqual(self.member.get(path).status_code, 200)
                self.assertEqual(outsider.get(path).status_code, 403)
                self.assertEqual(self.app.test_client().get(path).status_code, 302)
                self.assertIn(f'href="{path}"'.encode(), self.owner.get(self.base).data)
        members = self.owner.get(self.base + "/members").data
        self.assertIn(b"Appoint an administrator", members)
        self.assertNotIn(b"<h2>Expenses</h2>", members)
        self.assertNotIn(b"Appoint an administrator", self.owner.get(self.base).data)
        for path in (self.base, *(f"{self.base}/{s}" for s in ("members", "expenses", "repayments", "balances"))):
            page = self.owner.get(path).data
            for label in (b"Dashboard", b"Add expense", b"Record repayment"):
                self.assertIn(label, page)

    def test_balances_match_dashboard_and_section_redirects(self):
        self.assertIn(b"No balance activity", self.owner.get(self.base + "/balances").data)
        response = self.owner.post(self.base + "/expenses/new", data={
            "item": "Dinner", "amount": "20.00", "category_name": "Restaurant",
            f"payer_{self.owner_id}": "20.00",
        })
        self.assertEqual(response.location, self.base + "/expenses")
        response = self.member.post(self.base + "/repayments/new", data={
            "payer_id": self.member_id, "recipient_id": self.owner_id, "amount": "5.00",
        })
        self.assertEqual(response.location, self.base + "/repayments")
        for path in ("/balances", "/dashboard"):
            page = self.owner.get(self.base + path).data
            self.assertIn(b"owner: Owed EUR 5.00", page)
            self.assertIn(b"member: Owes EUR 5.00", page)
        self.assertIn(b"Dinner", self.owner.get(self.base + "/expenses").data)
        self.assertNotIn(b"Dinner", self.owner.get(self.base + "/members").data)
        self.assertIn(b"member paid", self.owner.get(self.base + "/repayments").data)


if __name__ == "__main__":
    unittest.main()

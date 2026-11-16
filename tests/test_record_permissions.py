import unittest

from roomsplit import create_app


class RecordPermissionTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app({"TESTING": True, "SECRET_KEY": "permissions-test"})
        self.storage = self.app.extensions["roomsplit_storage"]
        self.owner, self.owner_id = self.user("owner")
        self.owner.post("/rooms/create", data={"name": "Event", "password": "room"})
        self.room = next(iter(self.storage.rooms.values()))
        self.base = f"/rooms/{self.room.id}"
        self.creator, self.creator_id = self.join("creator")
        self.other, self.other_id = self.join("other")
        self.admin, self.admin_id = self.join("admin")
        self.expense_data = {
            "item": "Dinner", "amount": "40.00", "category_name": "Restaurant",
            f"payer_{self.owner_id}": "40.00",
        }
        self.assertEqual(self.creator.post(self.base + "/expenses/new", data=self.expense_data).status_code, 302)
        self.expense = next(iter(self.storage.expenses.values()))
        self.repayment_data = {
            "payer_id": self.creator_id, "recipient_id": self.owner_id, "amount": "5.00",
        }
        self.assertEqual(self.creator.post(self.base + "/repayments/new", data=self.repayment_data).status_code, 302)
        self.repayment = next(iter(self.storage.repayments.values()))

    def user(self, username):
        client = self.app.test_client()
        credentials = {"username": username, "password": "test-password"}
        self.assertEqual(client.post("/register", data=credentials).status_code, 302)
        self.assertEqual(client.post("/sign-in", data=credentials).status_code, 302)
        account = next(a for a in self.storage.accounts.values() if a.username == username)
        return client, account.id

    def join(self, username):
        client, user_id = self.user(username)
        self.assertEqual(client.post("/rooms/join", data={"room_code": self.room.code, "password": "room"}).status_code, 302)
        return client, user_id

    def test_owner_can_be_administrator(self):
        self.assertEqual(self.room.owner_id, self.owner_id)
        page = self.owner.get(self.base + "/members").data
        self.assertIn(f'value="{self.owner_id}"'.encode(), page)
        response = self.owner.post(self.base + "/administrator", data={"member_id": self.owner_id})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.room.administrator_id, self.owner_id)
        page = self.owner.get(self.base + "/members").data
        self.assertIn(b"(owner)", page)
        self.assertIn(b"(administrator)", page)

    def test_creator_and_administrator_permissions_and_labels(self):
        paths = {
            "expense": (f"{self.base}/expenses/{self.expense.id}", self.expense_data),
            "repayment": (f"{self.base}/repayments/{self.repayment.id}", self.repayment_data),
        }
        outsider, _ = self.user("outsider")
        for label, (path, data) in paths.items():
            with self.subTest(record=label):
                for client in (self.other, self.owner, outsider):
                    self.assertEqual(client.get(path + "/edit").status_code, 403)
                    self.assertEqual(client.post(path + "/edit", data=data).status_code, 403)
                    self.assertEqual(client.post(path + "/delete").status_code, 403)
                self.assertEqual(self.creator.get(path + "/edit").status_code, 200)
                self.assertEqual(self.creator.post(path + "/edit", data=data).status_code, 302)
                for client, visible in ((self.creator, True), (self.owner, False), (self.other, False)):
                    page = client.get(self.base + "/" + label + "s").data
                    self.assertIn(b"Created by: creator", page)
                    self.assertEqual((path + "/edit").encode() in page, visible)

        self.assertEqual(self.owner.post(self.base + "/administrator", data={"member_id": self.admin_id}).status_code, 302)
        for label, (path, data) in paths.items():
            self.assertEqual(self.admin.get(path + "/edit").status_code, 200)
            self.assertEqual(self.admin.post(path + "/edit", data=data).status_code, 302)
            self.assertIn((path + "/delete").encode(), self.admin.get(self.base + "/" + label + "s").data)
        self.assertEqual(self.storage.expenses[self.expense.id].created_by, self.creator_id)
        self.assertEqual(self.storage.repayments[self.repayment.id].created_by, self.creator_id)
        self.assertEqual(self.admin.post(paths["repayment"][0] + "/delete").status_code, 302)
        self.assertEqual(self.admin.post(paths["expense"][0] + "/delete").status_code, 302)
        self.assertEqual(self.admin.post(f"{self.base}/members/{self.other_id}/remove").status_code, 302)

    def test_creator_can_delete_own_records_and_former_creator_is_shown(self):
        self.assertEqual(self.creator.post(f"{self.base}/repayments/{self.repayment.id}/delete").status_code, 302)
        self.assertEqual(self.creator.post(f"{self.base}/expenses/{self.expense.id}/delete").status_code, 302)

    def test_departed_creator_loses_access_but_name_remains(self):
        self.assertEqual(self.creator.post(self.base + "/leave").status_code, 302)
        self.assertEqual(self.creator.get(f"{self.base}/expenses/{self.expense.id}/edit").status_code, 403)
        for section in ("expenses", "repayments"):
            self.assertIn(b"Created by: creator", self.owner.get(self.base + "/" + section).data)

    def test_owner_without_administrator_role_can_manage_own_expense(self):
        response = self.owner.post(self.base + "/expenses/new", data=self.expense_data)
        self.assertEqual(response.status_code, 302)
        expense = next(item for item in self.storage.expenses.values() if item.created_by == self.owner_id)
        path = f"{self.base}/expenses/{expense.id}"
        self.assertEqual(self.owner.get(path + "/edit").status_code, 200)
        self.assertEqual(self.owner.post(path + "/edit", data=self.expense_data).status_code, 302)
        self.assertEqual(self.owner.post(path + "/delete").status_code, 302)


if __name__ == "__main__":
    unittest.main()

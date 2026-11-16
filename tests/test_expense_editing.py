import unittest
from decimal import Decimal

from roomsplit import create_app
from roomsplit.balances import calculate_room_balances


class ExpenseEditingTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app({"TESTING": True, "SECRET_KEY": "expense-edit-test"})
        self.storage = self.app.extensions["roomsplit_storage"]
        self.owner, self.owner_id = self.user("owner")
        self.owner.post("/rooms/create", data={"name": "Event", "password": "room"})
        self.room = next(iter(self.storage.rooms.values()))
        self.member, self.member_id = self.user("member")
        self.member.post("/rooms/join", data={"room_code": self.room.code, "password": "room"})
        self.new_url = f"/rooms/{self.room.id}/expenses/new"

    def user(self, username):
        client = self.app.test_client()
        data = {"username": username, "password": "synthetic-password"}
        self.assertEqual(client.post("/register", data=data).status_code, 302)
        self.assertEqual(client.post("/sign-in", data=data).status_code, 302)
        account = next(a for a in self.storage.accounts.values() if a.username == username)
        return client, account.id

    def data(self):
        return {
            "item": "Dinner",
            "amount": "20.00",
            "category_name": "Restaurant",
            "split_type": "custom",
            f"payer_{self.owner_id}": "20.00",
            f"share_{self.owner_id}": "5.00",
            f"share_{self.member_id}": "15.00",
        }

    def create(self):
        self.assertEqual(self.owner.post(self.new_url, data=self.data()).status_code, 302)
        return next(iter(self.storage.expenses.values()))

    def test_custom_split_blanks_and_validation(self):
        data = self.data()
        data[f"share_{self.owner_id}"] = ""
        data[f"share_{self.member_id}"] = "20.00"
        self.assertEqual(self.member.post(self.new_url, data=data).status_code, 302)
        expense = next(iter(self.storage.expenses.values()))
        self.assertEqual(expense.custom_shares[self.owner_id], Decimal("0.00"))
        balances = calculate_room_balances([expense], self.room.member_ids)
        self.assertEqual(balances[self.owner_id], Decimal("20.00"))
        self.assertEqual(balances[self.member_id], Decimal("-20.00"))
        for value in ("-1.00", "1.001", "invalid", "19.00"):
            with self.subTest(value=value):
                invalid = dict(data, **{f"share_{self.member_id}": value})
                self.assertEqual(self.member.post(self.new_url, data=invalid).status_code, 400)
        self.assertEqual(len(self.storage.expenses), 1)

    def test_edit_snapshot_permissions_and_delete(self):
        expense = self.create()
        edit = f"/rooms/{self.room.id}/expenses/{expense.id}/edit"
        delete = f"/rooms/{self.room.id}/expenses/{expense.id}/delete"
        outsider, _ = self.user("outsider")
        for client in (self.member, outsider):
            self.assertEqual(client.get(edit).status_code, 403)
            self.assertEqual(client.post(edit, data=self.data()).status_code, 403)
            self.assertEqual(client.post(delete).status_code, 403)
        later, later_id = self.user("later")
        later.post("/rooms/join", data={"room_code": self.room.code, "password": "room"})
        self.member.post(f"/rooms/{self.room.id}/leave")
        form = self.owner.get(edit)
        self.assertIn(f'name="share_{self.member_id}"'.encode(), form.data)
        self.assertNotIn(f'name="share_{later_id}"'.encode(), form.data)
        changed = dict(self.data(), item="Updated")
        self.assertEqual(self.owner.post(edit, data=changed).status_code, 302)
        updated = self.storage.expenses[expense.id]
        self.assertEqual(updated.item, "Updated")
        self.assertEqual(updated.participant_ids, expense.participant_ids)
        self.assertEqual(updated.created_by, expense.created_by)
        self.assertEqual(self.owner.post(delete).status_code, 302)
        self.assertNotIn(expense.id, self.storage.expenses)

    def test_repayment_conflicts_reject_edit_and_delete_atomically(self):
        expense = self.create()
        self.assertEqual(self.member.post(
            f"/rooms/{self.room.id}/repayments/new",
            data={"payer_id": self.member_id, "recipient_id": self.owner_id, "amount": "10.00"},
        ).status_code, 302)
        edit = f"/rooms/{self.room.id}/expenses/{expense.id}/edit"
        delete = f"/rooms/{self.room.id}/expenses/{expense.id}/delete"
        changed = dict(self.data(), category_name="New category")
        changed[f"share_{self.owner_id}"] = "15.00"
        changed[f"share_{self.member_id}"] = "5.00"
        response = self.owner.post(edit, data=changed)
        self.assertEqual(response.status_code, 409)
        self.assertIn(b"repayment", response.data)
        self.assertIs(self.storage.expenses[expense.id], expense)
        self.assertNotIn("New category", [category.name for category in self.storage.categories.values()])
        response = self.owner.post(delete)
        self.assertEqual(response.status_code, 409)
        self.assertIs(self.storage.expenses[expense.id], expense)

    def test_event_page_actions_and_categories(self):
        expense = self.create()
        page = self.owner.get(f"/rooms/{self.room.id}/expenses").data
        self.assertNotIn(b"<h2>Categories</h2>", page)
        self.assertIn(f"/expenses/{expense.id}/edit".encode(), page)
        self.assertIn(f"/expenses/{expense.id}/delete".encode(), page)
        self.assertIn(b'class="record-action action-edit"', page)
        self.assertIn(b'class="record-action action-delete"', page)
        self.assertNotIn(b'>Delete expense</button>', page)
        members_page = self.owner.get(f"/rooms/{self.room.id}/members").data
        self.assertIn(b'aria-label="Remove member"', members_page)
        self.assertNotIn(b'>Remove member</button>', members_page)
        member_page = self.member.get(f"/rooms/{self.room.id}/expenses").data
        self.assertNotIn(f"/expenses/{expense.id}/edit".encode(), member_page)

    def test_repayment_actions_use_shared_labels_and_styles(self):
        self.create()
        self.assertEqual(self.member.post(
            f"/rooms/{self.room.id}/repayments/new",
            data={"payer_id": self.member_id, "recipient_id": self.owner_id, "amount": "5.00"},
        ).status_code, 302)
        page = self.member.get(f"/rooms/{self.room.id}/repayments").data
        self.assertIn(b'aria-label="Delete repayment', page)
        self.assertIn(b'class="record-action action-edit"', page)
        self.assertNotIn(b'>Delete repayment</button>', page)

    def test_administrator_can_edit_and_delete_and_equal_tie_is_retained(self):
        self.assertEqual(self.owner.post(
            f"/rooms/{self.room.id}/administrator",
            data={"member_id": self.member_id},
        ).status_code, 302)
        data = self.data()
        data["split_type"] = "equal"
        data[f"payer_{self.owner_id}"] = "10.00"
        data[f"payer_{self.member_id}"] = "10.00"
        data["remainder_payer_id"] = self.member_id
        self.assertEqual(self.member.post(self.new_url, data=data).status_code, 302)
        expense = next(iter(self.storage.expenses.values()))
        edit = f"/rooms/{self.room.id}/expenses/{expense.id}/edit"
        page = self.member.get(edit)
        self.assertEqual(page.status_code, 200)
        self.assertIn(f'name="remainder_payer_id" value="{self.member_id}"'.encode(), page.data)
        self.assertEqual(self.member.post(edit, data=data).status_code, 302)
        self.assertEqual(self.storage.expenses[expense.id].remainder_payer_id, self.member_id)
        self.assertEqual(self.member.post(
            f"/rooms/{self.room.id}/expenses/{expense.id}/delete",
        ).status_code, 302)


if __name__ == "__main__":
    unittest.main()

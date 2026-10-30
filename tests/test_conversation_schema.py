import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from app.models.conversation import Conversation
from app.schemas.conversation import ConversationCreate, ConversationRead, ConversationUpdate
from app.services.conversation_services import upsert_conversation


class ConversationFieldsTests(unittest.IsolatedAsyncioTestCase):
    def test_conversation_schemas_expose_customer_contact_fields(self):
        create = ConversationCreate(
            external_conversation_id="conversation-1",
            fullname="Nguyen Van A",
            phonenb="0901234567",
        )
        update = ConversationUpdate(fullname="Nguyen Van B", phonenb="0912345678")
        read = ConversationRead(
            id=1,
            external_conversation_id="conversation-1",
            fullname="Nguyen Van A",
            phonenb="0901234567",
            created_at="2026-01-01T00:00:00Z",
            updated_at="2026-01-01T00:00:00Z",
        )

        self.assertEqual(create.fullname, "Nguyen Van A")
        self.assertEqual(create.phonenb, "0901234567")
        self.assertEqual(update.phonenb, "0912345678")
        self.assertEqual(read.fullname, "Nguyen Van A")
        self.assertTrue(hasattr(Conversation, "fullname"))
        self.assertTrue(hasattr(Conversation, "phonenb"))

    async def test_upsert_updates_contact_fields_for_existing_conversation(self):
        existing = SimpleNamespace(fullname="Old Name", phonenb="0900000000")
        data = ConversationCreate(
            external_conversation_id="conversation-1",
            fullname="New Name",
            phonenb="0911111111",
        )
        db = AsyncMock()

        with patch(
            "app.services.conversation_services.get_conversation_by_external_id",
            AsyncMock(return_value=existing),
        ):
            result = await upsert_conversation(db, data)

        self.assertIs(result, existing)
        self.assertEqual(existing.fullname, "New Name")
        self.assertEqual(existing.phonenb, "0911111111")
        db.commit.assert_awaited_once()

    async def test_upsert_preserves_existing_contact_fields_when_omitted(self):
        existing = SimpleNamespace(fullname="Existing Name", phonenb="0900000000")
        data = ConversationCreate(external_conversation_id="conversation-1")
        db = AsyncMock()

        with patch(
            "app.services.conversation_services.get_conversation_by_external_id",
            AsyncMock(return_value=existing),
        ):
            await upsert_conversation(db, data)

        self.assertEqual(existing.fullname, "Existing Name")
        self.assertEqual(existing.phonenb, "0900000000")


if __name__ == "__main__":
    unittest.main()

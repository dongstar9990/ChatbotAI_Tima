import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from app.models.channel_accounts import ChannelAccount
from app.models.conversation import Conversation
from app.models.message import Message
from app.schemas.channel_accounts import (
    ChannelAccountCreate,
    ChannelAccountResponse,
    ChannelAccountUpdate,
)
from app.services.channel_accounts_services import (
    create_channel_account,
    update_channel_account,
)


class PancakeTokenTests(unittest.IsolatedAsyncioTestCase):
    def test_create_update_accept_token_but_response_hides_it(self):
        create = ChannelAccountCreate(
            name="pancake",
            channel_id="pancake",
            access_token_pancake="pancake-secret",
        )
        update = ChannelAccountUpdate(access_token_pancake="new-secret")
        response = ChannelAccountResponse.model_validate(
            SimpleNamespace(
                id=1,
                name="pancake",
                channel_id="pancake",
                account_name=None,
                external_page_id=None,
                access_token=None,
                status=1,
                created_at="2026-01-01T00:00:00Z",
                access_token_pancake="pancake-secret",
            )
        )

        self.assertEqual(create.access_token_pancake, "pancake-secret")
        self.assertEqual(update.access_token_pancake, "new-secret")
        self.assertNotIn("access_token_pancake", response.model_dump())
        self.assertTrue(hasattr(ChannelAccount, "access_token_pancake"))

    async def test_create_persists_pancake_token(self):
        db = SimpleNamespace(
            add=MagicMock(),
            commit=AsyncMock(),
            refresh=AsyncMock(),
        )
        data = ChannelAccountCreate(
            name="pancake",
            channel_id="pancake",
            access_token_pancake="pancake-secret",
        )

        result = await create_channel_account(db, data)

        self.assertEqual(result.access_token_pancake, "pancake-secret")
        db.add.assert_called_once_with(result)

    async def test_update_persists_pancake_token(self):
        account = SimpleNamespace(access_token_pancake="old-secret")
        db = AsyncMock()
        data = ChannelAccountUpdate(access_token_pancake="new-secret")

        with patch(
            "app.services.channel_accounts_services.get_channel_account",
            AsyncMock(return_value=account),
        ):
            result = await update_channel_account(db, 1, data)

        self.assertIs(result, account)
        self.assertEqual(account.access_token_pancake, "new-secret")
        db.commit.assert_awaited_once()

    def test_migration_adds_nullable_pancake_token_column(self):
        migration = Path("migrations/002_add_pancake_access_token.sql").read_text()

        self.assertIn("ALTER TABLE channel_accounts", migration)
        self.assertIn("access_token_pancake TEXT NULL", migration)


if __name__ == "__main__":
    unittest.main()

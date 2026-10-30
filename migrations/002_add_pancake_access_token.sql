ALTER TABLE channel_accounts
    ADD COLUMN IF NOT EXISTS access_token_pancake TEXT NULL;

"""Google OAuth scopes requested at consent time.

Single source of truth for what the app asks for, so the consent screen
(`auth/routes/auth_router.py`) and the drift check that decides whether an
already-connected account needs reconnecting (`auth/routes/connection_router.py`)
can never disagree.

Adding a scope here means every existing `ConnectedAccount` is missing it: their
refresh tokens were minted under the old set, and Google does not widen an
existing grant on refresh. The API call then fails with
`403 ACCESS_TOKEN_SCOPE_INSUFFICIENT` — an `HttpError`, not a `RefreshError`, so
`AuthService.get_google_credentials` never sees it. The drift check is what turns
that into a visible "Re-Connect" prompt.
"""

# Least-privilege Docs/Drive access: only files this app itself created. The Docs
# API accepts it for documents.create, so we never gain read access to the user's
# other documents (which `.../auth/documents` would grant).
DRIVE_FILE_SCOPE = "https://www.googleapis.com/auth/drive.file"

GOOGLE_SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.compose",
    "https://www.googleapis.com/auth/gmail.modify",
    DRIVE_FILE_SCOPE,
    "https://www.googleapis.com/auth/userinfo.profile",
    "https://www.googleapis.com/auth/userinfo.email",
    "openid",  # This scope is to get the user's ID
]

# Slack bot token scopes requested at install time. `chat:write` alone covers
# posting to public channels and any channel the bot has been invited to; a
# channel picker / name-resolution would additionally need `channels:read`.
SLACK_SCOPES = ["chat:write"]

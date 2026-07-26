from .config import Settings

# Every field is populated from the environment / .env by pydantic-settings, so
# the type checkers' "missing named argument" reading of this call is wrong.
settings = Settings()  # type: ignore[call-arg]  # pyright: ignore[reportCallIssue]

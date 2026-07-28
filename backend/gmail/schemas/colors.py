from typing import Any, Literal, cast, get_args

GmailBackgroundHex = Literal[
    "#cc3a21",  # Red
    "#ffad47",  # Orange
    "#f2c960",  # Yellow
    "#16a766",  # Green
    "#4a86e8",  # Blue
    "#a479e2",  # Purple
    "#f691b3",  # Pink
    "#000000",  # Black
    "#999999",  # Dark Gray (Default)
    "#ffffff",  # White
]

GmailTextHex = Literal[
    "#ffffff",  # White
    "#000000",  # Black
    "#434343",  # Dark Gray
    "#f3f3f3",  # Off-white (Default)
    "#efefef",  # Light Gray
    "#cccccc",  # Silver
    "#999999",  # Gray
    "#fce8b3",  # Cream
    "#c9daf8",  # Light Blue
    "#b9e4d0",  # Light Green
]

# Derived from the Literals above so the palette has exactly one definition.
VALID_BACKGROUND_COLORS = frozenset(get_args(GmailBackgroundHex))
VALID_TEXT_COLORS = frozenset(get_args(GmailTextHex))

DEFAULT_BACKGROUND_COLOR: GmailBackgroundHex = "#999999"
DEFAULT_TEXT_COLOR: GmailTextHex = "#f3f3f3"


def _clamp(value: Any, allowed: frozenset[str], default: str) -> str:
    """Normalize a hex string to the palette, falling back to `default`.

    Anything Gmail would reject — a colour outside the palette, a non-string, None —
    becomes `default` rather than raising, so a workflow saved with a bad colour still
    runs instead of failing the node at execution time.
    """
    if not isinstance(value, str):
        return default

    clean_hex_code = value.strip().lower()
    return clean_hex_code if clean_hex_code in allowed else default


def clamp_background_color(value: Any) -> GmailBackgroundHex:
    return cast(
        GmailBackgroundHex,
        _clamp(value, VALID_BACKGROUND_COLORS, DEFAULT_BACKGROUND_COLOR),
    )


def clamp_text_color(value: Any) -> GmailTextHex:
    return cast(GmailTextHex, _clamp(value, VALID_TEXT_COLORS, DEFAULT_TEXT_COLOR))

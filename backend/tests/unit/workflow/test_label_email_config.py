"""Regression tests for the label-colour crash.

A `label_email` node used to save with any hex string and only fail at execution time:
`LabelEmailConfig.label_info` builds a `LabelColor`, whose fields are `Literal`s over
Gmail's palette, so an off-palette colour raised a `ValidationError` from inside
`master_flow`. The clamping validators that should have prevented it were `mode="after"`
and therefore unreachable — the `Literal` check raised first.

Configs are built with `model_validate` rather than keyword arguments throughout: that is
how they actually arrive (JSONB out of `workflows.config`, or an imported/AI-generated
payload), and it is the only path that can carry an off-palette value now that the fields
are typed as `Literal`s.
"""

import pytest
from pydantic import ValidationError

from gmail.schemas.colors import DEFAULT_BACKGROUND_COLOR, DEFAULT_TEXT_COLOR
from gmail.schemas.label import LabelColor
from workflow.schemas.action import LabelEmailConfig


def test_off_palette_colors_clamp_instead_of_raising():
    """The original crash: an arbitrary hex must not blow up the config."""
    config = LabelEmailConfig.model_validate(
        {"label_name": "X", "background_color": "#123456", "text_color": "#abcdef"}
    )

    assert config.background_color == DEFAULT_BACKGROUND_COLOR
    assert config.text_color == DEFAULT_TEXT_COLOR


def test_label_info_builds_for_off_palette_colors():
    """`label_info` is the exact call master_flow makes when dispatching the node."""
    config = LabelEmailConfig.model_validate(
        {"label_name": "Offers", "background_color": "#123456", "text_color": "#abcdef"}
    )

    label = config.label_info

    assert label.name == "Offers"
    assert label.color is not None
    assert label.color.backgroundColor == DEFAULT_BACKGROUND_COLOR
    assert label.color.textColor == DEFAULT_TEXT_COLOR


def test_valid_palette_colors_round_trip():
    config = LabelEmailConfig.model_validate(
        {"label_name": "X", "background_color": "#cc3a21", "text_color": "#000000"}
    )

    assert config.background_color == "#cc3a21"
    assert config.text_color == "#000000"

    color = config.label_info.color
    assert color is not None
    assert color.backgroundColor == "#cc3a21"
    assert color.textColor == "#000000"


def test_colors_are_normalized_for_case_and_whitespace():
    config = LabelEmailConfig.model_validate(
        {"label_name": "X", "background_color": " #CC3A21 ", "text_color": "  #000000"}
    )

    assert config.background_color == "#cc3a21"
    assert config.text_color == "#000000"


@pytest.mark.parametrize("bad_value", [None, 123, ["#cc3a21"], {"hex": "#cc3a21"}])
def test_non_string_colors_fall_back_to_defaults(bad_value):
    """A malformed import or AI-generated config must not 422 the whole workflow."""
    config = LabelEmailConfig.model_validate(
        {"label_name": "X", "background_color": bad_value, "text_color": bad_value}
    )

    assert config.background_color == DEFAULT_BACKGROUND_COLOR
    assert config.text_color == DEFAULT_TEXT_COLOR


def test_defaults_apply_when_colors_are_omitted():
    config = LabelEmailConfig.model_validate({"label_name": "X"})

    assert config.background_color == DEFAULT_BACKGROUND_COLOR
    assert config.text_color == DEFAULT_TEXT_COLOR


def test_label_color_clamps_directly():
    """Proves the mode="before" switch made the validators reachable at all — under
    mode="after" this construction raised."""
    color = LabelColor.model_validate(
        {"backgroundColor": "#123456", "textColor": "#abcdef"}
    )

    assert color.backgroundColor == DEFAULT_BACKGROUND_COLOR
    assert color.textColor == DEFAULT_TEXT_COLOR


def test_label_color_no_longer_raises_validation_error():
    try:
        LabelColor.model_validate({"backgroundColor": "not-a-hex", "textColor": ""})
    except ValidationError as e:  # pragma: no cover - only runs on regression
        pytest.fail(f"LabelColor must clamp, not raise: {e}")

import pytest
from utils.resolve_variables import resolve_variables


# ---------------------------------------------------------------------------
# String inputs
# ---------------------------------------------------------------------------

def test_plain_string_unchanged():
    assert resolve_variables("hello world", {}) == "hello world"


def test_single_variable_resolved():
    ctx = {"node_1": {"subject": "Meeting at 9"}}
    assert resolve_variables("{{node_1.subject}}", ctx) == "Meeting at 9"


def test_variable_embedded_in_string():
    ctx = {"node_1": {"name": "Alice"}}
    assert resolve_variables("Hello {{node_1.name}}!", ctx) == "Hello Alice!"


def test_multiple_variables_in_string():
    ctx = {"a": {"x": "foo"}, "b": {"y": "bar"}}
    assert resolve_variables("{{a.x}} and {{b.y}}", ctx) == "foo and bar"


def test_whitespace_inside_braces_trimmed():
    ctx = {"node_1": {"subject": "Hi"}}
    assert resolve_variables("{{ node_1.subject }}", ctx) == "Hi"


def test_nested_path_resolved():
    ctx = {"trigger": {"email": {"from": "alice@example.com"}}}
    assert resolve_variables("{{trigger.email.from}}", ctx) == "alice@example.com"


def test_missing_key_raises():
    ctx = {"node_1": {"subject": "Hi"}}
    with pytest.raises(Exception, match="Could not resolve variable"):
        resolve_variables("{{node_1.missing_key}}", ctx)


def test_missing_top_level_key_raises():
    with pytest.raises(Exception, match="Could not resolve variable"):
        resolve_variables("{{nonexistent.key}}", {})


def test_non_string_value_coerced_to_string():
    ctx = {"node_1": {"count": 42}}
    assert resolve_variables("{{node_1.count}}", ctx) == "42"


def test_object_attribute_access():
    class Obj:
        subject = "from object"

    ctx = {"node_1": Obj()}
    assert resolve_variables("{{node_1.subject}}", ctx) == "from object"


# ---------------------------------------------------------------------------
# Default / fallback syntax  {{path | "default"}}
# ---------------------------------------------------------------------------

def test_default_ignored_when_path_resolves():
    ctx = {"node_1": {"subject": "Real Subject"}}
    assert (
        resolve_variables('{{node_1.subject | "No Subject"}}', ctx) == "Real Subject"
    )


def test_double_quoted_default_used_when_missing():
    assert resolve_variables('{{node_1.subject | "No Subject"}}', {}) == "No Subject"


def test_single_quoted_default_used_when_missing():
    assert resolve_variables("{{node_1.subject | 'No Subject'}}", {}) == "No Subject"


def test_bare_default_used_when_missing():
    assert resolve_variables("{{node_1.subject | fallback}}", {}) == "fallback"


def test_default_embedded_in_larger_string():
    assert resolve_variables('Hi {{x.name | "there"}}!', {}) == "Hi there!"


def test_whitespace_around_pipe_trimmed():
    ctx = {"node_1": {"subject": "Hi"}}
    assert resolve_variables('{{ node_1.subject  |  "x" }}', ctx) == "Hi"
    assert resolve_variables('{{ node_1.missing  |  "x" }}', ctx) == "x"


def test_missing_without_default_still_raises():
    with pytest.raises(Exception, match="Could not resolve variable"):
        resolve_variables("{{node_1.subject}}", {})


# ---------------------------------------------------------------------------
# Dict inputs (recursive)
# ---------------------------------------------------------------------------

def test_dict_values_resolved():
    ctx = {"node_1": {"to": "bob@example.com"}}
    result = resolve_variables({"to": "{{node_1.to}}", "body": "Hello"}, ctx)
    assert result == {"to": "bob@example.com", "body": "Hello"}


def test_nested_dict_resolved():
    ctx = {"n": {"v": "deep"}}
    result = resolve_variables({"outer": {"inner": "{{n.v}}"}}, ctx)
    assert result == {"outer": {"inner": "deep"}}


def test_dict_with_no_variables_unchanged():
    result = resolve_variables({"key": "static"}, {})
    assert result == {"key": "static"}


# ---------------------------------------------------------------------------
# List inputs (recursive)
# ---------------------------------------------------------------------------

def test_list_values_resolved():
    ctx = {"n": {"x": "a", "y": "b"}}
    result = resolve_variables(["{{n.x}}", "{{n.y}}"], ctx)
    assert result == ["a", "b"]


def test_list_with_no_variables_unchanged():
    result = resolve_variables(["hello", "world"], {})
    assert result == ["hello", "world"]


# ---------------------------------------------------------------------------
# Non-string scalars — returned unchanged
# ---------------------------------------------------------------------------

def test_integer_returned_unchanged():
    assert resolve_variables(99, {}) == 99


def test_boolean_returned_unchanged():
    assert resolve_variables(True, {}) is True


def test_none_returned_unchanged():
    assert resolve_variables(None, {}) is None

"""Tests for sparky.gemini_schema utilities (direct module import)."""

import importlib.util
from pathlib import Path

_GEMINI_SCHEMA_PATH = (
    Path(__file__).resolve().parents[2] / "src" / "sparky" / "gemini_schema.py"
)
_spec = importlib.util.spec_from_file_location("gemini_schema", _GEMINI_SCHEMA_PATH)
gemini_schema = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(gemini_schema)


class TestPrepareJsonSchemaForGemini:
    def test_strips_constraint_keys(self):
        schema = {
            "type": "object",
            "properties": {
                "query": {"type": "string", "minLength": 1, "maxLength": 100},
            },
            "required": ["query"],
            "minimum": 1,
        }
        fixes = gemini_schema.prepare_json_schema_for_gemini(schema)
        assert fixes == []
        assert "minLength" not in schema["properties"]["query"]
        assert "minimum" not in schema

    def test_drops_orphan_required_fields(self):
        schema = {
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query", "missing"],
        }
        fixes = gemini_schema.prepare_json_schema_for_gemini(schema)
        assert ("root", "missing") in fixes
        assert schema["required"] == ["query"]


class TestGeminiAutomaticFunctionCalling:
    def test_disable(self):
        assert gemini_schema.gemini_automatic_function_calling_kwarg(
            disable_afc=True
        ) == {"disable": True}

    def test_default_none_for_high_cap(self):
        assert (
            gemini_schema.gemini_automatic_function_calling_kwarg(max_remote_calls=10)
            is None
        )

    def test_capped_calls(self):
        assert gemini_schema.gemini_automatic_function_calling_kwarg(
            max_remote_calls=3
        ) == {"maximum_remote_calls": 3}

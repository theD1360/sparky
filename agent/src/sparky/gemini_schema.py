"""Gemini-safe JSON schema utilities for LangChain tool declarations."""

from __future__ import annotations

import copy
import logging
from typing import Any, List, Optional

from pydantic import BaseModel

logger = logging.getLogger(__name__)

try:
    from pydantic.v1 import BaseModel as BaseModelV1
except ImportError:
    BaseModelV1 = None  # type: ignore[misc, assignment]

_GEMINI_SCHEMA_STRIP_KEYS = frozenset(
    {
        "$schema",
        "$id",
        "$comment",
        "minimum",
        "maximum",
        "exclusiveMinimum",
        "exclusiveMaximum",
        "minLength",
        "maxLength",
        "minItems",
        "maxItems",
        "pattern",
        "format",
        "multipleOf",
        "const",
        "contentEncoding",
        "contentMediaType",
    }
)


def _strip_json_schema_gemini_noise(obj: Any) -> None:
    """In-place simplify JSON Schema for Gemini function declarations."""
    if isinstance(obj, dict):
        for key in list(obj.keys()):
            if key in _GEMINI_SCHEMA_STRIP_KEYS:
                obj.pop(key, None)
        for value in obj.values():
            _strip_json_schema_gemini_noise(value)
    elif isinstance(obj, list):
        for value in obj:
            _strip_json_schema_gemini_noise(value)


def _reconcile_json_schema_required_fields(obj: Any) -> list[tuple[str, str]]:
    """Drop ``required`` entries missing from sibling ``properties``."""
    fixes: list[tuple[str, str]] = []

    def _walk(node: Any, path: str) -> None:
        if isinstance(node, dict):
            props = node.get("properties")
            req = node.get("required")
            if isinstance(props, dict) and isinstance(req, list):
                kept: list[str] = []
                for key in req:
                    if not isinstance(key, str):
                        continue
                    if key in props:
                        kept.append(key)
                    else:
                        fixes.append((path or "root", key))
                if kept:
                    node["required"] = kept
                else:
                    node.pop("required", None)
            for key, val in node.items():
                if key in ("properties", "$defs", "definitions"):
                    if isinstance(val, dict):
                        for sub_key, sub_val in val.items():
                            _walk(
                                sub_val,
                                f"{path}.{key}.{sub_key}" if path else f"{key}.{sub_key}",
                            )
                elif key in ("items", "additionalProperties", "not"):
                    if isinstance(val, dict):
                        _walk(val, f"{path}.{key}" if path else key)
                elif key in ("anyOf", "oneOf", "allOf") and isinstance(val, list):
                    for idx, branch in enumerate(val):
                        if isinstance(branch, dict):
                            _walk(
                                branch,
                                f"{path}.{key}[{idx}]" if path else f"{key}[{idx}]",
                            )
        elif isinstance(node, list):
            for val in node:
                _walk(val, path)

    _walk(obj, "")
    return fixes


def prepare_json_schema_for_gemini(schema: dict) -> list[tuple[str, str]]:
    """Normalize a JSON Schema dict for Gemini function declarations."""
    _strip_json_schema_gemini_noise(schema)
    if schema.get("type") is None and isinstance(schema.get("properties"), dict):
        schema["type"] = "object"
    return _reconcile_json_schema_required_fields(schema)


def tools_with_gemini_safe_arg_schemas(
    tools: Optional[List[Any]],
) -> Optional[List[Any]]:
    """Clone LangChain tools with arg JSON schemas stripped for Gemini."""
    if not tools:
        return tools

    from langchain_core.tools import BaseTool

    out: List[Any] = []
    for tool in tools:
        if not isinstance(tool, BaseTool):
            out.append(tool)
            continue

        args_schema = getattr(tool, "args_schema", None)
        if args_schema is None:
            out.append(tool)
            continue

        schema: Optional[dict] = None
        if isinstance(args_schema, dict):
            schema = copy.deepcopy(args_schema)
        elif isinstance(args_schema, type):
            try:
                if issubclass(args_schema, BaseModel):
                    schema = args_schema.model_json_schema()
                elif BaseModelV1 is not None and issubclass(args_schema, BaseModelV1):
                    schema = args_schema.schema()
            except TypeError:
                schema = None

        if schema is None:
            out.append(tool)
            continue

        fixes = prepare_json_schema_for_gemini(schema)
        if fixes:
            logger.debug(
                "Gemini tool schema reconcile: tool=%s dropped required fields %s",
                getattr(tool, "name", type(tool).__name__),
                fixes,
            )
        try:
            out.append(tool.model_copy(update={"args_schema": schema}))
        except Exception:
            out.append(tool)
    return out


def gemini_automatic_function_calling_kwarg(
    *,
    disable_afc: bool = False,
    max_remote_calls: int = 10,
) -> Optional[dict[str, Any]]:
    """Return ``automatic_function_calling`` dict for google-genai, or None for defaults."""
    if disable_afc:
        return {"disable": True}
    if max_remote_calls >= 10:
        return None
    return {"maximum_remote_calls": max_remote_calls}

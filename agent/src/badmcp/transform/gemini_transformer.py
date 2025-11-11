from ..interfaces.transformer import TransformerInterface


class GeminiTransformer(TransformerInterface):
    def transform(self, schema: dict) -> dict:
        """Convert JSON Schema to Gemini-compatible schema.

        - Handles union types (arrays in JSON Schema) by removing "null"
          and collapsing to a single type when possible; otherwise falls back to OBJECT.
        - Recursively converts nested schemas in "properties" and "items".
        """
        if not schema:
            return {"type": "OBJECT", "properties": {}}

        # Map JSON Schema types to Gemini types
        type_mapping = {
            "string": "STRING",
            "number": "NUMBER",
            "integer": "INTEGER",
            "boolean": "BOOLEAN",
            "array": "ARRAY",
            "object": "OBJECT",
        }

        result: dict = {}

        # Convert type (string or list-of-strings)
        if "type" in schema:
            jtype = schema["type"]

            def normalize_type(t: str) -> str:
                return type_mapping.get(t, t.upper())

            if isinstance(jtype, list):
                # Remove "null" and deduplicate
                non_null = [t for t in jtype if t != "null"]
                non_null = list(dict.fromkeys(non_null))  # preserve order, unique
                if len(non_null) == 0:
                    # All null → treat as STRING to allow empty value; other choices possible
                    result["type"] = "STRING"
                elif len(non_null) == 1:
                    result["type"] = normalize_type(non_null[0])
                else:
                    # Multiple different types → fall back to OBJECT
                    result["type"] = "OBJECT"
            elif isinstance(jtype, str):
                result["type"] = normalize_type(jtype)

        # Convert properties recursively for objects
        # Only include properties if non-empty (Gemini rejects empty properties)
        if schema.get("properties") and isinstance(schema["properties"], dict):
            result["properties"] = {}
            for prop_name, prop_schema in schema["properties"].items():
                result["properties"][prop_name] = self.transform(prop_schema)

        # Convert items recursively for arrays
        if schema.get("items"):
            # "items" can be a single schema or an array of schemas; Gemini expects a single item schema
            items_schema = schema["items"]
            if isinstance(items_schema, list) and items_schema:
                # Use the first as a best-effort approximation
                result["items"] = self.transform(items_schema[0])
            elif isinstance(items_schema, dict):
                result["items"] = self.transform(items_schema)

        # Preserve selected fields that Gemini may use
        for key in ["description", "required", "enum"]:
            if key in schema:
                result[key] = schema[key]

        # Only add 'required' field if we have properties
        # Don't add empty required array for parameter-less tools
        if (
            result.get("type") == "OBJECT"
            and "required" not in result
            and "properties" in result
        ):
            result["required"] = []

        return result

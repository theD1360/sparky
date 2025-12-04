from typing import Dict, List


class FilterEvaluator:
    """Evaluate WHERE clause conditions."""

    def evaluate(self, conditions: List, bindings: Dict) -> bool:
        """Evaluate conditions against variable bindings."""
        if not conditions:
            return True

        for condition in conditions:
            if not self._evaluate_condition(condition, bindings):
                return False

        return True

    def _evaluate_condition(self, condition: Dict, bindings: Dict) -> bool:
        """Evaluate a single condition."""
        var = condition.get("var")
        prop = condition.get("property")
        value = condition.get("value")
        cond_type = condition.get("type")
        negated = condition.get("negated", False)

        if var not in bindings:
            return False

        node_data = bindings[var]

        # Get property value
        # Handle direct node fields: id, label, type, content
        if prop == "id":
            actual_value = node_data.get("id")
        elif prop == "label":
            actual_value = node_data.get("label")
        elif prop == "type":
            actual_value = node_data.get("type")
        elif prop == "content":
            actual_value = node_data.get("content")
        else:
            # Otherwise, get from properties JSON field
            actual_value = node_data.get("properties", {}).get(prop)

        # Evaluate condition
        result = False
        if cond_type == "equals":
            result = actual_value == value
        elif cond_type == "starts_with":
            result = isinstance(actual_value, str) and actual_value.startswith(value)

        # Apply negation if needed
        return not result if negated else result

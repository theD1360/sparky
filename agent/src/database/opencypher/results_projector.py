from typing import Dict, List


class ResultProjector:
    """Project and format query results."""

    def project(self, matches: List[Dict], return_spec: Dict) -> List[Dict]:
        """Project matches according to RETURN specification."""
        if not matches:
            return []

        results = []

        for match in matches:
            result = {}

            for field_spec in return_spec["fields"]:
                field = field_spec["field"]
                alias = field_spec.get("alias", field)

                if field == "*":
                    # Return all variables
                    result = match
                elif "." in field:
                    # Variable.property access
                    var, prop = field.split(".", 1)
                    if var in match:
                        if prop == "id":
                            result[alias] = match[var].get("id")
                        else:
                            result[alias] = match[var].get("properties", {}).get(prop)
                else:
                    # Just variable
                    if field in match:
                        result[alias] = match[field]

            results.append(result)

        # Handle DISTINCT
        if return_spec.get("distinct"):
            seen = set()
            unique_results = []
            for r in results:
                r_tuple = tuple(sorted(r.items()))
                if r_tuple not in seen:
                    seen.add(r_tuple)
                    unique_results.append(r)
            results = unique_results

        # Handle ORDER BY
        if return_spec.get("order_by"):
            order_field = return_spec["order_by"]["field"]
            reverse = return_spec["order_by"].get("desc", False)

            # Helper function to extract sort value from result
            def get_sort_value(result_item: Dict) -> str:
                """Extract sort value from result item, handling property access like t.created_at."""
                if "." in order_field:
                    # Handle variable.property access (e.g., t.created_at)
                    var, prop = order_field.split(".", 1)
                    if var in result_item:
                        node_data = result_item[var]
                        if prop == "id":
                            return node_data.get("id", "")
                        else:
                            # Access property from node's properties dict
                            return node_data.get("properties", {}).get(prop, "")
                else:
                    # Direct field access
                    return result_item.get(order_field, "")

            results.sort(
                key=get_sort_value,
                reverse=reverse,
            )

        # Handle LIMIT
        if return_spec.get("limit"):
            results = results[: return_spec["limit"]]

        return results

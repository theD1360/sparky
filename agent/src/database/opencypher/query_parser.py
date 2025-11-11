import re
from typing import Any, Dict, List


class QueryParser:
    """Parse openCypher-style queries into executable AST."""

    def parse(self, query: str) -> Dict[str, Any]:
        """Parse query string into structured representation."""
        query = query.strip()

        # Determine query type
        query_type = self._determine_query_type(query)

        result = {"type": query_type}

        if query_type == "match":
            # Extract MATCH clause
            result["match"] = self._extract_match(query)
            # Extract WHERE clause
            result["where"] = self._extract_where(query)
            # Extract RETURN clause
            result["return"] = self._extract_return(query)
        elif query_type == "create":
            result["create"] = self._extract_create(query)
        elif query_type == "update":
            result["update"] = self._extract_update(query)
            result["where"] = self._extract_where(query)
        elif query_type == "delete":
            result["delete"] = self._extract_delete(query)
            result["where"] = self._extract_where(query)

        return result

    def _determine_query_type(self, query: str) -> str:
        """Determine the type of query (match, create, update, delete)."""
        query_upper = query.upper()
        if query_upper.startswith("CREATE"):
            return "create"
        elif query_upper.startswith("UPDATE"):
            return "update"
        elif query_upper.startswith("DELETE"):
            return "delete"
        elif query_upper.startswith("MATCH"):
            return "match"
        else:
            # Default to match for backward compatibility
            return "match"

    def _extract_match(self, query: str) -> Dict:
        """Extract and parse MATCH pattern."""
        # Find MATCH clause
        match_re = re.search(
            r"MATCH\s+(.*?)(?:WHERE|RETURN|$)", query, re.IGNORECASE | re.DOTALL
        )
        if not match_re:
            return {}

        match_text = match_re.group(1).strip()

        # Parse node pattern: (var:Label {prop: value})
        # Parse edge pattern: -[var:TYPE]->
        # Simplified parser for basic patterns

        pattern = {
            "nodes": [],
            "edges": [],
            "variables": {},
        }

        # Extract node patterns
        node_pattern = re.findall(
            r"\((\w+)(?::(\w+))?(?:\s*\{([^}]+)\})?\)", match_text
        )

        for var, label, props in node_pattern:
            node_spec = {"var": var}
            if label:
                node_spec["label"] = label
            if props:
                # Parse simple property constraints
                prop_dict = {}
                for prop in props.split(","):
                    if ":" in prop:
                        key, val = prop.split(":", 1)
                        key = key.strip()
                        val = val.strip().strip("\"'")
                        prop_dict[key] = val
                node_spec["properties"] = prop_dict
            pattern["nodes"].append(node_spec)
            pattern["variables"][var] = "node"

        # Extract edge patterns -[:TYPE]-> or -[var:TYPE]->
        edge_pattern = re.findall(
            r"-\[(?:(\w+):)?(\w+)(?:\*(\d+)\.\.(\d+))?\]->", match_text
        )

        for var, edge_type, min_hops, max_hops in edge_pattern:
            edge_spec = {"type": edge_type}
            if var:
                edge_spec["var"] = var
            if min_hops:
                edge_spec["min_hops"] = int(min_hops)
                edge_spec["max_hops"] = int(max_hops) if max_hops else int(min_hops)
            pattern["edges"].append(edge_spec)

        return pattern

    def _extract_where(self, query: str) -> List:
        """Extract and parse WHERE conditions."""
        where_re = re.search(
            r"WHERE\s+(.*?)(?:RETURN|$)", query, re.IGNORECASE | re.DOTALL
        )
        if not where_re:
            return []

        where_text = where_re.group(1).strip()

        # Parse simple conditions: var.prop = value, var.prop STARTS WITH value
        conditions = []

        # Handle STARTS WITH
        starts_with = re.findall(
            r"(\w+)\.(\w+)\s+STARTS\s+WITH\s+[\"']([^\"']+)[\"']",
            where_text,
            re.IGNORECASE,
        )
        for var, prop, value in starts_with:
            conditions.append(
                {
                    "type": "starts_with",
                    "var": var,
                    "property": prop,
                    "value": value,
                }
            )

        # Handle equality
        equals = re.findall(r"(\w+)\.(\w+)\s*=\s*([^,\s]+)", where_text)
        for var, prop, value in equals:
            value = value.strip().strip("\"'")
            # Convert boolean strings
            if value.lower() == "true":
                value = True
            elif value.lower() == "false":
                value = False
            conditions.append(
                {
                    "type": "equals",
                    "var": var,
                    "property": prop,
                    "value": value,
                }
            )

        return conditions

    def _extract_return(self, query: str) -> Dict:
        """Extract and parse RETURN clause."""
        return_re = re.search(
            r"RETURN\s+(.*?)(?:ORDER|LIMIT|$)", query, re.IGNORECASE | re.DOTALL
        )
        if not return_re:
            return {"fields": ["*"]}

        return_text = return_re.group(1).strip()

        # Handle DISTINCT
        distinct = "DISTINCT" in return_text.upper()
        if distinct:
            return_text = re.sub(r"DISTINCT\s+", "", return_text, flags=re.IGNORECASE)

        # Parse fields
        fields = []
        for field in return_text.split(","):
            field = field.strip()
            # Handle aliases: field as alias
            if " as " in field.lower():
                field_name, alias = re.split(r"\s+as\s+", field, flags=re.IGNORECASE)
                fields.append({"field": field_name.strip(), "alias": alias.strip()})
            else:
                fields.append({"field": field})

        spec = {"fields": fields, "distinct": distinct}

        # Handle ORDER BY
        order_re = re.search(r"ORDER\s+BY\s+(.*?)(?:LIMIT|$)", query, re.IGNORECASE)
        if order_re:
            order_text = order_re.group(1).strip()
            order_desc = "DESC" in order_text.upper()
            order_field = re.sub(
                r"\s+(ASC|DESC)\s*", "", order_text, flags=re.IGNORECASE
            ).strip()
            spec["order_by"] = {"field": order_field, "desc": order_desc}

        # Handle LIMIT
        limit_re = re.search(r"LIMIT\s+(\d+)", query, re.IGNORECASE)
        if limit_re:
            spec["limit"] = int(limit_re.group(1))

        return spec

    def _extract_create(self, query: str) -> Dict:
        """Extract and parse CREATE clause."""
        # Find CREATE clause
        create_re = re.search(
            r"CREATE\s+(.*?)(?:WHERE|RETURN|$)", query, re.IGNORECASE | re.DOTALL
        )
        if not create_re:
            return {"nodes": [], "edges": []}

        create_text = create_re.group(1).strip()

        result = {"nodes": [], "edges": []}

        # Extract node patterns: (var:Label {prop: value})
        node_pattern = re.findall(
            r"\((\w+)(?::(\w+))?(?:\s*\{([^}]+)\})?\)", create_text
        )

        for var, label, props in node_pattern:
            node_spec = {"var": var}
            if label:
                node_spec["label"] = label
            if props:
                # Parse properties
                prop_dict = {}
                for prop in props.split(","):
                    if ":" in prop:
                        key, val = prop.split(":", 1)
                        key = key.strip()
                        val = val.strip().strip("\"'")
                        # Convert to appropriate type
                        if val.lower() == "true":
                            val = True
                        elif val.lower() == "false":
                            val = False
                        elif val.isdigit():
                            val = int(val)
                        elif val.replace(".", "").isdigit():
                            val = float(val)
                        prop_dict[key] = val
                node_spec["properties"] = prop_dict
            result["nodes"].append(node_spec)

        # Extract edge patterns: -[var:TYPE]-> or -[:TYPE]->
        edge_pattern = re.findall(r"-\[(?:(\w+):)?(\w+)\]->", create_text)

        for var, edge_type in edge_pattern:
            edge_spec = {"type": edge_type}
            if var:
                edge_spec["var"] = var
            result["edges"].append(edge_spec)

        return result

    def _extract_update(self, query: str) -> Dict:
        """Extract and parse UPDATE clause."""
        # Find UPDATE clause
        update_re = re.search(
            r"UPDATE\s+(\w+)\s+SET\s+(.*?)(?:WHERE|$)", query, re.IGNORECASE | re.DOTALL
        )
        if not update_re:
            return {"variable": None, "properties": {}}

        var = update_re.group(1).strip()
        set_text = update_re.group(2).strip()

        # Parse SET properties
        properties = {}
        for prop in set_text.split(","):
            if "=" in prop:
                key, val = prop.split("=", 1)
                key = key.strip()
                val = val.strip().strip("\"'")
                # Convert to appropriate type
                if val.lower() == "true":
                    val = True
                elif val.lower() == "false":
                    val = False
                elif val.isdigit():
                    val = int(val)
                elif val.replace(".", "").isdigit():
                    val = float(val)
                properties[key] = val

        return {"variable": var, "properties": properties}

    def _extract_delete(self, query: str) -> Dict:
        """Extract and parse DELETE clause."""
        # Find DELETE clause
        delete_re = re.search(
            r"DELETE\s+(.*?)(?:WHERE|$)", query, re.IGNORECASE | re.DOTALL
        )
        if not delete_re:
            return {"variables": []}

        delete_text = delete_re.group(1).strip()

        # Parse variables to delete
        variables = []
        for var in delete_text.split(","):
            var = var.strip()
            if var:
                variables.append(var)

        return {"variables": variables}

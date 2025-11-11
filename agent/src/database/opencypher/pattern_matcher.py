from typing import Dict, List

from database.models import Node


class PatternMatcher:
    """Match graph patterns from MATCH clauses."""

    def __init__(self, repository):
        self.repository = repository

    def match_pattern(self, pattern: Dict) -> List[Dict]:
        """Find all matches for the given pattern."""
        if not pattern or not pattern.get("nodes"):
            return []

        # Start with first node
        first_node = pattern["nodes"][0]
        candidates = self._match_node(first_node)

        # Build initial bindings
        matches = []
        for node in candidates:
            binding = {first_node["var"]: {"id": node.id, **node.to_dict()}}
            matches.append(binding)

        # If there are edges, traverse
        if pattern.get("edges"):
            matches = self._match_edges(pattern, matches)

        return matches

    def _match_node(self, node_spec: Dict) -> List[Node]:
        """Find nodes matching specification."""
        node_type = node_spec.get("label")
        properties = node_spec.get("properties", {})

        if properties:
            return self.repository.find_nodes_by_properties(properties, node_type)
        elif node_type:
            return self.repository.get_nodes(node_type=node_type)
        else:
            return self.repository.get_nodes()

    def _match_edges(self, pattern: Dict, initial_matches: List[Dict]) -> List[Dict]:
        """Extend matches by following edges."""
        if len(pattern["nodes"]) < 2:
            return initial_matches

        results = []

        for match in initial_matches:
            # Get source node from first variable
            source_var = pattern["nodes"][0]["var"]
            source_id = match[source_var]["id"]

            # Get target specification
            target_spec = pattern["nodes"][1]
            edge_spec = pattern["edges"][0]

            # Find matching neighbors
            edge_type = edge_spec.get("type")
            neighbors = self.repository.get_node_neighbors(
                source_id,
                direction="outgoing",
                edge_types=[edge_type] if edge_type else None,
            )

            for _, target_node in neighbors:
                # Check if target matches specification
                if (
                    target_spec.get("label")
                    and target_node.node_type != target_spec["label"]
                ):
                    continue

                if target_spec.get("properties"):
                    props_match = all(
                        target_node.properties.get(k) == v
                        for k, v in target_spec["properties"].items()
                    )
                    if not props_match:
                        continue

                # Create new binding
                new_match = match.copy()
                new_match[target_spec["var"]] = {
                    "id": target_node.id,
                    **target_node.to_dict(),
                }
                results.append(new_match)

        return results

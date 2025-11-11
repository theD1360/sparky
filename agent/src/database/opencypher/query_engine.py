from typing import Dict, List, Optional

from .filter_evaluator import FilterEvaluator
from .pattern_matcher import PatternMatcher
from .query_parser import QueryParser
from .results_projector import ResultProjector


class QueryEngine:
    """Execute openCypher-like queries."""

    def __init__(self, repository):
        self.repository = repository
        self.parser = QueryParser()
        self.matcher = PatternMatcher(repository)
        self.evaluator = FilterEvaluator()
        self.projector = ResultProjector()

    def execute(self, query: str, _parameters: Optional[Dict] = None) -> List[Dict]:
        """Parse and execute a graph query.

        Args:
            query: OpenCypher-style query string
            _parameters: Optional parameters for parameterized queries (reserved for future use)
        """
        # Parse query
        ast = self.parser.parse(query)

        # Match patterns
        matches = self.matcher.match_pattern(ast["match"])

        # Apply filters
        if ast.get("where"):
            matches = [m for m in matches if self.evaluator.evaluate(ast["where"], m)]

        # Project results
        results = self.projector.project(matches, ast["return"])

        return results

"""Utility functions for converting knowledge graph nodes to LLM history format."""

import logging
from typing import Any, Dict, List

from database.models import Node

logger = logging.getLogger(__name__)


def convert_nodes_to_llm_format(nodes: List[Node]) -> List[Dict[str, Any]]:
    """Convert ChatMessage nodes from the knowledge graph to LLM format.
    
    Args:
        nodes: List of ChatMessage Node objects from the knowledge graph
        
    Returns:
        List of message dictionaries in format: {"role": "user/model", "parts": ["content"]}
    """
    messages = []
    
    for node in nodes:
        try:
            # Extract role from node properties (default to 'user' if not found)
            role = node.properties.get("role", "user") if node.properties else "user"
            
            # Get content from node
            content = node.content or ""
            
            # Build message in LLM format
            message = {
                "role": role,
                "parts": [content]
            }
            
            messages.append(message)
            
        except Exception as e:
            logger.warning(f"Failed to convert node {node.id} to LLM format: {e}")
            continue
    
    return messages


def format_nodes_for_summary(nodes: List[Node]) -> str:
    """Format ChatMessage nodes as text for summarization.
    
    Similar to the previous HistoryManager.format_for_summary() method.
    Creates a concise text dump of a conversation suitable for summarization.
    
    Args:
        nodes: List of ChatMessage Node objects from the knowledge graph
        
    Returns:
        Formatted string with role: content pairs
    """
    lines: List[str] = []
    
    try:
        for node in nodes or []:
            # Extract role from node properties
            role = node.properties.get("role", "") if node.properties else ""
            role_str = str(role) or ""
            
            # Get content from node
            content = node.content or ""
            
            if content:
                lines.append(f"{role_str}: {content}")
                
    except Exception as e:
        logger.warning(f"Failed to format nodes for summary: {e}")
    
    # Return last 400 lines to limit size (same as previous implementation)
    return "\n".join(lines[-400:])


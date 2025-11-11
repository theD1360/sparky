import json
import os
from typing import Dict, Any


def validate_mcp_config(path: str) -> Dict[str, Any]:
    """
    Validate the mcp.json configuration file.

    Checks for:
    - Valid JSON format
    - Existence of declared Python module files
    - Duplicate TCP ports
    """
    errors = []
    warnings = []

    # 1. Check if file exists
    if not os.path.exists(path):
        return {"errors": [f"File not found at {path}"], "warnings": []}

    # 2. Check for valid JSON
    try:
        with open(path, "r") as f:
            config = json.load(f)
    except json.JSONDecodeError as e:
        return {"errors": [f"Invalid JSON: {e}"], "warnings": []}

    # 3. Validate structure and content
    if "servers" not in config or not isinstance(config["servers"], list):
        return {"errors": ["'servers' key is missing or not a list"], "warnings": []}

    ports = {}
    for i, server in enumerate(config["servers"]):
        # Check for 'name'
        if "name" not in server:
            errors.append(f"Server at index {i} is missing 'name'")

        # Check for 'module' and file existence
        if "module" in server:
            module_path = os.path.join("src", "servers", f"{server['module']}.py")
            if not os.path.exists(module_path):
                errors.append(
                    f"Module file not found for server '{server.get('name', 'N/A')}': {module_path}"
                )

        # Check for duplicate ports
        if "port" in server:
            port = server["port"]
            if port in ports:
                errors.append(
                    f"Duplicate port {port} found for servers '{server.get('name', 'N/A')}' and '{ports[port]}'"
                )
            else:
                ports[port] = server.get("name", "N/A")

    return {"errors": errors, "warnings": warnings}

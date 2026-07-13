"""Model listing API endpoints."""

from typing import Any, Dict, List

from fastapi import APIRouter, Depends
from middleware.auth_middleware import get_current_user
from pydantic import BaseModel
from services.model_catalog import list_available_models

router = APIRouter(prefix="/api", tags=["models"])


class ModelInfo(BaseModel):
    """A selectable LLM model."""

    id: str
    display_name: str
    description: str = ""
    is_default: bool = False


class ModelsResponse(BaseModel):
    """Available models for the UI."""

    models: List[ModelInfo]
    default: str


@router.get("/models", response_model=ModelsResponse)
async def get_models(current_user=Depends(get_current_user)) -> Dict[str, Any]:
    """Return Gemini models the user may assign to a chat."""
    models = list_available_models()
    default = next((m["id"] for m in models if m.get("is_default")), models[0]["id"])
    return {
        "models": [
            ModelInfo(
                id=m["id"],
                display_name=m.get("display_name") or m["id"],
                description=m.get("description") or "",
                is_default=bool(m.get("is_default")),
            )
            for m in models
        ],
        "default": default,
    }

from __future__ import annotations

import json
from functools import lru_cache
from typing import Any, Dict, List, Optional

import httpx
from fastapi import Depends, FastAPI, HTTPException, status
from pydantic import BaseModel, Field

from .guards import PatchError, extract_json_array
from .model_client import ModelClient


class ViolationPayload(BaseModel):
    violation: Dict[str, Any] = Field(..., description="Violation descriptor produced by the detector")
    manifest: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Original manifest object that triggered the violation (optional)",
    )
    metadata: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Additional context for the proposer (optional)",
    )


class ProposeResponse(BaseModel):
    patch: List[Dict[str, Any]] = Field(
        ..., description="JSON Patch operations that address the violation"
    )


def create_app() -> FastAPI:
    app = FastAPI(
        title="K8s Auto Fix Proposer",
        description="Generates JSON patches to remediate Kubernetes manifest violations.",
        version="0.1.0",
    )

    @app.post("/propose", response_model=ProposeResponse)
    def propose_patch(
        payload: ViolationPayload,
        client: ModelClient = Depends(get_model_client),
    ) -> ProposeResponse:
        prompt = build_prompt(payload)
        try:
            content = client.request_patch(prompt)
            patch = extract_json_array(content)
        except httpx.HTTPStatusError as exc:  # pragma: no cover - relies on external service
            raise HTTPException(
                status_code=exc.response.status_code,
                detail=f"Model endpoint returned error: {exc.response.text}",
            ) from exc
        except (httpx.HTTPError, RuntimeError, ValueError, PatchError) as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=str(exc),
            ) from exc

        return ProposeResponse(patch=patch)

    return app


@lru_cache()
def get_model_client() -> ModelClient:
    return ModelClient.from_env()


def build_prompt(payload: ViolationPayload) -> str:
    sections = ["You are an assistant that fixes Kubernetes manifests using JSON Patch."]
    violation_json = json.dumps(payload.violation, indent=2, sort_keys=True)
    sections.append(f"Violation details:\n{violation_json}")
    if payload.manifest is not None:
        manifest_json = json.dumps(payload.manifest, indent=2, sort_keys=True)
        sections.append(f"Problematic manifest:\n{manifest_json}")
    if payload.metadata is not None:
        metadata_json = json.dumps(payload.metadata, indent=2, sort_keys=True)
        sections.append(f"Additional context:\n{metadata_json}")
    sections.append(
        "Return only a JSON array compatible with RFC 6902 JSON Patch. No explanations."
    )
    return "\n\n".join(sections)


app = create_app()


__all__ = [
    "app",
    "create_app",
    "build_prompt",
    "ViolationPayload",
    "ProposeResponse",
]

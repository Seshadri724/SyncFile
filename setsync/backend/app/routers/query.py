import os
import re
import json
import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.dependencies import verify_token
from app.services.set_engine import get_computed_sets_from_db, get_summary_from_db
from pydantic import BaseModel
from typing import Optional, Any, Dict

router = APIRouter(
    prefix="/query",
    tags=["query"],
    dependencies=[Depends(verify_token)]
)

class NaturalQueryRequest(BaseModel):
    prompt: str
    source_x: str
    source_y: str

class NaturalQueryResponse(BaseModel):
    filters: Dict[str, Any]
    summary: Dict[str, Any]
    files: list

def _fallback_parse_prompt(prompt: str) -> Dict[str, Any]:
    """Simple regex-based parsing fallback if no LLM API keys are configured."""
    p_lower = prompt.lower()
    
    # Default filters
    filters = {
        "view_type": "union",
        "q": None,
        "min_size": None,
        "max_size": None
    }
    
    # Determine view type
    if "conflict" in p_lower:
        filters["view_type"] = "conflicts"
    elif "both" in p_lower or "intersection" in p_lower or "shared" in p_lower:
        filters["view_type"] = "intersection"
    elif any(w in p_lower for w in ["only on a", "only on left", "only a", "on a", "on left"]):
        filters["view_type"] = "only_a"
    elif any(w in p_lower for w in ["only on b", "only on right", "only b", "on b", "on right"]):
        filters["view_type"] = "only_b"
        
    # Check for file extension search
    ext_match = re.search(r'\.([a-zA-Z0-9]+)', p_lower)
    if ext_match:
        filters["q"] = ext_match.group(0)
    else:
        # Check for word in quotes
        quote_match = re.search(r'["\']([^"\']+)["\']', p_lower)
        if quote_match:
            filters["q"] = quote_match.group(1)

    # Check for size constraints (e.g. larger than 1MB)
    size_pattern = r'(?:larger|greater|more|bigger|smaller|less|fewer)\s+than\s+(\d+(?:\.\d+)?)\s*(kb|mb|gb|bytes|b)?'
    size_match = re.search(size_pattern, p_lower)
    if size_match:
        val = float(size_match.group(1))
        unit = size_match.group(2) or "bytes"
        
        # Convert to bytes
        bytes_val = int(val)
        if "kb" in unit:
            bytes_val = int(val * 1024)
        elif "mb" in unit:
            bytes_val = int(val * 1024 * 1024)
        elif "gb" in unit:
            bytes_val = int(val * 1024 * 1024 * 1024)
            
        if any(w in p_lower for w in ["larger", "greater", "more", "bigger"]):
            filters["min_size"] = bytes_val
        else:
            filters["max_size"] = bytes_val
            
    return filters

async def _llm_parse_prompt(prompt: str, api_key: str) -> Dict[str, Any]:
    """Query Gemini 1.5 Flash to translate the prompt into structured search parameters."""
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
    
    system_prompt = (
        "You are an API query parameter translator. Translate user natural language queries into a JSON object. "
        "Allowed keys:\n"
        "- view_type: string ('union', 'intersection', 'only_a', 'only_b', 'conflicts')\n"
        "- q: string search query matching filename or path (or null if not specified)\n"
        "- min_size: integer representing minimum file size in bytes (or null)\n"
        "- max_size: integer representing maximum file size in bytes (or null)\n"
        "Do not include any extra text, markdown wrappers, or backticks in the response. Return ONLY raw JSON."
    )
    
    payload = {
        "contents": [
            {
                "parts": [
                    {"text": f"System Instruction: {system_prompt}\nUser Prompt: '{prompt}'"}
                ]
            }
        ]
    }
    
    async with httpx.AsyncClient() as client:
        response = await client.post(url, json=payload, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        raw_text = data["contents"][0]["parts"][0]["text"].strip()
        # Clean up any potential markdown json blocks
        if raw_text.startswith("```"):
            lines = raw_text.splitlines()
            if lines[0].startswith("```json") or lines[0].startswith("```"):
                raw_text = "\n".join(lines[1:-1]).strip()
                
        return json.loads(raw_text)

@router.post("/natural", response_model=NaturalQueryResponse)
async def query_natural_language(
    request: NaturalQueryRequest,
    db: AsyncSession = Depends(get_db)
):
    prompt = request.prompt
    api_key = os.getenv("GEMINI_API_KEY")
    
    # 1. Parse prompt
    filters = None
    if api_key:
        try:
            filters = await _llm_parse_prompt(prompt, api_key)
        except Exception as e:
            print(f"LLM parsing failed: {e}. Falling back to regex parser.")
            
    if not filters:
        filters = _fallback_parse_prompt(prompt)
        
    # Standardize values
    view_type = filters.get("view_type", "union")
    q = filters.get("q")
    min_size = filters.get("min_size")
    max_size = filters.get("max_size")
    
    # 2. Run set engine query using parsed parameters
    try:
        summary = await get_summary_from_db(db, request.source_x, request.source_y)
        files_list = await get_computed_sets_from_db(
            db=db,
            source_x=request.source_x,
            source_y=request.source_y,
            view_type=view_type,
            q=q,
            min_size=min_size,
            max_size=max_size,
            limit=100,
            offset=0
        )
        
        return NaturalQueryResponse(
            filters=filters,
            summary={
                "total_files": summary.total_files,
                "union_count": summary.union_count,
                "intersection_count": summary.intersection_count,
                "only_a_count": summary.only_a_count,
                "only_b_count": summary.only_b_count,
                "conflict_count": summary.conflict_count
            },
            files=[f.model_dump() for f in files_list]
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

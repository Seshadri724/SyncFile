import os
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from app.schemas.sets import UnifiedFileRow, SetSummaryStrip
from typing import List, Optional, Dict, Any
import datetime

# SQL Queries defining each set logic view

QUERY_BOTH_PATH = """
SELECT 
  a.id || ':' || b.id as id,
  a.relative_path,
  a.size_bytes,
  a.hash_sha256,
  'Both' as location,
  a.path as path_a,
  b.path as path_b,
  a.mtime as mtime_a,
  b.mtime as mtime_b
FROM file_records a
JOIN file_records b ON a.relative_path = b.relative_path
WHERE a.source_pc = 'A' AND b.source_pc = 'B' AND a.hash_sha256 = b.hash_sha256
"""

QUERY_BOTH_HASH = """
SELECT 
  a.id || ':' || b.id as id,
  a.relative_path,
  a.size_bytes,
  a.hash_sha256,
  'Both' as location,
  a.path as path_a,
  b.path as path_b,
  a.mtime as mtime_a,
  b.mtime as mtime_b
FROM file_records a
JOIN file_records b ON a.hash_sha256 = b.hash_sha256
WHERE a.source_pc = 'A' AND b.source_pc = 'B' AND a.relative_path != b.relative_path
  AND a.relative_path NOT IN (SELECT relative_path FROM file_records WHERE source_pc = 'B')
  AND b.relative_path NOT IN (SELECT relative_path FROM file_records WHERE source_pc = 'A')
"""

QUERY_CONFLICT = """
SELECT 
  a.id || ':' || b.id as id,
  a.relative_path,
  a.size_bytes,
  a.hash_sha256,
  'Conflict' as location,
  a.path as path_a,
  b.path as path_b,
  a.mtime as mtime_a,
  b.mtime as mtime_b
FROM file_records a
JOIN file_records b ON a.relative_path = b.relative_path
WHERE a.source_pc = 'A' AND b.source_pc = 'B' AND a.hash_sha256 != b.hash_sha256
"""

QUERY_ONLY_A = """
SELECT 
  'a:' || a.id as id,
  a.relative_path,
  a.size_bytes,
  a.hash_sha256,
  'A' as location,
  a.path as path_a,
  NULL as path_b,
  a.mtime as mtime_a,
  NULL as mtime_b
FROM file_records a
WHERE a.source_pc = 'A'
  AND a.relative_path NOT IN (SELECT relative_path FROM file_records WHERE source_pc = 'B')
  AND a.hash_sha256 NOT IN (SELECT hash_sha256 FROM file_records WHERE source_pc = 'B')
"""

QUERY_ONLY_B = """
SELECT 
  'b:' || b.id as id,
  b.relative_path,
  b.size_bytes,
  b.hash_sha256,
  'B' as location,
  NULL as path_a,
  b.path as path_b,
  NULL as mtime_a,
  b.mtime as mtime_b
FROM file_records b
WHERE b.source_pc = 'B'
  AND b.relative_path NOT IN (SELECT relative_path FROM file_records WHERE source_pc = 'A')
  AND b.hash_sha256 NOT IN (SELECT hash_sha256 FROM file_records WHERE source_pc = 'A')
"""

# Helper to choose base query depending on view type
def _get_base_query(view_type: str) -> str:
    if view_type == "intersection":
        return f"SELECT * FROM ({QUERY_BOTH_PATH}) UNION ALL SELECT * FROM ({QUERY_BOTH_HASH})"
    elif view_type == "only_a":
        return QUERY_ONLY_A
    elif view_type == "only_b":
        return QUERY_ONLY_B
    elif view_type == "conflicts":
        return QUERY_CONFLICT
    else:
        # "union" - everything
        return f"""
        SELECT * FROM ({QUERY_BOTH_PATH})
        UNION ALL
        SELECT * FROM ({QUERY_BOTH_HASH})
        UNION ALL
        SELECT * FROM ({QUERY_CONFLICT})
        UNION ALL
        SELECT * FROM ({QUERY_ONLY_A})
        UNION ALL
        SELECT * FROM ({QUERY_ONLY_B})
        """

def _parse_db_datetime(val: Any) -> Optional[datetime.datetime]:
    if not val:
        return None
    if isinstance(val, datetime.datetime):
        return val
    try:
        val_str = str(val).replace(" ", "T")
        if val_str.endswith("Z"):
            val_str = val_str[:-1]
        # Drop microsecond timezone offset indicators if present to make parsing clean
        if "+" in val_str:
            val_str = val_str.split("+")[0]
        return datetime.datetime.fromisoformat(val_str)
    except Exception:
        return None

async def get_computed_sets_from_db(
    db: AsyncSession,
    view_type: str = "union",
    q: Optional[str] = None,
    min_size: Optional[int] = None,
    max_size: Optional[int] = None
) -> List[UnifiedFileRow]:
    base_sql = _get_base_query(view_type)
    
    # Wrap in filter wrapper
    wrapper_sql = f"SELECT * FROM ({base_sql}) WHERE 1=1"
    params: Dict[str, Any] = {}
    
    if q:
        # Support simple wildcard search
        wrapper_sql += " AND (relative_path LIKE :q_like)"
        params["q_like"] = f"%{q}%"
        
    if min_size is not None:
        wrapper_sql += " AND size_bytes >= :min_size"
        params["min_size"] = min_size
        
    if max_size is not None:
        wrapper_sql += " AND size_bytes <= :max_size"
        params["max_size"] = max_size
        
    wrapper_sql += " ORDER BY relative_path ASC"
    
    result = await db.execute(text(wrapper_sql), params)
    rows = result.fetchall()
    
    file_rows: List[UnifiedFileRow] = []
    for r in rows:
        # r behaves like a tuple or mapping
        # SQLite names: id, relative_path, size_bytes, hash_sha256, location, path_a, path_b, mtime_a, mtime_b
        name = os.path.basename(r.relative_path)
        file_rows.append(UnifiedFileRow(
            id=r.id,
            name=name,
            relative_path=r.relative_path,
            size_bytes=r.size_bytes,
            hash_sha256=r.hash_sha256,
            location=r.location,
            path_a=r.path_a,
            path_b=r.path_b,
            mtime_a=_parse_db_datetime(r.mtime_a),
            mtime_b=_parse_db_datetime(r.mtime_b),
        ))
        
    return file_rows

async def get_summary_from_db(db: AsyncSession) -> SetSummaryStrip:
    # Run cheap COUNT queries
    sql_intersection = f"SELECT COUNT(*) FROM ({QUERY_BOTH_PATH}) UNION ALL SELECT COUNT(*) FROM ({QUERY_BOTH_HASH})"
    sql_conflict = f"SELECT COUNT(*) FROM ({QUERY_CONFLICT})"
    sql_only_a = f"SELECT COUNT(*) FROM ({QUERY_ONLY_A})"
    sql_only_b = f"SELECT COUNT(*) FROM ({QUERY_ONLY_B})"
    
    # Exec integrations
    intersection_rows = (await db.execute(text(sql_intersection))).scalars().all()
    intersection_count = sum(intersection_rows)
    
    conflict_count = (await db.execute(text(sql_conflict))).scalar_one()
    only_a_count = (await db.execute(text(sql_only_a))).scalar_one()
    only_b_count = (await db.execute(text(sql_only_b))).scalar_one()
    
    union_count = intersection_count + conflict_count + only_a_count + only_b_count
    
    return SetSummaryStrip(
        total_files=union_count,
        union_count=union_count,
        intersection_count=intersection_count,
        only_a_count=only_a_count,
        only_b_count=only_b_count,
        conflict_count=conflict_count
    )

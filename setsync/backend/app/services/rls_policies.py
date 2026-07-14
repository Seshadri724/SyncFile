from sqlalchemy.ext.asyncio import AsyncConnection
import logging

logger = logging.getLogger("setsync.rls")

RLS_SQL_STATEMENTS = [
    # 1. Enable RLS on file_records, sources, plans, plan_items
    "ALTER TABLE file_records ENABLE ROW LEVEL SECURITY;",
    "ALTER TABLE sources ENABLE ROW LEVEL SECURITY;",
    "ALTER TABLE plans ENABLE ROW LEVEL SECURITY;",
    "ALTER TABLE plan_items ENABLE ROW LEVEL SECURITY;",
    
    # 2. Drop existing policies to prevent conflicts
    "DROP POLICY IF EXISTS tenant_isolation_policy ON file_records;",
    "DROP POLICY IF EXISTS tenant_isolation_policy ON sources;",
    "DROP POLICY IF EXISTS tenant_isolation_policy ON plans;",
    "DROP POLICY IF EXISTS tenant_isolation_policy ON plan_items;",
    
    # 3. Create policies enforcing local session variable 'app.current_org_id'
    "CREATE POLICY tenant_isolation_policy ON file_records FOR ALL USING (org_id = current_setting('app.current_org_id', true));",
    "CREATE POLICY tenant_isolation_policy ON sources FOR ALL USING (org_id = current_setting('app.current_org_id', true));",
    "CREATE POLICY tenant_isolation_policy ON plans FOR ALL USING (org_id = current_setting('app.current_org_id', true));",
    "CREATE POLICY tenant_isolation_policy ON plan_items FOR ALL USING (org_id = current_setting('app.current_org_id', true));"
]

async def apply_rls_policies(conn: AsyncConnection) -> None:
    """Applies PostgreSQL Row-Level Security policies to file_records and sources tables.
    Gracefully no-ops if dialect is not PostgreSQL (e.g. SQLite in local dev/testing)."""
    if conn.dialect.name != "postgresql":
        logger.info("Skipping RLS policies setup: database engine is not PostgreSQL (%s)", conn.dialect.name)
        return
        
    logger.info("Initializing PostgreSQL Row-Level Security (RLS) policies...")
    try:
        for stmt in RLS_SQL_STATEMENTS:
            await conn.execute(stmt)
        logger.info("PostgreSQL Row-Level Security (RLS) policies applied successfully.")
    except Exception as e:
        logger.error("Failed to apply PostgreSQL RLS policies: %s", e)
        raise e

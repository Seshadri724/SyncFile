import pytest
import sqlite3
import os
import sys
import keyring

# Dynamically resolve root project path for importing agent package
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from keyring.backend import KeyringBackend
from agent.config import get_agent_config, AGENT_DB_PATH
from agent.db import init_agent_db, set_config

# 1. Custom mock keyring backend to run securely inside headless container sandboxes
class InMemoryKeyring(KeyringBackend):
    priority = 10
    
    def __init__(self):
        self.storage = {}
        
    def get_password(self, servicename, username):
        return self.storage.get((servicename, username))
        
    def set_password(self, servicename, username, password):
        self.storage[(servicename, username)] = password
        
    def delete_password(self, servicename, username):
        self.storage.pop((servicename, username), None)

@pytest.fixture(autouse=True)
def setup_mock_keyring():
    mock_backend = InMemoryKeyring()
    keyring.set_keyring(mock_backend)
    yield mock_backend

def test_agent_keyring_sensitive_credentials():
    # Setup test agent database cache
    if os.path.exists(AGENT_DB_PATH):
        os.remove(AGENT_DB_PATH)
    init_agent_db()
    
    try:
        tenant_key = "3" * 64
        agent_key = "4" * 64
        regular_config = "http://localhost:8000"
        
        # 1. Write sensitive credentials using set_config
        set_config("tenant_key", tenant_key)
        set_config("agent_key", agent_key)
        
        # 2. Write regular config
        set_config("core_url", regular_config)
        
        # 3. Assert sensitive config is saved in keyring
        assert keyring.get_password("setsync", "tenant_key") == tenant_key
        assert keyring.get_password("setsync", "agent_key") == agent_key
        
        # 4. Assert regular config is NOT in keyring
        assert keyring.get_password("setsync", "core_url") is None
        
        # 5. Assert sensitive config has been pruned from SQLite database plain text
        conn = sqlite3.connect(AGENT_DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM config WHERE key = ?", ("tenant_key",))
        assert cursor.fetchone() is None
        
        # Assert regular config still exists in SQLite
        cursor.execute("SELECT value FROM config WHERE key = ?", ("core_url",))
        assert cursor.fetchone()[0] == regular_config
        conn.close()
        
        # 6. Retrieve config using get_agent_config and assert correctness
        assert get_agent_config("tenant_key") == tenant_key
        assert get_agent_config("agent_key") == agent_key
        assert get_agent_config("core_url") == regular_config
        
    finally:
        # Cleanup
        if os.path.exists(AGENT_DB_PATH):
            os.remove(AGENT_DB_PATH)

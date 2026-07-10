import pytest
from app.services.policy import is_path_protected, validate_action_policy
from unittest.mock import patch

def test_is_path_protected():
    patterns = ["**/work/**", "**/*.key", "**/protected/**"]
    
    # Matches
    assert is_path_protected("work/docs/file.txt", patterns) is True
    assert is_path_protected("some/path/work/file.txt", patterns) is True
    assert is_path_protected("backup/ssh_key.key", patterns) is True
    assert is_path_protected("protected/secrets.json", patterns) is True
    
    # Non-matches
    assert is_path_protected("workspace/docs/file.txt", patterns) is False
    assert is_path_protected("backup/ssh_key.key.backup", patterns) is False
    assert is_path_protected("projects/app/main.py", patterns) is False

@patch("app.services.policy.load_policy")
def test_validate_action_policy_rules(mock_load_policy):
    mock_load_policy.return_value = {
        "never_delete_unique": True,
        "protected_paths": ["**/work/**"],
        "max_batch_delete": 10,
        "require_approval_above_gb": 1.0 # 1 GB
    }
    
    # 1. Test protected path triggers block
    with pytest.raises(ValueError) as excinfo:
        validate_action_policy("my/work/file.txt", "copy")
    assert "blocked" in str(excinfo.value)
    
    # 2. Test unique delete without force triggers block
    with pytest.raises(ValueError) as excinfo:
        validate_action_policy("some/file.txt", "delete", is_unique=True, force=False)
    assert "refused" in str(excinfo.value)
    
    # 3. Test unique delete with force bypasses block
    validate_action_policy("some/file.txt", "delete", is_unique=True, force=True) # Should pass
    
    # 4. Test exceeding size limit without force triggers block
    large_size = int(1.5 * 1024 * 1024 * 1024) # 1.5 GB
    with pytest.raises(ValueError) as excinfo:
        validate_action_policy("some/file.txt", "copy", size_bytes=large_size, force=False)
    assert "exceeds" in str(excinfo.value)
    
    # 5. Test exceeding size limit with force passes
    validate_action_policy("some/file.txt", "copy", size_bytes=large_size, force=True) # Should pass

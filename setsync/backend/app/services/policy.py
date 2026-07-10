import os
import yaml
import fnmatch
from typing import Dict, Any, List

DEFAULT_POLICY = {
    "never_delete_unique": True,
    "protected_paths": [
        "**/work/**",
        "**/*.key",
        "**/protected/**"
    ],
    "max_batch_delete": 50,
    "require_approval_above_gb": 5.0
}

def load_policy() -> Dict[str, Any]:
    policy_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "policy.yaml")
    if not os.path.exists(policy_path):
        return DEFAULT_POLICY
        
    try:
        with open(policy_path, "r") as f:
            data = yaml.safe_load(f)
            if not isinstance(data, dict):
                return DEFAULT_POLICY
            # Merge with default policy keys if any are missing
            merged = DEFAULT_POLICY.copy()
            merged.update(data)
            return merged
    except Exception as e:
        print(f"Failed to parse policy.yaml: {e}. Using defaults.")
        return DEFAULT_POLICY

def is_path_protected(relative_path: str, protected_patterns: List[str]) -> bool:
    """Returns True if the file path matches any glob pattern in the protected_paths list."""
    path_lower = relative_path.lower()
    for pattern in protected_patterns:
        pat_lower = pattern.lower()
        # Direct match
        if fnmatch.fnmatch(path_lower, pat_lower) or fnmatch.fnmatch(relative_path, pattern):
            return True
        # If pattern starts with **/, try matching without it for root level matches
        if pat_lower.startswith("**/"):
            stripped_pat = pat_lower[3:]
            if fnmatch.fnmatch(path_lower, stripped_pat):
                return True
        # If path doesn't start with /, also try matching prepended slash
        if not path_lower.startswith("/"):
            if fnmatch.fnmatch(f"/{path_lower}", pat_lower):
                return True
    return False

def validate_action_policy(
    relative_path: str,
    action_type: str,
    size_bytes: int = 0,
    is_unique: bool = False,
    force: bool = False
) -> None:
    """Validates an action against loaded YAML safety policies. Raises ValueError on violation."""
    policy = load_policy()
    
    # 1. Check protected paths
    if is_path_protected(relative_path, policy.get("protected_paths", [])):
        raise ValueError(
            f"Safety Block: Action '{action_type}' on path '{relative_path}' is blocked. "
            f"Path matches a protected estate pattern."
        )
        
    # 2. Check unique delete policy
    if action_type == "delete" and is_unique:
        if policy.get("never_delete_unique", True) and not force:
            raise ValueError(
                f"Safety Block: Deletion of '{relative_path}' refused. "
                f"This file holds unique content not present on any other active source."
            )
            
    # 3. Check large size threshold
    limit_bytes = int(policy.get("require_approval_above_gb", 5.0) * 1024 * 1024 * 1024)
    if size_bytes > limit_bytes and not force:
        raise ValueError(
            f"Safety Block: Operation size {size_bytes} bytes exceeds the approval threshold of "
            f"{policy.get('require_approval_above_gb')} GB. Override with force=true if confirmed."
        )

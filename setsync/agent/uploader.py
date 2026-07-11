import requests
import json
import hmac
import hashlib
import time
import gzip
from typing import List, Dict, Any
from agent.config import get_agent_config

def get_auth_headers(payload_data: str = None) -> Dict[str, str]:
    source_id = get_agent_config("source_id")
    agent_key = get_agent_config("agent_key")
    
    if source_id and agent_key:
        return {
            "X-SetSync-Source-ID": source_id,
            "X-SetSync-Agent-Key": agent_key,
            "Content-Type": "application/json"
        }
    else:
        master_token = get_agent_config("api_token", "setsync_secret_token_123")
        timestamp = str(int(time.time()))
        message = f"{timestamp}.{payload_data or ''}"
        sig = hmac.new(
            master_token.encode("utf-8"),
            message.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()
        return {
            "X-SetSync-Timestamp": timestamp,
            "X-SetSync-Signature": sig,
            "Content-Type": "application/json"
        }

def upload_inventory_data(files: List[Dict[str, Any]], source_id_arg: str = None) -> Dict[str, Any]:
    core_url = get_agent_config("core_url", "http://localhost:8000")
    source_id = source_id_arg or get_agent_config("source_id")
    
    url = f"{core_url.rstrip('/')}/inventory/upload"
    
    payload = {
        "source_id": source_id,
        "files": files
    }
    
    json_data = json.dumps(payload, separators=(',', ':'))
    headers = get_auth_headers(json_data)
    
    # Compress with gzip if payload is larger than 1KB
    post_data = json_data.encode("utf-8")
    if len(post_data) > 1024:
        post_data = gzip.compress(post_data)
        headers["Content-Encoding"] = "gzip"
        
    try:
        response = requests.post(url, data=post_data, headers=headers, timeout=60)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error communicating with Core Service: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"Response: {e.response.text}")
        raise e

def upload_inventory_delta(action: str, file_item: Dict[str, Any], source_id_arg: str = None) -> Dict[str, Any]:
    core_url = get_agent_config("core_url", "http://localhost:8000")
    source_id = source_id_arg or get_agent_config("source_id")
    
    url = f"{core_url.rstrip('/')}/inventory/delta"
    
    payload = {
        "source_id": source_id,
        "action": action,
        "file": file_item
    }
    
    json_data = json.dumps(payload, separators=(',', ':'))
    headers = get_auth_headers(json_data)
    
    try:
        response = requests.patch(url, data=json_data, headers=headers, timeout=30)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error sending delta to Core Service: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"Response: {e.response.text}")
        raise e

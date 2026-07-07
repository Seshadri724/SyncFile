import requests
import json
import hmac
import hashlib
import time
from typing import List, Dict, Any
from agent.config import CORE_SERVICE_URL, API_TOKEN, PC_ID

def upload_inventory_data(files: List[Dict[str, Any]], pc_id: str = None) -> Dict[str, Any]:
    target_pc = pc_id or PC_ID
    url = f"{CORE_SERVICE_URL.rstrip('/')}/inventory/upload"
    
    payload = {
        "source_pc": target_pc,
        "files": files
    }
    
    # Standardize JSON formatting for request signing
    json_data = json.dumps(payload, separators=(',', ':'))
    timestamp = str(int(time.time()))
    
    # Message to sign: timestamp + "." + request_body
    message = f"{timestamp}.{json_data}"
    
    # Compute signature using shared secret API_TOKEN
    sig = hmac.new(
        API_TOKEN.encode("utf-8"),
        message.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()
    
    headers = {
        "X-SetSync-Timestamp": timestamp,
        "X-SetSync-Signature": sig,
        "Content-Type": "application/json"
    }
    
    try:
        response = requests.post(url, data=json_data, headers=headers, timeout=60)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error communicating with Core Service: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"Response: {e.response.text}")
        raise e

def upload_inventory_delta(action: str, file_item: Dict[str, Any], pc_id: str = None) -> Dict[str, Any]:
    target_pc = pc_id or PC_ID
    url = f"{CORE_SERVICE_URL.rstrip('/')}/inventory/delta"
    
    payload = {
        "source_pc": target_pc,
        "action": action,
        "file": file_item
    }
    
    json_data = json.dumps(payload, separators=(',', ':'))
    timestamp = str(int(time.time()))
    message = f"{timestamp}.{json_data}"
    
    sig = hmac.new(
        API_TOKEN.encode("utf-8"),
        message.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()
    
    headers = {
        "X-SetSync-Timestamp": timestamp,
        "X-SetSync-Signature": sig,
        "Content-Type": "application/json"
    }
    
    try:
        response = requests.patch(url, data=json_data, headers=headers, timeout=30)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error sending delta to Core Service: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"Response: {e.response.text}")
        raise e

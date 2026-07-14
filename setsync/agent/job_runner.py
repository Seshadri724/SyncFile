import os
import time
import requests
import json
import traceback
from agent.config import get_agent_config
from agent.uploader import get_auth_headers
from agent.chunked_upload import chunked_upload_file, chunked_download_file
from app.transfer.delta_sync import (
    generate_block_signatures,
    compute_delta,
    apply_delta
)

def run_job_loop():
    core_url = get_agent_config("core_url", "http://localhost:8000")
    source_id = get_agent_config("source_id")
    
    if not source_id:
        print("Agent is not initialized. Please run 'setsync-agent init' first.")
        return

    print(f"Starting Job Executor Loop for source_id: {source_id} ...")
    
    while True:
        try:
            # Poll pending jobs
            poll_url = f"{core_url.rstrip('/')}/jobs/poll"
            headers = get_auth_headers()
            
            response = requests.get(poll_url, headers=headers, timeout=15)
            response.raise_for_status()
            jobs = response.json()
            
            for job in jobs:
                job_id = job["id"]
                file_path = job["file_path"]
                action_type = job["action_type"]
                status = job["status"]
                
                # Resolve absolute path on this agent's filesystem
                roots_str = get_agent_config("roots", "./test_pc_a")
                roots = [r.strip() for r in roots_str.split(",") if r.strip()]
                root_dir = roots[0] if roots else "./test_pc_a"
                file_abs = os.path.abspath(os.path.join(root_dir, file_path))
                
                print(f"Processing job {job_id}: {action_type} on '{file_path}' (status: {status})")
                
                try:
                    if job["destination_id"] == source_id and status == "pending":
                        # 1. We are destination: Compute block signatures of target file (if exists)
                        print(f"  -> Generating signatures for target: '{file_abs}'")
                        sigs = generate_block_signatures(file_abs)
                        
                        # Upload signatures
                        sig_url = f"{core_url.rstrip('/')}/jobs/{job_id}/signatures"
                        payload = {"signatures": sigs}
                        res = requests.post(sig_url, json=payload, headers=headers, timeout=30)
                        res.raise_for_status()
                        print(f"  -> Signatures uploaded successfully.")
                        
                    elif job["source_id"] == source_id and status == "signatures_ready":
                        # 2. We are source: Fetch target signatures, compute delta ops
                        print(f"  -> Fetching signatures for job {job_id}")
                        sig_url = f"{core_url.rstrip('/')}/jobs/{job_id}/signatures"
                        res = requests.get(sig_url, headers=headers, timeout=30)
                        res.raise_for_status()
                        raw_sigs = res.json()
                        
                        # Critical: convert keys back to integers for Adler map matching
                        adler_map = {int(k): v for k, v in raw_sigs.items()}
                        
                        print(f"  -> Computing delta from source file: '{file_abs}'")
                        delta = compute_delta(adler_map, file_abs)
                        
                        # Convert any bytes payload (like data block) to hex string for JSON transport
                        serializable_delta = []
                        for op, val in delta:
                            if op == "data" and isinstance(val, bytes):
                                serializable_delta.append((op, val.hex()))
                            else:
                                serializable_delta.append((op, val))
                                
                        # Determine if we should use chunked transfer (e.g. payload > 512KB)
                        payload = {"delta_ops": serializable_delta}
                        json_str = json.dumps(payload)
                        payload_bytes = json_str.encode("utf-8")
                        
                        if len(payload_bytes) >= 512 * 1024:
                            print(f"  -> Large delta payload ({len(payload_bytes) / 1024:.2f} KB). Using chunked transfer.")
                            temp_delta_file = os.path.join(root_dir, f".setsync_temp_delta_{job_id}.json")
                            os.makedirs(os.path.dirname(temp_delta_file), exist_ok=True)
                            with open(temp_delta_file, "w") as f:
                                json.dump(payload, f)
                                
                            upload_success = chunked_upload_file(
                                filepath=temp_delta_file,
                                session_id=job_id,
                                target_rel_path=f"jobs/{job_id}/delta"
                            )
                            if os.path.exists(temp_delta_file):
                                os.remove(temp_delta_file)
                                
                            if not upload_success:
                                raise RuntimeError("Chunked delta upload failed")
                            print(f"  -> Chunked delta upload finalized.")
                        else:
                            # Standard upload
                            delta_url = f"{core_url.rstrip('/')}/jobs/{job_id}/delta"
                            res = requests.post(delta_url, json=payload, headers=headers, timeout=30)
                            res.raise_for_status()
                            print(f"  -> Delta ops uploaded successfully.")
                        
                    elif job["destination_id"] == source_id and status == "delta_ready":
                        # 3. We are destination: Fetch delta ops, apply to local file
                        print(f"  -> Fetching delta ops for job {job_id}")
                        delta_url = f"{core_url.rstrip('/')}/jobs/{job_id}/delta"
                        res = requests.get(delta_url, headers=headers, timeout=30)
                        res.raise_for_status()
                        serialized_delta = res.json()
                        
                        # Check if chunked transfer was used
                        if len(serialized_delta) == 1 and serialized_delta[0][0] == "chunked_transfer":
                            session_id = serialized_delta[0][1]
                            print(f"  -> Large transfer detected. Initiating chunked download for session: {session_id}")
                            temp_delta_file = os.path.join(root_dir, f".setsync_temp_delta_{job_id}.json")
                            download_success = chunked_download_file(session_id, temp_delta_file)
                            if not download_success:
                                raise RuntimeError("Chunked delta download failed")
                            with open(temp_delta_file, "r") as f:
                                payload = json.load(f)
                            serialized_delta = payload.get("delta_ops", [])
                            if os.path.exists(temp_delta_file):
                                os.remove(temp_delta_file)
                        
                        # Unserialize hex string data back to bytes
                        delta_ops = []
                        for op, val in serialized_delta:
                            if op == "data" and isinstance(val, str):
                                delta_ops.append((op, bytes.fromhex(val)))
                            else:
                                delta_ops.append((op, val))
                                
                        print(f"  -> Applying delta to target file: '{file_abs}'")
                        temp_dest = file_abs + f".tmp_{job_id}"
                        
                        # Apply signatures
                        apply_delta(delta_ops, file_abs, temp_dest)
                        print(f"  -> Rebuild complete.")
                        
                        # Update status to completed
                        status_url = f"{core_url.rstrip('/')}/jobs/{job_id}/status"
                        requests.post(status_url, json={"status": "completed"}, headers=headers, timeout=15).raise_for_status()
                        print(f"  -> Job status set to completed.")
                        
                except Exception as job_err:
                    print(f"  [ERROR] processing job {job_id}: {job_err}")
                    traceback.print_exc()
                    
                    # Update status to failed
                    status_url = f"{core_url.rstrip('/')}/jobs/{job_id}/status"
                    try:
                        requests.post(
                            status_url,
                            json={"status": "failed", "error_message": str(job_err)},
                            headers=headers,
                            timeout=15
                        )
                    except Exception:
                        pass
                        
        except Exception as e:
            print(f"Error in main job loop: {e}")
            
        time.sleep(5)

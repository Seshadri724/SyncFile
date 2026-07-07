import os
import time
import threading
import datetime
from typing import Optional, Dict, Any
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from agent.scanner import scan_directory, calculate_sha256
from agent.db import get_cached_file, update_cached_file
from agent.uploader import upload_inventory_data, upload_inventory_delta

EXCLUDED_PATTERNS = [
    ".git", "node_modules", "venv", ".venv", "dist", "build", 
    "__pycache__", ".pytest_cache", ".setsync_trash"
]

def get_single_file_metadata(abs_path_str: str, root_dir: str) -> Optional[Dict[str, Any]]:
    try:
        if not os.path.exists(abs_path_str):
            return None
            
        stat = os.stat(abs_path_str)
        size = stat.st_size
        mtime = stat.st_mtime
        
        # Check cache mapping
        cached = get_cached_file(abs_path_str)
        file_hash = None
        
        if cached:
            c_size, c_mtime, c_hash = cached
            if c_size == size and abs(c_mtime - mtime) < 0.001:
                file_hash = c_hash
                
        if not file_hash:
            from pathlib import Path
            file_hash = calculate_sha256(Path(abs_path_str))
            update_cached_file(abs_path_str, size, mtime, file_hash, datetime.datetime.utcnow())
            
        relative_path = os.path.relpath(abs_path_str, root_dir).replace(os.path.sep, "/")
        
        return {
            "path": abs_path_str,
            "relative_path": relative_path,
            "size_bytes": size,
            "mtime": datetime.datetime.fromtimestamp(mtime).isoformat(),
            "hash_sha256": file_hash
        }
    except Exception as e:
        print(f"Error compiling single file metadata: {e}")
        return None

class DebouncedChangeHandler(FileSystemEventHandler):
    def __init__(self, root_dir: str, pc_id: str, debounce_seconds: float = 2.0):
        super().__init__()
        self.root_dir = os.path.abspath(root_dir)
        self.pc_id = pc_id
        self.debounce_seconds = debounce_seconds
        self.timer: Optional[threading.Timer] = None
        self.lock = threading.Lock()
        self.pending_changes: Dict[str, tuple] = {} # relative_path -> (action, file_item)
        
    def _is_excluded(self, path: str) -> bool:
        path_norm = path.replace("\\", "/")
        return any(pattern in path_norm for pattern in EXCLUDED_PATTERNS)

    def on_any_event(self, event):
        if event.is_directory:
            return
            
        src_path = getattr(event, "src_path", "")
        dest_path = getattr(event, "dest_path", "")
        
        # Verify exclusions
        if self._is_excluded(src_path) or (dest_path and self._is_excluded(dest_path)):
            return
            
        basename = os.path.basename(src_path)
        if basename.startswith(".") or basename.endswith(".tmp") or basename.startswith("~"):
            return
            
        with self.lock:
            # 1. Handle deletion
            if event.event_type == "deleted":
                rel_path = os.path.relpath(src_path, self.root_dir).replace(os.path.sep, "/")
                self.pending_changes[rel_path] = ("delete", {
                    "path": src_path,
                    "relative_path": rel_path,
                    "size_bytes": 0,
                    "mtime": datetime.datetime.utcnow().isoformat(),
                    "hash_sha256": ""
                })
            # 2. Handle move
            elif event.event_type == "moved":
                rel_src = os.path.relpath(src_path, self.root_dir).replace(os.path.sep, "/")
                self.pending_changes[rel_src] = ("delete", {
                    "path": src_path,
                    "relative_path": rel_src,
                    "size_bytes": 0,
                    "mtime": datetime.datetime.utcnow().isoformat(),
                    "hash_sha256": ""
                })
                
                rel_dest = os.path.relpath(dest_path, self.root_dir).replace(os.path.sep, "/")
                meta = get_single_file_metadata(dest_path, self.root_dir)
                if meta:
                    self.pending_changes[rel_dest] = ("upsert", meta)
            # 3. Handle created / modified
            else:
                rel_path = os.path.relpath(src_path, self.root_dir).replace(os.path.sep, "/")
                meta = get_single_file_metadata(src_path, self.root_dir)
                if meta:
                    self.pending_changes[rel_path] = ("upsert", meta)
            
            # Reset debounce timer
            if self.timer:
                self.timer.cancel()
            
            self.timer = threading.Timer(self.debounce_seconds, self.trigger_sync)
            self.timer.start()
            print(f"Watchdog queued: {event.event_type} on {os.path.basename(src_path)}")

    def trigger_sync(self):
        with self.lock:
            changes = list(self.pending_changes.values())
            self.pending_changes.clear()
            
        if not changes:
            return
            
        print(f"Quiet period detected. Syncing {len(changes)} delta changes...")
        for action, file_item in changes:
            try:
                res = upload_inventory_delta(action, file_item, self.pc_id)
                print(f"Delta Synced: {res.get('message')}")
            except Exception as e:
                print(f"Failed to sync delta for {file_item['relative_path']}: {e}")

def start_watching(root_dir: str, pc_id: str):
    print(f"Starting real-time delta watcher on {os.path.abspath(root_dir)} for PC-{pc_id}...")
    
    # Run initial sweep to register existing state
    print("Running initial full inventory sync...")
    try:
        files = scan_directory(root_dir)
        upload_inventory_data(files, pc_id)
        print(f"Initial sync complete. Ingested {len(files)} files.")
    except Exception as e:
        print(f"Initial sync failed: {e}")
        
    event_handler = DebouncedChangeHandler(root_dir, pc_id)
    observer = Observer()
    observer.schedule(event_handler, path=root_dir, recursive=True)
    observer.start()
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Stopping watcher...")
        observer.stop()
    observer.join()

import os
import zlib
import hashlib
from typing import Dict, List, Tuple, Any

def generate_block_signatures(filepath: str, block_size: int = 65536) -> Dict[int, List[Tuple[str, int]]]:
    """Reads filepath in chunks and returns a dictionary mapping Adler32 hash to list of (SHA256, block_index)."""
    adler_map = {}
    if not os.path.exists(filepath):
        return adler_map
        
    with open(filepath, "rb") as f:
        idx = 0
        while True:
            chunk = f.read(block_size)
            if not chunk:
                break
            adler = zlib.adler32(chunk) & 0xffffffff
            sha256 = hashlib.sha256(chunk).hexdigest()
            if adler not in adler_map:
                adler_map[adler] = []
            adler_map[adler].append((sha256, idx))
            idx += 1
            
    return adler_map

def compute_delta(adler_map: Dict[int, List[Tuple[str, int]]], source_filepath: str, block_size: int = 65536) -> List[Tuple[str, Any]]:
    """Calculates rsync-like differences between source file and signatures of target file."""
    delta_ops = []
    if not os.path.exists(source_filepath):
        return delta_ops
        
    with open(source_filepath, "rb") as f:
        data = f.read()
        
    n = len(data)
    i = 0
    raw_data = bytearray()
    
    while i < n:
        # Check if sliding window has room for a block
        if i + block_size <= n:
            window = data[i:i+block_size]
            adler = zlib.adler32(window) & 0xffffffff
            
            matched = False
            if adler in adler_map:
                sha256 = hashlib.sha256(window).hexdigest()
                for target_sha256, block_idx in adler_map[adler]:
                    if target_sha256 == sha256:
                        # Emit any raw data accumulated before this match
                        if raw_data:
                            delta_ops.append(("data", bytes(raw_data)))
                            raw_data = bytearray()
                        delta_ops.append(("copy", block_idx))
                        i += block_size
                        matched = True
                        break
                        
            if matched:
                continue
                
        # Slide window by 1 byte
        raw_data.append(data[i])
        i += 1
        
    if raw_data:
        delta_ops.append(("data", bytes(raw_data)))
        
    return delta_ops

def apply_delta(delta_ops: List[Tuple[str, Any]], target_filepath: str, new_filepath: str, block_size: int = 65536) -> None:
    """Reconstructs destination file by merging target_filepath blocks and new raw bytes data."""
    os.makedirs(os.path.dirname(new_filepath), exist_ok=True)
    
    target_file = None
    if os.path.exists(target_filepath):
        target_file = open(target_filepath, "rb")
        
    try:
        with open(new_filepath, "wb") as out_f:
            for op, val in delta_ops:
                if op == "data":
                    out_f.write(val)
                elif op == "copy":
                    if not target_file:
                        raise FileNotFoundError(f"Cannot copy block {val}; target file does not exist.")
                    target_file.seek(val * block_size)
                    block_data = target_file.read(block_size)
                    out_f.write(block_data)
    finally:
        if target_file:
            target_file.close()
            
    # Swap rebuilt temp file into final target destination
    if os.path.exists(new_filepath):
        if os.path.exists(target_filepath):
            os.remove(target_filepath)
        os.rename(new_filepath, target_filepath)

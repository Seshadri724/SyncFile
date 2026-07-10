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
    """Calculates rsync-like differences between source file and signatures of target file using streaming sliding window."""
    delta_ops = []
    if not os.path.exists(source_filepath):
        return delta_ops

    MOD_ADLER = 65521
    from collections import deque

    with open(source_filepath, "rb") as f:
        # Read initial window
        window_bytes = f.read(block_size)
        if not window_bytes:
            return delta_ops

        # If file is smaller than block_size, we cannot slide. Just output the data.
        if len(window_bytes) < block_size:
            delta_ops.append(("data", window_bytes))
            return delta_ops

        # Initialize rolling Adler hash values for the first block
        a = 1
        b = 0
        for byte in window_bytes:
            a = (a + byte) % MOD_ADLER
            b = (b + a) % MOD_ADLER

        window_deque = deque(window_bytes)
        raw_data = bytearray()
        
        # Helper to read next byte in chunks of 1MB
        CHUNK_SIZE = 1024 * 1024
        file_buffer = bytearray()
        file_buf_ptr = 0
        
        def get_next_byte():
            nonlocal file_buffer, file_buf_ptr
            if file_buf_ptr >= len(file_buffer):
                file_buffer = f.read(CHUNK_SIZE)
                file_buf_ptr = 0
                if not file_buffer:
                    return None
            val = file_buffer[file_buf_ptr]
            file_buf_ptr += 1
            return val

        def get_next_chunk(size):
            nonlocal file_buffer, file_buf_ptr
            res = bytearray()
            while len(res) < size:
                if file_buf_ptr >= len(file_buffer):
                    file_buffer = f.read(CHUNK_SIZE)
                    file_buf_ptr = 0
                    if not file_buffer:
                        break
                take = min(size - len(res), len(file_buffer) - file_buf_ptr)
                res.extend(file_buffer[file_buf_ptr:file_buf_ptr+take])
                file_buf_ptr += take
            return bytes(res)

        while True:
            # 1. Compute current adler
            adler = ((b & 0xffff) << 16) | (a & 0xffff)
            
            matched = False
            if adler in adler_map:
                # We need the full window as bytes to compute SHA-256
                current_window = bytes(window_deque)
                sha256 = hashlib.sha256(current_window).hexdigest()
                for target_sha256, block_idx in adler_map[adler]:
                    if target_sha256 == sha256:
                        # Match found!
                        # Emit accumulated raw data
                        if raw_data:
                            delta_ops.append(("data", bytes(raw_data)))
                            raw_data = bytearray()
                        # Emit copy op
                        delta_ops.append(("copy", block_idx))
                        
                        # Jump forward: read the next block_size bytes to reset the window
                        new_block = get_next_chunk(block_size)
                        if len(new_block) < block_size:
                            if new_block:
                                raw_data.extend(new_block)
                            matched = True
                            window_deque.clear() # indicate we are done
                            break
                        else:
                            # Reset window to the new block
                            window_deque = deque(new_block)
                            # Reset rolling Adler
                            a = 1
                            b = 0
                            for byte in new_block:
                                a = (a + byte) % MOD_ADLER
                                b = (b + a) % MOD_ADLER
                            matched = True
                            break
            
            if window_deque:
                if matched:
                    continue
                
                # No match. Slide by 1 byte.
                out_byte = window_deque.popleft()
                raw_data.append(out_byte)
                
                # If raw_data grows, partition to prevent memory blowup (max 1MB chunks)
                if len(raw_data) >= 1024 * 1024:
                    delta_ops.append(("data", bytes(raw_data)))
                    raw_data = bytearray()
                
                # Read 1 new byte
                in_byte = get_next_byte()
                if in_byte is None:
                    # EOF reached for sliding.
                    raw_data.extend(window_deque)
                    window_deque.clear()
                    break
                else:
                    window_deque.append(in_byte)
                    # Roll the Adler hash
                    a = (a - out_byte + in_byte) % MOD_ADLER
                    b = (b - block_size * out_byte + a - 1) % MOD_ADLER
            else:
                break

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

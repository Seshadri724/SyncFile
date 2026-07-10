import os
import tempfile
import pytest
from hypothesis import given, strategies as st
from app.transfer.delta_sync import (
    generate_block_signatures,
    compute_delta,
    apply_delta
)

@given(
    src_data=st.binary(min_size=0, max_size=200000),  # up to 200KB to keep tests fast
    dst_data=st.binary(min_size=0, max_size=200000),
    block_size=st.sampled_from([512, 1024, 4096, 16384, 65536])
)
def test_delta_roundtrip_property(src_data, dst_data, block_size):
    with tempfile.TemporaryDirectory() as tmpdir:
        src_path = os.path.join(tmpdir, "source.bin")
        dst_path = os.path.join(tmpdir, "destination.bin")
        rebuilt_path = os.path.join(tmpdir, "rebuilt.bin")
        
        with open(src_path, "wb") as f:
            f.write(src_data)
        with open(dst_path, "wb") as f:
            f.write(dst_data)
            
        # 1. Generate signatures for destination
        sigs = generate_block_signatures(dst_path, block_size=block_size)
        
        # 2. Compute delta from source using signatures of destination
        delta = compute_delta(sigs, src_path, block_size=block_size)
        
        # 3. Apply delta to reconstruct source on destination
        apply_delta(delta, dst_path, rebuilt_path, block_size=block_size)
        
        # 4. Assert rebuilt matches source exactly
        if os.path.exists(dst_path):
            with open(dst_path, "rb") as f:
                rebuilt_data = f.read()
        else:
            rebuilt_data = b""
            
        assert rebuilt_data == src_data

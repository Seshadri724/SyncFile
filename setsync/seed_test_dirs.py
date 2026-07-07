import os
from pathlib import Path

def main():
    pc_a = Path("./test_pc_a")
    pc_b = Path("./test_pc_b")
    
    os.makedirs(pc_a, exist_ok=True)
    os.makedirs(pc_b, exist_ok=True)
    
    # 1. Identical files on both
    for i in range(1, 4):
        name = f"shared_file_{i}.txt"
        content = f"This is identical content for file {i}\n"
        with open(pc_a / name, "w") as f:
            f.write(content)
        with open(pc_b / name, "w") as f:
            f.write(content)
            
    # 2. Only on PC A
    for i in range(1, 3):
        name = f"only_on_a_{i}.txt"
        with open(pc_a / name, "w") as f:
            f.write(f"This content is only on PC A - file {i}\n")
            
    # 3. Only on PC B
    for i in range(1, 3):
        name = f"only_on_b_{i}.txt"
        with open(pc_b / name, "w") as f:
            f.write(f"This content is only on PC B - file {i}\n")
            
    # 4. Conflicting files (same name/path, different content)
    conflict_names = ["conflict_1.txt", "conflict_2.txt"]
    for idx, name in enumerate(conflict_names):
        with open(pc_a / name, "w") as f:
            f.write(f"Version A of conflict file {idx+1}\n")
        with open(pc_b / name, "w") as f:
            f.write(f"Version B of conflict file {idx+1} (different content)\n")
            
    # 5. Cross-reference match (same hash/content, different paths)
    # File with content 'cross-content' exists at 'cross_path_a.txt' on A
    # and at 'cross_path_b.txt' on B.
    with open(pc_a / "cross_path_a.txt", "w") as f:
        f.write("cross-content-123\n")
    with open(pc_b / "cross_path_b.txt", "w") as f:
        f.write("cross-content-123\n")
        
    print("Successfully seeded simulation test directories:")
    print("  - ./test_pc_a/")
    print("  - ./test_pc_b/")

if __name__ == "__main__":
    main()

#!/bin/bash
# Detailed performance test

echo "Performance Test - PyBoy-style Optimization"
echo "=========================================="
echo ""

# Create a simple timing test
python3 << 'EOF'
import time
import subprocess
import sys

roms = [
    ("01-special.gb", "roms/test/cpu_instrs/individual/01-special.gb"),
    ("add_sp_e_timing", "roms/mooneye/mts-20240926-1737-443f6e1/acceptance/add_sp_e_timing.gb"),
]

for name, path in roms:
    print(f"Testing {name}...")
    start = time.time()
    result = subprocess.run(
        ["uv", "run", "python", "main.py", path, "--batch", "--auto-exit"],
        capture_output=True,
        text=True,
        timeout=60
    )
    elapsed = time.time() - start
    status = "✅" if "Emulation finished" in result.stderr or "finished" in result.stdout else "❌"
    print(f"  {status} {elapsed:.2f} seconds")
    print()

print("==========================================")
print("Test completed")
EOF
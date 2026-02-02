#!/bin/bash
# Quick test runner with 15s timeout per test

echo "Running quick Mooneye tests (15s timeout each)..."
echo "================================================"
echo ""

# Only run tests expected to finish quickly
QUICK_TESTS=(
    "acceptance/add_sp_e_timing.gb"
    "acceptance/div_timing.gb"
    "acceptance/ei_timing.gb"
    "acceptance/rapid_di_ei.gb"
)

for test in "${QUICK_TESTS[@]}"; do
    testname=$(basename "$test")
    echo -n "Testing $testname... "
    
    result=$(timeout 15 uv run python main.py "roms/mooneye/mts-20240926-1737-443f6e1/$test" --batch --auto-exit 2>&1 | tail -5)
    
    if echo "$result" | grep -q "Emulation finished"; then
        echo "✅ PASS"
    elif echo "$result" | grep -q "Timeout"; then
        echo "⏱️ Timeout"
    else
        echo "❌ Other ($result)"
    fi
done

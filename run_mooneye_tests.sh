#!/bin/bash
# Run selected Mooneye acceptance tests with shorter timeout

echo "Running Mooneye Acceptance Tests..."
echo "==================================="
echo ""

TESTS=(
    "acceptance/add_sp_e_timing.gb"
    "acceptance/jp_timing.gb"
    "acceptance/call_timing.gb"
    "acceptance/ret_timing.gb"
    "acceptance/push_timing.gb"
    "acceptance/pop_timing.gb"
    "acceptance/rst_timing.gb"
    "acceptance/div_timing.gb"
    "acceptance/ei_timing.gb"
    "acceptance/intr_timing.gb"
)

PASS=0
FAIL=0
TIMEOUT=0

for test in "${TESTS[@]}"; do
    testname=$(basename "$test")
    echo -n "Testing $testname... "
    
    result=$(timeout 60 uv run python main.py "roms/mooneye/mts-20240926-1737-443f6e1/$test" --batch --auto-exit 2>&1)
    
    if echo "$result" | grep -q "Emulation finished"; then
        echo "✅"
        ((PASS++))
    elif echo "$result" | grep -q "Timeout"; then
        echo "⏱️ Timeout"
        ((TIMEOUT++))
    else
        echo "❌ Failed"
        ((FAIL++))
    fi
done

echo ""
echo "==================================="
echo "Results: $PASS passed, $FAIL failed, $TIMEOUT timeout"

#!/bin/bash
# Performance comparison test

echo "Running performance tests..."
echo "============================"
echo ""

# Test with optimized version
echo "Testing 01-special.gb (optimized):"
timeout 120 uv run python main.py roms/test/cpu_instrs/individual/01-special.gb --batch --auto-exit 2>&1 | tail -5

echo ""
echo "Testing add_sp_e_timing.gb:"
timeout 60 uv run python main.py roms/mooneye/mts-20240926-1737-443f6e1/acceptance/add_sp_e_timing.gb --batch --auto-exit 2>&1 | tail -5

echo ""
echo "============================"
echo "Tests completed"
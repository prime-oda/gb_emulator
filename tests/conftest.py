"""
Pytest configuration and shared fixtures for Game Boy Emulator tests
"""
import pytest
import sys
import os

# Add src to Python path so we can import gameboy modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from gameboy.memory import Memory
from gameboy.cpu import CPU


@pytest.fixture
def memory():
    """Create a fresh Memory instance for testing."""
    return Memory()


@pytest.fixture  
def cpu(memory):
    """Create a CPU instance with memory for testing."""
    return CPU(memory, debug=False)


@pytest.fixture
def cpu_with_debug(memory):
    """Create a CPU instance with debug enabled for testing."""
    return CPU(memory, debug=True)
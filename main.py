#!/usr/bin/env python3
"""
Game Boy Emulator
A Python implementation of the Nintendo Game Boy handheld console emulator.
"""

import sys
import argparse
from src.gameboy.emulator import GameBoy


def main():
    parser = argparse.ArgumentParser(description='Game Boy Emulator')
    parser.add_argument('rom_file', help='Path to the Game Boy ROM file')
    parser.add_argument('--debug', action='store_true', help='Enable debug mode')
    
    args = parser.parse_args()
    
    try:
        print("Starting Game Boy emulator...")
        gameboy = GameBoy(debug=args.debug)
        print("Loading ROM...")
        gameboy.load_rom(args.rom_file)
        print("Starting emulation...")
        gameboy.run()
        print("Emulation finished.")
    except FileNotFoundError:
        print(f"Error: ROM file '{args.rom_file}' not found.")
        sys.exit(1)
    except Exception as e:
        import traceback
        print(f"Error: {e}")
        print("Full traceback:")
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
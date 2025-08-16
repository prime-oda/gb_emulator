#!/usr/bin/env python3
"""
Analyze font data location and tile mapping
"""

import sys
import time
from src.gameboy.emulator import GameBoy

def analyze_font_data():
    """Analyze where font data is stored and how tiles are mapped"""
    print("🔤 Analyzing font data and tile mapping...")
    
    gameboy = GameBoy(debug=False)
    gameboy.load_rom("roms/test/cpu_instrs.gb")
    
    # Run for a bit to let ROM initialize
    for _ in range(500000):  # 500k cycles
        gameboy.step()
    
    print(f"After initialization (500k cycles):")
    print(f"PC: 0x{gameboy.cpu.pc:04X}")
    
    lcdc = gameboy.memory.read_byte(0xFF40)
    tile_data_base = 0x8000 if (lcdc & 0x10) else 0x8800
    print(f"LCDC: 0x{lcdc:02X}")
    print(f"Tile data mode: {'0x8000' if (lcdc & 0x10) else '0x8800'}")
    print()
    
    # Analyze font data distribution in VRAM
    print("📊 VRAM Font Data Analysis:")
    
    # Check different areas of VRAM for font data
    areas = [
        ("0x8000-0x87FF", 0x8000, 0x8800),  # Tile data area 1
        ("0x8800-0x8FFF", 0x8800, 0x9000),  # Tile data area 2
        ("0x9000-0x97FF", 0x9000, 0x9800),  # Tile data area 3
    ]
    
    for name, start, end in areas:
        non_zero_count = 0
        pattern_count = 0
        
        for addr in range(start, end):
            value = gameboy.memory.vram[addr - 0x8000]
            if value != 0:
                non_zero_count += 1
            # Look for font-like patterns (alternating or structured data)
            if addr % 16 < 8 and value != 0:  # First 8 bytes of each tile
                pattern_count += 1
        
        print(f"  {name}: {non_zero_count}/{end-start} non-zero bytes, {pattern_count} potential font bytes")
    
    print()
    
    # Look for specific characters that should be in "cpu_instrs"
    target_chars = {
        ord('c'): 0x63, ord('p'): 0x70, ord('u'): 0x75, 
        ord('_'): 0x5F, ord('i'): 0x69, ord('n'): 0x6E,
        ord('s'): 0x73, ord('t'): 0x74, ord('r'): 0x72
    }
    
    print("🔍 Searching for 'cpu_instrs' character tiles:")
    
    # Check both tile data areas
    for base_name, base_addr in [("0x8000 area", 0x8000), ("0x8800 area", 0x8800)]:
        print(f"\n  {base_name}:")
        found_chars = 0
        
        for char, expected_tile in target_chars.items():
            # Check multiple possible tile locations for this character
            possible_tiles = [expected_tile, char, char - 0x20, char - 0x40]
            
            for tile_idx in possible_tiles:
                if 0 <= tile_idx <= 255:
                    tile_addr = base_addr + tile_idx * 16
                    if tile_addr < 0x9800:  # Within VRAM
                        # Read first 8 bytes of tile data
                        tile_data = [gameboy.memory.vram[tile_addr + i - 0x8000] for i in range(8)]
                        if any(b != 0 for b in tile_data):
                            print(f"    '{chr(char)}' (tile {tile_idx:02X}): {' '.join(f'{b:02X}' for b in tile_data)}")
                            found_chars += 1
                            break
        
        print(f"    Found {found_chars}/{len(target_chars)} character tiles")
    
    print()
    
    # Check what's actually in the tile maps for debugging
    print("🗺️  Tile Map Content Analysis:")
    
    # Background tile map
    bg_map_base = 0x9C00 if (lcdc & 0x08) else 0x9800
    print(f"Background tile map (0x{bg_map_base:04X}):")
    
    # Look for non-space characters in tile map
    found_text = False
    for row in range(18):  # Check 18 rows (144 pixels / 8)
        row_data = []
        for col in range(20):  # Check 20 columns (160 pixels / 8)
            tile_id = gameboy.memory.vram[(bg_map_base + row * 32 + col) - 0x8000]
            row_data.append(tile_id)
            if tile_id != 0x20 and tile_id != 0x00:  # Not space or null
                found_text = True
        
        # Only show rows with interesting content
        if any(t != 0x20 and t != 0x00 for t in row_data):
            print(f"  Row {row:2d}: {' '.join(f'{t:02X}' for t in row_data)}")
    
    if not found_text:
        print("  All tiles are spaces (0x20) or empty (0x00)")
    
    # Check if we need to wait longer for text to appear
    print(f"\n⏰ Timing Analysis:")
    print(f"Execution cycles: ~500,000")
    print(f"At 4.19MHz real speed: ~0.12 seconds")
    print(f"Text might appear later in ROM execution")

if __name__ == "__main__":
    analyze_font_data()
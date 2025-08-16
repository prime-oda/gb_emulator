#!/usr/bin/env python3
"""
Analyze boot ROM transition and initial game ROM execution
"""

import sys
import time
from src.gameboy.emulator import GameBoy

def analyze_boot_rom_transition():
    """Analyze boot ROM transition to game ROM"""
    print("🔄 Analyzing boot ROM transition and game ROM initialization...")
    
    gameboy = GameBoy(debug=False)
    gameboy.load_rom("roms/test/cpu_instrs.gb")
    
    cycles = 0
    max_cycles = 2000000  # 2M cycles
    
    # Track key events
    boot_disable_detected = False
    boot_disable_cycle = 0
    pc_transitions = []
    
    print(f"🚀 Running for {max_cycles:,} cycles...")
    print("Monitoring boot ROM disable and PC transitions...")
    print()
    
    start_time = time.time()
    last_pc_range = None
    
    try:
        while cycles < max_cycles:
            # Check boot ROM disable register (0xFF50)
            boot_disable = gameboy.memory.read_byte(0xFF50)
            if not boot_disable_detected and boot_disable != 0:
                boot_disable_detected = True
                boot_disable_cycle = cycles
                print(f"🔓 Boot ROM disabled at cycle {cycles:,}, PC: 0x{gameboy.cpu.pc:04X}")
            
            current_pc = gameboy.cpu.pc
            
            # Determine PC range
            if current_pc < 0x0100:
                pc_range = "Boot ROM (0x0000-0x00FF)"
            elif current_pc < 0x8000:
                pc_range = "Game ROM (0x0100-0x7FFF)"
            elif current_pc < 0xA000:
                pc_range = "VRAM (0x8000-0x9FFF)"
            elif current_pc < 0xC000:
                pc_range = "External RAM (0xA000-0xBFFF)"
            elif current_pc < 0xE000:
                pc_range = "Work RAM (0xC000-0xDFFF)"
            else:
                pc_range = "High RAM (0xE000+)"
            
            # Track PC range transitions
            if pc_range != last_pc_range:
                pc_transitions.append((cycles, current_pc, pc_range))
                print(f"📍 PC transition at cycle {cycles:,}: 0x{current_pc:04X} ({pc_range})")
                last_pc_range = pc_range
            
            step_cycles = gameboy.step()
            cycles += step_cycles
            
            # Progress every 500k cycles
            if cycles % 500000 == 0:
                elapsed = time.time() - start_time
                speed = cycles / elapsed / 1000000
                print(f"{cycles//1000:3d}k cycles - PC: 0x{current_pc:04X} - {speed:.1f}M/s - Range: {pc_range}")
                
                if elapsed > 5:  # 5 second timeout
                    print("⏰ 5 second timeout reached")
                    break
                    
    except KeyboardInterrupt:
        print("⏸️ Interrupted by user")
    except Exception as e:
        print(f"💥 Error: {e}")
        import traceback
        traceback.print_exc()
    
    elapsed = time.time() - start_time
    final_pc = gameboy.cpu.pc
    
    print(f"\n📊 Boot ROM Analysis Results:")
    print(f"   Total cycles: {cycles:,}")
    print(f"   Total time: {elapsed:.2f}s")
    print(f"   Final PC: 0x{final_pc:04X}")
    print(f"   Boot ROM disabled: {'Yes' if boot_disable_detected else 'No'}")
    
    if boot_disable_detected:
        print(f"   Boot disable cycle: {boot_disable_cycle:,}")
        print(f"   Time to boot disable: {boot_disable_cycle / 4194304 * 1000:.1f}ms")
    
    print(f"\n🗺️  PC Transition Summary:")
    for i, (cycle, pc, range_name) in enumerate(pc_transitions):
        print(f"   {i+1}. Cycle {cycle:,}: PC 0x{pc:04X} -> {range_name}")
    
    # Check ROM header information
    print(f"\n📋 Game ROM Header Analysis:")
    
    # ROM title (0x0134-0x0143)
    title = ""
    for addr in range(0x0134, 0x0144):
        char_code = gameboy.memory.read_byte(addr)
        if 32 <= char_code <= 126:
            title += chr(char_code)
        else:
            break
    print(f"   Title: '{title.strip()}'")
    
    # Entry point (0x0100-0x0103)
    entry_point = []
    for addr in range(0x0100, 0x0104):
        entry_point.append(gameboy.memory.read_byte(addr))
    print(f"   Entry point: {' '.join(f'0x{b:02X}' for b in entry_point)}")
    
    # Cartridge type
    cart_type = gameboy.memory.read_byte(0x0147)
    print(f"   Cartridge type: 0x{cart_type:02X}")
    
    # Check if we're stuck in boot ROM
    if final_pc < 0x0100 and not boot_disable_detected:
        print(f"\n❌ PROBLEM: Still in boot ROM after {cycles:,} cycles")
        print(f"   Boot ROM may not be completing properly")
        print(f"   This would prevent game ROM initialization")
    elif final_pc >= 0x0100 and boot_disable_detected:
        print(f"\n✅ Boot ROM transition successful")
        print(f"   Game ROM is now executing")
        
        # Check what game ROM is doing
        print(f"\n🎮 Game ROM Execution Analysis:")
        
        # Look for signs of initialization
        lcdc = gameboy.memory.read_byte(0xFF40)
        print(f"   LCDC register: 0x{lcdc:02X} ({'LCD ON' if lcdc & 0x80 else 'LCD OFF'})")
        
        # Check if interrupts are set up
        ie = gameboy.memory.read_byte(0xFFFF)
        ime = gameboy.cpu.ime
        print(f"   Interrupts: IE=0x{ie:02X}, IME={ime}")
        
        # Check timer setup
        tac = gameboy.memory.read_byte(0xFF07)
        print(f"   Timer: TAC=0x{tac:02X} ({'ON' if tac & 0x04 else 'OFF'})")
        
        # Check if game ROM has written anything to VRAM
        vram_writes = getattr(gameboy.memory, '_text_writes', 0)
        print(f"   VRAM text writes: {vram_writes}")
        
        if vram_writes == 0:
            print(f"   ⚠️  Game ROM has not written text yet")
            print(f"   This may indicate:")
            print(f"   - ROM is still in initialization phase")
            print(f"   - ROM expects specific hardware conditions")
            print(f"   - ROM is waiting for user input")
            print(f"   - ROM has compatibility issues with emulator")
    else:
        print(f"\n❓ Unclear state: PC=0x{final_pc:04X}, Boot disabled={boot_disable_detected}")

if __name__ == "__main__":
    analyze_boot_rom_transition()
#!/usr/bin/env python3
"""
Game Boy Emulator
A Python implementation of the Nintendo Game Boy handheld console emulator.
"""

import sys
import argparse
import os
from src.gameboy.emulator import GameBoy


def main():
    parser = argparse.ArgumentParser(description='Game Boy Emulator')
    parser.add_argument('rom_file', help='Path to the Game Boy ROM file')
    parser.add_argument('--debug', action='store_true', help='Enable debug mode')
    parser.add_argument('--auto-exit', action='store_true', help='Auto exit on test completion')
    parser.add_argument('--boot-rom', action='store_true', help='Enable Boot ROM execution (uses roms/dmg_boot.bin by default)')
    parser.add_argument('--batch', action='store_true', help='Enable batch processing for 2-3x speedup')
    
    args = parser.parse_args()
    
    try:
        print("Starting Game Boy emulator...")
        gameboy = GameBoy(debug=args.debug, batch_mode=args.batch)
        
        print("Loading ROM...")
        gameboy.load_rom(args.rom_file, use_boot_rom=args.boot_rom)
        
        if args.auto_exit:
            gameboy.set_auto_exit(True)
        
        # Debug: run only a few thousand cycles to see timer behavior
        if os.getenv('TIMER_DEBUG'):
            print("Running in timer debug mode...")
            print("Looking for TAC=0x05 writes and timer behavior...")
            cycle_count = 0
            tac_written = False
            last_tac = 0
            timer_interrupt_count = 0
            
            for i in range(10000000):  # Run much longer to allow test completion
                # バッチ処理を使用（--batchオプション時）
                if args.batch:
                    gameboy.run_until_interrupt()
                else:
                    gameboy.step()
                cycle_count += 1
                
                # Check for TAC write using proper memory access
                try:
                    tac = gameboy.memory.read_byte(0xFF07)
                    tima = gameboy.memory.read_byte(0xFF05)
                    if_reg = gameboy.memory.read_byte(0xFF0F)
                    
                    # Report any TAC changes
                    if tac != last_tac:
                        print(f"TAC changed to 0x{tac:02X} at cycle {cycle_count}")
                        last_tac = tac
                    
                    # Check for Boot ROM disable register writes
                    if i % 10000 == 0:
                        boot_disable = gameboy.memory.read_byte(0xFF50)
                        if boot_disable != 0:
                            print(f"Cycle {cycle_count}: Boot ROM disable register = 0x{boot_disable:02X}")
                    
                    if tac == 0x05 and not tac_written:
                        print(f"TAC=0x05 detected at cycle {cycle_count}")
                        tac_written = True
                    
                    # Show status every 50000 cycles
                    if i % 50000 == 0:
                        pc = gameboy.cpu.pc if hasattr(gameboy, 'cpu') else 0
                        boot_rom_enabled = gameboy.memory.boot_rom_enabled if hasattr(gameboy, 'memory') else True
                        print(f"Cycle {cycle_count}: PC=0x{pc:04X}, BootROM={boot_rom_enabled}, TAC=0x{tac:02X}, TIMA=0x{tima:02X}, IF=0x{if_reg:02X}")
                    
                    # Count timer interrupts but don't exit immediately
                    if if_reg & 0x04 and tac_written:
                        timer_interrupt_count += 1
                        if timer_interrupt_count == 1:
                            print(f"Timer interrupt triggered at cycle {cycle_count}!")
                        
                        # Check for test completion via serial output every 10 interrupts
                        if timer_interrupt_count % 10 == 0 and hasattr(gameboy, 'serial') and gameboy.serial:
                            text_output = gameboy.serial.get_output_text()
                            if "passed" in text_output.lower() or "failed" in text_output.lower():
                                print(f"Test completed! Output: {text_output}")
                                break
                        
                        # Exit after multiple timer interrupts and no completion signal
                        if timer_interrupt_count > 10:
                            print(f"Multiple timer interrupts detected ({timer_interrupt_count}), continuing to look for test completion...")
                            
                        # Exit if too many interrupts without test completion
                        if timer_interrupt_count > 200:  # もっと多く許可
                            print(f"Too many timer interrupts ({timer_interrupt_count}) without test completion - stopping")
                            break
                        
                except Exception as e:
                    # Memory access might fail early in initialization
                    if i % 50000 == 0:
                        print(f"Memory access error at cycle {cycle_count}: {e}")
                        
            print("Timer debug complete.")
            return
        
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
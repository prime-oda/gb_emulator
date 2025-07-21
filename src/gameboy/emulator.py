"""
Main Game Boy Emulator class
Coordinates CPU, memory, and other components.
"""
import pygame

from .cpu import CPU
from .memory import Memory
from .ppu import PPU
from .apu import APU


class GameBoy:
    def __init__(self, debug=False):
        self.debug = debug
        self.memory = Memory()
        self.cpu = CPU(self.memory, debug)
        self.ppu = PPU(self.memory, debug)
        self.apu = APU(self.memory, debug)
        
        # Link APU to memory for register access
        self.memory.apu = self.apu
        
        self.running = True  # エミュレータを実行状態に設定
        
    def load_rom(self, rom_path):
        """Load ROM file into memory"""
        try:
            with open(rom_path, 'rb') as f:
                rom_data = f.read()
            self.memory.load_rom(rom_data)
            
            # Initialize CPU based on ROM type
            if len(rom_data) == 256:
                # Boot ROM - initialize for boot sequence
                self.cpu.init_for_boot_rom()
            else:
                # Game ROM - initialize as if boot completed
                self.cpu.init_for_game_rom()
                
            if self.debug:
                print(f"Loaded ROM: {rom_path} ({len(rom_data)} bytes)")
                if len(rom_data) > 256:
                    print(f"ROM banks: {self.memory.rom_banks}")
                print(f"Initial PC: 0x{self.cpu.pc:04X}")
        except FileNotFoundError:
            raise FileNotFoundError(f"ROM file not found: {rom_path}")
    
    def run(self):
        """Run the emulator main loop"""
        cycle_count = 0
        frame_count = 0
        
        print("Initializing PPU rendering...")
        # Initialize PPU rendering
        try:
            render_result = self.ppu.render_frame()
            print(f"Initial render result: {render_result}")
            if not render_result:
                print("Initial render failed, exiting")
                return
        except Exception as e:
            print(f"Error during initial render: {e}")
            import traceback
            traceback.print_exc()
            return
        
        print("Starting main emulation loop...")
        try:
            while self.running:
                # Execute one CPU instruction
                cycles = self.step()
                cycle_count += cycles
                
                # Debug output for CPU cycles and state
                if self.debug and cycle_count % 20000000 == 0:
                    ly = self.memory.read_byte(0xFF44)
                    lcdc = self.memory.read_byte(0xFF40)
                    stat = self.memory.read_byte(0xFF41)
                    print(f"Cycles: {cycle_count}, PC: 0x{self.cpu.pc:04X}, LY: {ly}, LCDC: 0x{lcdc:02X}, STAT: 0x{stat:02X}")
                
                # CPU cycle progress tracking - less frequent for speed
                if cycle_count % 500000 == 0:  # Every 500k cycles for speed
                    ly = self.memory.read_byte(0xFF44)
                    lcdc = self.memory.read_byte(0xFF40)
                    stat = self.memory.read_byte(0xFF41)
                    print(f"CPU Progress: {cycle_count} cycles, PC: 0x{self.cpu.pc:04X}, LY: {ly}, LCDC: 0x{lcdc:02X}")
                    # Show CPU registers to debug the waiting loop at 0x0213-0x0215
                    if 0x0210 <= self.cpu.pc <= 0x0220:
                        print(f"  Registers: A=0x{self.cpu.a:02X}, B=0x{self.cpu.b:02X}, C=0x{self.cpu.c:02X}, Flags: Z={self.cpu.flag_z}, N={self.cpu.flag_n}, H={self.cpu.flag_h}, C={self.cpu.flag_c}")
                
                # Render frames more frequently for maximum speed (every 10k cycles)
                if cycle_count % 10000 == 0:
                    frame_count += 1
                    # Render frame and check if window should close
                    try:
                        if not self.ppu.render_frame():
                            print("Render returned False, stopping...")
                            break
                    except Exception as e:
                        print(f"Error during render: {e}")
                        import traceback
                        traceback.print_exc()
                        break
                        
        except KeyboardInterrupt:
            print(f"\nEmulation stopped. Total cycles: {cycle_count}, Frames: {frame_count}")
        except Exception as e:
            print(f"Error in main loop: {e}")
            import traceback
            traceback.print_exc()
        
        print("Emulation loop ended, cleaning up...")
        pygame.quit()
    
    def step(self):
        """Execute one emulation step"""
        cycles_before = self.cpu.cycles
        self.cpu.step()
        cpu_cycles = self.cpu.cycles - cycles_before
        
        # Update PPU with CPU cycles
        self.ppu.step(cpu_cycles)
        
        # Update APU with CPU cycles (reduced frequency for performance)
        if cpu_cycles % 10 == 0:  # Update APU less frequently
            self.apu.step(cpu_cycles)
        
        # Update memory registers with PPU state (direct write to avoid recursion)
        self.memory.io[0x44] = self.ppu.get_ly()  # LY register
        stat = self.ppu.get_stat() 
        self.memory.io[0x41] = stat  # STAT register
        
        return cpu_cycles
    
    def stop(self):
        """Stop the emulator"""
        self.running = False
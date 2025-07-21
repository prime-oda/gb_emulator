"""
Main Game Boy Emulator class
Coordinates CPU, memory, and other components.
"""

from .cpu import CPU
from .memory import Memory
from .ppu import PPU


class GameBoy:
    def __init__(self, debug=False):
        self.debug = debug
        self.memory = Memory()
        self.cpu = CPU(self.memory, debug)
        self.ppu = PPU(self.memory, debug)
        self.running = False
        
    def load_rom(self, rom_path):
        """Load ROM file into memory"""
        try:
            with open(rom_path, 'rb') as f:
                rom_data = f.read()
            self.memory.load_rom(rom_data)
            if self.debug:
                print(f"Loaded ROM: {rom_path} ({len(rom_data)} bytes)")
        except FileNotFoundError:
            raise FileNotFoundError(f"ROM file not found: {rom_path}")
    
    def run(self):
        """Main emulation loop"""
        self.running = True
        
        if self.debug:
            print("Starting Game Boy emulator...")
            print(f"Initial PC: 0x{self.cpu.pc:04X}")
        
        try:
            while self.running:
                # Check if we should continue (pygame window not closed)
                if not self.step():
                    break
                
                # Simple exit condition for now
                if self.cpu.cycles > 10000000:  # Increased for longer testing
                    if self.debug:
                        print("Emulation stopped after 10M cycles")
                    break
                    
        except KeyboardInterrupt:
            if self.debug:
                print("\nEmulation stopped by user")
        
        if self.debug:
            print(f"Final cycles: {self.cpu.cycles}")
    
    def step(self):
        """Execute one emulation step"""
        cycles_before = self.cpu.cycles
        self.cpu.step()
        cpu_cycles = self.cpu.cycles - cycles_before
        
        # Update PPU with CPU cycles
        self.ppu.step(cpu_cycles)
        
        # Update memory registers with PPU state
        self.memory.write_byte(0xFF44, self.ppu.get_ly())  # LY register
        stat = self.ppu.get_stat()
        self.memory.write_byte(0xFF41, stat)  # STAT register
        
        # Check if PPU wants to continue (pygame window not closed)
        if self.ppu.scan_line == 0 and self.ppu.mode == 2:  # Start of new frame
            if not self.ppu.render_frame():
                return False
        
        if self.debug and self.cpu.cycles % 10000 == 0:
            print(f"Cycles: {self.cpu.cycles}, PC: 0x{self.cpu.pc:04X}, LY: {self.ppu.scan_line}")
        
        return True
    
    def stop(self):
        """Stop the emulator"""
        self.running = False
"""
Main Game Boy Emulator class
Coordinates CPU, memory, and other components.
"""

from .cpu import CPU
from .memory import Memory


class GameBoy:
    def __init__(self, debug=False):
        self.debug = debug
        self.memory = Memory()
        self.cpu = CPU(self.memory)
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
                self.step()
                
                # Simple exit condition for now
                if self.cpu.cycles > 1000000:
                    if self.debug:
                        print("Emulation stopped after 1M cycles")
                    break
                    
        except KeyboardInterrupt:
            if self.debug:
                print("\nEmulation stopped by user")
        
        if self.debug:
            print(f"Final cycles: {self.cpu.cycles}")
    
    def step(self):
        """Execute one emulation step"""
        self.cpu.step()
        
        if self.debug and self.cpu.cycles % 10000 == 0:
            print(f"Cycles: {self.cpu.cycles}, PC: 0x{self.cpu.pc:04X}")
    
    def stop(self):
        """Stop the emulator"""
        self.running = False
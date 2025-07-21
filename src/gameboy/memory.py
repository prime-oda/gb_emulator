"""
Game Boy Memory Management Unit (MMU)
Handles memory mapping and bank switching for the Game Boy system.
"""

class Memory:
    def __init__(self):
        # Game Boy memory map
        self.rom = [0] * 0x8000      # ROM banks 0-1 (32KB)
        self.vram = [0] * 0x2000     # Video RAM (8KB)
        self.eram = [0] * 0x2000     # External RAM (8KB)
        self.wram = [0] * 0x2000     # Work RAM (8KB)
        self.oam = [0] * 0xA0        # Object Attribute Memory (160 bytes)
        self.io = [0] * 0x80         # I/O registers (128 bytes)
        self.hram = [0] * 0x7F       # High RAM (127 bytes)
        self.ie = 0                  # Interrupt Enable register
        
        # Memory banking
        self.rom_bank = 1
        self.ram_bank = 0
        self.banking_mode = 0
        self.ram_enabled = False
        
    def read_byte(self, address):
        """Read a byte from the specified memory address"""
        address &= 0xFFFF
        
        if address < 0x4000:
            # ROM Bank 0 (fixed)
            return self.rom[address]
        elif address < 0x8000:
            # ROM Bank 1-N (switchable)
            bank_address = (address - 0x4000) + (self.rom_bank * 0x4000)
            if bank_address < len(self.rom):
                return self.rom[bank_address]
            return 0xFF
        elif address < 0xA000:
            # Video RAM
            return self.vram[address - 0x8000]
        elif address < 0xC000:
            # External RAM
            if self.ram_enabled:
                return self.eram[address - 0xA000]
            return 0xFF
        elif address < 0xE000:
            # Work RAM
            return self.wram[address - 0xC000]
        elif address < 0xFE00:
            # Echo RAM (mirrors work RAM)
            return self.wram[address - 0xE000]
        elif address < 0xFEA0:
            # Object Attribute Memory
            return self.oam[address - 0xFE00]
        elif address < 0xFF00:
            # Restricted area
            return 0xFF
        elif address < 0xFF80:
            # I/O registers
            return self.io[address - 0xFF00]
        elif address < 0xFFFF:
            # High RAM
            return self.hram[address - 0xFF80]
        elif address == 0xFFFF:
            # Interrupt Enable register
            return self.ie
        
        return 0xFF
    
    def write_byte(self, address, value):
        """Write a byte to the specified memory address"""
        address &= 0xFFFF
        value &= 0xFF
        
        if address < 0x2000:
            # RAM Enable
            self.ram_enabled = (value & 0x0F) == 0x0A
        elif address < 0x4000:
            # ROM Bank Number (lower 5 bits)
            bank = value & 0x1F
            if bank == 0:
                bank = 1
            self.rom_bank = (self.rom_bank & 0x60) | bank
        elif address < 0x6000:
            # ROM Bank Number (upper 2 bits) or RAM Bank Number
            if self.banking_mode == 0:
                # ROM banking mode
                self.rom_bank = (self.rom_bank & 0x1F) | ((value & 0x03) << 5)
            else:
                # RAM banking mode
                self.ram_bank = value & 0x03
        elif address < 0x8000:
            # Banking mode select
            self.banking_mode = value & 0x01
        elif address < 0xA000:
            # Video RAM
            self.vram[address - 0x8000] = value
        elif address < 0xC000:
            # External RAM
            if self.ram_enabled:
                self.eram[address - 0xA000] = value
        elif address < 0xE000:
            # Work RAM
            self.wram[address - 0xC000] = value
        elif address < 0xFE00:
            # Echo RAM (mirrors work RAM)
            self.wram[address - 0xE000] = value
        elif address < 0xFEA0:
            # Object Attribute Memory
            self.oam[address - 0xFE00] = value
        elif address < 0xFF00:
            # Restricted area - ignore writes
            pass
        elif address < 0xFF80:
            # I/O registers
            self.io[address - 0xFF00] = value
        elif address < 0xFFFF:
            # High RAM
            self.hram[address - 0xFF80] = value
        elif address == 0xFFFF:
            # Interrupt Enable register
            self.ie = value
    
    def read_word(self, address):
        """Read a 16-bit word from memory (little-endian)"""
        low = self.read_byte(address)
        high = self.read_byte(address + 1)
        return (high << 8) | low
    
    def write_word(self, address, value):
        """Write a 16-bit word to memory (little-endian)"""
        self.write_byte(address, value & 0xFF)
        self.write_byte(address + 1, (value >> 8) & 0xFF)
    
    def load_rom(self, rom_data):
        """Load ROM data into memory"""
        for i, byte in enumerate(rom_data):
            if i < len(self.rom):
                self.rom[i] = byte
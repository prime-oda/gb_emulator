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
        
        # Boot ROM
        self.boot_rom = [0] * 0x100
        self.boot_rom_enabled = True
        
        # Initialize LCD registers
        self.io[0x40] = 0x91  # LCDC: LCD on, BG on
        self.io[0x47] = 0xFC  # BGP: Background palette
        
    def read_byte(self, address):
        """Read a byte from the specified memory address"""
        address &= 0xFFFF
        
        if address < 0x100 and self.boot_rom_enabled:
            # Boot ROM (0x0000-0x00FF)
            return self.boot_rom[address]
        elif address < 0x4000:
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
            if address == 0xFF40:  # LCDC
                return self.io[address - 0xFF00]
            elif address == 0xFF41:  # STAT
                return self.io[address - 0xFF00]
            elif address == 0xFF42:  # SCY
                return self.io[address - 0xFF00]
            elif address == 0xFF43:  # SCX
                return self.io[address - 0xFF00]
            elif address == 0xFF44:  # LY
                return self.io[address - 0xFF00]
            elif address == 0xFF45:  # LYC
                return self.io[address - 0xFF00]
            elif address == 0xFF47:  # BGP
                return self.io[address - 0xFF00]
            elif address == 0xFF48:  # OBP0
                return self.io[address - 0xFF00]
            elif address == 0xFF49:  # OBP1
                return self.io[address - 0xFF00]
            elif address == 0xFF4A:  # WY
                return self.io[address - 0xFF00]
            elif address == 0xFF4B:  # WX
                return self.io[address - 0xFF00]
            else:
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
        if len(rom_data) == 256:
            # This is a boot ROM
            for i, byte in enumerate(rom_data):
                if i < len(self.boot_rom):
                    self.boot_rom[i] = byte
        else:
            # This is a regular game ROM
            self.boot_rom_enabled = False  # Disable boot ROM for games
            for i, byte in enumerate(rom_data):
                if i < len(self.rom):
                    self.rom[i] = byte
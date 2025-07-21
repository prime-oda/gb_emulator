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
        
        # Initialize I/O registers for boot ROM
        self.io[0x26] = 0x80  # NR52: Sound on
        self.io[0x11] = 0x80  # NR11: Sound length/wave pattern duty
        self.io[0x12] = 0xF3  # NR12: Channel 1 Volume Envelope
        self.io[0x25] = 0x77  # NR51: Selection of Sound output terminal
        self.io[0x24] = 0x77  # NR50: Channel control / ON-OFF / Volume
        self.io[0x40] = 0x91  # LCDC: LCD on, BG on, sprites on
        self.io[0x47] = 0xFC  # BGP: Background palette
        self.io[0x48] = 0xFF  # OBP0: Object palette 0
        self.io[0x49] = 0xFF  # OBP1: Object palette 1
        self.io[0x00] = 0x3F  # Joypad: all buttons released
        
        # Joypad state
        self.joypad_buttons = 0x0F  # All buttons released
        self.joypad_directions = 0x0F  # All directions released
        
    def read_byte(self, address):
        """Read a byte from the specified memory address"""
        address &= 0xFFFF
        
        if address < 0x100 and self.boot_rom_enabled:
            # Boot ROM (0x0000-0x00FF)
            return self.boot_rom[address]
        elif address < 0x4000:
            # ROM Bank 0 (fixed)
            if address < len(self.rom):
                return self.rom[address]
            else:
                # Reading beyond ROM - return 0xFF (uninitialized)
                return 0xFF
        elif address < 0x8000:
            # ROM Bank 1-N (switchable)
            # Calculate address in ROM with proper banking
            if self.rom_bank == 0:
                # Bank 0 is not switchable in 0x4000-0x7FFF range, use bank 1
                bank_address = (address - 0x4000) + 0x4000
            else:
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
            elif address == 0xFF00:  # Joypad register
                return self.read_joypad()
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
            if address == 0xFF00:  # Joypad register
                self.write_joypad(value)
            else:
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
            # Boot ROM starts at 0x0000
            self.boot_rom_enabled = True
            self.is_boot_rom = True
            
            # Reset I/O registers for clean boot ROM execution
            self.io[0x26] = 0x00  # NR52: Sound initially off (boot ROM turns it on)
            self.io[0x40] = 0x00  # LCDC: LCD initially off (boot ROM turns it on)
        else:
            # This is a regular game ROM
            self.boot_rom_enabled = False  # Disable boot ROM for games
            
            # Expand ROM array to accommodate the full ROM
            self.rom = [0] * len(rom_data)
            for i, byte in enumerate(rom_data):
                self.rom[i] = byte
                
            # Calculate number of ROM banks (16KB each)
            self.rom_banks = max(2, (len(rom_data) + 0x3FFF) // 0x4000)
            
            # Game ROM starts at 0x0100
            self.is_boot_rom = False
    
    def read_joypad(self):
        """Read joypad register with proper bit selection"""
        # Get current joypad register value (determines which bits to read)
        joypad_reg = self.io[0x00]
        
        # Bit 5 = 0: Read button keys (A, B, Select, Start)
        # Bit 4 = 0: Read direction keys (Right, Left, Up, Down)
        
        result = 0xC0  # Bits 7-6 are unused (always 1)
        
        if not (joypad_reg & 0x20):  # Button keys selected
            result |= 0x20  # Set bit 5
            result |= (self.joypad_buttons & 0x0F)  # Bits 3-0: button states
        elif not (joypad_reg & 0x10):  # Direction keys selected  
            result |= 0x10  # Set bit 4
            result |= (self.joypad_directions & 0x0F)  # Bits 3-0: direction states
        else:
            # No selection, return all released
            result |= 0x3F
        
        return result
    
    def write_joypad(self, value):
        """Write to joypad register (only bits 5-4 are writable)"""
        # Only bits 5-4 can be written (key selection)
        self.io[0x00] = (value & 0x30) | 0xC0  # Keep bits 7-6 as 1
        
    def press_button(self, button):
        """Simulate button press (0=pressed, 1=released in Game Boy)"""
        # Button mapping: A=0, B=1, Select=2, Start=3
        if 0 <= button <= 3:
            self.joypad_buttons &= ~(1 << button)  # Clear bit (pressed)
    
    def release_button(self, button):
        """Simulate button release"""
        if 0 <= button <= 3:
            self.joypad_buttons |= (1 << button)  # Set bit (released)
    
    def press_direction(self, direction):
        """Simulate direction press (Right=0, Left=1, Up=2, Down=3)"""
        if 0 <= direction <= 3:
            self.joypad_directions &= ~(1 << direction)  # Clear bit (pressed)
    
    def release_direction(self, direction):
        """Simulate direction release"""
        if 0 <= direction <= 3:
            self.joypad_directions |= (1 << direction)  # Set bit (released)
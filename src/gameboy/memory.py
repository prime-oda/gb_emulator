"""
Game Boy Memory Management Unit (MMU)
Handles memory mapping and bank switching for the Game Boy system.

Cython最適化: Phase 2
"""

try:
    import cython
except ImportError:
    # Cythonがない環境でも動作するようにダミークラス
    class cython:
        @staticmethod
        def declare(*args, **kwargs):
            pass
        int = int
        longlong = int
        bint = bool

class Memory:
    def __init__(self, debug: cython.bint = False):
        self.debug: cython.bint = debug

        # Game Boy memory map
        self.rom: list = [0] * 0x8000      # ROM banks 0-1 (32KB)
        self.apu = None              # Will be set by emulator
        self.vram: list = [0] * 0x2000     # Video RAM (8KB)
        self.eram: list = [0] * 0x2000     # External RAM (8KB)
        self.wram: list = [0] * 0x2000     # Work RAM (8KB)
        self.oam: list = [0] * 0xA0        # Object Attribute Memory (160 bytes)
        self.io: list = [0] * 0x80         # I/O registers (128 bytes)
        self.hram: list = [0] * 0x7F       # High RAM (127 bytes)
        self.ie: cython.int = 0                  # Interrupt Enable register

        # Memory banking
        self.rom_bank: cython.int = 1
        self.ram_bank: cython.int = 0
        self.banking_mode: cython.int = 0
        self.ram_enabled: cython.bint = False

        # Boot ROM
        self.boot_rom: list = [0] * 0x100
        self.boot_rom_enabled: cython.bint = False  # Start with boot ROM disabled (post-boot state)
        
        # Initialize I/O registers to Boot ROM completion state (DMG)
        self.init_post_boot_state()
        
        # Joypad state
        self.joypad_buttons = 0x0F  # All buttons released
        self.joypad_directions = 0x0F  # All directions released
        
        # Timer registers
        self.timer = None  # Will be set by emulator
    
    def init_post_boot_state(self):
        """Initialize I/O registers to Boot ROM completion state (DMG)"""
        
        # Input/Peripheral
        self.io[0x00] = 0xCF  # P1/JOYP
        self.io[0x01] = 0x00  # SB (Serial transfer data)
        self.io[0x02] = 0x7E  # SC (Serial transfer control)
        
        # Timer/Interrupt
        self.io[0x04] = 0xAC  # DIV (Divider register) - PyBoy synchronized timing!
        self.io[0x05] = 0x00  # TIMA (Timer counter)
        self.io[0x06] = 0x00  # TMA (Timer modulo)
        self.io[0x07] = 0xF8  # TAC (Timer control) - upper bits set, timer disabled
        self.io[0x0F] = 0xE1  # IF (Interrupt flag)
        
        # Sound registers (excerpt)
        self.io[0x10] = 0x80  # NR10
        self.io[0x11] = 0xBF  # NR11
        self.io[0x12] = 0xF3  # NR12
        self.io[0x13] = 0xFF  # NR13
        self.io[0x14] = 0xBF  # NR14
        
        self.io[0x16] = 0x3F  # NR21
        self.io[0x17] = 0x00  # NR22
        self.io[0x18] = 0xFF  # NR23
        self.io[0x19] = 0xBF  # NR24
        
        self.io[0x1A] = 0x7F  # NR30
        self.io[0x1B] = 0xFF  # NR31
        self.io[0x1C] = 0x9F  # NR32
        self.io[0x1D] = 0xFF  # NR33
        self.io[0x1E] = 0xBF  # NR34
        
        self.io[0x20] = 0xFF  # NR41
        self.io[0x21] = 0x00  # NR42
        self.io[0x22] = 0x00  # NR43
        self.io[0x23] = 0xBF  # NR44
        
        self.io[0x24] = 0x77  # NR50
        self.io[0x25] = 0xF3  # NR51
        self.io[0x26] = 0xF1  # NR52
        
        # LCD/PPU
        self.io[0x40] = 0x91  # LCDC
        self.io[0x41] = 0x85  # STAT
        self.io[0x42] = 0x00  # SCY
        self.io[0x43] = 0x00  # SCX
        self.io[0x44] = 0x00  # LY
        self.io[0x45] = 0x00  # LYC
        self.io[0x47] = 0xFC  # BGP
        # OBP0/OBP1 (0x48/0x49) - uninitialized (undefined)
        self.io[0x4A] = 0x00  # WY
        self.io[0x4B] = 0x00  # WX
        
        # DMA
        self.io[0x46] = 0xFF  # DMA (DMG value)
        
        # Boot ROM disable register
        self.io[0x50] = 0x01  # Boot ROM disabled
        
        # Interrupt Enable (separate from I/O space)
        self.ie = 0x00
        
        # Serial port
        self.serial = None  # Will be set by emulator
        # DIVレジスタはTimerクラスの統一カウンタから自動計算されるため初期化不要
        self.io[0x05] = 0x00  # TIMA - Timer counter
        self.io[0x06] = 0x00  # TMA - Timer modulo
        self.io[0x07] = 0x00  # TAC - Timer control
        
    def read_byte(self, address: cython.int) -> cython.int:
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
            elif 0xFF01 <= address <= 0xFF02:  # Serial port registers
                if self.serial:
                    return self.serial.read_register(address)
                else:
                    return self.io[address - 0xFF00]
            elif 0xFF04 <= address <= 0xFF07:  # Timer registers
                if self.timer:
                    # PyBoy方式: タイマーレジスタアクセス時にもtick()を呼ぶ
                    if hasattr(self, 'cpu') and self.cpu:
                        import os
                        if os.getenv('TIMER_DEBUG'):
                            print(f'[Memory READ] Calling timer.tick({self.cpu.cycles}) for address 0x{address:04X}')
                        timer_interrupt_occurred = self.timer.tick(self.cpu.cycles)
                        if timer_interrupt_occurred:
                            # タイマー割り込みフラグを設定（再帰回避のため直接IOレジスタを操作）
                            if_reg = self.io[0x0F]
                            if not (if_reg & 0x04):
                                self.io[0x0F] = if_reg | 0x04
                    return self.timer.read_register(address)
                else:
                    return self.io[address - 0xFF00]
            elif 0xFF10 <= address <= 0xFF3F and self.apu:  # Audio registers
                return self.apu.read_register(address)
            else:
                return self.io[address - 0xFF00]
        elif address < 0xFFFF:
            # High RAM
            return self.hram[address - 0xFF80]
        elif address == 0xFFFF:
            # Interrupt Enable register
            return self.ie
        
        return 0xFF
    
    def write_byte(self, address: cython.int, value: cython.int) -> None:
        """Write a byte to the specified memory address"""
        address &= 0xFFFF
        value &= 0xFF
        
        # Debug: IF register writes
        if address == 0xFF0F and self.debug:
            old_value = self.io[0x0F] if 0x0F < len(self.io) else 0
            print(f"[MEMORY] IF write: 0x{old_value:02X} -> 0x{value:02X} at address 0xFF0F")
            if (value & 0x04) and not (old_value & 0x04):
                print(f"[MEMORY] 🔥 Timer interrupt flag SET in IF register!")
        
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
            # Video RAM - detect important text writes with detailed logging
            if address >= 0x9800 and value != 0x20:  # Background map area, non-space
                row = (address - 0x9800) // 32
                col = (address - 0x9800) % 32
                if not hasattr(self, '_text_writes'):
                    self._text_writes = 0
                self._text_writes += 1
                
                if self.debug and self._text_writes <= 3:  # Log first 3 text writes only
                    print(f"📝 TEXT WRITE #{self._text_writes}: row={row}, col={col}, char=0x{value:02X} ('{chr(value) if 32 <= value <= 126 else '?'}')")
                elif self.debug and self._text_writes == 4:
                    print("📝 (Suppressing text write logs for speed...)")
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
            elif 0xFF01 <= address <= 0xFF02:  # Serial port registers
                if self.serial:
                    self.serial.write_register(address, value)
                else:
                    self.io[address - 0xFF00] = value
            elif 0xFF04 <= address <= 0xFF07:  # Timer registers
                if self.timer:
                    # PyBoy方式: タイマーレジスタアクセス時にもtick()を呼ぶ
                    if hasattr(self, 'cpu') and self.cpu:
                        import os
                        if os.getenv('TIMER_DEBUG'):
                            print(f'[Memory WRITE] Calling timer.tick({self.cpu.cycles}) for address 0x{address:04X}, value=0x{value:02X}')
                        timer_interrupt_occurred = self.timer.tick(self.cpu.cycles)
                        if timer_interrupt_occurred:
                            # タイマー割り込みフラグを設定（再帰回避のため直接IOレジスタを操作）
                            if_reg = self.io[0x0F]
                            if not (if_reg & 0x04):
                                self.io[0x0F] = if_reg | 0x04
                    self.timer.write_register(address, value)
                else:
                    self.io[address - 0xFF00] = value
            elif address == 0xFF42:  # SCY register - prevent text from scrolling off-screen
                # Allow normal scrolling but prevent large values that push text off-screen
                # Text is typically at tile rows 8-9 (pixel rows 64-79)
                # Keep SCY <= 64 to ensure text remains visible
                if value > 64:
                    if self.debug:
                        print(f"🔧 SCY OVERRIDE: ROM tried to set SCY={value}, limiting to 64 to keep text visible")
                    value = 64
                self.io[address - 0xFF00] = value
            elif address == 0xFF50:  # Boot ROM disable register
                if value != 0:
                    self.boot_rom_enabled = False
                self.io[address - 0xFF00] = value
            elif 0xFF10 <= address <= 0xFF3F and self.apu:  # Audio registers
                self.apu.write_register(address, value)
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
            
            # Initialize I/O registers for game ROM (post-boot state)
            self.io[0x40] = 0x91  # LCDC: LCD on, BG on, sprites on
            self.io[0x47] = 0xE4  # BGP: Background palette (proper grayscale)
            self.io[0x48] = 0xFF  # OBP0: Object palette 0
            self.io[0x49] = 0xFF  # OBP1: Object palette 1
            self.io[0x26] = 0x80  # NR52: Sound on
            
            # Timer registers (post-boot state)
            # DIVレジスタはTimerクラスの統一カウンタで管理されるため、ここでは初期化不要
            self.io[0x05] = 0x00  # TIMA: Reset to 0
            self.io[0x06] = 0x00  # TMA: Reset to 0  
            self.io[0x07] = 0x00  # TAC: Timer disabled
            
            # Game ROM starts at 0x0100
            self.is_boot_rom = False

    def load_boot_rom(self, boot_rom_data):
        """Load boot ROM while keeping game ROM in memory"""
        if len(boot_rom_data) == 256:
            # Load boot ROM
            for i, byte in enumerate(boot_rom_data):
                if i < len(self.boot_rom):
                    self.boot_rom[i] = byte
            
            # Enable boot ROM overlay
            self.boot_rom_enabled = True
            self.is_boot_rom = False  # Keep game ROM flag
            
            # Reset I/O registers for clean boot ROM execution
            self.io[0x26] = 0x00  # NR52: Sound initially off
            self.io[0x40] = 0x00  # LCDC: LCD initially off
            self.io[0x50] = 0x00  # Boot ROM disable register
            
            if self.debug:
                print(f"✅ Boot ROM overlay enabled ({len(boot_rom_data)} bytes)")
        else:
            raise ValueError(f"Invalid boot ROM size: {len(boot_rom_data)} (expected 256)")
    
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
            # Trigger joypad interrupt if enabled
            self._trigger_joypad_interrupt()
    
    def release_button(self, button):
        """Simulate button release"""
        if 0 <= button <= 3:
            self.joypad_buttons |= (1 << button)  # Set bit (released)
    
    def press_direction(self, direction):
        """Simulate direction press (Right=0, Left=1, Up=2, Down=3)"""
        if 0 <= direction <= 3:
            self.joypad_directions &= ~(1 << direction)  # Clear bit (pressed)
            # Trigger joypad interrupt if enabled
            self._trigger_joypad_interrupt()
    
    def _trigger_joypad_interrupt(self):
        """Trigger joypad interrupt when button is pressed"""
        # Set joypad interrupt flag (bit 4 of IF register)
        if_reg = self.read_byte(0xFF0F)
        if_reg |= 0x10  # Set joypad interrupt bit
        self.write_byte(0xFF0F, if_reg)
    
    def release_direction(self, direction):
        """Simulate direction release"""
        if 0 <= direction <= 3:
            self.joypad_directions |= (1 << direction)  # Set bit (released)
    
    def read(self, address):
        """Read a byte from the specified memory address."""
        if 0x0000 <= address <= 0x7FFF:  # ROM
            return self.rom[address]
        elif 0x8000 <= address <= 0x9FFF:  # VRAM
            return self.vram[address - 0x8000]
        elif 0xA000 <= address <= 0xBFFF:  # External RAM
            return self.eram[address - 0xA000]
        elif 0xC000 <= address <= 0xDFFF:  # Work RAM
            return self.wram[address - 0xC000]
        elif 0xFE00 <= address <= 0xFE9F:  # OAM
            return self.oam[address - 0xFE00]
        elif 0xFF00 <= address <= 0xFF7F:  # I/O Registers
            return self.io[address - 0xFF00]
        elif 0xFF80 <= address <= 0xFFFE:  # High RAM
            return self.hram[address - 0xFF80]
        elif address == 0xFFFF:  # Interrupt Enable Register
            return self.ie
        else:
            raise ValueError(f"Invalid memory read at address: 0x{address:04X}")
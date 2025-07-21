import logging

# Configure logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

"""
Game Boy CPU (Sharp LR35902) emulation
Based on the Z80 architecture with some modifications.
"""

class CPU:
    def __init__(self, memory, debug=False):
        self.memory = memory
        self.debug = debug
        
        # 8-bit registers
        self.a = 0x01  # Accumulator
        self.b = 0x00
        self.c = 0x13
        self.d = 0x00
        self.e = 0xD8
        self.h = 0x01
        self.l = 0x4D
        
        # Initialize HL register
        self.hl = (self.h << 8) | self.l
        
        # 16-bit registers
        self.sp = 0xFFFE  # Stack pointer
        # PC will be set correctly based on ROM type in load_rom
        self.pc = 0x0000  # Program counter (will be set by boot ROM or game)
        
        # Flags register (F)
        self.flag_z = False  # Zero flag
        self.flag_n = False  # Subtract flag
        self.flag_h = False  # Half carry flag
        self.flag_c = False  # Carry flag
        
        # Interrupt master enable
        self.ime = True
        
        # Cycle count
        self.cycles = 0
        
        # Debug tracking
        self._ff_count = 0
        self._pc_history = []
    
    def init_for_boot_rom(self):
        """Initialize CPU state for boot ROM execution"""
        # Reset all registers to boot ROM initial state
        self.a = 0x00
        self.b = 0x00
        self.c = 0x00
        self.d = 0x00
        self.e = 0x00
        self.h = 0x00
        self.l = 0x00
        
        # Boot ROM starts at 0x0000
        self.pc = 0x0000
        self.sp = 0xFFFE
        
        # Clear flags
        self.flag_z = False
        self.flag_n = False  
        self.flag_h = False
        self.flag_c = False
        
        # Reset cycle count
        self.cycles = 0
        
    def init_for_game_rom(self):
        """Initialize CPU state for game ROM execution (post-boot)"""
        # Game ROM initial state (as if boot ROM completed)
        self.a = 0x01
        self.b = 0x00
        self.c = 0x13
        self.d = 0x00
        self.e = 0xD8
        self.h = 0x01
        self.l = 0x4D
        
        # Game ROM starts at 0x0100
        self.pc = 0x0100
        self.sp = 0xFFFE
        
    def handle_interrupts(self):
        """Handle pending interrupts"""
        if not self.ime:  # Interrupt master enable must be on
            return False
            
        # Read interrupt enable and interrupt flag registers
        ie = self.memory.read_byte(0xFFFF)  # IE register
        if_reg = self.memory.read_byte(0xFF0F)  # IF register
        
        # Check for enabled and pending interrupts
        pending = ie & if_reg
        
        if pending & 0x01:  # V-Blank interrupt
            self._service_interrupt(0x40, 0x01)
            return True
        elif pending & 0x02:  # LCDC STAT interrupt
            self._service_interrupt(0x48, 0x02)
            return True
        elif pending & 0x04:  # Timer interrupt
            self._service_interrupt(0x50, 0x04)
            return True
        elif pending & 0x08:  # Serial interrupt
            self._service_interrupt(0x58, 0x08)
            return True
        elif pending & 0x10:  # Joypad interrupt
            self._service_interrupt(0x60, 0x10)
            return True
            
        return False
    
    def _service_interrupt(self, vector, flag_bit):
        """Service an interrupt"""
        # Disable interrupt master enable
        self.ime = False
        
        # Clear the interrupt flag
        if_reg = self.memory.read_byte(0xFF0F)
        self.memory.write_byte(0xFF0F, if_reg & ~flag_bit)
        
        # Push current PC to stack
        self.push_word(self.pc)
        
        # Jump to interrupt vector
        self.pc = vector
        
        # Takes 20 cycles
        self.cycles += 20
        
    def get_f(self):
        """Get flags register value"""
        f = 0
        if self.flag_z: f |= 0x80
        if self.flag_n: f |= 0x40
        if self.flag_h: f |= 0x20
        if self.flag_c: f |= 0x10
        return f
    
    def set_f(self, value):
        """Set flags register value"""
        self.flag_z = bool(value & 0x80)
        self.flag_n = bool(value & 0x40)
        self.flag_h = bool(value & 0x20)
        self.flag_c = bool(value & 0x10)
    
    def get_af(self):
        """Get AF register pair"""
        return (self.a << 8) | self.get_f()
    
    def set_af(self, value):
        """Set AF register pair"""
        self.a = (value >> 8) & 0xFF
        self.set_f(value & 0xFF)
    
    def get_bc(self):
        """Get BC register pair"""
        return (self.b << 8) | self.c
    
    def set_bc(self, value):
        """Set BC register pair"""
        self.b = (value >> 8) & 0xFF
        self.c = value & 0xFF
    
    def get_de(self):
        """Get DE register pair"""
        return (self.d << 8) | self.e
    
    def set_de(self, value):
        """Set DE register pair"""
        self.d = (value >> 8) & 0xFF
        self.e = value & 0xFF
    
    def get_hl(self):
        """Get HL register pair"""
        return (self.h << 8) | self.l
    
    def set_hl(self, value):
        """Set HL register pair"""
        self.h = (value >> 8) & 0xFF
        self.l = value & 0xFF
    
    def fetch_byte(self):
        """Fetch next byte from memory at PC"""
        byte = self.memory.read_byte(self.pc)
        self.pc = (self.pc + 1) & 0xFFFF
        return byte
    
    def fetch_word(self):
        """Fetch next word (16-bit) from memory at PC"""
        low = self.fetch_byte()
        high = self.fetch_byte()
        return (high << 8) | low
    
    def push_byte(self, value):
        """Push byte onto stack"""
        self.sp = (self.sp - 1) & 0xFFFF
        self.memory.write_byte(self.sp, value & 0xFF)
    
    def push_word(self, value):
        """Push word onto stack"""
        self.push_byte((value >> 8) & 0xFF)
        self.push_byte(value & 0xFF)
    
    def pop_byte(self):
        """Pop byte from stack"""
        value = self.memory.read_byte(self.sp)
        self.sp = (self.sp + 1) & 0xFFFF
        return value
    
    def pop_word(self):
        """Pop word from stack"""
        low = self.pop_byte()
        high = self.pop_byte()
        return (high << 8) | low
    
    def inc_8bit(self, value):
        """Increment 8-bit value and set flags"""
        result = (value + 1) & 0xFF
        self.flag_z = (result == 0)
        self.flag_n = False
        self.flag_h = ((value & 0x0F) == 0x0F)
        return result
    
    def dec_8bit(self, value):
        """Decrement 8-bit value and set flags"""
        result = (value - 1) & 0xFF
        self.flag_z = (result == 0)
        self.flag_n = True
        self.flag_h = ((value & 0x0F) == 0x00)
        return result
    
    def compare(self, value):
        """Compare A with value and set flags"""
        result = self.a - value
        self.flag_z = (result == 0)
        self.flag_n = True
        self.flag_h = ((self.a & 0x0F) < (value & 0x0F))
        self.flag_c = (self.a < value)
    
    def execute_cb_instruction(self, opcode):
        """Execute CB-prefixed bit operations"""
        # Basic implementation for common CB instructions
        if opcode == 0x6C:  # BIT 5, H
            self.flag_z = not bool(self.h & (1 << 5))
            self.flag_n = False
            self.flag_h = True
            self.cycles += 8
        elif opcode == 0x10:  # RL B
            carry = 1 if self.flag_c else 0
            self.flag_c = bool(self.b & 0x80)
            self.b = ((self.b << 1) | carry) & 0xFF
            self.flag_z = (self.b == 0)
            self.flag_n = False
            self.flag_h = False
            self.cycles += 8
        elif opcode == 0x11:  # RL C
            carry = 1 if self.flag_c else 0
            self.flag_c = bool(self.c & 0x80)
            self.c = ((self.c << 1) | carry) & 0xFF
            self.flag_z = (self.c == 0)
            self.flag_n = False
            self.flag_h = False
            self.cycles += 8
        elif opcode == 0x41:  # BIT 0, C
            self.flag_z = not bool(self.c & (1 << 0))
            self.flag_n = False
            self.flag_h = True
            self.cycles += 8
        elif opcode == 0x7C:  # BIT 7, H
            self.flag_z = not bool(self.h & (1 << 7))
            self.flag_n = False
            self.flag_h = True
            self.cycles += 8
        elif opcode == 0x37:  # SWAP A - Swap upper and lower nibbles of A
            self.a = ((self.a & 0x0F) << 4) | ((self.a & 0xF0) >> 4)
            self.flag_z = (self.a == 0)
            self.flag_n = False
            self.flag_h = False
            self.flag_c = False
            self.cycles += 8
        elif opcode == 0x3F:  # SRL A - Shift A right logical
            self.flag_c = bool(self.a & 0x01)
            self.a = self.a >> 1
            self.flag_z = (self.a == 0)
            self.flag_n = False
            self.flag_h = False
            self.cycles += 8
        elif opcode == 0x77:  # BIT 6, A - Test bit 6 in A
            self.flag_z = not bool(self.a & (1 << 6))
            self.flag_n = False
            self.flag_h = True
            self.cycles += 8
        elif opcode == 0x7F:  # BIT 7, A - Test bit 7 in A
            self.flag_z = not bool(self.a & (1 << 7))
            self.flag_n = False
            self.flag_h = True
            self.cycles += 8
        elif opcode == 0x1A:  # RR D - Rotate D right through carry
            carry = 1 if self.flag_c else 0
            self.flag_c = bool(self.d & 0x01)
            self.d = (self.d >> 1) | (carry << 7)
            self.flag_z = (self.d == 0)
            self.flag_n = False
            self.flag_h = False
            self.cycles += 8
        elif opcode == 0x38:  # SRL B - Shift B right logical
            self.flag_c = bool(self.b & 0x01)
            self.b = self.b >> 1
            self.flag_z = (self.b == 0)
            self.flag_n = False
            self.flag_h = False
            self.cycles += 8
        elif opcode == 0x19:  # RR C - Rotate C right through carry
            carry = 1 if self.flag_c else 0
            self.flag_c = bool(self.c & 0x01)
            self.c = (self.c >> 1) | (carry << 7)
            self.flag_z = (self.c == 0)
            self.flag_n = False
            self.flag_h = False
            self.cycles += 8
        else:
            if self.debug:
                print(f"Unimplemented CB opcode: 0x{opcode:02X} at PC: 0x{self.pc-2:04X}")
            self.cycles += 8
    
    def step(self):
        """Execute one CPU instruction"""
        # Handle interrupts before fetching next instruction
        if self.handle_interrupts():
            return  # Interrupt was serviced
            
        opcode = self.fetch_byte()
        self.execute_instruction(opcode)
    
    def execute_instruction(self, opcode):
        """Execute instruction based on opcode"""
        # Track PC history for debugging
        if self.debug and len(self._pc_history) < 10:
            self._pc_history.append(self.pc - 1)
        elif self.debug:
            self._pc_history.pop(0)
            self._pc_history.append(self.pc - 1)
            
        if opcode == 0x00:  # NOP
            self.cycles += 4
        
        # 16-bit loads
        elif opcode == 0x01:  # LD BC, nn
            self.set_bc(self.fetch_word())
            self.cycles += 12
        elif opcode == 0x11:  # LD DE, nn
            self.set_de(self.fetch_word())
            self.cycles += 12
        elif opcode == 0x21:  # LD HL, nn
            self.set_hl(self.fetch_word())
            self.cycles += 12
        elif opcode == 0x31:  # LD SP, nn
            self.sp = self.fetch_word()
            self.cycles += 12
        
        # 8-bit loads
        elif opcode == 0x06:  # LD B, n
            self.b = self.fetch_byte()
            self.cycles += 8
        elif opcode == 0x0E:  # LD C, n
            self.c = self.fetch_byte()
            self.cycles += 8
        elif opcode == 0x16:  # LD D, n
            self.d = self.fetch_byte()
            self.cycles += 8
        elif opcode == 0x1E:  # LD E, n
            self.e = self.fetch_byte()
            self.cycles += 8
        elif opcode == 0x26:  # LD H, n
            self.h = self.fetch_byte()
            self.cycles += 8
        elif opcode == 0x2E:  # LD L, n
            self.l = self.fetch_byte()
            self.cycles += 8
        elif opcode == 0x3E:  # LD A, n
            self.a = self.fetch_byte()
            self.cycles += 8
        
        # Memory operations
        elif opcode == 0x22:  # LD (HL+), A - Load A into address HL, then increment HL
            self.memory.write_byte(self.get_hl(), self.a)
            self.set_hl((self.get_hl() + 1) & 0xFFFF)
            self.cycles += 8
        elif opcode == 0x32:  # LD (HL-), A - Load A into address HL, then decrement HL
            self.memory.write_byte(self.get_hl(), self.a)
            self.set_hl((self.get_hl() - 1) & 0xFFFF)
            self.cycles += 8
        elif opcode == 0x2A:  # LD A, (HL+) - Load from address HL into A, then increment HL
            self.a = self.memory.read_byte(self.get_hl())
            self.set_hl((self.get_hl() + 1) & 0xFFFF)
            self.cycles += 8
        elif opcode == 0x3A:  # LD A, (HL-) - Load from address HL into A, then decrement HL
            self.a = self.memory.read_byte(self.get_hl())
            self.set_hl((self.get_hl() - 1) & 0xFFFF)
            self.cycles += 8
        
        # High memory operations (0xFF00 + n)
        elif opcode == 0xE0:  # LD (0xFF00+n), A
            address = 0xFF00 + self.fetch_byte()
            self.memory.write_byte(address, self.a)
            self.cycles += 12
        elif opcode == 0xE2:  # LD (0xFF00+C), A
            address = 0xFF00 + self.c
            self.memory.write_byte(address, self.a)
            self.cycles += 8
        elif opcode == 0xF0:  # LD A, (0xFF00+n)
            address = 0xFF00 + self.fetch_byte()
            self.a = self.memory.read_byte(address)
            self.cycles += 12
        elif opcode == 0xF8:  # LD HL, SP+n
            offset = self.fetch_byte()
            if offset > 127:
                offset = offset - 256
            result = (self.sp + offset) & 0xFFFF
            self.flag_z = False
            self.flag_n = False
            self.flag_h = ((self.sp & 0x0F) + (offset & 0x0F)) > 0x0F
            self.flag_c = ((self.sp & 0xFF) + (offset & 0xFF)) > 0xFF
            self.set_hl(result)
            self.cycles += 12        
        # Absolute memory operations
        elif opcode == 0xEA:  # LD (nn), A
            address = self.fetch_word()
            self.memory.write_byte(address, self.a)
            self.cycles += 16
        elif opcode == 0xFA:  # LD A, (nn)
            address = self.fetch_word()
            self.a = self.memory.read_byte(address)
            self.cycles += 16
        
        # Register to register loads
        elif opcode == 0x40:  # LD B, B
            self.cycles += 4
        elif opcode == 0x41:  # LD B, C
            self.b = self.c
            self.cycles += 4
        elif opcode == 0x47:  # LD B, A
            self.b = self.a
            self.cycles += 4
        elif opcode == 0x4F:  # LD C, A
            self.c = self.a
            self.cycles += 4
        elif opcode == 0x57:  # LD D, A
            self.d = self.a
            self.cycles += 4
        elif opcode == 0x5F:  # LD E, A
            self.e = self.a
            self.cycles += 4
        elif opcode == 0x67:  # LD H, A
            self.h = self.a
            self.cycles += 4
        elif opcode == 0x6F:  # LD L, A
            self.l = self.a
            self.cycles += 4
        elif opcode == 0x7F:  # LD A, A
            self.cycles += 4
        
        # Load from memory to register
        elif opcode == 0x46:  # LD B, (HL)
            self.b = self.memory.read_byte(self.get_hl())
            self.cycles += 8
        elif opcode == 0x4E:  # LD C, (HL)
            self.c = self.memory.read_byte(self.get_hl())
            self.cycles += 8
        elif opcode == 0x56:  # LD D, (HL)
            self.d = self.memory.read_byte(self.get_hl())
            self.cycles += 8
        elif opcode == 0x5E:  # LD E, (HL)
            self.e = self.memory.read_byte(self.get_hl())
            self.cycles += 8
        elif opcode == 0x66:  # LD H, (HL)
            self.h = self.memory.read_byte(self.get_hl())
            self.cycles += 8
        elif opcode == 0x6E:  # LD L, (HL)
            self.l = self.memory.read_byte(self.get_hl())
            self.cycles += 8
        elif opcode == 0x7E:  # LD A, (HL)
            self.a = self.memory.read_byte(self.get_hl())
            self.cycles += 8
        
        # Load from register to memory
        elif opcode == 0x70:  # LD (HL), B
            self.memory.write_byte(self.get_hl(), self.b)
            self.cycles += 8
        elif opcode == 0x71:  # LD (HL), C
            self.memory.write_byte(self.get_hl(), self.c)
            self.cycles += 8
        elif opcode == 0x72:  # LD (HL), D
            self.memory.write_byte(self.get_hl(), self.d)
            self.cycles += 8
        elif opcode == 0x73:  # LD (HL), E
            self.memory.write_byte(self.get_hl(), self.e)
            self.cycles += 8
        elif opcode == 0x74:  # LD (HL), H
            self.memory.write_byte(self.get_hl(), self.h)
            self.cycles += 8
        elif opcode == 0x75:  # LD (HL), L
            self.memory.write_byte(self.get_hl(), self.l)
            self.cycles += 8
        elif opcode == 0x77:  # LD (HL), A
            self.memory.write_byte(self.get_hl(), self.a)
            self.cycles += 8
        
        # Jump and branch instructions
        elif opcode == 0x18:  # JR n - Relative jump
            offset = self.fetch_byte()
            if offset > 127:  # Convert to signed
                offset = offset - 256
            self.pc = (self.pc + offset) & 0xFFFF
            self.cycles += 12
        elif opcode == 0x20:  # JR NZ, n - Jump if not zero
            offset = self.fetch_byte()
            if not self.flag_z:
                if offset > 127:
                    offset = offset - 256
                self.pc = (self.pc + offset) & 0xFFFF
                self.cycles += 12
            else:
                self.cycles += 8
        elif opcode == 0x28:  # JR Z, n - Jump if zero
            offset = self.fetch_byte()
            if self.flag_z:
                if offset > 127:
                    offset = offset - 256
                self.pc = (self.pc + offset) & 0xFFFF
                self.cycles += 12
            else:
                self.cycles += 8
        elif opcode == 0x30:  # JR NC, n - Jump if not carry
            offset = self.fetch_byte()
            if not self.flag_c:
                if offset > 127:
                    offset = offset - 256
                self.pc = (self.pc + offset) & 0xFFFF
                self.cycles += 12
            else:
                self.cycles += 8
        elif opcode == 0x38:  # JR C, n - Jump if carry
            offset = self.fetch_byte()
            if self.flag_c:
                if offset > 127:
                    offset = offset - 256
                self.pc = (self.pc + offset) & 0xFFFF
                self.cycles += 12
            else:
                self.cycles += 8
        elif opcode == 0xC3:  # JP nn - Absolute jump
            target = self.fetch_word()
            self.pc = target
            self.cycles += 16
        elif opcode == 0xC2:  # JP NZ, nn - Jump if not zero
            address = self.fetch_word()
            if not self.flag_z:
                self.pc = address
                self.cycles += 16
            else:
                self.cycles += 12
        elif opcode == 0xCA:  # JP Z, nn - Jump if zero
            address = self.fetch_word()
            if self.flag_z:
                self.pc = address
                self.cycles += 16
            else:
                self.cycles += 12
        elif opcode == 0xD2:  # JP NC, nn - Jump if not carry
            address = self.fetch_word()
            if not self.flag_c:
                self.pc = address
                self.cycles += 16
            else:
                self.cycles += 12
        elif opcode == 0xDA:  # JP C, nn - Jump if carry
            address = self.fetch_word()
            if self.flag_c:
                self.pc = address
                self.cycles += 16
            else:
                self.cycles += 12
        elif opcode == 0xE9:  # JP (HL) - Jump to address in HL
            self.pc = self.get_hl()
            self.cycles += 4
        
        # Call and return instructions
        elif opcode == 0xCD:  # CALL nn
            address = self.fetch_word()
            self.push_word(self.pc)
            self.pc = address
            self.cycles += 24
        elif opcode == 0xC4:  # CALL NZ, nn
            address = self.fetch_word()
            if not self.flag_z:
                self.push_word(self.pc)
                self.pc = address
                self.cycles += 24
            else:
                self.cycles += 12
        elif opcode == 0xCC:  # CALL Z, nn
            address = self.fetch_word()
            if self.flag_z:
                self.push_word(self.pc)
                self.pc = address
                self.cycles += 24
            else:
                self.cycles += 12
        elif opcode == 0xD4:  # CALL NC, nn
            address = self.fetch_word()
            if not self.flag_c:
                self.push_word(self.pc)
                self.pc = address
                self.cycles += 24
            else:
                self.cycles += 12
        elif opcode == 0xDC:  # CALL C, nn
            address = self.fetch_word()
            if self.flag_c:
                self.push_word(self.pc)
                self.pc = address
                self.cycles += 24
            else:
                self.cycles += 12
        elif opcode == 0xC9:  # RET
            self.pc = self.pop_word()
            self.cycles += 16
        elif opcode == 0xC0:  # RET NZ
            if not self.flag_z:
                self.pc = self.pop_word()
                self.cycles += 20
            else:
                self.cycles += 8
        elif opcode == 0xC8:  # RET Z
            if self.flag_z:
                self.pc = self.pop_word()
                self.cycles += 20
            else:
                self.cycles += 8
        elif opcode == 0xD0:  # RET NC
            if not self.flag_c:
                self.pc = self.pop_word()
                self.cycles += 20
            else:
                self.cycles += 8
        elif opcode == 0xD8:  # RET C
            if self.flag_c:
                self.pc = self.pop_word()
                self.cycles += 20
            else:
                self.cycles += 8
        
        # Arithmetic operations
        elif opcode == 0x04:  # INC B
            self.b = self.inc_8bit(self.b)
            self.cycles += 4
        elif opcode == 0x05:  # DEC B
            self.b = self.dec_8bit(self.b)
            self.cycles += 4
        elif opcode == 0x0C:  # INC C
            self.c = self.inc_8bit(self.c)
            self.cycles += 4
        elif opcode == 0x0D:  # DEC C
            self.c = self.dec_8bit(self.c)
            self.cycles += 4
        elif opcode == 0x14:  # INC D
            self.d = self.inc_8bit(self.d)
            self.cycles += 4
        elif opcode == 0x15:  # DEC D
            self.d = self.dec_8bit(self.d)
            self.cycles += 4
        elif opcode == 0x1C:  # INC E
            self.e = self.inc_8bit(self.e)
            self.cycles += 4
        elif opcode == 0x1D:  # DEC E
            self.e = self.dec_8bit(self.e)
            self.cycles += 4
        elif opcode == 0x24:  # INC H
            self.h = self.inc_8bit(self.h)
            self.cycles += 4
        elif opcode == 0x25:  # DEC H
            self.h = self.dec_8bit(self.h)
            self.cycles += 4
        elif opcode == 0x2C:  # INC L
            self.l = self.inc_8bit(self.l)
            self.cycles += 4
        elif opcode == 0x2D:  # DEC L
            self.l = self.dec_8bit(self.l)
            self.cycles += 4
        elif opcode == 0x34:  # INC (HL)
            value = self.memory.read_byte(self.get_hl())
            result = self.inc_8bit(value)
            self.memory.write_byte(self.get_hl(), result)
            self.cycles += 12
        elif opcode == 0x35:  # DEC (HL)
            value = self.memory.read_byte(self.get_hl())
            result = self.dec_8bit(value)
            self.memory.write_byte(self.get_hl(), result)
            self.cycles += 12
        elif opcode == 0x3C:  # INC A
            self.a = self.inc_8bit(self.a)
            self.cycles += 4
        elif opcode == 0x3D:  # DEC A
            self.a = self.dec_8bit(self.a)
            self.cycles += 4
        
        # 16-bit arithmetic
        elif opcode == 0x03:  # INC BC
            self.set_bc((self.get_bc() + 1) & 0xFFFF)
            self.cycles += 8
        elif opcode == 0x0B:  # DEC BC
            self.set_bc((self.get_bc() - 1) & 0xFFFF)
            self.cycles += 8
        elif opcode == 0x13:  # INC DE
            self.set_de((self.get_de() + 1) & 0xFFFF)
            self.cycles += 8
        elif opcode == 0x1B:  # DEC DE
            self.set_de((self.get_de() - 1) & 0xFFFF)
            self.cycles += 8
        elif opcode == 0x23:  # INC HL
            self.set_hl((self.get_hl() + 1) & 0xFFFF)
            self.cycles += 8
        elif opcode == 0x2B:  # DEC HL
            self.set_hl((self.get_hl() - 1) & 0xFFFF)
            self.cycles += 8
        elif opcode == 0x33:  # INC SP
            self.sp = (self.sp + 1) & 0xFFFF
            self.cycles += 8
        elif opcode == 0x3B:  # DEC SP
            self.sp = (self.sp - 1) & 0xFFFF
            self.cycles += 8
        
        # Compare operations
        elif opcode == 0xFE:  # CP n - Compare A with immediate value
            value = self.fetch_byte()
            self.compare(value)
            self.cycles += 8
        elif opcode == 0xBE:  # CP (HL) - Compare A with value at HL
            value = self.memory.read_byte(self.get_hl())
            self.compare(value)
            self.cycles += 8
        elif opcode == 0xB8:  # CP B - Compare A with B
            self.compare(self.b)
            self.cycles += 4
        elif opcode == 0xB9:  # CP C - Compare A with C
            self.compare(self.c)
            self.cycles += 4
        elif opcode == 0xBA:  # CP D - Compare A with D
            self.compare(self.d)
            self.cycles += 4
        elif opcode == 0xBB:  # CP E - Compare A with E
            self.compare(self.e)
            self.cycles += 4
        elif opcode == 0xBC:  # CP H - Compare A with H
            self.compare(self.h)
            self.cycles += 4
        elif opcode == 0xBD:  # CP L - Compare A with L
            self.compare(self.l)
            self.cycles += 4
        elif opcode == 0xBF:  # CP A - Compare A with A
            self.compare(self.a)
            self.cycles += 4
        
        # Logic operations
        elif opcode == 0xA7:  # AND A - AND A with A (used to set flags)
            self.a = self.a & self.a
            self.flag_z = (self.a == 0)
            self.flag_n = False
            self.flag_h = True
            self.flag_c = False
            self.cycles += 4
        elif opcode == 0xAF:  # XOR A - XOR A with A (clears A)
            self.a = 0
            self.flag_z = True
            self.flag_n = False
            self.flag_h = False
            self.flag_c = False
            self.cycles += 4
        elif opcode == 0xB7:  # OR A - OR A with A (sets flags)
            self.flag_z = (self.a == 0)
            self.flag_n = False
            self.flag_h = False
            self.flag_c = False
            self.cycles += 4
        
        # Bit operations (CB prefix)
        elif opcode == 0xCB:  # CB-prefixed opcodes
            cb_opcode = self.fetch_byte()
            self.execute_cb_instruction(cb_opcode)
        elif opcode == 0x1F:  # RRA - Rotate A right through carry
            carry = 1 if self.flag_c else 0
            self.flag_c = bool(self.a & 0x01)
            self.a = (self.a >> 1) | (carry << 7)
            self.flag_z = False
            self.flag_n = False
            self.flag_h = False
            self.cycles += 4
        
        # Stack operations
        elif opcode == 0xF5:  # PUSH AF
            self.push_word(self.get_af())
            self.cycles += 16
        elif opcode == 0xF1:  # POP AF
            self.set_af(self.pop_word())
            self.cycles += 12
        elif opcode == 0xC5:  # PUSH BC
            self.push_word(self.get_bc())
            self.cycles += 16
        elif opcode == 0xC1:  # POP BC
            self.set_bc(self.pop_word())
            self.cycles += 12
        elif opcode == 0xD5:  # PUSH DE
            self.push_word(self.get_de())
            self.cycles += 16
        elif opcode == 0xD1:  # POP DE
            self.set_de(self.pop_word())
            self.cycles += 12
        elif opcode == 0xE5:  # PUSH HL
            self.push_word(self.get_hl())
            self.cycles += 16
        elif opcode == 0xE1:  # POP HL
            self.set_hl(self.pop_word())
            self.cycles += 12
        
        # Additional register operations
        elif opcode == 0x1A:  # LD A, (DE)
            self.a = self.memory.read_byte(self.get_de())
            self.cycles += 8
        elif opcode == 0x0A:  # LD A, (BC)
            self.a = self.memory.read_byte(self.get_bc())
            self.cycles += 8
        elif opcode == 0x12:  # LD (DE), A
            self.memory.write_byte(self.get_de(), self.a)
            self.cycles += 8
        elif opcode == 0x02:  # LD (BC), A
            self.memory.write_byte(self.get_bc(), self.a)
            self.cycles += 8
        
        # Register to register loads (more complete set)
        elif opcode == 0x78:  # LD A, B
            self.a = self.b
            self.cycles += 4
        elif opcode == 0x79:  # LD A, C
            self.a = self.c
            self.cycles += 4
        elif opcode == 0x7A:  # LD A, D
            self.a = self.d
            self.cycles += 4
        elif opcode == 0x7B:  # LD A, E
            self.a = self.e
            self.cycles += 4
        elif opcode == 0x7C:  # LD A, H
            self.a = self.h
            self.cycles += 4
        elif opcode == 0x7D:  # LD A, L
            self.a = self.l
            self.cycles += 4
        
        # More complete register to register loads
        elif opcode == 0x42:  # LD B, D
            self.b = self.d
            self.cycles += 4
        elif opcode == 0x43:  # LD B, E
            self.b = self.e
            self.cycles += 4
        elif opcode == 0x44:  # LD B, H
            self.b = self.h
            self.cycles += 4
        elif opcode == 0x45:  # LD B, L
            self.b = self.l
            self.cycles += 4
        elif opcode == 0x48:  # LD C, B
            self.c = self.b
            self.cycles += 4
        elif opcode == 0x49:  # LD C, C
            self.cycles += 4
        elif opcode == 0x4A:  # LD C, D
            self.c = self.d
            self.cycles += 4
        elif opcode == 0x4B:  # LD C, E
            self.c = self.e
            self.cycles += 4
        elif opcode == 0x4C:  # LD C, H
            self.c = self.h
            self.cycles += 4
        elif opcode == 0x4D:  # LD C, L
            self.c = self.l
            self.cycles += 4
        elif opcode == 0x50:  # LD D, B
            self.d = self.b
            self.cycles += 4
        elif opcode == 0x51:  # LD D, C
            self.d = self.c
            self.cycles += 4
        elif opcode == 0x52:  # LD D, D
            self.cycles += 4
        elif opcode == 0x53:  # LD D, E
            self.d = self.e
            self.cycles += 4
        elif opcode == 0x54:  # LD D, H
            self.d = self.h
            self.cycles += 4
        elif opcode == 0x55:  # LD D, L
            self.d = self.l
            self.cycles += 4
        elif opcode == 0x58:  # LD E, B
            self.e = self.b
            self.cycles += 4
        elif opcode == 0x59:  # LD E, C
            self.e = self.c
            self.cycles += 4
        elif opcode == 0x5A:  # LD E, D
            self.e = self.d
            self.cycles += 4
        elif opcode == 0x5B:  # LD E, E
            self.cycles += 4
        elif opcode == 0x5C:  # LD E, H
            self.e = self.h
            self.cycles += 4
        elif opcode == 0x5D:  # LD E, L
            self.e = self.l
            self.cycles += 4
        elif opcode == 0x60:  # LD H, B
            self.h = self.b
            self.cycles += 4
        elif opcode == 0x61:  # LD H, C
            self.h = self.c
            self.cycles += 4
        elif opcode == 0x62:  # LD H, D
            self.h = self.d
            self.cycles += 4
        elif opcode == 0x63:  # LD H, E
            self.h = self.e
            self.cycles += 4
        elif opcode == 0x64:  # LD H, H
            self.cycles += 4
        elif opcode == 0x65:  # LD H, L
            self.h = self.l
            self.cycles += 4
        elif opcode == 0x68:  # LD L, B
            self.l = self.b
            self.cycles += 4
        elif opcode == 0x69:  # LD L, C
            self.l = self.c
            self.cycles += 4
        elif opcode == 0x6A:  # LD L, D
            self.l = self.d
            self.cycles += 4
        elif opcode == 0x6B:  # LD L, E
            self.l = self.e
            self.cycles += 4
        elif opcode == 0x6C:  # LD L, H
            self.l = self.h
            self.cycles += 4
        elif opcode == 0x6D:  # LD L, L
            self.cycles += 4
        
        # Interrupts
        elif opcode == 0xF3:  # DI - Disable interrupts
            self.ime = False
            self.cycles += 4
        elif opcode == 0xFB:  # EI - Enable interrupts
            self.ime = True
            self.cycles += 4
        
        elif opcode == 0x76:  # HALT
            # For now, just NOP
            self.cycles += 4
        
        # Additional critical opcodes for big2small.gb
        elif opcode == 0x2F:  # CPL - Complement A register
            self.a = (~self.a) & 0xFF
            self.flag_n = True
            self.flag_h = True
            self.cycles += 4
        elif opcode == 0x0F:  # RRCA - Rotate A right circular
            carry = self.a & 0x01
            self.a = ((self.a >> 1) | (carry << 7)) & 0xFF
            self.flag_z = False
            self.flag_n = False
            self.flag_h = False
            self.flag_c = bool(carry)
            self.cycles += 4
        elif opcode == 0xE6:  # AND n - AND A with immediate byte
            value = self.fetch_byte()
            self.a = self.a & value
            self.flag_z = (self.a == 0)
            self.flag_n = False
            self.flag_h = True
            self.flag_c = False
            self.cycles += 8
        elif opcode == 0xF2:  # LD A, (0xFF00+C) - Load A from high memory (C)
            address = 0xFF00 + self.c
            self.a = self.memory.read_byte(address)
            self.cycles += 8
        elif opcode == 0xD9:  # RETI - Return and enable interrupts
            self.pc = self.pop_word()
            self.ime = True  # Enable interrupts
            self.cycles += 16
        elif opcode == 0x87:  # ADD A, A - Add A to A
            result = self.a + self.a
            self.flag_c = result > 0xFF
            self.flag_h = ((self.a & 0x0F) + (self.a & 0x0F)) > 0x0F
            self.a = result & 0xFF
            self.flag_z = (self.a == 0)
            self.flag_n = False
            self.cycles += 4
        elif opcode == 0xC6:  # ADD A, n - Add immediate to A
            value = self.fetch_byte()
            result = self.a + value
            self.flag_c = result > 0xFF
            self.flag_h = ((self.a & 0x0F) + (value & 0x0F)) > 0x0F
            self.a = result & 0xFF
            self.flag_z = (self.a == 0)
            self.flag_n = False
            self.cycles += 8
        elif opcode == 0x09:  # ADD HL, BC - Add BC to HL
            hl = (self.h << 8) | self.l
            bc = (self.b << 8) | self.c
            result = hl + bc
            self.flag_c = result > 0xFFFF
            self.flag_h = ((hl & 0x0FFF) + (bc & 0x0FFF)) > 0x0FFF
            self.flag_n = False
            self.h = (result >> 8) & 0xFF
            self.l = result & 0xFF
            self.cycles += 8
        elif opcode == 0x19:  # ADD HL, DE - Add DE to HL
            hl = (self.h << 8) | self.l
            de = (self.d << 8) | self.e
            result = hl + de
            self.flag_c = result > 0xFFFF
            self.flag_h = ((hl & 0x0FFF) + (de & 0x0FFF)) > 0x0FFF
            self.flag_n = False
            self.h = (result >> 8) & 0xFF
            self.l = result & 0xFF
            self.cycles += 8
        elif opcode == 0x36:  # LD (HL), n - Load immediate into address HL
            value = self.fetch_byte()
            address = (self.h << 8) | self.l
            self.memory.write_byte(address, value)
            self.cycles += 12
        elif opcode == 0xD6:  # SUB n - Subtract immediate from A
            value = self.fetch_byte()
            self.flag_c = self.a < value
            self.flag_h = (self.a & 0x0F) < (value & 0x0F)
            self.a = (self.a - value) & 0xFF
            self.flag_z = (self.a == 0)
            self.flag_n = True
            self.cycles += 8
        elif opcode == 0xB0:  # OR B - OR A with B
            self.a = self.a | self.b
            self.flag_z = (self.a == 0)
            self.flag_n = False
            self.flag_h = False
            self.flag_c = False
            self.cycles += 4
        elif opcode == 0xA1:  # AND C - AND A with C
            self.a = self.a & self.c
            self.flag_z = (self.a == 0)
            self.flag_n = False
            self.flag_h = True
            self.flag_c = False
            self.cycles += 4
        elif opcode == 0x07:  # RLCA - Rotate A left circular
            carry = (self.a >> 7) & 0x01
            self.a = ((self.a << 1) | carry) & 0xFF
            self.flag_z = False
            self.flag_n = False
            self.flag_h = False
            self.flag_c = bool(carry)
            self.cycles += 4
        elif opcode == 0x80:  # ADD A, B - Add B to A
            result = self.a + self.b
            self.flag_c = result > 0xFF
            self.flag_h = ((self.a & 0x0F) + (self.b & 0x0F)) > 0x0F
            self.a = result & 0xFF
            self.flag_z = (self.a == 0)
            self.flag_n = False
            self.cycles += 4
        elif opcode == 0x81:  # ADD A, C - Add C to A
            result = self.a + self.c
            self.flag_c = result > 0xFF
            self.flag_h = ((self.a & 0x0F) + (self.c & 0x0F)) > 0x0F
            self.a = result & 0xFF
            self.flag_z = (self.a == 0)
            self.flag_n = False
            self.cycles += 4
        elif opcode == 0xF6:  # OR n - OR A with immediate
            value = self.fetch_byte()
            self.a = self.a | value
            self.flag_z = (self.a == 0)
            self.flag_n = False
            self.flag_h = False
            self.flag_c = False
            self.cycles += 8
        elif opcode == 0xCE:  # ADC A, n
            value = self.fetch_byte()
            carry = 1 if self.flag_c else 0
            result = self.a + value + carry
            self.flag_c = result > 0xFF
            self.flag_h = ((self.a & 0x0F) + (value & 0x0F) + carry) > 0x0F
            self.a = result & 0xFF
            self.flag_z = (self.a == 0)
            self.flag_n = False
            self.cycles += 8
        elif opcode == 0xAE:  # XOR (HL)
            value = self.read_byte(self.hl)
            self.cycles += 8
        elif opcode == 0xEE:  # XOR n
            value = self.fetch_byte()
            self.a ^= value
            self.flag_z = (self.a == 0)
            self.flag_n = False
            self.flag_h = False
            self.flag_c = False
            self.cycles += 8
        elif opcode == 0xED:  # Placeholder for unknown opcode
            raise NotImplementedError(f"Unimplemented opcode: 0x{opcode:02X} at PC: 0x{self.pc:04X}")
        elif opcode == 0x83:  # ADD A, E
            result = self.a + self.e
            self.flag_z = ((result & 0xFF) == 0)
            self.flag_n = False
            self.flag_h = ((self.a & 0x0F) + (self.e & 0x0F)) > 0x0F
            self.flag_c = (result > 0xFF)
            self.a = result & 0xFF
            self.cycles += 4
        elif opcode == 0xB6:  # OR (HL)
            value = self.read_byte(self.hl)
            self.a |= value
            self.flag_z = (self.a == 0)
            self.flag_n = False
            self.flag_h = False
            self.flag_c = False
            self.cycles += 8
        elif opcode == 0xB1:  # OR C
            self.a |= self.c
            self.flag_z = (self.a == 0)
            self.flag_n = False
            self.flag_h = False
            self.flag_c = False
            self.cycles += 4
        elif opcode == 0x29:  # ADD HL, HL
            result = self.hl + self.hl
            self.flag_n = False
            self.flag_h = ((self.hl & 0x0FFF) + (self.hl & 0x0FFF)) > 0x0FFF
            self.flag_c = (result > 0xFFFF)
            self.hl = result & 0xFFFF
            self.cycles += 8
        elif opcode == 0x91:  # SUB C
            result = self.a - self.c
            self.flag_z = ((result & 0xFF) == 0)
            self.flag_n = True
            self.flag_h = ((self.a & 0x0F) < (self.c & 0x0F))
            self.flag_c = (result < 0)
            self.a = result & 0xFF
            self.cycles += 4
        elif opcode == 0xA9:  # XOR C
#            logging.debug(f"[DEBUG] Executing XOR C at PC: 0x{self.pc:04X}")
#            logging.debug(f"[DEBUG] Initial state: A=0x{self.a:02X}, C=0x{self.c:02X}, Z={self.flag_z}, N={self.flag_n}, H={self.flag_h}, C={self.flag_c}")
            self.a ^= self.c
            self.flag_z = (self.a == 0)
            self.flag_n = False
            self.flag_h = False
            self.flag_c = False
#            logging.debug(f"[DEBUG] Result: A=0x{self.a:02X}, Z={self.flag_z}, N={self.flag_n}, H={self.flag_h}, C={self.flag_c}")
            self.cycles += 4
        elif opcode == 0x27:  # DAA - Decimal Adjust Accumulator
            if not self.flag_n:  # After addition
                if self.flag_h or (self.a & 0x0F) > 0x09:
                    self.a += 0x06
                if self.flag_c or self.a > 0x9F:
                    self.a += 0x60
            else:  # After subtraction
                if self.flag_h:
                    self.a = (self.a - 0x06) & 0xFF
                if self.flag_c:
                    self.a = (self.a - 0x60) & 0xFF

            self.flag_h = False
            self.flag_z = (self.a & 0xFF) == 0
            if self.a > 0xFF:
                self.flag_c = True
            self.a &= 0xFF
            self.cycles += 4
        else:
            # Placeholder for unimplemented instructions
            if self.debug:
                print(f"Unimplemented opcode: 0x{opcode:02X} at PC: 0x{self.pc-1:04X}")
                # Exit after too many consecutive 0xFF opcodes to prevent spam
                self._ff_count += 1 if opcode == 0xFF else 0
                if opcode == 0xFF and self._ff_count > 10:
                    print("Too many 0xFF opcodes, likely executing uninitialized memory")
                    print(f"PC history: {[hex(pc) for pc in self._pc_history]}")
                    raise Exception("CPU executing uninitialized memory")
            self.cycles += 4
    
    def read_byte(self, address):
        """Read a byte from the given memory address."""
        return self.memory.read(address)
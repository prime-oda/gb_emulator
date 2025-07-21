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
        
        # 16-bit registers
        self.sp = 0xFFFE  # Stack pointer
        self.pc = 0x0000  # Program counter (start at boot ROM)
        
        # Flags register (F)
        self.flag_z = False  # Zero flag
        self.flag_n = False  # Subtract flag
        self.flag_h = False  # Half carry flag
        self.flag_c = False  # Carry flag
        
        # Interrupt master enable
        self.ime = True
        
        # Cycle count
        self.cycles = 0
        
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
        else:
            if self.debug:
                print(f"Unimplemented CB opcode: 0x{opcode:02X} at PC: 0x{self.pc-2:04X}")
            self.cycles += 8
    
    def step(self):
        """Execute one CPU instruction"""
        opcode = self.fetch_byte()
        self.execute_instruction(opcode)
    
    def execute_instruction(self, opcode):
        """Execute instruction based on opcode"""
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
        elif opcode == 0xF0:  # LD A, (0xFF00+n)
            address = 0xFF00 + self.fetch_byte()
            self.a = self.memory.read_byte(address)
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
            self.pc = self.fetch_word()
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
        
        # Logic operations
        elif opcode == 0xA7:  # AND A - AND A with A (used to set flags)
            self.a = self.a & self.a
            self.flag_z = (self.a == 0)
            self.flag_n = False
            self.flag_h = True
            self.flag_c = False
            self.cycles += 4
        
        # Bit operations (CB prefix)
        elif opcode == 0xCB:  # CB prefix for bit operations
            cb_opcode = self.fetch_byte()
            self.execute_cb_instruction(cb_opcode)
        
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
        
        else:
            # Placeholder for unimplemented instructions
            if self.debug:
                print(f"Unimplemented opcode: 0x{opcode:02X} at PC: 0x{self.pc-1:04X}")
            self.cycles += 4
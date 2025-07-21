#!/usr/bin/env python3
"""
Game Boy CB Instructions Batch Generator
Generates implementations for all remaining CB instructions
"""

def generate_remaining_cb_instructions():
    """Generate all remaining CB instruction implementations"""
    
    instructions = []
    
    # RR operations (Right rotate through carry)
    rr_ops = [
        (0x18, 'B', 'self.b'),
        (0x1B, 'E', 'self.e'), 
        (0x1C, 'H', 'self.h'),
        (0x1D, 'L', 'self.l'),
        (0x1E, '(HL)', 'hl_mem'),
        (0x1F, 'A', 'self.a')
    ]
    
    for opcode, reg, var in rr_ops:
        if reg == '(HL)':
            instructions.append(f"""
        elif opcode == 0x{opcode:02X}:  # RR {reg}
            hl_addr = (self.h << 8) | self.l
            value = self.memory.read_byte(hl_addr)
            carry = 1 if self.flag_c else 0
            new_carry = bool(value & 0x01)
            value = (value >> 1) | (carry << 7)
            self.memory.write_byte(hl_addr, value)
            self.flag_z = (value == 0)
            self.flag_n = False
            self.flag_h = False
            self.flag_c = new_carry
            self.cycles += 16""")
        else:
            instructions.append(f"""
        elif opcode == 0x{opcode:02X}:  # RR {reg}
            carry = 1 if self.flag_c else 0
            new_carry = bool({var} & 0x01)
            {var} = ({var} >> 1) | (carry << 7)
            self.flag_z = ({var} == 0)
            self.flag_n = False
            self.flag_h = False
            self.flag_c = new_carry
            self.cycles += 8""")
    
    # SLA operations (Shift Left Arithmetic)
    sla_ops = [
        (0x20, 'B', 'self.b'),
        (0x22, 'D', 'self.d'),
        (0x23, 'E', 'self.e'),
        (0x24, 'H', 'self.h'),
        (0x25, 'L', 'self.l'),
        (0x26, '(HL)', 'hl_mem')
    ]
    
    for opcode, reg, var in sla_ops:
        if reg == '(HL)':
            instructions.append(f"""
        elif opcode == 0x{opcode:02X}:  # SLA {reg}
            hl_addr = (self.h << 8) | self.l
            value = self.memory.read_byte(hl_addr)
            self.flag_c = bool(value & 0x80)
            value = (value << 1) & 0xFF
            self.memory.write_byte(hl_addr, value)
            self.flag_z = (value == 0)
            self.flag_n = False
            self.flag_h = False
            self.cycles += 16""")
        else:
            instructions.append(f"""
        elif opcode == 0x{opcode:02X}:  # SLA {reg}
            self.flag_c = bool({var} & 0x80)
            {var} = ({var} << 1) & 0xFF
            self.flag_z = ({var} == 0)
            self.flag_n = False
            self.flag_h = False
            self.cycles += 8""")
    
    # SRA operations (Shift Right Arithmetic)
    sra_ops = [
        (0x28, 'B', 'self.b'),
        (0x29, 'C', 'self.c'),
        (0x2A, 'D', 'self.d'),
        (0x2B, 'E', 'self.e'),
        (0x2C, 'H', 'self.h'),
        (0x2D, 'L', 'self.l'),
        (0x2E, '(HL)', 'hl_mem')
    ]
    
    for opcode, reg, var in sra_ops:
        if reg == '(HL)':
            instructions.append(f"""
        elif opcode == 0x{opcode:02X}:  # SRA {reg}
            hl_addr = (self.h << 8) | self.l
            value = self.memory.read_byte(hl_addr)
            self.flag_c = bool(value & 0x01)
            value = (value >> 1) | (value & 0x80)  # Keep MSB
            self.memory.write_byte(hl_addr, value)
            self.flag_z = (value == 0)
            self.flag_n = False
            self.flag_h = False
            self.cycles += 16""")
        else:
            instructions.append(f"""
        elif opcode == 0x{opcode:02X}:  # SRA {reg}
            self.flag_c = bool({var} & 0x01)
            {var} = ({var} >> 1) | ({var} & 0x80)  # Keep MSB
            self.flag_z = ({var} == 0)
            self.flag_n = False
            self.flag_h = False
            self.cycles += 8""")
    
    # SWAP operations
    swap_ops = [
        (0x30, 'B', 'self.b'),
        (0x32, 'D', 'self.d'),
        (0x33, 'E', 'self.e'),
        (0x34, 'H', 'self.h'),
        (0x35, 'L', 'self.l'),
        (0x36, '(HL)', 'hl_mem')
    ]
    
    for opcode, reg, var in swap_ops:
        if reg == '(HL)':
            instructions.append(f"""
        elif opcode == 0x{opcode:02X}:  # SWAP {reg}
            hl_addr = (self.h << 8) | self.l
            value = self.memory.read_byte(hl_addr)
            value = ((value & 0x0F) << 4) | ((value & 0xF0) >> 4)
            self.memory.write_byte(hl_addr, value)
            self.flag_z = (value == 0)
            self.flag_n = False
            self.flag_h = False
            self.flag_c = False
            self.cycles += 16""")
        else:
            instructions.append(f"""
        elif opcode == 0x{opcode:02X}:  # SWAP {reg}
            {var} = (({var} & 0x0F) << 4) | (({var} & 0xF0) >> 4)
            self.flag_z = ({var} == 0)
            self.flag_n = False
            self.flag_h = False
            self.flag_c = False
            self.cycles += 8""")
    
    # SRL operations (Shift Right Logical)
    srl_ops = [
        (0x39, 'C', 'self.c'),
        (0x3A, 'D', 'self.d'),
        (0x3B, 'E', 'self.e'),
        (0x3C, 'H', 'self.h'),
        (0x3D, 'L', 'self.l'),
        (0x3E, '(HL)', 'hl_mem')
    ]
    
    for opcode, reg, var in srl_ops:
        if reg == '(HL)':
            instructions.append(f"""
        elif opcode == 0x{opcode:02X}:  # SRL {reg}
            hl_addr = (self.h << 8) | self.l
            value = self.memory.read_byte(hl_addr)
            self.flag_c = bool(value & 0x01)
            value = value >> 1
            self.memory.write_byte(hl_addr, value)
            self.flag_z = (value == 0)
            self.flag_n = False
            self.flag_h = False
            self.cycles += 16""")
        else:
            instructions.append(f"""
        elif opcode == 0x{opcode:02X}:  # SRL {reg}
            self.flag_c = bool({var} & 0x01)
            {var} = {var} >> 1
            self.flag_z = ({var} == 0)
            self.flag_n = False
            self.flag_h = False
            self.cycles += 8""")
    
    return '\n'.join(instructions)

def generate_bit_operations():
    """Generate remaining BIT operations"""
    instructions = []
    
    # Missing BIT operations
    missing_bits = [
        (0x63, 4, 'E', 'self.e'),
        (0x64, 4, 'H', 'self.h'),
        (0x65, 4, 'L', 'self.l'),
        (0x66, 4, '(HL)', 'hl_mem'),
        (0x69, 5, 'C', 'self.c'),
        (0x6B, 5, 'E', 'self.e'),
        (0x6C, 5, 'H', 'self.h'),
        (0x6D, 5, 'L', 'self.l'),
        (0x6E, 5, '(HL)', 'hl_mem'),
        (0x71, 6, 'C', 'self.c'),
        (0x74, 6, 'H', 'self.h'),
        (0x75, 6, 'L', 'self.l'),
        (0x76, 6, '(HL)', 'hl_mem'),
        (0x79, 7, 'C', 'self.c'),
        (0x7D, 7, 'L', 'self.l'),
        (0x7E, 7, '(HL)', 'hl_mem'),
    ]
    
    for opcode, bit, reg, var in missing_bits:
        if reg == '(HL)':
            instructions.append(f"""
        elif opcode == 0x{opcode:02X}:  # BIT {bit},{reg}
            hl_addr = (self.h << 8) | self.l
            value = self.memory.read_byte(hl_addr)
            self.flag_z = not bool(value & (1 << {bit}))
            self.flag_n = False
            self.flag_h = True
            self.cycles += 12""")
        else:
            instructions.append(f"""
        elif opcode == 0x{opcode:02X}:  # BIT {bit},{reg}
            self.flag_z = not bool({var} & (1 << {bit}))
            self.flag_n = False
            self.flag_h = True
            self.cycles += 8""")
    
    return '\n'.join(instructions)

def generate_res_set_operations():
    """Generate all RES and SET operations"""
    instructions = []
    
    registers = ['B', 'C', 'D', 'E', 'H', 'L', '(HL)', 'A']
    register_vars = ['self.b', 'self.c', 'self.d', 'self.e', 'self.h', 'self.l', 'hl_mem', 'self.a']
    
    # RES operations (0x80-0xBF)
    for bit in range(8):
        for reg_idx, (reg, var) in enumerate(zip(registers, register_vars)):
            opcode = 0x80 + (bit * 8) + reg_idx
            
            # Skip already implemented ones
            if opcode in [0x86, 0x8E, 0x96, 0x9E, 0x87, 0x8F, 0x97, 0x9F, 0xA7, 0xAF, 0xB7, 0xBF]:
                continue
            
            if reg == '(HL)':
                instructions.append(f"""
        elif opcode == 0x{opcode:02X}:  # RES {bit},{reg}
            hl_addr = (self.h << 8) | self.l
            value = self.memory.read_byte(hl_addr)
            value &= ~(1 << {bit})
            self.memory.write_byte(hl_addr, value)
            self.cycles += 16""")
            else:
                instructions.append(f"""
        elif opcode == 0x{opcode:02X}:  # RES {bit},{reg}
            {var} &= ~(1 << {bit})
            self.cycles += 8""")
    
    # SET operations (0xC0-0xFF)
    for bit in range(8):
        for reg_idx, (reg, var) in enumerate(zip(registers, register_vars)):
            opcode = 0xC0 + (bit * 8) + reg_idx
            
            # Skip already implemented ones
            if opcode in [0xC7, 0xCF, 0xD7, 0xDF, 0xE7, 0xEF, 0xF7, 0xFF]:
                continue
            
            if reg == '(HL)':
                instructions.append(f"""
        elif opcode == 0x{opcode:02X}:  # SET {bit},{reg}
            hl_addr = (self.h << 8) | self.l
            value = self.memory.read_byte(hl_addr)
            value |= (1 << {bit})
            self.memory.write_byte(hl_addr, value)
            self.cycles += 16""")
            else:
                instructions.append(f"""
        elif opcode == 0x{opcode:02X}:  # SET {bit},{reg}
            {var} |= (1 << {bit})
            self.cycles += 8""")
    
    return '\n'.join(instructions)

if __name__ == "__main__":
    print("=== REMAINING CB INSTRUCTIONS GENERATOR ===\n")
    
    print("# ROTATE/SHIFT OPERATIONS:")
    print(generate_remaining_cb_instructions())
    
    print("\n# REMAINING BIT OPERATIONS:")
    print(generate_bit_operations())
    
    print("\n# RES AND SET OPERATIONS:")
    print(generate_res_set_operations())

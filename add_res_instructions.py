#!/usr/bin/env python3
"""
Generate RES and SET instructions
"""

def generate_res_set_instructions():
    """Generate all missing RES and SET operations efficiently"""
    
    instructions = []
    
    # RES operations (0x80-0xBF) - Reset bit operations
    res_patterns = [
        # RES 0 (0x80-0x87)
        (0x80, 0, 'B', 'self.b'),
        (0x81, 0, 'C', 'self.c'),
        (0x82, 0, 'D', 'self.d'),
        (0x83, 0, 'E', 'self.e'),
        (0x84, 0, 'H', 'self.h'),
        (0x85, 0, 'L', 'self.l'),
        # 0x86 (HL) already implemented
        # 0x87 A already implemented
        
        # RES 1 (0x88-0x8F)
        (0x88, 1, 'B', 'self.b'),
        (0x89, 1, 'C', 'self.c'),
        (0x8A, 1, 'D', 'self.d'),
        (0x8B, 1, 'E', 'self.e'),
        (0x8C, 1, 'H', 'self.h'),
        (0x8D, 1, 'L', 'self.l'),
        # 0x8E (HL) already implemented
        # 0x8F A already implemented
        
        # RES 2 (0x90-0x97)
        (0x90, 2, 'B', 'self.b'),
        (0x91, 2, 'C', 'self.c'),
        (0x92, 2, 'D', 'self.d'),
        (0x93, 2, 'E', 'self.e'),
        (0x94, 2, 'H', 'self.h'),
        (0x95, 2, 'L', 'self.l'),
        # 0x96 (HL) already implemented
        # 0x97 A already implemented
        
        # RES 3 (0x98-0x9F)
        (0x98, 3, 'B', 'self.b'),
        (0x99, 3, 'C', 'self.c'),
        (0x9A, 3, 'D', 'self.d'),
        (0x9B, 3, 'E', 'self.e'),
        (0x9C, 3, 'H', 'self.h'),
        (0x9D, 3, 'L', 'self.l'),
        # 0x9E (HL) already implemented
        # 0x9F A already implemented
        
        # RES 4-7 similar pattern
        (0xA0, 4, 'B', 'self.b'),
        (0xA1, 4, 'C', 'self.c'),
        (0xA2, 4, 'D', 'self.d'),
        (0xA3, 4, 'E', 'self.e'),
        (0xA4, 4, 'H', 'self.h'),
        (0xA5, 4, 'L', 'self.l'),
        (0xA6, 4, '(HL)', 'hl_mem'),
        # 0xA7 A already implemented
        
        (0xA8, 5, 'B', 'self.b'),
        (0xA9, 5, 'C', 'self.c'),
        (0xAA, 5, 'D', 'self.d'),
        (0xAB, 5, 'E', 'self.e'),
        (0xAC, 5, 'H', 'self.h'),
        (0xAD, 5, 'L', 'self.l'),
        (0xAE, 5, '(HL)', 'hl_mem'),
        # 0xAF A already implemented
        
        (0xB0, 6, 'B', 'self.b'),
        (0xB1, 6, 'C', 'self.c'),
        (0xB2, 6, 'D', 'self.d'),
        (0xB3, 6, 'E', 'self.e'),
        (0xB4, 6, 'H', 'self.h'),
        (0xB5, 6, 'L', 'self.l'),
        (0xB6, 6, '(HL)', 'hl_mem'),
        # 0xB7 A already implemented
        
        (0xB8, 7, 'B', 'self.b'),
        (0xB9, 7, 'C', 'self.c'),
        (0xBA, 7, 'D', 'self.d'),
        (0xBB, 7, 'E', 'self.e'),
        (0xBC, 7, 'H', 'self.h'),
        (0xBD, 7, 'L', 'self.l'),
        (0xBE, 7, '(HL)', 'hl_mem'),
        # 0xBF A already implemented
    ]
    
    for opcode, bit, reg, var in res_patterns:
        if reg == '(HL)':
            instructions.append(f"""        elif opcode == 0x{opcode:02X}:  # RES {bit},{reg}
            hl_addr = (self.h << 8) | self.l
            value = self.memory.read_byte(hl_addr)
            value &= ~(1 << {bit})
            self.memory.write_byte(hl_addr, value)
            self.cycles += 16""")
        else:
            instructions.append(f"""        elif opcode == 0x{opcode:02X}:  # RES {bit},{reg}
            {var} &= ~(1 << {bit})
            self.cycles += 8""")
    
    return '\n'.join(instructions)

print(generate_res_set_instructions())

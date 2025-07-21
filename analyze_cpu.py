#!/usr/bin/env python3
"""
Game Boy CPU Instruction Coverage Analysis
Analyzes current CPU implementation to identify missing opcodes
"""

import re
import os

# Complete Game Boy CPU (Sharp LR35902) instruction set
COMPLETE_INSTRUCTION_SET = {
    # 0x00-0x0F
    0x00: "NOP",
    0x01: "LD BC,nn",
    0x02: "LD (BC),A", 
    0x03: "INC BC",
    0x04: "INC B",
    0x05: "DEC B",
    0x06: "LD B,n",
    0x07: "RLCA",
    0x08: "LD (nn),SP",
    0x09: "ADD HL,BC",
    0x0A: "LD A,(BC)",
    0x0B: "DEC BC",
    0x0C: "INC C",
    0x0D: "DEC C",
    0x0E: "LD C,n",
    0x0F: "RRCA",
    
    # 0x10-0x1F
    0x10: "STOP",
    0x11: "LD DE,nn",
    0x12: "LD (DE),A",
    0x13: "INC DE",
    0x14: "INC D",
    0x15: "DEC D",
    0x16: "LD D,n",
    0x17: "RLA",
    0x18: "JR n",
    0x19: "ADD HL,DE",
    0x1A: "LD A,(DE)",
    0x1B: "DEC DE",
    0x1C: "INC E",
    0x1D: "DEC E",
    0x1E: "LD E,n",
    0x1F: "RRA",
    
    # 0x20-0x2F
    0x20: "JR NZ,n",
    0x21: "LD HL,nn",
    0x22: "LD (HL+),A",
    0x23: "INC HL",
    0x24: "INC H",
    0x25: "DEC H",
    0x26: "LD H,n",
    0x27: "DAA",
    0x28: "JR Z,n",
    0x29: "ADD HL,HL",
    0x2A: "LD A,(HL+)",
    0x2B: "DEC HL",
    0x2C: "INC L",
    0x2D: "DEC L",
    0x2E: "LD L,n",
    0x2F: "CPL",
    
    # 0x30-0x3F
    0x30: "JR NC,n",
    0x31: "LD SP,nn",
    0x32: "LD (HL-),A",
    0x33: "INC SP",
    0x34: "INC (HL)",
    0x35: "DEC (HL)",
    0x36: "LD (HL),n",
    0x37: "SCF",
    0x38: "JR C,n",
    0x39: "ADD HL,SP",
    0x3A: "LD A,(HL-)",
    0x3B: "DEC SP",
    0x3C: "INC A",
    0x3D: "DEC A",
    0x3E: "LD A,n",
    0x3F: "CCF",
    
    # 0x40-0x7F: 8-bit loads
    **{0x40 + dst*8 + src: f"LD {['B','C','D','E','H','L','(HL)','A'][dst]},{['B','C','D','E','H','L','(HL)','A'][src]}" 
       for dst in range(8) for src in range(8) if dst*8 + src != 0x36},
    0x76: "HALT",
    
    # 0x80-0xBF: 8-bit arithmetic
    **{0x80 + op*8 + reg: f"{['ADD A','ADC A','SUB','SBC A','AND','XOR','OR','CP'][op]},{['B','C','D','E','H','L','(HL)','A'][reg]}" 
       for op in range(8) for reg in range(8)},
    
    # 0xC0-0xFF: Control flow and misc
    0xC0: "RET NZ", 0xC1: "POP BC", 0xC2: "JP NZ,nn", 0xC3: "JP nn",
    0xC4: "CALL NZ,nn", 0xC5: "PUSH BC", 0xC6: "ADD A,n", 0xC7: "RST 00H",
    0xC8: "RET Z", 0xC9: "RET", 0xCA: "JP Z,nn", 0xCB: "CB prefix",
    0xCC: "CALL Z,nn", 0xCD: "CALL nn", 0xCE: "ADC A,n", 0xCF: "RST 08H",
    0xD0: "RET NC", 0xD1: "POP DE", 0xD2: "JP NC,nn", 0xD3: "INVALID",
    0xD4: "CALL NC,nn", 0xD5: "PUSH DE", 0xD6: "SUB n", 0xD7: "RST 10H",
    0xD8: "RET C", 0xD9: "RETI", 0xDA: "JP C,nn", 0xDB: "INVALID",
    0xDC: "CALL C,nn", 0xDD: "INVALID", 0xDE: "SBC A,n", 0xDF: "RST 18H",
    0xE0: "LD (FF00+n),A", 0xE1: "POP HL", 0xE2: "LD (FF00+C),A", 0xE3: "INVALID",
    0xE4: "INVALID", 0xE5: "PUSH HL", 0xE6: "AND n", 0xE7: "RST 20H",
    0xE8: "ADD SP,n", 0xE9: "JP (HL)", 0xEA: "LD (nn),A", 0xEB: "INVALID",
    0xEC: "INVALID", 0xED: "INVALID", 0xEE: "XOR n", 0xEF: "RST 28H",
    0xF0: "LD A,(FF00+n)", 0xF1: "POP AF", 0xF2: "LD A,(FF00+C)", 0xF3: "DI",
    0xF4: "INVALID", 0xF5: "PUSH AF", 0xF6: "OR n", 0xF7: "RST 30H",
    0xF8: "LD HL,SP+n", 0xF9: "LD SP,HL", 0xFA: "LD A,(nn)", 0xFB: "EI",
    0xFC: "INVALID", 0xFD: "INVALID", 0xFE: "CP n", 0xFF: "RST 38H"
}

# Complete CB-prefixed instruction set
COMPLETE_CB_INSTRUCTION_SET = {}

# CB 0x00-0x3F: Rotate/shift operations
rotate_ops = ['RLC', 'RRC', 'RL', 'RR', 'SLA', 'SRA', 'SWAP', 'SRL']
registers = ['B', 'C', 'D', 'E', 'H', 'L', '(HL)', 'A']

for op_idx, op in enumerate(rotate_ops):
    for reg_idx, reg in enumerate(registers):
        opcode = op_idx * 8 + reg_idx
        COMPLETE_CB_INSTRUCTION_SET[opcode] = f"{op} {reg}"

# CB 0x40-0x7F: BIT operations
for bit in range(8):
    for reg_idx, reg in enumerate(registers):
        opcode = 0x40 + bit * 8 + reg_idx
        COMPLETE_CB_INSTRUCTION_SET[opcode] = f"BIT {bit},{reg}"

# CB 0x80-0xBF: RES operations
for bit in range(8):
    for reg_idx, reg in enumerate(registers):
        opcode = 0x80 + bit * 8 + reg_idx
        COMPLETE_CB_INSTRUCTION_SET[opcode] = f"RES {bit},{reg}"

# CB 0xC0-0xFF: SET operations
for bit in range(8):
    for reg_idx, reg in enumerate(registers):
        opcode = 0xC0 + bit * 8 + reg_idx
        COMPLETE_CB_INSTRUCTION_SET[opcode] = f"SET {bit},{reg}"


def analyze_cpu_implementation():
    """Analyze current CPU implementation to find missing opcodes"""
    
    # Read current CPU implementation
    cpu_file = "/Users/oda/github/gb_emulator/src/gameboy/cpu.py"
    
    if not os.path.exists(cpu_file):
        print(f"Error: CPU file not found at {cpu_file}")
        return
    
    with open(cpu_file, 'r') as f:
        cpu_content = f.read()
    
    # Extract implemented regular opcodes
    regular_pattern = r'elif opcode == 0x([0-9A-Fa-f]{2}):'
    cb_pattern = r'elif opcode == 0x([0-9A-Fa-f]{2}):'  # In CB section
    
    implemented_regular = set()
    implemented_cb = set()
    
    # Find regular opcodes
    matches = re.findall(regular_pattern, cpu_content)
    for match in matches:
        opcode = int(match, 16)
        implemented_regular.add(opcode)
    
    # Find CB opcodes (need to be more specific)
    # Look for CB opcodes in the execute_cb_instruction method
    cb_method_start = cpu_content.find("def execute_cb_instruction")
    if cb_method_start != -1:
        cb_method_end = cpu_content.find("def ", cb_method_start + 1)
        if cb_method_end == -1:
            cb_method_end = len(cpu_content)
        
        cb_section = cpu_content[cb_method_start:cb_method_end]
        cb_matches = re.findall(regular_pattern, cb_section)
        for match in cb_matches:
            opcode = int(match, 16)
            implemented_cb.add(opcode)
    
    # Also check for specific instructions that may be implemented differently
    if "0x00" in cpu_content and "NOP" in cpu_content:
        implemented_regular.add(0x00)
    
    # Analyze missing instructions
    missing_regular = []
    missing_cb = []
    
    # Check regular instructions
    for opcode in range(256):
        if opcode in COMPLETE_INSTRUCTION_SET:
            if COMPLETE_INSTRUCTION_SET[opcode] != "INVALID":
                if opcode not in implemented_regular:
                    missing_regular.append((opcode, COMPLETE_INSTRUCTION_SET[opcode]))
    
    # Check CB instructions
    for opcode in range(256):
        if opcode in COMPLETE_CB_INSTRUCTION_SET:
            if opcode not in implemented_cb:
                missing_cb.append((opcode, COMPLETE_CB_INSTRUCTION_SET[opcode]))
    
    # Print results
    print("=== GAME BOY CPU INSTRUCTION COVERAGE ANALYSIS ===\n")
    
    print(f"IMPLEMENTED REGULAR OPCODES: {len(implemented_regular)}")
    print(f"IMPLEMENTED CB OPCODES: {len(implemented_cb)}")
    
    print(f"\nMISSING REGULAR INSTRUCTIONS ({len(missing_regular)} total):")
    if missing_regular:
        # Group by instruction type for better organization
        load_ops = []
        jump_ops = []
        arith_ops = []
        misc_ops = []
        
        for opcode, name in missing_regular:
            if "LD" in name:
                load_ops.append((opcode, name))
            elif any(x in name for x in ["JP", "JR", "CALL", "RET", "RST"]):
                jump_ops.append((opcode, name))
            elif any(x in name for x in ["ADD", "SUB", "INC", "DEC", "AND", "OR", "XOR", "CP"]):
                arith_ops.append((opcode, name))
            else:
                misc_ops.append((opcode, name))
        
        if load_ops:
            print("\n  LOAD OPERATIONS:")
            for opcode, name in sorted(load_ops):
                print(f"    0x{opcode:02X}: {name}")
        
        if arith_ops:
            print("\n  ARITHMETIC OPERATIONS:")
            for opcode, name in sorted(arith_ops):
                print(f"    0x{opcode:02X}: {name}")
        
        if jump_ops:
            print("\n  CONTROL FLOW OPERATIONS:")
            for opcode, name in sorted(jump_ops):
                print(f"    0x{opcode:02X}: {name}")
        
        if misc_ops:
            print("\n  MISCELLANEOUS OPERATIONS:")
            for opcode, name in sorted(misc_ops):
                print(f"    0x{opcode:02X}: {name}")
    
    print(f"\nMISSING CB INSTRUCTIONS ({len(missing_cb)} total):")
    if missing_cb:
        # Group CB instructions by type
        rlc_ops = [x for x in missing_cb if x[1].startswith("RLC")]
        rrc_ops = [x for x in missing_cb if x[1].startswith("RRC")]
        rl_ops = [x for x in missing_cb if x[1].startswith("RL ")]
        rr_ops = [x for x in missing_cb if x[1].startswith("RR ")]
        sla_ops = [x for x in missing_cb if x[1].startswith("SLA")]
        sra_ops = [x for x in missing_cb if x[1].startswith("SRA")]
        srl_ops = [x for x in missing_cb if x[1].startswith("SRL")]
        swap_ops = [x for x in missing_cb if x[1].startswith("SWAP")]
        bit_ops = [x for x in missing_cb if x[1].startswith("BIT")]
        res_ops = [x for x in missing_cb if x[1].startswith("RES")]
        set_ops = [x for x in missing_cb if x[1].startswith("SET")]
        
        if bit_ops:
            print("\n  BIT OPERATIONS:")
            for opcode, name in sorted(bit_ops):
                print(f"    0x{opcode:02X}: {name}")
        
        if res_ops:
            print("\n  RES OPERATIONS:")
            for opcode, name in sorted(res_ops):
                print(f"    0x{opcode:02X}: {name}")
        
        if set_ops:
            print("\n  SET OPERATIONS:")
            for opcode, name in sorted(set_ops):
                print(f"    0x{opcode:02X}: {name}")
        
        if any([rlc_ops, rrc_ops, rl_ops, rr_ops, sla_ops, sra_ops, srl_ops, swap_ops]):
            print("\n  ROTATE/SHIFT OPERATIONS:")
            for ops, label in [(rlc_ops, "RLC"), (rrc_ops, "RRC"), (rl_ops, "RL"), (rr_ops, "RR"), 
                              (sla_ops, "SLA"), (sra_ops, "SRA"), (srl_ops, "SRL"), (swap_ops, "SWAP")]:
                if ops:
                    print(f"    {label}:")
                    for opcode, name in sorted(ops):
                        print(f"      0x{opcode:02X}: {name}")
    
    # Summary statistics
    total_valid_regular = len([x for x in COMPLETE_INSTRUCTION_SET.values() if x != "INVALID"])
    total_valid_cb = len(COMPLETE_CB_INSTRUCTION_SET)
    
    regular_coverage = ((total_valid_regular - len(missing_regular)) / total_valid_regular) * 100
    cb_coverage = ((total_valid_cb - len(missing_cb)) / total_valid_cb) * 100
    total_coverage = ((total_valid_regular + total_valid_cb - len(missing_regular) - len(missing_cb)) / 
                     (total_valid_regular + total_valid_cb)) * 100
    
    print(f"\n=== COVERAGE STATISTICS ===")
    print(f"Regular instructions: {total_valid_regular - len(missing_regular)}/{total_valid_regular} ({regular_coverage:.1f}%)")
    print(f"CB instructions: {total_valid_cb - len(missing_cb)}/{total_valid_cb} ({cb_coverage:.1f}%)")
    print(f"Total coverage: {total_valid_regular + total_valid_cb - len(missing_regular) - len(missing_cb)}/{total_valid_regular + total_valid_cb} ({total_coverage:.1f}%)")
    
    return missing_regular, missing_cb


if __name__ == "__main__":
    analyze_cpu_implementation()

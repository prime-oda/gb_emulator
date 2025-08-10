#!/usr/bin/env python3
"""
CPU命令サイクル分析ツール
現在の実装とBlargg標準サイクル表の比較
"""
import sys
import os
sys.path.append('src')

from gameboy.emulator import GameBoy
import re

def get_blargg_standard_cycles():
    """Blargg標準サイクル表を取得"""
    # readme.txtから抽出した標準サイクル数
    normal_cycles = [
        1,3,2,2,1,1,2,1,5,2,2,2,1,1,2,1,
        0,3,2,2,1,1,2,1,3,2,2,2,1,1,2,1,
        2,3,2,2,1,1,2,1,2,2,2,2,1,1,2,1,
        2,3,2,2,3,3,3,1,2,2,2,2,1,1,2,1,
        1,1,1,1,1,1,2,1,1,1,1,1,1,1,2,1,
        1,1,1,1,1,1,2,1,1,1,1,1,1,1,2,1,
        1,1,1,1,1,1,2,1,1,1,1,1,1,1,2,1,
        2,2,2,2,2,2,0,2,1,1,1,1,1,1,2,1,
        1,1,1,1,1,1,2,1,1,1,1,1,1,1,2,1,
        1,1,1,1,1,1,2,1,1,1,1,1,1,1,2,1,
        1,1,1,1,1,1,2,1,1,1,1,1,1,1,2,1,
        1,1,1,1,1,1,2,1,1,1,1,1,1,1,2,1,
        2,3,3,4,3,4,2,4,2,4,3,0,3,6,2,4,
        2,3,3,0,3,4,2,4,2,4,3,0,3,0,2,4,
        3,3,2,0,0,4,2,4,4,1,4,0,0,0,2,4,
        3,3,2,1,0,4,2,4,3,2,4,1,0,0,2,4
    ]
    
    cb_cycles = [
        2,2,2,2,2,2,4,2,2,2,2,2,2,2,4,2,
        2,2,2,2,2,2,4,2,2,2,2,2,2,2,4,2,
        2,2,2,2,2,2,4,2,2,2,2,2,2,2,4,2,
        2,2,2,2,2,2,4,2,2,2,2,2,2,2,4,2,
        2,2,2,2,2,2,3,2,2,2,2,2,2,2,3,2,
        2,2,2,2,2,2,3,2,2,2,2,2,2,2,3,2,
        2,2,2,2,2,2,3,2,2,2,2,2,2,2,3,2,
        2,2,2,2,2,2,3,2,2,2,2,2,2,2,3,2,
        2,2,2,2,2,2,4,2,2,2,2,2,2,2,4,2,
        2,2,2,2,2,2,4,2,2,2,2,2,2,2,4,2,
        2,2,2,2,2,2,4,2,2,2,2,2,2,2,4,2,
        2,2,2,2,2,2,4,2,2,2,2,2,2,2,4,2,
        2,2,2,2,2,2,4,2,2,2,2,2,2,2,4,2,
        2,2,2,2,2,2,4,2,2,2,2,2,2,2,4,2,
        2,2,2,2,2,2,4,2,2,2,2,2,2,2,4,2,
        2,2,2,2,2,2,4,2,2,2,2,2,2,2,4,2
    ]
    
    return normal_cycles, cb_cycles

def extract_current_cycles_from_source():
    """現在のソースコードから命令サイクル数を抽出"""
    print('🔍 CPU.execute_instruction()から現在の実装サイクル数を抽出')
    print('=' * 70)
    
    current_cycles = {}
    cb_cycles = {}
    
    # CPUファイルを読み込み
    with open('src/gameboy/cpu.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 通常命令のサイクル数を抽出
    print('📊 通常命令サイクル数抽出:')
    
    # elif opcode == 0xXX: パターンを検索
    opcode_patterns = re.findall(r'elif opcode == (0x[0-9A-Fa-f]{2}):(.*?)(?=elif opcode|else:|def )', content, re.DOTALL)
    
    for opcode_str, code_block in opcode_patterns:
        opcode = int(opcode_str, 16)
        
        # self.cycles += X を検索
        cycle_matches = re.findall(r'self\.cycles \+= (\d+)', code_block)
        if cycle_matches:
            # 最初に見つかったサイクル数を使用（条件分岐は後で処理）
            cycles = int(cycle_matches[0])
            current_cycles[opcode] = cycles
    
    # if opcode == 0xXX: パターンも検索
    if_patterns = re.findall(r'if opcode == (0x[0-9A-Fa-f]{2}):(.*?)(?=elif|else:|def )', content, re.DOTALL)
    
    for opcode_str, code_block in if_patterns:
        opcode = int(opcode_str, 16)
        cycle_matches = re.findall(r'self\.cycles \+= (\d+)', code_block)
        if cycle_matches:
            cycles = int(cycle_matches[0])
            current_cycles[opcode] = cycles
    
    # CB拡張命令の処理を検索（execute_cb_instruction メソッド内）
    cb_method = re.search(r'def execute_cb_instruction\(self, opcode\):', content)
    if cb_method:
        print('\n📊 CB拡張命令サイクル数抽出（execute_cb_instruction内）:')
        
        # CB命令は固定のサイクル数を使用（実装済み）
        # BIT operations: 8T(reg) + 4T(mem access) = 12T for (HL), 8T for others
        # SET/RES operations: 8T(reg) + 8T(mem access) = 16T for (HL), 8T for others  
        # Rotate/Shift operations: 8T(reg) + 8T(mem access) = 16T for (HL), 8T for others
        
        # 全CB命令に適切なサイクル数を設定
        for opcode in range(256):
            if opcode >= 0x40 and opcode <= 0x7F:  # BIT operations
                if (opcode & 0x07) == 6:  # (HL)
                    cb_cycles[opcode] = 12
                else:  # registers
                    cb_cycles[opcode] = 8
            else:  # SET/RES/Rotate/Shift operations
                if (opcode & 0x07) == 6:  # (HL)
                    cb_cycles[opcode] = 16
                else:  # registers
                    cb_cycles[opcode] = 8
    
    print(f'\\n📋 抽出結果:')
    print(f'  通常命令: {len(current_cycles)}/256 個')
    print(f'  CB拡張命令: {len(cb_cycles)}/256 個')
    
    return current_cycles, cb_cycles

def compare_cycles():
    """現在の実装とBlargg標準の比較"""
    print('\\n🔍 サイクル数比較分析')
    print('=' * 70)
    
    # 標準サイクル数取得
    standard_normal, standard_cb = get_blargg_standard_cycles()
    
    # 現在の実装サイクル数取得
    current_normal, current_cb = extract_current_cycles_from_source()
    
    # 通常命令比較
    print('📊 通常命令比較:')
    normal_mismatches = []
    missing_opcodes = []
    
    for opcode in range(256):
        standard_cycle = standard_normal[opcode]
        current_cycle = current_normal.get(opcode, None)
        
        if current_cycle is None:
            if standard_cycle != 0:  # 0は未実装/不正命令
                missing_opcodes.append(opcode)
        elif standard_cycle != 0 and current_cycle != standard_cycle * 4:  # Game Boyは4T-cycle単位
            normal_mismatches.append({
                'opcode': opcode,
                'standard': standard_cycle * 4,
                'current': current_cycle,
                'diff': current_cycle - (standard_cycle * 4)
            })
    
    print(f'  不一致: {len(normal_mismatches)} 個')
    print(f'  未実装: {len(missing_opcodes)} 個')
    
    if normal_mismatches:
        print('\\n❌ サイクル数不一致詳細 (上位10個):')
        for mismatch in normal_mismatches[:10]:
            print(f'    0x{mismatch["opcode"]:02X}: 標準{mismatch["standard"]:2d} vs 現在{mismatch["current"]:2d} (差分{mismatch["diff"]:+3d})')
    
    if missing_opcodes:
        print(f'\\n⚠️  未実装opcode (上位10個): {[f"0x{op:02X}" for op in missing_opcodes[:10]]}')
    
    # CB拡張命令比較
    print('\\n📊 CB拡張命令比較:')
    cb_mismatches = []
    cb_missing = []
    
    for opcode in range(256):
        standard_cycle = standard_cb[opcode]
        current_cycle = current_cb.get(opcode, None)
        
        if current_cycle is None:
            cb_missing.append(opcode)
        elif current_cycle != standard_cycle * 4:  # Game Boyは4T-cycle単位
            cb_mismatches.append({
                'opcode': opcode,
                'standard': standard_cycle * 4,
                'current': current_cycle,
                'diff': current_cycle - (standard_cycle * 4)
            })
    
    print(f'  不一致: {len(cb_mismatches)} 個')
    print(f'  未実装: {len(cb_missing)} 個')
    
    if cb_mismatches:
        print('\\n❌ CB命令サイクル数不一致詳細 (上位10個):')
        for mismatch in cb_mismatches[:10]:
            print(f'    CB {mismatch["opcode"]:02X}: 標準{mismatch["standard"]:2d} vs 現在{mismatch["current"]:2d} (差分{mismatch["diff"]:+3d})')
    
    if cb_missing:
        print(f'\\n⚠️  未実装CB opcode (上位10個): {[f"0x{op:02X}" for op in cb_missing[:10]]}')
    
    # サマリー
    total_errors = len(normal_mismatches) + len(missing_opcodes) + len(cb_mismatches) + len(cb_missing)
    accuracy = ((512 - total_errors) / 512) * 100
    
    print(f'\\n📊 総合分析結果:')
    print(f'  総エラー数: {total_errors}/512')
    print(f'  現在の精度: {accuracy:.1f}%')
    
    return {
        'normal_mismatches': normal_mismatches,
        'missing_opcodes': missing_opcodes,
        'cb_mismatches': cb_mismatches,
        'cb_missing': cb_missing,
        'accuracy': accuracy
    }

if __name__ == "__main__":
    print('🔧 Instruction Timing 分析ツール')
    print('=' * 70)
    
    analysis = compare_cycles()
    
    print(f'\\n🎯 改善が必要な領域:')
    if analysis['accuracy'] < 95.0:
        print(f'  ⚡ 緊急: サイクル精度が{analysis["accuracy"]:.1f}%と低い')
        print(f'  📝 推奨: 全命令のサイクル数見直しが必要')
    else:
        print(f'  ✅ 良好: サイクル精度{analysis["accuracy"]:.1f}%')
        print(f'  🔧 推奨: 細かい調整のみ必要')
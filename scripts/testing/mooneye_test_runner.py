#!/usr/bin/env python3
"""
Mooneye Test Suite ランナー - フィボナッチ判定システム付き
"""
import sys
import os
sys.path.append('src')

from gameboy.emulator import GameBoy

class MooneyeTestRunner:
    """Mooneye Test Suite 実行とフィボナッチ判定"""
    
    # Mooneye 成功判定フィボナッチ数値
    FIBONACCI_SUCCESS = {
        'B': 3,
        'C': 5, 
        'D': 8,
        'E': 13,
        'H': 21,
        'L': 34
    }
    
    def __init__(self):
        self.results = {}
    
    def check_fibonacci_registers(self, gb):
        """レジスタがフィボナッチ数値かチェック"""
        cpu_registers = {
            'B': gb.cpu.b,
            'C': gb.cpu.c,
            'D': gb.cpu.d,
            'E': gb.cpu.e,
            'H': gb.cpu.h,
            'L': gb.cpu.l
        }
        
        success_count = 0
        total_regs = len(self.FIBONACCI_SUCCESS)
        
        print(f"📊 Mooneye フィボナッチ判定:")
        for reg_name, expected in self.FIBONACCI_SUCCESS.items():
            actual = cpu_registers[reg_name]
            is_correct = (actual == expected)
            success_count += is_correct
            status = "✅" if is_correct else "❌"
            print(f"  {reg_name}: {actual:3d} (期待値: {expected:2d}) {status}")
        
        success_rate = success_count / total_regs
        overall_success = success_count == total_regs
        
        print(f"📈 判定結果: {success_count}/{total_regs} ({success_rate:.1%}) {'✅ PASS' if overall_success else '❌ FAIL'}")
        
        return overall_success, success_rate
    
    def run_test(self, rom_path, max_cycles=50_000_000):
        """単一のMooneyeテストを実行"""
        test_name = os.path.basename(rom_path).replace('.gb', '')
        print(f'\n🧪 Mooneye Test: {test_name}')
        print('=' * 60)
        
        if not os.path.exists(rom_path):
            print(f"❌ テストROMが見つかりません: {rom_path}")
            return False, 0.0
        
        try:
            gb = GameBoy(debug=False)
            gb.load_rom(rom_path)
            
            cycles = 0
            last_opcode = None
            
            while cycles < max_cycles:
                # オペコード0x40 (LD B,B) を監視
                current_pc = gb.cpu.pc
                if current_pc < len(gb.memory.rom):
                    current_opcode = gb.memory.rom[current_pc]
                    
                    # 0x40 (LD B,B) でMooneyeテスト完了
                    if current_opcode == 0x40 and last_opcode != 0x40:
                        print(f"🎯 テスト完了検出 (LD B,B): {cycles:,} サイクル")
                        break
                    
                    last_opcode = current_opcode
                
                gb.step()
                cycles = gb.cpu.cycles
                
                # 進捗表示
                if cycles % 10_000_000 == 0:
                    print(f"[{cycles//1_000_000:2d}M] 実行中... PC: 0x{gb.cpu.pc:04X}")
            
            print(f"\n📊 実行完了: {cycles:,} サイクル")
            
            # フィボナッチ判定
            success, success_rate = self.check_fibonacci_registers(gb)
            
            # 結果記録
            self.results[test_name] = {
                'success': success,
                'success_rate': success_rate,
                'cycles': cycles
            }
            
            return success, success_rate
            
        except Exception as e:
            print(f"❌ テスト実行エラー: {e}")
            import traceback
            traceback.print_exc()
            return False, 0.0
    
    def run_timer_tests(self):
        """タイマー関連テスト群を実行"""
        timer_test_dir = "roms/mooneye-test-suite-wilbertpol/acceptance/timer"
        
        # 重要なタイマーテストを優先実行
        priority_tests = [
            'tim01.gb',      # 262144Hz - 02-interrupts.gb と同周波数！
            'timer_if.gb',   # タイマー割り込みフラグテスト
            'tima_reload.gb' # TIMA リロードテスト
        ]
        
        print(f"🎯 タイマーテスト群実行開始")
        print(f"=" * 70)
        
        success_count = 0
        total_count = 0
        
        # 優先テスト実行
        for test_name in priority_tests:
            test_path = os.path.join(timer_test_dir, test_name)
            if os.path.exists(test_path):
                success, rate = self.run_test(test_path)
                success_count += success
                total_count += 1
        
        # その他のタイマーテスト
        all_timer_tests = [f for f in os.listdir(timer_test_dir) if f.endswith('.gb')]
        for test_name in all_timer_tests:
            if test_name not in priority_tests:
                test_path = os.path.join(timer_test_dir, test_name)
                success, rate = self.run_test(test_path, max_cycles=30_000_000)  # 短めのタイムアウト
                success_count += success
                total_count += 1
        
        # 全体結果
        overall_rate = success_count / total_count if total_count > 0 else 0
        print(f"\n🏆 タイマーテスト総合結果")
        print(f"=" * 50)
        print(f"成功テスト: {success_count}/{total_count}")
        print(f"成功率: {overall_rate:.1%}")
        
        return success_count, total_count, overall_rate

def main():
    """メイン実行"""
    runner = MooneyeTestRunner()
    
    if len(sys.argv) > 1:
        # 個別テスト実行
        rom_path = sys.argv[1]
        runner.run_test(rom_path)
    else:
        # タイマーテスト群実行
        runner.run_timer_tests()

if __name__ == "__main__":
    main()
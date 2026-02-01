"""
Game Boy Timer Implementation - PyBoy Compatible Style
Handles DIV, TIMA, TMA, and TAC registers with proper timing.

Cython最適化: Phase 1
"""
import os
try:
    import cython
except ImportError:
    # Cythonがない環境でも動作するようにダミークラス
    class cython:
        @staticmethod
        def declare(*args, **kwargs):
            pass

# PyBoy互換のMAX_CYCLES定義
MAX_CYCLES: cython.longlong = 0x7FFFFFFFFFFFFFFF  # 最大サイクル数

class Timer:
    def __init__(self, memory, debug: cython.bint = False):
        # PyBoy準拠: 全て0で初期化
        self.DIV: cython.int = 0
        self.TIMA: cython.int = 0
        self.TMA: cython.int = 0
        self.TAC: cython.int = 0

        # PyBoy互換のカウンタ
        self.DIV_counter: cython.int = 0
        self.TIMA_counter: cython.int = 0
        self.dividers: list = [10, 4, 6, 8]
        self._cycles_to_interrupt: cython.longlong = MAX_CYCLES  # 初期状態: タイマー無効なのでMAX_CYCLES

        # 統一カウンタシステム（将来の拡張用）
        self.system_counter: cython.longlong = 0

        # デバッグ機能
        self.debug_enabled: cython.bint = debug
        self.tac_write_cycle = None
        self.last_debug_cycle: cython.longlong = 0
        self.last_cycles: cython.longlong = 0

        # メモリ参照保存
        self.memory = memory
        
        # PPU参照（メモリタイミングテスト対応）
        self.ppu = None  # emulatorで設定
        
    def reset(self):
        """PyBoy互換のリセット処理"""
        # TODO: Should probably one be DIV=0, but this makes a bunch of mooneye tests pass
        self.DIV_counter = 0
        self.TIMA_counter = 0
        self.DIV = 0
        
    def init_post_boot_state(self):
        """Post-boot state initialization"""
        # 統一カウンタからDIV=0x1Cを生成
        self.DIV = 0x1C  # Blarggテスト互換の初期値
        self.system_counter = self.DIV << 8  # DIVから逆算

        # 旧カウンタ（互換性のため）
        self.DIV_counter = 0
        self.TIMA_counter = 0

        # Timer関連レジスタ
        self.memory.io[0x04] = self.DIV
        self.memory.io[0x05] = 0x00   # TIMA
        self.memory.io[0x06] = 0x00   # TMA
        self.memory.io[0x07] = 0xF8   # TAC
        self.TIMA = 0
        self.TMA = 0
        self.TAC = 0xF8

        self.last_cycles = 0

        if self.debug_enabled:
            print(f"🔧 Timer post-boot初期化: DIV=0x{self.DIV:02X}, system_counter=0x{self.system_counter:04X}")
            
    def get_div(self):
        """統一カウンタからDIVレジスタ値を計算

        Game Boy実機では、DIVは内部カウンタの上位8ビット（bit 8-15）
        256サイクルごとに1増加する
        """
        return (self.system_counter >> 8) & 0xFF

    def get_timer_bit(self, tac):
        """統一カウンタから現在のタイマービット値を取得

        TACの下位2ビットで選択されたビット位置の値を返す
        TAC=00: bit 10 (1024 cycles)
        TAC=01: bit 4  (16 cycles)
        TAC=10: bit 6  (64 cycles)
        TAC=11: bit 8  (256 cycles)
        """
        freq_select = tac & 0x03
        bit_positions = [10, 4, 6, 8]  # Game Boy実機のビット位置
        bit_pos = bit_positions[freq_select]
        return (self.system_counter >> bit_pos) & 1

    def increment_tima(self):
        """TIMAをインクリメント（オーバーフロー処理付き）

        注: このメソッドは統一カウンタシステム用（現在未使用）

        Returns:
            bool: オーバーフローが発生した場合True
        """
        self.TIMA = (self.TIMA + 1) & 0xFF

        if self.TIMA == 0:  # オーバーフロー発生（0xFF → 0x00）
            # TMAをリロード
            self.TIMA = self.TMA

            # デバッグ出力
            if self.debug_enabled and os.getenv('TIMER_DEBUG'):
                print(f"[Timer] TIMA overflow! Reloaded with TMA=0x{self.TMA:02X} at system_counter=0x{self.system_counter:08X}")

            return True  # 割り込み発生

        return False

    def read_register(self, address: cython.int) -> cython.int:
        """PyBoy互換のレジスタ読み出し"""
        if address == 0xFF04:  # DIV
            return self.DIV
        elif address == 0xFF05:  # TIMA
            return self.TIMA
        elif address == 0xFF06:  # TMA
            return self.TMA
        elif address == 0xFF07:  # TAC
            return self.TAC
        return 0xFF
        
    def write_register(self, address: cython.int, value: cython.int) -> None:
        """PyBoy方式のシンプルなレジスタ書き込み"""
        value &= 0xFF

        if address == 0xFF04:  # DIV
            # PyBoy準拠: シンプルにreset()を呼ぶだけ
            self.reset()
            if self.debug_enabled and os.getenv('TIMER_DEBUG'):
                print(f"[Timer] DIV reset to 0")

        elif address == 0xFF05:  # TIMA
            # PyBoy方式: 単純な値の代入のみ
            if self.debug_enabled and os.getenv('TIMER_DEBUG'):
                print(f"[Timer] TIMA write: 0x{self.TIMA:02X} -> 0x{value:02X}")
            self.TIMA = value

        elif address == 0xFF06:  # TMA
            if self.debug_enabled and os.getenv('TIMER_DEBUG'):
                print(f"[Timer] TMA write: 0x{self.TMA:02X} -> 0x{value:02X}")
            self.TMA = value

        elif address == 0xFF07:  # TAC
            old_tac = self.TAC
            self.TAC = value & 0b111

            # バッチ処理用: _cycles_to_interruptを更新
            if self.TAC & 0b100:  # タイマー有効化
                divider = self.dividers[self.TAC & 0b11]
                self._cycles_to_interrupt = ((0x100 - self.TIMA) << divider) - self.TIMA_counter
            else:  # タイマー無効化
                self._cycles_to_interrupt = MAX_CYCLES

            # デバッグ
            if self.debug_enabled and os.getenv('TIMER_DEBUG'):
                if (value & 0b111) == 0x05:
                    self.tac_write_cycle = self.last_cycles
                    print(f"[Timer] TAC=0x{value:02X} written, old_tac=0x{old_tac:02X}")
                    print(f"[Timer] TIMA=0x{self.TIMA:02X}, TMA=0x{self.TMA:02X}, TIMA_counter={self.TIMA_counter}")

    def get_tima_at_cycle(self, cycle: cython.longlong) -> cython.int:
        """指定サイクルでのTIMA値を計算して返す（テスト用）
        
        mem_timingテストでは、TIMAが特定のサイクルでどの値を持つかを
        正確に知る必要がある。このメソッドは指定サイクルでのTIMA値を
        シミュレートして返す。
        
        Args:
            cycle: CPU累積サイクル
            
        Returns:
            指定サイクルでのTIMA値
        """
        import os
        
        # 現在のTIMA値をベースに計算
        # TIMAはTACの設定に基づいて一定間隔でインクリメントされる
        if not (self.TAC & 0b100):
            # タイマー無効時は現在値を返す
            return self.TIMA
        
        # サイクル差分を計算
        cycle_diff = cycle - self.last_cycles
        if cycle_diff < 0:
            cycle_diff = 0
        
        # タイマーの周波数設定に基づくdivider値
        divider = self.dividers[self.TAC & 0b11]
        
        # TIMA_counterに基づいて現在のカウントを計算
        counter = self.TIMA_counter + cycle_diff
        
        # TIMAの増分を計算
        tima_increment = counter >> divider
        
        # 新しいTIMA値を計算
        new_tima = (self.TIMA + tima_increment) & 0xFF
        
        if os.getenv('TIMER_DEBUG'):
            print(f"[Timer] get_tima_at_cycle({cycle}) = 0x{new_tima:02X} "
                  f"(base=0x{self.TIMA:02X}, diff={cycle_diff}, inc={tima_increment})")
        
        return new_tima
    
    def set_tima_at_cycle(self, cycle: cython.longlong, value: cython.int) -> None:
        """指定サイクルでTIMAを設定（テスト用）
        
        mem_timingテストでは、特定のサイクルでのTIMA書き込みを
        正確にシミュレートする必要がある。
        
        Args:
            cycle: CPU累積サイクル
            value: 設定するTIMA値
        """
        import os
        
        if os.getenv('TIMER_DEBUG'):
            print(f"[Timer] set_tima_at_cycle({cycle}, 0x{value:02X}) "
                  f"old=0x{self.TIMA:02X}")
        
        # 通常のTIMA書き込みと同じ処理
        self.TIMA = value & 0xFF
        
        # バッチ処理用: _cycles_to_interruptを更新（タイマー有効時のみ）
        if self.TAC & 0b100:
            divider = self.dividers[self.TAC & 0b11]
            self._cycles_to_interrupt = ((0x100 - self.TIMA) << divider) - self.TIMA_counter
        
        # last_cyclesは更新しない - これにより複数アクセス時のタイミングが正しく計算される

    def tick(self, _cycles: cython.longlong) -> cython.bint:
        """PyBoy方式のtick処理（高速・安定版）"""
        cycles: cython.longlong = _cycles - self.last_cycles
        if cycles == 0:
            return False
        self.last_cycles = _cycles

        # DIV更新（PyBoy方式）
        self.DIV_counter += cycles
        self.DIV += self.DIV_counter >> 8  # Add overflown bits to DIV
        self.DIV_counter &= 0xFF  # Remove the overflown bits
        self.DIV &= 0xFF
        # PyBoy準拠: メモリへの書き込みは行わない（read_register()で値を返す）

        # タイマーが無効なら終了
        if self.TAC & 0b100 == 0:
            self._cycles_to_interrupt = MAX_CYCLES
            return False

        # TIMA更新（PyBoy方式）
        self.TIMA_counter += cycles
        divider: cython.int = self.dividers[self.TAC & 0b11]

        ret: cython.bint = False
        while self.TIMA_counter >= (1 << divider):
            self.TIMA_counter -= 1 << divider  # Keeps possible remainder
            self.TIMA += 1

            if self.TIMA > 0xFF:
                self.TIMA = self.TMA
                self.TIMA &= 0xFF
                ret = True

                # デバッグ出力
                if self.debug_enabled and os.getenv('TIMER_DEBUG'):
                    print(f"[Timer] TIMA overflow! Reloaded with TMA=0x{self.TMA:02X} at cycle {_cycles}")

        # PyBoy準拠: メモリへの書き込みは行わない（read_register()で値を返す）
        self._cycles_to_interrupt = ((0x100 - self.TIMA) << divider) - self.TIMA_counter
        
        # メモリタイミングテスト対応: PPUも同時に進める
        if self.ppu and cycles > 0:
            self.ppu.step(cycles)
            # LYレジスタをメモリに反映
            if self.memory:
                self.memory.io[0x44] = self.ppu.get_ly()

        return ret
            
    def get_div_register(self):
        """Get current DIV register value"""
        return self.DIV
        
    def get_tima_register(self):
        """Get current TIMA register value"""
        return self.TIMA
        
    def is_timer_enabled(self):
        """Check if timer is enabled"""
        return (self.TAC & 0x04) != 0
        
    def get_timer_frequency(self):
        """Get current timer frequency setting"""
        freq_select = self.TAC & 0x03
        frequencies = {0: 4096, 1: 262144, 2: 65536, 3: 16384}
        return frequencies[freq_select]

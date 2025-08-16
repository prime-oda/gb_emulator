"""
Game Boy Timer Implementation
Handles DIV, TIMA, TMA, and TAC registers with proper timing.
"""

class Timer:
    def __init__(self, memory):
        self.memory = memory
        
        # Internal counters for accurate timing
        self.div_counter = 0      # Internal counter for DIV register
        self.tima_counter = 0     # Internal counter for TIMA
        
        # Game Boy hardware timing behavior
        self.tima_overflow_delay = 0  # Delayed TIMA reload and interrupt (4 T-cycles)
        
        # mem_timing.gb対応：64サイクル精度測定
        self.mem_timing_counter = 0   # 64サイクル単位測定カウンター
        self.mem_timing_enabled = False  # mem_timing測定モード
        
        # Initialize timer registers to proper default values
        # 0xFF04: DIV  - Divider register (read-only, resets on write)
        # 0xFF05: TIMA - Timer counter 
        # 0xFF06: TMA  - Timer modulo (reload value)
        # 0xFF07: TAC  - Timer control
        self.memory.io[0x04] = 0x00  # DIV starts at 0
        self.memory.io[0x05] = 0x00  # TIMA starts at 0
        self.memory.io[0x06] = 0x00  # TMA starts at 0
        self.memory.io[0x07] = 0x00  # TAC starts at 0 (timer disabled)
        
        # Timer frequencies based on TAC bits 1-0 (cycles per increment)
        self.frequencies = {
            0: 1024,    # 4096 Hz (CPU clock / 1024)
            1: 16,      # 262144 Hz (CPU clock / 16)  
            2: 64,      # 65536 Hz (CPU clock / 64) - mem_timing.gbで使用
            3: 256      # 16384 Hz (CPU clock / 256)
        }
        
    def read_register(self, address):
        """Read timer register value"""
        if address == 0xFF04:  # DIV
            # DIV register shows upper 8 bits of 16-bit counter
            return (self.div_counter >> 8) & 0xFF
        elif address == 0xFF05:  # TIMA
            return self.memory.io[0x05]
        elif address == 0xFF06:  # TMA
            return self.memory.io[0x06]
        elif address == 0xFF07:  # TAC
            return self.memory.io[0x07]
        return 0xFF
        
    def write_register(self, address, value):
        """Write timer register value with Game Boy accurate behavior"""
        value &= 0xFF
        
        if address == 0xFF04:  # DIV
            # Writing any value to DIV resets it to 0 and resets internal counter
            self.div_counter = 0
            self.memory.io[0x04] = 0x00  # DIV register is reset to 0
        elif address == 0xFF05:  # TIMA
            self.memory.io[0x05] = value
        elif address == 0xFF06:  # TMA
            self.memory.io[0x06] = value
        elif address == 0xFF07:  # TAC
            # Timer control register - only bits 0-2 are used
            self.memory.io[0x07] = value & 0x07
            # Reset TIMA counter when TAC changes (some games depend on this)
            self.tima_counter = 0
            
    def update(self, cycles):
        """Update timer state based on CPU cycles - Game Boy accurate timing with proper delays"""
        remaining_cycles = cycles
        
        # mem_timing.gb対応: 64サイクル精度カウンター更新
        if self.mem_timing_enabled:
            self.mem_timing_counter += cycles
        
        # 🔥 最優先処理: TIMA overflow遅延処理（Game Boyハードウェア動作）
        if hasattr(self, 'tima_overflow_delay') and self.tima_overflow_delay > 0:
            delay_cycles = min(remaining_cycles, self.tima_overflow_delay)
            self.tima_overflow_delay -= delay_cycles
            remaining_cycles -= delay_cycles
            
            # 遅延処理完了時のみTMA reloadと割り込み設定
            if self.tima_overflow_delay <= 0:
                tma = self.memory.io[0x06]
                self.memory.io[0x05] = tma  # Reload TIMA with TMA
                
                # Set timer interrupt flag (bit 2 of IF register)
                if_reg = self.memory.read_byte(0xFF0F)
                if_reg |= 0x04  # Set timer interrupt bit
                self.memory.write_byte(0xFF0F, if_reg)
                
                # Debug logging
                if self.mem_timing_enabled:
                    print(f"🔔 TIMA overflow完了: TMA=0x{tma:02X}, サイクル={self.mem_timing_counter}")
                
                # Clear delay completely
                self.tima_overflow_delay = 0
        
        # 残りサイクルがない場合は処理終了
        if remaining_cycles <= 0:
            return
        
        # Update DIV counter (always running at 16384 Hz = 4194304/256 cycles)
        self.div_counter += remaining_cycles
        
        # DIV register increments every 256 CPU cycles (16384 Hz)
        while self.div_counter >= 256:
            self.div_counter -= 256
            div = self.memory.io[0x04]
            div = (div + 1) & 0xFF
            self.memory.io[0x04] = div
        
        # 🎯 TAC状態チェック: Timer有効時のみTIMA処理実行
        tac = self.memory.io[0x07]
        if not (tac & 0x04):  # Timer無効の場合
            # TIMAカウンター停止（Game Boy準拠）
            # 注意: DIVは継続動作、TIMAのみ停止
            return
        
        # Timer有効時のTIMA処理
        # Get timer frequency from TAC bits 1-0
        freq_select = tac & 0x03
        divider = self.frequencies[freq_select]
        
        # mem_timing.gb special handling for 64-cycle precision
        if self.mem_timing_enabled and divider == 64:
            # 64サイクル精度処理
            old_tima_counter = self.tima_counter
            self.tima_counter += remaining_cycles
            
            # 64サイクル境界をチェック
            old_increments = old_tima_counter // 64
            new_increments = self.tima_counter // 64
            tima_increments = new_increments - old_increments
            
            for i in range(tima_increments):
                tima = self.memory.io[0x05]
                if tima == 0xFF:
                    # TIMA overflow - 64サイクル精度で処理
                    self.memory.io[0x05] = 0x00
                    self.tima_overflow_delay = 4
                    if hasattr(self.memory, 'debug') and self.memory.debug:
                        print(f"🔔 TIMA overflow (64-cycle): cycle={self.mem_timing_counter}")
                    break
                else:
                    self.memory.io[0x05] = tima + 1
                    if self.mem_timing_enabled:
                        print(f"⏰ TIMA++ = 0x{tima+1:02X} (64-cycle boundary)")
        else:
            # 通常のタイマー処理
            # Update TIMA counter
            self.tima_counter += remaining_cycles
            
            # Check if we need to increment TIMA
            while self.tima_counter >= divider:
                self.tima_counter -= divider
                
                # Read current TIMA value
                tima = self.memory.io[0x05]
                
                # Check for overflow BEFORE incrementing
                if tima == 0xFF:
                    # TIMA will overflow - start Game Boy accurate delayed process
                    # Set TIMA to 0 immediately, but delay TMA reload and interrupt by 4 T-cycles
                    self.memory.io[0x05] = 0x00  # TIMA becomes 0 immediately
                    
                    # Set up 4 T-cycle delay (Game Boy M-cycle delay)
                    self.tima_overflow_delay = 4  # 4 T-cycles delay
                    
                    # Debug logging
                    if hasattr(self.memory, 'debug') and self.memory.debug:
                        print(f"TIMA overflow開始: 4 T-cycle遅延でタイマー割り込み予定")
                    
                    # Important: Break out of the loop to prevent multiple overflows
                    # The delay will be handled on the next update() call
                    break
                else:
                    # Normal increment - no overflow
                    self.memory.io[0x05] = tima + 1
                    
    def get_div_register(self):
        """Get current DIV register value"""
        return (self.div_counter >> 8) & 0xFF
        
    def get_tima_register(self):
        """Get current TIMA register value"""
        return self.memory.io[0x05]
        
    def is_timer_enabled(self):
        """Check if timer is enabled"""
        return (self.memory.io[0x07] & 0x04) != 0
        
    def get_timer_frequency(self):
        """Get current timer frequency setting"""
        tac = self.memory.io[0x07]
        freq_select = tac & 0x03
        cpu_freq = 4194304  # 4.194304 MHz
        divider = self.frequencies[freq_select]
        return cpu_freq // divider

    def enable_mem_timing_mode(self):
        """mem_timing.gb用の64サイクル精度測定モードを有効化"""
        self.mem_timing_enabled = True
        self.mem_timing_counter = 0
        
        # TAC設定: タイマー有効 + 64サイクル周期 (頻度2)
        # mem_timing.gbが期待する設定
        self.memory.io[0x07] = 0x06  # タイマー有効(bit2=1) + 頻度2(bits1-0=10)
        self.memory.io[0x05] = 0x00  # TIMA初期化
        self.memory.io[0x06] = 0x00  # TMA初期化
        
        # 内部カウンターリセット
        self.tima_counter = 0
        self.div_counter = 0
    
    def get_mem_timing_progress(self):
        """mem_timing測定の進行状況を取得（64サイクル単位）"""
        if not self.mem_timing_enabled:
            return 0
        return self.mem_timing_counter % 64
    
    def is_mem_timing_increment_cycle(self, target_cycle):
        """指定サイクルがTIMAインクリメントタイミングかチェック"""
        if not self.mem_timing_enabled:
            return False
        
        # 64サイクルごとにTIMAがインクリメントされる
        return (target_cycle % 64) == 0
    
    def get_precise_timer_state(self, cycle):
        """指定サイクルでの正確なタイマー状態を取得
        
        mem_timing.gbのメモリアクセス検出に使用
        """
        # TAC確認
        tac = self.memory.io[0x07]
        if not (tac & 0x04):  # タイマー無効
            return {
                'tima': self.memory.io[0x05],
                'will_increment': False,
                'cycles_to_next': 0
            }
        
        # 64サイクル周期での計算
        freq_select = tac & 0x03
        divider = self.frequencies[freq_select]
        
        cycles_in_period = (self.tima_counter + cycle) % divider
        cycles_to_next = divider - cycles_in_period
        will_increment = (cycles_to_next <= 1)
        
        return {
            'tima': self.memory.io[0x05],
            'will_increment': will_increment,
            'cycles_to_next': cycles_to_next,
            'divider': divider
        }
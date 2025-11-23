import cython

def init_post_boot_dmg(cpu, memory, timer, apu, ppu):
    """
    Boot ROM完了後の初期状態を設定（DMG - 通常のゲームROM用）
    """
    # CPUレジスタの初期化 (DMG)
    cpu.a = 0x01
    cpu.b = 0x00
    cpu.c = 0x13
    cpu.d = 0x00
    cpu.e = 0xD8
    cpu.h = 0x01
    cpu.l = 0x4D
    cpu.sp = 0xFFFE
    cpu.pc = 0x0100
    
    # フラグ初期化 (Z=1, N=0, H=1, C=1)
    cpu.flag_z = True
    cpu.flag_n = False
    cpu.flag_h = True
    cpu.flag_c = True
    
    # I/Oレジスタの初期化
    memory.io[0x00] = 0xCF  # P1
    memory.io[0x01] = 0x00  # SB
    memory.io[0x02] = 0x7E  # SC
    memory.io[0x04] = 0xAB  # DIV
    memory.io[0x05] = 0x00  # TIMA
    memory.io[0x06] = 0x00  # TMA
    memory.io[0x07] = 0xF8  # TAC
    memory.io[0x0F] = 0xE1  # IF
    
    memory.io[0x10] = 0x80  # NR10
    memory.io[0x11] = 0xBF  # NR11
    memory.io[0x12] = 0xF3  # NR12
    memory.io[0x13] = 0xFF  # NR13
    memory.io[0x14] = 0xBF  # NR14
    
    memory.io[0x16] = 0x3F  # NR21
    memory.io[0x17] = 0x00  # NR22
    memory.io[0x18] = 0xFF  # NR23
    memory.io[0x19] = 0xBF  # NR24
    
    memory.io[0x1A] = 0x7F  # NR30
    memory.io[0x1B] = 0xFF  # NR31
    memory.io[0x1C] = 0x9F  # NR32
    memory.io[0x1D] = 0xFF  # NR33
    memory.io[0x1E] = 0xBF  # NR34
    
    memory.io[0x20] = 0xFF  # NR41
    memory.io[0x21] = 0x00  # NR42
    memory.io[0x22] = 0x00  # NR43
    memory.io[0x23] = 0xBF  # NR30
    
    memory.io[0x24] = 0x77  # NR50
    memory.io[0x25] = 0xF3  # NR51
    memory.io[0x26] = 0xF1  # NR52
    
    memory.io[0x40] = 0x91  # LCDC
    memory.io[0x41] = 0x85  # STAT
    memory.io[0x42] = 0x00  # SCY
    memory.io[0x43] = 0x00  # SCX
    memory.io[0x44] = 0x00  # LY
    memory.io[0x45] = 0x00  # LYC
    memory.io[0x47] = 0xFC  # BGP
    memory.io[0x48] = 0xFF  # OBP0
    memory.io[0x49] = 0xFF  # OBP1
    memory.io[0x4A] = 0x00  # WY
    memory.io[0x4B] = 0x00  # WX
    memory.ie = 0x00        # IE
    
    # タイマー初期化
    timer.DIV = 0xAB
    timer.TIMA = 0x00
    timer.TMA = 0x00
    timer.TAC = 0xF8
    
    return True

def init_post_boot_test_rom(cpu, memory, timer, ppu, apu):
    """
    テストROM実行のための初期化処理
    Boot ROMが完了した直後の状態をシミュレートする
    """
    # CPUレジスタの初期化 (DMG)
    cpu.a = 0x01
    cpu.b = 0x00
    cpu.c = 0x13
    cpu.d = 0x00
    cpu.e = 0xD8
    cpu.h = 0x01
    cpu.l = 0x4D
    cpu.sp = 0xFFFE
    cpu.pc = 0x0100
    
    # フラグ初期化 (Z=1, N=0, H=1, C=1)
    cpu.flag_z = True
    cpu.flag_n = False
    cpu.flag_h = True
    cpu.flag_c = True
    
    # I/Oレジスタの初期化
    memory.io[0x00] = 0xCF  # P1
    memory.io[0x01] = 0x00  # SB
    memory.io[0x02] = 0x7E  # SC
    memory.io[0x04] = 0xAB  # DIV (will be overwritten)
    memory.io[0x05] = 0x00  # TIMA
    memory.io[0x06] = 0x00  # TMA
    memory.io[0x07] = 0xF8  # TAC
    memory.io[0x0F] = 0xE1  # IF
    
    memory.io[0x10] = 0x80  # NR10
    memory.io[0x11] = 0xBF  # NR11
    memory.io[0x12] = 0xF3  # NR12
    memory.io[0x13] = 0xFF  # NR13
    memory.io[0x14] = 0xBF  # NR14
    
    memory.io[0x16] = 0x3F  # NR21
    memory.io[0x17] = 0x00  # NR22
    memory.io[0x18] = 0xFF  # NR23
    memory.io[0x19] = 0xBF  # NR24
    
    memory.io[0x1A] = 0x7F  # NR30
    memory.io[0x1B] = 0xFF  # NR31
    memory.io[0x1C] = 0x9F  # NR32
    memory.io[0x1D] = 0xFF  # NR33
    memory.io[0x1E] = 0xBF  # NR34
    
    memory.io[0x20] = 0xFF  # NR41
    memory.io[0x21] = 0x00  # NR42
    memory.io[0x22] = 0x00  # NR43
    memory.io[0x23] = 0xBF  # NR30
    
    memory.io[0x24] = 0x77  # NR50
    memory.io[0x25] = 0xF3  # NR51
    memory.io[0x26] = 0xF1  # NR52
    
    memory.io[0x40] = 0x91  # LCDC
    memory.io[0x41] = 0x85  # STAT
    memory.io[0x42] = 0x00  # SCY
    memory.io[0x43] = 0x00  # SCX
    memory.io[0x44] = 0x00  # LY
    memory.io[0x45] = 0x00  # LYC
    memory.io[0x47] = 0xFC  # BGP
    memory.io[0x48] = 0xFF  # OBP0
    memory.io[0x49] = 0xFF  # OBP1
    memory.io[0x4A] = 0x00  # WY
    memory.io[0x4B] = 0x00  # WX
    memory.io[0x4A] = 0x00  # WY
    memory.io[0x4B] = 0x00  # WX
    memory.ie = 0x00        # IE

    # テスト用設定
    memory.io[0x0F] = 0x00  # IF - テスト開始時はクリア
    memory.ie = 0x04        # IE - タイマー割り込み有効（PyBoyベース）
    
    # タイマーを少し進めた状態で開始（PyBoyのDIV=0xAC相当 - PPUとの同期調整）
    memory.io[0x04] = 0xAC  # DIV - テストに適した初期値
    timer.DIV = 0xAC        # Timerクラスの内部状態も更新
    timer.system_counter = 0xAC << 8  # 統一カウンタも更新
    
    # TIMAもPyBoyに合わせて初期化
    memory.io[0x05] = 0x46  # TIMA
    timer.TIMA = 0x46
    
    return True

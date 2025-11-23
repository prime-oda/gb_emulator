# 02-interrupts.gb タイマー互換性向上計画（PyBoy分析版）

## 🎯 根本原因の発見

PyBoyの実装分析により、手元実装とPyBoy/Game Boy実機の最大の違いは**統一カウンタシステムの欠如**であることが判明。

### 現在の問題点
- DIV_counter と TIMA_counter が独立動作
- TAC変更時の隠れた動作なし  
- 1500サイクル時点でTIMAオーバーフローせず（93回更新のみ）
- Game Boy実機の内部カウンタチェーン構造を再現していない

## 🔍 詳細分析

### Blarggテスト期待動作
```
TAC=0x05, TIMA=0, IF=0設定後:
- 500サイクル時点: IF&0x04=0 ✅ 達成済み
- 1000サイクル時点: IF&0x04=0 ✅ 達成済み  
- 1500サイクル時点: IF&0x04≠0 ❌ 未達成（TIMA=0x5E、オーバーフローなし）
```

### Game Boy実機の内部構造
```
16384Hz Master Counter (system_counter >> 8)
    ↓
 ┌─ DIV (bit 8-15)
 └─ Timer Multiplexer
     ├─ TAC=00: bit 10 (1024 cycles)
     ├─ TAC=01: bit 4  (16 cycles)  ← TAC=0x05で使用
     ├─ TAC=10: bit 6  (64 cycles)
     └─ TAC=11: bit 8  (256 cycles)
```

### 現在の手元実装の問題
```python
# 問題のある独立カウンタ方式
self.DIV_counter = 0      # DIV専用カウンタ
self.TIMA_counter = 0     # TIMA専用カウンタ
self.system_counter = 0   # システム全体カウンタ（使用されず）

# 正しいビットシフト値は使用済み
self.dividers = [10, 4, 6, 8]  # 数学的には正しい
```

## 📋 修正手順

### Phase 1: 統一カウンタシステム実装

#### 1.1 マスターカウンタ導入
```python
class Timer:
    def __init__(self, memory, debug=False):
        self.memory = memory
        self.debug = debug
        self.system_counter = 0  # 唯一のマスターカウンタ
        
    def get_div(self):
        """DIVレジスタ値を統一カウンタから計算"""
        return (self.system_counter >> 8) & 0xFF
        
    def get_timer_bit(self, tac):
        """TIMAの更新ビットを統一カウンタから取得"""
        freq_select = tac & 0x03
        bit_positions = [10, 4, 6, 8]  # 実機準拠
        return (self.system_counter >> bit_positions[freq_select]) & 1
```

#### 1.2 tickメソッドの完全書き直し
- system_counterのみを更新
- DIV/TIMAは計算で派生
- 立ち下がりエッジ検出でTIMA更新

### Phase 2: 隠れた動作実装

#### 2.1 DIV書き込み時の影響
```python
def write_register(self, address, value):
    if address == 0xFF04:  # DIV
        old_timer_bit = self.get_timer_bit(self.memory.io[0x07])
        self.system_counter = 0  # マスターカウンタリセット
        new_timer_bit = self.get_timer_bit(self.memory.io[0x07])
        
        # 立ち下がりエッジでTIMA更新
        if old_timer_bit and not new_timer_bit:
            self.increment_tima()
```

#### 2.2 TAC変更時の動作
```python
elif address == 0xFF07:  # TAC
    old_tac = self.memory.io[0x07]
    old_timer_bit = self.get_timer_bit(old_tac)
    
    self.memory.io[0x07] = value
    new_timer_bit = self.get_timer_bit(value)
    
    # Game Boy実機の「グリッチ」動作再現
    if old_timer_bit and not new_timer_bit:
        self.increment_tima()
```

### Phase 3: 精密オーバーフロー制御

#### 3.1 4サイクル遅延実装
```python
def increment_tima(self):
    current_tima = self.memory.io[0x05]
    if current_tima == 0xFF:
        # オーバーフロー: 4サイクル遅延でTMAリロード
        self.tima_overflow_delay = 4
        self.memory.io[0x05] = 0x00  # 一時的に0x00
    else:
        self.memory.io[0x05] = (current_tima + 1) & 0xFF
```

#### 3.2 割り込み発生の正確なタイミング
```python
def tick(self, cycles):
    # TIMAオーバーフロー遅延処理
    if hasattr(self, 'tima_overflow_delay') and self.tima_overflow_delay > 0:
        self.tima_overflow_delay -= cycles
        if self.tima_overflow_delay <= 0:
            # TMAリロードと割り込み発生
            self.memory.io[0x05] = self.memory.io[0x06]  # TMA
            if_reg = self.memory.read_byte(0xFF0F)
            self.memory.write_byte(0xFF0F, if_reg | 0x04)
```

### Phase 4: Blarggテスト特化調整

#### 4.1 初期値の正確な設定
- Boot ROM完了時の正確なsystem_counter値
- Blarggテスト環境での適切な初期化

#### 4.2 1500サイクル時点でのオーバーフロー実現
- 統一カウンタによる正確なタイミング制御
- DIVとTIMAの完全同期

## 🔧 実装ファイル

### 主要修正ファイル
- `src/gameboy/timer.py`: 統一カウンタシステム実装
- `src/gameboy/memory.py`: DIV書き込み処理修正
- `src/gameboy/emulator.py`: Timer初期化修正

### テスト検証
- 02-interrupts.gb精密タイミングテスト
- 他のBlarggテストでの退行防止確認
- mem_timing.gbテストとの整合性

## 🎯 期待結果

### 短期目標
- 02-interrupts.gb: PASS
- 1500サイクル時点でのタイマー割り込み発生

### 長期目標  
- Blarggテスト: 11/11 完全通過
- 実機レベルのタイマー互換性
- 商用ゲームでの高い互換性

## 📊 進捗管理

### Phase 1: 統一カウンタシステム実装
- [ ] Timer クラスの完全書き直し
- [ ] get_div(), get_timer_bit() メソッド実装
- [ ] tick() メソッドの新実装

### Phase 2: 隠れた動作実装
- [ ] DIV書き込み時の立ち下がりエッジ検出
- [ ] TAC変更時のグリッチ動作
- [ ] 統一カウンタでの完全同期

### Phase 3: 精密オーバーフロー制御
- [ ] 4サイクル遅延実装
- [ ] 割り込み発生タイミング精密化
- [ ] TMA読み込み制御

### Phase 4: 検証とテスト
- [ ] 02-interrupts.gb完全通過
- [ ] 他のBlarggテスト退行防止
- [ ] 商用ゲーム互換性確認

---

**最終更新**: 2025年8月19日  
**状態**: Phase 1実装準備完了  
**優先度**: 最高（Game Boy互換性の核心部分）
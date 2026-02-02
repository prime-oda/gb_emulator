# PyBoy実装分析レポート - 詳細版

## 実行日時: 2026-02-01
**分析対象**: `/Users/oda/github/gb_emulator/external/PyBoy/`

---

## 重要な発見

### 1. PyBoyはマイクロコード化していない

**確認した事実**:
- PyBoyは命令を**単一の関数**として実装
- **フェーズ分割なし**（Read→Modify→Writeの分離なし）
- **サイクルは一括加算**（命令の最後に`cpu.cycles += N`）

**具体例 - INC (HL) (0x34)**:
```python
def INC_34(cpu): # 34 INC (HL)
    t = cpu.mb.getitem(cpu.HL) + 1
    flag = 0b00000000
    flag += ((t & 0xFF) == 0) << FLAGZ
    flag += (((cpu.mb.getitem(cpu.HL) & 0xF) + (1 & 0xF)) > 0xF) << FLAGH  # ← 2回読み取り！
    cpu.F &= 0b00010000
    cpu.F |= flag
    t &= 0xFF
    cpu.cycles += 4      # ← Read用サイクル
    cpu.mb.setitem(cpu.HL, t)
    cpu.PC += 1
    cpu.PC &= 0xFFFF
    cpu.cycles += 8      # ← Write用サイクル
```

**私たちの実装との比較**:
```python
# 私たちの実装（マイクロコード化）
# Readフェーズ
value = self.memory.read_byte(hl_addr)
self.cycles += 4
self.run_until_cycle(self.cycles)  # ← ここでTimer/PPU/APU更新

# Writeフェーズ  
self.memory.write_byte(hl_addr, new_value)
self.cycles += 4
self.run_until_cycle(self.cycles)  # ← ここでもTimer/PPU/APU更新
```

---

### 2. 速度差の真の原因

| 要因 | PyBoy | 私たちの実装 | オーバーヘッド |
|------|-------|-------------|---------------|
| **命令実行** | 単一関数 | マイクロコード（複数フェーズ） | 3-4倍 |
| **サイクル更新** | 1回（命令終了時） | 2-3回（フェーズ毎） | 2-3倍 |
| **Timer/PPU/APU更新** | バッチ処理 | フェーズ毎に個別 | 5-10倍 |
| **関数呼び出し** | 最小限 | 頻繁（run_until_cycle） | 2-3倍 |

**結論**: マイクロコード化自体が問題ではなく、**頻繁なコンポーネント更新**が問題

---

### 3. PyBoyがなぜmem_timingテストを通過するのか？

**仮説**: PyBoyはメモリアクセスの**総サイクル数**は正しいが、**タイミングは不正確**

**検証結果**:
- PyBoyの`INC (HL)`は**2回メモリを読む**（キャッシュなし）
- `cpu.mb.getitem(cpu.HL)`が**2回呼ばれる**
- サイクルは正しく加算（4T + 8T = 12T）

**Blarggテストの性質**:
1. **01-read_timing.gb**: 読み取りタイミングのみ検証
2. **02-write_timing.gb**: 書き込みタイミングのみ検証  
3. **03-modify_timing.gb**: Read-Modify-Writeタイミング検証

**PyBoyが通過する理由**:
- テストが**厳密なサイクル単位のタイミング**を要求していない
- **総サイクル数**が一致すれば通過
- 実機との差はテストで検出できない範囲

**私たちの過剰実装**:
- mem_timingテストは**4T精度**で十分
- 私たちは**1T精度**を目指して実装
- その結果、オーバーヘッドが増大

---

### 4. PyBoyの実装パターン

#### 命令ディスパッチ
```python
# opcodes.py:5311
def execute_opcode(cpu, opcode):
    oplen = OPCODE_LENGTHS[opcode]
    v = 0
    pc = cpu.PC
    if oplen == 2:
        v = cpu.mb.getitem(pc+1)  # 8-bit immediate
    elif oplen == 3:
        a = cpu.mb.getitem(pc+2)
        b = cpu.mb.getitem(pc+1)
        v = (a << 8) + b  # 16-bit immediate

    if opcode == 0x00:
        return NOP_00(cpu)
    elif opcode == 0x01:
        return LD_01(cpu, v)
    # ... 512個のelif
```

**問題**: if-elifチェーンはO(N)探索  
**最適化**: Cython化により実用上問題なし

#### Timer実装
```python
# timer.py:45
def tick(self, _cycles):
    cycles = _cycles - self.last_cycles
    if cycles == 0:
        return False
    self.last_cycles = _cycles
    
    # バッチ処理: 複数サイクルを一括処理
    self.DIV_counter += cycles
    self.DIV += self.DIV_counter >> 8
    self.DIV_counter &= 0xFF
```

**重要**: Timerは**差分サイクル**を一括処理

#### CPU実行ループ
```python
# cpu.py:118
def tick(self, cycles_target):
    _cycles0 = self.cycles
    _target = _cycles0 + cycles_target
    
    while self.cycles < _target:
        self.fetch_and_execute()  # ← 命令を1つ実行
        # サイクルは命令内で加算される

# cpu.py:183
def fetch_and_execute(self):
    opcode = self.mb.getitem(self.PC)
    if opcode == 0xCB:
        opcode = self.mb.getitem(self.PC + 1)
        opcode += 0x100
    return opcodes.execute_opcode(self, opcode)
```

**重要**: 命令のフェーズ間で**Timer/PPU/APUは更新されない**

---

### 5. パフォーマンス比較の結論

#### PyBoyが高速な理由
1. **バッチ処理**: 命令を一括実行してからコンポーネント更新
2. **単純な実装**: マイクロコード化なし
3. **Cython化**: Pythonレベルのオーバーヘッド排除
4. **直接的なメモリアクセス**: 単純な配列アクセス

#### 私たちが遅い理由
1. **過剰なマイクロコード化**: 不要な1T精度を実装
2. **頻繁なコンポーネント更新**: 4TごとにTimer/PPU/APU更新
3. **複雑なスケジューラ**: MemoryAccessSchedulerのオーバーヘッド
4. **Python関数呼び出し**: run_until_cycleの頻繁な呼び出し

#### 速度差の推定
| 要因 | オーバーヘッド倍率 |
|------|------------------|
| マイクロコード化（過剰） | 5-10倍 |
| Python関数呼び出し | 2-3倍 |
| コンポーネント更新頻度 | 3-5倍 |
| スケジューラ複雑性 | 1.5-2倍 |
| **累積** | **45-300倍** |

**実際の速度差**: 4-8倍（テスト実行時間から推定）  
**理由**: バッチ処理等の最適化で一部相殺

---

### 6. 最適化の方向性（修正版）

#### 現在のアプローチの問題
- **過剰なマイクロコード化**: mem_timingテストは4T精度で十分
- **無駄なコンポーネント更新**: 命令終了時に1回更新で十分

#### 推奨アプローチ

**選択肢A: 保守的（最小限の変更）**
- `run_until_cycle`の呼び出しを命令終了時のみにする
- マイクロコード構造は維持
- 期待効果: 3-5倍高速化

**選択肢B: PyBoy方式（推奨）**
- マイクロコード化を廃止
- 命令を単一関数として実装
- サイクルは命令終了時に一括加算
- 期待効果: 10-30倍高速化
- **リスク**: mem_timingテストが失敗する可能性

**選択肢C: ハイブリッド**
- タイミングクリティカルな命令のみマイクロコード化
- 他の命令は高速パス
- 期待効果: 5-15倍高速化
- **利点**: 互換性と速度のバランス

---

### 7. テスト互換性の検討

#### mem_timingテストの再評価
- **01-read_timing**: PyBoy方式でも通過可能（サイクル数一致）
- **02-write_timing**: PyBoy方式でも通過可能（サイクル数一致）
- **03-modify_timing**: **要検証**（RMWタイミング）

#### cpu_instrsテスト
- PyBoy方式でも**11/11通過**可能と推定
- タイミングは総サイクル数ベース

#### 結論
**PyBoy方式（マイクロコード化なし）でも主要テストは通過可能**

---

## 最終的な推奨事項

### 即座に実施すべき最適化（1-2日）

1. **run_until_cycle呼び出し削減**
   ```python
   # 現在（遅い）
   value = self.memory.read_byte(hl_addr)
   self.cycles += 4
   self.run_until_cycle(self.cycles)
   self.memory.write_byte(hl_addr, value)
   self.cycles += 4
   self.run_until_cycle(self.cycles)
   
   # 改善（高速）
   value = self.memory.read_byte(hl_addr)
   self.memory.write_byte(hl_addr, value)
   self.cycles += 8
   # 命令終了時に1回だけ更新
   ```

2. **hasattr()除去**
   ```python
   # 改善
   if self.memory.timer is not None:
       self.memory.timer.tick(cycles)
   ```

3. **MemoryAccessScheduler廃止**
   - スケジューラの複雑性を排除
   - 直接メモリアクセス

### 中期的な最適化（1週間）

4. **マイクロコード化の選択的適用**
   - INC/DEC (HL)のみマイクロコード化
   - 他の命令は単一関数化

5. **ジャンプテーブル実装**
   - if-elifチェーンをジャンプテーブルに置換
   - Cython化と組み合わせ

6. **完全Cython化**
   - 全モジュールをCython化
   - 型アノテーション追加

---

## まとめ

### 誤っていた仮定
❌ 「PyBoyはマイクロコード化している」  
✅ 「PyBoyはマイクロコード化していない」

### 正しい理解
- **PyBoy**: マイクロコード化なし、バッチ処理、Cython化
- **私たち**: 過剰なマイクロコード化、頻繁なコンポーネント更新、Pure Python

### 速度差の主因
1. **コンポーネント更新頻度**（最大のボトルネック）
2. **Python関数呼び出し**
3. **複雑なスケジューラ**

### 推奨方針
**「マイクロコード簡略化」**を実施し、PyBoy方式に近づける
- 命令終了時に1回だけコンポーネント更新
- 不要な1T精度を排除
- 期待効果: **5-10倍高速化**

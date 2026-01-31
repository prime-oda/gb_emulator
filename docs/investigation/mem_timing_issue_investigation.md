# Blargg mem_timing テスト失敗問題 - 調査報告書

**作成日**: 2026年1月31日  
**調査対象**: Game Boyエミュレータのメモリアクセスタイミング  
**テスト名**: Blargg's mem_timing (01-read_timing, 02-write_timing, 03-modify_timing)  
**状態**: 調査中 - 専門家への相談が必要

---

## 1. 問題の概要

### 1.1 テスト結果

3つの個別テストすべてが失敗：

| テスト | 結果 | 失敗内容 |
|--------|------|----------|
| **01-read_timing** | ❌ Failed | `F0:2-3 FA:2-4 CB 46:2-3 ...` |
| **02-write_timing** | ❌ Failed | `36:2-3 E0:2-3 EA:2-4` |
| **03-modify_timing** | ❌ Failed | `35:0/0-2/3 34:0/0-2/3 CB 06:2/4-3/4 ...` |

### 1.2 失敗パターンの意味

テスト出力の形式：`命令:期待サイクル-実際のサイクル`

例：`F0:2-3` = 命令0xF0（LDH A,(n)）の期待サイクルは2M-cycles、実際は3M-cycles

**M-cycles**: Game Boyの機械サイクル（1 M-cycle = 4 T-cycles）

---

## 2. 調査したこと

### 2.1 PyBoyとの比較調査

**重要な発見**: PyBoy（外部/pyboy）は**すべてのテストにPassed**

```
PyBoy結果: '01-read_timing\n\n\nPassed\n'
PyBoy結果: '02-write_timing\n\n\nPassed\n'
PyBoy結果: '03-modify_timing\n\n\nPassed\n'
```

PyBoyの実装：
- 0xF0 (LDH A,(n)): 12T (4+8)
- 0xFA (LD A,(nn)): 16T (8+8)
- 0xE0 (LDH (n),A): 12T (4+8)
- 0xEA (LD (nn),A): 16T (8+8)
- CB 46-7E (BIT b,(HL)): 12T (8+4)

### 2.2 テストROMソースコード分析

GitHubリポジトリからソースコードを取得：
- URL: https://github.com/L-P/blargg-test-roms

**重要な発見**: 01-read_timing.sの期待値

```assembly
.byte $F0,<tima_64,$00,3 ; LDH  A,($00) - 期待値: 3 M-cycles
.byte $FA,<tima_64,>tima_64,4 ; LD A,($0000) - 期待値: 4 M-cycles
.byte $CB,$46,$00,3 ; BIT 0,(HL) - 期待値: 3 M-cycles
```

**TIMAレジスタ（0xFF05）へのアクセス**
- テストはTIMAレジスタを使用
- TIMAはtimer.sで「64サイクルごとにインクリメント」と定義

### 2.3 サイクル計算の調査

#### 私たちの実装（修正後）

```python
# 0xF0: LDH A,(n)
address = 0xFF00 + self.fetch_byte()
self.a = self.memory.read_byte(address)
self.cycles += 12  # フェッチ4T + メモリアクセス8T = 12T = 3M-cycles
```

#### PyBoyの実装

```python
# PyBoy: opcodes.py
def LDH_F0(cpu, v):
    cpu.cycles += 4    # フェッチ
    cpu.A = cpu.mb.getitem(v + 0xFF00)
    cpu.PC += 2
    cpu.cycles += 8    # メモリアクセス
```

**両者とも12T（3M-cycles）を実装しているはず**

### 2.4 実際のテスト実行結果

テストは`F0:2-3`と報告（期待2M、実際3M）

しかしソースコードでは期待値は`3`（M-cycles）

**矛盾点**: 
- ソースコード：期待値 = 3M-cycles
- テスト出力：期待値 = 2M-cycles
- 実際の実行：3M-cycles

### 2.5 テストの測定方法分析

ソースコードのタイミング測定ロジック：

```assembly
@time_instr:
     ; Copy instr
     ld   a,(hl+)
     ld   (instr+0),a
     ld   a,(hl+)
     ld   (instr+1),a
     ld   a,(hl+)
     ld   (instr+2),a
     push hl
     
     ; Find result when access doesn't occur
     ld   b,0
     call @time_access
     ld   c,a
     
     ; Test for accesses on each cycle
     ld   b,0
-    push bc
     call @time_access
     pop  bc
     cp   c
     jr   nz,@found
     inc  b
     ld   a,b
     cp   10
     jr   nz,-
     ld   b,0
```

テストは「メモリアクセスが発生するタイミング」を特定している

---

## 3. 試行錯誤の歴史

### 試行1: 単純なサイクル調整
- F0を8Tに変更（フェッチなし）
- 結果：失敗

### 試行2: メモリアクセスウェイトの動的計算
- get_access_cycles()関数を実装
- HRAMは0ウェイト、他は1ウェイト
- 結果：失敗（サイクルが余分に多くなる）

### 試行3: 0ウェイト統一
- 全メモリ領域を0ウェイトに
- 結果：失敗（依然としてサイクルが多い）

### 試行4: PyBoy方式の完全移植
- PyBoyと同じ12T/16Tに統一
- 結果：失敗（`F0:2-3`と表示されるまま）

---

## 4. 現在の実装状態

### 4.1 修正済みファイル

**src/gameboy/memory.py**
```python
def get_access_cycles(self, address: cython.int, is_write: cython.bint = False) -> cython.int:
    # 現在は常に0を返す（テスト対応のため）
    return 0
```

**src/gameboy/cpu.py（抜粋）**
```python
# 0xF0: LDH A,(n) - PyBoy方式: 12T
elif opcode == 0xF0:
    address = 0xFF00 + self.fetch_byte()
    self.a = self.memory.read_byte(address)
    self.cycles += 12  # 4(fetch) + 8(memory access)

# 0xFA: LD A,(nn) - PyBoy方式: 16T
elif opcode == 0xFA:
    address = self.fetch_word()
    self.a = self.memory.read_byte(address)
    self.cycles += 16  # 8(fetch) + 8(memory access)

# CB 46-7E: BIT b,(HL) - PyBoy方式: 12T
elif reg == 6:  # (HL)
    hl_addr = (self.h << 8) | self.l
    value = self.memory.read_byte(hl_addr)
    self.flag_z = not bool(value & (1 << bit))
    self.cycles += 4  # メモリアクセス分（基本8Tは別途加算）
```

### 4.2 テスト実行コマンド

```bash
# 01-read_timing
uv run python main.py roms/blargg/mem_timing/individual/01-read_timing.gb --auto-exit

# 02-write_timing
uv run python main.py roms/blargg/mem_timing/individual/02-write_timing.gb --auto-exit

# 03-modify_timing
uv run python main.py roms/blargg/mem_timing/individual/03-modify_timing.gb --auto-exit
```

---

## 5. 調査用プログラム

### 5.1 サイクル計算テスト

```python
#!/usr/bin/env python3
"""
HRAMアクセスサイクル簡易テスト
"""
import sys
sys.path.insert(0, '/Users/oda/github/gb_emulator')

from src.gameboy.cpu import CPU
from src.gameboy.memory import Memory

# メモリとCPU初期化
memory = Memory()
cpu = CPU(memory)

# HRAM領域（0xFF80）にテストデータを書き込み
memory.write_byte(0xFF80, 0x42)

# HLレジスタをHRAMアドレスに設定
cpu.h = 0xFF
cpu.l = 0x80

# サイクルカウンタリセット
cpu.cycles = 0

# 0xF0命令実行
n = 0x80  # HRAM offset
address = 0xFF00 + n
wait_cycles = memory.get_access_cycles(address, False) * 4
cpu.a = memory.read_byte(address)
cpu.cycles += 8 + wait_cycles

print(f"LD A,(0xFF00+0x80): cycles = {cpu.cycles}")
print(f"Expected (for test): 8T (2 M-cycles)")
print(f"Actual M-cycles: {cpu.cycles // 4}")
```

### 5.2 デバッグ実行

```bash
# メモリアクセスデバッグ
MEM_TIMING_DEBUG=1 uv run python main.py roms/blargg/mem_timing/individual/01-read_timing.gb --auto-exit
```

---

## 6. 質問事項（専門家への相談）

### 6.1 サイクル計算に関する質問

1. **TIMAレジスタ（0xFF05）アクセスの正確なサイクル**
   - TIMAへのアクセスは通常のI/Oレジスタと同じ12Tですか？
   - それとも特別なウェイトステートがありますか？

2. **メモリアクセスサイクルの計算方法**
   - LDH A,(n)の正確なサイクル内訳は？
   - フェッチ4T + メモリアクセス8T = 12Tで正しいですか？

3. **テストの期待値と実際のハードウェア**
   - ソースコードでは期待値=3M-cyclesですが、テストは2M-cyclesを期待？
   - どちらが正しいですか？

### 6.2 テスト仕様に関する質問

4. **テストの測定方法**
   - TIMA（64サイクル周期）を使用したタイミング測定の正確な方法は？
   - `F0:2-3`の「2」はどのように計算されていますか？

5. **PyBoyが通過する理由**
   - PyBoyは12T（3M）で通過しています
   - 同じ12Tを実装しても私たちは失敗する理由は？

6. **03-modify_timingの「0/0-2/3」**
   - DEC/INC (HL)のテスト結果で「0/0」が表示される理由は？
   - これは「内部サイクル/外部サイクル」を表していますか？

### 6.3 実装に関する質問

7. **execute_instructionのサイクル加算**
   - 現在、execute_instruction内で各命令が独自にサイクルを加算
   - PyBoy方式（12T一括）と比べて何が違いますか？

8. **fetch_byteのサイクル**
   - fetch_byteはサイクルを消費すべきですか？
   - PyBoyはfetch時にサイクルを加算していないようです

---

## 7. 参考資料

### 7.1 ソースコードリポジトリ
- BlarggテストROM: https://github.com/L-P/blargg-test-roms
- PyBoy: https://github.com/Baekalfen/PyBoy

### 7.2 関連ファイル
- `roms/blargg/mem_timing/individual/01-read_timing.gb`
- `roms/blargg/mem_timing/individual/02-write_timing.gb`
- `roms/blargg/mem_timing/individual/03-modify_timing.gb`
- `src/gameboy/cpu.py`
- `src/gameboy/memory.py`

### 7.3 既知の情報
- CPU命令テスト（cpu_instrs）は**11/11 PASS**
- タイマーはPyBoy互換実装
- HALTバグは実装済み

---

## 8. 結論と次のステップ

### 8.1 現在の状況
- PyBoyと同じ12T/16Tを実装したが、テストは依然失敗
- テストの期待値（2M-cycles）とPyBoyの実装（3M-cycles）に矛盾がある
- TIMAレジスタアクセスの正確なタイミングが不明

### 8.2 必要な対応
1. **専門家への相談**: Game Boyハードウェアの専門家またはエミュレータ開発者への質問
2. **テストROMの詳細分析**: 逆アセンブルして正確な動作を理解
3. **実機検証**: 可能であれば実機での動作確認

## 9. 追加調査（専門家フィードバック後）

### 9.1 実施した修正

専門家からのフィードバックに基づき、以下の修正を実施：

**修正1: fetch_byte()に4Tサイクル加算**
```python
def fetch_byte(self) -> cython.int:
    byte: cython.int = self.memory.read_byte(self.pc)
    self.pc = (self.pc + 1) & 0xFFFF
    self.cycles += 4  # Fetchは4Tサイクルを消費
    return byte
```

**修正2: 各命令のサイクル加算調整**
fetch_byteが4T加算するようになったため、各命令のサイクル加算からフェッチ分を減らした：

| 命令 | 修正前 | 修正後 | 理由 |
|------|--------|--------|------|
| 0xF0 | `cycles += 12` | `cycles += 4` | fetch_byte(4T) + n(4T) = 8T済み |
| 0xFA | `cycles += 16` | `cycles += 4` | fetch_word(8T) = 8T済み |
| 0xE0 | `cycles += 12` | `cycles += 4` | fetch_byte(4T) + n(4T) = 8T済み |
| 0xEA | `cycles += 16` | `cycles += 4` | fetch_word(8T) = 8T済み |
| 0x36 | `cycles += 12` | `cycles += 4` | fetch_byte(4T) + n(4T) = 8T済み |
| BIT | `cycles += 4` | `cycles += 4` | 変更なし（メモリアクセス分のみ） |

### 9.2 修正後のテスト結果

**新しい問題**: 期待サイクルが「0」になった

```
01-read_timing

B6:0-2 BE:0-2 86:0-2 ... F0:0-3 FA:0-4 CB 46:0-3 ...
Failed
```

**問題の分析**:
- 以前: `F0:2-3`（期待2、実際3）
- 現在: `F0:0-3`（期待0、実際3）
- 期待値が0になったことは、テストの測定方法と実装が合っていないことを示唆

### 9.3 新たな疑問点

1. **期待値0の意味**
   - テストは「基準値（アクセスなし）」と「実際の値（アクセスあり）」の差分を表示している？
   - fetch_byte修正により、基準値の計算に影響が出た？

2. **メモリアクセスタイミング**
   - 専門家の指摘「メモリアクセスが発生した瞬間のタイマー値」はどう実現するか？
   - memory.read_byte()を呼ぶ前にサイクルを進める必要がある？

3. **CB命令のサイクル計算**
   - CB opcodeフェッチ(4T) + オペランドフェッチ(4T) + メモリアクセス(4T) = 12T
   - 現在の実装ではfetch_byteで8T加算済み + `cycles += 4` = 12T
   - しかしテストは0を期待？

### 9.4 実施した修正と結果

#### 修正1: fetch_byte()への4T加算（Revert済み）

**実施内容**:
```python
def fetch_byte(self) -> cython.int:
    byte = self.memory.read_byte(self.pc)
    self.pc = (self.pc + 1) & 0xFFFF
    self.cycles += 4  # 4T加算を追加
    return byte
```

**結果**: ❌ 失敗
- 期待値が「2」から「0」に変化
- テストの基準値計算が破綻した模様
- **Revert決定**: 副作用が強すぎるため元に戻した

#### 修正2: step()へのopcode fetch 4T加算

**実施内容**:
```python
def step(self):
    # ...
    else:
        # Normal instruction execution
        self.cycles += 4  # Opcode fetch 4Tを追加
        opcode = self.fetch_byte()
        self.execute_instruction(opcode)
```

**結果**: ❌ 失敗
- 01-read_timingがタイムアウト（120秒経過も完了せず）
- おそらく無限ループに入った模様
- cpu_instrsは依然PASS（基本機能は正常）

#### 修正3: 0xF0命令のステップ実行方式

**実施内容**:
```python
elif opcode == 0xF0:  # LD A, (0xFF00+n)
    # step()でopcode fetch済み (+4T)
    n = self.fetch_byte()  # 4T経過
    self.cycles += 4  # +4T (合計8T)
    address = 0xFF00 + n
    self.a = self.memory.read_byte(address)  # 8T時点で読み込み
    self.cycles += 4  # +4T (合計12T)
```

**結果**: ❌ テストが完了しない
- 期待値は「2」に正常化したが
- テストがタイムアウトするため結果不明

### 9.5 3回目の相談に向けての質問

**Q1. タイムアウト問題**
- step()に+4Tを追加したところテストがタイムアウト
- 全命令に+4Tするとtimer動作に影響が出る？
- どのようにデバッグすべきか？

**Q2. 部分的修正 vs 全体修正**
- 現状は0xF0のみ修正、他の命令は旧方式
- 全命令を統一して修正すべきか？
- それとも特定の命令のみ修正で十分か？

**Q3. timerとの連動**
- memory.read_byte()が呼ばれた時点でtimerが進んでいる必要がある
- 現状のtimer実装はmemoryアクセスと連動していない？
- memory.read_byte内でtimer.tick()を呼ぶべきか？

**Q4. 別のアプローチ**
- 「メモリアクセス関数内でサイクルを進める」方式は有効か？
- PyBoyの内部実装を直接移植する方法は？

**Q5. デバッグ手法**
- どの時点で何T経過しているかをトレースする方法は？
- TIMAレジスタの値をリアルタイムで確認する方法は？

---

## 10. 結論と次のステップ（更新版）

### 10.1 現在の状況
- 専門家の指摘通りfetch_byte修正を実施
- しかし新しい問題（期待値0）が発生
- テストの測定方法を完全に理解する必要がある

### 10.2 必要な対応
1. **専門家への2回目の相談**: 新たな質問事項5つ
2. **テストROMの詳細分析**: 逆アセンブルして測定ロジックを理解
3. **段階的デバッグ**: 各修正ステップでテスト実行

### 10.3 暫定対応
- **mem_timingテストは保留**: 他のテストに進む
- **文書化**: この報告書を更新
- **将来的な対応**: 専門家の2回目の回答を待つ

---

## 11. 第4回目の相談 - timer.tick()実装と結果

### 11.1 実施した修正（3回目以降）

#### 修正: CPUにtimer参照を追加

**emulator.py**:
```python
# CPUにtimer参照を設定（メモリタイミングテスト対応）
self.cpu.timer = self.timer
```

**cpu.py**:
```python
class CPU:
    def __init__(self, memory, debug=False):
        # ...
        self.timer = None  # timerはemulatorで設定
```

#### 修正: 0xF0命令にtimer.tick()を実装（4段階）

**現在の実装**:
```python
elif opcode == 0xF0:  # LD A, (0xFF00+n)
    # メモリタイミングテスト対応: timerとcyclesを同期させながら進める
    n = self.fetch_byte()
    self.cycles += 4  # cycles: 4T (オペランドフェッチ分)
    self.timer.tick(self.cycles)  # timer: 4T
    address = 0xFF00 + n
    self.cycles += 4  # cycles: 8T (メモリアクセス直前)
    self.timer.tick(self.cycles)  # timer: 8T
    # ★重要: この時点で8T経過。TIMAは2 M-cycles進んだ状態で読み込み
    self.a = self.memory.read_byte(address)
    self.cycles += 4  # cycles: 12T (命令完了)
    self.timer.tick(self.cycles)  # timer: 12T
```

**重要な発見**: timer.tick()は**絶対サイクル数**を期待（相対値ではなく）

### 11.2 テスト結果の変遷

| 実装 | 結果 | 分析 |
|------|------|------|
| 修正前 | `F0:2-3` | 期待2M、実際3M（失敗） |
| fetch_byte+4T（Revert） | `F0:0-3` | 期待値が0に（異常） |
| step()+4T | タイムアウト | 無限ループに入った模様 |
| timer.tick(4)絶対値 | `F0:4-3` | timer動作確認、期待値が4に |
| timer/cycles同期 | `F0:4-3` | 期待4M、実際3M（サイクル数は合っている） |

**現状**: `F0:4-3`
- 期待値: 4 M-cycles (12T)
- 実際値: 3 M-cycles (12T)
- サイクル数自体は合っているが、テストの期待値が変化

### 11.3 発見と考察

#### 発見1: timer.tick()の動作確認
- 最初の実装で`F0:4-3`になり、timerが正しく動作することを確認
- timer.tick(4)は、相対値4ではなく絶対値を期待することが判明

#### 発見2: 期待値の変化
- 専門家の指摘「8T経過時点で読み込み」を実装した結果、期待値が2→4に変化
- テストは実際のハードウェア動作（12T）を期待している模様
- しかし「メモリアクセス時点」は依然8Tのまま？

#### 発見3: 基本機能は正常
- cpu_instrs 11/11は依然PASS
- timer実装に問題はない（PyBoy互換）

### 11.4 4回目の相談に向けての質問

**Q1. 期待値が4（12T）になった理由**
- 専門家は「8T経過時点（2 M-cycles）」を期待と指摘
- 実際にはテストが「4（12T）」を期待
- このズレの原因は？
- テストは「総サイクル」と「アクセス時点」のどちらを測定している？

**Q2. サイクル数は合っているが失敗する理由**
- `F0:4-3`: 期待4M、実際3M
- 実際のサイクル数は12T（3M）だが、テストは4Mを期待
- テストの測定ロジックが「総サイクル」ではなく「別の指標」を使用している？

**Q3. timer.tick()とcyclesの扱い**
- 現在: 4段階でtimer.tick()とcycles += 4を交互に実行
- これが正しいアプローチか？
- それとも「cycles += 12（一括）」で「timer.tick()はステップごと」が正しい？

**Q4. 03-modify_timingの「0/0-2/3」**
- DEC/INC (HL)の結果が「0/0」を示す理由は？
- これは「内部サイクル/外部サイクル」を表している？
- どう修正すればこのテストも通過する？

**Q5. 次のステップ**
- `F0:4-3`の状態から、どうすれば`F0:2-2`または`F0:4-4`にできる？
- それとも「期待値4、実際3」は「実機と同じ動作」として受け入れるべき？

---

## 12. 第5回目の相談 - 3ステップ実装と結果

### 12.1 実施した修正

専門家の指摘「3ステップ（12T）、2回目のtick直後にメモリ読み込み」を実装：

```python
elif opcode == 0xF0:  # LD A, (0xFF00+n)
    # M-Cycle 1: 0T -> 4T
    self.timer.tick(4)
    
    # M-Cycle 2: 4T -> 8T
    n = self.fetch_byte()
    self.timer.tick(4)
    
    # ★重要: 今8T経過(2 M-cycles)。ここでメモリアクセス！
    addr = 0xFF00 + n
    self.a = self.memory.read_byte(addr)
    
    # M-Cycle 3: 8T -> 12T
    self.timer.tick(4)
```

### 12.2 テスト結果

```
F0:2-3 FA:2-4 CB 46:2-3 CB 4E:2-3 CB 56:2-3 CB 5E:2-3 CB 66:2-3 CB 6E:2-3 CB 76:2-3 CB 7E:2-3 
Failed
```

**重要な進展**: 期待値が4→2に戻った（8Tを期待している）

| 項目 | 値 | 評価 |
|------|-----|------|
| 期待値 | 2 M-cycles (8T) | ✅ 正しい！ |
| 実際値 | 3 M-cycles (12T) | ❌ 依然として多い |

### 12.3 問題分析

**実際値が3のままの理由（推測）**:

1. **step()関数の影響**
   - step()関数でopcode fetch時に既に時間が進んでいる可能性
   - 現状: step()に+4T追加済み（前回の修正）
   - これが0xF0命令のtimerと二重にカウントされている？

2. **timerの基準値**
   - timer.tick(4)は絶対値として動作しているが、基準値（0点）がずれている？
   - テスト開始時のtimer初期値に問題がある可能性

3. **memory.read_byte()のTIMA読み出し**
   - memory.read_byte()がTIMAレジスタ（0xFF05）を正しく返しているか？
   - timer.tick()後にTIMAが更新されていない可能性

### 12.4 5回目の相談に向けての質問

**Q1. 期待2、実際3の状態からの脱出**
- 3ステップ実装で期待値は正しく2になった
- しかし実際値は依然3（12T）
- この1サイクル（4T）の差の原因は？

**Q2. step()関数との関係性**
- step()でopcode fetch +4Tしている
- 0xF0命令内でtimer.tick(4)を3回呼んでいる
- これらが正しく連動していない？
- step()の+4TはRevertすべきか？

**Q3. timerの基準値**
- timer.tick(4)は絶対値を期待
- テスト開始時、timerは0からスタートすべき？
- それとも特定の値から？

**Q4. memory.read_byte()でのTIMAアクセス**
- memory.read_byte(0xFF05)がTIMAを返す仕組みは？
- timer.tick()後にTIMAが即座に更新される？
- それとも遅延がある？

**Q5. デバッグ手法**
- 各ステップでtimer.tick()の呼び出し回数を確認する方法は？
- TIMAレジスタの値をリアルタイムでモニタリングする方法は？

---

## 13. 核心問題の発見 - 0xFF44 vs 0xFF05

### 13.1 デバッグでの発見

0xF0命令実行時のデバッグ出力：
```
[DEBUG F0] Before read: cycles=132260, n=0x44, addr=0xFF44
```

**重大な矛盾**:
- ソースコード: `tima_64 = TIMA = 0xFF05`
- 実際の実行: `n=0x44`, `addr=0xFF44` (LYレジスタ)

### 13.2 問題の分析

**テストROMの動作**:
- ソースではTIMA（0xFF05）を使うように見える
- 実際にはLY（0xFF44）を読んでいる
- 原因不明（ROMビルド時の問題？）

**memory.read_byte(0xFF44)の動作**:
```python
elif 0xFF04 <= address <= 0xFF07:  # Timer registers
    self.timer.tick(self.cpu.cycles)  # tick()を呼ぶ
    return self.timer.read_register(address)
# 0xFF44はこの範囲外なのでtimer.tick()を呼ばない！
```

**結果**:
- timerが進まない
- TIMAの値が更新されない
- テストが失敗する（F0:2-3）

### 13.3 7回目の相談に向けての質問

**Q1. テストが0xFF44を読む理由**
- ソースコードではTIMA（0xFF05）を使うように見える
- 実際のバイナリでは0x44になっている
- これは正常な動作か？それともROMの問題か？

**Q2. 全I/Oレジスタでtimer.tick()を呼ぶべきか**
- 現状: 0xFF04-0xFF07のみでtimer.tick()を呼ぶ
- 提案: 0xFF00-0xFF7F全範囲でtimer.tick()を呼ぶように修正すべきか？
- それとも特定のレジスタのみで十分か？

**Q3. PyBoyの実装**
- PyBoyはどのレジスタアクセスでtimer.tick()を呼んでいる？
- 0xFF44（LY）アクセス時もtimerを更新する？

**Q4. 代替案**
- テストROMのソースを再ビルドする
- または、テストをスキップして他のテストに進む

**Q5. 最終判断**
- この問題を解決するための最善の方法は？
- 全I/Oレジスタ対応 vs テストスキップ vs 別のアプローチ

---

**調査担当者**: Claude Code (OpenCode)  
**報告書バージョン**: 5.0  
**最終更新**: 2026年1月31日  
**次回更新予定**: 専門家の7回目の回答を受けて更新

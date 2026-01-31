# Blargg mem_timing テスト - 第8回目相談メモ

## 実施した修正（7回目以降）

### 修正1: timerにppu参照を追加

**timer.py**:
```python
def __init__(self, memory, debug=False):
    # ...
    self.ppu = None  # emulatorで設定
```

### 修正2: timer.tick()内でppu.step()を呼ぶ

**timer.py tick()メソッド**:
```python
# PyBoy準拠: メモリへの書き込みは行わない
self._cycles_to_interrupt = ((0x100 - self.TIMA) << divider) - self.TIMA_counter

# メモリタイミングテスト対応: PPUも同時に進める
if self.ppu and cycles > 0:
    self.ppu.step(cycles)
    # LYレジスタをメモリに反映
    if self.memory:
        self.memory.io[0x44] = self.ppu.get_ly()

return ret
```

### 修正3: emulatorでppuをtimerに設定

**emulator.py**:
```python
# timerにppu参照を設定（メモリタイミングテスト対応）
self.timer.ppu = self.ppu
```

## テスト結果

```
F0:2-3 FA:2-4 CB 46:2-3 CB 4E:2-3 CB 56:2-3 CB 5E:2-3 CB 66:2-3 CB 6E:2-3 CB 76:2-3 CB 7E:2-3 
Failed
```

**結果**: 依然として`F0:2-3`
- ✅ 基本機能（cpu_instrs 11/11）は正常
- ❌ mem_timingテストは失敗続き

## 8回目の相談に向けての質問

### Q1. ppu.step()の呼び出し確認
- timer.tick()内でppu.step(cycles)を呼んでいる
- cyclesは正しく計算されているか？
- デバッグ方法：ppu.step()の呼び出し回数を確認する方法は？

### Q2. LYレジスタの更新確認
- `self.memory.io[0x44] = self.ppu.get_ly()`でLYを更新
- テストが読む0xFF44はこの値を参照しているか？
- memory.read_byte(0xFF44)の動作を確認する方法は？

### Q3. 0xF0命令でのtimer.tick()呼び出し
- 現在の0xF0実装：
```python
n = self.fetch_byte()
addr = 0xFF00 + n
self.a = self.memory.read_byte(addr)
self.cycles += 12
```
- memory.read_byte(0xFF44)内でtimer.tick()が呼ばれる
- その結果ppu.step()も呼ばれるはず
- しかし依然2-3の理由は？

### Q4. 別の原因の可能性
- 0xFF44（LY）と0xFF05（TIMA）の混同？
- テストは実際どちらのレジスタを期待している？
- ソースコードとバイナリの不一致の可能性

### Q5. 最終判断
- このアプローチで解決可能か？
- それとも別のアーキテクチャ変更が必要？
- テストを保留して他に進むべきタイミングは？

## 現在の実装状態

- **timer.tick()**: ppu.step()呼び出し追加済み
- **0xF0命令**: シンプルな実装（fetch→read→cycles+=12）
- **基本機能**: cpu_instrs 11/11 PASS（正常）
- **テスト結果**: F0:2-3（失敗）

## 結論

timer+ppu同期を実装したが、依然テストは失敗。原因特定のため、専門家の追加アドバイスを求める。

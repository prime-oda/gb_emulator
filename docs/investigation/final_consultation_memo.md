# Blargg mem_timing テスト - 最終相談メモ

## これまでの実装総括

### 実装1: timer+ppu同期（維持）
- timer.tick()内でppu.step(cycles)を呼ぶ
- ppu更新時にLYレジスタもmemory.io[0x44]に反映

### 実装2: 0xF0命令の3段階timer.tick()
```python
elif opcode == 0xF0:
    self.timer.tick(4)   # Step 1: 0->4T
    n = self.fetch_byte()
    self.timer.tick(4)   # Step 2: 4->8T
    addr = 0xFF00 + n
    self.a = self.memory.read_byte(addr)  # 8T時点で読み込み
    self.timer.tick(4)   # Step 3: 8->12T
```

## テスト結果

```
F0:2-3 FA:2-4 CB 46:2-3 ... Failed
```

**依然として失敗**

## 実装の確認事項

### timer.tick()の累積動作
- `tick(4)`: last_cyclesとの差分は4
- `tick(4)`: 差分は0（同じ値を渡したため）
- **問題**: 累積値(4, 8, 12)を渡す必要があるが、差分計算のため同じ値を渡すと0になる

### 修正案
timer.tick()は差分を計算するため、以下のように累積値を渡す必要がある：
```python
# 修正前（誤り）
self.timer.tick(4)  # 4を渡すが、差分は4-0=4 → OK
self.timer.tick(4)  # 4を渡すが、差分は4-4=0 → NG

# 修正後（正しい）
self.timer.tick(4)   # 累積4T
self.timer.tick(8)   # 累積8T（差分4T）
self.timer.tick(12)  # 累積12T（差分4T）
```

## 最終質問

### Q1. timer.tick()の使い方
- timer.tick()は累積サイクル数を期待（絶対値）
- 各ステップで累積値を渡す必要がある
- 現状の`tick(4)`を3回は正しくない？

### Q2. 累積値の計算
```python
# 正しい使い方は？
self.timer.tick(4)   # 第1回目
self.timer.tick(8)   # 第2回目（+4T）
self.timer.tick(12)  # 第3回目（+4T）
# それとも別の方法？
```

### Q3. cycles変数との関係
- timer.tick()は絶対値、cycles変数は加算
- この二重管理をどう同期する？
- それともcycles変数は使わない？

### Q4. 最終的な実装コード
- 正しい0xF0実装を具体的に示してください
- timer.tick()の正しい呼び出し方
- ppu.step()との連携

### Q5. 次のステップ
- このアプローチで解決可能か？
- それとも別のアーキテクチャが必要？
- テストを保留すべきか？

## 補足情報

- **基本機能**: cpu_instrs 11/11 PASS（正常）
- **timer実装**: PyBoy互換
- **ppu実装**: step(cycles)をtimer.tick()内で呼ぶ
- **memory実装**: 0xFF04-0xFF07でtimer.tick()呼び出し

## 結論

timer+ppu同期を実装し、0xF0を3段階timer.tick()に修正したが、依然`F0:2-3`。timer.tick()の累積値の渡し方が誤っている可能性。専門家の最終アドバイスを求める。

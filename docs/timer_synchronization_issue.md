# Game Boy Emulator - Timer実行タイミング同期問題

## 課題の背景

### 問題の発生経緯
- Blarggのcpu_instrs/individual/02-interrupts.gb テストが失敗
- PyBoyエミュレータとのレジスタ値比較により、タイマー実装の調査を実施
- レジスタ値（DIV、TIMA、TAC）は完全にPyBoyと同期しているが、テストが失敗し続ける

### 技術的調査結果
1. **レジスタ同期は完璧**: Step 83282でDIV=0x83、TIMA=0x46がPyBoyと完全一致
2. **Boot ROM初期化値も正確**: PyBoy検証済みのDMG初期化値を実装済み
3. **メモリアクセス時のtick呼び出し**: PyBoy互換のタイマーレジスタアクセス時tick呼び出しを実装済み
4. **ループ処理の正常性確認**: メモリコピーループは正常に動作し、無限ループではない

## 根本問題：実行タイミング同期の不整合

### 問題の本質
我々のエミュレータは**機能的には完全に正しい**が、**実行速度がPyBoyと大きく異なる**：

- PyBoy: TAC=0x05到達まで約100 ticks
- 我々のエミュレータ: TAC=0x05到達まで65,486 steps
- **655:1の実行速度差**

### 4つの同期問題

#### 1. CPU実行速度 vs PyBoy基準速度
```
PyBoyの期待値: ~100 ticks でTAC=0x05到達
実際の実装: 65,486 steps でTAC=0x05到達
比率: 655:1の速度差
```

#### 2. DIVレジスタ進行 vs 実行進行
```
DIVは16384Hz（約16.384kHz）で進行すべき
現在：実行ステップ数に対してDIV進行が遅すぎる可能性
```

#### 3. タイマー有効化タイミング vs テスト期待値
```
TAC書き込みからTIMA開始までのタイミング
Blarggテストの期待値と実装の差異
```

#### 4. timer.tick()の重複呼び出し
```
emulator.py内で発見された潜在的な重複：
- line 142: run()メソッド内でtimer.tick()
- line 222: step()メソッド内でtimer.tick()
```

## 確認方法

### 1. 現在の実行状況確認
```bash
cd /Users/oda/github/gb_emulator
uv run python debug_pyboy_comparison.py
```

### 2. タイミング測定
```bash
uv run python -c "
from src.gameboy.emulator import GameBoy
import time

gameboy = GameBoy(debug=False)
gameboy.load_rom('roms/blargg/cpu_instrs/individual/02-interrupts.gb')

start_time = time.time()
steps = 0
while gameboy.memory.read(0xFF07) != 0x05 and steps < 100000:
    gameboy.step()
    steps += 1

end_time = time.time()
print(f'Steps: {steps}, Time: {end_time - start_time:.2f}s')
print(f'Speed: {steps/(end_time - start_time):.0f} steps/sec')
"
```

### 3. tick()呼び出し重複確認
```bash
uv run python -c "
from src.gameboy.emulator import GameBoy

gameboy = GameBoy(debug=False)
gameboy.load_rom('roms/blargg/cpu_instrs/individual/02-interrupts.gb')

original_tick = gameboy.timer.tick
call_count = 0

def counting_tick(cycles):
    global call_count
    call_count += 1
    return original_tick(cycles)

gameboy.timer.tick = counting_tick
gameboy.step()
print(f'1 stepでのtick()呼び出し回数: {call_count}')
"
```

### 4. Blarggテスト実行
```bash
uv run python main.py roms/blargg/cpu_instrs/individual/02-interrupts.gb
```

## 解決すべき課題

### 優先度1: timer.tick()重複呼び出しの排除
- `emulator.py`の`run()`と`step()`メソッドでの重複確認
- 適切な呼び出し場所の決定

### 優先度2: CPU実行サイクルとタイマー進行の正しい関係確立
- PyBoyとの655:1速度差の原因調査
- CPU命令サイクル数とタイマー進行の正しい比率設定

### 優先度3: DIVレジスタ進行頻度の調整
- 16384Hzの正確な実装確認
- 実行ステップ数に対する適切なDIV進行設定

### 優先度4: タイマー有効化タイミングの精密調整
- TAC書き込み時のTIMA開始タイミング
- Blarggテストの期待値との完全一致

## 期待される結果

1. **機能的正確性の維持**: 現在の完璧なレジスタ同期を保持
2. **実行速度の調整**: PyBoyとの実行速度差を解消
3. **Blarggテスト成功**: 02-interrupts.gbテストのパス
4. **他テストへの影響なし**: 既存の動作する機能の保持

## 関連ファイル

- `src/gameboy/timer.py`: タイマー実装本体
- `src/gameboy/emulator.py`: メインループとstep()実装
- `src/gameboy/memory.py`: メモリアクセス時のtick呼び出し
- `debug_pyboy_comparison.py`: PyBoy比較検証ツール
- `src/gameboy/post_boot_init.py`: Boot ROM後初期化値

## 注意事項

- この問題は**機能的な正確性**の問題ではない
- **実行タイミングの同期**の問題である
- レジスタ値やメモリ状態は正確、実行速度のみが課題
- 解決時は既存の正確な動作を壊さないよう注意が必要

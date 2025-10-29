# 🚀 パフォーマンス改善計画（完全版）

**作成日**: 2025年10月29日
**最終更新**: 2025年10月29日（根本原因調査完了）
**現状**: PyBoyと比較して**50-100倍遅い**
**目標**: PyBoy並みの実行速度を実現

---

## 🔥 重大発見：100倍の速度差の正体

### PyBoyの秘密 = **Cythonによる完全ネイティブコンパイル**

詳細調査の結果、PyBoyは**全コアモジュールをCythonでC言語にコンパイル**していることが判明しました。

```bash
# PyBoyのビルド済みモジュール（実例）
external/PyBoy/pyboy/core/
├── cpu.cpython-39-darwin.so        # ← Cythonコンパイル済み（ネイティブコード）
├── mb.cpython-39-darwin.so         # ← Cythonコンパイル済み
├── timer.cpython-39-darwin.so      # ← Cythonコンパイル済み
└── ...
```

**手元実装はすべてPure Python（インタプリタ実行）**であり、これが100倍の速度差を生んでいます。

---

## 📊 速度差の内訳（累積効果）

| 要因 | 速度倍率 | 寄与度 | 実装難易度 |
|------|----------|--------|-----------|
| **Cythonネイティブコンパイル** | 10-30倍 | 60-70% | ⭐⭐⭐ 高 |
| **命令ディスパッチ最適化** | 2-4倍 | 15-20% | ⭐⭐ 中 |
| **バッチ処理/先読み実行** | 2-3倍 | 10-15% | ⭐⭐ 中 |
| **C言語レベルメモリアクセス** | 1.5-2倍 | 5-10% | ⭐⭐⭐ 高 |
| **データ構造最適化** | 1.3-1.5倍 | 3-5% | ⭐⭐ 中 |
| **累積効果** | **50-100倍** | **100%** | - |

### 結論

- 旧TODO_IMPROVE.mdの最適化（3-10倍）では**全く不十分**
- **Cython導入が絶対必要**（60-70%の寄与度）
- バッチ処理＋Cythonで累積**20-90倍高速化**が可能

---

## 🎯 根本的改善計画

### 全体ロードマップ

```
Phase 0: バッチ処理導入（1-3日）    → 2-3倍高速化
    ↓
Phase 1: Cython導入準備（3-5日）    → 10-30倍高速化
    ↓
Phase 2: 段階的Cythonコンパイル（1-2週間） → 20-50倍高速化
    ↓
Phase 3: 最終最適化（1週間）        → 50-100倍高速化（PyBoy並み）
```

---

## Phase 0: バッチ処理導入（即効性）

**優先度**: ⭐⭐⭐ 最優先
**期待効果**: 2-3倍高速化
**工数**: 1-3日

### PyBoyのバッチ処理の仕組み

```python
# PyBoy mb.py: Fast-forward to next interrupt
cycles_target = max(
    4,
    min(
        self.timer._cycles_to_interrupt,      # タイマー割り込みまで
        self.lcd._cycles_to_interrupt,        # LCD割り込みまで
        self.lcd._cycles_to_frame,            # フレーム完了まで
        self.sound._cycles_to_interrupt,      # サウンド割り込みまで
        self.serial._cycles_to_interrupt,     # シリアル割り込みまで
    ),
)
self.cpu.tick(cycles_target)  # 次の割り込みまで一気に実行
```

**キーアイデア**: 各コンポーネントが「次の割り込みまでのサイクル数」を事前計算し、その間は割り込みチェックせずに高速実行。

### 手元実装への適用

#### 実装内容

1. **各コンポーネントに`_cycles_to_interrupt`を追加**

```python
class Timer:
    def tick(self, _cycles):
        # ... TIMA更新処理 ...

        # 次の割り込みまでのサイクル数を計算
        self._cycles_to_interrupt = ((0x100 - self.TIMA) << divider) - self.TIMA_counter
```

2. **emulator.pyでバッチ実行**

```python
class GameBoy:
    def step_batch(self):
        """バッチ処理版step（高速）"""
        # 次の割り込みまでのサイクル数を計算
        cycles_target = min(
            self.timer._cycles_to_interrupt,
            self.ppu._cycles_to_interrupt,
            # ...
        )

        # 一気に実行
        for _ in range(cycles_target // 4):  # 平均4サイクル/命令
            self.cpu.step()
            if self.cpu.halted or not self.running:
                break
```

#### チェックリスト

- [x] Timer._cycles_to_interruptの実装 ✅
- [x] PPU._cycles_to_interruptの実装 ✅
- [x] APU._cycles_to_interruptの実装 ✅
- [x] GameBoy.run_until_interrupt()の実装 ✅
- [x] パフォーマンステスト（01-special.gb）✅

#### 実装完了（2025年10月29日）

**成果**: 🎉 **2.01倍高速化を達成！**

| テストROM | バッチなし | バッチあり | 速度比 |
|-----------|-----------|-----------|--------|
| 01-special.gb | 8.97秒 | 4.47秒 | **2.01x** |

**実装詳細**:
1. **Timer._cycles_to_interrupt管理** (timer.py:22, 139-141, 147-152, 192)
   - 初期値: `MAX_CYCLES`
   - TAC/TIMA書き込み時に更新
   - tick()実行時に毎回計算

2. **PPU._cycles_to_interrupt最適化** (ppu.py:43, 976)
   - スキャンライン単位（456サイクル）で計算
   - モード遷移ベースから変更して大幅なバッチサイズ増加

3. **APU._cycles_to_interrupt初期化** (apu.py:52)
   - 割り込みなし: `MAX_CYCLES`

4. **GameBoy.run_until_interrupt()実装** (emulator.py:237-297)
   - Timer/PPU/APUの最小値で目標サイクル決定
   - HALT状態も考慮

5. **コマンドラインオプション追加** (main.py:19, 25)
   - `--batch`フラグ

**実行方法**:
```bash
uv run python main.py <ROM> --batch --auto-exit
```

---

## Phase 1: Cython導入準備

**優先度**: ⭐⭐⭐
**期待効果**: 10-30倍高速化
**工数**: 3-5日

### PyBoyのCythonコンパイル設定

```python
# setup.py: PyBoyの実際の設定
from setuptools import setup
from Cython.Build import cythonize

setup(
    ext_modules=cythonize(
        ["pyboy/core/*.py"],  # 全コアモジュールをコンパイル
        compiler_directives={
            "boundscheck": False,        # 配列境界チェック無効（高速化）
            "cdivision": True,           # C言語式整数除算
            "wraparound": False,         # 負のインデックス無効
            "infer_types": True,         # 型推論で最適化
            "initializedcheck": False,   # 初期化チェック無効
            "nonecheck": False,          # Noneチェック無効
            "overflowcheck": False,      # オーバーフローチェック無効
            "language_level": "3",       # Python 3構文
        },
        extra_compile_args=["-O3"],      # GCC最適化レベル3
    ),
)
```

### 手元実装への適用

#### 1. setup.py作成

```python
# setup.py
from setuptools import setup
from Cython.Build import cythonize
import numpy as np

setup(
    name="gb_emulator",
    ext_modules=cythonize(
        [
            "src/gameboy/cpu.py",
            "src/gameboy/memory.py",
            "src/gameboy/timer.py",
            "src/gameboy/ppu.py",
            # 段階的に追加
        ],
        compiler_directives={
            "boundscheck": False,
            "cdivision": True,
            "wraparound": False,
            "infer_types": True,
            "initializedcheck": False,
            "nonecheck": False,
            "overflowcheck": False,
            "language_level": "3",
        },
        extra_compile_args=["-O3"],
    ),
    include_dirs=[np.get_include()],  # NumPy配列用
)
```

#### 2. 型アノテーション追加

```python
# cpu.py: Cython型アノテーション例
cimport cython

@cython.cfunc
@cython.returns(cython.void)
def execute_instruction(self, cython.uchar opcode):
    cdef cython.int cycles = 0
    cdef cython.ushort value

    if opcode == 0x00:  # NOP
        cycles = 4
    elif opcode == 0x01:  # LD BC, nn
        value = self.fetch_word()
        self.set_bc(value)
        cycles = 12
    # ...
```

#### 3. .pxdヘッダーファイル作成

```python
# cpu.pxd: 公開型定義
cdef class CPU:
    cdef public int a, f, b, c, d, e, h, l
    cdef public int sp, pc
    cdef public long cycles
    cdef public bint halted, stopped, interrupt_master_enable

    cdef void execute_instruction(self, unsigned char opcode)
    cdef unsigned char fetch_byte(self)
    cdef unsigned short fetch_word(self)
```

#### チェックリスト

- [ ] setup.pyの作成
- [ ] pyproject.tomlにCython依存関係追加
- [ ] cpu.pyに型アノテーション追加
- [ ] cpu.pxdヘッダーファイル作成
- [ ] ビルドテスト（`python setup.py build_ext --inplace`）
- [ ] 互換性テスト（01-special.gb）

---

## Phase 2: 段階的Cythonコンパイル

**優先度**: ⭐⭐⭐
**期待効果**: 20-50倍高速化（累積）
**工数**: 1-2週間

### コンパイル順序（依存関係順）

1. **timer.py** → timer.so（最も単純）
2. **cpu.py** → cpu.so（最重要、最大の効果）
3. **memory.py** → memory.so（CPU依存）
4. **ppu.py** → ppu.so（Memory依存）
5. **apu.py** → apu.so（Memory依存）

### 各モジュールの最適化ポイント

#### cpu.py
```python
# execute_instruction: 246個のif-elifをジャンプテーブル化
cdef void (*opcode_handlers[256])(CPU) nogil

opcode_handlers[0x00] = &nop_00
opcode_handlers[0x01] = &ld_bc_nn_01
# ... 256個の関数ポインタ

cdef void execute_instruction(self, unsigned char opcode) nogil:
    opcode_handlers[opcode](self)  # O(1)ディスパッチ
```

#### memory.py
```python
# メモリアクセスをC配列化
cdef unsigned char rom[0x8000]
cdef unsigned char vram[0x2000]
cdef unsigned char wram[0x2000]
cdef unsigned char io[0x80]

@cython.boundscheck(False)
@cython.wraparound(False)
cdef inline unsigned char read_byte(self, unsigned short address) nogil:
    if address < 0x8000:
        return self.rom[address]
    # ...
```

#### チェックリスト

- [ ] timer.pyのCython化＋テスト
- [ ] cpu.pyのCython化＋テスト
- [ ] memory.pyのCython化＋テスト
- [ ] ppu.pyのCython化＋テスト
- [ ] apu.pyのCython化＋テスト
- [ ] 統合テスト（cpu_instrs.gb）

---

## Phase 3: 最終最適化

**優先度**: ⭐⭐
**期待効果**: 50-100倍高速化（PyBoy並み）
**工数**: 1週間

### 追加最適化項目

#### 1. NumPy配列の活用

```python
import numpy as np
cimport numpy as cnp

# PPUフレームバッファ
cdef cnp.ndarray[cnp.uint8_t, ndim=2] framebuffer = np.zeros((144, 160), dtype=np.uint8)
```

#### 2. GILロック解放

```python
@cython.nogil
cdef void cpu_step(self):
    # GILなしで実行（マルチスレッド高速化）
    ...
```

#### 3. プロファイリングベースの最適化

```bash
# Cythonアノテーションファイル生成
cython -a src/gameboy/cpu.py

# ホットスポット（黄色い行）を重点的に最適化
```

#### チェックリスト

- [ ] NumPy配列導入（PPU、APU）
- [ ] GILロック解放（CPU、Memory）
- [ ] cProfile詳細分析
- [ ] ホットスポット最適化
- [ ] 最終パフォーマンステスト

---

## 📈 期待される最終効果

| Phase | 施策 | 速度倍率 | 累積倍率 |
|-------|------|----------|----------|
| Phase 0 | バッチ処理 | 2-3倍 | 2-3倍 |
| Phase 1 | Cython導入 | 5-10倍 | 10-30倍 |
| Phase 2 | 完全Cython化 | 2-3倍 | 20-90倍 |
| Phase 3 | 最終最適化 | 1.5-2倍 | **30-180倍** |

**現実的な目標**: 50-100倍高速化（PyBoy並み）

---

## 🔬 ベンチマーク計測

### 現状（Phase 0前）

```bash
# 01-special.gb
time timeout 60 uv run python main.py roms/test/cpu_instrs/individual/01-special.gb
# 予想: 10秒以上（タイムアウト）

# PyBoy（参考）
time python -m pyboy --no-window roms/test/cpu_instrs/individual/01-special.gb
# 実測: 1-2秒
```

### 目標（Phase 3後）

```bash
# 01-special.gb
time timeout 60 uv run python main.py roms/test/cpu_instrs/individual/01-special.gb
# 目標: 1-2秒（PyBoy並み）

# 速度比較
# 現状: 10秒以上
# 目標: 1-2秒
# 改善: 5-10倍高速化
```

---

## 🛠️ 実装スケジュール

### Week 1: Phase 0（バッチ処理）
- Day 1-2: _cycles_to_interrupt実装
- Day 3: step_batch()実装
- Day 4: テスト＋デバッグ
- Day 5: ベンチマーク計測

### Week 2-3: Phase 1（Cython準備）
- Day 1-2: setup.py作成＋依存関係整理
- Day 3-5: timer.py型アノテーション
- Day 6-7: cpu.py型アノテーション
- Day 8-10: ビルド＋テスト

### Week 4-5: Phase 2（段階的コンパイル）
- Week 4: cpu.py、memory.pyコンパイル
- Week 5: ppu.py、apu.pyコンパイル＋統合テスト

### Week 6: Phase 3（最終最適化）
- Day 1-3: NumPy、GILロック最適化
- Day 4-5: プロファイリング＋ホットスポット最適化
- Day 6-7: 最終テスト＋ドキュメント

**合計**: 6週間で50-100倍高速化達成

---

## 📚 技術参考資料

### Cython公式ドキュメント
- https://cython.readthedocs.io/en/latest/
- Pure Python Mode: https://cython.readthedocs.io/en/latest/src/tutorial/pure.html

### PyBoy実装
- setup.py: `external/PyBoy/setup.py`
- コンパイル済みモジュール: `external/PyBoy/pyboy/core/*.so`

### 高速化テクニック
- Cython型付け: https://cython.readthedocs.io/en/latest/src/userguide/language_basics.html
- GILロック解放: https://cython.readthedocs.io/en/latest/src/userguide/nogil.html
- NumPy統合: https://cython.readthedocs.io/en/latest/src/userguide/numpy_tutorial.html

---

## 🚨 重要な注意事項

### Cython導入のデメリット

1. **デバッグ困難**: コンパイル後はPythonデバッガが使えない
2. **コンパイル必要**: コード変更後に毎回`python setup.py build_ext --inplace`
3. **プラットフォーム依存**: .soファイルはOS/CPU依存

### 対策

- **開発時**: Pure Pythonで開発＋デバッグ
- **リリース時**: Cythonでコンパイル＋配布
- **CI/CD**: 自動ビルドパイプライン構築

---

## ✅ 成功基準

### Phase 0完了時点
- ✅ 01-special.gb: 5秒以内
- ✅ cpu_instrs.gb: 90秒以内

### Phase 1完了時点
- ✅ 01-special.gb: 2秒以内
- ✅ cpu_instrs.gb: 30秒以内

### Phase 3完了時点（最終目標）
- ✅ 01-special.gb: 1-2秒（PyBoy並み）
- ✅ cpu_instrs.gb: 15-30秒（PyBoy並み）
- ✅ big2small.gb: 60FPS安定動作

---

**次のアクション**: Phase 0（バッチ処理導入）から開始

**最終目標**: 6週間で50-100倍高速化、PyBoy並みの実行速度を実現 🚀

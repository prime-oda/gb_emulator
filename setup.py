"""
Game Boy Emulator - Cython Setup
Phase 1: 段階的Cythonコンパイル設定

段階的コンパイル順序：
1. timer.py → timer.so（最も単純）
2. cpu.py → cpu.so（最重要、最大の効果）
3. memory.py → memory.so（CPU依存）
4. ppu.py → ppu.so（Memory依存）
5. apu.py → apu.so（Memory依存）
"""
from setuptools import setup, Extension
from Cython.Build import cythonize
import numpy as np

# PyBoy互換のコンパイラディレクティブ
compiler_directives = {
    "boundscheck": False,        # 配列境界チェック無効（高速化）
    "cdivision": True,           # C言語式整数除算
    "wraparound": False,         # 負のインデックス無効
    "infer_types": True,         # 型推論で最適化
    "initializedcheck": False,   # 初期化チェック無効
    "nonecheck": False,          # Noneチェック無効
    "overflowcheck": False,      # オーバーフローチェック無効
    "language_level": "3",       # Python 3構文
}

# コンパイル対象モジュール（段階的に追加）
modules_to_compile = [
    "src/gameboy/timer.py",    # Phase 1a: 最も単純なモジュール ✅
    "src/gameboy/cpu.py",      # Phase 1b: 最重要（60-70%の実行時間）
    # "src/gameboy/memory.py", # Phase 2: CPU依存（後で追加）
    # "src/gameboy/ppu.py",    # Phase 3: Memory依存（後で追加）
    # "src/gameboy/apu.py",    # Phase 4: Memory依存（後で追加）
]

setup(
    name="gb_emulator",
    version="0.1.0",
    description="Game Boy Emulator with Cython optimization",
    ext_modules=cythonize(
        modules_to_compile,
        compiler_directives=compiler_directives,
        annotate=True,  # HTMLアノテーションファイル生成（最適化分析用）
    ),
    include_dirs=[np.get_include()],  # NumPy配列用（将来的に使用）
    zip_safe=False,
)

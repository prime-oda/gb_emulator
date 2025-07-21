# Game Boy Emulator Project

このプロジェクトは、PythonでNintendo Game Boyのエミュレータを作成することを目的としています。

## プロジェクト構成

```
gb_emulator/
├── main.py                 # エントリーポイント
├── requirements.txt        # 依存関係（レガシー）
├── pyproject.toml         # uv設定（推奨）
├── setup.py               # セットアップスクリプト
├── src/
│   └── gameboy/
│       ├── __init__.py
│       ├── emulator.py    # メインエミュレータクラス
│       ├── cpu.py         # CPU (Sharp LR35902) エミュレーション
│       ├── memory.py      # メモリ管理ユニット (MMU)
│       └── ppu.py         # 画像処理ユニット (PPU)
├── roms/
│   └── dmg_bootrom.bin    # Game Boyブートロム
└── tests/                 # テストファイル
```

## 使用方法

### uvを使用（推奨）
```bash
# ブートROM実行
uv run python main.py roms/dmg_bootrom.bin --debug

# ゲームROM実行
uv run python main.py roms/big2small.gb --debug
```

### pipを使用
```bash
# ブートROM実行
python main.py roms/dmg_bootrom.bin --debug

# ゲームROM実行  
python main.py roms/big2small.gb --debug
```

## 開発状況

- [x] 基本プロジェクト構造
- [x] CPU基本実装 (レジスタ、基本命令)
- [x] メモリ管理 (MMU、バンク切り替え)
- [x] ブートROM対応
- [x] 包括的な命令セット実装
- [x] PPU (画像処理ユニット)
- [x] 背景レンダリング
- [x] Pygame グラフィック出力
- [x] ゲームROM対応
- [x] 拡張CPU命令セット
- [ ] スプライト描画
- [ ] ウィンドウレイヤー
- [ ] 音声処理 (APU)
- [ ] 入力処理（ジョイパッド）
- [ ] セーブ機能

## 実装済み機能

### CPU (Sharp LR35902)
- ロード/ストア命令（8/16ビット）
- ジャンプ/ブランチ命令（相対・絶対）
- 算術・論理演算
- スタック操作（PUSH/POP）
- ビット操作（CB拡張命令）
- 割り込み制御

### PPU (Picture Processing Unit)
- LCDタイミング制御
- 背景タイル描画
- スクロール機能
- パレット適用
- 160x144ピクセル出力

### グラフィック
- Pygame統合
- 4倍スケール表示（640x576）
- 60FPS制限
- Game Boyカラーパレット

## 技術仕様

- **CPU**: Sharp LR35902 (Z80ベース、4.19MHz)
- **メモリ**: 64KB アドレス空間
- **画面解像度**: 160x144 ピクセル
- **パレット**: 4階調グレースケール
- **フレームレート**: 約60Hz

## 動作確認

現在のバージョンでは、ブートROMとゲームROMが正常に実行され、グラフィック出力が表示されます：

1. VRAMクリア処理の実行
2. LCDスキャンライン制御
3. 背景描画システム
4. PPU-CPU同期
5. ゲームROM実行（big2small.gb対応）

## テストROM

### 対応ROM
- **dmg_bootrom.bin**: Game Boyブートロム（256バイト）
- **big2small.gb**: GPLライセンスのテストゲーム

### big2small.gb について
- **開発者**: MDSteele
- **入手先**: https://mdsteele.itch.io/big2small
- **ライセンス**: GPL
- **説明**: Game Boy用パズルゲーム、エミュレータテストに最適

## 依存関係

- pygame>=2.6.1

## 参考資料

- [Game Boy CPU Manual](http://www.codeslinger.co.uk/pages/projects/gameboy/files/GB.pdf)
- [Game Boy Development Wiki](https://gbdev.gg8.se/wiki/articles/Main_Page)
- [Pan Docs](https://gbdev.io/pandocs/)

## 開発コマンド

```bash
# 開発環境セットアップ
uv sync

# エミュレータ実行
uv run python main.py roms/dmg_bootrom.bin --debug

# テスト実行（今後追加予定）
uv run pytest

# リンター実行（今後追加予定）
uv run ruff check src/
```

## 今後の開発予定

1. **スプライト描画**: オブジェクト（キャラクター）の表示
2. **ウィンドウレイヤー**: UI表示用の追加画面レイヤー
3. **音声処理**: APU（Audio Processing Unit）実装
4. **入力処理**: ジョイパッド（十字キー、A/Bボタン等）
5. **ゲームROM対応**: 実際のゲームカートリッジ読み込み
6. **セーブ機能**: SRAM、RTCサポート
7. **デバッガー**: ステップ実行、ブレークポイント
8. **パフォーマンス最適化**: 高速化とメモリ効率改善
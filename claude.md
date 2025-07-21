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
- [x] スプライト描画システム
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
- **スプライト描画システム**: OAM対応、8x8/8x16サイズ、X/Y反転、優先度制御

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

## 最新実装: スプライト描画システム

### 実装された機能
- **OAM（Object Attribute Memory）処理**: 0xFE00-0xFEA0領域から40個のスプライトデータを管理
- **マルチサイズスプライト**: 8x8および8x16ピクセルスプライトに対応
- **スプライト属性制御**:
  - X/Y軸フリップ（反転）機能
  - 背景優先度制御（BG Priority）
  - 2つのスプライトパレット選択（OBP0/OBP1）
- **透明度処理**: カラー0を透明として扱う
- **性能制限**: 1スキャンラインあたり最大10スプライト表示
- **適切な描画順序**: X座標による優先度制御

### スプライトレンダリングプロセス
1. 各スキャンラインでOAMをスキャンして表示スプライトを特定
2. Y座標範囲内のスプライトを最大10個まで選択
3. X座標でソートして描画優先度を決定
4. 各スプライトのピクセルデータを背景レイヤーの上に描画
5. 透明ピクセル（カラー0）をスキップ
6. 背景優先度属性を考慮した重ね合わせ処理

### 技術仕様
- **スプライトサイズ**: 8x8または8x16ピクセル（LCDC bit 2で制御）
- **最大スプライト数**: 40個（OAM内）
- **スキャンライン制限**: 10スプライト/ライン
- **パレット**: OBP0（0xFF48）、OBP1（0xFF49）
- **属性フラグ**: X/Y flip、BG priority、palette select

## 現在の課題

### CPU実行フロー問題
現在、CPUがROM領域外のメモリ（0x6879など）を実行しようとして停止する問題があります：
- ブートROM、ゲームROM共に発生
- PCが想定範囲外の高いアドレスに到達
- 0xFF opcodeの連続実行によるエラー検出機能を追加済み

### 解決が必要な項目
1. **メモリバンク切り替え**: 大容量ROMのサポート
2. **ジャンプ命令の検証**: 不正なアドレスへのジャンプ防止
3. **ROM境界チェック**: 実行アドレスの妥当性検証

## 今後の開発予定

1. **CPU実行フロー修正**: ROM境界外実行問題の解決
2. **ウィンドウレイヤー**: UI表示用の追加画面レイヤー
3. **音声処理**: APU（Audio Processing Unit）実装
4. **入力処理**: ジョイパッド（十字キー、A/Bボタン等）
5. **ゲームROM対応**: 実際のゲームカートリッジ読み込み
6. **セーブ機能**: SRAM、RTCサポート
7. **デバッガー**: ステップ実行、ブレークポイント
8. **パフォーマンス最適化**: 高速化とメモリ効率改善
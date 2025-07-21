# Game Boy Emulator

PythonでNintendo Game Boyのエミュレータを作成するプロジェクトです。

## 機能

### 実装済み機能

#### CPU (Sharp LR35902)
- **基本命令セット**: 8/16ビットロード、算術演算、論理演算
- **ジャンプ/ブランチ**: 相対・絶対ジャンプ、条件分岐
- **関数呼び出し**: CALL/RET命令、スタック操作
- **ビット操作**: CB拡張命令、ビットテスト
- **割り込み制御**: DI/EI命令
- **レジスタ操作**: AF、BC、DE、HL、SP、PC

#### メモリ管理 (MMU)
- **メモリマッピング**: Game Boy標準メモリマップ
- **ブートROM対応**: 0x0000-0x00FF領域
- **バンク切り替え**: ROM/RAMバンク管理
- **I/Oレジスタ**: LCD制御レジスタ

#### PPU (Picture Processing Unit)
- **LCDタイミング**: スキャンライン制御、V-Blank/H-Blank
- **背景レンダリング**: タイル描画、スクロール対応
- **パレット機能**: 4階調グレースケール
- **レジスタ管理**: LCDC、STAT、LY、SCY、SCX、BGP

#### グラフィック出力
- **Pygame統合**: 160x144ピクセル表示
- **4倍スケール**: 640x576ピクセルウィンドウ
- **60FPS制限**: リアルタイム描画
- **Game Boyカラーパレット**: 緑色モノクロ

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

### 必要な環境
- Python 3.10以上
- uv (推奨) または pip

### インストール

#### uvを使用（推奨）
```bash
# 依存関係をインストール
uv sync

# エミュレータを実行
uv run python main.py roms/dmg_bootrom.bin --debug
```

#### pipを使用
```bash
# 依存関係をインストール
pip install pygame

# エミュレータを実行
python main.py roms/dmg_bootrom.bin --debug
```

### コマンドラインオプション
- `<rom_file>`: 実行するROMファイルのパス
- `--debug`: デバッグモードを有効化（CPU状態の詳細表示）

## 技術仕様

### Game Boy仕様
- **CPU**: Sharp LR35902 (Z80ベース、4.19MHz)
- **メモリ**: 64KB アドレス空間
- **画面**: 160x144 ピクセル
- **パレット**: 4階調グレースケール
- **フレームレート**: 約60Hz

### 実装済み命令
#### ロード/ストア命令
- `LD r, n` - 即値ロード
- `LD r, r'` - レジスタ間転送
- `LD r, (HL)` - メモリからロード
- `LD (HL), r` - メモリへストア
- `LD A, (nn)` - 絶対アドレスロード
- `LD (nn), A` - 絶対アドレスストア
- `LD (HL+), A` / `LD A, (HL+)` - インクリメント付き
- `LD (HL-), A` / `LD A, (HL-)` - デクリメント付き

#### ジャンプ/ブランチ命令
- `JP nn` - 絶対ジャンプ
- `JP cc, nn` - 条件ジャンプ
- `JR n` - 相対ジャンプ
- `JR cc, n` - 条件相対ジャンプ
- `CALL nn` - 関数呼び出し
- `RET` - 関数復帰

#### 算術演算命令
- `INC r` / `DEC r` - インクリメント/デクリメント
- `INC rr` / `DEC rr` - 16ビット演算
- `CP r` - 比較演算

#### スタック操作
- `PUSH rr` / `POP rr` - スタック操作
- `CALL` / `RET` - 関数呼び出しとスタック

#### ビット操作
- `BIT n, r` - ビットテスト
- `RL r` - 左ローテート

## 開発状況

- [x] 基本プロジェクト構造
- [x] CPU基本実装 (レジスタ、基本命令)
- [x] メモリ管理 (MMU、バンク切り替え)
- [x] ブートROM対応
- [x] 包括的命令セット実装
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

## 動作確認

現在の実装では以下が動作します：

1. **ブートROM実行**: dmg_bootrom.binの読み込みと実行
2. **ゲームROM実行**: big2small.gbなどのGame Boyカートリッジ
3. **VRAMクリア**: 背景タイルメモリの初期化
4. **LCD表示**: グラフィック出力ウィンドウの表示
5. **PPUタイミング**: 正確なスキャンライン処理
6. **CPU命令実行**: ゲーム開始から実際のコード実行

### 実行例

#### ブートROM実行
```bash
uv run python main.py roms/dmg_bootrom.bin --debug
```

#### ゲームROM実行
```bash
uv run python main.py roms/big2small.gb --debug
```

実行すると：
- Pygameウィンドウが開く（640x576ピクセル）
- ブートROMまたはゲームROMが実行される
- CPUとPPUの状態がコンソールに表示される（デバッグモード）
- LCDスキャンラインが正常に動作する
- 実際のGame Boyゲームグラフィックが表示される

## テストROM

### 対応ROM
- **dmg_bootrom.bin**: オリジナルGame Boyブートロム（256バイト）
- **big2small.gb**: GPLライセンスのテストゲーム

### big2small.gb について
- **開発者**: [MDSteele](https://mdsteele.itch.io/)
- **入手先**: [https://mdsteele.itch.io/big2small](https://mdsteele.itch.io/big2small)
- **ライセンス**: GPL（GNU General Public License）
- **説明**: Game Boy用パズルゲーム、エミュレータのテストに適している

### ROM配置
```
roms/
├── dmg_bootrom.bin    # ブートロム
└── big2small.gb      # テストゲーム
```

## 依存関係

- **pygame>=2.6.1**: グラフィック出力とウィンドウ管理

## ライセンス

このプロジェクトは教育目的で作成されています。

含まれるROMファイル：
- `dmg_bootrom.bin`: [Gameboy-free_bootrom](https://github.com/take44444/Gameboy-free_bootrom)より
- `big2small.gb`: GPLライセンスでリリースされたテストゲーム

## 参考資料

- [Game Boy CPU Manual](http://www.codeslinger.co.uk/pages/projects/gameboy/files/GB.pdf)
- [Game Boy Development Wiki](https://gbdev.gg8.se/wiki/articles/Main_Page)
- [Pan Docs](https://gbdev.io/pandocs/)
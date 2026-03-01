#!/usr/bin/env python3
"""Game Boy Emulator MCP Server

LLMからGame Boyエミュレータをプログラム的に操作するためのMCPサーバー。
ROMロード、ステップ実行、スクリーンショット取得、メモリ読み書き、ジョイパッド操作が可能。
"""
from mcp.server.fastmcp import FastMCP
import base64
import io
import os
import sys

# プロジェクトルートをパスに追加
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

mcp = FastMCP("gameboy-emulator")

# グローバル状態
_gb = None
_rom_path_saved = None

CYCLES_PER_FRAME = 70224


def _get_gb():
    """エミュレータインスタンスを取得（未初期化時はエラー）"""
    if _gb is None:
        raise RuntimeError("ROMがロードされていません。先にgb_load_romを呼んでください。")
    return _gb


# ============================================================================
# エミュレータ管理
# ============================================================================

@mcp.tool()
def gb_load_rom(rom_path: str, use_boot_rom: bool = False) -> dict:
    """Game Boy ROMをロードする。ROMヘッダ情報を返す。

    Args:
        rom_path: ROMファイルのパス
        use_boot_rom: ブートROMを使用するか（デフォルト: False）
    """
    global _gb, _rom_path_saved
    from src.gameboy.emulator import GameBoy

    _gb = GameBoy(debug=False, batch_mode=True, headless=True)
    _gb.load_rom(rom_path, use_boot_rom=use_boot_rom)
    _rom_path_saved = rom_path

    # ROMヘッダからタイトル取得
    title = bytes(_gb.memory.rom[0x134:0x144]).decode('ascii', errors='ignore').rstrip('\x00')
    rom_size = len(_gb.memory.rom)
    cart_type = _gb.memory.rom[0x147]
    rom_banks = _gb.memory.rom_banks if hasattr(_gb.memory, 'rom_banks') else 1

    return {
        "status": "ok",
        "title": title,
        "size": rom_size,
        "cartridge_type": f"0x{cart_type:02X}",
        "rom_banks": rom_banks,
        "pc": f"0x{_gb.cpu.pc:04X}",
    }


@mcp.tool()
def gb_reset() -> dict:
    """エミュレータをリセットしてROMを再ロードする。"""
    global _gb
    if _rom_path_saved is None:
        raise RuntimeError("ROMがロードされていません。")
    from src.gameboy.emulator import GameBoy

    _gb = GameBoy(debug=False, batch_mode=True, headless=True)
    _gb.load_rom(_rom_path_saved)
    return {"status": "ok", "pc": f"0x{_gb.cpu.pc:04X}"}


# ============================================================================
# 実行制御
# ============================================================================

@mcp.tool()
def gb_step(count: int = 1) -> dict:
    """N個のCPU命令をステップ実行する。

    Args:
        count: 実行する命令数（デフォルト: 1）
    """
    gb = _get_gb()
    total_cycles = 0
    for _ in range(count):
        total_cycles += gb.step()
    return {
        "cycles_executed": total_cycles,
        "instructions": count,
        **_cpu_state_dict(gb),
    }


@mcp.tool()
def gb_run_frames(count: int = 1) -> dict:
    """Nフレーム分実行する（1フレーム = 70224サイクル）。

    Args:
        count: 実行するフレーム数（デフォルト: 1）
    """
    gb = _get_gb()
    total_cycles = 0
    for _ in range(count):
        frame_cycles = 0
        while frame_cycles < CYCLES_PER_FRAME:
            frame_cycles += gb.step()
        total_cycles += frame_cycles
    return {
        "frames": count,
        "cycles_executed": total_cycles,
        "pc": f"0x{gb.cpu.pc:04X}",
        "ly": gb.ppu.get_ly(),
    }


@mcp.tool()
def gb_run_until(condition: str, max_cycles: int = 10_000_000) -> dict:
    """指定条件を満たすまで実行する。

    Args:
        condition: 停止条件。以下の形式をサポート:
            - "vblank": 次のV-Blank（scanline==144）まで
            - "serial:<text>": シリアル出力に<text>が含まれるまで
            - "pc:0xNNNN": PCが指定アドレスに到達するまで
            - "mem:0xNNNN:0xNN": 指定メモリアドレスが指定値になるまで
        max_cycles: 最大実行サイクル数（デフォルト: 10,000,000）
    """
    gb = _get_gb()
    total_cycles = 0
    met = False

    # 条件パーサー
    if condition == "vblank":
        check = lambda: gb.ppu.get_ly() == 144 and gb.ppu.mode == 1
    elif condition.startswith("serial:"):
        target_text = condition[7:]
        check = lambda: target_text in gb.serial.get_output_text()
    elif condition.startswith("pc:"):
        target_pc = int(condition[3:], 16)
        check = lambda: gb.cpu.pc == target_pc
    elif condition.startswith("mem:"):
        parts = condition[4:].split(":")
        addr = int(parts[0], 16)
        val = int(parts[1], 16)
        check = lambda: gb.memory.read_byte(addr) == val
    else:
        raise ValueError(f"不明な条件: {condition}。vblank, serial:<text>, pc:0xNNNN, mem:0xNNNN:0xNN を使用してください。")

    while total_cycles < max_cycles:
        total_cycles += gb.step()
        if check():
            met = True
            break

    return {
        "condition_met": met,
        "condition": condition,
        "cycles_executed": total_cycles,
        "pc": f"0x{gb.cpu.pc:04X}",
    }


# ============================================================================
# 状態取得
# ============================================================================

def _cpu_state_dict(gb):
    """CPU状態を辞書として返すヘルパー"""
    cpu = gb.cpu
    f_val = ((0x80 if cpu.flag_z else 0) |
             (0x40 if cpu.flag_n else 0) |
             (0x20 if cpu.flag_h else 0) |
             (0x10 if cpu.flag_c else 0))
    return {
        "pc": f"0x{cpu.pc:04X}",
        "sp": f"0x{cpu.sp:04X}",
        "a": f"0x{cpu.a:02X}",
        "f": f"0x{f_val:02X}",
        "b": f"0x{cpu.b:02X}",
        "c": f"0x{cpu.c:02X}",
        "d": f"0x{cpu.d:02X}",
        "e": f"0x{cpu.e:02X}",
        "h": f"0x{cpu.h:02X}",
        "l": f"0x{cpu.l:02X}",
        "flags": {
            "z": cpu.flag_z,
            "n": cpu.flag_n,
            "h": cpu.flag_h,
            "c": cpu.flag_c,
        },
        "ime": cpu.interrupt_master_enable,
        "halted": cpu.halted,
        "cycles": cpu.cycles,
    }


@mcp.tool()
def gb_get_cpu_state() -> dict:
    """CPU状態を取得する（全レジスタ、フラグ、PC、SP、サイクル数、IME、halt状態）。"""
    gb = _get_gb()
    return _cpu_state_dict(gb)


@mcp.tool()
def gb_get_ppu_state() -> dict:
    """PPU状態を取得する（スキャンライン、モード、LCDC、STAT等）。"""
    gb = _get_gb()
    ppu = gb.ppu
    lcdc = ppu.get_lcdc()
    stat = ppu.get_stat()
    return {
        "scanline": ppu.get_ly(),
        "mode": ppu.mode,
        "lcdc": f"0x{lcdc:02X}",
        "stat": f"0x{stat:02X}",
        "cycles": ppu.cycles,
        "lcdc_flags": {
            "lcd_enable": bool(lcdc & 0x80),
            "window_tilemap": "9C00" if lcdc & 0x40 else "9800",
            "window_enable": bool(lcdc & 0x20),
            "tile_data": "8000" if lcdc & 0x10 else "8800",
            "bg_tilemap": "9C00" if lcdc & 0x08 else "9800",
            "sprite_size": "8x16" if lcdc & 0x04 else "8x8",
            "sprite_enable": bool(lcdc & 0x02),
            "bg_enable": bool(lcdc & 0x01),
        },
    }


@mcp.tool()
def gb_read_memory(address: int, length: int = 1) -> dict:
    """メモリを読み取る。

    Args:
        address: 読み取り開始アドレス（0x0000-0xFFFF）
        length: 読み取りバイト数（デフォルト: 1、最大256）
    """
    gb = _get_gb()
    if length > 256:
        length = 256
    data = [gb.memory.read_byte((address + i) & 0xFFFF) for i in range(length)]
    hex_str = " ".join(f"{b:02X}" for b in data)
    return {
        "address": f"0x{address:04X}",
        "length": length,
        "hex": hex_str,
        "values": data,
    }


@mcp.tool()
def gb_get_serial_output(clear: bool = False) -> dict:
    """シリアル出力テキストを取得する。

    Args:
        clear: 取得後にバッファをクリアするか（デフォルト: False）
    """
    gb = _get_gb()
    text = gb.serial.get_output_text()
    if clear:
        gb.serial.clear_output()
    return {
        "text": text,
        "length": len(text),
    }


# ============================================================================
# 状態変更
# ============================================================================

@mcp.tool()
def gb_write_memory(address: int, values: list[int]) -> dict:
    """メモリに書き込む。

    Args:
        address: 書き込み開始アドレス
        values: 書き込むバイト値のリスト（0-255）
    """
    gb = _get_gb()
    for i, val in enumerate(values):
        gb.memory.write_byte((address + i) & 0xFFFF, val & 0xFF)
    return {
        "address": f"0x{address:04X}",
        "bytes_written": len(values),
    }


@mcp.tool()
def gb_set_register(register: str, value: int) -> dict:
    """CPUレジスタを設定する。

    Args:
        register: レジスタ名（a, b, c, d, e, h, l, sp, pc）
        value: 設定する値
    """
    gb = _get_gb()
    cpu = gb.cpu
    reg = register.lower()

    reg_map_8bit = {"a", "b", "c", "d", "e", "h", "l"}
    reg_map_16bit = {"sp", "pc"}

    if reg in reg_map_8bit:
        setattr(cpu, reg, value & 0xFF)
        if reg in ("h", "l"):
            cpu.hl = (cpu.h << 8) | cpu.l
    elif reg in reg_map_16bit:
        setattr(cpu, reg, value & 0xFFFF)
    else:
        raise ValueError(f"不明なレジスタ: {register}。a, b, c, d, e, h, l, sp, pc を使用してください。")

    return {"register": reg, "value": f"0x{getattr(cpu, reg):04X}" if reg in reg_map_16bit else f"0x{getattr(cpu, reg):02X}"}


# ============================================================================
# 入力
# ============================================================================

_BUTTON_MAP = {
    "a": ("button", 0),
    "b": ("button", 1),
    "select": ("button", 2),
    "start": ("button", 3),
    "right": ("direction", 0),
    "left": ("direction", 1),
    "up": ("direction", 2),
    "down": ("direction", 3),
}


@mcp.tool()
def gb_joypad_press(buttons: list[str]) -> dict:
    """ジョイパッドのボタン/方向キーを押下する。

    Args:
        buttons: 押すボタンのリスト。値: "a", "b", "start", "select", "up", "down", "left", "right"
    """
    gb = _get_gb()
    pressed = []
    for btn in buttons:
        key = btn.lower()
        if key not in _BUTTON_MAP:
            raise ValueError(f"不明なボタン: {btn}。{list(_BUTTON_MAP.keys())} を使用してください。")
        kind, idx = _BUTTON_MAP[key]
        if kind == "button":
            gb.memory.press_button(idx)
        else:
            gb.memory.press_direction(idx)
        pressed.append(key)
    return {"pressed": pressed}


@mcp.tool()
def gb_joypad_release(buttons: list[str]) -> dict:
    """ジョイパッドのボタン/方向キーを解放する。

    Args:
        buttons: 解放するボタンのリスト。値: "a", "b", "start", "select", "up", "down", "left", "right"
    """
    gb = _get_gb()
    released = []
    for btn in buttons:
        key = btn.lower()
        if key not in _BUTTON_MAP:
            raise ValueError(f"不明なボタン: {btn}。{list(_BUTTON_MAP.keys())} を使用してください。")
        kind, idx = _BUTTON_MAP[key]
        if kind == "button":
            gb.memory.release_button(idx)
        else:
            gb.memory.release_direction(idx)
        released.append(key)
    return {"released": released}


# ============================================================================
# グラフィック
# ============================================================================

@mcp.tool()
def gb_screenshot() -> str:
    """現在のフレームバッファをbase64エンコードPNG画像で返す。"""
    from PIL import Image
    import numpy as np

    gb = _get_gb()
    palette = [(224, 248, 208), (136, 192, 112), (52, 104, 86), (8, 24, 32)]
    palette_array = np.array(palette, dtype=np.uint8)

    # frame_buffer のカラーインデックスをRGBに変換
    buf = np.clip(gb.ppu.frame_buffer, 0, 3)
    rgb = palette_array[buf]
    img = Image.fromarray(rgb, 'RGB')

    out = io.BytesIO()
    img.save(out, format='PNG')
    return base64.b64encode(out.getvalue()).decode()


# ============================================================================
# デバッグ
# ============================================================================

# 主要なopcodeのニーモニックテーブル（簡易逆アセンブラ用）
# (ニーモニック, バイト長)
_OPCODES = {
    0x00: ("NOP", 1), 0x01: ("LD BC,d16", 3), 0x02: ("LD (BC),A", 1), 0x03: ("INC BC", 1),
    0x04: ("INC B", 1), 0x05: ("DEC B", 1), 0x06: ("LD B,d8", 2), 0x07: ("RLCA", 1),
    0x08: ("LD (a16),SP", 3), 0x09: ("ADD HL,BC", 1), 0x0A: ("LD A,(BC)", 1), 0x0B: ("DEC BC", 1),
    0x0C: ("INC C", 1), 0x0D: ("DEC C", 1), 0x0E: ("LD C,d8", 2), 0x0F: ("RRCA", 1),
    0x10: ("STOP", 2), 0x11: ("LD DE,d16", 3), 0x12: ("LD (DE),A", 1), 0x13: ("INC DE", 1),
    0x14: ("INC D", 1), 0x15: ("DEC D", 1), 0x16: ("LD D,d8", 2), 0x17: ("RLA", 1),
    0x18: ("JR r8", 2), 0x19: ("ADD HL,DE", 1), 0x1A: ("LD A,(DE)", 1), 0x1B: ("DEC DE", 1),
    0x1C: ("INC E", 1), 0x1D: ("DEC E", 1), 0x1E: ("LD E,d8", 2), 0x1F: ("RRA", 1),
    0x20: ("JR NZ,r8", 2), 0x21: ("LD HL,d16", 3), 0x22: ("LD (HL+),A", 1), 0x23: ("INC HL", 1),
    0x24: ("INC H", 1), 0x25: ("DEC H", 1), 0x26: ("LD H,d8", 2), 0x27: ("DAA", 1),
    0x28: ("JR Z,r8", 2), 0x29: ("ADD HL,HL", 1), 0x2A: ("LD A,(HL+)", 1), 0x2B: ("DEC HL", 1),
    0x2C: ("INC L", 1), 0x2D: ("DEC L", 1), 0x2E: ("LD L,d8", 2), 0x2F: ("CPL", 1),
    0x30: ("JR NC,r8", 2), 0x31: ("LD SP,d16", 3), 0x32: ("LD (HL-),A", 1), 0x33: ("INC SP", 1),
    0x34: ("INC (HL)", 1), 0x35: ("DEC (HL)", 1), 0x36: ("LD (HL),d8", 2), 0x37: ("SCF", 1),
    0x38: ("JR C,r8", 2), 0x39: ("ADD HL,SP", 1), 0x3A: ("LD A,(HL-)", 1), 0x3B: ("DEC SP", 1),
    0x3C: ("INC A", 1), 0x3D: ("DEC A", 1), 0x3E: ("LD A,d8", 2), 0x3F: ("CCF", 1),
    0x40: ("LD B,B", 1), 0x41: ("LD B,C", 1), 0x42: ("LD B,D", 1), 0x43: ("LD B,E", 1),
    0x44: ("LD B,H", 1), 0x45: ("LD B,L", 1), 0x46: ("LD B,(HL)", 1), 0x47: ("LD B,A", 1),
    0x48: ("LD C,B", 1), 0x49: ("LD C,C", 1), 0x4A: ("LD C,D", 1), 0x4B: ("LD C,E", 1),
    0x4C: ("LD C,H", 1), 0x4D: ("LD C,L", 1), 0x4E: ("LD C,(HL)", 1), 0x4F: ("LD C,A", 1),
    0x50: ("LD D,B", 1), 0x51: ("LD D,C", 1), 0x52: ("LD D,D", 1), 0x53: ("LD D,E", 1),
    0x54: ("LD D,H", 1), 0x55: ("LD D,L", 1), 0x56: ("LD D,(HL)", 1), 0x57: ("LD D,A", 1),
    0x58: ("LD E,B", 1), 0x59: ("LD E,C", 1), 0x5A: ("LD E,D", 1), 0x5B: ("LD E,E", 1),
    0x5C: ("LD E,H", 1), 0x5D: ("LD E,L", 1), 0x5E: ("LD E,(HL)", 1), 0x5F: ("LD E,A", 1),
    0x60: ("LD H,B", 1), 0x61: ("LD H,C", 1), 0x62: ("LD H,D", 1), 0x63: ("LD H,E", 1),
    0x64: ("LD H,H", 1), 0x65: ("LD H,L", 1), 0x66: ("LD H,(HL)", 1), 0x67: ("LD H,A", 1),
    0x68: ("LD L,B", 1), 0x69: ("LD L,C", 1), 0x6A: ("LD L,D", 1), 0x6B: ("LD L,E", 1),
    0x6C: ("LD L,H", 1), 0x6D: ("LD L,L", 1), 0x6E: ("LD L,(HL)", 1), 0x6F: ("LD L,A", 1),
    0x70: ("LD (HL),B", 1), 0x71: ("LD (HL),C", 1), 0x72: ("LD (HL),D", 1), 0x73: ("LD (HL),E", 1),
    0x74: ("LD (HL),H", 1), 0x75: ("LD (HL),L", 1), 0x76: ("HALT", 1), 0x77: ("LD (HL),A", 1),
    0x78: ("LD A,B", 1), 0x79: ("LD A,C", 1), 0x7A: ("LD A,D", 1), 0x7B: ("LD A,E", 1),
    0x7C: ("LD A,H", 1), 0x7D: ("LD A,L", 1), 0x7E: ("LD A,(HL)", 1), 0x7F: ("LD A,A", 1),
    0x80: ("ADD A,B", 1), 0x81: ("ADD A,C", 1), 0x82: ("ADD A,D", 1), 0x83: ("ADD A,E", 1),
    0x84: ("ADD A,H", 1), 0x85: ("ADD A,L", 1), 0x86: ("ADD A,(HL)", 1), 0x87: ("ADD A,A", 1),
    0x88: ("ADC A,B", 1), 0x89: ("ADC A,C", 1), 0x8A: ("ADC A,D", 1), 0x8B: ("ADC A,E", 1),
    0x8C: ("ADC A,H", 1), 0x8D: ("ADC A,L", 1), 0x8E: ("ADC A,(HL)", 1), 0x8F: ("ADC A,A", 1),
    0x90: ("SUB B", 1), 0x91: ("SUB C", 1), 0x92: ("SUB D", 1), 0x93: ("SUB E", 1),
    0x94: ("SUB H", 1), 0x95: ("SUB L", 1), 0x96: ("SUB (HL)", 1), 0x97: ("SUB A", 1),
    0x98: ("SBC A,B", 1), 0x99: ("SBC A,C", 1), 0x9A: ("SBC A,D", 1), 0x9B: ("SBC A,E", 1),
    0x9C: ("SBC A,H", 1), 0x9D: ("SBC A,L", 1), 0x9E: ("SBC A,(HL)", 1), 0x9F: ("SBC A,A", 1),
    0xA0: ("AND B", 1), 0xA1: ("AND C", 1), 0xA2: ("AND D", 1), 0xA3: ("AND E", 1),
    0xA4: ("AND H", 1), 0xA5: ("AND L", 1), 0xA6: ("AND (HL)", 1), 0xA7: ("AND A", 1),
    0xA8: ("XOR B", 1), 0xA9: ("XOR C", 1), 0xAA: ("XOR D", 1), 0xAB: ("XOR E", 1),
    0xAC: ("XOR H", 1), 0xAD: ("XOR L", 1), 0xAE: ("XOR (HL)", 1), 0xAF: ("XOR A", 1),
    0xB0: ("OR B", 1), 0xB1: ("OR C", 1), 0xB2: ("OR D", 1), 0xB3: ("OR E", 1),
    0xB4: ("OR H", 1), 0xB5: ("OR L", 1), 0xB6: ("OR (HL)", 1), 0xB7: ("OR A", 1),
    0xB8: ("CP B", 1), 0xB9: ("CP C", 1), 0xBA: ("CP D", 1), 0xBB: ("CP E", 1),
    0xBC: ("CP H", 1), 0xBD: ("CP L", 1), 0xBE: ("CP (HL)", 1), 0xBF: ("CP A", 1),
    0xC0: ("RET NZ", 1), 0xC1: ("POP BC", 1), 0xC2: ("JP NZ,a16", 3), 0xC3: ("JP a16", 3),
    0xC4: ("CALL NZ,a16", 3), 0xC5: ("PUSH BC", 1), 0xC6: ("ADD A,d8", 2), 0xC7: ("RST 00H", 1),
    0xC8: ("RET Z", 1), 0xC9: ("RET", 1), 0xCA: ("JP Z,a16", 3), 0xCB: ("PREFIX CB", 2),
    0xCC: ("CALL Z,a16", 3), 0xCD: ("CALL a16", 3), 0xCE: ("ADC A,d8", 2), 0xCF: ("RST 08H", 1),
    0xD0: ("RET NC", 1), 0xD1: ("POP DE", 1), 0xD2: ("JP NC,a16", 3), 0xD4: ("CALL NC,a16", 3),
    0xD5: ("PUSH DE", 1), 0xD6: ("SUB d8", 2), 0xD7: ("RST 10H", 1),
    0xD8: ("RET C", 1), 0xD9: ("RETI", 1), 0xDA: ("JP C,a16", 3), 0xDC: ("CALL C,a16", 3),
    0xDE: ("SBC A,d8", 2), 0xDF: ("RST 18H", 1),
    0xE0: ("LDH (a8),A", 2), 0xE1: ("POP HL", 1), 0xE2: ("LD (C),A", 1), 0xE5: ("PUSH HL", 1),
    0xE6: ("AND d8", 2), 0xE7: ("RST 20H", 1), 0xE8: ("ADD SP,r8", 2), 0xE9: ("JP (HL)", 1),
    0xEA: ("LD (a16),A", 3), 0xEE: ("XOR d8", 2), 0xEF: ("RST 28H", 1),
    0xF0: ("LDH A,(a8)", 2), 0xF1: ("POP AF", 1), 0xF2: ("LD A,(C)", 1), 0xF3: ("DI", 1),
    0xF5: ("PUSH AF", 1), 0xF6: ("OR d8", 2), 0xF7: ("RST 30H", 1),
    0xF8: ("LD HL,SP+r8", 2), 0xF9: ("LD SP,HL", 1), 0xFA: ("LD A,(a16)", 3),
    0xFB: ("EI", 1), 0xFE: ("CP d8", 2), 0xFF: ("RST 38H", 1),
}

# CB接頭辞opcodeのニーモニック生成
_CB_OPS = ["RLC", "RRC", "RL", "RR", "SLA", "SRA", "SWAP", "SRL",
           "BIT 0,", "BIT 1,", "BIT 2,", "BIT 3,", "BIT 4,", "BIT 5,", "BIT 6,", "BIT 7,",
           "RES 0,", "RES 1,", "RES 2,", "RES 3,", "RES 4,", "RES 5,", "RES 6,", "RES 7,",
           "SET 0,", "SET 1,", "SET 2,", "SET 3,", "SET 4,", "SET 5,", "SET 6,", "SET 7,"]
_CB_REGS = ["B", "C", "D", "E", "H", "L", "(HL)", "A"]

_CB_OPCODES = {}
for i in range(256):
    op = _CB_OPS[i >> 3]
    reg = _CB_REGS[i & 7]
    if op.endswith(","):
        _CB_OPCODES[i] = f"{op}{reg}"
    else:
        _CB_OPCODES[i] = f"{op} {reg}"


def _disassemble_at(gb, addr, count):
    """指定アドレスからcount命令分を逆アセンブルする"""
    result = []
    pos = addr
    for _ in range(count):
        if pos > 0xFFFF:
            break
        opcode = gb.memory.read_byte(pos)

        if opcode == 0xCB:
            cb_op = gb.memory.read_byte((pos + 1) & 0xFFFF)
            mnemonic = f"CB {_CB_OPCODES.get(cb_op, f'??? 0x{cb_op:02X}')}"
            length = 2
        elif opcode in _OPCODES:
            mnemonic, length = _OPCODES[opcode]
            # オペランドを実際の値に置換
            if length == 2:
                operand = gb.memory.read_byte((pos + 1) & 0xFFFF)
                if "r8" in mnemonic:
                    # 符号付きオフセット
                    signed = operand if operand < 128 else operand - 256
                    target = (pos + 2 + signed) & 0xFFFF
                    mnemonic = mnemonic.replace("r8", f"0x{target:04X}")
                elif "a8" in mnemonic:
                    mnemonic = mnemonic.replace("a8", f"0x{operand:02X}")
                elif "d8" in mnemonic:
                    mnemonic = mnemonic.replace("d8", f"0x{operand:02X}")
            elif length == 3:
                lo = gb.memory.read_byte((pos + 1) & 0xFFFF)
                hi = gb.memory.read_byte((pos + 2) & 0xFFFF)
                word = (hi << 8) | lo
                if "a16" in mnemonic:
                    mnemonic = mnemonic.replace("a16", f"0x{word:04X}")
                elif "d16" in mnemonic:
                    mnemonic = mnemonic.replace("d16", f"0x{word:04X}")
        else:
            mnemonic = f"??? 0x{opcode:02X}"
            length = 1

        raw_bytes = " ".join(f"{gb.memory.read_byte((pos + i) & 0xFFFF):02X}" for i in range(length))
        result.append({
            "address": f"0x{pos:04X}",
            "bytes": raw_bytes,
            "mnemonic": mnemonic,
        })
        pos = (pos + length) & 0xFFFF
    return result


@mcp.tool()
def gb_disassemble(address: int | None = None, count: int = 10) -> dict:
    """指定アドレスからN命令を逆アセンブルする。

    Args:
        address: 開始アドレス（省略時は現在のPC）
        count: 逆アセンブルする命令数（デフォルト: 10）
    """
    gb = _get_gb()
    if address is None:
        address = gb.cpu.pc
    instructions = _disassemble_at(gb, address, count)
    return {
        "start_address": f"0x{address:04X}",
        "instructions": instructions,
    }


@mcp.tool()
def gb_get_tiles(start: int = 0, count: int = 16) -> dict:
    """VRAMタイルデータを取得する。各タイルは8x8ピクセルで、2bppエンコード。

    Args:
        start: 開始タイルインデックス（デフォルト: 0）
        count: 取得するタイル数（デフォルト: 16、最大384）
    """
    gb = _get_gb()
    if count > 384:
        count = 384
    tiles = []
    for tile_idx in range(start, start + count):
        tile_addr = 0x8000 + (tile_idx * 16)
        tile_data = []
        for row in range(8):
            lo = gb.memory.read_byte(tile_addr + row * 2)
            hi = gb.memory.read_byte(tile_addr + row * 2 + 1)
            pixels = []
            for bit in range(7, -1, -1):
                color = ((hi >> bit) & 1) << 1 | ((lo >> bit) & 1)
                pixels.append(color)
            tile_data.append(pixels)
        tiles.append({
            "index": tile_idx,
            "address": f"0x{tile_addr:04X}",
            "pixels": tile_data,
        })
    return {
        "start": start,
        "count": len(tiles),
        "tiles": tiles,
    }


# ============================================================================
# エントリーポイント
# ============================================================================

if __name__ == "__main__":
    mcp.run()

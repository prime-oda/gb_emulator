#!/usr/bin/env python3
"""Ollama MCP Client for Game Boy Emulator

OllamaのローカルLLMを通じてGame Boyエミュレータを自然言語で操作する対話型クライアント。
MCPサーバー(mcp_server.py)をサブプロセスとして起動し、Ollamaのtool calling機能で接続する。

使用方法:
    uv run python mcp_client.py
    uv run python mcp_client.py --model llama3.1
    uv run python mcp_client.py --model qwen2.5 --server-command python --server-args mcp_server.py
"""
import argparse
import asyncio
import base64
import json
import os
import re
import sys
import tempfile

import ollama
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

SYSTEM_PROMPT = """\
あなたはGame Boyエミュレータの操作アシスタントです。
ユーザーの自然言語による指示に従い、提供されたツールを使ってGame Boyエミュレータを操作します。

基本的な操作フロー:
1. gb_load_rom でROMをロード（例: "roms/test/cpu_instrs/individual/01-special.gb"）
2. gb_step / gb_run_frames / gb_run_until で実行
3. gb_get_cpu_state / gb_get_ppu_state / gb_read_memory で状態確認
4. gb_screenshot でスクリーンショット取得
5. gb_joypad_press / gb_joypad_release でボタン操作
6. gb_disassemble で逆アセンブル

注意事項:
- ROMパスはプロジェクトルートからの相対パスで指定してください
- ジョイパッドのボタン名: a, b, start, select, up, down, left, right
- メモリアドレスは16進数（例: 0xFF44）で指定します
- gb_run_until の条件: "vblank", "serial:<text>", "pc:0xNNNN", "mem:0xNNNN:0xNN"
"""

MAX_HISTORY = 50
MAX_TOOL_RESULT_CHARS = 4000


def _parse_arg_descriptions(docstring: str) -> dict[str, str]:
    """docstringのArgs:セクションからパラメータ説明を抽出する"""
    descriptions = {}
    if not docstring:
        return descriptions

    in_args = False
    for line in docstring.split("\n"):
        stripped = line.strip()
        if stripped == "Args:":
            in_args = True
            continue
        if in_args:
            if not stripped or (not line.startswith("    ") and not line.startswith("\t") and stripped):
                if not stripped.startswith("-") and ":" not in stripped[:30]:
                    break
            match = re.match(r"\s+(\w+)\s*[:]\s*(.*)", line)
            if match:
                descriptions[match.group(1)] = match.group(2).strip()
    return descriptions


def _clean_description(docstring: str) -> str:
    """Args:セクションを除去した説明文を返す"""
    if not docstring:
        return ""
    lines = []
    for line in docstring.split("\n"):
        if line.strip() == "Args:":
            break
        lines.append(line)
    return "\n".join(lines).strip()


def convert_mcp_tools_to_ollama(mcp_tools: list) -> list[dict]:
    """MCPツールリストをOllama tools形式に変換する"""
    ollama_tools = []
    for tool in mcp_tools:
        description = _clean_description(tool.description or "")
        arg_descriptions = _parse_arg_descriptions(tool.description or "")

        schema = tool.inputSchema or {}
        properties = schema.get("properties", {})
        required = schema.get("required", [])

        ollama_properties = {}
        for prop_name, prop_schema in properties.items():
            prop = dict(prop_schema)
            if prop_name in arg_descriptions and "description" not in prop:
                prop["description"] = arg_descriptions[prop_name]
            ollama_properties[prop_name] = prop

        ollama_tools.append({
            "type": "function",
            "function": {
                "name": tool.name,
                "description": description,
                "parameters": {
                    "type": "object",
                    "properties": ollama_properties,
                    "required": required,
                },
            },
        })
    return ollama_tools


async def execute_tool(session: ClientSession, name: str, args: dict) -> str:
    """MCPツールを実行し、結果をフォーマットして返す"""
    try:
        result = await session.call_tool(name, args)
    except Exception as e:
        return f"[エラー] ツール '{name}' の実行に失敗: {e}"

    texts = []
    for content in result.content:
        if hasattr(content, "text"):
            texts.append(content.text)

    combined = "\n".join(texts)

    # スクリーンショットの場合: base64デコード → 一時PNGファイルに保存
    if name == "gb_screenshot" and combined:
        try:
            # JSON形式でない場合は直接base64データとして扱う
            try:
                data = json.loads(combined)
                b64_data = data if isinstance(data, str) else combined
            except (json.JSONDecodeError, TypeError):
                b64_data = combined

            png_bytes = base64.b64decode(b64_data)
            tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False, prefix="gb_screenshot_")
            tmp.write(png_bytes)
            tmp.close()
            return f"スクリーンショットを保存しました: {tmp.name}"
        except Exception as e:
            return f"スクリーンショット保存エラー: {e}"

    if len(combined) > MAX_TOOL_RESULT_CHARS:
        combined = combined[:MAX_TOOL_RESULT_CHARS] + "\n... (結果が長すぎるため切り詰め)"

    return combined


def _trim_history(messages: list) -> list:
    """メッセージ履歴をsystemプロンプト＋最新MAX_HISTORYメッセージに制限"""
    if len(messages) <= MAX_HISTORY + 1:
        return messages
    # systemメッセージを保持し、最新のメッセージだけ残す
    system_msgs = [m for m in messages if m.get("role") == "system"]
    non_system = [m for m in messages if m.get("role") != "system"]
    return system_msgs + non_system[-MAX_HISTORY:]


async def main(model: str, server_command: str, server_args: list[str]):
    """メインの非同期REPLループ"""
    print(f"Game Boy Emulator MCP Client")
    print(f"モデル: {model}")
    print(f"MCPサーバー: {server_command} {' '.join(server_args)}")
    print(f"終了: 'quit' または Ctrl+C")
    print("-" * 50)

    server_params = StdioServerParameters(
        command=server_command,
        args=server_args,
        cwd=os.path.dirname(os.path.abspath(__file__)),
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            tools_result = await session.list_tools()
            mcp_tools = tools_result.tools
            ollama_tools = convert_mcp_tools_to_ollama(mcp_tools)

            print(f"利用可能なツール ({len(ollama_tools)}個):")
            for t in ollama_tools:
                print(f"  - {t['function']['name']}: {t['function']['description'][:60]}")
            print("-" * 50)

            messages = [{"role": "system", "content": SYSTEM_PROMPT}]

            while True:
                try:
                    user_input = input("\nあなた> ").strip()
                except (EOFError, KeyboardInterrupt):
                    print("\n終了します。")
                    break

                if not user_input:
                    continue
                if user_input.lower() in ("quit", "exit", "q"):
                    print("終了します。")
                    break

                messages.append({"role": "user", "content": user_input})
                messages = _trim_history(messages)

                # ツール呼び出しループ
                while True:
                    try:
                        response = ollama.chat(
                            model=model,
                            messages=messages,
                            tools=ollama_tools,
                        )
                    except ollama.ResponseError as e:
                        if "not found" in str(e).lower():
                            print(f"\n[エラー] モデル '{model}' が見つかりません。")
                            print(f"  → ollama pull {model} を実行してください。")
                        else:
                            print(f"\n[Ollamaエラー] {e}")
                        # エラー時はユーザー入力に戻る
                        messages.pop()
                        break
                    except Exception as e:
                        err_str = str(e).lower()
                        if "connection" in err_str or "refused" in err_str:
                            print("\n[エラー] Ollamaに接続できません。")
                            print("  → ollama serve を実行してサーバーを起動してください。")
                        else:
                            print(f"\n[エラー] {e}")
                        messages.pop()
                        break

                    msg = response.message

                    if not msg.tool_calls:
                        # テキスト応答
                        content = msg.content or ""
                        print(f"\nアシスタント> {content}")
                        messages.append({"role": "assistant", "content": content})
                        break

                    # ツール呼び出しあり
                    messages.append(msg)
                    for tc in msg.tool_calls:
                        fn_name = tc.function.name
                        fn_args = tc.function.arguments
                        print(f"  [ツール呼び出し] {fn_name}({json.dumps(fn_args, ensure_ascii=False)})")

                        result_text = await execute_tool(session, fn_name, fn_args)
                        print(f"  [結果] {result_text[:200]}{'...' if len(result_text) > 200 else ''}")
                        messages.append({"role": "tool", "content": result_text})


def cli():
    parser = argparse.ArgumentParser(
        description="Ollama MCP Client for Game Boy Emulator",
    )
    parser.add_argument(
        "--model", "-m",
        default="qwen2.5",
        help="Ollamaモデル名（デフォルト: qwen2.5）",
    )
    parser.add_argument(
        "--server-command",
        default="uv",
        help="MCPサーバー起動コマンド（デフォルト: uv）",
    )
    parser.add_argument(
        "--server-args",
        nargs="*",
        default=["run", "python", "mcp_server.py"],
        help="MCPサーバー引数（デフォルト: run python mcp_server.py）",
    )
    args = parser.parse_args()
    asyncio.run(main(args.model, args.server_command, args.server_args))


if __name__ == "__main__":
    cli()

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
演示录制助手：把 `--demo-real` 的输出切成若干屏，**按回车逐屏播放**。

为什么需要它：
  `--demo-real` 一次输出 338 行、13 个模式。直接录屏要么手忙脚乱地滚动窗口，
  要么观众根本来不及看。本工具把输出切成「屏」，你按一下回车翻一屏，
  节奏完全掌控在自己手里，也能随时停下来重录某一屏。

用法：
  python record_demo.py              # 逐屏播放，按回车推进
  python record_demo.py --per 2      # 每屏放 2 个模式（总时长更短）
  python record_demo.py --auto 5     # 每 5 秒自动翻屏（无人值守录屏）
  python record_demo.py --list       # 只看分镜清单，不播放
  python record_demo.py --save       # 导出每屏文本到 demo_out/，当提词器或字幕底稿
  python record_demo.py --save --play  # 导出同时逐屏播放（边录边留稿）

录屏建议：终端窗口调大（120x32 以上）或把字号调到 16px+，确保每屏不用滚动。
零依赖，仅用标准库。
"""
import argparse
import os
import re
import subprocess
import sys
import time

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

BASE = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable


def run(cmd, timeout=120):
    """跑一条命令并 capturing 全部输出（stdout+stderr）。"""
    try:
        r = subprocess.run([PY] + cmd, cwd=BASE, capture_output=True,
                           text=True, encoding="utf-8", errors="replace",
                           timeout=timeout)
        return (r.stdout or "") + (r.stderr or "")
    except subprocess.TimeoutExpired:
        return "⚠️ 命令超时：%s" % " ".join(cmd)
    except Exception as e:
        return "⚠️ 命令失败：%s" % e


def split_blocks(text):
    """把回放输出切成 (头部, [(标题, 正文行)], 尾部)。"""
    lines = text.splitlines()
    first = next((i for i, l in enumerate(lines) if l.startswith("【")), len(lines))
    head = lines[:first]
    rest = lines[first:]

    # 尾部归纳：最后那道分隔线之后属于 footer
    seps = [i for i, l in enumerate(rest) if l.startswith("---")]
    cut = seps[-1] if seps else len(rest)
    body, tail = rest[:cut], rest[cut:]

    blocks, title, cur = [], None, []
    for l in body:
        if l.startswith("【"):
            if title is not None:
                blocks.append((title, cur))
            title, cur = l, [l]
        else:
            cur.append(l)
    if title is not None:
        blocks.append((title, cur))
    return head, blocks, tail


def _count_tests(out):
    """从 unittest 输出里动态取测试条数，避免标题与实际测试数脱节。"""
    for l in out.splitlines():
        m = re.match(r"^Ran (\d+) tests?", l.strip())
        if m:
            return m.group(1)
    return ""


def _clean_tail(lines):
    """去掉纯分隔线，避免最后一屏出现一条孤零零的横线。"""
    out = []
    for l in lines:
        s = l.strip()
        if s and set(s) <= set("-=─ "):
            continue
        out.append(l)
    return out


def test_screen():
    """最后一屏：跑回归测试，只保留「跑了多少条 / 结果是什么」这两行。"""
    out = run(["test_fixes.py"])
    lines = out.splitlines()
    n = _count_tests(out)
    ran = next((l for l in lines if l.strip().startswith("Ran ")), "")
    status = ""
    for l in lines:
        s = l.strip()
        if s == "OK" or s.startswith("OK (") or s.startswith("FAILED"):
            status = s
    keep = [t for t in _clean_tail([ran, status]) if t.strip()]
    if not keep:  # 极端情况：连跑都没跑起来，就把原文尾部亮出来，别粉饰
        keep = [l for l in lines if l.strip("-= ")][-3:]
    title = "【回归测试 · %s 条断言】" % n if n else "【回归测试】"
    return (title, keep)


def render(kind, chunk, head, tail, i, total):
    """把一屏渲染成纯文本。播放与导出共用这一份，保证屏幕与稿子一字不差。"""
    if kind == "head":
        body = "\n".join(head)
    else:
        body = "\n\n".join("\n".join(b) for _t, b in chunk)
    body = body.rstrip()
    if i == total:
        body += "\n" + "\n".join(_clean_tail(tail)).rstrip()
    return body


def save_scenes(scenes, head, tail, outdir):
    """每屏导出成一个 UTF-8(带 BOM) 文本文件，当提词器、字幕底稿或录后复核用。"""
    os.makedirs(outdir, exist_ok=True)
    index = []
    for i, (kind, chunk) in enumerate(scenes, 1):
        title = ("数据出处 / 真实性标注" if kind == "head"
                 else " + ".join(t for t, _ in chunk))
        path = os.path.join(outdir, "%02d.txt" % i)
        body = render(kind, chunk, head, tail, i, len(scenes))
        # utf-8-sig：Windows 记事本也能正确识别；\r\n：粘到任何编辑器都不串行
        with open(path, "w", encoding="utf-8-sig", newline="\r\n") as f:
            f.write(body + "\n")
        index.append("%02d  %s" % (i, title))
    idx = os.path.join(outdir, "00_index.txt")
    with open(idx, "w", encoding="utf-8-sig", newline="\r\n") as f:
        f.write("演示分镜索引（共 %d 屏）\n" % len(scenes))
        f.write("导出时间：%s\n\n" % time.strftime("%Y-%m-%d %H:%M:%S"))
        f.write("\n".join(index) + "\n")
    return outdir, len(scenes)


def clear():
    os.system("cls" if os.name == "nt" else "clear")


def _ask(prompt):
    """等一次回车。没有可用输入时（重定向 / 非交互）返回 False 而不是崩掉。"""
    try:
        input(prompt)
        return True
    except (EOFError, KeyboardInterrupt):
        return False


def _ask_quit(prompt):
    """返回 True 表示继续，False 表示用户要退出。"""
    try:
        return input(prompt).strip().lower() != "q"
    except (EOFError, KeyboardInterrupt):
        return False


def main():
    ap = argparse.ArgumentParser(description="麦麦精算师 · 演示录制助手（逐屏播放）")
    ap.add_argument("--per", type=int, default=1, help="每屏放几个模式（默认 1）")
    ap.add_argument("--auto", type=float, default=0,
                    help="每屏停留秒数自动翻页（>0 时无需按键）")
    ap.add_argument("--list", action="store_true", help="只列分镜清单")
    ap.add_argument("--no-tests", action="store_true", help="末尾不加回归测试那一屏")
    ap.add_argument("--save", nargs="?", const="demo_out", default=None,
                    help="导出每屏文本到指定目录（只写 --save 则默认 demo_out/），导出后结束")
    ap.add_argument("--play", action="store_true",
                    help="配合 --save：导出后继续逐屏播放（边录边留稿）")
    args = ap.parse_args()

    print(">>> 正在生成演示输出（跑一次 --demo-real）...")
    text = run(["mcd_whiz.py", "--demo-real"])
    if not text.strip():
        print("❌ 没有拿到输出，请确认 fixtures/real_snapshot_public.json 存在。")
        return 1
    head, blocks, tail = split_blocks(text)
    if not args.no_tests:
        blocks.append(test_screen())

    # 「数据出处」单独做开场屏：这是整个演示最该停留的一屏
    scenes = [("head", None)]
    for i in range(0, len(blocks), args.per):
        scenes.append(("blocks", blocks[i:i + args.per]))

    if args.save:
        outdir, n = save_scenes(scenes, head, tail, args.save)
        print("📝 已导出 %d 屏到 %s/（含 00_index.txt 索引，UTF-8）" % (n, outdir))
        if not args.play:
            return 0

    if args.list:
        print("\n分镜清单（共 %d 屏）：" % len(scenes))
        print("  %2d. %s" % (1, "数据出处 / 真实性标注（建议停留最久）"))
        for i, (_kind, chunk) in enumerate(scenes[1:], 2):
            print("  %2d. %s" % (i, " + ".join(t for t, _ in chunk)))
        return 0

    print("共 %d 屏。回车翻页，输入 q 退出。\n" % len(scenes))
    if not _ask("按回车开始 ▶ "):
        print("（没有交互输入，已跳过播放。要看内容请加 --list 或 --save-only。）")
        return 0

    for i, (kind, chunk) in enumerate(scenes, 1):
        clear()
        print(render(kind, chunk, head, tail, i, len(scenes)))
        hint = "─── [%d/%d] " % (i, len(scenes))
        hint += "回车下一屏 · q 退出" if not args.auto else "%.0fs 后自动翻页" % args.auto
        print("\n" + hint)
        if args.auto:
            time.sleep(args.auto)
        elif not _ask_quit("> "):
            print("已中止。")
            return 0

    clear()
    print("\n".join(tail))
    print("\n✅ 演示结束。")
    return 0


if __name__ == "__main__":
    sys.exit(main())

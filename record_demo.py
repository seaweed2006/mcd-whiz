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

录屏建议：终端窗口调大（120x32 以上）或把字号调到 16px+，确保每屏不用滚动。
零依赖，仅用标准库。
"""
import argparse
import os
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


def test_screen():
    """最后一屏：跑回归测试并只取结论部分。"""
    out = run(["test_fixes.py"])
    keep = [l for l in out.splitlines() if l.strip(("-= "))]
    tail = keep[-4:] if len(keep) >= 4 else keep
    return ("【回归测试 · 38 条断言】", tail)


def clear():
    os.system("cls" if os.name == "nt" else "clear")


def main():
    ap = argparse.ArgumentParser(description="麦麦精算师 · 演示录制助手（逐屏播放）")
    ap.add_argument("--per", type=int, default=1, help="每屏放几个模式（默认 1）")
    ap.add_argument("--auto", type=float, default=0,
                    help="每屏停留秒数自动翻页（>0 时无需按键）")
    ap.add_argument("--list", action="store_true", help="只列分镜清单")
    ap.add_argument("--no-tests", action="store_true", help="末尾不加回归测试那一屏")
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

    if args.list:
        print("\n分镜清单（共 %d 屏）：" % len(scenes))
        print("  %2d. %s" % (1, "数据出处 / 真实性标注（建议停留最久）"))
        for i, (_kind, chunk) in enumerate(scenes[1:], 2):
            print("  %2d. %s" % (i, " + ".join(t for t, _ in chunk)))
        return 0

    print("共 %d 屏。回车翻页，输入 q 退出。\n" % len(scenes))
    input("按回车开始 ▶ ")

    for i, (kind, chunk) in enumerate(scenes, 1):
        clear()
        if kind == "head":
            print("\n".join(head).rstrip())
        else:
            for _t, body in chunk:
                print("\n".join(body).rstrip())
                print()
        if i == len(scenes):
            print("\n".join(tail).rstrip())
        hint = "─── [%d/%d] " % (i, len(scenes))
        hint += "回车下一屏 · q 退出" if not args.auto else "%.0fs 后自动翻页" % args.auto
        print("\n" + hint)
        if args.auto:
            time.sleep(args.auto)
        else:
            try:
                if input("> ").strip().lower() == "q":
                    print("已中止。")
                    return 0
            except (EOFError, KeyboardInterrupt):
                return 0

    clear()
    print("\n".join(tail))
    print("\n✅ 演示结束。")
    return 0


if __name__ == "__main__":
    sys.exit(main())

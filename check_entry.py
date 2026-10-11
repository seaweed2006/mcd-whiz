#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
麦麦精算师 · 参赛状态核对助手（只读）

用途：核对 M-CODE 报名状态与官方赛程信息，避免"功能做满却漏提交"。
  1) 报名 Issue #22 的状态（open/closed、是否被官方打标签、有无官方回复）
  2) 官方仓库 M-China/mcd-mcp-server 里与"截止/报名/赛程"相关的说明

用法：
  python check_entry.py                 # 用环境变量 GITHUB_TOKEN
  python check_entry.py --token ghp_xxx # 或直接给 Token

只读操作：只做 GET，不创建/修改任何内容。
"""
import argparse
import base64
import json
import os
import re
import sys

def _detect_proxy():
    """自动探测可用代理：优先环境变量，其次本机 WorkBuddy 常用端口。"""
    for k in ("HTTPS_PROXY", "https_proxy", "HTTP_PROXY", "http_proxy"):
        v = os.environ.get(k)
        if v:
            return v
    import socket
    for p in (60182, 65182, 60149, 7890, 10809):
        s = socket.socket()
        s.settimeout(0.4)
        try:
            s.connect(("127.0.0.1", p))
            return f"http://127.0.0.1:{p}"
        except OSError:
            pass
        finally:
            s.close()
    return None


PROXY = _detect_proxy()
API = "https://api.github.com"
OFFICIAL_REPO = "M-China/mcd-mcp-server"
ISSUE_NO = 22

import urllib.request


def http_get(url, token):
    req = urllib.request.Request(url, method="GET")
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("User-Agent", "mcd-whiz-check")
    req.add_header("X-GitHub-Api-Version", "2022-11-28")
    if PROXY:
        handler = urllib.request.ProxyHandler({"http": PROXY, "https": PROXY})
        opener = urllib.request.build_opener(handler)
    else:
        opener = urllib.request.build_opener()
    try:
        with opener.open(req, timeout=30) as r:
            raw = r.read().decode("utf-8", "ignore")
            try:
                return r.status, json.loads(raw)
            except json.JSONDecodeError:
                return r.status, raw
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "ignore")[:300]
    except Exception as e:
        return 0, str(e)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--token", default=os.environ.get("GITHUB_TOKEN", ""))
    ap.add_argument("--issue", type=int, default=ISSUE_NO)
    args = ap.parse_args()
    if not args.token:
        print("❌ 缺少 GitHub Token：用 --token ghp_xxx 或设环境变量 GITHUB_TOKEN")
        return

    print(f"使用代理：{PROXY or '（无，走直连）'}")
    print()
    print("=" * 60)
    print(f"① 报名 Issue #{args.issue} 状态")
    print("=" * 60)
    st, d = http_get(f"{API}/repos/{OFFICIAL_REPO}/issues/{args.issue}", args.token)
    if st != 200 or not isinstance(d, dict):
        print(f"  查询失败（HTTP {st}）：{d}")
    else:
        labels = [l["name"] for l in d.get("labels", [])]
        print(f"  标题    ：{d.get('title')}")
        print(f"  状态    ：{d.get('state')}（open=仍在处理/未关闭；closed=已关闭）")
        print(f"  创建    ：{d.get('created_at')}")
        print(f"  最后更新：{d.get('updated_at')}  ← 官方若动过，这里会变")
        print(f"  标签    ：{labels or '（无标签）'}  ← 官方常用标签确认参赛资格")
        print(f"  经办人  ：{[a['login'] for a in d.get('assignees', [])] or '（无）'}")
        print(f"  评论数  ：{d.get('comments')}")
        print(f"  链接    ：{d.get('html_url')}")

    print()
    print("=" * 60)
    print("② 官方回复 / 评论")
    print("=" * 60)
    st2, c = http_get(f"{API}/repos/{OFFICIAL_REPO}/issues/{args.issue}/comments", args.token)
    if st2 != 200 or not isinstance(c, list):
        print(f"  查询失败（HTTP {st2}）：{c}")
    elif not c:
        print("  （暂无任何评论或官方回复 —— 报名已提交，等待官方处理）")
    else:
        for cm in c:
            who = (cm.get("user") or {}).get("login")
            print(f"  --- {who} @ {cm.get('created_at')} ---")
            print("  " + (cm.get("body") or "").replace("\n", "\n  ")[:600])

    print()
    print("=" * 60)
    print("③ 官方仓库文档里与「截止/报名/赛程」相关的行")
    print("=" * 60)
    st3, rd = http_get(f"{API}/repos/{OFFICIAL_REPO}/readme", args.token)
    if st3 != 200 or not isinstance(rd, dict):
        print(f"  查询失败（HTTP {st3}）：{rd}")
    else:
        try:
            txt = base64.b64decode(rd.get("content", "")).decode("utf-8", "ignore")
        except Exception:
            txt = ""
        kw = r"截止|报名|赛程|时间|日期|Deadline|deadline|投稿|评审|公布|开奖|2026|2025|月.*日|大赛|M-CODE|流程|截止日|评选"
        hits = [ln.strip()[:300] for ln in txt.splitlines() if re.search(kw, ln)]
        if hits:
            for h in hits[:40]:
                print("  • " + h)
        else:
            print("  （README 未出现明显的时间/截止关键词，见下方建议的查看位置）")

    # 仓库根文件清单，便于定位活动说明文件
    print()
    print("=" * 60)
    print("④ 官方仓库根目录文件（找活动/报名说明用）")
    print("=" * 60)
    st4, files = http_get(f"{API}/repos/{OFFICIAL_REPO}/contents/", args.token)
    if st4 == 200 and isinstance(files, list):
        for f in files:
            print(f"  - {f.get('name')}  ({f.get('type')})")
    else:
        print(f"  （获取失败 HTTP {st4}）")

    print()
    print("提示：若上面没查到截止日期，说明官方未把它写进 README/根文件，")
    print("      需以你报名时的活动页面/官方通知为准（README 抓不到即属此类情况）。")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import datetime as dt
import os
import re
import sys
from html.parser import HTMLParser
from urllib.request import Request, urlopen
from urllib.error import HTTPError

TRENDING_URL = "https://github.com/trending?since=daily"
KEYWORD = "ai"
TOP_N = 15
README_MAX_CHARS = 4000

class TrendingParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.in_h2 = False
        self.in_a = False
        self.in_desc = False
        self.current_href = None
        self.current_text = []
        self.current_desc = []
        self.items = []  # list of dicts

    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)
        if tag == "h2":
            self.in_h2 = True
        if self.in_h2 and tag == "a" and "href" in attrs_dict:
            href = attrs_dict.get("href")
            if href and href.startswith("/") and href.count("/") >= 2:
                self.in_a = True
                self.current_href = href
                self.current_text = []
        if tag == "p":
            klass = attrs_dict.get("class", "")
            if "col-9" in klass:
                self.in_desc = True
                self.current_desc = []

    def handle_data(self, data):
        if self.in_a:
            self.current_text.append(data)
        if self.in_desc:
            self.current_desc.append(data)

    def handle_endtag(self, tag):
        if tag == "a" and self.in_a:
            text = " ".join(self.current_text)
            text = re.sub(r"\s+", " ", text).strip()
            href = self.current_href.lstrip("/")
            if href:
                self.items.append({
                    "repo": href,
                    "display": text,
                    "desc": ""
                })
            self.in_a = False
            self.current_href = None
            self.current_text = []
        if tag == "h2":
            self.in_h2 = False
        if tag == "p" and self.in_desc:
            desc = " ".join(self.current_desc)
            desc = re.sub(r"\s+", " ", desc).strip()
            if self.items and not self.items[-1]["desc"]:
                self.items[-1]["desc"] = desc
            self.in_desc = False
            self.current_desc = []


def fetch_trending():
    req = Request(TRENDING_URL, headers={"User-Agent": "Mozilla/5.0"})
    html = urlopen(req, timeout=20).read().decode("utf-8", errors="ignore")
    parser = TrendingParser()
    parser.feed(html)
    return parser.items


def filter_ai(items):
    result = []
    for it in items:
        hay = f"{it.get('repo','')} {it.get('desc','')}".lower()
        if KEYWORD in hay:
            result.append(it)
    return result


def fetch_readme(repo):
    for branch in ["main", "master"]:
        url = f"https://raw.githubusercontent.com/{repo}/{branch}/README.md"
        try:
            req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
            data = urlopen(req, timeout=15).read().decode("utf-8", errors="ignore")
            return data[:README_MAX_CHARS]
        except HTTPError:
            continue
        except Exception:
            continue
    return ""


def extract_section(text, patterns):
    if not text:
        return ""
    lines = text.splitlines()
    indices = []
    for i, line in enumerate(lines):
        if any(re.search(p, line, re.I) for p in patterns):
            indices.append(i)
    if not indices:
        return ""
    start = indices[0]
    end = len(lines)
    for j in range(start + 1, len(lines)):
        if re.match(r"^#", lines[j]):
            end = j
            break
    snippet = "\n".join(lines[start:end]).strip()
    snippet = re.sub(r"`{3}[\s\S]*?`{3}", "", snippet)
    snippet = re.sub(r"`[^`]+`", "", snippet)
    snippet = re.sub(r"\s+", " ", snippet)
    return snippet[:400]


def summarize_repo_cn(repo, desc):
    readme = fetch_readme(repo)
    install = extract_section(readme, [r"installation", r"install", r"setup", r"快速开始", r"安装"])
    usage = extract_section(readme, [r"usage", r"getting started", r"example", r"使用", r"用法", r"quickstart"])
    intro = extract_section(readme, [r"^#", r"简介", r"about", r"overview"]) or desc

    scenario = "适合开发者进行 AI 项目实验或快速集成" if desc else "适合开发者进行 AI 项目实验或快速集成"
    meaning = "提升开发效率或增强 AI 能力的开源项目" if desc else "提供可复用的 AI 能力或工具"

    return {
        "intro": intro.strip() if intro else desc,
        "install": install,
        "usage": usage,
        "scenario": scenario,
        "meaning": meaning,
    }


def build_markdown(items, date_str):
    lines = []
    lines.append(f"# GitHub AI Trending 日报 - {date_str}")
    lines.append("")
    lines.append(f"数据源：[{TRENDING_URL}]({TRENDING_URL})")
    lines.append("")
    if not items:
        lines.append("今日未匹配到包含 'AI' 关键字的 Trending 项目。")
        return "\n".join(lines)

    lines.append(f"今日共匹配到 {len(items)} 个项目，展示前 {min(TOP_N, len(items))} 个：")
    lines.append("")
    for i, it in enumerate(items[:TOP_N], 1):
        repo = it["repo"]
        desc = it.get("desc", "").strip()
        url = f"https://github.com/{repo}"
        summary = summarize_repo_cn(repo, desc)
        lines.append(f"{i}. [{repo}]({url})")
        if summary.get("intro"):
            lines.append(f"   - 简介：{summary['intro']}")
        lines.append(f"   - 适合场景：{summary['scenario']}")
        if summary.get("install"):
            lines.append(f"   - 安装方式：{summary['install']}")
        if summary.get("usage"):
            lines.append(f"   - 使用方式：{summary['usage']}")
        lines.append(f"   - 项目意义：{summary['meaning']}")
    lines.append("")
    lines.append("---")
    lines.append("生成时间（本地）：" + dt.datetime.now().strftime("%Y-%m-%d %H:%M"))
    return "\n".join(lines)


def update_readme(latest_path):
    readme_path = os.path.join(os.getcwd(), "README.md")
    if not os.path.exists(readme_path):
        return
    with open(readme_path, "r", encoding="utf-8") as f:
        content = f.read()

    latest_line = f"- [{os.path.basename(latest_path)}](reports/{os.path.basename(latest_path)})"
    new_content = re.sub(r"## 最新日报[\s\S]*?## 目录", f"## 最新日报\n\n{latest_line}\n\n## 目录", content, count=1)
    if new_content == content:
        # fallback: append
        new_content = content + f"\n\n## 最新日报\n\n{latest_line}\n"

    with open(readme_path, "w", encoding="utf-8") as f:
        f.write(new_content)


def main():
    items = fetch_trending()
    ai_items = filter_ai(items)

    today = dt.date.today().strftime("%Y-%m-%d")
    reports_dir = os.path.join(os.getcwd(), "reports")
    os.makedirs(reports_dir, exist_ok=True)
    out_path = os.path.join(reports_dir, f"{today}.md")

    md = build_markdown(ai_items, today)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(md)

    update_readme(out_path)
    print(out_path)

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        sys.exit(1)

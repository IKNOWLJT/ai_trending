#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import datetime as dt
import os
import re
import sys
from html.parser import HTMLParser
from urllib.request import Request, urlopen

TRENDING_URL = "https://github.com/trending?since=daily"
KEYWORD = "ai"
TOP_N = 15

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
        lines.append(f"{i}. [{repo}]({url})")
        if desc:
            lines.append(f"   - {desc}")
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

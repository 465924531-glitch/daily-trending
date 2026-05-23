#!/usr/bin/env python3
"""Fetch GitHub trending repositories and format for PushPlus push."""

import urllib.request
import json
import re
import html

def fetch_trending(language="", since="daily"):
    url = f"https://github.com/trending/{language}?since={since}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            html_content = resp.read().decode("utf-8")
    except Exception as e:
        return f"❌ 抓取失败: {e}"

    # Parse repos from HTML
    repos = []
    # Find repo blocks: <article class="Box-row"> ... </article>
    pattern = r'<article class="Box-row[^"]*"[^>]*>.*?<h2[^>]*>.*?<a[^>]*href="/([^"]+)"[^>]*>([^<]+)</a>.*?</h2>'
    matches = re.findall(pattern, html_content, re.DOTALL)
    
    for full_name, name in matches[:10]:
        full_name = html.unescape(full_name.strip())
        name = html.unescape(name.strip().replace('\n', '').strip())
        
        # Description
        desc_match = re.search(
            rf'<article class="Box-row[^"]*"[^>]*>.*?<h2[^>]*>.*?{re.escape(name)}.*?</h2>\s*<p[^>]*>(.*?)</p>',
            html_content, re.DOTALL
        )
        desc = ""
        if desc_match:
            desc = re.sub(r'<[^>]+>', '', desc_match.group(1)).strip()
            desc = html.unescape(desc)
        
        # Stars
        stars_match = re.search(
            rf'<a[^>]*href="/{re.escape(full_name)}/stargazers"[^>]*>.*?<svg.*?</svg>\s*([^<]+)',
            html_content, re.DOTALL
        )
        stars = ""
        if stars_match:
            stars = stars_match.group(1).strip()
        
        repos.append((full_name, name, desc, stars))
    
    return repos

def format_message(repos):
    """Format repo list as PushPlus-friendly HTML."""
    if isinstance(repos, str):
        return repos
    
    lines = [
        "<h2>🔥 GitHub 今日热门项目</h2>",
        f"<p>📅 更新时间：北京时间 8:00</p>",
        "<hr>"
    ]
    
    for i, (full_name, name, desc, stars) in enumerate(repos, 1):
        repo_url = f"https://github.com/{full_name}"
        star_text = f" ⭐ {stars}" if stars else ""
        
        lines.append(f"<h3>{i}. <a href='{repo_url}'>{full_name}</a>{star_text}</h3>")
        if desc:
            lines.append(f"<blockquote>{desc}</blockquote>")
        lines.append("<br>")
    
    lines.append("<hr><p>🤖 由 Hermes Agent 自动推送</p>")
    return "\n".join(lines)

def push_to_pushplus(token, content, title="GitHub 每日热门"):
    url = "https://www.pushplus.plus/send"
    data = json.dumps({
        "token": token,
        "title": title,
        "content": content,
        "template": "html"
    }).encode("utf-8")
    
    req = urllib.request.Request(
        url, data=data,
        headers={"Content-Type": "application/json"}
    )
    
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            return result.get("code") == 200
    except Exception as e:
        print(f"Push failed: {e}")
        return False

if __name__ == "__main__":
    import os
    token = os.environ.get("PUSHPLUS_TOKEN", "")
    if not token:
        print("❌ PUSHPLUS_TOKEN 未设置")
        exit(1)
    
    repos = fetch_trending()
    if isinstance(repos, str):
        push_to_pushplus(token, repos)
        exit(1)
    
    if not repos:
        push_to_pushplus(token, "<p>今日暂无热门项目数据</p>")
        exit(0)
    
    msg = format_message(repos)
    success = push_to_pushplus(token, msg)
    
    if success:
        print(f"✅ 推送成功，共 {len(repos)} 个项目")
    else:
        print("❌ 推送失败")
        exit(1)

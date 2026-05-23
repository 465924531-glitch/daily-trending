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
        print(f"PushPlus failed: {e}")
        return False

def push_to_email(smtp_host, smtp_port, smtp_user, smtp_pass, to_addr, subject, html_content):
    """Send email via SMTP."""
    import smtplib
    from email.mime.text import MIMEText
    from email.header import Header
    import base64
    
    msg = MIMEText(html_content, "html", "utf-8")
    msg["Subject"] = Header(subject, "utf-8")
    msg["From"] = smtp_user
    msg["To"] = to_addr
    
    try:
        server = smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=15)
        server.login(smtp_user, smtp_pass)
        server.sendmail(smtp_user, [to_addr], msg.as_string())
        server.quit()
        return True
    except Exception as e:
        print(f"Email failed: {e}")
        return False

if __name__ == "__main__":
    import os
    
    repos = fetch_trending()
    if isinstance(repos, str):
        print(f"❌ 抓取失败: {repos}")
        exit(1)
    
    if not repos:
        msg = "<p>今日暂无热门项目数据</p>"
    else:
        msg = format_message(repos)
    
    title = f"GitHub 每日热门 ({len(repos)}个项目)"
    all_ok = True
    
    # 1. PushPlus 推送微信
    pp_token = os.environ.get("PUSHPLUS_TOKEN", "")
    if pp_token:
        pp_ok = push_to_pushplus(pp_token, msg, title)
        print(f"{'✅' if pp_ok else '❌'} PushPlus微信推送: {'成功' if pp_ok else '失败'}")
        if not pp_ok:
            all_ok = False
    else:
        print("⏭️ PushPlus 未配置，跳过")
    
    # 2. QQ邮箱推送（给小号）
    smtp_host = os.environ.get("SMTP_HOST", "")
    smtp_port = os.environ.get("SMTP_PORT", "465")
    smtp_user = os.environ.get("SMTP_USER", "")
    smtp_pass = os.environ.get("SMTP_PASS", "")
    email_to = os.environ.get("EMAIL_TO", "")
    
    if smtp_host and smtp_user and smtp_pass and email_to:
        email_ok = push_to_email(
            smtp_host, int(smtp_port), smtp_user, smtp_pass, email_to,
            title, msg
        )
        print(f"{'✅' if email_ok else '❌'} 邮箱推送: {'成功' if email_ok else '失败'}")
        if not email_ok:
            all_ok = False
    else:
        print("⏭️ 邮箱未配置，跳过")
    
    if all_ok:
        print(f"🎉 全部推送完成，共 {len(repos)} 个项目")
    else:
        exit(1)

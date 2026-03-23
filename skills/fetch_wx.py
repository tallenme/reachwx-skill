#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
微信文章抓取器 (CLI版) - 仅使用Python内置库
支持输出 Markdown、HTML、纯文本
"""

import urllib.request
import urllib.parse
import urllib.error
import re
import html
import time
import argparse
import sys
from html.parser import HTMLParser

class WeChatHTMLParser(HTMLParser):
    """自定义HTML解析器，提取微信文章信息"""

    def __init__(self):
        super().__init__()
        self.in_title = False
        self.in_author = False
        self.in_time = False
        self.in_content = False
        self.title = ""
        self.author = ""
        self.publish_time = ""
        self.content_html = ""
        self.content_text = ""
        self.current_tag = None
        self.tag_stack =[]
        self.title_h1_count = 0

    def handle_starttag(self, tag, attrs):
        self.current_tag = tag
        self.tag_stack.append(tag)
        attrs_dict = dict(attrs)

        if self.in_content:
            self.content_html += f'<{tag}{self._attrs_to_str(attrs)}>'

        if tag == 'h1':
            self.title_h1_count += 1
            if 'class' in attrs_dict and 'rich_media_title' in attrs_dict['class']:
                self.in_title = True
            elif self.title_h1_count == 1 and not self.title:
                self.in_title = True
        elif tag == 'a':
            if 'id' in attrs_dict and attrs_dict['id'] == 'js_name':
                self.in_author = True
            elif 'class' in attrs_dict and 'profile_nickname' in attrs_dict['class']:
                self.in_author = True
        elif tag in ['em', 'span']:
            if 'id' in attrs_dict and attrs_dict['id'] == 'publish_time':
                self.in_time = True
            elif 'class' in attrs_dict and 'publish_time' in attrs_dict['class']:
                self.in_time = True
        elif tag == 'div':
            if 'id' in attrs_dict and attrs_dict['id'] == 'js_content':
                self.in_content = True
                self.content_html += f'<div{self._attrs_to_str(attrs)}>'

    def handle_endtag(self, tag):
        if self.tag_stack and self.tag_stack[-1] == tag:
            self.tag_stack.pop()

        if tag == 'h1' and self.in_title:
            self.in_title = False
        elif tag == 'a' and self.in_author:
            self.in_author = False
        elif tag in ['em', 'span'] and self.in_time:
            self.in_time = False
        elif tag == 'div' and self.in_content:
            if not self.tag_stack or 'div' not in self.tag_stack:
                pass
            self.content_html += '</div>'
            if self.tag_stack.count('div') == 0:
                self.in_content = False
        elif self.in_content:
            self.content_html += f'</{tag}>'

    def handle_startendtag(self, tag, attrs):
        if self.in_content:
            self.content_html += f'<{tag}{self._attrs_to_str(attrs)} />'

    def handle_data(self, data):
        data = data.strip()
        if not data:
            return

        if self.in_title:
            self.title += data
        if self.in_author:
            self.author += data
        if self.in_time:
            self.publish_time += data
        if self.in_content:
            self.content_text += data + ' '
            self.content_html += html.escape(data)

    def _attrs_to_str(self, attrs):
        if not attrs:
            return ""
        parts =[]
        for key, value in attrs:
            if value is None:
                parts.append(key)
            else:
                parts.append(f'{key}="{html.escape(value)}"')
        return " " + " ".join(parts)


def fetch_wechat_article(url, timeout=30):
    """获取微信公众号文章内容"""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Referer': 'https://mp.weixin.qq.com/'
    }

    req = urllib.request.Request(url, headers=headers, method='GET')

    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            raw_data = response.read()

            content_type = response.headers.get('Content-Type', '')
            charset = 'utf-8'
            if 'charset=' in content_type:
                charset = content_type.split('charset=')[1].split(';')[0].strip()

            if response.headers.get('Content-Encoding') == 'gzip':
                import gzip
                content = gzip.decompress(raw_data).decode(charset, errors='replace')
            else:
                content = raw_data.decode(charset, errors='replace')

            #print(f"[*] 请求成功，内容长度: {len(content)} 字符")

            parser = WeChatHTMLParser()
            parser.feed(content)

            if not parser.publish_time:
                m = re.search(r"create_time:\s*JsDecode\('([^']+)'\)", content)
                if m:
                    parser.publish_time = m.group(1)

            content_html = parser.content_html
            if content_html:
                content_html = _replace_image_urls(content_html)

            article_info = {
                'title': parser.title.strip() if parser.title else "未知标题",
                'author': parser.author.strip() if parser.author else "未知作者",
                'publish_time': parser.publish_time.strip() if parser.publish_time else "未知时间",
                'content_html': content_html,
                'content_text': parser.content_text.strip(),
                'url': url,
                'html_length': len(content)
            }

            return article_info

    except Exception as e:
        print(f"[✗] 发生错误: {e}")
        return None


def _replace_image_urls(html_content):
    """替换图片URL为代理地址，解决防盗链问题"""
    pattern = r'<img[^>]+>'

    def replace_func(match):
        img_tag = match.group(0)
        src_match = re.search(r'data-src=["\']([^"\']+)', img_tag)
        if not src_match:
            src_match = re.search(r'src=["\']([^"\']+)', img_tag)

        if src_match:
            original_url = src_match.group(1)
            if 'mmbiz.qpic.cn' in original_url or 'qq.com' in original_url:
                encoded_url = urllib.parse.quote(original_url, safe='')
                proxy_url = f"https://images.weserv.nl/?url={encoded_url}"
                new_tag = re.sub(r'(data-src|src)=["\'][^"\']+["\']', f'src="{proxy_url}"', img_tag)
                return new_tag
        return img_tag

    return re.sub(pattern, replace_func, html_content, flags=re.IGNORECASE)


def html_to_markdown(html_content):
    """将HTML内容转换为Markdown格式"""
    if not html_content:
        return ""

    class MarkdownParser(HTMLParser):
        def __init__(self):
            super().__init__()
            self.md_lines = []
            self.list_stack = []
            self.link_stack =[]
            self.in_pre = False
            self.ignore_tags = {'style', 'script', 'noscript', 'iframe', 'svg'}
            self.ignore_level = 0

        def handle_starttag(self, tag, attrs):
            if tag in self.ignore_tags:
                self.ignore_level += 1
                return
            if self.ignore_level > 0:
                return

            attrs_dict = dict(attrs)

            if tag in['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
                level = int(tag[1])
                self.md_lines.append(f"\n\n{'#' * level} ")
            elif tag in ['p', 'div', 'section']:
                self.md_lines.append("\n\n")
            elif tag == 'br':
                self.md_lines.append("\n")
            elif tag == 'blockquote':
                self.md_lines.append("\n\n> ")
            elif tag in ['strong', 'b']:
                self.md_lines.append("**")
            elif tag in['em', 'i']:
                self.md_lines.append("*")
            elif tag == 'a':
                href = attrs_dict.get('href', '')
                self.link_stack.append(href)
                self.md_lines.append("[")
            elif tag == 'img':
                src = attrs_dict.get('src') or attrs_dict.get('data-src') or ''
                alt = attrs_dict.get('alt', 'image')
                if src:
                    self.md_lines.append(f"\n![{alt}]({src})\n")
            elif tag == 'ul':
                self.list_stack.append('ul')
                self.md_lines.append("\n\n")
            elif tag == 'ol':
                self.list_stack.append(1)
                self.md_lines.append("\n\n")
            elif tag == 'li':
                depth = max(0, len(self.list_stack) - 1)
                indent = "  " * depth
                if self.list_stack:
                    if self.list_stack[-1] == 'ul':
                        self.md_lines.append(f"\n{indent}- ")
                    else:
                        idx = self.list_stack[-1]
                        self.md_lines.append(f"\n{indent}{idx}. ")
                        self.list_stack[-1] += 1
                else:
                    self.md_lines.append("\n- ")
            elif tag == 'pre':
                self.in_pre = True
                self.md_lines.append("\n\n```text\n")
            elif tag == 'code':
                if not self.in_pre:
                    self.md_lines.append("`")

        def handle_endtag(self, tag):
            if tag in self.ignore_tags:
                self.ignore_level = max(0, self.ignore_level - 1)
                return
            if self.ignore_level > 0:
                return

            if tag in['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'p', 'div', 'section']:
                self.md_lines.append("\n\n")
            elif tag in ['strong', 'b']:
                self.md_lines.append("**")
            elif tag in['em', 'i']:
                self.md_lines.append("*")
            elif tag == 'a':
                href = self.link_stack.pop() if self.link_stack else ''
                self.md_lines.append(f"]({href})")
            elif tag in ['ul', 'ol']:
                if self.list_stack:
                    self.list_stack.pop()
                self.md_lines.append("\n\n")
            elif tag == 'pre':
                self.in_pre = False
                self.md_lines.append("\n```\n\n")
            elif tag == 'code':
                if not self.in_pre:
                    self.md_lines.append("`")

        def handle_startendtag(self, tag, attrs):
            self.handle_starttag(tag, attrs)
            if tag not in['img', 'br', 'hr', 'input', 'meta', 'link']:
                self.handle_endtag(tag)

        def handle_data(self, data):
            if self.ignore_level > 0:
                return

            if self.in_pre:
                self.md_lines.append(data)
            else:
                text = re.sub(r'\s+', ' ', data)
                if text == ' ':
                    if self.md_lines and not self.md_lines[-1].endswith((' ', '\n', '> ')):
                        self.md_lines.append(' ')
                elif text:
                    self.md_lines.append(text)

        def get_markdown(self):
            text = "".join(self.md_lines)
            text = re.sub(r'\n{3,}', '\n\n', text)
            text = re.sub(r'\*\*\s*\*\*', '', text)
            text = re.sub(r'[ \t]+\n', '\n', text)
            return text.strip()

    parser = MarkdownParser()
    try:
        parser.feed(html_content)
        return parser.get_markdown()
    except Exception as e:
        print(f"[!] Markdown转换异常，返回原始文本: {e}")
        return html_content

def get_valid_filename(title):
    """移除标题中不能作为文件名的特殊字符"""
    # 替换不合法的文件名字符（Windows / macOS / Linux）
    clean_title = re.sub(r'[\\/*?:"<>|]', '_', title)
    # 去除多余的空格或下划线
    clean_title = re.sub(r'\s+', '_', clean_title.strip())
    return clean_title if clean_title else "wechat_article"

def main():
    """程序CLI入口"""
    # 设置 argparse 参数
    parser = argparse.ArgumentParser(
        description="微信公众号文章抓取器 - 支持 Markdown / HTML / Text 输出",
        formatter_class=argparse.RawTextHelpFormatter
    )

    parser.add_argument("url", help="要抓取的微信公众号文章URL")

    parser.add_argument("-f", "--format",
                        choices=["markdown", "html", "text"],
                        default="markdown",
                        help="指定输出文件的格式 (默认: markdown)")

    parser.add_argument("-o", "--output",
                        help="输出文件的路径。\n(如果不指定，直接打印内容)")

    parser.add_argument("-t", "--timeout",
                        type=int,
                        default=30,
                        help="请求超时时间，单位秒 (默认: 30)")

    args = parser.parse_args()

    #print(f"[*] 开始抓取文章...")
    #print(f"[*] 目标链接: {args.url}")

    # 抓取文章内容
    result = fetch_wechat_article(args.url, timeout=args.timeout)

    if not result:
        print("\n[✗] 抓取失败，请检查网络或URL是否正确。")
        sys.exit(1)

    #print("\n" + "="*50)
    #print(" 抓取结果摘要:")
    #print("="*50)
    #print(f" 标题: {result['title']}")
    #print(f" 作者: {result['author']}")
    #print(f" 发布时间: {result['publish_time']}")
    #print("="*50)

    # 确定输出文件名
    if args.output:
        output_file = args.output
    else:
        output_file = None
        #ext_map = {"markdown": ".md", "html": ".html", "text": ".txt"}
        #safe_title = get_valid_filename(result['title'])
        #output_file = f"{safe_title}{ext_map[args.format]}"

    # 根据选定的格式组装内容
    if args.format == "markdown":
        md_content = html_to_markdown(result['content_html'])
        content_to_save = f"# {result['title']}\n\n"
        content_to_save += f"**作者**: {result['author']}\n\n"
        content_to_save += f"**发布时间**: {result['publish_time']}\n\n"
        content_to_save += f"**原文链接**: {result['url']}\n\n"
        content_to_save += "---\n\n"
        content_to_save += md_content

    elif args.format == "html":
        # 为 HTML 提供一个自带简单排版的完整骨架
        content_to_save = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{result['title']}</title>
    <style>
        body {{ max-width: 800px; margin: 0 auto; padding: 20px; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Arial, sans-serif; line-height: 1.6; color: #333; }}
        h1 {{ font-size: 24px; color: #111; }}
        img {{ max-width: 100%; height: auto; display: block; margin: 10px auto; border-radius: 4px; }}
        .meta-info {{ color: #888; font-size: 15px; margin-bottom: 30px; }}
        .meta-info span {{ margin-right: 15px; }}
        a {{ color: #576b95; text-decoration: none; }}
        pre {{ background: #f6f8fa; padding: 15px; overflow-x: auto; border-radius: 6px; }}
        code {{ font-family: Consolas, Monaco, monospace; font-size: 14px; background: #f6f8fa; padding: 2px 4px; border-radius: 4px; }}
        blockquote {{ margin: 0; padding-left: 15px; border-left: 4px solid #cbd5e1; color: #64748b; }}
    </style>
</head>
<body>
    <h1>{result['title']}</h1>
    <div class="meta-info">
        <span>作者: {result['author']}</span>
        <span>发布时间: {result['publish_time']}</span>
        <span><a href="{result['url']}" target="_blank">阅读原文</a></span>
    </div>
    <hr style="border: none; border-top: 1px solid #eee; margin-bottom: 30px;">

    <div id="js_content">
        {result['content_html']}
    </div>
</body>
</html>"""

    elif args.format == "text":
        content_to_save = f"标题: {result['title']}\n"
        content_to_save += f"作者: {result['author']}\n"
        content_to_save += f"发布时间: {result['publish_time']}\n"
        content_to_save += f"原文链接: {result['url']}\n\n"
        content_to_save += "-" * 50 + "\n\n"
        content_to_save += result['content_text']

    # 写入文件
    if output_file is not None:
        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(content_to_save)
            print(f"\n[✓] 成功保存 {args.format.upper()} 格式文件至:")
            print(f"    -> {output_file}\n")
        except Exception as e:
            print(f"\n[✗] 保存文件时发生错误: {e}")
            sys.exit(1)
    else:
        print(content_to_save)

if __name__ == "__main__":
    main()

import re
import random
import time
import argparse
import json
from datetime import datetime
from urllib import request, parse, error
from http.cookiejar import CookieJar
import html.parser


class WxSpider:
    def __init__(self):
        self.base_url = 'https://weixin.sogou.com/weixin'
        self.user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        ]

    def _get_random_ua(self):
        return random.choice(self.user_agents)

    def _request(self, url, method='GET', params=None, headers=None, timeout=10, allow_redirects=False):
        """
        发送 HTTP 请求，支持参数、自定义头部、超时和重定向控制
        """
        if params:
            url += '?' + parse.urlencode(params)

        req = request.Request(url, method=method)
        if headers:
            for k, v in headers.items():
                req.add_header(k, v)

        # 构建一个不自动处理重定向的 opener
        opener = request.OpenerDirector()
        opener.add_handler(request.HTTPHandler())
        opener.add_handler(request.HTTPSHandler())
        # 不添加 HTTPRedirectHandler，从而禁止自动重定向
        try:
            resp = opener.open(req, timeout=timeout)
            if allow_redirects and resp.getcode() in (301, 302, 303, 307, 308):
                # 如果允许重定向且是重定向状态码，手动处理
                location = resp.headers.get('Location')
                if location:
                    return self._request(location, method=method, params=None, headers=headers, timeout=timeout, allow_redirects=True)
            return resp
        except error.HTTPError as e:
            # 对于非 2xx 状态码，如果需要获取响应内容，可以返回 e 对象
            # 这里返回空表示失败
            return None
        except error.URLError:
            return None

    def get_new_cookies(self):
        """
        获取 SNUID cookie 值
        """
        url = 'https://v.sogou.com/v?ie=utf8&query=&p=40030600'
        resp = self._request(url, allow_redirects=False)
        if resp is None:
            return {}
        # 提取 Set-Cookie 头部
        cookies = {}
        set_cookie = resp.headers.get('Set-Cookie')
        if set_cookie:
            # 简单解析 Set-Cookie，获取 SNUID
            match = re.search(r'SNUID=([^;]+)', set_cookie)
            if match:
                cookies['SNUID'] = match.group(1)
        return cookies

    def weixin_fetch(self, url, ke, retries=5, timeout=10):
        """
        搜索请求，带重试
        """
        for attempt in range(retries):
            cookies = self.get_new_cookies()
            snuid = cookies.get('SNUID', '')
            # 硬编码的 Cookie 模板，替换 SNUID
            cookie_str = (
                'SUID=3747A9742B83A20A000000006606A2E7; '
                'SUID=3747A97426A6A20B000000006606A2E7; '
                'SUV=00ED051974A947376606A2F3884B8464; '
                'ABTEST=7|1716888919|v1; '
                'IPLOC=CN5101; '
                'PHPSESSID=8pft1e0o80d3a29v2mld4thsg6; '
                f'SNUID={snuid}; '
                'ariaDefaultTheme=default; '
                'ariaFixed=true; '
                'ariaReadtype=1; '
                'ariaStatus=false'
            )
            headers = {
                'Cookie': cookie_str,
                'User-Agent': self._get_random_ua()
            }
            resp = self._request(url, params=ke, headers=headers, timeout=timeout, allow_redirects=False)
            if resp and resp.getcode() == 200:
                return resp.read().decode('utf-8')
            # 简单延迟后重试
            time.sleep(1)
        return ""

    def get_weixin_article_url(self, url, retries=3, timeout=10):
        """
        获取文章页面内容（用于解析真实 URL）
        """
        for attempt in range(retries):
            cookies = self.get_new_cookies()
            snuid = cookies.get('SNUID', '')
            cookie_str = (
                'SUID=3747A9742B83A20A000000006606A2E7; '
                'SUID=3747A97426A6A20B000000006606A2E7; '
                'SUV=00ED051974A947376606A2F3884B8464; '
                'ABTEST=7|1716888919|v1; '
                'IPLOC=CN5101; '
                'PHPSESSID=8pft1e0o80d3a29v2mld4thsg6; '
                f'SNUID={snuid}; '
                'ariaDefaultTheme=default; '
                'ariaFixed=true; '
                'ariaReadtype=1; '
                'ariaStatus=false'
            )
            headers = {
                'Cookie': cookie_str,
                'User-Agent': self._get_random_ua()
            }
            resp = self._request(url, headers=headers, timeout=timeout, allow_redirects=False)
            if resp and resp.getcode() == 200:
                return resp.read().decode('utf-8')
            time.sleep(1)
        return ""

    def parse_item(self, item_html):
        """
        解析单个新闻条目（li 元素）的 HTML
        """
        try:
            # 标题
            title_match = re.search(r'<h3>(.*?)</h3>', item_html, re.DOTALL)
            title = ''
            if title_match:
                title = re.sub(r'<.*?>', '', title_match.group(1)).strip()

            # 摘要
            summary_match = re.search(r'<p class="txt-info">(.*?)</p>', item_html, re.DOTALL)
            summary = summary_match.group(1).strip() if summary_match else ''

            # 来源
            source_match = re.search(r'<span class="all-time-y2">(.*?)</span>', item_html, re.DOTALL)
            source = source_match.group(1).strip() if source_match else ''

            # 时间戳（从 script 中提取）
            script_match = re.search(r'<span class="s2">.*?<script>(.*?)</script>', item_html, re.DOTALL)
            timestamp = '0'
            if script_match:
                ts_script = script_match.group(1)
                ts_match = re.search(r"'(\d+)'", ts_script)
                if ts_match:
                    timestamp = ts_match.group(1)
            date = ''
            if timestamp.isdigit():
                date = datetime.fromtimestamp(int(timestamp)).strftime('%Y-%m-%d %H:%M:%S')

            # 文章链接（原始搜索结果中的临时链接）
            link_match = re.search(r'<a target="_blank" href="([^"]+)"', item_html)
            link = link_match.group(1) if link_match else ''
            full_link = "https://weixin.sogou.com" + link if link else ''

            # 获取文章真实 URL（二次请求）
            article_content = self.get_weixin_article_url(full_link) if full_link else ''
            pattern = re.compile(r"url\s*\+=\s*'([^']*)'")
            url_parts = pattern.findall(article_content) if article_content else []
            real_url = ''.join(url_parts).replace('@', '') if url_parts else ''

            return {
                'title': title,
                'snippet': summary,
                'url': real_url.replace("src=11×tamp", "src=11&timestamp"),
                'source': source,
                'date': date
            }
        except Exception as e:
            print(f"Error parsing item: {e}")
            return {
                'title': '',
                'snippet': '',
                'url': '',
                'source': '',
                'date': ''
            }

    def weixin_spider(self, query, page=1):
        """
        获取搜索结果页 HTML
        """
        ke = {'query': query, 'type': '2', 'page': str(page)}
        content = self.weixin_fetch(self.base_url, ke)
        return content

    def get_weixin_article(self, query, top_num=5):
        """
        主方法：获取指定关键词的微信文章列表
        """
        content = self.weixin_spider(query)
        if not content:
            return []

        # 提取所有符合条件的 li 元素
        li_pattern = re.compile(r'<li id="sogou_vr_11002601_box_\d+".*?</li>', re.DOTALL)
        li_items = li_pattern.findall(content)

        articles = []
        for item_html in li_items:
            article = self.parse_item(item_html)
            if article['url']:
                articles.append(article)
                if len(articles) >= top_num:
                    break
        return articles


def get_weixin_article(query, top_num=5):
    spider = WxSpider()
    return spider.get_weixin_article(query, top_num)


def main():
    parser = argparse.ArgumentParser(description='搜狗微信文章爬虫')
    parser.add_argument('-q', '--query', required=True, help='搜索关键词')
    parser.add_argument('-n', '--top-num', type=int, default=5, help='获取的文章数量（默认5）')
    parser.add_argument('-f', '--format', choices=['text', 'json'], default='text', help='输出格式：text 或 json（默认text）')
    args = parser.parse_args()

    articles = get_weixin_article(args.query, args.top_num)

    if args.format == 'json':
        print(json.dumps(articles, ensure_ascii=False, indent=2))
    else:
        for idx, item in enumerate(articles, 1):
            print(f"[{idx}] 标题：{item['title']}")
            print(f"    链接：{item['url']}")
            print(f"    来源：{item['source']}")
            print(f"    日期：{item['date']}")
            print("-" * 50)


if __name__ == "__main__":
    main()

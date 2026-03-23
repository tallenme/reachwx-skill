---
name: reach-wx
description: 搜索和获取微信文章 (only python required).
homepage: https://github.com/idiomer2/reach-wx
metadata: {"nanobot":{"emoji":"🕷","requires":{"bins":["python"]}}}
---

## 概述
- 使用`scripts/search_wx.py`搜索微信文章列表
- 使用`scripts/fetch_wx.py`获取微信文章

## 使用方法

### 搜索文章

usage: search_wx.py [-h] -q QUERY [-n TOP_NUM] [-f {text,json}]

搜狗微信文章爬虫

options:
  -h, --help            show this help message and exit
  -q QUERY, --query QUERY
                        搜索关键词
  -n TOP_NUM, --top-num TOP_NUM
                        获取的文章数量（默认5）
  -f {text,json}, --format {text,json}
                        输出格式：text 或 json（默认text）


### 获取文章内容

usage: fetch_wx.py [-h] [-f {markdown,html,text}] [-o OUTPUT] [-t TIMEOUT] url

微信公众号文章抓取器 - 支持 Markdown / HTML / Text 输出

positional arguments:
  url                   要抓取的微信公众号文章URL

options:
  -h, --help            show this help message and exit
  -f {markdown,html,text}, --format {markdown,html,text}
                        指定输出文件的格式 (默认: markdown)
  -o OUTPUT, --output OUTPUT
                        输出文件的路径。
                        (如果不指定，直接打印内容)
  -t TIMEOUT, --timeout TIMEOUT
                        请求超时时间，单位秒 (默认: 30)

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""世界镜像采集器: 抓多国媒体头条, 生成《世界镜像》原始素材"""
import urllib.request, urllib.parse, xml.etree.ElementTree as ET, json, datetime, sys

UA = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36'}

def fetch(url, timeout=20):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode('utf-8', 'replace')

def parse_rss(xml_text, limit=8):
    items = []
    try:
        root = ET.fromstring(xml_text)
        for item in root.iter('item'):
            title = item.findtext('title') or ''
            link = item.findtext('link') or ''
            pub = item.findtext('pubDate') or ''
            src = item.findtext('source') or ''
            items.append({'title': title.strip(), 'link': link.strip(), 'time': pub.strip(), 'src': src.strip()})
    except Exception as e:
        print(f"  [parse err] {e}", file=sys.stderr)
    return items[:limit]

def gnews(topic_or_query, hl='en-US', gl='US', ceid='US:en', limit=8):
    if topic_or_query.startswith('topic:'):
        url = f"https://news.google.com/rss/headlines/section/topic/{topic_or_query[6:]}?hl={hl}&gl={gl}&ceid={ceid}"
    else:
        url = f"https://news.google.com/rss/search?q={urllib.parse.quote(topic_or_query)}&hl={hl}&gl={gl}&ceid={ceid}"
    return parse_rss(fetch(url), limit)

def main():
    out = {}
    now = datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%d %H:%M UTC')

    # 1) 美国视角全球头条
    out['us_headlines'] = gnews('topic:WORLD', 'en-US', 'US', 'US:en')
    # 2) 英国视角
    out['uk_headlines'] = gnews('topic:WORLD', 'en-GB', 'GB', 'GB:en')
    # 3) 中国(美国媒体眼中的中国) - 用search词
    out['china_in_world_media'] = gnews('China', 'en-US', 'US', 'US:en')
    # 4) 台湾议题(美国视角)
    out['taiwan_us'] = gnews('Taiwan', 'en-US', 'US', 'US:en')
    # 5) 台湾议题(日本视角)
    out['taiwan_jp'] = gnews('Taiwan', 'en-JP', 'JP', 'JP:en')
    # 6) AI行业
    out['ai_industry'] = gnews('AI industry', 'en-US', 'US', 'US:en')
    # 7) 创业/startup
    out['startup'] = gnews('startup funding', 'en-US', 'US', 'US:en')
    # 8) 世界经济
    out['world_economy'] = gnews('world economy', 'en-US', 'US', 'US:en')
    # 9) 中东
    out['middle_east'] = gnews('topic:WORLD', 'en-US', 'US', 'US:en')  # placeholder replaced below
    out['middle_east'] = gnews('Middle East', 'en-US', 'US', 'US:en')
    # 10) 俄乌
    out['ukraine'] = gnews('Ukraine war', 'en-US', 'US', 'US:en')

    print(f"# 世界镜像原始素材 {now}")
    print(json.dumps(out, ensure_ascii=False, indent=1))

if __name__ == '__main__':
    main()

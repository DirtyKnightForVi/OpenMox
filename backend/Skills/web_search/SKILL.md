---
name: web_search
description: 搜索互联网获取最新信息。当你需要查找实时数据、新闻、或超出训练数据范围的信息时使用。
---

# web_search

## 用途
搜索互联网获取最新信息。

## 使用方式
1. 使用 Bash 工具执行 curl 请求搜索 API
2. 解析返回的 JSON 结果
3. 提取关键信息

## 搜索 API
```
curl -s "https://api.duckduckgo.com/?q={query}&format=json"
```

## 输出格式
- 标题
- URL
- 摘要（不超过 200 字）

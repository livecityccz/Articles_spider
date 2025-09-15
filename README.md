## 文章爬取与导出

一个将网页内容按分类抓取、转 Markdown 并按目录保存的命令行工具。

### 安装
```bash
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

### 快速开始
```bash
python articles_spider.py \
  --root Articles \
  --delay-min 1.0 \
  --delay-max 2.5 \
  --threads 1
```

### 常用参数
- `--root`：保存根目录（默认 `MyArticles`）
- `--delay-min` / `--delay-max`：相邻请求的最小/最大延迟（秒，默认 1.0/2.0）
- `--threads`：并发线程数（默认 1，建议从 1 起，谨慎升高）
- `--retries`：请求失败重试次数（默认 3）
- `--only-tags`：仅抓取给定标签（逗号分隔），示例：`--only-tags "A,B"`
- `--no-resume`：禁用断点续爬（默认启用断点续爬）

### 断点续爬
- 默认启用。每篇文章处理完成后会生成完成标记文件：
  - 路径：`<root>/<标签名>/.done/p{ID}.done`
  - 下次运行检测到标记即跳过该文章
- 同时保存的 Markdown 文件名会在末尾追加 `[p{ID}]`，便于去重识别。
- 关闭续爬：添加 `--no-resume` 参数。
- 建议保守设置并发与请求间隔，避免高频访问。
- 若页面结构变更导致抽取失败，可根据日志提示调整选择器或参数。


### 示例
- 指定根目录与线程数：
```bash
python articles_spider.py --root Articles --threads 1
```
- 仅抓取部分标签：
```bash
python articles_spider.py --only-tags "A,B" --threads 1
```
- 关闭断点续爬：
```bash
python articles_spider.py --no-resume
```

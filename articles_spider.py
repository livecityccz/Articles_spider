#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import os
import random
import re
import sys
import time
import json
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Tuple

import requests
from bs4 import BeautifulSoup
from markdownify import markdownify as md
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type


BASE_TAG_URL = "https://www.cnblogs.com/chuchengzhi/tag/"
DEFAULT_ROOT_DIR = "MyArticles"
DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9",
    "Referer": "https://www.cnblogs.com/",
    "Connection": "keep-alive",
}


@dataclass
class Config:
    root_dir: str = DEFAULT_ROOT_DIR
    delay_min: float = 1.0
    delay_max: float = 2.0
    retries: int = 3
    threads: int = 1
    only_tags: Optional[List[str]] = None
    resume: bool = True
    base_tag_url: str = BASE_TAG_URL


class RequestError(Exception):
    pass


def log_info(message: str) -> None:
    print(f"[INFO] {message}")


def log_warn(message: str) -> None:
    print(f"[WARN] {message}")


def log_error(message: str) -> None:
    print(f"[ERROR] {message}", file=sys.stderr)


class HttpClient:
    def __init__(self, headers: Optional[Dict[str, str]] = None, timeout: int = 20):
        self.session = requests.Session()
        self.session.headers.update(headers or DEFAULT_HEADERS)
        self.timeout = timeout

    @retry(reraise=True,
           stop=stop_after_attempt(3),
           wait=wait_exponential(multiplier=0.8, min=1, max=10),
           retry=retry_if_exception_type(RequestError))
    def get(self, url: str) -> str:
        try:
            resp = self.session.get(url, timeout=self.timeout)
        except requests.RequestException as exc:
            raise RequestError(f"request failed: {exc}")
        if resp.status_code >= 400:
            raise RequestError(f"bad status {resp.status_code} for {url}")
        resp.encoding = resp.apparent_encoding or "utf-8"
        return resp.text


def random_delay(cfg: Config) -> None:
    delay = random.uniform(cfg.delay_min, cfg.delay_max)
    time.sleep(delay)


def sanitize_filename(name: str) -> str:
    sanitized = re.sub(r'[\\/:*?"<>|]', "_", name).strip()
    sanitized = re.sub(r"\s+", " ", sanitized)
    return sanitized[:180] if len(sanitized) > 180 else sanitized


def ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def find_my_tags_container(soup: BeautifulSoup) -> Optional[BeautifulSoup]:
    heading = soup.find(lambda tag: tag.name in ("h2", "h3", "h4") and "我的标签" in tag.get_text(strip=True))
    if heading:
        for sibling in heading.find_all_next(limit=10):
            if sibling.name in ("div", "section", "ul", "dl") and sibling.find_all("a", href=True):
                return sibling
    candidates = [
        soup.find(id=re.compile(r"tag", re.I)),
        soup.find(class_=re.compile(r"tag|tags|mytag", re.I)),
    ]
    for c in candidates:
        if c and c.find_all("a", href=True):
            return c
    return None


def parse_tag_link_text(text: str) -> Tuple[str, Optional[int]]:
    m = re.match(r"^\s*(.*?)\s*\((\d+)\)\s*$", text)
    if m:
        name = m.group(1).strip()
        count = int(m.group(2))
        return name, count
    return text.strip(), None


def get_all_tags(client: HttpClient, cfg: Config, base_url: str) -> Dict[str, str]:
    html = client.get(base_url)
    soup = BeautifulSoup(html, "lxml")
    container = find_my_tags_container(soup)
    if not container:
        raise RuntimeError("未找到‘我的标签’板块容器，页面结构可能已变化。")

    tags: Dict[str, str] = {}
    for a in container.find_all("a", href=True):
        tag_text = a.get_text(strip=True)
        if not tag_text:
            continue
        name, _ = parse_tag_link_text(tag_text)
        href = a["href"].strip()
        if not href.startswith("http"):
            href = requests.compat.urljoin(base_url, href)
        if "/tag/" not in href:
            continue
        if cfg.only_tags and name not in cfg.only_tags:
            continue
        tags[name] = href

    if not tags:
        raise RuntimeError("未解析到任何标签链接。")

    log_info(f"共解析到 {len(tags)} 个标签。")
    return tags


def find_next_page_url(soup: BeautifulSoup) -> Optional[str]:
    for a in soup.find_all("a", string=re.compile("下一页|下页|Next", re.I)):
        href = a.get("href")
        if href:
            return href
    a = soup.find("a", rel=lambda v: v and "next" in v)
    if a and a.get("href"):
        return a["href"]
    pager = soup.find(class_=re.compile(r"pager|paging|page", re.I))
    if pager:
        link = pager.find("a", string=re.compile("下一页|下页|Next", re.I))
        if link and link.get("href"):
            return link.get("href")
    return None


def normalize_url(current_url: str, href: str) -> str:
    if href.startswith("http"):
        return href
    if href.startswith("//"):
        return "https:" + href
    return requests.compat.urljoin(current_url, href)


ARTICLE_LINK_RE = re.compile(r"/p/(\d+)\.html($|#)")


def is_article_link(href: str) -> bool:
    if not href:
        return False
    return bool(ARTICLE_LINK_RE.search(href))


def extract_article_id(url: str) -> Optional[str]:
    m = ARTICLE_LINK_RE.search(url)
    return m.group(1) if m else None


def get_article_links(client: HttpClient, cfg: Config, tag_list_url: str) -> List[str]:
    all_links: List[str] = []
    seen: set = set()
    current_url = tag_list_url
    page_index = 1

    while True:
        log_info(f"抓取标签列表页：{current_url}（第 {page_index} 页）")
        html = client.get(current_url)
        soup = BeautifulSoup(html, "lxml")

        content_scope = soup.select_one("#mainContent, #main, .main, .forFlow, body") or soup
        page_links: List[str] = []
        for a in content_scope.find_all("a", href=True):
            href = a["href"].strip()
            full = normalize_url(current_url, href)
            if is_article_link(full):
                page_links.append(full)

        if not page_links:
            for a in soup.select("a[title], h2 a, h3 a, .postTitle a, .entrylistTitle a"):
                href = a.get("href")
                if not href:
                    continue
                full = normalize_url(current_url, href)
                if is_article_link(full):
                    page_links.append(full)

        added = 0
        for u in page_links:
            if u not in seen:
                seen.add(u)
                all_links.append(u)
                added += 1
        log_info(f"本页解析到候选 {len(page_links)} 条，新增 {added} 条，累计 {len(all_links)} 条。")

        next_href = find_next_page_url(soup)
        if not next_href:
            break
        next_url = normalize_url(current_url, next_href)
        if next_url == current_url or next_url in (normalize_url(current_url, h) for h in ("#", "javascript:void(0)")):
            break

        page_index += 1
        current_url = next_url
        random_delay(cfg)

    return all_links


def extract_title_and_body(soup: BeautifulSoup) -> Tuple[str, str]:
    title_candidates = [
        soup.find(id="cb_post_title_url"),
        soup.find("h1", id="cb_post_title_url"),
        soup.find("h1", class_=re.compile("post|title", re.I)),
        soup.find("a", id="cb_post_title_url"),
    ]
    title = None
    for t in title_candidates:
        if t and t.get_text(strip=True):
            title = t.get_text(strip=True)
            break
    if not title:
        title_tag = soup.find("title")
        title = title_tag.get_text(strip=True) if title_tag else "untitled"

    body = soup.find(id="cnblogs_post_body")
    if not body:
        body = soup.find(class_=re.compile("post|content|body", re.I))
    if not body:
        raise RuntimeError("未找到正文容器，页面结构可能已变化。")

    for selector in [
        "script", "style", "noscript",
        "div#MySignature", "div#MyTopNavigator", "div#MyBottomNavigator",
        "div.recommend_btns", "div#div_digg", "div#opt_under_post",
        "div#cnblogs_c1", "div#cnblogs_c2", "div#blog_post_info_block",
        "div#ad_t2", "div#ad_c1", "div#ad_c2",
        "iframe", "ins", "aside", "footer",
    ]:
        for x in body.select(selector):
            x.decompose()

    for x in body.find_all("a", href=True):
        if x["href"].startswith("#"):
            x.attrs.pop("href", None)

    return title, str(body)


def fix_image_sources(body_html: str, base_url: str) -> str:
    soup = BeautifulSoup(body_html, "lxml")
    for img in soup.find_all("img"):
        src_candidates = [
            img.get("data-src"),
            img.get("data-original"),
            img.get("src"),
        ]
        if not any(src_candidates) and img.get("srcset"):
            srcset = img.get("srcset")
            first = srcset.split(",")[0].strip().split(" ")[0]
            src_candidates = [first]
        real = next((s for s in src_candidates if s), None)
        if not real:
            continue
        real = real.strip()
        if real.startswith("//"):
            real = "https:" + real
        elif not real.startswith("http"):
            real = requests.compat.urljoin(base_url, real)
        img["src"] = real
        for attr in ["srcset", "data-src", "data-original", "data-lazy-src", "loading"]:
            if attr in img.attrs:
                img.attrs.pop(attr, None)
    return str(soup)


def html_to_markdown(html: str) -> str:
    try:
        return md(html, heading_style="ATX", bullets="-*+")
    except Exception:
        try:
            return md(html)
        except Exception:
            try:
                soup = BeautifulSoup(html, "lxml")
                return soup.get_text("\n")
            except Exception:
                return html


def fetch_article_content(client: HttpClient, cfg: Config, article_url: str) -> Tuple[str, str]:
    html = client.get(article_url)
    soup = BeautifulSoup(html, "lxml")
    title, body_html = extract_title_and_body(soup)
    body_html = fix_image_sources(body_html, article_url)
    md_text = html_to_markdown(body_html)
    return title, md_text


def get_done_marker_path(root_dir: str, tag_name: str, article_id: str) -> str:
    tag_dir = os.path.join(root_dir, sanitize_filename(tag_name))
    done_dir = os.path.join(tag_dir, ".done")
    ensure_dir(done_dir)
    return os.path.join(done_dir, f"p{article_id}.done")


def save_article_to_markdown(root_dir: str, tag_name: str, title: str, markdown_content: str, article_id: Optional[str] = None) -> str:
    tag_dir = os.path.join(root_dir, sanitize_filename(tag_name))
    ensure_dir(tag_dir)
    suffix = f" [p{article_id}]" if article_id else ""
    filename = (sanitize_filename(title) or "untitled") + suffix
    path = os.path.join(tag_dir, f"{filename}.md")

    base, ext = os.path.splitext(path)
    index = 1
    while os.path.exists(path):
        path = f"{base} ({index}){ext}"
        index += 1

    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(markdown_content)
    return path


def crawl_single_tag(client: HttpClient, cfg: Config, tag_name: str, tag_url: str) -> None:
    log_info(f"开始爬取标签：{tag_name} -> {tag_url}")
    random_delay(cfg)
    links = get_article_links(client, cfg, tag_url)
    log_info(f"标签 {tag_name} 共获取文章链接 {len(links)} 条。")

    for idx, url in enumerate(links, start=1):
        try:
            article_id = extract_article_id(url)
            if cfg.resume and article_id:
                marker = get_done_marker_path(cfg.root_dir, tag_name, article_id)
                if os.path.exists(marker):
                    log_info(f"[{tag_name}] 跳过已完成 p{article_id}：{url}")
                    continue

            random_delay(cfg)
            title, md_text = fetch_article_content(client, cfg, url)
            saved_path = save_article_to_markdown(cfg.root_dir, tag_name, title, md_text, article_id)

            if article_id:
                marker = get_done_marker_path(cfg.root_dir, tag_name, article_id)
                with open(marker, "w", encoding="utf-8") as f:
                    f.write(url)

            log_info(f"[{tag_name}] 第 {idx}/{len(links)} 篇《{title}》已保存：{saved_path}")
        except Exception as e:
            log_error(f"抓取文章失败：{url}，原因：{e}")


def crawl_all(cfg: Config) -> None:
    client = HttpClient(DEFAULT_HEADERS)
    ensure_dir(cfg.root_dir)

    tags = get_all_tags(client, cfg, cfg.base_tag_url)
    if cfg.only_tags:
        missing = [t for t in cfg.only_tags if t not in tags]
        if missing:
            log_warn(f"以下指定标签未在页面解析到：{missing}")

    items = list(tags.items())

    if cfg.threads <= 1:
        for name, url in items:
            crawl_single_tag(client, cfg, name, url)
    else:
        from concurrent.futures import ThreadPoolExecutor, as_completed
        max_workers = min(max(cfg.threads, 1), 8)
        log_info(f"并发抓取启用：{max_workers} 线程。请注意访问频率合规。")
        with ThreadPoolExecutor(max_workers=max_workers) as ex:
            futures = {ex.submit(crawl_single_tag, client, cfg, name, url): name for name, url in items}
            for fut in as_completed(futures):
                name = futures[fut]
                try:
                    fut.result()
                except Exception as e:
                    log_error(f"并发抓取标签 {name} 失败：{e}")


def parse_args(argv: Optional[Iterable[str]] = None) -> Config:
    p = argparse.ArgumentParser(description="标签文章爬取器")
    p.add_argument("--root", default=DEFAULT_ROOT_DIR, help="保存根目录")
    p.add_argument("--delay-min", type=float, default=1.0, help="相邻请求最小延迟秒")
    p.add_argument("--delay-max", type=float, default=2.0, help="相邻请求最大延迟秒")
    p.add_argument("--retries", type=int, default=3, help="请求失败重试次数（全局占位，当前使用装饰器固定为3）")
    p.add_argument("--threads", type=int, default=1, help="下载线程数（谨慎提高以避免触发风控）")
    p.add_argument("--only-tags", type=str, default=None, help="仅抓取指定标签，逗号分隔")
    p.add_argument("--no-resume", dest="resume", action="store_false", help="禁用断点续爬（默认开启）")
    p.add_argument("--config", type=str, default="config.json", help="JSON 配置文件路径（可覆盖 base_tag_url 等）")
    p.set_defaults(resume=True)

    args = p.parse_args(argv)

    only_tags_list = [s.strip() for s in args.only_tags.split(",")] if args.only_tags else None

    if args.delay_min <= 0 or args.delay_max <= 0 or args.delay_min > args.delay_max:
        log_warn("delay 参数不合理，重置为 1.0~2.0 秒。")
        args.delay_min, args.delay_max = 1.0, 2.0

    base_tag_url = BASE_TAG_URL
    if args.config and os.path.exists(args.config):
        try:
            with open(args.config, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict) and data.get("base_tag_url"):
                base_tag_url = str(data["base_tag_url"]).strip()
                log_info(f"从配置文件加载 base_tag_url：{base_tag_url}")
        except Exception as e:
            log_warn(f"读取配置文件失败，将使用默认 base_tag_url：{e}")

    return Config(
        root_dir=args.root,
        delay_min=args.delay_min,
        delay_max=args.delay_max,
        retries=args.retries,
        threads=args.threads,
        only_tags=only_tags_list,
        resume=args.resume,
        base_tag_url=base_tag_url,
    )


def main() -> None:
    cfg = parse_args()
    log_info(f"保存目录：{cfg.root_dir}")
    try:
        crawl_all(cfg)
        log_info("任务完成。")
    except KeyboardInterrupt:
        log_warn("用户中断。")
    except Exception as e:
        log_error(f"运行失败：{e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

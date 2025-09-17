#!/usr/bin/env python3
# -*- coding: utf-8 -*-


import os
import re
import requests
import urllib.parse
from pathlib import Path
import time
import hashlib

def get_image_extension(url):
    """
    从URL中提取图片扩展名
    
    Args:
        url (str): 图片URL
        
    Returns:
        str: 图片扩展名，默认为.jpg
    """
    try:
        parsed_url = urllib.parse.urlparse(url)
        path = parsed_url.path
        if '.' in path:
            ext = os.path.splitext(path)[1].lower()
            if ext in ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.svg']:
                return ext
    except:
        pass
    return '.jpg'  # 默认扩展名

def download_image(url, local_path, max_retries=3):
    """
    下载图片到本地
    
    Args:
        url (str): 图片URL
        local_path (str): 本地保存路径
        max_retries (int): 最大重试次数
        
    Returns:
        bool: 下载是否成功
    """
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    for attempt in range(max_retries):
        try:
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            
            # 确保目录存在
            os.makedirs(os.path.dirname(local_path), exist_ok=True)
            
            # 保存图片
            with open(local_path, 'wb') as f:
                f.write(response.content)
            
            print(f"  ✓ 下载成功: {os.path.basename(local_path)}")
            return True
            
        except Exception as e:
            print(f"  ✗ 下载失败 (尝试 {attempt + 1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                time.sleep(2)  # 等待2秒后重试
    
    return False

def generate_local_filename(url, index=0):
    """
    生成本地文件名
    
    Args:
        url (str): 图片URL
        index (int): 索引，用于避免重名
        
    Returns:
        str: 本地文件名
    """
    # 使用URL的hash值作为文件名基础
    url_hash = hashlib.md5(url.encode()).hexdigest()[:8]
    ext = get_image_extension(url)
    
    if index > 0:
        return f"image_{url_hash}_{index}{ext}"
    else:
        return f"image_{url_hash}{ext}"

def process_md_file(file_path, images_dir="images"):
    """
    处理单个md文件，下载图片并更新链接
    
    Args:
        file_path (str): md文件路径
        images_dir (str): 图片存储目录名
        
    Returns:
        tuple: (是否修改了文件, 下载的图片数量, 失败的图片数量)
    """
    try:
        # 读取文件内容
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 查找所有图片链接
        # 匹配格式: ![](url) 或 ![alt](url)
        image_pattern = r'!\[([^\]]*)\]\((https?://[^\)]+)\)'
        matches = re.findall(image_pattern, content)
        
        if not matches:
            return False, 0, 0
        
        print(f"处理文件: {file_path}")
        print(f"  找到 {len(matches)} 个图片链接")
        
        # 获取文件所在目录
        file_dir = os.path.dirname(file_path)
        local_images_dir = os.path.join(file_dir, images_dir)
        
        # 统计信息
        downloaded_count = 0
        failed_count = 0
        new_content = content
        
        # 处理每个图片链接
        for i, (alt_text, url) in enumerate(matches):
            try:
                # 生成本地文件名
                local_filename = generate_local_filename(url, i)
                local_path = os.path.join(local_images_dir, local_filename)
                
                # 检查文件是否已存在
                if os.path.exists(local_path):
                    print(f"  - 图片已存在: {local_filename}")
                    downloaded_count += 1
                else:
                    # 下载图片
                    if download_image(url, local_path):
                        downloaded_count += 1
                    else:
                        failed_count += 1
                        continue
                
                # 更新md文件中的链接
                old_link = f"![{alt_text}]({url})"
                new_link = f"![{alt_text}]({images_dir}/{local_filename})"
                new_content = new_content.replace(old_link, new_link)
                
            except Exception as e:
                print(f"  ✗ 处理图片失败: {e}")
                failed_count += 1
        
        # 如果内容有变化，写回文件
        if new_content != content:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(new_content)
            print(f"  ✓ 文件已更新")
            return True, downloaded_count, failed_count
        else:
            print(f"  - 文件无需更新")
            return False, downloaded_count, failed_count
            
    except Exception as e:
        print(f"处理文件 {file_path} 时出错: {e}")
        return False, 0, 0

def download_articles_images(articles_dir="Articles", images_dir="images"):     #扫描文件夹名称
    """
    递归遍历Articles目录，下载所有图片并更新md文件
    
    Args:
        articles_dir (str): Articles目录路径
        images_dir (str): 图片存储目录名
    """
    if not os.path.exists(articles_dir):
        print(f"错误: 目录 {articles_dir} 不存在")
        return
    
    # 统计信息
    total_files = 0
    modified_files = 0
    total_downloaded = 0
    total_failed = 0
    
    print(f"开始处理目录: {os.path.abspath(articles_dir)}")
    print(f"图片将保存到各md文件同级的 '{images_dir}' 目录中")
    print("=" * 60)
    
    # 递归遍历所有md文件
    for root, dirs, files in os.walk(articles_dir):
        for file in files:
            if file.endswith('.md'):
                file_path = os.path.join(root, file)
                total_files += 1
                
                # 处理文件
                modified, downloaded, failed = process_md_file(file_path, images_dir)
                
                if modified:
                    modified_files += 1
                
                total_downloaded += downloaded
                total_failed += failed
                
                print()  # 空行分隔
    
    print("=" * 60)
    print(f"处理完成!")
    print(f"总共处理文件: {total_files}")
    print(f"修改的文件: {modified_files}")
    print(f"成功下载图片: {total_downloaded}")
    print(f"下载失败图片: {total_failed}")

if __name__ == "__main__":
    print("MD文档图片下载工具 - 自动执行版本")
    print("将下载外链图片到本地并更新md文档中的图片链接")
    print()
    
    # 直接执行下载
    download_articles_images()




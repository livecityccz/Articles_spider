#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import re
import sys
from pathlib import Path


def log_info(message: str) -> None:
    """输出信息日志"""
    print(f"[INFO] {message}")


def log_warn(message: str) -> None:
    """输出警告日志"""
    print(f"[WARN] {message}")


def log_error(message: str) -> None:
    """输出错误日志"""
    print(f"[ERROR] {message}", file=sys.stderr)


def remove_article_id_suffix(filename: str) -> str:
    """
    从文件名中移除类似 [p9916437] 的后缀
    
    Args:
        filename: 原始文件名
        
    Returns:
        处理后的文件名
    """
    # 匹配 [p数字] 模式的后缀，支持文件名中的中文字符
    # 使用更宽松的匹配，不要求必须在行尾
    pattern = r'\s*\[p\d+\]\s*'
    cleaned = re.sub(pattern, '', filename)
    return cleaned


def process_file(file_path: Path, dry_run: bool = True) -> bool:
    """
    处理单个文件，移除文件名中的文章ID后缀
    
    Args:
        file_path: 文件路径
        dry_run: 是否为试运行模式（不实际重命名）
        
    Returns:
        是否成功处理
    """
    try:
        original_name = file_path.name
        cleaned_name = remove_article_id_suffix(original_name)
        
        # 如果文件名没有变化，跳过
        if original_name == cleaned_name:
            return True
            
        new_path = file_path.parent / cleaned_name
        
        # 检查新文件名是否已存在
        if new_path.exists():
            log_warn(f"目标文件已存在，跳过重命名: {file_path} -> {new_path}")
            return False
            
        if dry_run:
            log_info(f"[试运行] 将重命名: {file_path} -> {new_path}")
        else:
            file_path.rename(new_path)
            log_info(f"已重命名: {file_path} -> {new_path}")
            
        return True
        
    except Exception as e:
        log_error(f"处理文件失败 {file_path}: {e}")
        return False


def process_directory(directory: Path, dry_run: bool = True, file_extensions: list = None) -> tuple:
    """
    递归处理目录中的所有文件
    
    Args:
        directory: 要处理的目录路径
        dry_run: 是否为试运行模式
        file_extensions: 要处理的文件扩展名列表，None表示处理所有文件
        
    Returns:
        (成功处理的文件数, 总文件数)
    """
    if not directory.exists() or not directory.is_dir():
        log_error(f"目录不存在或不是有效目录: {directory}")
        return 0, 0
        
    success_count = 0
    total_count = 0
    
    # 递归遍历目录
    for file_path in directory.rglob('*'):
        if file_path.is_file():
            # 如果指定了文件扩展名，检查是否匹配
            if file_extensions:
                if file_path.suffix.lower() not in file_extensions:
                    continue
                    
            total_count += 1
            if process_file(file_path, dry_run):
                success_count += 1
                
    return success_count, total_count


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description="递归重命名Articles目录下的文件，移除[p数字]后缀")
    parser.add_argument("--directory", "-d", default="Articles", 
                       help="要处理的目录路径 (默认: Articles)")
    parser.add_argument("--extensions", "-e", nargs="+", default=[".md", ".html", ".txt"],
                       help="要处理的文件扩展名 (默认: .md .html .txt)")
    parser.add_argument("--dry-run", action="store_true", default=True,
                       help="试运行模式，不实际重命名文件 (默认开启)")
    parser.add_argument("--execute", action="store_true",
                       help="执行实际重命名操作")
    
    args = parser.parse_args()
    
    # 如果指定了 --execute，则关闭试运行模式
    if args.execute:
        args.dry_run = False
        
    directory = Path(args.directory)
    
    if not directory.exists():
        log_error(f"目录不存在: {directory}")
        sys.exit(1)
        
    # 转换扩展名为小写
    extensions = [ext.lower() if ext.startswith('.') else f'.{ext.lower()}' 
                  for ext in args.extensions]
    
    log_info(f"开始处理目录: {directory}")
    log_info(f"文件扩展名: {extensions}")
    log_info(f"模式: {'试运行' if args.dry_run else '实际执行'}")
    
    success_count, total_count = process_directory(directory, args.dry_run, extensions)
    
    log_info(f"处理完成: 成功 {success_count}/{total_count} 个文件")
    
    if args.dry_run and success_count > 0:
        log_info("这是试运行模式，如需实际执行请添加 --execute 参数")


if __name__ == "__main__":
    main()

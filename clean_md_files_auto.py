#!/usr/bin/env python3
# -*- coding: utf-8 -*-


import os

def clean_md_file(file_path):
    """
    清理单个md文件，删除包含指定关键词的行
    
    Args:
        file_path (str): 文件路径
        
    Returns:
        tuple: (是否修改了文件, 删除的行数)
    """
    try:
        # 读取文件内容
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        # 记录原始行数
        original_line_count = len(lines)
        
        # 过滤掉包含的行
        filtered_lines = []
        removed_lines = []
        
        for line in lines:
            if "XXX" in line or "cnblogs.com" in line:      #填写过滤内容
                removed_lines.append(line.strip())
            else:
                filtered_lines.append(line)
        
        # 如果没有删除任何行，直接返回
        if len(filtered_lines) == original_line_count:
            return False, 0
        
        # 写回文件
        with open(file_path, 'w', encoding='utf-8') as f:
            f.writelines(filtered_lines)
        
        return True, len(removed_lines)
        
    except Exception as e:
        print(f"处理文件 {file_path} 时出错: {e}")
        return False, 0

def clean_articles_directory(articles_dir="Articles"):
    """
    递归遍历Articles目录，清理所有md文件
    
    Args:
        articles_dir (str): Articles目录路径
    """
    if not os.path.exists(articles_dir):
        print(f"错误: 目录 {articles_dir} 不存在")
        return
    
    # 统计信息
    total_files = 0
    modified_files = 0
    total_removed_lines = 0
    
    print(f"开始清理目录: {os.path.abspath(articles_dir)}")
    print("=" * 50)
    
    # 递归遍历所有md文件
    for root, dirs, files in os.walk(articles_dir):
        for file in files:
            if file.endswith('.md'):
                file_path = os.path.join(root, file)
                total_files += 1
                
                print(f"处理文件: {file_path}")
                
                # 清理文件
                modified, removed_count = clean_md_file(file_path)
                
                if modified:
                    modified_files += 1
                    total_removed_lines += removed_count
                    print(f"  ✓ 已修改，删除了 {removed_count} 行")
                else:
                    print(f"  - 无需修改")
    
    print("=" * 50)
    print(f"清理完成!")
    print(f"总共处理文件: {total_files}")
    print(f"修改的文件: {modified_files}")
    print(f"总共删除行数: {total_removed_lines}")

if __name__ == "__main__":
    print("MD文件清理工具 - 自动执行版本")
    print("将删除包含'尹正杰'和'版权声明'的行")
    print()
    
    # 直接执行清理
    clean_articles_directory()

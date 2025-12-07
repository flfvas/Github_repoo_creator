#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GitHub 远程仓库自动创建工具
支持通过 GitHub CLI 或 Personal Access Token 创建仓库
"""

import os
import sys
import subprocess
import json
import requests
from pathlib import Path

# 处理打包后的路径问题
if getattr(sys, 'frozen', False):
    # 如果是打包后的程序
    application_path = os.path.dirname(sys.executable)
else:
    # 如果是脚本运行
    application_path = os.path.dirname(os.path.abspath(__file__))

# 尝试导入 pyperclip，如果失败则使用备选方案
try:
    import pyperclip

    CLIPBOARD_AVAILABLE = True
except ImportError:
    CLIPBOARD_AVAILABLE = False
    print("[警告] pyperclip 模块未安装，将无法自动复制到剪贴板")


class GitHubRepoCreator:
    def __init__(self):
        self.use_gh_cli = self.check_gh_cli()
        self.token = None
        self.username = None

    def check_gh_cli(self):
        """检查是否安装了 GitHub CLI"""
        try:
            result = subprocess.run(['gh', '--version'],
                                    capture_output=True,
                                    text=True,
                                    encoding='utf-8',
                                    errors='ignore',
                                    timeout=5)
            return result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False

    def check_gh_auth(self):
        """检查 GitHub CLI 登录状态"""
        try:
            result = subprocess.run(['gh', 'auth', 'status'],
                                    capture_output=True,
                                    text=True,
                                    encoding='utf-8',
                                    errors='ignore',
                                    timeout=5)
            return result.returncode == 0
        except subprocess.TimeoutExpired:
            return False

    def gh_login(self):
        """启动 GitHub CLI 登录流程"""
        print("\n[提示] 正在启动 GitHub CLI 登录流程...")
        try:
            subprocess.run(['gh', 'auth', 'login'], check=True)
            return True
        except subprocess.CalledProcessError:
            return False

    def get_token_from_input(self):
        """从用户输入获取 PAT"""
        print("\n" + "=" * 50)
        print("GitHub Personal Access Token (PAT) 配置")
        print("=" * 50)
        print("\n如何获取 PAT:")
        print("1. 访问: https://github.com/settings/tokens")
        print("2. 点击 'Generate new token' → 'Tokens (classic)'")
        print("3. 勾选 'repo' 权限")
        print("4. 生成并复制 Token\n")

        token = input("请输入你的 GitHub PAT (或按 Enter 跳过): ").strip()
        return token if token else None

    def get_username_from_token(self, token):
        """通过 API 获取用户名"""
        headers = {
            'Authorization': f'token {token}',
            'Accept': 'application/vnd.github.v3+json'
        }
        try:
            response = requests.get('https://api.github.com/user',
                                    headers=headers,
                                    timeout=10)
            if response.status_code == 200:
                return response.json()['login']
            else:
                print(f"[错误] 获取用户信息失败: {response.status_code}")
                return None
        except requests.RequestException as e:
            print(f"[错误] 网络请求失败: {e}")
            return None

    def get_username_from_gh(self):
        """通过 GitHub CLI 获取用户名"""
        try:
            result = subprocess.run(['gh', 'api', 'user', '--jq', '.login'],
                                    capture_output=True,
                                    text=True,
                                    encoding='utf-8',
                                    errors='ignore',
                                    timeout=10)
            if result.returncode == 0:
                return result.stdout.strip()
            return None
        except subprocess.TimeoutExpired:
            return None

    def create_repo_with_gh(self, repo_name, description, is_private):
        """使用 GitHub CLI 创建仓库"""
        cmd = ['gh', 'repo', 'create', repo_name]
        cmd.append('--private' if is_private else '--public')

        if description:
            cmd.extend(['--description', description])

        try:
            result = subprocess.run(cmd,
                                    capture_output=True,
                                    text=True,
                                    encoding='utf-8',
                                    errors='ignore',
                                    timeout=30)
            return result.returncode == 0, result.stderr
        except subprocess.TimeoutExpired:
            return False, "命令执行超时"

    def create_repo_with_api(self, token, repo_name, description, is_private):
        """使用 GitHub API 创建仓库"""
        headers = {
            'Authorization': f'token {token}',
            'Accept': 'application/vnd.github.v3+json'
        }

        data = {
            'name': repo_name,
            'private': is_private,
            'auto_init': False
        }

        if description:
            data['description'] = description

        try:
            response = requests.post('https://api.github.com/user/repos',
                                     headers=headers,
                                     json=data,
                                     timeout=30)

            if response.status_code == 201:
                return True, None
            else:
                error_msg = response.json().get('message', '未知错误')
                return False, f"创建失败 ({response.status_code}): {error_msg}"
        except requests.RequestException as e:
            return False, f"网络请求失败: {e}"

    def setup_auth(self):
        """设置认证方式"""
        print("\n" + "=" * 50)
        print("     GitHub 远程仓库自动创建工具")
        print("=" * 50)

        # 检查 GitHub CLI
        if self.use_gh_cli:
            print("\n[检测] 已安装 GitHub CLI")
            if self.check_gh_auth():
                print("[检测] GitHub CLI 已登录")
                self.username = self.get_username_from_gh()
                return True
            else:
                print("[检测] GitHub CLI 未登录")
                choice = input("\n是否使用 GitHub CLI 登录? (Y/N, 默认 Y): ").strip().upper()
                if choice != 'N':
                    if self.gh_login():
                        self.username = self.get_username_from_gh()
                        return True
                    else:
                        print("[错误] GitHub CLI 登录失败")
        else:
            print("\n[提示] 未检测到 GitHub CLI")
            print("可以安装 GitHub CLI: https://cli.github.com/")

        # 使用 PAT
        self.token = self.get_token_from_input()
        if not self.token:
            print("\n[错误] 未配置任何认证方式")
            return False

        self.username = self.get_username_from_token(self.token)
        if not self.username:
            print("[错误] Token 验证失败")
            return False

        print(f"[成功] 已验证用户: {self.username}")
        return True

    def get_repo_info(self):
        """获取仓库信息"""
        print("\n" + "-" * 50)

        # 仓库名称
        repo_name = input("请输入仓库名称: ").strip()
        if not repo_name:
            print("[错误] 仓库名称不能为空")
            return None

        # 默认描述为 1.0
        description = "1.0"

        # 默认为公开仓库
        is_private = False

        return {
            'name': repo_name,
            'description': description,
            'is_private': is_private
        }

    def create_repository(self):
        """创建仓库主流程"""
        if not self.setup_auth():
            return False

        repo_info = self.get_repo_info()
        if not repo_info:
            return False

        # 显示信息但不需要确认
        print("\n" + "-" * 50)
        print(f"仓库名称: {repo_info['name']}")
        print(f"仓库描述: {repo_info['description']}")
        print(f"可见性: {'私有' if repo_info['is_private'] else '公开'}")
        print("-" * 50)

        # 创建仓库
        print("\n[信息] 正在创建仓库...")

        if self.use_gh_cli and not self.token:
            success, error = self.create_repo_with_gh(
                repo_info['name'],
                repo_info['description'],
                repo_info['is_private']
            )
        else:
            success, error = self.create_repo_with_api(
                self.token,
                repo_info['name'],
                repo_info['description'],
                repo_info['is_private']
            )

        if not success:
            print(f"[错误] 仓库创建失败: {error}")
            return False

        # 构建仓库 URL
        repo_url = f"https://github.com/{self.username}/{repo_info['name']}.git"

        print(f"\n[成功] 仓库创建成功!")
        print(f"\n仓库地址: {repo_url}")

        # 复制到剪贴板
        if CLIPBOARD_AVAILABLE:
            try:
                pyperclip.copy(repo_url)
                print("\n[成功] 仓库地址已复制到剪贴板!")
            except Exception as e:
                print(f"\n[警告] 复制到剪贴板失败: {e}")
                print("请手动复制上面的地址")
        else:
            print("\n[提示] 请手动复制上面的地址")

        return True


def main():
    # 设置控制台编码为 UTF-8
    if sys.platform == 'win32':
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32
            kernel32.SetConsoleOutputCP(65001)
            kernel32.SetConsoleCP(65001)
        except:
            pass

    # 确保即使出错也能看到错误信息
    try:
        print("正在启动 GitHub 仓库创建工具...")
        print("Python 版本:", sys.version)
        print("工作目录:", os.getcwd())
        print()

        creator = GitHubRepoCreator()
        success = creator.create_repository()

        # 无论成功失败都等待用户按键
        if success:
            print("\n" + "=" * 50)
            print("操作完成!")
            print("=" * 50)

    except KeyboardInterrupt:
        print("\n\n[提示] 用户取消操作")
    except Exception as e:
        print(f"\n[错误] 发生未预期的错误: {e}")
        print(f"错误类型: {type(e).__name__}")
        import traceback
        print("\n完整错误信息:")
        traceback.print_exc()
    finally:
        # 确保窗口不会闪退
        print("\n" + "=" * 50)
        input("按 Enter 键退出...")


if __name__ == '__main__':
    main()
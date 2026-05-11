#!/usr/bin/env python3
"""
打包 Python 服务器为独立可执行文件
"""
import subprocess
import shutil
from pathlib import Path

def _find_pyinstaller(project_root: Path) -> Path:
    venv_pyinstaller = project_root / ".venv312" / "Scripts" / "pyinstaller.exe"
    if venv_pyinstaller.exists():
        return venv_pyinstaller
    return Path("pyinstaller")


def main():
    script_dir = Path(__file__).resolve().parent
    project_root = script_dir.parents[2]
    server_dir = project_root / "apps" / "server"
    resources_dir = project_root / "apps" / "desktop" / "src-tauri" / "resources"
    
    print(f"脚本目录: {script_dir}")
    print(f"项目根目录: {project_root}")
    print(f"服务器目录: {server_dir}")
    print(f"资源目录: {resources_dir}")
    
    output_dir = resources_dir / "gjj-ocr-server"
    if output_dir.exists():
        print(f"删除旧的输出目录: {output_dir}")
        shutil.rmtree(output_dir)
    
    pyinstaller = _find_pyinstaller(project_root)
    print(f"\n使用 PyInstaller: {pyinstaller}")
    print("开始打包 Python 服务器...")
    result = subprocess.run(
        [str(pyinstaller), "gjj-ocr-server.spec", "--noconfirm"],
        cwd=server_dir,
        capture_output=True,
        text=True
    )
    
    if result.returncode != 0:
        print("打包失败!")
        print(result.stdout)
        print(result.stderr)
        return 1
    
    print("打包成功!")
    
    dist_dir = server_dir / "dist" / "gjj-ocr-server"
    if dist_dir.exists():
        print(f"复制打包结果到: {output_dir}")
        shutil.copytree(dist_dir, output_dir)
        # 清理构建过程中产生的 __pycache__
        for pycache in output_dir.parent.rglob("__pycache__"):
            if pycache.is_dir():
                shutil.rmtree(pycache, ignore_errors=True)
        print("完成!")
    else:
        print(f"错误: 打包结果目录不存在: {dist_dir}")
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main())

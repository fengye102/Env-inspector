"""env_inspector — 环境探针
一键扫描本机已安装的开发环境,以直观 GUI 呈现结果。
"""

import sys
import os

# 确保项目根目录在 sys.path 中
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ui.app import App


def main():
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()
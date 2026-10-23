"""系统适配层：所有和操作系统打交道的地方都在这里。主流程只调用这些函数，不关心是 macOS 还是 Windows。
接口（两个实现必须一致）：
  NAME / FILE_MANAGER                    系统名、文件管理器名（访达 / 资源管理器）
  data_volume() / disk_status()          数据盘、(可用字节, 总字节)
  du_bytes(path) / dir_sizes(root, depth)目录占用
  find_large_files(home, min_bytes)      大文件列表
  running_processes()                    正在运行的进程名集合
  to_trash(path, home)                   移到废纸篓 / 回收站，返回目标路径
  reveal(path, folder)                   在文件管理器中打开文件夹或定位文件
  notify(title, text) / show_alert(...)  系统通知 / 提醒弹窗（返回 scan / later）
  install_monitor(...) / uninstall_monitor(label) / monitor_loaded(label)  后台定时检查
"""
import sys

if sys.platform == "win32":
    from plat.win import *  # noqa: F401,F403
else:
    from plat.mac import *  # noqa: F401,F403

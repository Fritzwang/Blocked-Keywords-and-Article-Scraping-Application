"""双击程序入口；诊断选项仅供打包后验收使用。"""
import argparse
import json
import logging
from pathlib import Path
import sys


def app_directory() -> Path:
    return Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--self-test", metavar="REPORT")
    parser.add_argument("--smoke-ui", action="store_true")
    parser.add_argument("--test-url")
    args = parser.parse_args()
    if args.self_test:
        from clipdesk.diagnostics import run
        report = {}
        try:
            report = run(ui=args.smoke_ui, url=args.test_url)
            report["ok"] = True
        except Exception:
            import traceback
            report = {"ok": False, "error": traceback.format_exc()}
        Path(args.self_test).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        return 0 if report["ok"] else 1
    import tkinter as tk
    from tkinter import messagebox
    root = tk.Tk()
    root.withdraw()
    data_dir = app_directory() / "data"
    try:
        data_dir.mkdir(parents=True, exist_ok=True)
        from logging.handlers import RotatingFileHandler
        logging.basicConfig(handlers=[RotatingFileHandler(data_dir / "app.log", maxBytes=1024 * 1024, backupCount=2, encoding="utf-8")], level=logging.WARNING, format="%(asctime)s %(levelname)s %(message)s")
        from clipdesk.ui import App
        App(root, data_dir)
        icon = Path(getattr(sys, "_MEIPASS", app_directory())) / "assets" / "app.ico"
        if icon.exists():
            root.iconbitmap(str(icon))
    except Exception as exc:
        logging.exception("启动失败")
        messagebox.showerror("无法启动网页摘录", f"{exc}\n\n请将程序放在可写入的普通文件夹，再重新启动。", parent=root)
        root.destroy()
        return 1

    def callback_error(kind, value, tb):
        logging.error("界面操作失败", exc_info=(kind, value, tb))
        messagebox.showerror("操作未完成", str(value), parent=root)
    root.report_callback_exception = callback_error
    root.deiconify()
    root.mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())

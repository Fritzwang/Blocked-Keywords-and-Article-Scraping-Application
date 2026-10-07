from dataclasses import asdict
import json
from pathlib import Path
import queue
import re
import sqlite3
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from .extractor import ExtractionError, fetch_article, normalize_url
from .models import Article
from .replacement import Rule, preview
from .storage import Store
from .i18n import t, translate, refresh_widgets

BG = "#f3f5f9"
INK = "#192a42"
MUTED = "#718096"
BLUE = "#2563eb"
NAVY = "#17253d"
FONT = "Microsoft YaHei UI"


def button(parent, text, command, primary=False, **kwargs):
    return tk.Button(parent, text=text, command=command, font=(FONT, 10),
                     bg=BLUE if primary else "#eaf0fa", fg="white" if primary else INK,
                     activebackground="#1d4ed8" if primary else "#dce6f7",
                     activeforeground="white" if primary else INK,
                     disabledforeground="#a5b1c4", relief="flat", bd=0,
                     cursor="hand2", padx=15, pady=8, **kwargs)


class App:
    def __init__(self, root: tk.Tk, data_dir: Path):
        self.root = root
        self.language = 'zh'
        self.dialogs = []
        self.modal_action = False
        self.data_dir = data_dir
        self.store = Store(data_dir / "articles.db")
        self.current: Article | None = None
        self.loading = False
        self.refreshing = False
        self.busy = False
        self.save_job = None
        self.context_article_id = None
        self.messages = queue.Queue()
        self.root.title(self.t('网页摘录 · 内容编辑器'))
        width = max(1000, min(1180, self.root.winfo_screenwidth() - 60))
        height = max(680, min(800, self.root.winfo_screenheight() - 90))
        self.root.geometry(f"{width}x{height}")
        self.root.minsize(1000, 680)
        self.root.configure(bg=BG)
        self.root.option_add("*Font", (FONT, 10))
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self._styles()
        self._build()
        self._menus()
        self.refresh_list()
        articles = self.store.all()
        if articles:
            self.show_article(articles[0])
        else:
            self.show_empty()
        self.root.bind("<Control-s>", lambda event: self.save_now())
        self.root.bind("<Control-n>", lambda event: self.new_article())
        self.root.bind("<Control-h>", lambda event: self.open_replace())
        self.root.after(100, self.poll)
        self.url_entry.focus_set()

    def t(self, key, **values):
        return t(key, self.language, **values)

    def toggle_language(self):
        self.set_language('en' if self.language == 'zh' else 'zh')

    def set_language(self, language):
        if language not in ('zh', 'en') or language == self.language:
            return
        old = self.language
        self.language = language
        refresh_widgets(self.root, language, old)
        for variable in (self.status_var, self.length_var, self.draft_count):
            variable.set(translate(variable.get(), language, old))
        if not self.current or not self.current.url:
            self.source_var.set(translate(self.source_var.get(), language, old))
        self.refresh_list()
        self.dialogs = [dialog for dialog in self.dialogs if dialog.window.winfo_exists()]
        for dialog in self.dialogs:
            dialog.refresh_language(old)

    def open_challenge(self):
        if self.busy:
            messagebox.showinfo(self.t('文本再生'), self.t('请等待当前抓取完成后再开始文本再生。'), parent=self.root)
            return
        if not self.current:
            messagebox.showinfo(self.t('文本再生'), self.t('当前没有文章，请先抓取或新建文章。'), parent=self.root)
            return
        from .challenge_ui import ChallengeDialog
        # Snapshot the actual editor contents without writing game state or
        # forcing a save; the original editor and its undo stack stay intact.
        dialog = ChallengeDialog(self, self.editor.get('1.0', 'end-1c'))
        self.dialogs.append(dialog)
        return dialog

    def open_twisted(self):
        if self.busy:
            messagebox.showinfo(self.t('模式 3 · 扭曲再生'), self.t('请等待当前抓取完成后再开始文本再生。'), parent=self.root)
            return
        if not self.current:
            messagebox.showinfo(self.t('模式 3 · 扭曲再生'), self.t('当前没有文章，请先抓取或新建文章。'), parent=self.root)
            return
        from .twisted_ui import TwistedDialog
        dialog = TwistedDialog(self, self.editor.get('1.0', 'end-1c'))
        self.dialogs.append(dialog)
        return dialog

    def open_reframe(self):
        if self.busy:
            messagebox.showinfo(self.t('模式 4 · 重构再生'), self.t('请等待当前抓取完成后再开始文本再生。'), parent=self.root)
            return
        if not self.current:
            messagebox.showinfo(self.t('模式 4 · 重构再生'), self.t('当前没有文章，请先抓取或新建文章。'), parent=self.root)
            return
        from .reframe_ui import ReframeDialog
        dialog = ReframeDialog(self, self.editor.get('1.0', 'end-1c'))
        self.dialogs.append(dialog)
        return dialog

    def open_cipher(self):
        existing = getattr(self, 'cipher_dialog', None)
        if existing is not None and existing.window.winfo_exists():
            existing.window.lift()
            existing.window.focus_set()
            return existing
        from .cipher import CipherGame
        from .cipher_ui import CipherDialog
        source = self.editor.get('1.0', 'end-1c') if self.current else ''
        try:
            CipherGame.validate_source(source)
        except ValueError as exc:
            messagebox.showinfo(self.t('密码破译'), self.t(str(exc)), parent=self.root)
            return
        try:
            game = CipherGame(self.data_dir / 'cipher_game.db', source=source)
        except (OSError, sqlite3.Error, ValueError, TypeError, KeyError) as exc:
            self.error(self.t('无法打开密码进度'), exc)
            return
        try:
            dialog = CipherDialog(self, game)
        except Exception:
            game.close()
            raise
        self.cipher_dialog = dialog
        self.dialogs.append(dialog)
        return dialog

    def _styles(self):
        style = ttk.Style(self.root)
        style.theme_use("clam")
        style.configure("Draft.Treeview", background=NAVY, fieldbackground=NAVY,
                        foreground="#d8e3f6", borderwidth=0, rowheight=58, font=(FONT, 10))
        style.map("Draft.Treeview", background=[("selected", "#2b4269")], foreground=[("selected", "white")])
        style.layout("Draft.Treeview", [("Treeview.treearea", {"sticky": "nswe"})])
        style.configure("TCombobox", padding=5)
        style.configure("TProgressbar", background=BLUE, troughcolor="#e4eaf3", borderwidth=0)

    def _build(self):
        sidebar = tk.Frame(self.root, bg=NAVY, width=232)
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False)
        tk.Label(sidebar, text=self.t('网页摘录'), font=(FONT, 22, "bold"), bg=NAVY, fg="white").pack(anchor="w", padx=22, pady=(26, 3))
        tk.Label(sidebar, text=self.t('把网页，变成你的文稿'), bg=NAVY, fg="#9cb0cf", font=(FONT, 9)).pack(anchor="w", padx=23)
        button(sidebar, self.t('＋  新建文稿'), self.new_article, primary=True).pack(fill="x", padx=20, pady=(25, 20))
        tk.Label(sidebar, text=self.t('本地文稿'), bg=NAVY, fg="#9cb0cf", font=(FONT, 9)).pack(anchor="w", padx=22)
        self.search = tk.StringVar()
        search = tk.Entry(sidebar, textvariable=self.search, relief="flat", bg="#263853", fg="white", insertbackground="white")
        search.pack(fill="x", padx=20, pady=(10, 6), ipady=6)
        self.search.trace_add("write", lambda *_: self.refresh_list())
        tk.Label(sidebar, text=self.t('输入关键词筛选标题 / 正文'), bg=NAVY, fg="#869bbd", font=(FONT, 8)).pack(anchor="w", padx=22, pady=(0, 10))
        self.drafts = ttk.Treeview(sidebar, columns=("title",), show="tree", selectmode="browse", style="Draft.Treeview")
        self.drafts.column("#0", width=206, stretch=True)
        self.drafts.column("title", width=0, stretch=False)
        self.drafts.pack(fill="both", expand=True, padx=10)
        self.drafts.bind("<<TreeviewSelect>>", self.select_article)
        self.drafts.bind("<Button-3>", self.article_context_menu)
        self.draft_count = tk.StringVar(value=self.t('0 篇文稿'))
        tk.Label(sidebar, textvariable=self.draft_count, bg=NAVY, fg="#9cb0cf", font=(FONT, 9)).pack(anchor="w", padx=22, pady=(12, 6))
        button(sidebar, self.t('删除当前文稿'), self.delete_article).pack(fill="x", padx=20, pady=(0, 10))
        tk.Label(sidebar, text=self.t('本地保存 · 无需账号'), bg=NAVY, fg="#869bbd", font=(FONT, 9)).pack(anchor="w", padx=22, pady=(0, 20))

        workspace = tk.Frame(self.root, bg=BG)
        workspace.pack(side="left", fill="both", expand=True, padx=26, pady=24)
        top = tk.Frame(workspace, bg=BG)
        top.pack(fill="x")
        tk.Label(top, text=self.t('内容工作台'), bg=BG, fg=INK, font=(FONT, 20, "bold")).pack(side="left")
        button(top, '中文 / EN', self.toggle_language).pack(side='right', padx=(8, 0))
        button(top, self.t('批量替换'), self.open_replace, primary=True).pack(side="right")
        tk.Label(workspace, text=self.t('输入文章网址，提取标题与正文后直接编辑。'), bg=BG, fg=MUTED).pack(anchor="w", pady=(5, 17))
        fetch_bar = tk.Frame(workspace, bg="white", highlightbackground="#dce3ee", highlightthickness=1)
        fetch_bar.pack(fill="x")
        tk.Label(fetch_bar, text=self.t('网址'), bg="white", fg=MUTED).pack(side="left", padx=(14, 8))
        self.url_var = tk.StringVar()
        self.url_entry = tk.Entry(fetch_bar, textvariable=self.url_var, relief="flat", bg="white", fg=INK, insertbackground=BLUE)
        self.url_entry.pack(side="left", fill="x", expand=True, padx=4, ipady=13)
        self.url_entry.bind("<Return>", lambda event: self.start_fetch())
        self.fetch_button = button(fetch_bar, self.t('提取正文'), self.start_fetch, primary=True)
        self.fetch_button.pack(side="right", padx=6, pady=6)
        self.progress = ttk.Progressbar(workspace, mode="indeterminate")
        self.progress.pack(fill="x", pady=(5, 0))
        actions = tk.Frame(workspace, bg=BG)
        actions.pack(fill="x", pady=14)
        button(actions, self.t('保存'), self.save_now).pack(side="left", padx=(0, 7))
        button(actions, self.t('查看原文'), self.view_original).pack(side="left", padx=(0, 7))
        button(actions, self.t('撤销批量替换'), self.undo_batch).pack(side="left")
        button(actions, self.t('文本再生'), self.open_challenge).pack(side='left', padx=7)
        button(actions, self.t('导出文稿…'), self.export_article).pack(side="right")

        modes = tk.Frame(workspace, bg=BG)
        modes.pack(fill='x', pady=(0, 10))
        button(modes, self.t('模式 3 · 扭曲再生'), self.open_twisted).pack(side='left')
        button(modes, self.t('模式 4 · 重构再生'), self.open_reframe).pack(side='left', padx=8)
        self.cipher_button = button(modes, self.t('密码破译'), self.open_cipher)
        self.cipher_button.pack(side='left')

        paper = tk.Frame(workspace, bg="white", highlightbackground="#e1e6ee", highlightthickness=1)
        paper.pack(fill="both", expand=True)
        tk.Label(paper, text=self.t('标题'), bg="white", fg=MUTED, font=(FONT, 9)).pack(anchor="w", padx=25, pady=(18, 6))
        self.title_var = tk.StringVar()
        self.title_entry = tk.Entry(paper, textvariable=self.title_var, font=(FONT, 19, "bold"), bg="white", fg=INK,
                                   disabledbackground="white", disabledforeground=MUTED, relief="flat", insertbackground=BLUE)
        self.title_entry.pack(fill="x", padx=25, pady=(0, 10))
        self.title_var.trace_add("write", self.changed)
        self.source_var = tk.StringVar(value="")
        tk.Label(paper, textvariable=self.source_var, bg="white", fg=MUTED, font=(FONT, 8), anchor="w").pack(fill="x", padx=25, pady=(0, 14))
        tk.Frame(paper, bg="#edf0f5", height=1).pack(fill="x", padx=25)
        editor_frame = tk.Frame(paper, bg="white")
        editor_frame.pack(fill="both", expand=True, padx=(25, 10), pady=(16, 12))
        scrollbar = ttk.Scrollbar(editor_frame)
        scrollbar.pack(side="right", fill="y")
        self.editor = tk.Text(editor_frame, wrap="word", undo=True, maxundo=200, font=(FONT, 12), bg="white", fg="#2d3c50", bd=0,
                              highlightthickness=0, insertbackground=BLUE, selectbackground="#cfe0ff", padx=0, pady=3,
                              spacing1=4, spacing3=9, yscrollcommand=scrollbar.set)
        self.editor.pack(side="left", fill="both", expand=True)
        scrollbar.configure(command=self.editor.yview)
        self.editor.bind("<<Modified>>", self.body_changed)
        self.editor.bind("<Control-a>", self.select_all)
        self.empty_hint = tk.Label(editor_frame, text=self.t('从一个网址开始\n\n在上方粘贴文章链接，点击「提取正文」。\n\n也可以新建文稿，自由书写。'), bg="white", fg=MUTED, font=(FONT, 12), justify="center")
        footer = tk.Frame(workspace, bg=BG)
        footer.pack(fill="x", pady=(12, 0))
        self.status_var = tk.StringVar(value=self.t('就绪'))
        tk.Label(footer, textvariable=self.status_var, bg=BG, fg=MUTED, anchor="w", wraplength=620, justify="left").pack(side="left", fill="x", expand=True)
        self.length_var = tk.StringVar(value=self.t('0 字'))
        tk.Label(footer, textvariable=self.length_var, bg=BG, fg=MUTED).pack(side="right", padx=(8, 0))

    def _menus(self):
        menu = tk.Menu(self.root)
        file_menu = tk.Menu(menu, tearoff=False)
        file_menu.add_command(label=self.t('新建文稿    Ctrl+N'), command=self.new_article)
        file_menu.add_command(label=self.t('保存    Ctrl+S'), command=self.save_now)
        file_menu.add_command(label=self.t('导出文稿…'), command=self.export_article)
        file_menu.add_command(label=self.t('删除所有文章...'), command=self.delete_all_articles)
        file_menu.add_separator()
        file_menu.add_command(label=self.t('退出'), command=self.close)
        menu.add_cascade(label=self.t('文件'), menu=file_menu)
        edit = tk.Menu(menu, tearoff=False)
        edit.add_command(label=self.t('撤销正文编辑    Ctrl+Z'), command=lambda: self.text_action("<<Undo>>"))
        edit.add_command(label=self.t('重做正文编辑    Ctrl+Y'), command=lambda: self.text_action("<<Redo>>"))
        edit.add_separator()
        edit.add_command(label=self.t('批量替换    Ctrl+H'), command=self.open_replace)
        edit.add_command(label=self.t('撤销上次批量替换'), command=self.undo_batch)
        menu.add_cascade(label=self.t('编辑'), menu=edit)
        menu.add_command(label=self.t('使用说明'), command=self.help)
        self.root.configure(menu=menu)
        popup = tk.Menu(self.root, tearoff=False)
        for label, event in ((self.t('撤销'), "<<Undo>>"), (self.t('重做'), "<<Redo>>"), (self.t('剪切'), "<<Cut>>"), (self.t('复制'), "<<Copy>>"), (self.t('粘贴'), "<<Paste>>")):
            popup.add_command(label=label, command=lambda e=event: self.text_action(e))
        popup.add_separator()
        popup.add_command(label=self.t('全选'), command=self.select_all)
        self.editor.bind("<Button-3>", lambda event: popup.tk_popup(event.x_root, event.y_root))
        self.article_popup = tk.Menu(self.root, tearoff=False)
        self.article_popup.add_command(label=self.t('打开文章'))
        self.article_popup.add_command(label=self.t('删除这篇文章'))
        self.article_popup.add_separator()
        self.article_popup.add_command(label=self.t('删除所有文章...'), command=self.delete_all_articles)
        self.article_popup.bind(
            "<Unmap>", lambda event: self.root.after_idle(self.restore_article_selection))

    def article_context_menu(self, event):
        self.article_popup.unpost()
        article_id = self.drafts.identify_row(event.y)
        if not article_id:
            self.restore_article_selection()
            return "break"
        # TreeviewSelect is queued: keep this guard until the popup closes.
        self.context_article_id = article_id
        self.drafts.selection_set(article_id)
        self.drafts.focus(article_id)
        self.article_popup.entryconfigure(
            0, command=lambda target=article_id: self.open_article_by_id(target))
        self.article_popup.entryconfigure(
            1, command=lambda target=article_id: self.delete_article_by_id(target))
        try:
            self.article_popup.tk_popup(event.x_root, event.y_root)
        finally:
            self.article_popup.grab_release()
        return "break"

    def open_article_by_id(self, article_id):
        if self.current and self.current.id == article_id:
            return
        if not self.flush():
            return
        article = self.store.get(article_id)
        if article:
            self.show_article(article)

    def restore_article_selection(self):
        # A previous popup's Unmap callback must not dismiss a newer popup.
        if self.article_popup.winfo_ismapped():
            return
        self.drafts.selection_remove(*self.drafts.selection())
        if self.current and self.drafts.exists(self.current.id):
            self.drafts.selection_set(self.current.id)
            self.drafts.focus(self.current.id)
        self.context_article_id = None

    def text_action(self, event):
        if self.current:
            self.editor.focus_set()
            self.editor.event_generate(event)

    def select_all(self, event=None):
        self.editor.tag_add("sel", "1.0", "end-1c")
        return "break"

    def help(self):
        messagebox.showinfo(self.t('使用说明'), self.t('1. 输入文章详情页网址，点击「提取正文」。\n2. 标题和正文可直接编辑，修改会自动保存在本地。\n3.「批量替换」支持多条规则、当前/全部文稿及规则导入导出。\n4. 可导出 TXT、Markdown 或 JSON。\n\n采集原文会单独保留，可通过「查看原文」复制。\n普通网页通常可以提取；需登录、验证码或动态加载的网站可能无法直接抓取。\n\n数据目录：\n') + str(Path(self.store.db.execute("PRAGMA database_list").fetchone()[2]).parent), parent=self.root)

    def refresh_list(self):
        self.refreshing = True
        try:
            self.drafts.delete(*self.drafts.get_children())
            keyword = self.search.get().strip().casefold()
            articles = self.store.all()
            visible = 0
            for article in articles:
                if keyword and keyword not in (article.title + "\n" + article.body).casefold():
                    continue
                title = article.title.strip() or self.t('未命名文稿')
                label = title[:13] + ("…" if len(title) > 13 else "")
                label += "\n" + article.updated[:10] + "   ·   " + str(len(article.body)) + self.t(' 字')
                self.drafts.insert("", "end", iid=article.id, text=label)
                visible += 1
            if self.current and self.drafts.exists(self.current.id):
                self.drafts.selection_set(self.current.id)
            self.draft_count.set(self.t("{visible} / {total} 篇文稿", visible=visible, total=len(articles)))
        finally:
            self.refreshing = False

    def show_empty(self):
        self.loading = True
        self.current = None
        self.title_entry.configure(state="normal")
        self.title_var.set("")
        self.title_entry.configure(state="disabled")
        self.editor.configure(state="normal")
        self.editor.delete("1.0", "end")
        self.editor.edit_reset()
        self.editor.edit_modified(False)
        self.editor.configure(state="disabled")
        self.source_var.set(self.t('等待导入文章'))
        self.length_var.set(self.t('0 字'))
        self.empty_hint.place(relx=0.5, rely=0.4, anchor="center")
        self.loading = False

    def show_article(self, article):
        self.loading = True
        self.current = article
        self.empty_hint.place_forget()
        self.title_entry.configure(state="normal")
        self.title_var.set(article.title)
        self.editor.configure(state="normal")
        self.editor.delete("1.0", "end")
        self.editor.insert("1.0", article.body)
        self.editor.edit_reset()
        self.editor.edit_modified(False)
        source = article.url or self.t('本地文稿')
        self.source_var.set(source[:110] + ("…" if len(source) > 110 else ""))
        self.length_var.set(self.t("{count} 字", count=f"{len(article.body):,}"))
        self.loading = False
        self.refresh_list()

    def select_article(self, event=None):
        if self.refreshing or self.context_article_id is not None:
            return
        selected = self.drafts.selection()
        if selected and (not self.current or selected[0] != self.current.id):
            if not self.flush():
                self.refresh_list()
                return
            article = self.store.get(selected[0])
            if article:
                self.show_article(article)

    def new_article(self):
        if not self.flush():
            return
        article = Article(title=self.t('未命名文稿'), body="")
        try:
            self.store.save(article)
        except sqlite3.Error as exc:
            self.error(self.t('无法创建文稿'), exc)
            return
        self.search.set("")
        self.show_article(article)
        self.title_entry.focus_set()
        self.title_entry.selection_range(0, "end")
        self.status_var.set(self.t('新文稿已创建，编辑内容将自动保存。'))

    def changed(self, *_):
        if self.loading or not self.current:
            return
        if self.save_job:
            self.root.after_cancel(self.save_job)
        self.length_var.set(self.t("{count} 字", count=f"{len(self.editor.get('1.0', 'end-1c')):,}"))
        self.status_var.set(self.t('正在编辑…'))
        self.save_job = self.root.after(700, self.autosave)

    def body_changed(self, event=None):
        if self.editor.edit_modified():
            self.editor.edit_modified(False)
            self.changed()

    def autosave(self):
        self.save_job = None
        self.flush(quiet=True)

    def flush(self, quiet=False) -> bool:
        if self.save_job:
            self.root.after_cancel(self.save_job)
            self.save_job = None
        if not self.current:
            return True
        title = self.title_var.get()
        body = self.editor.get("1.0", "end-1c")
        if (title, body) == (self.current.title, self.current.body):
            return True
        updated = Article(**{**self.current.to_dict(), "title": title, "body": body})
        try:
            self.store.save(updated)
        except sqlite3.Error as exc:
            self.status_var.set(self.t('保存失败，请导出文稿备份后检查磁盘。'))
            if not quiet:
                self.error(self.t('保存失败，编辑内容仍保留在界面中'), exc)
            return False
        self.current = updated
        self.refresh_list()
        self.status_var.set(self.t('已自动保存到本地'))
        return True

    def save_now(self):
        if self.flush():
            self.status_var.set(self.t('已保存到本地') if self.current else self.t('请先提取网页或新建文稿。'))
        return "break"

    def start_fetch(self):
        if self.busy or not self.flush():
            return
        try:
            url = normalize_url(self.url_var.get())
        except ExtractionError as exc:
            self.error(self.t('网址有误'), exc)
            return
        self.busy = True
        self.fetch_button.configure(state="disabled", text=self.t('提取中…'))
        self.progress.start(12)
        self.status_var.set(self.t('正在下载网页并识别正文…'))

        def work():
            try:
                self.messages.put(("article", fetch_article(url)))
            except ExtractionError as exc:
                self.messages.put(("error", str(exc)))
            except Exception as exc:
                import logging
                logging.exception(self.t('网页提取失败'))
                self.messages.put(("error", self.t('处理网页时遇到错误：') + str(exc)))
        threading.Thread(target=work, daemon=True, name="article-fetch").start()

    def poll(self):
        if self.modal_action:
            self.root.after(100, self.poll)
            return
        try:
            while True:
                kind, value = self.messages.get_nowait()
                self.busy = False
                self.fetch_button.configure(state="normal", text=self.t('提取正文'))
                self.progress.stop()
                self.progress.configure(value=0)
                if kind == "error":
                    self.status_var.set(self.t('提取失败，已有文稿仍保留。'))
                    self.error(self.t('无法提取正文'), value)
                else:
                    saved_current = self.flush()
                    try:
                        self.store.save(value)
                    except sqlite3.Error as exc:
                        self.error(self.t('下载完成，但保存失败'), exc)
                        continue
                    if saved_current:
                        self.search.set("")
                        self.show_article(value)
                    else:
                        self.refresh_list()
                    self.status_var.set(self.t("提取完成 · {count} 字 · 已保存到本地", count=f"{len(value.body):,}"))
        except queue.Empty:
            pass
        self.root.after(100, self.poll)

    def delete_article(self):
        if self.current:
            self.delete_article_by_id(self.current.id)

    def delete_all_articles(self):
        if self.busy:
            messagebox.showinfo(self.t('删除所有文章...'),
                                self.t('请等待当前抓取完成后再删除全部文章。'), parent=self.root)
            return
        pending_save = self.save_job is not None
        if self.save_job:
            self.root.after_cancel(self.save_job)
            self.save_job = None
        deleted = False
        self.modal_action = True
        try:
            count = len(self.store.all())
            if not messagebox.askyesno(self.t('删除所有文章...'),
                    self.t('确定删除全部 {count} 篇文章吗？\n\n此操作无法撤销。', count=count),
                    parent=self.root, default='no', icon='warning'):
                return
            self.store.delete_all()
            deleted = True
        except sqlite3.Error as exc:
            self.error(self.t('删除失败'), exc)
            return
        finally:
            self.modal_action = False
            if pending_save and not deleted:
                self.save_job = self.root.after(700, self.autosave)
        self.show_empty()
        self.refresh_list()
        self.status_var.set(self.t('所有文章已删除'))

    def delete_article_by_id(self, article_id):
        if article_id is None:
            return
        try:
            article = self.store.get(article_id)
            if article is None:
                return
            deleting_current = self.current is not None and self.current.id == article_id
            title = self.title_var.get() if deleting_current else article.title
            # Modal dialogs run a nested event loop: suspend autosave until the
            # user has decided, so cancellation cannot save or delete data.
            pending_save = self.save_job is not None
            if self.save_job:
                self.root.after_cancel(self.save_job)
                self.save_job = None
            try:
                confirmed = messagebox.askyesno(
                    self.t('删除文稿'), self.t("确定删除《{title}》吗？\n\n该操作会删除这篇文稿及保存的原始采集内容，且无法撤销。", title=title.strip() or self.t("未命名文稿")),
                    parent=self.root)
            finally:
                if pending_save:
                    self.save_job = self.root.after(700, self.autosave)
            if not confirmed:
                return
            # Capture the displayed order before saving can reorder the list.
            visible = list(self.drafts.get_children())
            candidates = []
            if article_id in visible:
                index = visible.index(article_id)
                candidates = visible[index + 1:] + visible[:index][::-1]
            next_article = None
            if deleting_current:
                for candidate in candidates:
                    next_article = self.store.get(candidate)
                    if next_article:
                        break
            elif not self.flush():
                return
            had_save_job = self.save_job is not None
            if deleting_current and self.save_job:
                self.root.after_cancel(self.save_job)
                self.save_job = None
            try:
                self.store.delete(article_id)
            except sqlite3.Error:
                if deleting_current and had_save_job:
                    self.save_job = self.root.after(700, self.autosave)
                raise
        except sqlite3.Error as exc:
            self.error(self.t('删除失败'), exc)
            return
        if deleting_current:
            if next_article:
                self.show_article(next_article)
            else:
                self.show_empty()
        self.refresh_list()
        self.status_var.set(self.t('文稿已删除'))

    def view_original(self):
        if not self.current:
            return
        if not self.current.original_body:
            messagebox.showinfo(self.t('原始内容'), self.t('这是本地新建文稿，没有网页原文。'), parent=self.root)
            return
        window = tk.Toplevel(self.root)
        window.title(self.t('采集时的原始内容'))
        window.geometry("800x650")
        text = tk.Text(window, wrap="word", font=(FONT, 11), padx=20, pady=20)
        scroll = ttk.Scrollbar(window, command=text.yview)
        scroll.pack(side="right", fill="y")
        text.configure(yscrollcommand=scroll.set)
        text.pack(fill="both", expand=True)
        text.insert("1.0", self.current.original_title + "\n\n" + self.current.url + "\n\n" + self.current.original_body)
        text.configure(state="disabled")

    def export_article(self):
        if not self.current:
            messagebox.showinfo(self.t('导出'), self.t('请先提取网页或新建文稿。'), parent=self.root)
            return
        self.flush(quiet=True)
        # 保存异常时也能导出当前编辑器内容作备份。
        article = Article(**{**self.current.to_dict(), "title": self.title_var.get(), "body": self.editor.get("1.0", "end-1c")})
        safe_name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", article.title).strip(" .")[:70] or self.t('文稿')
        if re.fullmatch(r"(?i)(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\..*)?", safe_name):
            safe_name = self.t('文稿_') + safe_name
        path = filedialog.asksaveasfilename(parent=self.root, title=self.t('导出文稿'), initialfile=safe_name + ".txt", defaultextension=".txt",
                                          filetypes=[(self.t('纯文本'), "*.txt"), ("Markdown", "*.md"), (self.t('完整文稿 JSON'), "*.json")])
        if not path:
            return
        extension = Path(path).suffix.lower()
        if extension == ".json":
            content = json.dumps(article.to_dict(), ensure_ascii=False, indent=2)
        elif extension == ".md":
            content = "# " + article.title + "\n\n" + article.body + (self.t('\n\n来源：') + article.url if article.url else "") + "\n"
        else:
            content = article.title + "\n\n" + article.body + (self.t('\n\n来源：') + article.url if article.url else "") + "\n"
        try:
            Path(path).write_text(content, encoding="utf-8-sig" if extension == ".txt" else "utf-8")
            self.status_var.set(self.t('已导出：{name}', name=Path(path).name))
        except OSError as exc:
            self.error(self.t('导出失败'), exc)

    def open_replace(self):
        if not self.flush():
            return
        self.dialogs.append(ReplaceDialog(self))
        return "break"

    def undo_batch(self):
        if not self.flush():
            return
        try:
            count = self.store.undo_batch()
            if self.current:
                self.show_article(self.store.get(self.current.id))
            self.refresh_list()
            self.status_var.set(self.t("已撤销上次替换，恢复 {count} 篇文稿。", count=count) if count else self.t('没有可撤销的批量替换。'))
        except (ValueError, sqlite3.Error) as exc:
            self.error(self.t('无法撤销'), exc)

    def error(self, title, error):
        messagebox.showerror(title, translate(str(error), self.language), parent=self.root)

    def close(self):
        if not self.flush():
            return
        self.store.close()
        self.root.destroy()


class ReplaceDialog:
    def __init__(self, app: App):
        self.app = app
        self.t = app.t
        self.rules: list[Rule] = []
        self.changes = []
        self.window = tk.Toplevel(app.root)
        self.window.title(self.t('批量替换'))
        self.window.geometry(f"920x{max(620, min(710, app.root.winfo_screenheight() - 100))}")
        self.window.minsize(800, 620)
        self.window.configure(bg=BG)
        self.window.transient(app.root)
        self.window.grab_set()
        outer = tk.Frame(self.window, bg=BG)
        outer.pack(fill="both", expand=True, padx=22, pady=20)
        tk.Label(outer, text=self.t('批量替换'), font=(FONT, 20, "bold"), bg=BG, fg=INK).pack(anchor="w")
        tk.Label(outer, text=self.t('规则按列表顺序执行。查找按字面文本匹配，替换内容可留空（删除）。'), bg=BG, fg=MUTED).pack(anchor="w", pady=(5, 14))
        target_row = tk.Frame(outer, bg=BG)
        target_row.pack(fill="x", pady=(0, 12))
        tk.Label(target_row, text=self.t('处理文稿'), bg=BG).pack(side="left")
        self.target = tk.StringVar(value=self.t('当前文稿'))
        self.target_combo = ttk.Combobox(target_row, textvariable=self.target, values=(self.t('当前文稿'), self.t('全部文稿')), state="readonly", width=15)
        self.target_combo.pack(side="left", padx=10)
        self.target.trace_add("write", lambda *_: self.invalidate())
        button(target_row, self.t('导出规则…'), self.export_rules).pack(side="right")
        button(target_row, self.t('导入规则…'), self.import_rules).pack(side="right", padx=8)
        entry_row = tk.Frame(outer, bg=BG)
        entry_row.pack(fill="x")
        entry_row.columnconfigure(0, weight=1)
        entry_row.columnconfigure(1, weight=1)
        tk.Label(entry_row, text=self.t('查找内容'), bg=BG, fg=INK).grid(row=0, column=0, sticky="w")
        tk.Label(entry_row, text=self.t('替换为'), bg=BG, fg=INK).grid(row=0, column=1, sticky="w", padx=(10, 0))
        self.find = tk.StringVar()
        self.replace = tk.StringVar()
        ttk.Entry(entry_row, textvariable=self.find).grid(row=1, column=0, sticky="ew", ipady=5, pady=6)
        ttk.Entry(entry_row, textvariable=self.replace).grid(row=1, column=1, sticky="ew", ipady=5, padx=(10, 0), pady=6)
        rule_options = tk.Frame(outer, bg=BG)
        rule_options.pack(fill="x", pady=(4, 12))
        self.scope = tk.StringVar(value=self.t('标题和正文'))
        self.scope_combo = ttk.Combobox(rule_options, textvariable=self.scope, values=(self.t('标题和正文'), self.t('仅标题'), self.t('仅正文')), state="readonly", width=16)
        self.scope_combo.pack(side="left")
        self.case = tk.BooleanVar(value=True)
        tk.Checkbutton(rule_options, text=self.t('区分英文大小写'), variable=self.case, bg=BG, activebackground=BG).pack(side="left", padx=8)
        button(rule_options, self.t('添加规则 ↓'), self.add_rule, primary=True).pack(side="right")
        self.table = ttk.Treeview(outer, columns=("find", "replace", "scope", "case"), show="headings", height=5, selectmode="browse")
        for key, label, width in (("find", self.t('查找'), 240), ("replace", self.t('替换为'), 240), ("scope", self.t('范围'), 110), ("case", self.t('大小写'), 90)):
            self.table.heading(key, text=label)
            self.table.column(key, width=width, minwidth=70)
        self.table.pack(fill="x")
        row = tk.Frame(outer, bg=BG)
        row.pack(fill="x", pady=8)
        button(row, self.t('删除选中规则'), self.remove_rule).pack(side="left")
        button(row, self.t('上移'), lambda: self.move_rule(-1)).pack(side="left", padx=8)
        button(row, self.t('下移'), lambda: self.move_rule(1)).pack(side="left")
        self.summary = tk.StringVar(value=self.t('添加规则后点击预览，再应用修改。'))
        tk.Label(outer, textvariable=self.summary, bg=BG, fg=INK, anchor="w").pack(fill="x", pady=(6, 8))
        preview_frame = tk.Frame(outer, bg="white")
        preview_frame.pack(fill="both", expand=True)
        self.preview_text = tk.Text(preview_frame, wrap="word", font=(FONT, 10), height=6, bd=0, padx=12, pady=10)
        scroll = ttk.Scrollbar(preview_frame, command=self.preview_text.yview)
        scroll.pack(side="right", fill="y")
        self.preview_text.configure(yscrollcommand=scroll.set, state="disabled")
        self.preview_text.pack(fill="both", expand=True)
        self.preview_text.tag_configure("removed", foreground="#b42318")
        self.preview_text.tag_configure("added", foreground="#087443")
        bottom = tk.Frame(outer, bg=BG)
        bottom.pack(fill="x", pady=(14, 0))
        tk.Label(bottom, text=self.t('原始采集内容保留，可撤销最近一次批量替换。'), bg=BG, fg=MUTED, font=(FONT, 9)).pack(side="left")
        self.apply_button = button(bottom, self.t('应用替换'), self.apply, primary=True, state="disabled")
        self.apply_button.pack(side="right")
        button(bottom, self.t('预览修改'), self.make_preview).pack(side="right", padx=10)

    def refresh_language(self, old):
        target = translate(self.target.get(), self.app.language, old)
        scope = translate(self.scope.get(), self.app.language, old)
        self.target_combo.configure(values=(self.t('当前文稿'), self.t('全部文稿')))
        self.scope_combo.configure(values=(self.t('标题和正文'), self.t('仅标题'), self.t('仅正文')))
        self.target.set(target)
        self.scope.set(scope)
        self.render_rules()

    def invalidate(self):
        self.changes = []
        self.apply_button.configure(state="disabled")
        self.summary.set(self.t('规则或范围已改变，请重新预览。'))
        self.preview_text.configure(state="normal")
        self.preview_text.delete("1.0", "end")
        self.preview_text.configure(state="disabled")

    def render_rules(self, selected=None):
        self.table.delete(*self.table.get_children())
        names = {"both": self.t('标题和正文'), "title": self.t('仅标题'), "body": self.t('仅正文')}
        for i, rule in enumerate(self.rules):
            self.table.insert("", "end", iid=str(i), values=(rule.find, rule.replacement or self.t('（删除）'), names[rule.scope], self.t('区分') if rule.case_sensitive else self.t('不区分')))
        if selected is not None and self.table.exists(str(selected)):
            self.table.selection_set(str(selected))
        self.invalidate()

    def add_rule(self):
        try:
            rule = Rule(self.find.get(), self.replace.get(), {self.t('标题和正文'): "both", self.t('仅标题'): "title", self.t('仅正文'): "body"}[self.scope.get()], self.case.get())
        except ValueError as exc:
            messagebox.showerror(self.t('规则有误'), translate(str(exc), self.app.language), parent=self.window)
            return
        self.rules.append(rule)
        self.render_rules(len(self.rules) - 1)
        self.find.set("")
        self.replace.set("")

    def remove_rule(self):
        selected = self.table.selection()
        if selected:
            self.rules.pop(int(selected[0]))
            self.render_rules()

    def move_rule(self, step):
        selected = self.table.selection()
        if not selected:
            return
        old = int(selected[0])
        new = old + step
        if 0 <= new < len(self.rules):
            self.rules[old], self.rules[new] = self.rules[new], self.rules[old]
            self.render_rules(new)

    def import_rules(self):
        path = filedialog.askopenfilename(parent=self.window, title=self.t('导入替换规则'), filetypes=[(self.t('替换规则 JSON'), "*.json")])
        if not path:
            return
        try:
            data = json.loads(Path(path).read_text(encoding="utf-8-sig"))
            if not isinstance(data, list) or len(data) > 500:
                raise ValueError(self.t('规则文件必须是 JSON 数组，最多 500 条规则。'))
            rules = [Rule(**item) for item in data]
        except (OSError, ValueError, TypeError) as exc:
            messagebox.showerror(self.t('导入失败'), translate(str(exc), self.app.language), parent=self.window)
            return
        self.rules.extend(rules)
        self.render_rules()
        self.summary.set(self.t("已追加 {count} 条规则，请预览修改。", count=len(rules)))

    def export_rules(self):
        path = filedialog.asksaveasfilename(parent=self.window, title=self.t('导出替换规则'), initialfile=self.t('替换规则.json'), defaultextension=".json", filetypes=[(self.t('替换规则 JSON'), "*.json")])
        if path:
            try:
                Path(path).write_text(json.dumps([asdict(rule) for rule in self.rules], ensure_ascii=False, indent=2), encoding="utf-8")
            except OSError as exc:
                messagebox.showerror(self.t('导出失败'), translate(str(exc), self.app.language), parent=self.window)

    def make_preview(self):
        if not self.rules:
            messagebox.showinfo(self.t('预览'), self.t('请先添加至少一条规则。'), parent=self.window)
            return
        articles = self.app.store.all() if self.target.get() == self.t('全部文稿') else ([self.app.store.get(self.app.current.id)] if self.app.current else [])
        self.changes = preview(articles, self.rules)
        count = sum(change.matches for change in self.changes)
        self.summary.set(self.t("检查 {total} 篇文稿 · 将修改 {changed} 篇 · 共匹配 {count} 处（规则顺序执行）", total=len(articles), changed=len(self.changes), count=count))
        self.preview_text.configure(state="normal")
        self.preview_text.delete("1.0", "end")
        import difflib
        for change in self.changes[:50]:
            self.preview_text.insert("end", f"【{change.before.title or self.t('未命名文稿')}】\n")
            before = (change.before.title + "\n\n" + change.before.body).splitlines()
            after = (change.after.title + "\n\n" + change.after.body).splitlines()
            for index, line in enumerate(difflib.unified_diff(before, after, fromfile=self.t('替换前'), tofile=self.t('替换后'), lineterm="", n=1)):
                if index >= 180:
                    self.preview_text.insert("end", self.t('… 此篇预览已截断，应用时处理全文。\n'))
                    break
                self.preview_text.insert("end", line[:2000] + ("…" if len(line) > 2000 else "") + "\n", "added" if line.startswith("+") else "removed" if line.startswith("-") else "")
            self.preview_text.insert("end", "\n")
        if len(self.changes) > 50:
            self.preview_text.insert("end", self.t('仅展示前 50 篇的修改，应用时会处理所有命中文稿。'))
        if not self.changes:
            self.preview_text.insert("end", self.t('没有需要修改的内容。'))
        self.preview_text.configure(state="disabled")
        self.apply_button.configure(state="normal" if self.changes else "disabled")

    def apply(self):
        try:
            self.app.store.apply(self.changes)
        except (ValueError, sqlite3.Error) as exc:
            messagebox.showerror(self.t('替换失败'), translate(str(exc), self.app.language), parent=self.window)
            return
        count = len(self.changes)
        if self.app.current:
            self.app.show_article(self.app.store.get(self.app.current.id))
        self.app.refresh_list()
        self.app.status_var.set(self.t("已替换 {count} 篇文稿，可点击「撤销批量替换」恢复。", count=count))
        self.window.destroy()

from pathlib import Path
p = Path('clipdesk/ui.py')
s = p.read_text(encoding='utf-8')
s = s.replace('        self.save_job = None\n', '        self.save_job = None\n        self.context_article_id = None\n', 1)
s = s.replace('        self.drafts.bind("<<TreeviewSelect>>", self.select_article)', '        self.drafts.bind("<<TreeviewSelect>>", self.select_article)\n        self.drafts.bind("<Button-3>", self.article_context_menu)')
pos = '    def text_action(self, event):'
addition = '''    def article_context_menu(self, event):
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
            0, command=lambda target=article_id: self.delete_article(target))
        try:
            self.article_popup.tk_popup(event.x_root, event.y_root)
        finally:
            self.article_popup.grab_release()
        return "break"

    def restore_article_selection(self):
        # A previous popup's Unmap callback must not dismiss a newer popup.
        if self.article_popup.winfo_ismapped():
            return
        self.drafts.selection_remove(*self.drafts.selection())
        if self.current and self.drafts.exists(self.current.id):
            self.drafts.selection_set(self.current.id)
            self.drafts.focus(self.current.id)
        self.context_article_id = None

'''
s = s.replace(pos, addition + pos)
s = s.replace('    def text_action(self, event):', '    def text_action(self, event):', 1)
s = s.replace('        self.editor.bind("<Button-3>", lambda event: popup.tk_popup(event.x_root, event.y_root))', '''        self.editor.bind("<Button-3>", lambda event: popup.tk_popup(event.x_root, event.y_root))
        self.article_popup = tk.Menu(self.root, tearoff=False)
        self.article_popup.add_command(label="删除这篇文章")
        self.article_popup.bind(
            "<Unmap>", lambda event: self.root.after_idle(self.restore_article_selection))''')
s = s.replace('        if self.refreshing:\n', '        if self.refreshing or self.context_article_id is not None:\n')
start = s.index('    def delete_article(self):')
end = s.index('    def view_original(self):', start)
s = s[:start] + '''    def delete_article(self, article_id=None):
        article_id = article_id if article_id is not None else (self.current.id if self.current else None)
        if article_id is None:
            return
        try:
            article = self.store.get(article_id)
            if article is None:
                return
            deleting_current = self.current is not None and self.current.id == article_id
            title = self.title_var.get() if deleting_current else article.title
            if not messagebox.askyesno(
                    "删除文稿", f"确定删除《{title.strip() or '未命名文稿'}》吗？\\n\\n"
                    "该操作会删除这篇文稿及保存的原始采集内容，且无法撤销。",
                    parent=self.root):
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
            self.error("删除失败", exc)
            return
        if deleting_current:
            if next_article:
                self.show_article(next_article)
            else:
                self.show_empty()
        self.refresh_list()
        self.status_var.set("文稿已删除")

''' + s[end:]
p.write_text(s, encoding='utf-8')
for name in ('README.md', '使用说明.txt'):
    p = Path(name)
    p.write_text(p.read_text(encoding='utf-8') + '\n\n在左侧文稿列表中右键某篇文章，可以直接删除该文章。删除前会显示确认提示。\n删除其他文稿时会保存并保留当前编辑内容；删除当前文稿时优先显示列表中的下一篇，其次上一篇。\n搜索状态下只在可见结果中选择；没有剩余结果时显示空白编辑状态，可清除搜索查看其他文稿。\n删除会移除文稿及原始采集内容，无法撤销。\n', encoding='utf-8')

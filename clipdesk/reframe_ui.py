"""Mode 4 controls operate only on source fragments in a ReframeSession."""
import tkinter as tk
from tkinter import ttk, messagebox

from .reframe import ReframeSession
from .i18n import translate
from .ui import BG, INK, MUTED, FONT, button

METHOD_LABELS = {'pure': '纯重排', 'editorial': '编辑重构'}
OUTCOME_LABELS = {'close': '接近原文', 'context': '上下文偏移', 'selective': '选择性重构', 'strong': '强重构'}


class ReframeDialog:
    def __init__(self, app, source):
        self.app, self.t, self.source = app, app.t, source
        self.session = ReframeSession(source)
        self.window = tk.Toplevel(app.root)
        self.window.title(self.t('模式 4 · 重构再生'))
        self.window.geometry('960x640')
        self.window.minsize(820, 580)
        self.window.configure(bg=BG)
        self.window.transient(app.root)
        self.window.grab_set()
        outer = tk.Frame(self.window, bg=BG)
        outer.pack(fill='both', expand=True, padx=20, pady=16)
        header = tk.Frame(outer, bg=BG)
        header.pack(fill='x')
        self.heading = tk.StringVar()
        tk.Label(header, textvariable=self.heading, font=(FONT, 18, 'bold'), bg=BG, fg=INK).pack(side='left')
        button(header, '中文 / EN', app.toggle_language).pack(side='right')
        self.content = tk.Frame(outer, bg=BG)
        self.content.pack(fill='both', expand=True)
        style = ttk.Style(self.window)
        style.configure('Reframe.Treeview', rowheight=34, font=(FONT, 10), background='white', fieldbackground='white')
        self.show_choice()

    def clear(self):
        for child in self.content.winfo_children():
            child.destroy()

    def label(self, parent, key, **kwargs):
        label = tk.Label(parent, text=self.t(key), bg=BG, fg=MUTED, wraplength=870, justify='left', **kwargs)
        label.pack(anchor='w', pady=5)
        return label

    def text_panel(self, parent, text, height=3):
        frame = tk.Frame(parent, bg='white')
        frame.pack(fill='both', expand=True)
        box = tk.Text(frame, height=height, width=25, wrap='word', font=(FONT, 10), padx=9, pady=7)
        scrollbar = ttk.Scrollbar(frame, command=box.yview)
        scrollbar.pack(side='right', fill='y')
        box.configure(yscrollcommand=scrollbar.set)
        box.pack(fill='both', expand=True)
        self.set_text(box, text)
        return box

    @staticmethod
    def set_text(box, text):
        box.configure(state='normal')
        box.delete('1.0', 'end')
        box.insert('1.0', text)
        box.configure(state='disabled')

    def show_choice(self):
        self.clear()
        self.label(self.content, '信息不需要改变，也可能因为重新排列而长成不同的故事。')
        self.label(self.content, '你想怎样重新讲述这个故事？', font=(FONT, 13, 'bold'))
        choices = tk.Frame(self.content, bg=BG)
        choices.pack(fill='both', expand=True, pady=18)
        for method, description in (('pure', '只能改变碎片顺序，必须保留所有信息。'),
                                    ('editorial', '可以重新排列，并删除有限的信息碎片。')):
            card = tk.Frame(choices, bg=BG)
            card.pack(fill='x', pady=12)
            choice = button(card, self.t(METHOD_LABELS[method]), lambda key=method: self.start(key), primary=True)
            choice.pack(anchor='w')
            choice.configure(state='normal' if self.session.sections else 'disabled')
            self.label(card, description)
        if not self.session.sections:
            self.label(self.content, '正文太短或没有适合重构的片段。')
        self.label(self.content, '同样的信息，不同的排列，可以产生不同的故事。')
        button(self.content, self.t('返回编辑器'), self.window.destroy).pack(anchor='e', pady=8)
        self.refresh_language(None)

    def start(self, method):
        self.session.start(method)
        self.show_round()

    def make_tree(self, parent, with_source=False):
        tree = ttk.Treeview(parent, columns=('source',) if with_source else (),
                            show='tree headings', selectmode='browse', height=7, style='Reframe.Treeview')
        tree.heading('#0', text=self.t('信息碎片'))
        tree.column('#0', width=360 if with_source else 160, stretch=True)
        if with_source:
            tree.heading('source', text=self.t('来源'))
            tree.column('source', width=140, stretch=False)
        scroll = ttk.Scrollbar(parent, command=tree.yview)
        scroll.pack(side='right', fill='y')
        tree.configure(yscrollcommand=scroll.set)
        tree.pack(fill='both', expand=True)
        tree.bind('<<TreeviewSelect>>', lambda event: self.update_controls())
        return tree

    def show_round(self):
        self.clear()
        self.round_label, self.goal_label, self.rules_label = tk.StringVar(), tk.StringVar(), tk.StringVar()
        tk.Label(self.content, textvariable=self.round_label, bg=BG, fg=INK, font=(FONT, 11, 'bold')).pack(anchor='w', pady=(8, 2))
        tk.Label(self.content, textvariable=self.goal_label, bg=BG, fg=INK, wraplength=870, justify='left').pack(anchor='w')
        tk.Label(self.content, textvariable=self.rules_label, bg=BG, fg=MUTED, wraplength=870, justify='left').pack(anchor='w', pady=4)
        panels = tk.Frame(self.content, bg=BG)
        panels.pack(fill='x', pady=5)
        for column in range(2):
            panels.columnconfigure(column, weight=1, uniform='section')
        left, right = tk.Frame(panels, bg=BG), tk.Frame(panels, bg=BG)
        left.grid(row=0, column=0, sticky='nsew', padx=(0, 6))
        right.grid(row=0, column=1, sticky='nsew', padx=(6, 0))
        self.label(left, '本轮原文')
        self.label(right, '当前重构')
        self.original_section_box = self.text_panel(left, self.session.current_round.original_section)
        self.preview_box = self.text_panel(right, self.session.preview())
        # Reserve the footer before allocating the expanding list, so Lock and
        # Next remain reachable at the default/minimum size and Windows DPI.
        footer = tk.Frame(self.content, bg=BG)
        footer.pack(side='bottom', fill='x')
        tables = tk.Frame(self.content, bg=BG)
        tables.pack(fill='both', expand=True, pady=8)
        kept = tk.Frame(tables, bg=BG)
        kept.pack(side='left', fill='both', expand=True)
        self.fragments = self.make_tree(kept, True)
        removed = tk.Frame(tables, bg=BG, width=205)
        if self.session.method == 'editorial':
            removed.pack(side='right', fill='both', padx=(12, 0))
            removed.pack_propagate(False)
        self.removed_fragments = self.make_tree(removed)
        self.removed_fragments.heading('#0', text=self.t('已移除'))
        controls = tk.Frame(footer, bg=BG)
        controls.pack(fill='x')
        self.up_button = button(controls, self.t('上移'), lambda: self.move(-1))
        self.up_button.pack(side='left')
        self.down_button = button(controls, self.t('下移'), lambda: self.move(1))
        self.down_button.pack(side='left', padx=6)
        self.remove_button = button(controls, self.t('删除'), self.remove)
        self.remove_button.pack(side='left')
        self.restore_button = button(controls, self.t('fragment_restore'), self.restore)
        self.restore_button.pack(side='left', padx=6)
        self.label(footer, '选择碎片后上移或下移。锁定重构保存本轮；目标用于思考，不做语义评分。')
        actions = tk.Frame(footer, bg=BG)
        actions.pack(fill='x', pady=(3, 0))
        self.lock_button = button(actions, self.t('锁定重构'), self.lock, primary=True)
        self.lock_button.pack(side='left')
        self.next_button = button(actions, self.t('下一轮'), self.next_round, state='disabled')
        self.next_button.pack(side='left', padx=8)
        button(actions, self.t('返回编辑器'), self.window.destroy).pack(side='right')
        self.refresh_fragments()
        self.refresh_language(None)

    @staticmethod
    def selected(tree):
        selection = tree.selection()
        return selection[0] if selection else None

    def refresh_fragments(self, selected=None, removed_selected=None):
        current = self.session.current_round
        by_id = {fragment.id: fragment for fragment in current.pieces.fragments}
        for tree in (self.fragments, self.removed_fragments):
            tree.delete(*tree.get_children())
        for key in current.order:
            fragment = by_id[key]
            self.fragments.insert('', 'end', iid=key, text=fragment.text,
                                  values=(self.t('来自原文第 {number} 段', number=fragment.paragraph),))
        for key in current.removed:
            self.removed_fragments.insert('', 'end', iid=key, text=by_id[key].text)
        for tree, key, fallback in ((self.fragments, selected, current.order),
                                    (self.removed_fragments, removed_selected, current.removed)):
            if key in fallback or fallback:
                tree.selection_set(key if key in fallback else fallback[0])
                tree.see(tree.selection()[0])
        self.set_text(self.preview_box, self.session.preview())
        self.refresh_language(None)
        self.update_controls()

    def update_controls(self):
        if not hasattr(self, 'up_button') or not self.up_button.winfo_exists():
            return
        current = self.session.current_round
        selected = self.selected(self.fragments)
        index = current.order.index(selected) if selected in current.order else -1
        editable = not current.locked
        self.up_button.configure(state='normal' if editable and index > 0 else 'disabled')
        self.down_button.configure(state='normal' if editable and 0 <= index < len(current.order) - 1 else 'disabled')
        can_remove = (editable and selected in current.order and self.session.method == 'editorial'
                      and len(current.removed) < self.session.removal_limit and len(current.order) > self.session.minimum_kept)
        self.remove_button.configure(state='normal' if can_remove else 'disabled')
        self.restore_button.configure(state='normal' if editable and self.selected(self.removed_fragments) in current.removed else 'disabled')

    def operate(self, method, key, *args):
        if not key:
            return
        try:
            method(key, *args)
        except ValueError as exc:
            messagebox.showinfo(self.t('无法重构'), translate(str(exc), self.app.language), parent=self.window)
            return
        self.refresh_fragments(selected=key, removed_selected=key)

    def move(self, step):
        self.operate(self.session.move, self.selected(self.fragments), step)

    def remove(self):
        self.operate(self.session.remove, self.selected(self.fragments))

    def restore(self):
        self.operate(self.session.restore, self.selected(self.removed_fragments))

    def lock(self):
        try:
            self.session.lock()
        except ValueError as exc:
            messagebox.showerror(self.t('无法重构'), translate(str(exc), self.app.language), parent=self.window)
            return
        if self.session.finished:
            self.show_result()
        else:
            self.lock_button.configure(state='disabled')
            self.next_button.configure(state='normal')
            self.update_controls()
            self.refresh_language(None)

    def next_round(self):
        self.session.next_round()
        self.show_round()

    def show_result(self):
        self.clear()
        self.stats = tk.StringVar()
        tk.Label(self.content, textvariable=self.stats, bg=BG, fg=INK, wraplength=870,
                 justify='left').pack(anchor='w', pady=12)
        self.label(self.content, '同样的信息，不同的排列，可以产生不同的故事。')
        panels = tk.Frame(self.content, bg=BG)
        panels.pack(fill='both', expand=True)
        panels.columnconfigure((0, 1), weight=1, uniform='result')
        panels.rowconfigure(0, weight=1)
        left, right = tk.Frame(panels, bg=BG), tk.Frame(panels, bg=BG)
        left.grid(row=0, column=0, sticky='nsew', padx=(0, 6))
        right.grid(row=0, column=1, sticky='nsew', padx=(6, 0))
        self.label(left, '原始故事')
        self.label(right, '重构故事')
        self.original_box = self.text_panel(left, self.session.original_text)
        self.final_box = self.text_panel(right, self.session.working_copy)
        actions = tk.Frame(self.content, bg=BG)
        actions.pack(fill='x', pady=(12, 0))
        button(actions, self.t('重新重构'), self.restart, primary=True).pack(side='left')
        button(actions, self.t('查看历史'), self.view_history).pack(side='left', padx=8)
        button(actions, self.t('返回编辑器'), self.window.destroy).pack(side='right')
        self.refresh_language(None)

    def restart(self):
        self.session = ReframeSession(self.source)
        self.show_choice()

    def history_details(self, record):
        removed = ' | '.join(fragment.text for fragment in record.removed_fragments) or self.t('无')
        return '\n'.join((self.t('本轮目标：{goal}', goal=self.t(record.goal)),
            self.t('移动碎片数：{count}', count=record.moved), self.t('已移除：{fragments}', fragments=removed)))

    def view_history(self):
        self.history_window = tk.Toplevel(self.window)
        self.history_window.title(self.t('查看历史'))
        self.history_window.geometry('820x560')
        self.history_window.transient(self.window)
        self.history_window.grab_set()
        self.history_tabs = ttk.Notebook(self.history_window)
        self.history_tabs.pack(fill='both', expand=True, padx=10, pady=10)
        self.history_variables = []
        for record in self.session.history:
            frame = tk.Frame(self.history_tabs, bg=BG)
            self.history_tabs.add(frame, text=self.t('第 {number} 轮', number=record.number))
            details = tk.StringVar(value=self.history_details(record))
            self.history_variables.append(details)
            tk.Label(frame, textvariable=details, bg=BG, fg=INK, wraplength=760, justify='left').pack(anchor='w', padx=10, pady=10)
            self.label(frame, '本轮原文')
            self.text_panel(frame, record.original_section)
            self.label(frame, '重构故事')
            self.text_panel(frame, record.reframed_section)
        self.history_window.protocol('WM_DELETE_WINDOW', self.close_history)

    def close_history(self):
        self.history_window.destroy()
        self.window.grab_set()

    def refresh_language(self, old):
        self.window.title(self.t('模式 4 · 重构再生'))
        self.heading.set(self.t('重构完成' if self.session.finished else '模式 4 · 重构再生'))
        if self.session.finished:
            self.stats.set('\n'.join((self.t('玩法：{method}', method=self.t(METHOD_LABELS[self.session.method])),
                self.t('处理轮数：{count}', count=len(self.session.history)) + '    ' + self.t('处理段落数：{count}', count=self.session.sections_reframed),
                self.t('移动碎片数：{count}', count=self.session.fragments_moved) + '    ' + self.t('删除碎片数：{count}', count=self.session.fragments_removed),
                self.t('重构结果：{outcome}', outcome=self.t(OUTCOME_LABELS[self.session.outcome])))))
        elif self.session.current_round:
            current = self.session.current_round
            self.restore_button.configure(text=self.t('fragment_restore'))
            self.fragments.heading('#0', text=self.t('信息碎片'))
            self.removed_fragments.heading('#0', text=self.t('已移除'))
            self.round_label.set(self.t('第 {number} / 3 轮', number=current.number) + ' · ' + self.t(METHOD_LABELS[self.session.method]))
            self.goal_label.set(self.t('本轮目标：{goal}', goal=self.t(current.goal)))
            if current.locked:
                self.rules_label.set(self.t('本轮已锁定，点击下一轮继续。'))
            elif self.session.method == 'pure':
                self.rules_label.set(self.t('纯重排：保留全部碎片，只改变顺序。'))
            else:
                self.rules_label.set(self.t('本轮最多删除 {limit} 个，已移除 {removed} 个；至少保留 {minimum} 个。锁定前可恢复。',
                    limit=self.session.removal_limit, removed=len(current.removed), minimum=self.session.minimum_kept))
            for fragment in current.pieces.fragments:
                if self.fragments.exists(fragment.id):
                    self.fragments.item(fragment.id, values=(self.t('来自原文第 {number} 段', number=fragment.paragraph),))
        if hasattr(self, 'history_window') and self.history_window.winfo_exists():
            for index, record in enumerate(self.session.history):
                self.history_tabs.tab(index, text=self.t('第 {number} 轮', number=record.number))
                self.history_variables[index].set(self.history_details(record))

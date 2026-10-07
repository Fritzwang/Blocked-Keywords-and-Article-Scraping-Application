"""A separate, temporary puzzle window; the editor remains untouched."""
import tkinter as tk
from tkinter import messagebox, ttk

from .challenge import Challenge
from .ui import BG, INK, MUTED, FONT, button


class ChallengeDialog:
    def __init__(self, app, source):
        self.app = app
        self.t = app.t
        self.source = source
        self.challenge = None
        self.window = tk.Toplevel(app.root)
        self.window.title(self.t('文本再生'))
        self.window.geometry('920x640')
        self.window.minsize(760, 580)
        self.window.configure(bg=BG)
        self.window.transient(app.root)
        self.window.grab_set()
        outer = tk.Frame(self.window, bg=BG)
        outer.pack(fill='both', expand=True, padx=20, pady=16)
        header = tk.Frame(outer, bg=BG)
        header.pack(fill='x')
        tk.Label(header, text=self.t('文本再生'), bg=BG, fg=INK,
                 font=(FONT, 20, 'bold')).pack(side='left')
        button(header, '中文 / EN', app.toggle_language).pack(side='right')
        tk.Label(outer, text=self.t('填写缺失词，再点击测试。同一词的所有位置一起恢复。遮罩统一为 *****。'),
                 bg=BG, fg=MUTED, wraplength=850, justify='left').pack(anchor='w', pady=10)
        body = tk.Frame(outer)
        body.pack(fill='both', expand=True)
        self.text = tk.Text(body, wrap='word', font=(FONT, 12), padx=12, pady=12,
                            height=10, state='disabled')
        scroll = ttk.Scrollbar(body, command=self.text.yview)
        self.text.configure(yscrollcommand=scroll.set)
        scroll.pack(side='right', fill='y')
        self.text.pack(fill='both', expand=True)
        self.inputs_frame = tk.Frame(outer, bg=BG)
        self.inputs_frame.pack(fill='x', pady=12)
        self.summary = tk.StringVar()
        tk.Label(outer, textvariable=self.summary, bg=BG, fg=INK,
                 wraplength=850, justify='left').pack(anchor='w')
        actions = tk.Frame(outer, bg=BG)
        actions.pack(fill='x', pady=(12, 0))
        self.test_button = button(actions, self.t('测试'), self.test, primary=True)
        self.test_button.pack(side='left')
        self.reveal_button = button(actions, self.t('揭露答案'), self.reveal)
        self.reveal_button.pack(side='left', padx=8)
        button(actions, self.t('重新生成'), self.new_challenge).pack(side='left')
        button(actions, self.t('返回编辑器'), self.window.destroy).pack(side='right')
        self.new_challenge()

    def new_challenge(self):
        previous = self.challenge.targets if self.challenge else ()
        self.challenge = Challenge.create(self.source, previous=previous)
        for child in self.inputs_frame.winfo_children():
            child.destroy()
        self.answers, self.entries, self.result_vars, self.answer_vars = [], [], [], []
        for index, target in enumerate(self.challenge.targets):
            tk.Label(self.inputs_frame, text=self.t('缺失词 {number}', number=index + 1),
                     bg=BG, fg=INK).grid(row=index, column=0, sticky='w', pady=3)
            answer = tk.StringVar()
            entry = ttk.Entry(self.inputs_frame, textvariable=answer, width=23)
            entry.grid(row=index, column=1, padx=12, pady=3)
            entry.bind('<Return>', lambda event: self.test())
            result = tk.StringVar()
            tk.Label(self.inputs_frame, textvariable=result, bg=BG, fg=INK,
                     width=18, anchor='w').grid(row=index, column=2, sticky='w')
            revealed = tk.StringVar()
            tk.Label(self.inputs_frame, textvariable=revealed, bg=BG, fg=MUTED,
                     anchor='w').grid(row=index, column=3, sticky='w')
            self.answers.append(answer)
            self.entries.append(entry)
            self.result_vars.append(result)
            self.answer_vars.append(revealed)
        self.test_button.configure(state='normal' if self.answers else 'disabled')
        self.reveal_button.configure(state='normal' if self.answers else 'disabled')
        self.render()

    def test(self):
        self.challenge.test([answer.get() for answer in self.answers])
        self.render()

    def reveal(self):
        if self.challenge.revealed:
            return
        if messagebox.askyesno(self.t('揭露答案'), self.t('确定要揭露所有剩余答案吗？'),
                               parent=self.window, default='no'):
            self.challenge.reveal()
            for entry in self.entries:
                entry.configure(state='disabled')
            self.test_button.configure(state='disabled')
            self.reveal_button.configure(state='disabled')
            self.render()

    def render(self):
        view = self.text.yview()
        self.text.configure(state='normal')
        self.text.delete('1.0', 'end')
        self.text.insert('1.0', self.challenge.render())
        self.text.configure(state='disabled')
        if view:
            self.text.yview_moveto(view[0])
        labels = {'pending': '', 'correct': '✅ 正确', 'incorrect': '❌ 不正确', 'unanswered': '⚪ 未作答'}
        for index, result in enumerate(self.challenge.results):
            self.result_vars[index].set(self.t(labels[result]))
            self.answer_vars[index].set(self.t('答案：{answer}', answer=self.challenge.targets[index])
                                        if self.challenge.revealed else '')
        if not self.challenge.targets:
            self.summary.set(self.t('没有找到适合出题的词语。可返回编辑器选择更长的正文。'))
        else:
            summary = self.t('自主恢复：{score} / {total}', score=self.challenge.score, total=len(self.answers))
            summary += ' · ' + self.t('已揭露：{count}', count=self.challenge.revealed_count)
            summary += ' · ' + self.t('文本完整度：{percent}%', percent=self.challenge.restoration)
            self.summary.set(summary)

    def refresh_language(self, old):
        self.render()

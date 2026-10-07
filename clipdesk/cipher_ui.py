"""Bilingual cipher puzzle and five-seat command desk."""
import sqlite3
import tkinter as tk
from tkinter import messagebox, ttk

from .cipher import ACTION_COST, SOLVE_REWARD, STAFF_COST
from .ui import BG, BLUE, FONT, INK, MUTED, button


class CipherDialog:
    def __init__(self, app, game):
        self.app, self.t, self.game = app, app.t, game
        self.window = tk.Toplevel(app.root)
        self.window.title(self.t('密码破译'))
        height = max(680, min(820, self.window.winfo_screenheight() - 80))
        self.window.geometry(f'1080x{height}')
        self.window.minsize(860, 680)
        self.window.configure(bg=BG)
        self.window.transient(app.root)
        self.window.grab_set()
        self.window.protocol('WM_DELETE_WINDOW', self.close)
        self.window.bind('<Destroy>', self._destroy)
        self.feedback_key, self.feedback_values = '', {}
        outer = tk.Frame(self.window, bg=BG)
        outer.pack(fill='both', expand=True, padx=20, pady=8)
        outer.columnconfigure(0, weight=1)
        outer.rowconfigure(3, weight=1)
        header = tk.Frame(outer, bg=BG)
        header.grid(row=0, column=0, sticky='ew')
        tk.Label(header, text=self.t('密码破译'), bg=BG, fg=INK,
                 font=(FONT, 19, 'bold')).pack(side='left')
        button(header, '中文 / EN', app.toggle_language).pack(side='right')
        self.wallet = tk.StringVar()
        tk.Label(outer, textvariable=self.wallet, bg=BG, fg=BLUE, font=(FONT, 11, 'bold')).grid(row=1, column=0, sticky='w', pady=(4, 6))
        modes = tk.Frame(header, bg=BG)
        modes.pack(side='left', padx=16)
        self.solo_button = button(modes, self.t('独立解密'), lambda: self.set_mode('solo'))
        self.solo_button.pack(side='left', padx=(0, 8))
        self.command_button = button(modes, self.t('指挥模式'), lambda: self.set_mode('command'))
        self.command_button.pack(side='left')
        self.rule_note = tk.Label(outer, text=self.t('A=1，B=2，…，Z=26。先乘再加，超过 26 循环回 A；例如 A ×1＋1 → B。\n乘数 1–2，加数 0–3。密文再随机替换三种字母；按下方替换关系辨认，再填写规律。'),
                                  bg=BG, fg=MUTED, justify='left', anchor='w')
        self.rule_note.grid(row=2, column=0, sticky='ew', pady=(7, 6))

        card = tk.Frame(outer, bg='white', padx=14, pady=8)
        card.grid(row=3, column=0, sticky='nsew')
        self.round_label = tk.StringVar()
        tk.Label(card, textvariable=self.round_label, bg='white', fg=MUTED).pack(anchor='w')
        self.substitutions = tk.StringVar()
        tk.Label(card, textvariable=self.substitutions, bg='white', fg=BLUE,
                 font=(FONT, 11)).pack(side='bottom', anchor='w', pady=(4, 0))
        text_frame = tk.Frame(card, bg='white')
        text_frame.pack(fill='both', expand=True, pady=(4, 0))
        self.article_scrollbar = ttk.Scrollbar(text_frame)
        self.article_scrollbar.pack(side='right', fill='y')
        self.article_text = tk.Text(text_frame, wrap='word', height=3, width=1,
                                    font=(FONT, 11), bg='white', fg=INK, relief='flat',
                                    padx=3, pady=3, spacing3=4, state='disabled',
                                    yscrollcommand=self.article_scrollbar.set)
        self.article_text.pack(side='left', fill='both', expand=True)
        self.article_scrollbar.configure(command=self.article_text.yview)
        self._display_key = None

        answer = tk.Frame(outer, bg=BG)
        answer.grid(row=4, column=0, sticky='ew', pady=(8, 0))
        tk.Label(answer, text=self.t('规律：字母编号'), bg=BG, fg=INK).pack(side='left')
        tk.Label(answer, text='×', bg=BG, fg=INK, font=(FONT, 16)).pack(side='left', padx=6)
        self.multiplier = tk.StringVar()
        self.addend = tk.StringVar()
        self.multiplier_entry = ttk.Entry(answer, textvariable=self.multiplier, width=4, font=(FONT, 13))
        self.multiplier_entry.pack(side='left')
        tk.Label(answer, text='＋', bg=BG, fg=INK, font=(FONT, 16)).pack(side='left', padx=6)
        self.addend_entry = ttk.Entry(answer, textvariable=self.addend, width=4, font=(FONT, 13))
        self.addend_entry.pack(side='left')
        self.submit_button = button(answer, self.t('验证规律'), self.submit, primary=True)
        self.submit_button.pack(side='left', padx=10)
        self.next_button = button(answer, self.t('重新加密全文'), self.next_puzzle)
        self.next_button.pack(side='right')
        for entry in (self.multiplier_entry, self.addend_entry):
            entry.bind('<Return>', lambda _event: self.submit())

        self.feedback = tk.StringVar()
        self.feedback_label = tk.Label(outer, textvariable=self.feedback, bg=BG, fg=INK,
                                      justify='left', anchor='w', wraplength=815)
        self.feedback_label.grid(row=5, column=0, sticky='ew', pady=(6, 4))
        self.team_panel = tk.Frame(outer, bg=BG)
        self.team_title = tk.StringVar()
        tk.Label(self.team_panel, textvariable=self.team_title, bg=BG, fg=INK,
                 font=(FONT, 11, 'bold')).pack(anchor='w', pady=(0, 4))
        style = ttk.Style(self.window)
        style.configure('Cipher.Treeview', rowheight=25, font=(FONT, 10))
        self.team = ttk.Treeview(self.team_panel, columns=('robot', 'hint', 'actions'),
                                 show='headings', height=5, selectmode='browse', style='Cipher.Treeview')
        self.team.column('robot', width=210, minwidth=130)
        self.team.column('hint', width=330, minwidth=150)
        self.team.column('actions', width=100, minwidth=80, anchor='center')
        self.team.pack(fill='x')
        self.team.bind('<<TreeviewSelect>>', lambda _event: self.update_controls())
        controls = tk.Frame(self.team_panel, bg=BG)
        controls.pack(fill='x', pady=6)
        self.act_button = button(controls, self.t('行动 · 1 币'), self.act_selected)
        self.act_button.pack(side='left')
        self.all_button = button(controls, '', self.act_all, primary=True)
        self.all_button.pack(side='left', padx=6)
        self.dismiss_button = button(controls, self.t('解雇 · 5 币'), self.dismiss)
        self.dismiss_button.pack(side='right')
        self.recruit_button = button(controls, self.t('招募 · 5 币'), self.recruit)
        self.recruit_button.pack(side='right', padx=6)
        self.team_note = tk.Label(self.team_panel, text=self.t('提示是随机猜测，可能出现 +4、+5。满编五人一起行动时，一定包含正确乘数和加数。\n正确数字可能分属两人；单人行动或队伍不足五人时不保证正确数字。'),
                                 bg=BG, fg=MUTED, justify='left', anchor='w', wraplength=815)
        self.team_note.pack(fill='x')
        self.footer = tk.Frame(outer, bg=BG)
        self.footer.grid(row=7, column=0, sticky='ew', pady=(6, 0))
        button(self.footer, self.t('返回编辑器'), self.close).pack(side='right')
        self.reward_note = tk.Label(self.footer, text=self.t('答对 +10 币；自己答题免费。金币与队伍自动保存。'), bg=BG, fg=MUTED)
        self.reward_note.pack(side='left')
        self.window.bind('<Configure>', self._resize)
        self.refresh()

    def _resize(self, event):
        if event.widget is self.window:
            width = max(500, event.width - 45)
            for label in (self.rule_note, self.feedback_label, self.team_note):
                label.configure(wraplength=width)

    def _run(self, action):
        try:
            result = action()
        except ValueError as exc:
            self.set_feedback(str(exc))
            self.refresh()
            return False, None
        except (sqlite3.Error, OSError) as exc:
            messagebox.showerror(self.t('密码进度保存失败'), str(exc), parent=self.window)
            self.set_feedback('操作未保存，金币和队伍保持原状，请重试。')
            self.refresh()
            return False, None
        return True, result

    def set_feedback(self, key, **values):
        self.feedback_key, self.feedback_values = key, values
        self.feedback.set(self.t(key, **values))

    def source(self):
        return self.app.editor.get('1.0', 'end-1c') if self.app.current else ''

    def set_mode(self, mode):
        ok, _ = self._run(lambda: self.game.set_mode(mode))
        if ok:
            self.refresh()

    def submit(self):
        if self.game.state.puzzle.solved:
            return
        try:
            m, b = int(self.multiplier.get().strip()), int(self.addend.get().strip())
        except ValueError:
            self.set_feedback('请在两个框中填写整数：乘数 1–2，加数 0–3。')
            return
        ok, correct = self._run(lambda: self.game.submit(m, b))
        if ok:
            if correct:
                self.set_feedback('破解成功！奖励 {reward} 币，全文已还原。规律：×{m}＋{b}。',
                                  reward=SOLVE_REWARD, m=m, b=b)
            else:
                self.set_feedback('规律不匹配，请结合密文替换关系再试。答错不扣币。')
            self.refresh()

    def next_puzzle(self):
        ok, _ = self._run(lambda: self.game.next_puzzle(self.source()))
        if ok:
            self.multiplier.set('')
            self.addend.set('')
            self.set_feedback('已加密全文并随机替换密文字母。大小写、中文、标点和段落保留。')
            self.refresh()
            self.multiplier_entry.focus_set()

    def selected_slot(self):
        selection = self.team.selection()
        return int(selection[0]) if selection else None

    def act_selected(self):
        slot = self.selected_slot()
        if slot is not None:
            self._act(slot)

    def act_all(self):
        self._act(None)

    def _act(self, slot):
        ok, guesses = self._run(lambda: self.game.act(slot))
        if ok:
            self.set_feedback('已派出 {count} 名机器人，消耗 {cost} 币。请比较提示后填写规律。',
                              count=len(guesses), cost=len(guesses) * ACTION_COST)
            self.refresh()

    def dismiss(self):
        slot = self.selected_slot()
        if slot is not None:
            ok, _ = self._run(lambda: self.game.dismiss(slot))
            if ok:
                self.set_feedback('已支付 5 币遣散费，该席位现在可以招募。')
                self.refresh()

    def recruit(self):
        slot = self.selected_slot()
        if slot is not None:
            ok, _ = self._run(lambda: self.game.recruit(slot))
            if ok:
                self.set_feedback('已支付 5 币招募费，新机器人加入队伍。')
                self.refresh()

    def refresh(self):
        state, puzzle = self.game.state, self.game.state.puzzle
        self.wallet.set(self.t('金币：{coins}  ·  已破解：{wins} 题', coins=state.coins, wins=state.wins))
        self.round_label.set(self.t('第 {number} 题 · 已还原全文（{count} 字符）' if puzzle.solved
                                    else '第 {number} 题 · 全文密文（{count} 字符）',
                                    number=puzzle.number, count=len(puzzle.plaintext)))
        display_key = (puzzle.number, puzzle.plaintext, puzzle.rule, puzzle.solved,
                       tuple(puzzle.substitutions.items()))
        if display_key != self._display_key:
            self.article_text.configure(state='normal')
            self.article_text.delete('1.0', 'end')
            self.article_text.insert('1.0', puzzle.plaintext if puzzle.solved else puzzle.ciphertext)
            self.article_text.configure(state='disabled')
            self.article_text.yview_moveto(0)
            self._display_key = display_key
        self.substitutions.set(self.t('密文二次替换（原密文 → 显示字母）：{pairs}',
                                      pairs='     '.join(f'{a} → {b}' for a, b in puzzle.substitutions.items())))
        if puzzle.solved:
            self.set_feedback('破解成功！奖励 {reward} 币，全文已还原。规律：×{m}＋{b}。',
                              reward=SOLVE_REWARD,
                              m=puzzle.rule.multiplier, b=puzzle.rule.addend)
        elif not self.feedback_key:
            self.set_feedback('已加密全文并随机替换密文字母。大小写、中文、标点和段落保留。')
        for mode, widget in (('solo', self.solo_button), ('command', self.command_button)):
            widget.configure(bg=BLUE if state.mode == mode else '#eaf0fa',
                             fg='white' if state.mode == mode else INK)
        if state.mode == 'command':
            if not self.team_panel.winfo_manager():
                self.team_panel.grid(row=6, column=0, sticky='ew', pady=(4, 0))
        else:
            self.team_panel.grid_remove()
        selected = self.selected_slot()
        for index, robot in enumerate(state.robots):
            values = (self.t('机器人 {number}', number=f'{robot.number:02d}'),
                      f'×{robot.hint[0]} ＋ {robot.hint[1]}' if robot.hint else self.t('等待指令'),
                      robot.actions) if robot else (self.t('空席位 {number}', number=index + 1), '—', '—')
            if self.team.exists(str(index)):
                self.team.item(str(index), values=values)
            else:
                self.team.insert('', 'end', iid=str(index), values=values)
        self.team.selection_set(str(selected if selected is not None else 0))
        self.team_title.set(self.t('机器人队伍：{count} / 5 · 选择一个席位后操作',
                                   count=sum(robot is not None for robot in state.robots)))
        for name, text in (('robot', '队员 / 席位'), ('hint', '本题最新猜测'), ('actions', '累计行动')):
            self.team.heading(name, text=self.t(text))
        self.update_controls()

    def update_controls(self):
        state = self.game.state
        slot = self.selected_slot()
        robot = state.robots[slot] if slot is not None else None
        active = sum(robot is not None for robot in state.robots)
        playing = not state.puzzle.solved
        command = state.mode == 'command'
        self.submit_button.configure(state='normal' if playing else 'disabled')
        for entry in (self.multiplier_entry, self.addend_entry):
            entry.configure(state='normal' if playing else 'disabled')
        self.act_button.configure(state='normal' if command and playing and robot and state.coins >= ACTION_COST else 'disabled')
        self.all_button.configure(text=self.t('全员行动 · {cost} 币', cost=active * ACTION_COST),
                                  state='normal' if command and playing and active and state.coins >= active * ACTION_COST else 'disabled')
        self.dismiss_button.configure(state='normal' if command and robot and state.coins >= STAFF_COST else 'disabled')
        self.recruit_button.configure(state='normal' if command and slot is not None and not robot and state.coins >= STAFF_COST else 'disabled')

    def refresh_language(self, old):
        # The app translates widget chrome; variables retain their underlying state.
        self.feedback.set(self.t(self.feedback_key, **self.feedback_values))
        self.refresh()

    def close(self):
        self.window.destroy()

    def _destroy(self, event):
        if event.widget is self.window:
            self.game.close()

"""Mode 3 UI. All state lives in TwistedSession, never in Article or Store."""
import tkinter as tk
from tkinter import ttk, messagebox

from .twisted import TwistedSession
from .blind import CATEGORIES, MAX_INPUT_LENGTH
from .i18n import translate
from .ui import BG, INK, MUTED, FONT, button

DIRECTION_LABELS = {'nature': '自然', 'technology': '科技', 'surreal': '超现实'}
ACTION_LABELS = {**DIRECTION_LABELS, 'restore': '再生回来'}
OUTCOME_LABELS = {'restoration': 'outcome_restoration', 'redirected': '重定向生长', 'wild': '野性生长', 'fragmented': '碎片化生长'}
OUTCOME_DESCRIPTIONS = {
    'restoration': '文本已明显接近原文，或多数变异位置已被恢复。',
    'redirected': '文本沿玩家选择的方向形成了不同且仍可读的故事。',
    'wild': '文本经历大幅变化，保留一定可读性并呈现意外组合。',
    'fragmented': '文本变化后可读性明显下降，形成了碎片化的故事。',
}
BLIND_PROMPTS = dict(zip(CATEGORIES, ('输入一个人物', '输入一个动物', '输入一个动作', '输入一个地方',
                                      '输入一个奇怪的物品', '输入一个团体', '输入一种情绪或描述')))


class TwistedDialog:
    def __init__(self, app, source):
        self.app, self.t, self.source = app, app.t, source
        self.session = TwistedSession(source, blind=True)
        self.reveal_job = None
        self.editor_cover = None
        self.window = tk.Toplevel(app.root)
        self.window.title(self.t('模式 3 · 扭曲再生'))
        self.window.geometry('960x640')
        self.window.minsize(820, 580)
        self.window.configure(bg=BG)
        self.window.transient(app.root)
        self.window.grab_set()
        self.window.bind('<Destroy>', self.on_destroy, add='+')
        self.outer = tk.Frame(self.window, bg=BG)
        self.outer.pack(fill='both', expand=True, padx=20, pady=16)
        header = tk.Frame(self.outer, bg=BG)
        header.pack(fill='x')
        self.heading = tk.StringVar()
        tk.Label(header, textvariable=self.heading, bg=BG, fg=INK,
                 font=(FONT, 19, 'bold')).pack(side='left')
        button(header, '中文 / EN', app.toggle_language).pack(side='right')
        self.content = tk.Frame(self.outer, bg=BG)
        self.content.pack(fill='both', expand=True)
        self.show_blind()

    def cover_editor(self):
        # Cover the parent as well: moving the modal must not expose the article.
        # The editor contents, undo stack and packing remain completely intact.
        if self.editor_cover is None:
            self.editor_cover = tk.Frame(self.app.root, bg=BG)
            self.editor_cover.place(x=0, y=0, relwidth=1, relheight=1)
            tk.Label(self.editor_cover, text=self.t('文章已隐藏'), bg=BG, fg=MUTED,
                     font=(FONT, 20, 'bold')).pack(expand=True)
            self.editor_cover.lift()

    def uncover_editor(self):
        if self.editor_cover is not None:
            self.editor_cover.destroy()
            self.editor_cover = None

    def on_destroy(self, event):
        if event.widget == self.window:
            if self.reveal_job is not None:
                self.window.after_cancel(self.reveal_job)
                self.reveal_job = None
            self.uncover_editor()

    def footer(self):
        actions = tk.Frame(self.content, bg=BG)
        actions.pack(side='bottom', fill='x', pady=(12, 0))
        button(actions, self.t('返回编辑器'), self.window.destroy).pack(side='right')
        return actions

    def show_blind(self):
        self.clear_content()
        self.cover_editor()
        self.heading.set(self.t('模式 3 · 扭曲再生'))
        actions = self.footer()
        self.blind_regrow_button = button(actions, self.t('🌱 开始再生'), self.regrow_seed, primary=True, state='disabled')
        self.blind_regrow_button.configure(font=(FONT, 14, 'bold'), padx=30, pady=12)
        self.blind_regrow_button.pack(side='left')
        tk.Label(self.content, text=self.t('先种下你的词，再看看它会长成什么。'),
                 bg=BG, fg=INK, font=(FONT, 13), wraplength=770, justify='left').pack(anchor='w', pady=(20, 8))
        tk.Label(self.content, text=self.t('文章已隐藏'), bg=BG, fg=MUTED).pack(anchor='w', pady=(0, 12))
        table = tk.Frame(self.content, bg=BG)
        table.pack(fill='x')
        table.columnconfigure(1, weight=1)
        self.blind_inputs, self.wild_buttons = {}, {}
        # Category order hides source order as well as all text and positions.
        for index, slot in enumerate(sorted(self.session.blind_slots, key=lambda slot: CATEGORIES.index(slot.category))):
            tk.Label(table, text=self.t(BLIND_PROMPTS[slot.category]), bg=BG, fg=INK,
                     anchor='w').grid(row=index, column=0, sticky='w', padx=(0, 12), pady=9)
            value = tk.StringVar(value=self.session.blind_inputs[slot.id])
            entry = ttk.Entry(table, textvariable=value, width=28,
                              validate='key', validatecommand=(self.window.register(lambda proposed: len(proposed) <= MAX_INPUT_LENGTH), '%P'))
            entry.grid(row=index, column=1, sticky='ew', pady=9)
            value.trace_add('write', lambda *_, key=slot.id, variable=value: self.blind_changed(key, variable))
            wild = button(table, self.t('🎲 疯狂建议'), lambda key=slot.id: self.suggest_wild(key))
            wild.grid(row=index, column=2, padx=(12, 0), pady=9)
            self.blind_inputs[slot.id], self.wild_buttons[slot.id] = value, wild
        if not self.blind_inputs:
            tk.Label(self.content, text=self.t('这颗种子太短，换一篇文章再来种词吧。'), bg=BG, fg=MUTED,
                     wraplength=750).pack(anchor='w', pady=20)
        self.update_blind_ready()

    def blind_changed(self, key, variable):
        self.session.blind_inputs[key] = variable.get()
        self.update_blind_ready()

    def update_blind_ready(self):
        try:
            self.session.validate_blind({key: value.get() for key, value in self.blind_inputs.items()})
            ready = True
        except ValueError:
            ready = False
        self.blind_regrow_button.configure(state='normal' if ready else 'disabled')

    def suggest_wild(self, key):
        self.blind_inputs[key].set(self.session.wild_suggestion(key, self.app.language))

    def regrow_seed(self):
        if self.reveal_job is not None or self.session.phase != 'blind':
            return
        try:
            answers = self.session.validate_blind({key: value.get() for key, value in self.blind_inputs.items()})
        except ValueError as exc:
            messagebox.showerror(self.t('无法再生'), translate(str(exc), self.app.language), parent=self.window)
            return
        self.clear_content()
        tk.Label(self.content, text=self.t('正在生长……'), bg=BG, fg=INK,
                 font=(FONT, 24, 'bold')).pack(expand=True)
        self.reveal_job = self.window.after(450, lambda: self.finish_reveal(answers))

    def finish_reveal(self, answers):
        self.reveal_job = None
        self.session.reveal_seed(answers)
        self.show_reveal()

    def show_reveal(self):
        self.clear_content()
        self.uncover_editor()
        self.heading.set(self.t('看看你创造了什么。'))
        actions = self.footer()
        self.continue_button = button(actions, self.t('继续生长'), self.continue_growing, primary=True)
        self.continue_button.pack(side='left')
        self.seed_back_button = button(actions, self.t('再生回来'), lambda: self.continue_growing(restore=True))
        self.seed_back_button.pack(side='left', padx=12)
        tk.Label(self.content, text=self.t('种子变异 · 第 0 代'), bg=BG, fg=MUTED).pack(anchor='w', pady=12)
        panels = tk.Frame(self.content, bg=BG)
        panels.pack(fill='both', expand=True)
        panels.columnconfigure((0, 1), weight=1, uniform='reveal')
        panels.rowconfigure(1, weight=1)
        tk.Label(panels, text=self.t('原始故事'), bg=BG, fg=INK).grid(row=0, column=0, sticky='w', pady=6)
        tk.Label(panels, text=self.t('你的再生故事'), bg=BG, fg=INK).grid(row=0, column=1, sticky='w', pady=6)
        left, right = tk.Frame(panels), tk.Frame(panels)
        left.grid(row=1, column=0, sticky='nsew', padx=(0, 6))
        right.grid(row=1, column=1, sticky='nsew', padx=(6, 0))
        self.original_box = self.text_panel(left, self.source)
        self.reveal_box = self.text_panel(right, self.session.current_generation)
        self.original_box.tag_configure('seed', background='#fff0bf', foreground='#754b00')
        self.reveal_box.tag_configure('seed', background='#d2f4e2', foreground='#14543b')
        offset = 0
        for change in self.session.seed_record.mutations_applied:
            self.original_box.tag_add('seed', f'1.0+{change.start}c', f'1.0+{change.end}c')
            start = change.start + offset
            self.reveal_box.tag_add('seed', f'1.0+{start}c', f'1.0+{start + len(change.after)}c')
            offset += len(change.after) - (change.end - change.start)

    def continue_growing(self, restore=False):
        self.session.continue_seed()
        self.show_round()
        if restore:
            self.begin_restore()

    def clear_content(self):
        for widget in self.content.winfo_children():
            widget.destroy()

    def text_panel(self, parent, text):
        frame = tk.Frame(parent, bg='white')
        frame.pack(fill='both', expand=True)
        box = tk.Text(frame, wrap='word', height=5, font=(FONT, 11), padx=12, pady=10)
        scroll = ttk.Scrollbar(frame, command=box.yview)
        scroll.pack(side='right', fill='y')
        box.configure(yscrollcommand=scroll.set)
        box.pack(fill='both', expand=True)
        box.insert('1.0', text)
        box.configure(state='disabled')
        return box

    def show_round(self):
        if self.session.phase != 'growth':
            return
        self.clear_content()
        actions = self.footer()
        tk.Label(self.content, text=self.t('先选生长方向，再填写或选择替换词。再生后点击下一代；共 3 代，结束时查看故事和最终形态。'),
                 bg=BG, fg=MUTED, wraplength=880, justify='left').pack(anchor='w', pady=8)
        self.round_label = tk.StringVar()
        tk.Label(self.content, textvariable=self.round_label, bg=BG, fg=INK).pack(anchor='w')
        self.action_hint = tk.StringVar()
        tk.Label(self.content, textvariable=self.action_hint, bg=BG, fg=MUTED,
                 wraplength=880, justify='left').pack(anchor='w')
        direction_row = tk.Frame(self.content, bg=BG)
        direction_row.pack(fill='x', pady=6)
        tk.Label(direction_row, text=self.t('生长方向'), bg=BG, fg=INK).pack(side='left')
        self.direction_var = tk.StringVar()
        self.direction_combo = ttk.Combobox(direction_row, textvariable=self.direction_var, state='readonly', width=16,
                                           values=[self.t(label) for label in DIRECTION_LABELS.values()])
        self.direction_combo.pack(side='left', padx=12)
        self.direction_combo.bind('<<ComboboxSelected>>', self.direction_selected)
        self.back_button = button(direction_row, self.t('再生回来'), self.begin_restore)
        self.back_button.pack(side='right')
        self.text = self.text_panel(self.content, self.session.current_generation)
        # Four targets leave space for the story and the next action.
        area = tk.Frame(self.content, bg=BG, height=220)
        area.pack(fill='x', pady=8)
        area.pack_propagate(False)
        canvas = tk.Canvas(area, bg=BG, highlightthickness=0)
        scroll = ttk.Scrollbar(area, command=canvas.yview)
        scroll.pack(side='right', fill='y')
        canvas.configure(yscrollcommand=scroll.set)
        canvas.pack(fill='both', expand=True)
        table = tk.Frame(canvas, bg=BG)
        table_id = canvas.create_window(0, 0, window=table, anchor='nw')
        table.bind('<Configure>', lambda event: canvas.configure(scrollregion=canvas.bbox('all')))
        canvas.bind('<Configure>', lambda event: canvas.itemconfigure(table_id, width=event.width))
        tk.Label(table, text=self.t('原文'), bg=BG, fg=MUTED).grid(row=0, column=0, sticky='w')
        tk.Label(table, text=self.t('自定义替换 / 随机候选'), bg=BG, fg=MUTED).grid(row=0, column=1, sticky='w')
        self.inputs, self.combos, self.suggest_buttons = {}, {}, []
        for index, target in enumerate(self.session.targets, 1):
            # Raw target words must never be translated as interface strings.
            target_var = tk.StringVar(value=target)
            label = tk.Label(table, textvariable=target_var, bg=BG, fg=INK, width=24, wraplength=235, anchor='w', justify='left')
            label.target_var = target_var
            label.grid(row=index, column=0, sticky='w', pady=3)
            value = tk.StringVar()
            combo = ttk.Combobox(table, textvariable=value, values=self.session.suggestions[target], width=32)
            combo.grid(row=index, column=1, sticky='ew', padx=(0, 12), pady=3)
            suggest = button(table, self.t('随机候选'), lambda word=target: self.suggest(word))
            suggest.configure(pady=2)
            suggest.grid(row=index, column=2, sticky='w', pady=3)
            self.inputs[target], self.combos[target] = value, combo
            self.suggest_buttons.append(suggest)
        table.columnconfigure(1, weight=1)
        if not self.session.targets:
            tk.Label(table, text=self.t('本代没有合适的目标词，可保留正文继续下一代。'),
                     bg=BG, fg=MUTED).grid(row=1, column=0, columnspan=3, pady=15)
        self.mutation_widgets = list(table.winfo_children())
        self.restore_vars, self.restore_widgets = {}, []
        hint = tk.Label(table, text=self.t('选择要恢复的词'), bg=BG, fg=INK)
        hint.grid(row=0, column=0, columnspan=3, sticky='w')
        self.restore_widgets.append(hint)
        for index, key in enumerate(self.session.restore_options, 1):
            original, current = key[:2]
            selected = tk.BooleanVar(value=False)
            label = tk.StringVar(value=f'{current} → {original}')
            checkbox = tk.Checkbutton(table, textvariable=label, variable=selected, bg=BG, anchor='w', wraplength=720, justify='left')
            checkbox.label_var = label
            checkbox.grid(row=index, column=0, columnspan=3, sticky='w', pady=3)
            self.restore_vars[key] = selected
            self.restore_widgets.append(checkbox)
        if not self.restore_vars:
            empty = tk.Label(table, text=self.t('当前没有可恢复的变异词。'), bg=BG, fg=MUTED)
            empty.grid(row=1, column=0, columnspan=3, sticky='w', pady=10)
            self.restore_widgets.append(empty)
        for widget in self.mutation_widgets + self.restore_widgets:
            widget.grid_remove()
        self.regrow_button = button(actions, self.t('再生'), self.regrow, primary=True, state='disabled')
        self.regrow_button.pack(side='left')
        self.next_button = button(actions, self.t('下一代'), self.next_generation, state='disabled')
        self.next_button.pack(side='left', padx=8)
        self.refresh_language(None)

    def direction_selected(self, event=None):
        direction = next(key for key, label in DIRECTION_LABELS.items() if self.t(label) == self.direction_var.get())
        self.choose_direction(direction)

    def choose_direction(self, direction):
        self.session.set_direction(direction)
        self.direction_var.set(self.t(DIRECTION_LABELS[direction]))
        self.show_action()

    def begin_restore(self):
        self.session.begin_restore()
        self.show_action()

    def show_action(self):
        for widget in self.mutation_widgets + self.restore_widgets:
            widget.grid_remove()
        for widget in self.restore_widgets if self.session.action == 'restore' else self.mutation_widgets:
            widget.grid()
        for target, combo in self.combos.items():
            combo.configure(values=self.session.suggestions[target])
        self.regrow_button.configure(state='normal')
        self.refresh_language(None)

    def suggest(self, target):
        self.session.refresh_suggestions(target)
        self.combos[target].configure(values=self.session.suggestions[target])
        self.combos[target].focus_set()
        self.combos[target].event_generate('<Down>')

    def regrow(self):
        try:
            if self.session.action == 'restore':
                self.session.regrow(restore=[key for key, value in self.restore_vars.items() if value.get()])
            else:
                self.session.regrow({word: value.get() for word, value in self.inputs.items()})
        except ValueError as exc:
            messagebox.showerror(self.t('无法再生'), translate(str(exc), self.app.language), parent=self.window)
            return
        if self.session.finished:
            self.show_result()
            return
        self.text.configure(state='normal')
        self.text.delete('1.0', 'end')
        self.text.insert('1.0', self.session.current_generation)
        self.text.configure(state='disabled')
        for combo in self.combos.values():
            combo.configure(state='disabled')
        for widget in self.suggest_buttons:
            widget.configure(state='disabled')
        self.regrow_button.configure(state='disabled')
        self.direction_combo.configure(state='disabled')
        self.back_button.configure(state='disabled')
        for widget in self.restore_widgets:
            if isinstance(widget, tk.Checkbutton):
                widget.configure(state='disabled')
        self.next_button.configure(state='normal')
        self.refresh_language(None)

    def next_generation(self):
        self.session.next_generation()
        self.show_round()

    def show_result(self):
        self.clear_content()
        if not self.session.growth_awarded:
            self.app.stories_regrown = getattr(self.app, 'stories_regrown', 0) + 1
            self.session.growth_awarded = True
        actions = self.footer()
        button(actions, self.t('再次扭曲'), self.new_mutation, primary=True).pack(side='left')
        button(actions, self.t('查看历史'), self.view_history).pack(side='left', padx=8)
        self.growth_feedback = tk.StringVar()
        tk.Label(self.content, textvariable=self.growth_feedback, bg=BG, fg='#16704a',
                 font=(FONT, 13, 'bold')).pack(anchor='w', pady=(10, 0))
        self.stats = tk.StringVar()
        tk.Label(self.content, textvariable=self.stats, bg=BG, fg=INK,
                 font=(FONT, 10), wraplength=930, justify='left').pack(anchor='w', pady=12)
        tk.Label(self.content, text=self.t('评分是确定性文本规则的估计，不代表语义或语法质量。'),
                 bg=BG, fg=MUTED).pack(anchor='w')
        tk.Label(self.content, text=self.t('修改词数按各代实际替换的出现次数累计。'),
                 bg=BG, fg=MUTED).pack(anchor='w', pady=(0, 10))
        panels = tk.Frame(self.content, bg=BG)
        panels.pack(fill='both', expand=True)
        panels.columnconfigure((0, 1), weight=1, uniform='result')
        panels.rowconfigure(1, weight=1)
        tk.Label(panels, text=self.t('原始故事'), bg=BG, fg=INK).grid(row=0, column=0, sticky='w')
        tk.Label(panels, text=self.t('最终故事'), bg=BG, fg=INK).grid(row=0, column=1, sticky='w')
        left, right = tk.Frame(panels), tk.Frame(panels)
        left.grid(row=1, column=0, sticky='nsew', padx=(0, 6))
        right.grid(row=1, column=1, sticky='nsew', padx=(6, 0))
        self.original_box = self.text_panel(left, self.session.original_text)
        self.final_box = self.text_panel(right, self.session.current_generation)
        self.refresh_language(None)

    def view_history(self):
        if self.session.phase != 'growth':
            return
        self.history_window = tk.Toplevel(self.window)
        self.history_window.title(self.t('查看历史'))
        self.history_window.geometry('800x560')
        self.history_window.transient(self.window)
        self.history_window.grab_set()
        self.history_tabs = ttk.Notebook(self.history_window)
        self.history_tabs.pack(fill='both', expand=True, padx=10, pady=10)
        self.history_details = []
        texts = [self.source] + ([self.session.seed_record.text] if self.session.seed_record else []) + self.session.generation_history[1:]
        for index, text in enumerate(texts):
            frame = tk.Frame(self.history_tabs)
            number = index if not self.session.seed_record or index == 0 else ('seed' if index == 1 else index - 1)
            self.history_tabs.add(frame, text=self.history_label(number))
            details = tk.StringVar(value=self.history_detail(number))
            tk.Label(frame, textvariable=details, wraplength=760, justify='left',
                     anchor='w').pack(fill='x', padx=12, pady=8)
            self.history_details.append(details)
            self.text_panel(frame, text)
        self.history_window.protocol('WM_DELETE_WINDOW', self.close_history)

    def close_history(self):
        self.history_window.destroy()
        self.window.grab_set()

    def new_mutation(self):
        self.session = TwistedSession(self.source, blind=True)
        self.show_blind()

    def history_label(self, index):
        if index == 'seed':
            return self.t('种子变异 · 第 0 代')
        return self.t('原文') if index == 0 else self.t('第 {number} 代：{direction}', number=index,
            direction=self.t(ACTION_LABELS[self.session.generation_records[index - 1].direction]))

    def history_detail(self, index):
        if index == 0:
            return self.t('原始故事')
        record = self.session.seed_record if index == 'seed' else self.session.generation_records[index - 1]
        def changes(items):
            return ', '.join(f'{item.before} → {item.after}' for item in items) or self.t('无')
        return self.t('本代修改：{changes}', changes=changes(record.mutations_applied)) + '\n' + \
               self.t('本代恢复：{changes}', changes=changes(record.restores_applied))

    def refresh_language(self, old):
        self.window.title(self.t('模式 3 · 扭曲再生'))
        if self.session.phase in ('blind', 'reveal'):
            self.heading.set(self.t('看看你创造了什么。' if self.session.phase == 'reveal' else '模式 3 · 扭曲再生'))
            return
        if self.session.finished:
            self.heading.set(self.t('扭曲再生完成'))
            self.growth_feedback.set(self.t('本次生长 +1 · 已再生故事：{count}', count=self.app.stories_regrown))
            score = self.session.scores
            self.stats.set('\n'.join((
                self.t('代数：{count}', count=self.session.generation) + '    ' + self.t('修改词数：{count}', count=self.session.words_mutated),
                self.t('恢复词数：{count}', count=self.session.words_restored),
                self.t('扭曲度：{value}%', value=score.distortion) + '    ' + self.t('可读性：{value}%', value=score.coherence),
                self.t('再生评分：{value}%', value=score.regrowth),
                self.t('生长路径') + ': ' + ' → '.join(self.history_label(index) for index in range(1, 4)),
                self.t('最终形态：{outcome}', outcome=self.t(OUTCOME_LABELS[self.session.outcome])),
                self.t(OUTCOME_DESCRIPTIONS[self.session.outcome]),
            )))
        else:
            self.heading.set(self.t('模式 3 · 扭曲再生'))
            number = self.session.generation if self.session.round_complete else self.session.generation + 1
            self.round_label.set(self.t('第 {number} 代完成' if self.session.round_complete else '第 {number} / 3 代', number=number))
            self.direction_combo.configure(values=[self.t(label) for label in DIRECTION_LABELS.values()])
            self.direction_var.set(self.t(DIRECTION_LABELS[self.session.direction]) if self.session.direction else '')
            self.action_hint.set(self.t('勾选部分变异词，点击再生恢复到原词并消耗这一代。其他变异保留；选生长方向可继续修改。'
                if self.session.action == 'restore' else '选择这一代的生长方向') if not self.session.round_complete
                else self.t('本代已完成，点击下一代继续。'))
        if hasattr(self, 'history_window') and self.history_window.winfo_exists():
            for index in range(len(self.history_tabs.tabs())):
                number = index if not self.session.seed_record or index == 0 else ('seed' if index == 1 else index - 1)
                self.history_tabs.tab(index, text=self.history_label(number))
                self.history_details[index].set(self.history_detail(number))

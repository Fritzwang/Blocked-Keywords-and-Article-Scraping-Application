"""验证打包后的依赖、提取、保存、替换和界面，不读写用户文稿。"""
import tempfile
from pathlib import Path

from .extractor import extract_html, fetch_article
from .replacement import Rule, preview
from .storage import Store

SAMPLE_HTML = """<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><title>城市阅读空间开放 - 新闻</title></head>
<body><nav><a href="/">首页</a> 导航中心</nav><article><h1>城市阅读空间开放</h1>
<p>城市阅读空间今天正式开放，为周边居民提供安静舒适的阅读环境。新空间设置了图书阅览区、交流区和儿童活动区，方便不同年龄的读者使用。</p>
<p>工作人员介绍，场馆将定期举办读书交流和文化讲座。居民可以通过公开渠道了解活动安排，并根据自己的时间报名参加。</p>
<p>下一阶段，城市阅读空间还将持续收集读者意见，完善设施与服务，让更多人享受到便利的公共文化资源。</p></article><footer>页脚版权说明</footer></body></html>"""


def run(ui=False, url=None):
    report = {}
    article = extract_html(SAMPLE_HTML, "https://example.com/article")
    assert article.title == "城市阅读空间开放"
    assert "新空间设置了图书阅览区" in article.body
    assert "导航中心" not in article.body
    report["extraction"] = {"title": article.title, "characters": len(article.body)}
    with tempfile.TemporaryDirectory(prefix="clipdesk-check-") as temp:
        directory = Path(temp)
        store = Store(directory / "articles.db")
        store.save(article)
        changes = preview(store.all(), [Rule("城市", "社区")])
        assert len(changes) == 1
        store.apply(changes)
        assert "社区" in store.get(article.id).title
        store.close()
        store = Store(directory / "articles.db")
        assert store.undo_batch() == 1
        assert store.get(article.id).title == article.title
        assert store.get(article.id).original_body == article.body
        store.close()
        report["storage_and_batch_undo"] = "passed"
        if ui:
            import tkinter as tk
            from .ui import App, ReplaceDialog
            root = tk.Tk()
            root.withdraw()
            failures = []
            root.report_callback_exception = lambda kind, value, tb: failures.append(str(value))
            app = App(root, directory)
            root.update()
            assert app.current.id == article.id
            app.title_var.set("编辑后的标题")
            app.editor.insert("end", "\n\n新增段落。")
            root.update()
            assert app.flush()
            assert app.store.get(article.id).title == "编辑后的标题"
            assert app.store.get(article.id).body.endswith("新增段落。")
            dialog = ReplaceDialog(app)
            dialog.rules = [Rule("新增", "替换")]
            dialog.render_rules()
            dialog.make_preview()
            assert len(dialog.changes) == 1
            dialog.apply()
            assert app.editor.get("1.0", "end-1c").endswith("替换段落。")
            app.undo_batch()
            assert app.editor.get("1.0", "end-1c").endswith("新增段落。")
            # Exercise the new UI in the packaged executable as well as source.
            app.set_language('en')
            assert app.article_popup.entrycget(0, 'label') == 'Open Article'
            assert app.article_popup.entrycget(1, 'label') == 'Delete Article'
            assert app.article_popup.entrycget(3, 'label') == 'Delete All Articles...'
            assert app.current.id == article.id
            app.set_language('zh')
            assert app.article_popup.entrycget(3, 'label') == '删除所有文章...'
            report['language_roundtrip'] = 'passed'
            from .models import Article
            puzzle_article = Article(title='Regrowth verification', body='Forest river forest city.')
            app.store.save(puzzle_article)
            app.show_article(puzzle_article)
            puzzle = app.open_challenge()
            root.update()
            assert len(puzzle.answers) == 3
            assert puzzle.challenge.render() == '***** ***** ***** *****.'
            puzzle.answers[0].set(' FOREST ')
            puzzle.answers[1].set('cat')
            puzzle.test()
            assert puzzle.challenge.render() == 'Forest ***** forest *****.'
            assert puzzle.challenge.results == ['correct', 'incorrect', 'unanswered']
            assert not any(value.get() for value in puzzle.answer_vars)
            from tkinter import messagebox
            original_confirm = messagebox.askyesno
            try:
                messagebox.askyesno = lambda *args, **kwargs: False
                puzzle.reveal()
                assert not puzzle.challenge.revealed
                messagebox.askyesno = lambda *args, **kwargs: True
                puzzle.reveal()
                assert puzzle.challenge.render() == puzzle_article.body
                assert puzzle.challenge.score == 1
                app.set_language('en')
                assert puzzle.summary.get() == 'Player Recovery: 1 / 3 · Revealed: 2 · Document Restoration: 100%'
                puzzle.new_challenge()
                assert not puzzle.challenge.revealed
                assert all(value.get() == '' for value in puzzle.answers)
                puzzle.window.destroy()
                assert app.editor.get('1.0', 'end-1c') == puzzle_article.body
                assert app.store.get(puzzle_article.id).body == puzzle_article.body
                twisted = app.open_twisted()
                assert twisted.session.phase == 'blind'
                assert not hasattr(twisted, 'text')
                for slot in twisted.session.blind_slots:
                    twisted.blind_inputs[slot.id].set(slot.original)
                twisted.blind_regrow_button.invoke()
                done = tk.BooleanVar(value=False)
                root.after(550, lambda: done.set(True))
                root.wait_variable(done)
                assert twisted.session.phase == 'reveal'
                assert twisted.original_box.get('1.0', 'end-1c') == puzzle_article.body
                twisted.continue_button.invoke()
                twisted.choose_direction('technology')
                twisted.inputs['forest'].set('machine')
                twisted.inputs['river'].set('network')
                targets, choices = twisted.session.targets, dict(twisted.session.suggestions)
                app.set_language('zh')
                assert twisted.session.targets == targets
                assert twisted.session.suggestions == choices
                assert twisted.inputs['forest'].get() == 'machine'
                for generation in range(3):
                    if generation == 1:
                        twisted.inputs['machine'].set('robot')
                    elif generation == 2:
                        for key, value in twisted.restore_vars.items():
                            if key[:2] == ('forest', 'robot'):
                                value.set(True)
                    twisted.regrow()
                    if generation < 2:
                        twisted.next_generation()
                        twisted.choose_direction('surreal') if generation == 0 else twisted.begin_restore()
                assert twisted.session.finished
                assert len(twisted.session.generation_history) == 4
                assert twisted.original_box.get('1.0', 'end-1c') == puzzle_article.body
                assert twisted.final_box.get('1.0', 'end-1c') == 'Forest network forest city.'
                assert twisted.session.words_restored == 2
                assert len(twisted.session.targets) <= 4
                assert len(twisted.session.generation_records[0].mutations_applied) == 3
                assert len(twisted.session.generation_records[2].restores_applied) == 2
                assert [record.direction for record in twisted.session.generation_records] == ['technology', 'surreal', 'restore']
                scores = twisted.session.scores
                app.set_language('en')
                assert 'Distortion:' in twisted.stats.get()
                assert twisted.session.scores == scores
                report['twisted_three_rounds_history_language'] = 'passed'
                report['direction_lineage_partial_restore_outcome'] = 'passed'
                report['final_outcome'] = twisted.session.outcome
                report['twisted_scores'] = {'distortion': scores.distortion, 'coherence': scores.coherence, 'regrowth': scores.regrowth}
                from .twisted import TwistedSession
                import random
                diverse = TwistedSession('forest river city fire garden ocean mountain flower engine island bird castle', random.Random(8))
                first = set(diverse.targets)
                diverse.set_direction('technology')
                tech = dict(diverse.suggestions)
                diverse.regrow()
                diverse.next_generation()
                assert len(set(diverse.targets) - first) == 4
                diverse.set_direction('surreal')
                assert all(set(values).isdisjoint(set().union(*map(set, tech.values()))) for values in diverse.suggestions.values())
                report['four_targets_diversity_suggestion_history'] = 'passed'
                twisted.new_mutation()
                assert twisted.session.generation_history == [puzzle_article.body]
                twisted.window.destroy()
                assert app.store.get(puzzle_article.id).body == puzzle_article.body
                reframe_article = Article(title='Reframe verification', body=(
                    'The city council approved the new project after several months of public debate despite strong local opposition and concerns about the woodland.\n\n'
                    'Residents welcomed the new gardens because children needed a safe place to play while volunteers planted flowers and opened paths beside the river.\n\n'
                    'The mayor promised to protect the forest after heavy floods damaged nearby roads but local families asked for stronger plans before winter arrived.'))
                app.store.save(reframe_article)
                app.show_article(reframe_article)
                source_row = app.store.get(reframe_article.id).to_dict()
                reframe_results = {}
                for method in ('pure', 'editorial'):
                    reframe = app.open_reframe()
                    assert reframe.session.method is None
                    reframe.start(method)
                    for number in range(1, 4):
                        assert 5 <= len(reframe.session.current_round.order) <= 7
                        if method == 'pure' or number == 1:
                            assert reframe.remove_button.cget('state') == 'disabled'
                        reframe.down_button.invoke()
                        reframe.down_button.invoke()
                        if method == 'editorial':
                            for _ in range(number - 1):
                                reframe.remove_button.invoke()
                            assert reframe.remove_button.cget('state') == 'disabled'
                            if number == 2:
                                removed = list(reframe.session.current_round.removed)
                                reframe.restore_button.invoke()
                                assert not reframe.session.current_round.removed
                                reframe.remove_button.invoke()
                                assert reframe.session.current_round.removed == removed
                        selected = reframe.fragments.selection()
                        order = list(reframe.session.current_round.order)
                        app.set_language('en' if app.language == 'zh' else 'zh')
                        assert reframe.fragments.selection() == selected
                        assert reframe.session.current_round.order == order
                        reframe.lock_button.invoke()
                        if number < 3:
                            reframe.next_button.invoke()
                    assert reframe.session.finished
                    assert reframe.original_box.get('1.0', 'end-1c') == reframe_article.body
                    assert reframe.final_box.get('1.0', 'end-1c') == reframe.session.working_copy
                    assert reframe.session.sections_reframed == 3
                    assert reframe.session.fragments_removed == (3 if method == 'editorial' else 0)
                    reframe_results[method] = {'rounds': len(reframe.session.history),
                        'moved': reframe.session.fragments_moved, 'removed': reframe.session.fragments_removed,
                        'sections': reframe.session.sections_reframed, 'outcome': reframe.session.outcome}
                    reframe.window.destroy()
                    assert app.editor.get('1.0', 'end-1c') == reframe_article.body
                    assert app.store.get(reframe_article.id).to_dict() == source_row
                report['reframe_pure_editorial_three_rounds_language_restore_isolation'] = reframe_results
                import json
                fixture = Path('work/mode4-real-article.json')
                if fixture.exists():
                    public_source = json.loads(fixture.read_text(encoding='utf-8'))
                    blind_article = Article(title=public_source['title'], body=public_source['body'], url=public_source['url'])
                else:
                    blind_article = Article(title='Blind verification', body=(
                        'The Prime Minister met business leaders in Sydney. A penguin carried a telescope '
                        'through the ancient garden. Scientists launched a rocket while residents watched the mysterious sky.'))
                report['blind_playthroughs'] = verify_blind_playthroughs(app, blind_article)
                before = [item.to_dict() for item in app.store.all()]
                messagebox.askyesno = lambda *args, **kwargs: False
                app.delete_all_articles()
                assert [item.to_dict() for item in app.store.all()] == before
                messagebox.askyesno = lambda *args, **kwargs: True
                app.delete_all_articles()
                assert app.store.all() == []
                assert app.current is None
                assert app.editor.get('1.0', 'end-1c') == ''
                assert app.drafts.get_children() == ()
            finally:
                messagebox.askyesno = original_confirm
            report['regrowth_repeated_words_test_reveal_reset'] = 'passed'
            report['delete_all_cancel_confirm'] = 'passed'
            app.new_article()
            root.update()
            assert len(app.store.all()) == 1
            report['cipher_command_economy_persistence'] = verify_cipher_playthrough(app)
            if url:
                live_article = fetch_article(url)
                app.store.save(live_article)
                app.show_article(live_article)
                puzzle = app.open_challenge()
                assert 0 < len(puzzle.answers) <= 5
                assert '*****' in puzzle.challenge.render()
                assert app.store.get(live_article.id).body == live_article.body
                puzzle.window.destroy()
                report['live_fetch_to_editor_and_challenge'] = 'passed'
                report['live_fetch'] = {'url': live_article.url, 'title': live_article.title,
                                        'characters': len(live_article.body)}
            assert not failures, failures
            for job in root.tk.call('after', 'info'):
                root.after_cancel(job)
            app.close()
            report["ui_edit_preview_apply_undo"] = "passed"
    if url and not ui:
        live_article = fetch_article(url)
        report["live_fetch"] = {"url": live_article.url, "title": live_article.title, "characters": len(live_article.body), "sample": live_article.body[:200]}
    return report


def verify_cipher_playthrough(app):
    """Check the new mode against temporary data in source and packaged builds."""
    from dataclasses import asdict

    article = app.current
    article.body = ('The whole article is encrypted, including every paragraph.\n'
                    'Mixed CASE, punctuation, 中文 and 123 remain in their positions.\n\n') * 100
    app.store.save(article)
    app.show_article(article)
    before = [article.to_dict() for article in app.store.all()]
    editor = app.editor.get('1.0', 'end-1c')
    dialog = app.open_cipher()
    assert dialog.game.state.puzzle.plaintext == editor
    assert dialog.article_text.get('1.0', 'end-1c') == dialog.game.state.puzzle.ciphertext
    substitutions = dict(dialog.game.state.puzzle.substitutions)
    assert len(substitutions) == 3
    assert not hasattr(dialog, 'clues')
    for a, b in substitutions.items():
        assert a != b and f'{a} → {b}' in dialog.substitutions.get()
    assert dialog.game.state.puzzle.ciphertext != dialog.game.state.puzzle.rule.encrypt(editor)
    assert dialog.game.state.coins == 20
    dialog.command_button.invoke()
    dialog.all_button.invoke()
    state = dialog.game.state
    rule = state.puzzle.rule
    assert state.coins == 15
    assert rule.multiplier in [bot.hint[0] for bot in state.robots]
    assert rule.addend in [bot.hint[1] for bot in state.robots]
    dialog.multiplier.set(str(rule.multiplier))
    dialog.addend.set(str(rule.addend))
    app.set_language('en')
    assert dialog.window.title() == 'Cipher Challenge'
    dialog.submit_button.invoke()
    assert dialog.game.state.coins == 25
    assert dialog.game.state.wins == 1
    assert dialog.article_text.get('1.0', 'end-1c') == editor
    dialog.submit()
    assert dialog.game.state.coins == 25
    dialog.team.selection_set('0')
    dialog.dismiss()
    assert dialog.game.state.coins == 20
    dialog.recruit()
    assert dialog.game.state.coins == 15
    assert dialog.game.state.robots[0].number == 6
    snapshot = asdict(dialog.game.state)
    dialog.close()
    dialog = app.open_cipher()
    assert asdict(dialog.game.state) == snapshot
    app.set_language('zh')
    assert asdict(dialog.game.state) == snapshot
    dialog.next_button.invoke()
    assert dialog.game.state.coins == 15
    assert not dialog.game.state.puzzle.solved
    assert all(bot.hint is None for bot in dialog.game.state.robots)
    dialog.close()
    assert [article.to_dict() for article in app.store.all()] == before
    assert app.editor.get('1.0', 'end-1c') == editor
    return {'starting_coins': 20, 'reward': 10, 'robot_action_cost': 1,
            'dismiss_cost': 5, 'recruit_cost': 5, 'final_coins': 15,
            'full_team_correct_values': True, 'repeat_reward_blocked': True,
            'reopen_and_language_preserve_state': True, 'article_unchanged': True,
            'full_article_characters': len(editor), 'full_article_restored': True,
            'secondary_cipher_substitutions': substitutions, 'plaintext_clues_removed': True}


def verify_blind_playthroughs(app, article):
    """Exercise packaged Tk controls with a public fixture; never user records."""
    import copy
    import tkinter as tk
    from dataclasses import asdict

    app.store.save(article)
    app.show_article(article)
    app.root.update()
    original_row = app.store.get(article.id).to_dict()
    writes_before = app.store.db.total_changes
    results = {'source': article.url, 'title': article.title, 'characters': len(article.body)}
    custom = {'person': 'three suspicious ducks', 'animal': 'an angry penguin',
              'action': 'arguing with pigeons', 'place': 'on the Moon',
              'object': 'a haunted microwave', 'group': 'three suspicious ducks',
              'description': 'suspiciously sparkly'}
    for play in ('A', 'B'):
        app.set_language('en')
        dialog = app.open_twisted()
        assert dialog.session.phase == 'blind'
        assert not hasattr(dialog, 'original_box')
        assert dialog.editor_cover is not None
        assert 4 <= len(dialog.blind_inputs) <= 6
        for slot in dialog.session.blind_slots:
            if play == 'A':
                dialog.blind_inputs[slot.id].set(custom[slot.category])
            else:
                dialog.wild_buttons[slot.id].invoke()
                first = dialog.blind_inputs[slot.id].get()
                dialog.wild_buttons[slot.id].invoke()
                assert dialog.blind_inputs[slot.id].get() != first
        state = dialog.session
        inputs = dict(state.blind_inputs)
        slots = state.blind_slots
        app.set_language('zh')
        assert dict(state.blind_inputs) == inputs and state.blind_slots == slots
        app.set_language('en')
        dialog.blind_regrow_button.invoke()
        assert state.phase == 'blind' and dialog.reveal_job is not None
        done = tk.BooleanVar(value=False)
        app.root.after(550, lambda: done.set(True))
        app.root.wait_variable(done)
        assert state.phase == 'reveal' and state.generation == 0
        assert dialog.original_box.get('1.0', 'end-1c') == article.body
        assert dialog.reveal_box.get('1.0', 'end-1c') == state.current_generation
        assert len(state.seed_record.mutations_applied) == len(slots)
        dialog.continue_button.invoke()
        for number in range(3):
            if number == 2 and play == 'A':
                dialog.back_button.invoke()
                seed_key = next(key for key in dialog.restore_vars if len(key) == 3)
                later_key = next((key for key in dialog.restore_vars if len(key) == 2), None)
                dialog.restore_vars[seed_key].set(True)
                if later_key:
                    dialog.restore_vars[later_key].set(True)
                selections = [key for key, value in dialog.restore_vars.items() if value.get()]
                app.set_language('zh')
                assert all(dialog.restore_vars[key].get() for key in selections)
                app.set_language('en')
            else:
                dialog.choose_direction(('technology', 'surreal', 'nature')[number])
                if state.targets:
                    target = state.targets[0]
                    dialog.inputs[target].set(state.suggestions[target][0])
            dialog.regrow_button.invoke()
            if number < 2:
                dialog.next_button.invoke()
        assert state.finished
        assert len(state.generation_records) == 3
        before = (state.current_generation, copy.deepcopy(state.lineage), list(state.generation_history), state.outcome)
        app.set_language('zh')
        assert '本次生长 +1' in dialog.growth_feedback.get()
        app.set_language('en')
        assert before == (state.current_generation, state.lineage, state.generation_history, state.outcome)
        assert 'Growth +1' in dialog.growth_feedback.get()
        dialog.view_history()
        assert len(dialog.history_tabs.tabs()) == 5
        dialog.close_history()
        results[play] = {'inputs': inputs, 'slots': [asdict(slot) for slot in slots],
                         'seed': asdict(state.seed_record), 'generations': [asdict(record) for record in state.generation_records],
                         'outcome': state.outcome, 'scores': asdict(state.scores), 'growth': app.stories_regrown}
        dialog.window.destroy()
        assert app.store.get(article.id).to_dict() == original_row
        assert app.editor.get('1.0', 'end-1c') == article.body
        assert app.store.db.total_changes == writes_before
    results['article_and_database_unchanged'] = True
    results['bilingual_state_preserved'] = True
    return results

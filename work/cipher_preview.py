"""Capture the cipher window using an isolated temporary profile."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import tkinter as tk

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))
from clipdesk.ui import App
from clipdesk.models import Article

with tempfile.TemporaryDirectory(prefix='cipher-preview-') as temp:
    root = tk.Tk()
    app = App(root, Path(temp))
    failures = []
    root.report_callback_exception = lambda kind, value, tb: failures.append(str(value))
    article = Article(title='Cipher article preview', body=(
        'The whole article is now part of the cipher challenge. Every paragraph uses the same hidden rule.\n\n'
        'The five robots can suggest a multiplier and an addend. Compare their guesses with the cipher substitutions.\n\n'
        'Mixed CASE, numbers 123, punctuation and 中文 stay in the article. Find the rule to restore the full text.\n\n') * 10)
    app.store.save(article)
    app.show_article(article)
    dialog = app.open_cipher()
    dialog.command_button.invoke()
    dialog.all_button.invoke()
    dialog.window.geometry('1080x820')
    captures = []
    for language in ('zh', 'en'):
        app.set_language(language)
        root.update()
        output = PROJECT / f'work/cipher-substitutions-{language}.png'
        command = ['powershell', '-NoProfile', '-ExecutionPolicy', 'Bypass',
                   '-File', str(PROJECT / 'work/capture_cipher.ps1'),
                   '-WindowHandle', str(dialog.window.winfo_id()), '-OutputPath', str(output)]
        process = subprocess.Popen(command, creationflags=subprocess.CREATE_NO_WINDOW)
        # Keep servicing PrintWindow messages while the capture process runs.
        done = tk.BooleanVar(value=False)
        def poll():
            if process.poll() is None:
                root.after(25, poll)
            else:
                done.set(True)
        root.after(25, poll)
        root.wait_variable(done)
        assert process.returncode == 0
        captures.append(str(output))
    for job in root.tk.call('after', 'info'):
        root.after_cancel(job)
    app.close()
    assert not failures, failures
    (PROJECT / 'verification-cipher-preview.json').write_text(
        json.dumps({'ok': True, 'captures': captures}, indent=2), encoding='utf-8')

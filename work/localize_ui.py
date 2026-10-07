"""One-time migration of existing UI literals to the shared message catalog."""
import ast
from pathlib import Path

path = Path('clipdesk/ui.py')
source = path.read_text(encoding='utf-8')
replacements = {
    'f"{visible} / {len(articles)} 篇文稿"': 'self.t("{visible} / {total} 篇文稿", visible=visible, total=len(articles))',
    'f"{len(article.body):,} 字"': 'self.t("{count} 字", count=f"{len(article.body):,}")',
    '''f"{len(self.editor.get('1.0', 'end-1c')):,} 字"''': '''self.t("{count} 字", count=f"{len(self.editor.get('1.0', 'end-1c')):,}")''',
    'f"提取完成 · {len(value.body):,} 字 · 已保存到本地"': 'self.t("提取完成 · {count} 字 · 已保存到本地", count=f"{len(value.body):,}")',
    '''f"确定删除《{title.strip() or '未命名文稿'}》吗？\\n\\n"
                    "该操作会删除这篇文稿及保存的原始采集内容，且无法撤销。"''':
        '''self.t("确定删除《{title}》吗？\\n\\n该操作会删除这篇文稿及保存的原始采集内容，且无法撤销。", title=title.strip() or self.t("未命名文稿"))''',
    'f"已撤销上次替换，恢复 {count} 篇文稿。"': 'self.t("已撤销上次替换，恢复 {count} 篇文稿。", count=count)',
    'f"已追加 {len(rules)} 条规则，请预览修改。"': 'self.t("已追加 {count} 条规则，请预览修改。", count=len(rules))',
    'f"检查 {len(articles)} 篇文稿 · 将修改 {len(self.changes)} 篇 · 共匹配 {count} 处（规则顺序执行）"':
        'self.t("检查 {total} 篇文稿 · 将修改 {changed} 篇 · 共匹配 {count} 处（规则顺序执行）", total=len(articles), changed=len(self.changes), count=count)',
    'f"已替换 {count} 篇文稿，可点击「撤销批量替换」恢复。"': 'self.t("已替换 {count} 篇文稿，可点击「撤销批量替换」恢复。", count=count)',
}
for before, after in replacements.items():
    assert before in source, before
    source = source.replace(before, after)
tree = ast.parse(source)
parents = {child: node for node in ast.walk(tree) for child in ast.iter_child_nodes(node)}
lines = source.encode('utf-8').splitlines(keepends=True)
offsets = [0]
for line in lines:
    offsets.append(offsets[-1] + len(line))
changes = []
for node in ast.walk(tree):
    if not isinstance(node, ast.Constant) or not isinstance(node.value, str):
        continue
    if not any('\u4e00' <= char <= '\u9fff' for char in node.value):
        continue
    parent = parents.get(node)
    if isinstance(parent, ast.JoinedStr):
        continue
    if isinstance(parent, ast.Call) and isinstance(parent.func, ast.Attribute) and parent.func.attr == 't':
        continue
    start = offsets[node.lineno - 1] + node.col_offset
    end = offsets[node.end_lineno - 1] + node.end_col_offset
    changes.append((start, end, ('self.t(' + repr(node.value) + ')').encode('utf-8')))
data = source.encode('utf-8')
for start, end, replacement in sorted(changes, reverse=True):
    data = data[:start] + replacement + data[end:]
path.write_bytes(data)

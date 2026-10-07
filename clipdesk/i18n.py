"""UI-only string resources. Chinese source strings are stable message IDs."""
import re


EN = {
    '网页摘录': 'ClipDesk',
    '网页摘录 · 内容编辑器': 'ClipDesk · Article Editor',
    '把网页，变成你的文稿': 'Turn web pages into drafts',
    '＋  新建文稿': '+  New Article',
    '新建文稿    Ctrl+N': 'New Article    Ctrl+N',
    '本地文稿': 'Local Articles',
    '输入关键词筛选标题 / 正文': 'Search titles / body text',
    '删除当前文稿': 'Delete Current Article',
    '本地保存 · 无需账号': 'Saved locally · No account',
    '内容工作台': 'Workspace',
    '批量替换': 'Batch Replace',
    '输入文章网址，提取标题与正文后直接编辑。': 'Enter an article URL to extract and edit its title and text.',
    '网址': 'URL', '提取正文': 'Extract', '保存': 'Save',
    '查看原文': 'View Original', '撤销批量替换': 'Undo Batch Replace',
    '导出文稿…': 'Export…', '标题': 'Title', '就绪': 'Ready',
    '从一个网址开始\n\n在上方粘贴文章链接，点击「提取正文」。\n\n也可以新建文稿，自由书写。':
        'Start with a URL\n\nPaste an article link above and click Extract.\n\nOr create a new article and start writing.',
    '保存    Ctrl+S': 'Save    Ctrl+S', '退出': 'Exit', '文件': 'File',
    '撤销正文编辑    Ctrl+Z': 'Undo Text Edit    Ctrl+Z',
    '重做正文编辑    Ctrl+Y': 'Redo Text Edit    Ctrl+Y',
    '批量替换    Ctrl+H': 'Batch Replace    Ctrl+H',
    '撤销上次批量替换': 'Undo Last Batch Replace', '编辑': 'Edit',
    '使用说明': 'Help', '撤销': 'Undo', '重做': 'Redo', '剪切': 'Cut',
    '复制': 'Copy', '粘贴': 'Paste', '全选': 'Select All',
    '打开文章': 'Open Article', '删除这篇文章': 'Delete Article',
    '删除所有文章...': 'Delete All Articles...', '删除文稿': 'Delete Article',
    '未命名文稿': 'Untitled Article', ' 字': ' chars', '0 字': '0 chars',
    '0 篇文稿': '0 articles', '等待导入文章': 'Waiting for an article',
    '无法创建文稿': 'Cannot Create Article',
    '新文稿已创建，编辑内容将自动保存。': 'New article created. Edits are saved automatically.',
    '正在编辑…': 'Editing…',
    '保存失败，请导出文稿备份后检查磁盘。': 'Save failed. Export a backup, then check your disk.',
    '保存失败，编辑内容仍保留在界面中': 'Save Failed — Your Edits Remain in the Editor',
    '已自动保存到本地': 'Saved locally', '已保存到本地': 'Saved locally',
    '请先提取网页或新建文稿。': 'Extract a web page or create an article first.',
    '网址有误': 'Invalid URL', '提取中…': 'Extracting…',
    '正在下载网页并识别正文…': 'Downloading the page and extracting article text…',
    '网页提取失败': 'Article extraction failed',
    '处理网页时遇到错误：': 'Could not process the page: ',
    '提取失败，已有文稿仍保留。': 'Extraction failed. Your existing articles are safe.',
    '无法提取正文': 'Cannot Extract Article', '下载完成，但保存失败': 'Downloaded, but Could Not Save',
    '删除失败': 'Delete Failed', '文稿已删除': 'Article deleted',
    '原始内容': 'Original Content',
    '这是本地新建文稿，没有网页原文。': 'This is a local draft with no original web content.',
    '采集时的原始内容': 'Original Extracted Content',
    '导出': 'Export', '文稿': 'Article', '文稿_': 'Article_',
    '导出文稿': 'Export Article', '纯文本': 'Plain Text', '完整文稿 JSON': 'Complete Article JSON',
    '\n\n来源：': '\n\nSource: ', '已导出：': 'Exported: ', '导出失败': 'Export Failed',
    '没有可撤销的批量替换。': 'No batch replacement to undo.', '无法撤销': 'Cannot Undo',
    '规则按列表顺序执行。查找按字面文本匹配，替换内容可留空（删除）。':
        'Rules run in order using literal matches. Leave replacement blank to delete matches.',
    '处理文稿': 'Articles', '当前文稿': 'Current Article', '全部文稿': 'All Articles',
    '导出规则…': 'Export Rules…', '导入规则…': 'Import Rules…',
    '查找内容': 'Find Text', '替换为': 'Replace With',
    '标题和正文': 'Title and Body', '仅标题': 'Title Only', '仅正文': 'Body Only',
    '区分英文大小写': 'Case sensitive', '添加规则 ↓': 'Add Rule ↓',
    '查找': 'Find', '范围': 'Scope', '大小写': 'Case',
    '删除选中规则': 'Remove Rule', '上移': 'Move Up', '下移': 'Move Down',
    '添加规则后点击预览，再应用修改。': 'Add rules, preview changes, then apply.',
    '原始采集内容保留，可撤销最近一次批量替换。': 'Original content is kept. The last batch can be undone.',
    '应用替换': 'Apply', '预览修改': 'Preview',
    '规则或范围已改变，请重新预览。': 'Rules or scope changed. Preview again.',
    '（删除）': '(delete)', '区分': 'Sensitive', '不区分': 'Insensitive',
    '规则有误': 'Invalid Rule', '导入替换规则': 'Import Replacement Rules',
    '替换规则 JSON': 'Replacement Rules JSON',
    '规则文件必须是 JSON 数组，最多 500 条规则。': 'Rules must be a JSON array with at most 500 rules.',
    '导入失败': 'Import Failed', '导出替换规则': 'Export Replacement Rules',
    '替换规则.json': 'replacement-rules.json', '预览': 'Preview',
    '请先添加至少一条规则。': 'Add at least one rule first.',
    '替换前': 'Before', '替换后': 'After',
    '… 此篇预览已截断，应用时处理全文。\n': '… Preview truncated. Apply processes the full article.\n',
    '仅展示前 50 篇的修改，应用时会处理所有命中文稿。': 'Showing the first 50 articles. Apply processes all matches.',
    '没有需要修改的内容。': 'No changes needed.', '替换失败': 'Replacement Failed',
    '{visible} / {total} 篇文稿': '{visible} / {total} articles',
    '{count} 字': '{count} chars',
    '提取完成 · {count} 字 · 已保存到本地': 'Extracted · {count} chars · Saved locally',
    '确定删除《{title}》吗？\n\n该操作会删除这篇文稿及保存的原始采集内容，且无法撤销。':
        'Delete “{title}”?\n\nThis deletes the article and its saved original content. This action cannot be undone.',
    '已撤销上次替换，恢复 {count} 篇文稿。': 'Undid the last replacement in {count} articles.',
    '已追加 {count} 条规则，请预览修改。': 'Added {count} rules. Preview the changes.',
    '检查 {total} 篇文稿 · 将修改 {changed} 篇 · 共匹配 {count} 处（规则顺序执行）':
        'Checked {total} articles · {changed} to change · {count} matches (rules run in order)',
    '已替换 {count} 篇文稿，可点击「撤销批量替换」恢复。':
        'Replaced text in {count} articles. Use Undo Batch Replace to restore.',
    '确定删除全部 {count} 篇文章吗？\n\n此操作无法撤销。':
        'Are you sure you want to delete all {count} articles?\n\nThis action cannot be undone.',
    '所有文章已删除': 'All articles deleted',
    '请等待当前抓取完成后再删除全部文章。': 'Wait for the current extraction to finish before deleting all articles.',
    '文本再生': 'Regrowth Challenge', '测试': 'Test', '揭露答案': 'Reveal Answers',
    '重新生成': 'New Challenge', '返回编辑器': 'Back to Editor',
    '缺失词 {number}': 'Missing Word {number}',
    '✅ 正确': '✅ Correct', '❌ 不正确': '❌ Incorrect', '⚪ 未作答': '⚪ Not answered',
    '已揭露答案': 'Answers Revealed',
    '确定要揭露所有剩余答案吗？': 'Reveal all remaining answers?',
    '答对 {score} / {total}': '{score} / {total} Correct',
    '答案：{answer}': 'Answer: {answer}',
    '填写缺失词，再点击测试。同一词的所有位置一起恢复。点击遮罩可定位输入框。':
        'Fill in the missing words, then Test. All occurrences regrow together. Click a mask to focus its input.',
    '没有找到适合出题的词语。可返回编辑器选择更长的正文。':
        'No suitable words found. Return to the editor and choose a longer article.',
    '当前没有文章，请先抓取或新建文章。': 'No current article. Extract or create an article first.',
    '请等待当前抓取完成后再开始文本再生。': 'Wait for the current extraction to finish before starting a challenge.',
    '已导出：{name}': 'Exported: {name}',
    '请先输入网页地址。': 'Enter a web page URL first.',
    '网址中不能包含空格或换行。': 'URLs cannot contain spaces or line breaks.',
    '只支持 http:// 和 https:// 网页地址。': 'Only http:// and https:// URLs are supported.',
    '请输入完整的网址，不要在网址中附带账号密码。': 'Enter a complete URL without a username or password.',
    '网址格式不正确，请检查域名和端口。': 'Invalid URL. Check the domain and port.',
    '网站拒绝访问（HTTP {code}），可能需要登录或人机验证。': 'Access denied (HTTP {code}). Login or verification may be required.',
    '网站暂时限制访问频率，请稍后再试。': 'The site is rate limiting requests. Try again later.',
    '该地址返回的不是 HTML 网页。请使用文章页面的网址。': 'This URL does not return HTML. Use an article page URL.',
    '网页超过 8 MB，请换用该文章的简洁版页面。': 'Page exceeds 8 MB. Try a simpler version of the article.',
    '网页下载耗时过长，请稍后重试。': 'Download took too long. Try again later.',
    '网页重定向次数过多，请检查网址。': 'Too many redirects. Check the URL.',
    '网站的 HTTPS 证书验证失败，请检查网址和电脑时间。': 'HTTPS certificate verification failed. Check the URL and system clock.',
    '连接或读取网页超时，请稍后重试。': 'Connection or read timeout. Try again later.',
    '网页访问失败（HTTP {code}）。': 'Page request failed (HTTP {code}).',
    '无法连接网站，请检查网络、网址或系统代理设置。': 'Cannot connect. Check the network, URL, or proxy settings.',
    '网站返回了访问验证页面，无法取得正文。': 'The site returned a verification page instead of the article.',
    '没有找到可用正文。请确认这是文章详情页；需要登录、验证码或 JavaScript 动态加载的页面可能无法直接提取。':
        'No article text found. Use an article detail page; login, verification, or JavaScript pages may not be extractable.',
    '查找内容不能为空。': 'Find text cannot be empty.',
    '替换内容必须是文本。': 'Replacement must be text.',
    '规则范围必须是 both、title 或 body。': 'Rule scope must be both, title, or body.',
    'case_sensitive 必须为 true 或 false。': 'case_sensitive must be true or false.',
    '预览后文章已发生变化，请重新预览。': 'An article changed after the preview. Preview again.',
    '替换后有文章被再次编辑或删除。为保留这些修改，无法直接撤销；可查看原始内容或先恢复替换后的文字。':
        'An article was edited or deleted after replacement. Undo is blocked to preserve these changes. View the original content or restore the replaced text first.',
}
HELP_ZH = ('1. 输入文章详情页网址，点击「提取正文」。\n2. 标题和正文可直接编辑，修改会自动保存在本地。\n'
           '3.「批量替换」支持多条规则、当前/全部文稿及规则导入导出。\n4. 可导出 TXT、Markdown 或 JSON。\n\n'
           '采集原文会单独保留，可通过「查看原文」复制。\n普通网页通常可以提取；需登录、验证码或动态加载的网站可能无法直接抓取。\n\n数据目录：\n')
EN[HELP_ZH] = ('1. Enter an article URL and click Extract.\n2. Edit the title and body; changes save automatically.\n'
               '3. Batch Replace supports multiple rules, current/all articles and rule import/export.\n'
               '4. Export TXT, Markdown or JSON.\n\nOriginal text is kept separately under View Original.\n'
               'Login, verification or JavaScript pages may not be extractable.\n\nData directory:\n')
EN.update({
    '填写缺失词，再点击测试。同一词的所有位置一起恢复。遮罩统一为 *****。':
        'Fill in the missing words, then Test. All occurrences restore together. Every mask is *****.',
    '自主恢复：{score} / {total}': 'Player Recovery: {score} / {total}',
    '已揭露：{count}': 'Revealed: {count}',
    '文本完整度：{percent}%': 'Document Restoration: {percent}%',
    '模式 3 · 扭曲再生': 'Mode 3 · Twisted Regrowth',
    '模式 3': 'Mode 3', '扭曲再生': 'Twisted Regrowth',
    '原文': 'Original', '当前代': 'Current Generation',
    '第 {number} 代': 'Generation {number}',
    '第 {number} 代完成': 'Generation {number} Complete',
    '自定义替换 / 随机候选': 'Custom Replacement / Random Suggestions',
    '自定义替换': 'Custom Replacement', '随机候选': 'Random Suggestions',
    '再生': 'Regrow', '下一代': 'Next Generation',
    '扭曲再生完成': 'Twisted Regrowth Complete',
    '原始文本': 'Original Text', '最终形态': 'Final Outcome',
    '最终变异': 'Final Mutation', '再次扭曲': 'New Mutation',
    '代数：{count}': 'Generations: {count}',
    '修改词数：{count}': 'Words Mutated: {count}',
    '修改词数': 'Words Mutated', '恢复词数': 'Words Restored',
    '扭曲度：{value}%': 'Distortion: {value}%',
    '可读性：{value}%': 'Coherence: {value}%',
    '再生评分：{value}%': 'Regrowth Score: {value}%',
    '输入新词，或从下拉列表选择候选。留空保留原词；重复词会一起替换。共 3 代。':
        'Type a word or choose from the dropdown. Blank keeps the original; repeats change together. Three generations.',
    '本代没有合适的目标词，可保留正文继续下一代。':
        'No suitable targets in this generation. Regrow to continue with the unchanged text.',
    '替换内容须为单个英文词或不超过 12 字的中文词语，不能包含空格、数字或符号。':
        'Use one English word or a Chinese phrase up to 12 characters, without spaces, numbers or symbols.',
    '本代已完成，请进入下一代或再次扭曲。': 'This generation is complete. Continue to the next generation or start a new mutation.',
    '只能替换本代选中的目标词。': 'Only selected targets in this generation can be replaced.',
    '请先完成本代；最多进行 3 代。': 'Complete this generation first. A session has at most three generations.',
    '无法再生': 'Cannot Regrow',
    '评分是确定性文本规则的估计，不代表语义或语法质量。':
        'Scores are deterministic text heuristics, not semantic or grammar judgments.',
    '修改词数按各代实际替换的出现次数累计。': 'Words mutated counts changed occurrences across all generations.',
    '查看历史': 'View History',
})
EN.update({
    '生长方向': 'Growth Direction', '自然': 'Nature', '科技': 'Technology',
    '人文': 'Human', '超现实': 'Surreal', '恢复': 'Restoration',
    '再生回来': 'Regrow Back', '选择要恢复的词': 'Choose words to restore',
    '生长路径': 'Growth Path', '原始故事': 'Original Story', '最终故事': 'Final Story',
    '最终文本': 'Final Text', '重定向生长': 'Redirected Growth',
    '野性生长': 'Wild Growth', '碎片化生长': 'Fragmented Growth',
    '恢复词数：{count}': 'Words Restored: {count}',
    '选择这一代的生长方向': 'Choose how this generation will grow',
    '第 {number} / 3 代': 'Generation {number} / 3',
    '第 {number} 代：{direction}': 'Generation {number}: {direction}',
    '最终形态：{outcome}': 'Final Outcome: {outcome}',
    '请选择这一代的生长方向。': 'Choose a growth direction for this generation.',
    '只能恢复当前列表中选中的变异词。': 'Select mutations from the current restoration list.',
    '再生回来仅使用勾选项；生长方向使用自定义替换。': 'Regrow Back uses checked mutations; Growth Direction uses replacement words.',
    '先选生长方向，再填写或选择替换词。再生后点击下一代；共 3 代，结束时查看故事和最终形态。':
        'Choose a direction and replacements. Regrow, then Next Generation. After three generations, compare stories and see the outcome.',
    '勾选部分变异词，点击再生恢复到原词并消耗这一代。其他变异保留；选生长方向可继续修改。':
        'Select words and Regrow to restore their origins, using this generation. Other changes remain. Choose a direction to edit instead.',
    '本代已完成，点击下一代继续。': 'This generation is complete. Click Next Generation to continue.',
    '无': 'None', '本代修改：{changes}': 'Mutations applied: {changes}',
    '本代恢复：{changes}': 'Restores applied: {changes}',
    '当前没有可恢复的变异词。': 'There are no mutated words to restore yet.',
    '文本已明显接近原文，或多数变异位置已被恢复。': 'The text is close to its origin, or most mutated positions have been restored.',
    '文本沿玩家选择的方向形成了不同且仍可读的故事。': 'Your chosen direction has grown into a different, readable story.',
    '文本经历大幅变化，保留一定可读性并呈现意外组合。': 'Large changes have produced unexpected combinations while retaining some readability.',
    '文本变化后可读性明显下降，形成了碎片化的故事。': 'Reduced readability has formed a fragmented story.',
    'outcome_restoration': 'Restoration',
})
EN.update({
    '模式 4 · 重构再生': 'Mode 4 · Reframed Regrowth',
    '你想怎样重新讲述这个故事？': 'How do you want to reframe the story?',
    '纯重排': 'Pure Reframe', '编辑重构': 'Editorial Reframe',
    '只能改变碎片顺序，必须保留所有信息。': 'Reorder the fragments, but keep every piece.',
    '可以重新排列，并删除有限的信息碎片。': 'Reorder the fragments and remove a limited number of pieces.',
    '信息不需要改变，也可能因为重新排列而长成不同的故事。': 'Information can grow into a different story without changing its pieces.',
    '同样的信息，不同的排列，可以产生不同的故事。': 'Same information. Different arrangement. Different story.',
    '本轮目标': 'Reframe Goal', '本轮目标：{goal}': 'Reframe Goal: {goal}',
    '第 {number} / 3 轮': 'Round {number} / 3', '第 {number} 轮': 'Round {number}',
    '删除': 'Remove', 'fragment_restore': 'Restore', '已移除': 'Removed',
    '锁定重构': 'Lock Reframe', '下一轮': 'Next Round', '重新重构': 'New Reframe',
    '本轮原文': 'Original Section', '当前重构': 'Current Reframe',
    '信息碎片': 'Fragments', '来源': 'Source',
    '重构故事': 'Reframed Story', '重构完成': 'Reframing Complete',
    '玩法': 'Method', '处理轮数': 'Rounds', '移动碎片数': 'Fragments Moved',
    '删除碎片数': 'Fragments Removed', '处理段落数': 'Sections Reframed',
    '玩法：{method}': 'Method: {method}', '处理轮数：{count}': 'Rounds: {count}',
    '移动碎片数：{count}': 'Fragments Moved: {count}', '删除碎片数：{count}': 'Fragments Removed: {count}',
    '处理段落数：{count}': 'Sections Reframed: {count}',
    '重构结果': 'Reframing Outcome', '重构结果：{outcome}': 'Reframing Outcome: {outcome}',
    '接近原文': 'Close to Original', '上下文偏移': 'Context Shift',
    '选择性重构': 'Selective Reframe', '强重构': 'Strong Reframe',
    '来自原文第 {number} 段': 'From paragraph {number}',
    '需要保留至少 3 个信息碎片。': 'Keep at least 3 fragments.',
    '让这段内容听起来更积极。': 'Make the story sound more positive.',
    '让事件显得更有争议。': 'Make the event sound more controversial.',
    '改变这段内容最重要的重点。': 'Change what feels most important.',
    '让某个角色显得更需要负责。': 'Make someone seem more responsible.',
    '让结果听起来更严重。': 'Make the outcome sound more serious.',
    '创造一个仍然可读但最意外的版本。': 'Create the most unexpected readable version.',
    '选择碎片后上移或下移。锁定重构保存本轮；目标用于思考，不做语义评分。':
        'Select a fragment, then Move Up or Move Down. Lock Reframe saves this round. Goals guide reflection; there is no semantic grading.',
    '纯重排：保留全部碎片，只改变顺序。': 'Pure Reframe: keep every fragment; only change the order.',
    '本轮最多删除 {limit} 个，已移除 {removed} 个；至少保留 {minimum} 个。锁定前可恢复。':
        'Remove up to {limit} this round; {removed} removed. Keep at least {minimum}. Restore before locking.',
    '本轮最多删除 {count} 个碎片。': 'Remove at most {count} fragments this round.',
    '本轮已锁定，点击下一轮继续。': 'This round is locked. Click Next Round to continue.',
    '本轮已锁定，请进入下一轮。': 'This round is locked. Continue to the next round.',
    '请先锁定本轮；每局共 3 轮。': 'Lock this round first. Each session has three rounds.',
    '请选择当前列表中的信息碎片。': 'Select a fragment in the current list.',
    '请选择已移除的信息碎片。': 'Select a removed fragment.',
    '纯重排必须保留所有信息碎片。': 'Pure Reframe must keep every fragment.',
    '只能重排原始碎片，不能新增、复制或丢失碎片。': 'Use only the source fragments, without additions, duplicates or missing pieces.',
    '请先选择纯重排或编辑重构。': 'Choose Pure Reframe or Editorial Reframe first.',
    '正文太短或没有适合重构的片段。': 'The text is too short or has no suitable sections to reframe.',
    '无法重构': 'Cannot Reframe', '已移除：{fragments}': 'Removed: {fragments}',
})
EN.update({
    '先种下你的词，再看看它会长成什么。': 'Plant your words first. Discover what they grow into.',
    '文章已隐藏': 'Article Hidden',
    '输入一个人物': 'Enter a person', '输入一个动物': 'Enter an animal',
    '输入一个动作': 'Enter an action', '输入一个地方': 'Enter a place',
    '输入一个奇怪的物品': 'Enter a strange object', '输入一个团体': 'Enter a group',
    '输入一种情绪或描述': 'Enter an emotion or description',
    '🎲 疯狂建议': '🎲 Wild Suggestion', '🌱 开始再生': '🌱 REGROW',
    '正在生长……': 'Growing...', '看看你创造了什么。': 'See what you created.',
    '你的再生故事': 'Your Regrowth', '继续生长': 'Continue Growing',
    '种子变异 · 第 0 代': 'Seed Mutation · Generation 0',
    '本次生长 +1 · 已再生故事：{count}': 'Growth +1 · Stories Regrown: {count}',
    '请填写每一项，使用 1–100 字的词或短语。': 'Fill every field with a word or phrase of 1–100 characters.',
    '请先完成盲填并揭晓故事。': 'Complete the blind inputs and reveal the story first.',
    '盲填位置无效，请重新开始。': 'Invalid blind input locations. Start a new session.',
    '这颗种子太短，换一篇文章再来种词吧。': 'This seed is too short. Try planting words in another article.',
})
EN.update({
    '密码破译': 'Cipher Challenge',
    '请先导入或填写文章正文，再开始密码破译。':
        'Import or write an article before starting the cipher challenge.',
    '当前正文没有 A–Z 英文字母，无法使用字母密码。请导入含英文字母的文章。':
        'This article has no A–Z letters. Import an article containing English letters to use this cipher.',
    '重新加密全文': 'Encrypt Article Again',
    '第 {number} 题 · 全文密文（{count} 字符）':
        'Puzzle {number} · Encrypted article ({count} characters)',
    '第 {number} 题 · 已还原全文（{count} 字符）':
        'Puzzle {number} · Restored article ({count} characters)',
    '破解成功！奖励 {reward} 币，全文已还原。规律：×{m}＋{b}。':
        'Solved! +{reward} coins. Full article restored. Rule: ×{m} +{b}.',
    '已加密全文并随机替换密文字母。大小写、中文、标点和段落保留。':
        'Full article encrypted with random cipher substitutions. Case, other characters and paragraphs are preserved.',
    '独立解密': 'Solo Decode', '指挥模式': 'Command Mode',
    'A=1，B=2，…，Z=26。先乘再加，超过 26 循环回 A；例如 A ×1＋1 → B。\n乘数 1–2，加数 0–3。密文再随机替换三种字母；按下方替换关系辨认，再填写规律。':
        'A=1, B=2, …, Z=26. Multiply, then add; wrap after 26. Example: A ×1 +1 → B.\nMultiplier 1–2, addend 0–3. Three cipher letters change again. Undo the shown substitutions to find the rule.',
    '规律：字母编号': 'Rule: letter number',
    '验证规律': 'Check Rule', '随机下一题': 'Next Random Puzzle',
    '行动 · 1 币': 'Act · 1 coin', '解雇 · 5 币': 'Dismiss · 5 coins',
    '招募 · 5 币': 'Recruit · 5 coins',
    '全员行动 · {cost} 币': 'All Act · {cost} coins',
    '提示是随机猜测，可能出现 +4、+5。满编五人一起行动时，一定包含正确乘数和加数。\n正确数字可能分属两人；单人行动或队伍不足五人时不保证正确数字。':
        'Random guesses may include +4 or +5. All five acting together guarantee both correct values.\nThe values may come from different robots. Single actions or smaller teams have no guarantee.',
    '答对 +10 币；自己答题免费。金币与队伍自动保存。':
        'Solve: +10 coins. Your guesses are free. Coins and crew save automatically.',
    '密码进度保存失败': 'Could Not Save Cipher Progress',
    '无法打开密码进度': 'Could Not Open Cipher Progress',
    '操作未保存，金币和队伍保持原状，请重试。':
        'Action not saved. Coins and crew are unchanged. Please retry.',
    '请在两个框中填写整数：乘数 1–2，加数 0–3。':
        'Enter two whole numbers: multiplier 1–2, addend 0–3.',
    '乘数只能填 1 或 2，加数只能填 0、1、2、3。':
        'Multiplier must be 1 or 2; addend must be 0, 1, 2 or 3.',
    '破解成功！奖励 {reward} 币。原文：{text}；规律：×{m}＋{b}。':
        'Solved! Reward: {reward} coins. Original: {text}; rule: ×{m} +{b}.',
    '规律不匹配，请结合密文替换关系再试。答错不扣币。':
        'Rule does not match. Use the cipher substitutions and try again. Wrong guesses cost no coins.',
    '已派出 {count} 名机器人，消耗 {cost} 币。请比较提示后填写规律。':
        'Dispatched {count} robots for {cost} coins. Compare their hints and enter a rule.',
    '已支付 5 币遣散费，该席位现在可以招募。':
        'Paid 5 coins in severance. You can recruit into this seat.',
    '已支付 5 币招募费，新机器人加入队伍。':
        'Paid 5 coins to recruit a new robot.',
    '金币：{coins}  ·  已破解：{wins} 题': 'Coins: {coins}  ·  Solved: {wins}',
    '第 {number} 题 · 加密文本': 'Puzzle {number} · Ciphertext',
    '密文二次替换（原密文 → 显示字母）：{pairs}': 'Cipher substitutions (before → displayed): {pairs}',
    '机器人 {number}': 'Robot {number}', '等待指令': 'Awaiting orders',
    '空席位 {number}': 'Empty seat {number}',
    '机器人队伍：{count} / 5 · 选择一个席位后操作':
        'Robot crew: {count} / 5 · Select a seat to give an order',
    '队员 / 席位': 'Robot / Seat', '本题最新猜测': 'Latest guess for this puzzle',
    '累计行动': 'Total actions',
    '无效的密码模式。': 'Invalid cipher mode.',
    '金币不足，请先自己解题赚币。': 'Not enough coins. Solve a puzzle yourself to earn more.',
    '无效的机器人席位。': 'Invalid robot seat.',
    '请先切换到指挥模式。': 'Switch to Command Mode first.',
    '本题已破解，请先生成下一题。': 'This puzzle is solved. Generate the next puzzle first.',
    '该席位没有机器人。': 'There is no robot in this seat.',
    '没有在队机器人，请先招募。': 'Your crew is empty. Recruit a robot first.',
    '请先解雇该席位的机器人。': 'Dismiss the robot in this seat first.',
})
STRINGS = {'zh': {key: key for key in EN}, 'en': EN}
STRINGS['zh']['outcome_restoration'] = '恢复'
STRINGS['zh']['fragment_restore'] = '恢复'


def t(key, language='zh', **values):
    template = STRINGS.get(language, STRINGS['zh']).get(key, key)
    return template.format(**values) if values else template


def translate(text, language='zh', source='zh'):
    """Translate known UI messages, including formatted error/status text."""
    for key, template in STRINGS.get(source, STRINGS['zh']).items():
        if text == template:
            return t(key, language)
        names = re.findall(r'\{(\w+)\}', template)
        if names:
            pattern = re.escape(template)
            for name in names:
                pattern = pattern.replace(re.escape('{' + name + '}'), '(?P<' + name + '>.*?)')
            match = re.fullmatch(pattern, text, re.DOTALL)
            if match:
                return t(key, language, **match.groupdict())
    return text


def refresh_widgets(widget, language, source):
    """Refresh only widget chrome; never translate Text, Entry, or article rows."""
    import tkinter as tk
    from tkinter import ttk
    if isinstance(widget, (tk.Tk, tk.Toplevel)):
        widget.title(translate(widget.title(), language, source))
    if isinstance(widget, (tk.Label, tk.Button, tk.Checkbutton)) and not widget.cget('textvariable'):
        widget.configure(text=translate(str(widget.cget('text')), language, source))
    if isinstance(widget, tk.Menu):
        for index in range((widget.index('end') or 0) + 1):
            if widget.type(index) in ('command', 'cascade', 'checkbutton', 'radiobutton'):
                widget.entryconfigure(index, label=translate(widget.entrycget(index, 'label'), language, source))
    if isinstance(widget, ttk.Treeview):
        for column in widget['columns']:
            widget.heading(column, text=translate(widget.heading(column, 'text'), language, source))
    for child in widget.winfo_children():
        refresh_widgets(child, language, source)

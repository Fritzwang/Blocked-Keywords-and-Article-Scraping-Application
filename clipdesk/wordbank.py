"""Small offline suggestion banks, separated by language and rough word class."""
BANKS = {
    'en': {
        'noun': tuple('forest machine kingdom ocean toaster dragon office moon engine garden banana river city mountain library robot cloud castle mirror island wedding fire planet museum lantern village flower'.split()),
        'verb': tuple('returned recovered celebrated danced whispered wandered survived discovered shimmered floated dreamed listened waited vanished grew changed smiled travelled'.split()),
        'adjective': tuple('quiet strange golden bright ancient curious gentle wild tiny brave silent restless purple patient silver distant warm mysterious'.split()),
        'adverb': tuple('slowly quietly suddenly gently brightly curiously wildly calmly boldly softly patiently strangely quickly carefully silently happily'.split()),
    },
    'zh': {
        'noun': tuple('森林 机器 王国 海洋 烤箱 巨龙 办公室 月亮 引擎 花园 香蕉 河流 城市 高山 图书馆 机器人 云朵 城堡 镜子 岛屿 婚礼 火焰 星球 博物馆 灯笼 村庄 花朵'.split()),
        'verb': tuple('返回 恢复 庆祝 舞蹈 低语 漫游 存活 发现 闪耀 漂浮 梦想 倾听 等待 消失 生长 改变 微笑 旅行'.split()),
        'adjective': tuple('安静 奇妙 金色 明亮 古老 好奇 温柔 狂野 微小 勇敢 寂静 不安 紫色 耐心 银色 遥远 温暖 神秘'.split()),
        'adverb': tuple('慢慢 悄悄 突然 轻轻 渐渐 默默 静静 缓缓 迅速 认真 开心 自由 轻快 悠悠 稳稳 匆匆'.split()),
    },
}

DIRECTION_BANKS = {
    'en': {
        'nature': tuple('forest river seed flower rain root animal garden ocean mountain meadow leaf sunlight blossom breeze willow moss island bird waterfall'.split()),
        'technology': tuple('machine robot network engine system digital device circuit sensor server software processor cable signal laser satellite battery turbine algorithm factory'.split()),
        'surreal': tuple('dragon moon dream ghost toaster kingdom portal phantom rainbow wizard comet illusion labyrinth mermaid phoenix shadow cloud mirror starlight castle'.split()),
    },
    'zh': {
        'nature': tuple('森林 河流 种子 花朵 雨水 树根 动物 花园 海洋 高山 草地 叶子 阳光 花瓣 微风 柳树 青苔 岛屿 飞鸟 瀑布'.split()),
        'technology': tuple('机器 机器人 网络 引擎 系统 数码 设备 电路 传感器 服务器 软件 处理器 电缆 信号 激光 卫星 电池 涡轮 算法 工厂'.split()),
        'surreal': tuple('巨龙 月亮 梦境 幽灵 烤箱 王国 传送门 幻影 彩虹 巫师 彗星 幻觉 迷宫 人鱼 凤凰 影子 云朵 镜子 星光 城堡'.split()),
    },
}

"""一次性生成自制图标及依赖许可清单，不是应用运行依赖。"""
import importlib.metadata as metadata
from pathlib import Path
import sys
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
assets = ROOT / "assets"
assets.mkdir(exist_ok=True)
canvas = Image.new("RGBA", (256, 256), (0, 0, 0, 0))
draw = ImageDraw.Draw(canvas)
draw.rounded_rectangle((6, 6, 250, 250), radius=55, fill="#2563eb")
draw.rounded_rectangle((65, 44, 191, 212), radius=13, fill="white")
draw.rectangle((91, 82, 151, 93), fill="#2563eb")
for y, end in ((116, 164), (141, 164), (166, 143)):
    draw.rounded_rectangle((91, y, end, y + 7), radius=3, fill="#8aacfa")
canvas.save(assets / "app.ico", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])

names = ["requests", "beautifulsoup4", "soupsieve", "typing_extensions", "trafilatura", "lxml", "lxml_html_clean", "certifi", "charset_normalizer", "idna", "urllib3", "courlan", "htmldate", "justext", "dateparser", "python-dateutil", "pytz", "regex", "tzlocal", "tzdata", "tld", "babel", "six", "pyinstaller"]
sections = ["网页摘录 — 第三方许可说明\n\n本程序包含下列开源组件。以下是构建环境中随依赖提供的许可文本。\n图标为本项目绘制。"]
versions = []
for name in names:
    try:
        dist = metadata.distribution(name)
    except metadata.PackageNotFoundError:
        continue
    versions.append(f"{dist.metadata['Name']}=={dist.version}")
    label = f"{name} {dist.version}"
    details = [label, dist.metadata.get("Home-page", ""), dist.metadata.get("License-Expression", "") or dist.metadata.get("License", "")]
    for file in dist.files or []:
        if any(word in file.name.lower() for word in ("license", "copying", "copyright", "notice")) and file.suffix.lower() not in (".py", ".pyc", ".html"):
            path = Path(dist.locate_file(file))
            if path.is_file() and path.stat().st_size < 500_000:
                details.extend([str(file), path.read_text(encoding="utf-8", errors="replace")])
    sections.append("\n".join(details))
for path in [Path(sys.base_prefix) / "LICENSE.txt", Path(sys.base_prefix) / "tcl" / "tcl8.6" / "license.terms", Path(sys.base_prefix) / "tcl" / "tk8.6" / "license.terms"]:
    if path.exists():
        sections.append(str(path.name) + "\n" + path.read_text(encoding="utf-8", errors="replace"))
(ROOT / "第三方许可说明.txt").write_text("\n\n" + ("\n\n" + "=" * 72 + "\n\n").join(sections), encoding="utf-8")
(ROOT / "requirements-lock.txt").write_text("\n".join(versions) + "\n", encoding="utf-8")
# Windows PowerShell 5.1 需要 BOM 来正确读取中文构建参数。
script = ROOT / "build.ps1"
script.write_text(script.read_text(encoding="utf-8-sig"), encoding="utf-8-sig")
print("Icon, dependency versions and license notices generated.")

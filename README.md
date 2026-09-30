# hello-llm-tts 🎧

《[Happy-LLM：从零开始构建大语言模型](https://github.com/datawhalechina/happy-llm)》（Datawhale）的
**网页 TTS 朗读版**。把原书 `docs/` 目录的 Markdown 全自动转换成对浏览器语音合成（Read Aloud /
Web Speech API）友好的静态站点——像听播客一样"读"完一本书，公式和代码随时回到文字对照。

> **在线阅读**：启用 GitHub Pages（Settings → Pages → Deploy from branch → `main` / `/ (root)`）后
> 访问 `https://nongsia.github.io/hello-llm-tts/`。也可直接双击 `index.html` 本地打开，无需服务器。

## 功能

- **逐句朗读 + 高亮跟随**：基于浏览器原生 Web Speech API，正在朗读的句子自动高亮并滚动跟随，
  支持 上一句 / 下一句 / 回到开头 / 空格暂停。
- **语速与音色**：0.6×–2.2× 语速，音色下拉框列出系统全部语音（推荐 Edge 的中文在线自然音色，
  如 Xiaoxiao / Yunxi）。
- **代码块自动跳过**：所有代码折叠为可展开面板，朗读自动跳过，阅读时点击即可展开看全部代码。
- **公式口语化**：LaTeX 公式转为双语——页面显示 Unicode 符号版（QKᵀ、√dₖ），朗读播口语版
  （"Q K 的转置"、"d 下标 k 的平方根"；α→阿尔法、Σ→求和、\frac{a}{b}→"b 分之 a"）。
- **表格线性化**：表格保留外观，朗读时按"表头：…。第 1 行：某列 为 某值…"通顺读出。
- **图片保留**：原书配图全部保留（外链 raw.githubusercontent），朗读时只读图注。
- **进度记忆 / 连播**：每页朗读位置本地记忆，关闭浏览器再打开能继续；勾选"连播"读完自动进下一章。
- **深浅色主题**：自动跟随系统，可手动切换；移动端自适应。

全书 12 个页面共约 **380 分钟**朗读量（1× 语速估算）。

## 目录结构

```
hello-llm-tts/
├── build.py            # 构建脚本：happy-llm/docs/*.md → TTS 友好 HTML
├── templates/          # 页面模板 + 样式 + 朗读器脚本（站点的源码）
│   ├── page.html
│   ├── index.html
│   ├── style.css
│   └── app.js
├── index.html          # ↓ 以下为构建产物（已提交，可直接部署 GitHub Pages）
├── preface.html / setup.html / chapter1..8.html / ...
└── assets/             # style.css + app.js
```

## 重新构建

上游 `happy-llm` 更新后可一键重新生成：

```bash
pip install -r requirements.txt
python build.py --docs /path/to/happy-llm/docs   # 默认自动探测本仓库的上级 docs/
```

## 转换规则（为 TTS 做了什么）

| 原文元素 | 视觉处理 | 朗读处理 |
|---|---|---|
| 代码块 | 折叠面板，可展开 | 自动跳过 |
| `$$…$$` / `$…$` | Unicode 符号化显示 | 转口语（希腊字母、分数、上下标、求和积分等） |
| Markdown 表格 | 保留表格 | 行列线性化成自然语句 |
| `<div align=center>` 配图 | 保留图片 + 图注 | 只读图注 |
| 链接 | 外链保留、站内 .md 链接改写为新页面 | 只读链接文字 |
| `<bos>`、`<\|im_start\|>` 等代码记号 | 转义显示 | 按普通文本朗读 |

## 已知限制

- 朗读效果取决于系统 TTS 引擎：Windows 推荐 Edge（在线自然音色）；Chrome 用系统语音包。
- 公式口语化是"可听懂"优先，不是精确的数学朗读，严谨表述请回到文字对照。
- 原书第六章 6.4 节的配图在上游仓库中缺失，本站以占位文字标示。

## 版权与致谢

- 原书：[datawhalechina/happy-llm](https://github.com/datawhalechina/happy-llm) —— 感谢 Datawhale 开源社区。
- 原书及本项目均采用 **[CC BY-NC-SA 4.0](LICENSE)**（署名-非商业性使用-相同方式共享）协议，
  仅供学习交流，请勿商用。

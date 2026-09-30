#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Happy-LLM TTS 文档站构建脚本。

把 datawhalechina/happy-llm 的 docs/ 目录（docsify markdown）转换成
适合浏览器 TTS 朗读的静态站点：

  1. 代码块      → 默认折叠的 <details data-no-tts>，朗读自动跳过
  2. LaTeX 公式  → 视觉版（Unicode 符号）+ 口语版（data-tts，朗读用）
  3. 表格        → 保留外观，行/列线性化成一句通顺的中文放入 data-tts
  4. 图片        → 保留外链图片，仅朗读图注文字
  5. 超链接      → 只读链接文字，站内 .md 链接自动改写为新页面
  6. 前端朗读器  → Web Speech API 逐句朗读 + 高亮 + 语速/音色/记忆进度

用法：
    python build.py [--docs 路径] [--out 路径]
默认从本仓库的上级目录找 docs/，输出到本仓库根目录（可直接开 GitHub Pages）。
"""
import argparse
import html
import pathlib
import re
import shutil
import sys

import markdown

REPO = pathlib.Path(__file__).resolve().parent
RAW_BASE = "https://raw.githubusercontent.com/datawhalechina/happy-llm/main/docs/"
ORIGIN_URL = "https://github.com/datawhalechina/happy-llm"

# ---------------------------------------------------------------- 页面清单

PAGES = [
    dict(src="前言.md", out="preface", title="前言", group="开始之前"),
    dict(src="学习与环境准备.md", out="setup", title="学习与环境准备", group="开始之前"),
    dict(src="chapter1/第一章 NLP基础概念.md", out="chapter1", title="第一章 NLP 基础概念", group="正文"),
    dict(src="chapter2/第二章 Transformer架构.md", out="chapter2", title="第二章 Transformer 架构", group="正文"),
    dict(src="chapter3/第三章 预训练语言模型.md", out="chapter3", title="第三章 预训练语言模型", group="正文"),
    dict(src="chapter4/第四章 大语言模型.md", out="chapter4", title="第四章 大语言模型", group="正文"),
    dict(src="chapter5/第五章 动手搭建大模型.md", out="chapter5", title="第五章 动手搭建大模型", group="正文"),
    dict(src="chapter6/第六章 大模型训练流程实践.md", out="chapter6", title="第六章 大模型训练流程实践", group="正文"),
    dict(src="chapter7/第七章 大模型应用.md", out="chapter7", title="第七章 大模型应用", group="正文"),
    dict(src="chapter8/第八章 大模型强化学习.md", out="chapter8", title="第八章 大模型强化学习", group="正文"),
    dict(src="chapter6/readme.md", out="chapter6-notes", title="第六章 实践说明", group="附录"),
    dict(src="chapter6/6.4[WIP] 偏好对齐.md", out="chapter6-alignment", title="第六章 偏好对齐（WIP）", group="附录"),
]

MD_LINK_MAP = {
    "前言.md": "preface.html",
    "学习与环境准备.md": "setup.html",
    "第一章 NLP基础概念.md": "chapter1.html",
    "第二章 Transformer架构.md": "chapter2.html",
    "第三章 预训练语言模型.md": "chapter3.html",
    "第四章 大语言模型.md": "chapter4.html",
    "第五章 动手搭建大模型.md": "chapter5.html",
    "第六章 大模型训练流程实践.md": "chapter6.html",
    "第七章 大模型应用.md": "chapter7.html",
    "第八章 大模型强化学习.md": "chapter8.html",
    "readme.md": "chapter6-notes.html",
    "README.md": "index.html",
    "6.4[WIP] 偏好对齐.md": "chapter6-alignment.html",
}

LANG_CN = {
    "python": "Python 代码", "python3": "Python 代码", "json": "JSON 示例",
    "bash": "Shell 脚本", "sh": "Shell 脚本", "shell": "Shell 脚本",
    "yaml": "YAML 配置", "yml": "YAML 配置", "text": "文本", "txt": "文本",
    "markdown": "Markdown", "diff": "差异对比", "cfg": "配置", "ini": "配置",
}

# ---------------------------------------------------------------- LaTeX 处理

GREEK_VIS = {
    "alpha": "α", "beta": "β", "gamma": "γ", "delta": "δ", "epsilon": "ε",
    "varepsilon": "ε", "zeta": "ζ", "eta": "η", "theta": "θ", "iota": "ι",
    "kappa": "κ", "lambda": "λ", "mu": "μ", "nu": "ν", "xi": "ξ", "pi": "π",
    "rho": "ρ", "sigma": "σ", "tau": "τ", "upsilon": "υ", "phi": "φ",
    "varphi": "φ", "chi": "χ", "psi": "ψ", "omega": "ω", "Gamma": "Γ",
    "Delta": "Δ", "Theta": "Θ", "Lambda": "Λ", "Xi": "Ξ", "Pi": "Π",
    "Sigma": "Σ", "Phi": "Φ", "Psi": "Ψ", "Omega": "Ω",
}
GREEK_SPOKEN = {
    "alpha": "阿尔法", "beta": "贝塔", "gamma": "伽马", "delta": "德尔塔",
    "epsilon": "艾普西隆", "varepsilon": "艾普西隆", "zeta": "泽塔",
    "eta": "伊塔", "theta": "西塔", "iota": "约塔", "kappa": "卡帕",
    "lambda": "拉姆达", "mu": "缪", "nu": "纽", "xi": "克西", "pi": "派",
    "rho": "柔", "sigma": "西格玛", "tau": "陶", "upsilon": "宇普西隆",
    "phi": "斐", "varphi": "斐", "chi": "卡", "psi": "普西", "omega": "欧米伽",
    "Gamma": "大写伽马", "Delta": "大写德尔塔", "Theta": "大写西塔",
    "Lambda": "大写拉姆达", "Xi": "大写克西", "Pi": "大写派",
    "Sigma": "大写西格玛", "Phi": "大写斐", "Psi": "大写普西", "Omega": "大写欧米伽",
}
SYM_VIS = {
    "times": "×", "cdot": "·", "div": "÷", "pm": "±", "mp": "∓",
    "leq": "≤", "le": "≤", "geq": "≥", "ge": "≥", "neq": "≠", "ne": "≠",
    "approx": "≈", "sim": "∼", "simeq": "≃", "propto": "∝",
    "rightarrow": "→", "to": "→", "longrightarrow": "⟶",
    "Rightarrow": "⇒", "leftarrow": "←", "Leftarrow": "⇐",
    "leftrightarrow": "↔", "Leftrightarrow": "⇔", "mapsto": "↦",
    "infty": "∞", "partial": "∂", "nabla": "∇", "sum": "Σ", "prod": "Π",
    "int": "∫", "iint": "∬", "iiint": "∭", "cup": "∪", "cap": "∩",
    "in": "∈", "notin": "∉", "subset": "⊂", "subseteq": "⊆",
    "forall": "∀", "exists": "∃", "ldots": "…", "cdots": "⋯", "dots": "…",
    "prime": "′", "circ": "∘", "bullet": "•", "star": "⋆", "oplus": "⊕",
    "otimes": "⊗", "perp": "⊥", "parallel": "∥", "angle": "∠",
    "top": "⊤", "bot": "⊥", "emptyset": "∅", "ni": "∋",
    "mid": "|", "vert": "|",
    "lt": "<", "gt": ">", "ll": "≪", "gg": "≫", "leqslant": "≤", "geqslant": "≥",
    "langle": "⟨", "rangle": "⟩", "lVert": "‖", "rVert": "‖",
}
SYM_SPOKEN = {
    "times": "乘", "cdot": "点乘", "div": "除以", "pm": "正负", "mp": "负正",
    "leq": "小于等于", "le": "小于等于", "geq": "大于等于", "ge": "大于等于",
    "neq": "不等于", "ne": "不等于", "approx": "约等于", "sim": "相似于",
    "simeq": "约等于", "propto": "正比于",
    "rightarrow": "得到", "to": "得到", "longrightarrow": "得到",
    "Rightarrow": "推出", "leftarrow": "回到", "Leftarrow": "可推出",
    "leftrightarrow": "与…互相转换", "Leftrightarrow": "等价于", "mapsto": "映射到",
    "infty": "无穷大", "partial": "偏导", "nabla": "梯度", "sum": "求和",
    "prod": "连乘", "int": "积分", "iint": "二重积分", "iiint": "三重积分",
    "cup": "并集", "cap": "交集", "in": "属于", "notin": "不属于",
    "subset": "包含于", "subseteq": "包含于", "forall": "对任意",
    "exists": "存在", "ldots": "等等", "cdots": "等等", "dots": "等等",
    "prime": "撇", "circ": "复合", "bullet": "点", "star": "星号",
    "oplus": "异或", "otimes": "张量积", "perp": "垂直", "parallel": "平行",
    "angle": "角", "top": "转置", "bot": "底符号", "emptyset": "空集",
    "mid": "，在…条件下，", "vert": "，在…条件下，",
    "lt": "小于", "gt": "大于", "ll": "远小于", "gg": "远大于",
    "leqslant": "小于等于", "geqslant": "大于等于",
}
KEEP_WORD = {"log", "ln", "exp", "sin", "cos", "tan", "max", "min", "arg",
             "softmax", "KL", "loss", "Reward", "Encoder", "Decoder"}
BB_MAP = {"R": "ℝ", "N": "ℕ", "Z": "ℤ", "Q": "ℚ", "C": "ℂ", "E": "𝔼", "P": "ℙ"}
BB_SPOKEN = {"R": "实数集", "N": "自然数集", "Z": "整数集", "Q": "有理数集",
             "C": "复数集", "E": "期望", "P": "概率"}
SUP_MAP = {"0": "⁰", "1": "¹", "2": "²", "3": "³", "4": "⁴", "5": "⁵",
           "6": "⁶", "7": "⁷", "8": "⁸", "9": "⁹", "+": "⁺", "-": "⁻",
           "n": "ⁿ", "i": "ⁱ", "k": "ᵏ", "T": "ᵀ", "t": "ᵗ", "p": "ᵖ"}
SUB_MAP = {"0": "₀", "1": "₁", "2": "₂", "3": "₃", "4": "₄", "5": "₅",
           "6": "₆", "7": "₇", "8": "₈", "9": "₉", "+": "₊", "-": "₋",
           "n": "ₙ", "i": "ᵢ", "j": "ⱼ", "k": "ₖ", "t": "ₜ", "e": "ₑ",
           "a": "ₐ", "o": "ₒ", "x": "ₓ", "v": "ᵥ"}

SPACING_CMDS = re.compile(
    r"\\left|\\right|\\!|\\,|\\;|\\:|\\ |\\quad|\\qquad|\\displaystyle|\\limits"
    r"|\\nolimits|\\nonumber|\\cr|\\hline|\\[Bb]igg?[lr]?[jt]?|\\label\{[^}]*\}"
    r"|\\tag\{[^}]*\}|\\begin\{[a-zA-Z*]+\}|\\end\{[a-zA-Z*]+\}")


def _clean_tex(s: str) -> str:
    s = " ".join(s.split())
    s = SPACING_CMDS.sub(" ", s)
    s = s.replace(r"\\", "；").replace("&", "，").replace("~", " ")
    return s


def _read_group(s: str, i: int):
    """读出位置 i 开始的一个 LaTeX 参数（{...} 或单个 token），返回 (内容, 新位置)。"""
    while i < len(s) and s[i] == " ":
        i += 1
    if i >= len(s):
        return "", i
    if s[i] == "{":
        depth, j = 0, i
        while j < len(s):
            if s[j] == "{":
                depth += 1
            elif s[j] == "}":
                depth -= 1
                if depth == 0:
                    return s[i + 1:j], j + 1
            j += 1
        return s[i + 1:], len(s)
    if s[i] == "\\":
        m = re.match(r"\\[a-zA-Z]+", s[i:])
        if m:
            return m.group(0), i + len(m.group(0))
        return s[i:i + 2], i + 2
    return s[i], i + 1


def _apply_supsub(text: str) -> str:
    def sup(m):
        g = m.group(1)
        if 0 < len(g) <= 4 and all(c in SUP_MAP for c in g):
            return "".join(SUP_MAP[c] for c in g)
        return m.group(0)

    def sub(m):
        g = m.group(1)
        if 0 < len(g) <= 4 and all(c in SUB_MAP for c in g):
            return "".join(SUB_MAP[c] for c in g)
        return m.group(0)

    text = re.sub(r"\^\{([^{}]*)\}", sup, text)
    text = re.sub(r"_\{([^{}]*)\}", sub, text)
    text = re.sub(r"\^(\w)", lambda m: SUP_MAP.get(m.group(1), "^" + m.group(1)), text)
    text = re.sub(r"_(\w)", lambda m: SUB_MAP.get(m.group(1), "_" + m.group(1)), text)
    return text


def latex_visual(tex: str) -> str:
    s = _clean_tex(tex)
    out, i = [], 0
    while i < len(s):
        c = s[i]
        if c == "\\":
            m = re.match(r"\\([a-zA-Z]+)", s[i:])
            if not m:  # \$ \% \{ 等转义
                if i + 1 < len(s):
                    out.append(s[i + 1])
                    i += 2
                else:
                    i += 1
                continue
            name = m.group(1)
            j = i + m.end()
            if name == "frac":
                a, j = _read_group(s, j)
                b, j = _read_group(s, j)
                av, bv = latex_visual(a), latex_visual(b)
                av = av if len(av) <= 3 else f"({av})"
                bv = bv if len(bv) <= 3 else f"({bv})"
                out.append(f"{av}/{bv}")
            elif name == "sqrt":
                a, j = _read_group(s, j)
                out.append(f"√({latex_visual(a)})")
            elif name in ("text", "mathrm", "mathbf", "mathit", "mathsf", "mathtt",
                          "mathcal", "boldsymbol", "operatorname", "mathfrak"):
                a, j = _read_group(s, j)
                inner = latex_visual(a)
                out.append(BB_MAP.get(a, inner) if name == "mathbb" else inner)
            elif name == "hat":
                a, j = _read_group(s, j)
                out.append(f"{latex_visual(a)}^")
            elif name == "bar":
                a, j = _read_group(s, j)
                out.append(f"{latex_visual(a)}‾")
            elif name in ("underset", "overset"):
                a, j = _read_group(s, j)
                b, j = _read_group(s, j)
                mark = "_" if name == "underset" else "^"
                out.append(f"{latex_visual(b)}{mark}{{{latex_visual(a)}}}")
            elif name in GREEK_VIS:
                out.append(GREEK_VIS[name])
            elif name in SYM_VIS:
                out.append(SYM_VIS[name])
            elif name in KEEP_WORD:
                out.append(name)
            else:
                out.append(name)
            i = j
        else:
            out.append(c)
            i += 1
    s = _apply_supsub("".join(out))
    s = s.replace("{", "").replace("}", "")
    s = re.sub(r"\s+", " ", s).strip()
    return s


def latex_speech(tex: str) -> str:
    s = _clean_tex(tex)
    out, i = [], 0
    while i < len(s):
        c = s[i]
        if c == "\\":
            m = re.match(r"\\([a-zA-Z]+)", s[i:])
            if not m:
                if i + 1 < len(s):
                    out.append(" " + s[i + 1] + " ")
                    i += 2
                else:
                    i += 1
                continue
            name = m.group(1)
            j = i + m.end()
            if name == "frac":
                a, j = _read_group(s, j)
                b, j = _read_group(s, j)
                sa, sb = latex_speech(a), latex_speech(b)
                if len(sa) <= 4 and len(sb) <= 4:
                    out.append(f" {sb}分之{sa} ")
                else:
                    out.append(f" {sa}，除以，{sb} ")
            elif name == "sqrt":
                a, j = _read_group(s, j)
                out.append(f" {latex_speech(a)}的平方根 ")
            elif name in ("text", "mathrm", "mathbf", "mathit", "mathsf", "mathtt",
                          "mathcal", "boldsymbol", "operatorname", "mathfrak"):
                a, j = _read_group(s, j)
                out.append(f" {a} ")
            elif name == "mathbb":
                a, j = _read_group(s, j)
                out.append(f" {BB_SPOKEN.get(a, a)} ")
            elif name == "hat":
                a, j = _read_group(s, j)
                av = latex_speech(a)
                prefix = "预测" if av.strip() in ("y", "ŷ") else "估计"
                out.append(f" {prefix}{av} ")
            elif name == "bar":
                a, j = _read_group(s, j)
                out.append(f" 平均的{latex_speech(a)} ")
            elif name in ("underset", "overset"):
                a, j = _read_group(s, j)
                b, j = _read_group(s, j)
                if name == "underset" and latex_speech(b).strip() in ("arg max", "argmax", "arg min", "argmin"):
                    out.append(f" 使{latex_speech(a)}{'最大' if 'max' in b else '最小'}的 ")
                else:
                    out.append(f" {latex_speech(b)}，{latex_speech(a)} ")
            elif name in GREEK_SPOKEN:
                out.append(f" {GREEK_SPOKEN[name]} ")
            elif name in SYM_SPOKEN:
                out.append(f" {SYM_SPOKEN[name]} ")
            elif name in KEEP_WORD:
                out.append(f" {name} ")
            else:
                out.append(f" {name} ")
            i = j
        else:
            out.append(c)
            i += 1
    s = "".join(out)
    # 上标 / 下标口语化
    def sup_spoken(m):
        g = m.group(1).strip()
        if g in ("T", "top", r"\top"):
            return " 的转置 "
        if g in ("*", r"\ast", r"\star"):
            return " 的星号上标 "
        if re.fullmatch(r"-?\d+", g):
            return f" 的{g.replace('-', '负')}次方 "
        return f" 的{latex_speech(g)}次方 "

    def sub_spoken(m):
        return f" 下标{latex_speech(m.group(1))} "

    s = re.sub(r"\^\{([^{}]*)\}", sup_spoken, s)
    s = re.sub(r"_\{([^{}]*)\}", sub_spoken, s)

    def single_sup(m):
        g = m.group(1)
        if g in ("T", "t"):
            return " 的转置 "
        return f" 的{g}次方 "

    s = re.sub(r"\^(\w)", single_sup, s)
    s = re.sub(r"_(\w)", lambda m: " 下标" + m.group(1) + " ", s)
    # 命令转成中文后下标与内容之间会有空格（如 \pi_\theta → _ 西塔）
    s = re.sub(r"_\s*([\u4e00-\u9fff]{1,6})", r" 下标\1 ", s)
    s = re.sub(r"_\s+(?=[(（\w])", " 下标 ", s)
    # 基础运算符
    s = re.sub(r"\s*=\s*", " 等于 ", s)
    s = re.sub(r"\s*\+\s*", " 加 ", s)
    s = re.sub(r"(?<=[\d\w\)\]])\s*-\s*(?=[\d\w\(])", " 减 ", s)
    s = re.sub(r"\*", " 乘 ", s)
    s = re.sub(r"\s*<\s*", " 小于 ", s)
    s = re.sub(r"\s*>\s*", " 大于 ", s)
    s = re.sub(r"(\d+(?:\.\d+)?)%", r"百分之\1", s)
    for ch in "{}|$":
        s = s.replace(ch, " ")
    s = re.sub(r"\s+", " ", s).strip()
    s = re.sub(r" ，", "，", s)
    return s

# ---------------------------------------------------------------- Markdown 预处理

CODE_RE = re.compile(r"(?ms)^[ \t]*```([\w+#.\-]*)[ \t]*\n(.*?)[ \t]*```[ \t]*$")
MATH_BLOCK_RE = re.compile(r"\$\$(.+?)\$\$", re.S)
MATH_INLINE_RE = re.compile(r"(?<!\$)\$([^\n$]+?)\$(?!\$)")
FIG_DIV_RE = re.compile(
    r"[ \t]*<div[^>]*align[^>]*>\s*(<img[^>]*>)(?:\s*<p[^>]*>(.*?)</p>)?\s*</div>",
    re.S)
MD_IMG_RE = re.compile(r"!\[([^\]]*)\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)\s]+)\)")

KNOWN_HTML = {"div", "p", "img", "br", "hr", "a", "b", "i", "em", "strong",
              "sup", "sub", "span", "figure", "figcaption", "details",
              "summary", "nav", "ul", "ol", "li", "pre", "code"}


def _fix_img_src(src: str, docs_dir: pathlib.Path, page_dir: str):
    """返回 (可用的 src, 是否本地确实存在)。"""
    if src.startswith(("http://", "https://", "//")):
        return src, True
    rel = src.lstrip("./")
    local = docs_dir / page_dir / rel if page_dir else docs_dir / rel
    if local.exists():
        if src.startswith(("images/", "chapter")):
            return RAW_BASE + rel, True
        if page_dir:
            return RAW_BASE + f"{page_dir}/{rel}", True
        return RAW_BASE + rel, True
    # docs 根下找一次（如 images/...）
    alt = docs_dir / rel
    if alt.exists():
        return RAW_BASE + rel, True
    return src, False


def render_figure(img_tag: str, caption: str, docs_dir: pathlib.Path, page_dir: str) -> str:
    m = re.search(r'src="([^"]+)"', img_tag)
    src = m.group(1) if m else ""
    src, exists = _fix_img_src(src, docs_dir, page_dir)
    cap = (caption or "").strip()
    cap_html = f"<figcaption>{html.escape(cap)}</figcaption>" if cap else ""
    if not exists:
        note = f"（原书图片缺失：{cap or src}）"
        return f'<figure class="figure figure-missing"><figcaption>{html.escape(note)}</figcaption></figure>'
    alt = html.escape(cap or "插图")
    return (f'<figure class="figure"><span class="fig-img" data-no-tts>'
            f'<img src="{html.escape(src)}" alt="{alt}" loading="lazy"></span>{cap_html}</figure>')


def render_codeblock(lang: str, code: str) -> str:
    lang = lang.lower()
    label = LANG_CN.get(lang, f"{lang} 代码" if lang else "代码")
    nline = code.count("\n") + 1
    body = html.escape(code.rstrip())
    return (f'<details class="codeblock" data-no-tts><summary>'
            f'<span class="lang">{html.escape(label)}</span>'
            f'<span class="meta">{nline} 行 · 朗读时自动跳过 · 点击展开</span></summary>'
            f'<pre><code>{body}</code></pre></details>')


def render_math(tex: str, display: bool) -> str:
    tex = " ".join(tex.split())
    vis = latex_visual(tex)
    spo = latex_speech(tex)
    spo = f"数学公式：{spo}" if display else spo
    tag = "div" if display else "span"
    cls = "formula f-display" if display else "formula"
    return (f'<{tag} class="{cls}" data-tts="{html.escape(spo, quote=True)}">'
            f'<code>{html.escape(vis)}</code></{tag}>')


def preprocess(md: str, docs_dir: pathlib.Path, page_dir: str) -> str:
    ctr = {"code": 0, "mb": 0, "mi": 0}
    code_html, math_html = {}, {}

    def sub_code(m):
        i = ctr["code"]; ctr["code"] += 1
        code_html[i] = render_codeblock(m.group(1), m.group(2))
        return f"\n\n§§CODE{i}§§\n\n"

    def sub_mb(m):
        i = ctr["mb"]; ctr["mb"] += 1
        math_html[("b", i)] = render_math(m.group(1), display=True)
        return f"\n\n§§MATHB{i}§§\n\n"

    def sub_mi(m):
        i = ctr["mi"]; ctr["mi"] += 1
        math_html[("i", i)] = render_math(m.group(1), display=False)
        return f"§§MATHI{i}§§"

    def sub_fig(m):
        return render_figure(m.group(1), m.group(2), docs_dir, page_dir)

    def sub_mdimg(m):
        alt = m.group(1).strip()
        cap = alt if alt and not alt.lower().startswith(("image", "img", "图片描述")) else ""
        return render_figure(f'<img src="{m.group(2)}">', cap, docs_dir, page_dir)

    def sub_link(m):
        text, url = m.group(1), m.group(2)
        if url.startswith(("http://", "https://", "#", "mailto:")):
            return m.group(0)
        from urllib.parse import unquote
        base = unquote(url.split("#")[0]).replace("\\", "/").split("/")[-1]
        if base.lower().endswith(".md"):
            target = MD_LINK_MAP.get(base) or MD_LINK_MAP.get(base.replace("README", "README"))
            if target:
                anchor = url.split("#", 1)
                suffix = f"#{anchor[1]}" if len(anchor) == 2 else ""
                return f"[{text}]({target}{suffix})"
        return text  # 代码文件等本地路径 → 纯文字，避免死链

    md = CODE_RE.sub(sub_code, md)
    md = MATH_BLOCK_RE.sub(sub_mb, md)
    md = MATH_INLINE_RE.sub(sub_mi, md)
    # 残留的非 HTML 尖括号标记（如 <bos>、<|im_start|>）转义，避免被解析器吞掉
    def esc_tag(m):
        name = m.group(1).lower()
        if name in KNOWN_HTML:
            return m.group(0)
        return m.group(0).replace("<", "&lt;").replace(">", "&gt;")
    md = re.sub(r"<([a-zA-Z][\w|.\-]*)[^>]*>", esc_tag, md)
    md = FIG_DIV_RE.sub(sub_fig, md)
    md = MD_IMG_RE.sub(sub_mdimg, md)
    md = LINK_RE.sub(sub_link, md)
    # 保存渲染结果供后处理替换
    preprocess.code_html = code_html
    preprocess.math_html = math_html
    return md

# ---------------------------------------------------------------- HTML 后处理

TABLE_RE = re.compile(r"<table>.*?</table>", re.S)
HEADING_RE = re.compile(r"<h([1-6])([^>]*)>(.*?)</h\1>", re.S)
PLACEHOLDER_P_RE = re.compile(r"<p>\s*§§(CODE|MATHB)(\d+)§§\s*</p>")
PLACEHOLDER_RE = re.compile(r"§§(CODE|MATHB|MATHI)(\d+)§§")

EMOJI_RE = re.compile(r"[\U0001F000-\U0001FAFF\u2190-\u21FF\u2600-\u27BF\u2B00-\u2BFF\uFE0F]")


def _strip_tags(s: str) -> str:
    s = re.sub(r'<span class="formula"[^>]*data-tts="([^"]*)"[^>]*>.*?</span>',
               lambda m: " " + m.group(1) + " ", s, flags=re.S)
    return html.unescape(re.sub(r"<[^>]+>", "", s))


def _cell_text(cell_html: str) -> str:
    t = _strip_tags(cell_html)
    t = EMOJI_RE.sub("", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t.replace('"', "")


def table_linearize(m: re.Match) -> str:
    t = m.group(0)
    rows_html = re.findall(r"<tr[^>]*>(.*?)</tr>", t, re.S)
    rows = []
    for r in rows_html:
        cells = []
        for cm in re.finditer(r"<t([dh])[^>]*>(.*?)</t\1>", r, re.S):
            cells.append(_cell_text(cm.group(2)))
        if cells:
            rows.append(cells)
    if not rows:
        return t
    ncol = max(len(r) for r in rows)
    header = rows[0] if "<thead" in t else None
    body = rows[1:] if header else rows
    parts = [f"表格，共{len(rows)}行{ncol}列。"]
    if header:
        parts.append("表头：" + "、".join(h for h in header if h) + "。")
    for i, row in enumerate(body, 1):
        segs = []
        for j, cell in enumerate(row):
            if not cell:
                continue
            col = header[j] if header and j < len(header) else f"第{j + 1}列"
            segs.append(f"{col}为{cell}")
        if segs:
            parts.append(f"第{i}行：" + "，".join(segs) + "。")
    spoken = " ".join(parts)
    return (f'<div class="table-wrap" data-tts="{html.escape(spoken, quote=True)}" data-no-read>'
            f"{t}</div>")


def postprocess(htm: str):
    code_html = preprocess.code_html
    math_html = preprocess.math_html

    def repl_p(m):
        kind, i = m.group(1), int(m.group(2))
        return code_html[i] if kind == "CODE" else math_html[("b", i)]

    def repl(m):
        kind, i = m.group(1), int(m.group(2))
        if kind == "CODE":
            return code_html[i]
        if kind == "MATHB":
            return math_html[("b", i)]
        return math_html[("i", i)]

    htm = PLACEHOLDER_P_RE.sub(repl_p, htm)
    htm = PLACEHOLDER_RE.sub(repl, htm)
    htm = TABLE_RE.sub(table_linearize, htm)

    toc, hno = [], [0]

    def heading(m):
        level, attrs, inner = int(m.group(1)), m.group(2), m.group(3)
        hno[0] += 1
        hid = f"sec-{hno[0]}"
        text = re.sub(r"<[^>]+>", "", inner)
        text = html.unescape(text).strip()
        if level in (2, 3):
            toc.append((level, hid, text))
        return f'<h{level} id="{hid}"{attrs}>{inner}</h{level}>'

    htm = HEADING_RE.sub(heading, htm)

    if toc:
        items = "".join(
            f'<li class="lv{lv}"><a href="#{hid}">{html.escape(txt)}</a></li>'
            for lv, hid, txt in toc)
        htm = re.sub(r"(</h1>)",
                     r'\1<nav class="toc"><details><summary>本页目录（点击可跳转）</summary>'
                     f"<ul>{items}</ul></details></nav>", htm, count=1)
    return htm, toc

# ---------------------------------------------------------------- 朗读时长估算

def spoken_minutes(page_html: str) -> int:
    h = re.sub(r'<nav class="toc">.*?</nav>', " ", page_html, flags=re.S)
    h = re.sub(r"<(\w+)[^>]*\bdata-no-tts\b[^>]*>.*?</\1>", " ", h, flags=re.S)
    h = re.sub(r"<[^>]*\bdata-tts=\"([^\"]*)\"[^>]*>", lambda m: " " + m.group(1) + " ", h)
    text = html.unescape(re.sub(r"<[^>]+>", " ", h))
    cjk = len(re.findall(r"[\u4e00-\u9fff]", text))
    words = len(re.findall(r"[A-Za-z0-9]+", text))
    return max(1, round((cjk + words * 0.7) / 240))

# ---------------------------------------------------------------- 页面组装

SIDEBAR_GROUPS = ["开始之前", "正文", "附录"]


def build_nav(current_out: str, root: str) -> str:
    parts = ['<nav class="nav">']
    for g in SIDEBAR_GROUPS:
        pages = [p for p in PAGES if p["group"] == g]
        if not pages:
            continue
        parts.append(f'<div class="nav-group">{g}</div>')
        for p in pages:
            cls = " active" if p["out"] == current_out else ""
            parts.append(f'<a class="nav-link{cls}" href="{root}{p["out"]}.html">{p["title"]}</a>')
    parts.append("</nav>")
    return "\n".join(parts)


def build_pager(idx: int) -> str:
    prev_html = next_html = ""
    if idx > 0:
        p = PAGES[idx - 1]
        prev_html = f'<a class="pager-link prev" href="{p["out"]}.html"><span>上一篇</span><b>{p["title"]}</b></a>'
    if idx < len(PAGES) - 1:
        p = PAGES[idx + 1]
        next_html = f'<a class="pager-link next" href="{p["out"]}.html"><span>下一篇</span><b>{p["title"]}</b></a>'
    return f'<nav class="pager">{prev_html}{next_html}</nav>'


def meta_description(page_html: str, drop_title: bool = False) -> str:
    h = re.sub(r'<nav class="toc">.*?</nav>', " ", page_html, flags=re.S)
    if drop_title:
        h = re.sub(r"<h1[^>]*>.*?</h1>", " ", h, flags=re.S)
    h = re.sub(r"<(\w+)[^>]*\bdata-no-tts\b[^>]*>.*?</\1>", " ", h, flags=re.S)
    text = html.unescape(re.sub(r"<[^>]+>", " ", h))
    text = re.sub(r"\s+", " ", text).strip()
    return text[:150]


def build_page(tpl: str, page: dict, content_html: str, idx: int, root: str) -> str:
    nxt = PAGES[idx + 1]["out"] + ".html" if idx < len(PAGES) - 1 else ""
    desc = meta_description(content_html)
    out_html = (tpl
                .replace("%%TITLE%%", page["title"])
                .replace("%%DESC%%", html.escape(desc, quote=True))
                .replace("%%NAV%%", build_nav(page["out"], root))
                .replace("%%CONTENT%%", content_html)
                .replace("%%PAGER%%", build_pager(idx))
                .replace("%%NEXT%%", nxt)
                .replace("%%PAGEKEY%%", page["out"])
                .replace("%%ROOT%%", root))
    return out_html


def build_index(tpl: str, root: str) -> str:
    cards = []
    for p in PAGES:
        minutes = STATS.get(p["out"], 0)
        first = STATS.get(p["out"] + ":desc", "")
        cards.append(
            f'<a class="card" href="{p["out"]}.html"><span class="card-group">{p["group"]}</span>'
            f'<b class="card-title">{p["title"]}</b>'
            f'<span class="card-desc">{html.escape(first, quote=False)}</span>'
            f'<span class="card-time">🎧 约 {minutes} 分钟</span></a>')
    total = sum(STATS.get(p["out"], 0) for p in PAGES)
    return (tpl.replace("%%CARDS%%", "\n".join(cards))
               .replace("%%TOTAL%%", str(total))
               .replace("%%NAV%%", build_nav("", root))
               .replace("%%ROOT%%", root))


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--docs", type=pathlib.Path, default=None,
                        help="happy-llm 的 docs 目录（默认自动探测 ../docs）")
    parser.add_argument("--out", type=pathlib.Path, default=REPO,
                        help="站点输出目录（默认本仓库根目录）")
    args = parser.parse_args()

    docs = args.docs
    if docs is None:
        for cand in (REPO.parent / "docs", REPO / "docs"):
            if (cand / "chapter1").exists():
                docs = cand.resolve()
                break
    if docs is None or not docs.exists():
        sys.exit("未找到 docs 目录，请用 --docs 指定 happy-llm 的 docs 路径")

    out_dir = args.out.resolve()
    tpl_dir = REPO / "templates"
    page_tpl = (tpl_dir / "page.html").read_text(encoding="utf-8")
    index_tpl = (tpl_dir / "index.html").read_text(encoding="utf-8")

    (out_dir / "assets").mkdir(parents=True, exist_ok=True)
    shutil.copy(tpl_dir / "style.css", out_dir / "assets" / "style.css")
    shutil.copy(tpl_dir / "app.js", out_dir / "assets" / "app.js")

    global STATS
    STATS = {}
    md_engine = markdown.Markdown(
        extensions=["tables", "fenced_code"],
        output_format="html5")

    for idx, page in enumerate(PAGES):
        src = docs / page["src"]
        raw = src.read_text(encoding="utf-8")
        page_dir = str(src.parent.relative_to(docs)).replace("\\", "/")
        page_dir = "" if page_dir == "." else page_dir
        prepared = preprocess(raw, docs, page_dir)
        md_engine.reset()
        body = md_engine.convert(prepared)
        body, _toc = postprocess(body)
        minutes = spoken_minutes(body)
        STATS[page["out"]] = minutes
        STATS[page["out"] + ":desc"] = meta_description(body, drop_title=True)[:72] + "…"
        html_text = build_page(page_tpl, page, body, idx, "")
        (out_dir / f'{page["out"]}.html').write_text(html_text, encoding="utf-8")
        print(f"  ✓ {page['title']:<22} → {page['out']}.html  （约 {minutes} 分钟）")

    (out_dir / "index.html").write_text(build_index(index_tpl, ""), encoding="utf-8")
    print(f"\n完成：{len(PAGES)} 个内容页 + index.html → {out_dir}")
    print("全部章节朗读时长约", sum(STATS[p['out']] for p in PAGES), "分钟")


if __name__ == "__main__":
    main()

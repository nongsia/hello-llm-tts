/* Happy-LLM 语音版 · 前端脚本：主题/侧栏 + Web Speech 朗读器 */
(function () {
  "use strict";

  var doc = document, body = doc.body;
  var store = {
    get: function (k, d) { try { var v = localStorage.getItem(k); return v === null ? d : v; } catch (e) { return d; } },
    set: function (k, v) { try { localStorage.setItem(k, v); } catch (e) {} },
    del: function (k) { try { localStorage.removeItem(k); } catch (e) {} }
  };

  /* ---------------- 主题 ---------------- */
  var theme = store.get("hlt:theme", "");
  if (!theme) theme = window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  doc.documentElement.setAttribute("data-theme", theme);
  var themeBtn = doc.getElementById("theme-btn");
  if (themeBtn) themeBtn.addEventListener("click", function () {
    theme = doc.documentElement.getAttribute("data-theme") === "dark" ? "light" : "dark";
    doc.documentElement.setAttribute("data-theme", theme);
    store.set("hlt:theme", theme);
  });

  /* ---------------- 移动端侧栏 ---------------- */
  var menuBtn = doc.getElementById("menu-btn");
  var mask = doc.getElementById("sidebar-mask");
  function closeSide() { body.classList.remove("sidebar-open"); if (mask) mask.hidden = true; }
  if (menuBtn) menuBtn.addEventListener("click", function () {
    body.classList.toggle("sidebar-open");
    if (mask) mask.hidden = !body.classList.contains("sidebar-open");
  });
  if (mask) mask.addEventListener("click", closeSide);

  /* ---------------- 朗读器 ---------------- */
  var article = doc.getElementById("article");
  var bar = doc.getElementById("readerbar");
  if (!article || !bar || typeof speechSynthesis === "undefined") {
    if (bar) { var info0 = doc.getElementById("rb-info"); if (info0) info0.textContent = "当前浏览器不支持语音合成"; }
    return;
  }

  var synth = window.speechSynthesis;
  var $ = function (id) { return doc.getElementById(id); };
  var playBtn = $("rb-play"), prevBtn = $("rb-prev"), nextBtn = $("rb-next"),
      restartBtn = $("rb-restart"), closeBtn = $("rb-close"),
      rateSel = $("rb-rate"), voiceSel = $("rb-voice"),
      autoChk = $("rb-auto"), fill = $("rb-fill"), info = $("rb-info"),
      chip = $("reader-chip"), toastEl = $("toast");

  var PAGEKEY = body.getAttribute("data-page") || location.pathname;
  var POSKEY = "hlt:pos:" + PAGEKEY;

  /* ----- 分句 ----- */
  function splitSentences(text) {
    var parts = text.match(/[^。！？!?；;…]*[。！？!?；;…]+[”’"』」）)】]*|[^。！？!?；;…]+$/g) || [];
    var merged = [];
    for (var i = 0; i < parts.length; i++) {
      var p = parts[i];
      if (merged.length && (p.trim().length < 2 || merged[merged.length - 1].trim().length < 6)) {
        merged[merged.length - 1] += p;
      } else merged.push(p);
    }
    var out = [];
    for (var j = 0; j < merged.length; j++) {
      var seg = merged[j];
      while (seg.length > 160) {
        var win = seg.slice(0, 160);
        var cut = Math.max(win.lastIndexOf("，"), win.lastIndexOf("、"), win.lastIndexOf("："), win.lastIndexOf(","));
        if (cut < 60) cut = 159;
        out.push(seg.slice(0, cut + 1));
        seg = seg.slice(cut + 1);
      }
      if (seg.length) out.push(seg);
    }
    return out;
  }

  /* ----- 收集朗读片段 ----- */
  var segments = [];
  (function collect(root) {
    function onText(node) {
      var text = node.textContent;
      if (!text.trim()) return;
      var frag = doc.createDocumentFragment();
      splitSentences(text).forEach(function (p) {
        if (!p.trim()) { frag.appendChild(doc.createTextNode(p)); return; }
        var sp = doc.createElement("span");
        sp.className = "s";
        sp.textContent = p;
        frag.appendChild(sp);
        segments.push({ el: sp, text: p.trim(), virtual: false });
      });
      node.parentNode.replaceChild(frag, node);
    }
    (function walk(el) {
      Array.prototype.slice.call(el.childNodes).forEach(function (child) {
        if (child.nodeType === 3) { onText(child); return; }
        if (child.nodeType !== 1) return;
        var tag = child.tagName;
        if (tag === "SCRIPT" || tag === "STYLE") return;
        if (child.hasAttribute("data-no-tts")) return;
        if (child.classList && child.classList.contains("toc")) return;
        if (child.hasAttribute("data-tts")) {
          splitSentences(child.getAttribute("data-tts")).forEach(function (piece) {
            if (piece.trim()) segments.push({ el: child, text: piece.trim(), virtual: true });
          });
          return;
        }
        walk(child);
      });
    })(root);
  })(article);

  /* ----- 状态 ----- */
  var state = "idle";          // idle | playing | paused
  var idx = 0;
  var voices = [];
  var lastStart = 0;

  /* 点击句子/公式/表格 → 从该处开始朗读（元素记录自己的首个分段号） */
  segments.forEach(function (seg, i) {
    if (seg.el && seg.el._hltSeg === undefined) seg.el._hltSeg = i;
  });

  var savedPos = parseInt(store.get(POSKEY, "0"), 10) || 0;
  if (savedPos >= segments.length) savedPos = 0;
  idx = savedPos;
  function updateInfo(msg) {
    info.textContent = msg || ("第 " + (idx + 1) + " / " + segments.length + " 句 · 共 " + segments.length + " 句");
    fill.style.width = segments.length ? (Math.min(idx + 1, segments.length) / segments.length * 100) + "%" : "0";
  }
  if (savedPos > 0) updateInfo("上次读到第 " + (savedPos + 1) + " 句，点 ▶ 继续");

  function toast(msg) {
    if (!toastEl) return;
    toastEl.textContent = msg;
    toastEl.hidden = false;
    clearTimeout(toast._t);
    toast._t = setTimeout(function () { toastEl.hidden = true; }, 2200);
  }

  function highlight(i) {
    var old = article.querySelector(".reading");
    if (old) old.classList.remove("reading");
    var seg = segments[i];
    if (seg && seg.el) {
      seg.el.classList.add("reading");
      var r = seg.el.getBoundingClientRect();
      if (r.top < 60 || r.bottom > window.innerHeight - 120) {
        seg.el.scrollIntoView({ block: "center", behavior: "smooth" });
      }
    }
  }

  function currentVoice() { return voices[voiceSel.value] || null; }

  function speakFrom(i) {
    if (i >= segments.length) { finish(); return; }
    idx = i;
    highlight(i);
    updateInfo();
    store.set(POSKEY, String(i));
    var u = new SpeechSynthesisUtterance(segments[i].text);
    var v = currentVoice();
    if (v) { u.voice = v; u.lang = v.lang; } else { u.lang = "zh-CN"; }
    u.rate = parseFloat(rateSel.value) || 1;
    var n = i;
    u.onend = function () {
      if (state !== "playing") return;
      speakFrom(n + 1);
    };
    u.onerror = function (e) {
      if (state !== "playing") return;
      if (e && (e.error === "interrupted" || e.error === "canceled")) return;
      setTimeout(function () { if (state === "playing") speakFrom(n); }, 200);
    };
    lastStart = Date.now();
    synth.speak(u);
  }

  function finish() {
    state = "idle";
    store.del(POSKEY);
    highlight(-1);
    playBtn.textContent = "▶";
    updateInfo("本页读完 🎉");
    if (autoChk.checked) {
      var next = doc.querySelector(".pager-link.next");
      var href = next && next.getAttribute("href");
      if (href) { toast("连播：进入下一章"); setTimeout(function () { location.href = href; }, 900); }
    }
  }

  function start(at) {
    synth.cancel();
    state = "playing";
    playBtn.textContent = "⏸";
    speakFrom(at);
  }
  function pause() {
    state = "paused";
    playBtn.textContent = "▶";
    synth.pause();
  }
  function resume() {
    state = "playing";
    playBtn.textContent = "⏸";
    synth.resume();
    /* 部分浏览器 resume 不生效，兜底重读当前句 */
    setTimeout(function () {
      if (state === "playing" && !synth.speaking && !synth.pending) speakFrom(idx);
    }, 350);
  }

  playBtn.addEventListener("click", function () {
    if (state === "idle") start(savedPos > 0 ? savedPos : 0);
    else if (state === "playing") pause();
    else resume();
  });
  prevBtn.addEventListener("click", function () { start(Math.max(0, idx - (state === "idle" ? 1 : 1))); });
  nextBtn.addEventListener("click", function () { start(Math.min(segments.length - 1, idx + 1)); });
  restartBtn.addEventListener("click", function () {
    store.del(POSKEY);
    savedPos = 0;
    start(0);
  });
  closeBtn.addEventListener("click", function () {
    synth.cancel();
    state = "idle";
    bar.style.display = "none";
    chip.hidden = false;
  });
  chip.addEventListener("click", function () {
    chip.hidden = true;
    bar.style.display = "";
  });

  /* 点击任意句子跳转朗读；选中文字或点链接时不劫持 */
  article.addEventListener("click", function (e) {
    var sel = window.getSelection && window.getSelection();
    if (sel && !sel.isCollapsed && String(sel)) return;
    var t = e.target && e.target.closest ? e.target.closest(".s, [data-tts]") : null;
    if (!t || !article.contains(t)) return;
    if (t.closest("a[href]")) return;
    var i = t._hltSeg;
    if (i === undefined) return;
    savedPos = i;
    store.set(POSKEY, String(i));
    start(i);
    toast("从第 " + (i + 1) + " 句开始朗读");
  });

  rateSel.value = store.get("hlt:rate", "1");
  rateSel.addEventListener("change", function () {
    store.set("hlt:rate", rateSel.value);
    if (state === "playing") { synth.cancel(); speakFrom(idx); }
  });
  autoChk.checked = store.get("hlt:auto", "0") === "1";
  autoChk.addEventListener("change", function () { store.set("hlt:auto", autoChk.checked ? "1" : "0"); });

  /* ----- 音色 ----- */
  function voiceScore(v) {
    var s = 0, n = v.name.toLowerCase();
    if (/natural|online|neural/i.test(n)) s += 10;
    if (/xiaoxiao|xiaoyi|yunxi|yunjian|yunyang|yunye|huihui|yaoyao|kangkang|tingting|meijia/.test(n)) s += 6;
    if (/^zh\b|^zh[-_]/i.test(v.lang)) s += 5;
    if (v.localService) s += 1;
    return s;
  }
  function loadVoices() {
    var all = synth.getVoices();
    if (!all.length) return;
    voices = {};
    voiceSel.innerHTML = "";
    var sorted = all.slice().sort(function (a, b) { return voiceScore(b) - voiceScore(a); });
    sorted.forEach(function (v, i) {
      voices["v" + i] = v;
      var opt = doc.createElement("option");
      opt.value = "v" + i;
      opt.textContent = v.name.replace(/^Microsoft /, "").replace(/ - .*/, "") + "（" + v.lang + "）";
      voiceSel.appendChild(opt);
    });
    var saved = store.get("hlt:voice", "");
    if (saved && voices[saved]) voiceSel.value = saved;
    voiceSel.addEventListener("change", function () {
      store.set("hlt:voice", voiceSel.value);
      if (state === "playing") { synth.cancel(); speakFrom(idx); }
    });
  }
  loadVoices();
  if (typeof synth.onvoiceschanged !== "undefined") synth.onvoiceschanged = loadVoices;

  /* ----- 看门狗：浏览器偶发静默停止 ----- */
  setInterval(function () {
    if (state === "playing" && !synth.speaking && !synth.pending && Date.now() - lastStart > 3000) {
      speakFrom(idx);
    }
  }, 3000);

  /* ----- 键盘 ----- */
  doc.addEventListener("keydown", function (e) {
    var t = e.target;
    if (t && /^(INPUT|SELECT|TEXTAREA)$/.test(t.tagName)) return;
    if (e.key === " ") {
      e.preventDefault();
      playBtn.click();
    } else if (e.key === "ArrowLeft") {
      prevBtn.click();
    } else if (e.key === "ArrowRight") {
      nextBtn.click();
    }
  });

  window.addEventListener("beforeunload", function () { synth.cancel(); });
  updateInfo();
})();

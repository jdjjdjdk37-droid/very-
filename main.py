#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import time
import threading
from flask import Flask, request, jsonify, Response
from functools import lru_cache
from concurrent.futures import ThreadPoolExecutor, as_completed

import argostranslate.package
import argostranslate.translate

APP_DIR = os.path.dirname(os.path.abspath(__file__))
PACKAGES_DIR = os.path.join(APP_DIR, "packages")
os.makedirs(PACKAGES_DIR, exist_ok=True)

ARABIC_CODE = "ar"
ENGLISH_CODE = "en"

_installed_languages = {}
_install_lock = threading.Lock()
_init_done = False


def _ensure_packages_dir():
    try:
        from argostranslate import settings
        settings.package_dir = PACKAGES_DIR
    except Exception:
        pass


def _download_and_install(from_code, to_code):
    key = f"{from_code}_{to_code}"
    if key in _installed_languages:
        return _installed_languages[key]

    with _install_lock:
        if key in _installed_languages:
            return _installed_languages[key]

        try:
            argostranslate.package.update_package_index()
            available = argostranslate.package.get_available_packages()

            pkg = next(
                (p for p in available
                 if p.from_code == from_code and p.to_code == to_code),
                None
            )

            if pkg is None:
                print(f"⚠️  لا يوجد نموذج مباشر: {from_code} → {to_code}")
                return None

            print(f"⬇️  جاري تحميل نموذج {from_code} → {to_code} ...")
            download_path = pkg.download()
            argostranslate.package.install_from_path(download_path)
            print(f"✅ تم تثبيت نموذج {from_code} → {to_code}")

            _installed_languages[key] = True
            return True

        except Exception as e:
            print(f"❌ فشل تثبيت {from_code} → {to_code}: {e}")
            return None


def _get_installed_pairs():
    try:
        langs = argostranslate.translate.get_installed_languages()
        pairs = {}
        for lang in langs:
            for t in lang.translations_from:
                pairs[f"{lang.code}_{t.to_lang.code}"] = True
        return pairs
    except Exception:
        return {}


def _translate(text, from_code, to_code):
    if not text or not text.strip():
        return text

    if from_code == to_code:
        return text

    try:
        langs = argostranslate.translate.get_installed_languages()
        from_lang = next((l for l in langs if l.code == from_code), None)
        to_lang = next((l for l in langs if l.code == to_code), None)

        if not from_lang or not to_lang:
            return None

        translation = from_lang.get_translation(to_lang)
        if translation is None:
            return None

        return translation.translate(text)
    except Exception as e:
        print(f"خطأ ترجمة: {e}")
        return None


def init_languages():
    global _init_done
    if _init_done:
        return

    _ensure_packages_dir()

    print("🚀 جاري تهيئة نماذج الترجمة (قد يأخذ وقتاً في المرة الأولى)...")
    _download_and_install(ENGLISH_CODE, ARABIC_CODE)
    _download_and_install(ARABIC_CODE, ENGLISH_CODE)
    _download_and_install("fr", ARABIC_CODE)
    _download_and_install("de", ARABIC_CODE)
    _download_and_install("es", ARABIC_CODE)
    _download_and_install("tr", ARABIC_CODE)
    _download_and_install("ru", ARABIC_CODE)
    _download_and_install("zh", ARABIC_CODE)
    _download_and_install("ja", ARABIC_CODE)

    _init_done = True
    print("✅ جميع النماذج جاهزة!")


@lru_cache(maxsize=5000)
def translate_cached(text, from_code="en", to_code=ARABIC_CODE):
    return _translate(text, from_code, to_code)


def translate_batch(texts, from_code="en", to_code=ARABIC_CODE, workers=4):
    results = [None] * len(texts)

    def task(i, text):
        try:
            return i, translate_cached(text, from_code, to_code)
        except Exception:
            return i, None

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(task, i, t) for i, t in enumerate(texts)]
        for fut in as_completed(futures):
            try:
                i, r = fut.result()
                results[i] = r
            except Exception:
                pass

    return results


app = Flask(__name__)


HTML_PAGE = """<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>محرك الترجمة إلى العربية</title>
<style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
        font-family: 'Segoe UI', Tahoma, sans-serif;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        min-height: 100vh;
        padding: 30px 20px;
    }
    .container {
        background: white;
        border-radius: 20px;
        padding: 35px;
        box-shadow: 0 20px 60px rgba(0,0,0,0.3);
        max-width: 900px;
        margin: 0 auto;
    }
    h1 { text-align: center; color: #333; margin-bottom: 8px; font-size: 1.9em; }
    .subtitle { text-align: center; color: #666; margin-bottom: 25px; font-size: 0.9em; }
    .tabs { display: flex; gap: 8px; margin-bottom: 20px; border-bottom: 2px solid #eee; }
    .tab {
        padding: 12px 24px; background: none; border: none;
        font-size: 15px; font-family: inherit; color: #666;
        cursor: pointer; border-bottom: 3px solid transparent;
        margin-bottom: -2px; transition: all 0.2s; font-weight: bold;
    }
    .tab.active { color: #667eea; border-bottom-color: #667eea; }
    .tab:hover { color: #667eea; }
    .panel { display: none; }
    .panel.active { display: block; }
    textarea {
        width: 100%; min-height: 110px; padding: 14px;
        border: 2px solid #e0e0e0; border-radius: 12px;
        font-size: 15px; font-family: inherit; resize: vertical;
        transition: border-color 0.3s; line-height: 1.6;
    }
    textarea:focus { outline: none; border-color: #667eea; }
    .btn {
        width: 100%; padding: 14px; margin-top: 14px;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white; border: none; border-radius: 12px;
        font-size: 16px; font-weight: bold; cursor: pointer;
        transition: transform 0.2s, box-shadow 0.2s; font-family: inherit;
    }
    .btn:hover { transform: translateY(-2px); box-shadow: 0 10px 20px rgba(102, 126, 234, 0.4); }
    .btn:disabled { opacity: 0.6; cursor: not-allowed; transform: none; }
    .result {
        margin-top: 20px; padding: 18px; background: #f8f9ff;
        border-right: 5px solid #667eea; border-radius: 12px; display: none;
    }
    .result.show { display: block; animation: fadeIn 0.4s; }
    .result-label { color: #667eea; font-size: 0.9em; margin-bottom: 8px; font-weight: bold; }
    .result-text { color: #333; font-size: 1.15em; line-height: 1.6; word-wrap: break-word; }
    .error { background: #fff5f5; border-right-color: #f56565; }
    .error .result-label { color: #f56565; }
    .error .result-text { color: #c53030; }
    .status { text-align: center; margin-top: 12px; color: #666; font-size: 0.85em; min-height: 20px; }
    .examples { margin-top: 15px; display: flex; flex-wrap: wrap; gap: 8px; justify-content: center; }
    .example {
        padding: 6px 14px; background: #eef1ff; color: #667eea;
        border-radius: 20px; font-size: 0.85em; cursor: pointer;
        transition: background 0.2s; border: 1px solid transparent;
    }
    .example:hover { background: #dde3ff; border-color: #667eea; }
    table { width: 100%; border-collapse: collapse; margin-top: 18px; background: white; border-radius: 12px; overflow: hidden; box-shadow: 0 2px 8px rgba(0,0,0,0.05); }
    th, td { padding: 12px 15px; text-align: right; border-bottom: 1px solid #f0f0f0; }
    th { background: #667eea; color: white; font-weight: bold; font-size: 0.9em; }
    tr:last-child td { border-bottom: none; }
    tr:hover td { background: #f8f9ff; }
    td.num { color: #999; width: 50px; font-weight: bold; }
    td.src { color: #555; font-size: 0.95em; }
    td.dst { color: #333; font-weight: 600; font-size: 1.05em; }
    .batch-actions { margin-top: 15px; display: flex; gap: 10px; }
    .batch-actions .btn { margin-top: 0; }
    .btn-ghost { background: #f0f0f0; color: #333; }
    .btn-ghost:hover { background: #e0e0e0; box-shadow: none; }
    .info { margin-top: 12px; padding: 10px; background: #fffbea; border-right: 4px solid #f6c23e; border-radius: 8px; font-size: 0.85em; color: #7a5c00; }
    @keyframes fadeIn { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }
</style>
</head>
<body>
<div class="container">
    <h1>🌍 محرك الترجمة</h1>
    <p class="subtitle">ترجم نصاً واحداً أو عدة كلمات دفعة واحدة إلى العربية</p>

    <div class="tabs">
        <button class="tab active" onclick="switchTab(event, 'single')">📝 نص واحد</button>
        <button class="tab" onclick="switchTab(event, 'batch')">📋 عدة كلمات</button>
    </div>

    <div class="panel active" id="single-panel">
        <textarea id="input" placeholder="اكتب هنا... (إنجليزي، فرنسي، ألماني، ياباني، صيني، روسي، وغيرها)"></textarea>
        <button class="btn" id="translateBtn" onclick="doTranslate()">ترجم إلى العربية</button>

        <div class="examples">
            <span class="example" onclick="setInput('Hello, how are you?')">Hello</span>
            <span class="example" onclick="setInput('Bonjour tout le monde')">Bonjour</span>
            <span class="example" onclick="setInput('Guten Tag')">Guten Tag</span>
            <span class="example" onclick="setInput('こんにちは')">日本語</span>
            <span class="example" onclick="setInput('안녕하세요')">한국어</span>
            <span class="example" onclick="setInput('你好世界')">中文</span>
            <span class="example" onclick="setInput('Привет мир')">Русский</span>
        </div>

        <div class="result" id="result">
            <div class="result-label">الترجمة:</div>
            <div class="result-text" id="resultText"></div>
        </div>
        <div class="status" id="status"></div>
    </div>

    <div class="panel" id="batch-panel">
        <div class="info">💡 اكتب كل كلمة أو جملة في سطر منفصل. سيتم ترجمتها كلها دفعة واحدة.</div>
        <textarea id="batchInput" rows="10" placeholder="Hello world&#10;Bonjour tout le monde&#10;Guten Tag&#10;こんにちは&#10;안녕하세요&#10;你好世界&#10;Привет мир"></textarea>

        <div class="batch-actions">
            <button class="btn" id="batchBtn" onclick="doBatchTranslate()" style="flex:1">ترجم كل الكلمات</button>
            <button class="btn btn-ghost" onclick="clearBatch()">مسح</button>
            <button class="btn btn-ghost" onclick="copyResults()">نسخ النتائج</button>
        </div>

        <div id="batchResult"></div>
        <div class="status" id="batchStatus"></div>
    </div>
</div>

<script>
const input       = document.getElementById('input');
const btn         = document.getElementById('translateBtn');
const result      = document.getElementById('result');
const resultText  = document.getElementById('resultText');
const status      = document.getElementById('status');

const batchInput  = document.getElementById('batchInput');
const batchBtn    = document.getElementById('batchBtn');
const batchStatus = document.getElementById('batchStatus');
const batchResult = document.getElementById('batchResult');

let lastResults = [];

function switchTab(e, name) {
    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
    e.target.classList.add('active');
    document.getElementById(name + '-panel').classList.add('active');
}

function setInput(text) {
    input.value = text;
    input.focus();
    doTranslate();
}

function escapeHtml(s) {
    return s.replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;');
}

async function doTranslate() {
    const text = input.value.trim();
    if (!text) { status.textContent = '⚠️ اكتب نصاً أولاً'; return; }

    btn.disabled = true;
    btn.textContent = 'جاري الترجمة...';
    status.textContent = '';
    result.classList.remove('show', 'error');

    const t0 = Date.now();

    try {
        const r = await fetch('/api/translate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ text })
        });
        const data = await r.json();
        const dt = Date.now() - t0;

        if (data.ok) {
            result.classList.add('show');
            resultText.textContent = data.translated;
            status.textContent = '✅ ' + dt + 'ms';
        } else {
            result.classList.add('show', 'error');
            resultText.textContent = data.error || 'خطأ غير معروف';
            status.textContent = '❌ فشلت الترجمة';
        }
    } catch (e) {
        result.classList.add('show', 'error');
        resultText.textContent = 'فشل الاتصال بالخادم';
        status.textContent = '❌ ' + e.message;
    } finally {
        btn.disabled = false;
        btn.textContent = 'ترجم إلى العربية';
    }
}

function clearBatch() {
    batchInput.value = '';
    batchResult.innerHTML = '';
    batchStatus.textContent = '';
    lastResults = [];
}

async function doBatchTranslate() {
    const raw = batchInput.value;
    const lines = raw.split('\\n').map(l => l.trim()).filter(l => l.length > 0);

    if (lines.length === 0) { batchStatus.textContent = '⚠️ اكتب كلمة واحدة على الأقل'; return; }
    if (lines.length > 100) {
        batchStatus.textContent = '⚠️ الحد الأقصى 100 سطر — سيتم تجاهل الباقي';
        lines.length = 100;
    }

    batchBtn.disabled = true;
    batchBtn.textContent = 'جاري الترجمة...';
    batchStatus.textContent = '';
    batchResult.innerHTML = '';
    lastResults = [];

    const t0 = Date.now();
    const total = lines.length;

    try {
        const r = await fetch('/api/translate-batch', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ texts: lines })
        });
        const data = await r.json();
        const dt = Date.now() - t0;

        if (!data.ok) { batchStatus.textContent = '❌ ' + (data.error || 'فشلت الترجمة'); return; }

        let html = '<table><tr><th>#</th><th>الأصل</th><th>الترجمة</th></tr>';
        data.results.forEach((item, i) => {
            const src = escapeHtml(item.source || '');
            const dst = item.translated ? escapeHtml(item.translated) : '<span style="color:#f56565">❌ فشل</span>';
            html += '<tr><td class="num">' + (i + 1) + '</td><td class="src">' + src + '</td><td class="dst">' + dst + '</td></tr>';
            lastResults.push({ source: item.source, translated: item.translated || '' });
        });
        html += '</table>';
        batchResult.innerHTML = html;

        const okCount = lastResults.filter(r => r.translated).length;
        batchStatus.textContent = '✅ ' + okCount + ' / ' + total + '  ·  ' + dt + 'ms';
    } catch (e) {
        batchStatus.textContent = '❌ ' + e.message;
    } finally {
        batchBtn.disabled = false;
        batchBtn.textContent = 'ترجم كل الكلمات';
    }
}

function copyResults() {
    if (!lastResults.length) { batchStatus.textContent = '⚠️ لا نتائج للنسخ'; return; }
    const text = lastResults.map(r => r.source + ' → ' + r.translated).join('\\n');
    navigator.clipboard.writeText(text).then(() => {
        batchStatus.textContent = '✅ تم النسخ';
    });
}

input.addEventListener('keydown', e => {
    if (e.ctrlKey && e.key === 'Enter') doTranslate();
});
</script>
</body>
</html>
"""


@app.route("/")
def index():
    return Response(HTML_PAGE, mimetype="text/html")


@app.route("/api/translate", methods=["POST"])
def api_translate():
    try:
        data = request.get_json() or {}
        text = (data.get("text") or "").strip()
        from_code = (data.get("from") or "en").strip()

        if not text:
            return jsonify({"ok": False, "error": "النص فارغ"}), 400

        if len(text) > 5000:
            text = text[:5000]

        result = translate_cached(text, from_code, ARABIC_CODE)

        if result:
            return jsonify({"ok": True, "translated": result, "source": text})

        return jsonify({"ok": False, "error": "لا يوجد نموذج لهذه اللغة"}), 500
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/translate-batch", methods=["POST"])
def api_translate_batch():
    try:
        data = request.get_json() or {}
        texts = data.get("texts") or []
        from_code = (data.get("from") or "en").strip()

        if not isinstance(texts, list) or len(texts) == 0:
            return jsonify({"ok": False, "error": "لم يتم إرسال نصوص"}), 400

        if len(texts) > 100:
            texts = texts[:100]

        texts = [(t or "").strip()[:5000] for t in texts]

        translated = translate_batch(texts, from_code, ARABIC_CODE, workers=4)

        results = [
            {"source": texts[i], "translated": translated[i]}
            for i in range(len(texts))
        ]

        return jsonify({"ok": True, "results": results})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/languages")
def api_languages():
    pairs = _get_installed_pairs()
    return jsonify({"ok": True, "installed": list(pairs.keys())})


if __name__ == "__main__":
    init_languages()
    app.run(host="0.0.0.0", port=5000, debug=False, threaded=True)

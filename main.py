#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import requests
import json
import time
import uuid
import random
import hashlib
import threading
from flask import Flask, request, jsonify, Response
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from functools import lru_cache
from concurrent.futures import ThreadPoolExecutor, as_completed

API_URL      = "https://api.translasion.com/enhance/dictionary"
API_KEY      = "eb298ebd8ac6c5c6c34d0fab40b871dc"
APP_KEY_SIG  = "3be659f52e8f"
BODY_APP_KEY = "aa466fe2a01b"
PKG          = "com.zaz.translate"
PKG_SIGN     = "61ed377e85d386a8dfee6b864bd85b0bfaa5af81"
VERSION_NAME = "6.2.0.003.gp"
VERSION_CODE = "2026083103"
APP_VERSION  = "6.2.0"

DEVICES = [
    ("TECNO TECNO LJ9",  "TECNO"),
    ("TECNO TECNO CM7",  "TECNO"),
    ("TECNO TECNO KI5",  "TECNO"),
    ("Samsung SM-G998B", "samsung"),
    ("Samsung SM-A536B", "samsung"),
    ("Samsung SM-S918B", "samsung"),
    ("Xiaomi 2201123G",  "Xiaomi"),
    ("Xiaomi M2101K7AG", "Xiaomi"),
    ("Redmi 21091116AG", "Xiaomi"),
    ("POCO 2207117BPG",  "Xiaomi"),
    ("HUAWEI ELS-NX9",   "HUAWEI"),
    ("HUAWEI VOG-L29",   "HUAWEI"),
    ("HONOR BVL-N49",    "HONOR"),
    ("OPPO CPH2451",     "OPPO"),
    ("OnePlus CPH2449",  "OnePlus"),
    ("vivo V2148A",      "vivo"),
    ("realme RMX3630",   "realme"),
    ("Google Pixel 7",   "google"),
    ("Google Pixel 8",   "google"),
    ("motorola moto g62","motorola"),
    ("Nokia G21",        "HMD Global"),
    ("Sony XQ-DQ72",     "Sony"),
    ("Nothing A063",     "Nothing"),
    ("Infinix X6819",    "Infinix"),
    ("ASUS_AI2202",      "asus"),
    ("LG LM-G910",       "LGE"),
]

USER_AGENTS = [
    "okhttp/5.1.0",
    "okhttp/4.12.0",
    "okhttp/4.11.0",
    "okhttp/4.10.0",
    "okhttp/4.9.3",
    "Dalvik/2.1.0 (Linux; U; Android 16; TECNO CM7 Build/BP2A.250605.031.A3)",
    "Dalvik/2.1.0 (Linux; U; Android 15; SM-S918B Build/AP3A.240905.015)",
    "Dalvik/2.1.0 (Linux; U; Android 14; Pixel 8 Build/AP1A.240505.005)",
    "Dalvik/2.1.0 (Linux; U; Android 13; SM-A536B Build/TP1A.220624.014)",
]

TIMEZONES = [
    "Asia/Baghdad", "Asia/Riyadh", "Asia/Dubai", "Asia/Kuwait",
    "Asia/Qatar", "Asia/Amman", "Asia/Beirut", "Africa/Cairo",
    "Europe/London", "Europe/Paris", "Europe/Berlin",
    "Asia/Tokyo", "Asia/Seoul", "Asia/Istanbul",
]

DEVICE_LANGS = [
    "ar-IQ", "ar-SA", "ar-EG", "ar-AE", "ar-KW", "ar-JO",
    "en-US", "en-GB", "fr-FR", "de-DE", "es-ES", "tr-TR",
    "fa-IR", "ur-PK", "ru-RU", "zh-CN", "ja-JP", "ko-KR", "hi-IN",
]

ALPHANUM = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"


class Translator:
    def __init__(self, rotate_every=100):
        self.session      = self._build_session()
        self.install_id   = self._rand_id()
        self.rotate_every = rotate_every
        self.counter      = 0
        self.lock         = threading.Lock()
        self.stats        = {"ok": 0, "err": 0, "blocked": 0}

    @staticmethod
    def _build_session():
        s = requests.Session()
        retry = Retry(
            total=3,
            backoff_factor=0.3,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["POST"],
        )
        adapter = HTTPAdapter(
            max_retries=retry,
            pool_connections=30,
            pool_maxsize=100,
        )
        s.mount("https://", adapter)
        s.mount("http://", adapter)
        return s

    @staticmethod
    def _rand_id():
        return ''.join(random.choice(ALPHANUM) for _ in range(22))

    def _rotate(self):
        with self.lock:
            self.counter += 1
            if self.counter % self.rotate_every == 0:
                self.install_id = self._rand_id()
                if self.counter % (self.rotate_every * 3) == 0:
                    self.session = self._build_session()

    def _headers(self):
        ts    = int(time.time())
        uid   = str(uuid.uuid4())
        nonce = str(random.randint(1000, 9999))
        sig   = hashlib.md5(
            f"{APP_KEY_SIG}&{ts}&{uid}&{nonce}".encode()
        ).hexdigest()
        device, brand = random.choice(DEVICES)
        return {
            'User-Agent'        : random.choice(USER_AGENTS),
            'Accept-Encoding'   : "identity",
            'api-key'           : API_KEY,
            'package-name'      : PKG,
            'package-sign'      : PKG_SIGN,
            'app-key'           : APP_KEY_SIG,
            'x-install-id'      : self.install_id,
            'timestamp'         : str(ts),
            'sig'               : sig,
            'nonce'             : nonce,
            'uuid'              : uid,
            'app_version'       : APP_VERSION,
            'x-package-name'    : PKG,
            'x-version-name'    : VERSION_NAME,
            'x-version-code'    : VERSION_CODE,
            'x-device'          : device,
            'x-brand'           : brand,
            'x-timezone'        : random.choice(TIMEZONES),
            'x-device-language' : random.choice(DEVICE_LANGS),
            'to'                : "ar",
            'content-type'      : "application/json; charset=UTF-8",
        }

    def _send(self, payload, retries=2):
        for _ in range(retries + 1):
            try:
                r = self.session.post(
                    API_URL,
                    data=json.dumps(payload),
                    headers=self._headers(),
                    timeout=8,
                )
                if r.status_code in (429, 403):
                    self.stats["blocked"] += 1
                    self.install_id = self._rand_id()
                    time.sleep(1.5 + random.random())
                    continue
                return r.json()
            except (requests.Timeout, requests.ConnectionError):
                time.sleep(0.5)
                continue
            except Exception:
                return {"code": -1, "message": "exception"}
        return {"code": -1, "message": "max retries"}

    def translate(self, text, to_lang="ar"):
        if not text or not text.strip():
            return {"ok": True, "translated": text, "source": text}

        self._rotate()

        payload = {
            "app_key"           : BODY_APP_KEY,
            "from"              : "auto",
            "gpt_switch"        : "0",
            "override_from_flag": "0",
            "scene"             : 100,
            "system_lang"       : "ar",
            "to"                : to_lang,
            "word"              : text,
        }

        data = self._send(payload)
        if data.get("code") == 1000:
            self.stats["ok"] += 1
            translated = data["data"].get("translated") or text
            return {"ok": True, "translated": translated, "source": text}

        self.stats["err"] += 1
        return {
            "ok": False,
            "translated": None,
            "source": text,
            "error": data.get("message"),
        }

    def translate_str(self, text, to_lang="ar"):
        r = self.translate(text, to_lang)
        return r["translated"] if r["ok"] else None

    def close(self):
        try:
            self.session.close()
        except Exception:
            pass


_engine = None
_lock = threading.Lock()


def get_translator():
    global _engine
    if _engine is None:
        with _lock:
            if _engine is None:
                _engine = Translator()
    return _engine


@lru_cache(maxsize=10000)
def translate_cached(text, to_lang="ar"):
    return get_translator().translate_str(text, to_lang)


def translate_batch(texts, workers=8):
    results = [None] * len(texts)

    def task(i, text):
        try:
            return i, translate_cached(text)
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
    .progress { margin-top: 15px; height: 8px; background: #eee; border-radius: 4px; overflow: hidden; display: none; }
    .progress.show { display: block; }
    .progress-bar { height: 100%; width: 0%; background: linear-gradient(90deg, #667eea, #764ba2); transition: width 0.3s; }
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

        <div class="progress" id="progress">
            <div class="progress-bar" id="progressBar"></div>
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
const progress    = document.getElementById('progress');
const progressBar = document.getElementById('progressBar');

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
    progress.classList.add('show');
    progressBar.style.width = '0%';
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

        progressBar.style.width = '100%';

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

        if not text:
            return jsonify({"ok": False, "error": "النص فارغ"}), 400

        if len(text) > 5000:
            text = text[:5000]

        result = translate_cached(text)

        if result:
            return jsonify({"ok": True, "translated": result, "source": text})

        return jsonify({"ok": False, "error": "فشلت الترجمة"}), 500
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/translate-batch", methods=["POST"])
def api_translate_batch():
    try:
        data = request.get_json() or {}
        texts = data.get("texts") or []

        if not isinstance(texts, list) or len(texts) == 0:
            return jsonify({"ok": False, "error": "لم يتم إرسال نصوص"}), 400

        if len(texts) > 100:
            texts = texts[:100]

        texts = [(t or "").strip()[:5000] for t in texts]

        translated = translate_batch(texts, workers=8)

        results = [
            {"source": texts[i], "translated": translated[i]}
            for i in range(len(texts))
        ]

        return jsonify({"ok": True, "results": results})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/stats")
def api_stats():
    return jsonify(get_translator().stats)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False, threaded=True)

from flask import Flask, request, redirect
import sqlite3
from datetime import datetime
import json
import random
import os

app = Flask(__name__)

DB_PATH = "consent_records.sqlite3"

# 后台口令（Render 里设置环境变量 ADMIN_TOKEN）
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "")

# ============ 160个不重复单词（4部分×40） ============
WORD_BANK = [
    # 1-40
    "anchor","bamboo","barrel","beacon","beetle","biscuit","blossom","border","breeze","bronze",
    "cactus","canvas","canyon","carpet","carrot","castle","celery","cherry","copper","crystal",
    "daisy","desert","dolphin","domino","dragon","drizzle","eagle","ember","engine","falcon",
    "feather","fossil","galaxy","goblet","hammer","harbor","hazelnut","helmet","honey","horizon",
    # 41-80
    "iceberg","jacket","jasmine","jigsaw","jungle","kernel","kettle","kitten","ladder","lantern",
    "lizard","locust","marble","meadow","meteor","mint","monarch","mosaic","mountain","museum",
    "napkin","nectar","needle","notebook","oasis","octagon","orchid","oxygen","paddle","parade",
    "pebble","pepper","pillow","pirate","planet","plaza","pocket","puzzle","quartz","quiver",
    # 81-120
    "radar","ribbon","rocket","saffron","sailor","sandbox","satellite","scarlet","season","shadow",
    "signal","silver","sketch","socket","sparrow","spice","spider","spiral","sponge","stadium",
    "staple","station","stone","strawberry","sunrise","tablet","tanker","temple","thunder","ticket",
    "timber","tornado","tulip","tunnel","turquoise","umbrella","velvet","vendor","voyage","walnut",
    # 121-160
    "whisper","willow","windowpane","winter","wizard","yogurt","zephyr","zigzag","zodiac","zombie",
    "apricot","avalanche","bandit","banjo","basil","battery","bayonet","boulder","bouquet","bubble",
    "butterfly","cabinet","carnival","cathedral","chimney","cinnamon","coconut","compass","crescent","cushion",
    "daylight","diamond","dinner","distant","drawer","festival","firefly","fountain","gardenia","glacier"
]

# ============ 4部分配置 ============
PARTS = [
    {"part": 1, "minutes": 4, "instruction": "say out the words you see.", "interval_sec": 6},
    {"part": 2, "minutes": 2, "instruction": "say out the words you see.", "interval_sec": 3},
    {"part": 3, "minutes": 4, "instruction": "remember the words you see without say.", "interval_sec": 6},
    {"part": 4, "minutes": 2, "instruction": "remember the words you see without say.", "interval_sec": 3},
]

def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS consent (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            participant_code TEXT,
            consent INTEGER,
            created_at TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS recall (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            participant_code TEXT,
            part INTEGER,
            instruction TEXT,
            interval_sec INTEGER,
            words_json TEXT,
            recalled_text TEXT,
            created_at TEXT
        )
    """)
    conn.commit()
    conn.close()

init_db()

def get_words_for_part(part_num: int):
    start = (part_num - 1) * 40
    chunk = WORD_BANK[start:start + 40]
    chunk = chunk[:]  # copy
    random.shuffle(chunk)
    return chunk

def save_recall(participant_code, part, instruction, interval_sec, words_list, recalled_text):
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """INSERT INTO recall
           (participant_code, part, instruction, interval_sec, words_json, recalled_text, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (
            participant_code,
            int(part),
            instruction,
            int(interval_sec),
            json.dumps(words_list),
            (recalled_text or "").strip(),
            datetime.now().isoformat(timespec="seconds")
        )
    )
    conn.commit()
    conn.close()

# ============ Scoring (admin 和 done 共用，保证一致) ============
def normalize_tokens(text: str):
    if not text:
        return []
    t = text.lower()
    for ch in [",", ".", ";", ":", "/", "\\", "|", "\t", "\r", "\n"]:
        t = t.replace(ch, " ")
    parts = [p.strip() for p in t.split(" ") if p.strip()]
    return parts

def score_recall(words_shown, recalled_text):
    shown_set = set([w.lower() for w in (words_shown or [])])
    recalled_tokens = normalize_tokens(recalled_text)

    correct = []
    seen = set()
    for tok in recalled_tokens:
        if tok in shown_set and tok not in seen:
            correct.append(tok)
            seen.add(tok)

    return {
        "correct_count": len(correct),
        "correct_words": correct,
        "typed_tokens": recalled_tokens
    }

@app.route("/", methods=["GET", "POST"])
def consent():
    if request.method == "POST":
        participant_code = request.form.get("participant_code", "").strip()
        consent_value = request.form.get("consent")
        consent_int = 1 if consent_value == "yes" else 0

        conn = sqlite3.connect(DB_PATH)
        conn.execute(
            "INSERT INTO consent (participant_code, consent, created_at) VALUES (?, ?, ?)",
            (participant_code, consent_int, datetime.now().isoformat(timespec="seconds"))
        )
        conn.commit()
        conn.close()

        return redirect(f"/start?code={participant_code}")

    return """
    <!doctype html>
    <html>
    <head>
      <meta charset="utf-8">
      <title>Informed Consent</title>
      <style>
        body { font-family: Arial, sans-serif; margin: 40px; max-width: 900px; }
        .box { border: 1px solid #ccc; padding: 20px; }
        label { display: block; margin-top: 15px; }
        input { font-size: 16px; padding: 6px; }
        button { margin-top: 20px; font-size: 16px; padding: 8px 14px; }
      </style>
    </head>
    <body>
    <h2>Informed Consent Instructions</h2>
    <div class="box">
    <p>
    I am a student in Introductory Psychology. I am asking for your consent to participate in a brief memory study that is part of my course. Please listen to these instructions and feel free to ask any questions. Your data will be anonymous so that your identity cannot be revealed. No-one will be able to know your name or scores. If you volunteer to be in the study your results will be referred to by a numeric code provided by the student researcher. You may quit the study at any time if you are at all uncomfortable.
    </p>
    <p>
    1. You will be asked to study some lists of words, images, or similar materials and then you will be asked to remember them until the end of the study.<br>
    2. You will be informed of the specific predictions after the study is completed, and if you have any questions they will be gladly answered.<br>
    3. There are no known risks or expected benefits of participating in this study.<br>
    4. There is no payment for your involvement, and you can quit the study at any time.<br>
    5. The student researcher will ask for verbal permission from all participants to be in their study.
    </p>
    <p>
    If you have any concerns about this study, you can ask me, and I can refer you to the course instructor.
    </p>
    <p><strong>Do you agree to be a subject in this study?</strong></p>

    <form method="post">
      <label>
        <input type="checkbox" name="consent" value="yes" required>
        I agree to participate
      </label>

      <label>
        Participant Code (e.g., P01):
        <input name="participant_code" required>
      </label>

      <button type="submit">Continue</button>
    </form>
    </div>
    </body>
    </html>
    """

@app.route("/start")
def start():
    code = request.args.get("code", "").strip()
    return f"""
    <!doctype html>
    <html>
    <head>
      <meta charset="utf-8">
      <title>Experiment Start</title>
      <style>
        body {{ font-family: Arial, sans-serif; margin: 40px; max-width: 900px; }}
        .box {{ border: 1px solid #ccc; padding: 20px; }}
        button {{ margin-top: 16px; font-size: 16px; padding: 8px 14px; }}
      </style>
    </head>
    <body>
      <h2>Memory Experiment</h2>
      <div class="box">
        <p><strong>This experiment will take about 15 minutes.</strong></p>
        <p>You will complete 4 parts. Each part shows 40 words, then you will type the words you remember.</p>
        <p>Participant Code: <strong>{code}</strong></p>
        <a href="/part/1?code={code}"><button>Start Part 1</button></a>
      </div>
    </body>
    </html>
    """

@app.route("/part/<int:part_num>")
def part(part_num):
    code = request.args.get("code", "").strip()
    cfg = next((p for p in PARTS if p["part"] == part_num), None)
    if not cfg:
        return "Invalid part", 400

    return f"""
    <!doctype html>
    <html>
    <head>
      <meta charset="utf-8">
      <title>Part {part_num}</title>
      <style>
        body {{ font-family: Arial, sans-serif; margin: 40px; max-width: 900px; }}
        .box {{ border: 1px solid #ccc; padding: 20px; }}
        button {{ margin-top: 16px; font-size: 16px; padding: 8px 14px; }}
      </style>
    </head>
    <body>
      <h2>Part {part_num} ({cfg["minutes"]} minutes)</h2>
      <div class="box">
        <p><strong>Instruction:</strong> {cfg["instruction"]}</p>
        <p>Words will appear one at a time. Do your best.</p>
        <a href="/run/{part_num}?code={code}"><button>Begin Part {part_num}</button></a>
      </div>
    </body>
    </html>
    """

@app.route("/run/<int:part_num>")
def run_part(part_num):
    code = request.args.get("code", "").strip()
    cfg = next((p for p in PARTS if p["part"] == part_num), None)
    if not cfg:
        return "Invalid part", 400

    words = get_words_for_part(part_num)
    payload = {
        "code": code,
        "part": part_num,
        "instruction": cfg["instruction"],
        "interval_ms": int(cfg["interval_sec"] * 1000),
        "words": words
    }

    return f"""
    <!doctype html>
    <html>
    <head>
      <meta charset="utf-8">
      <title>Running Part {part_num}</title>
      <style>
        body {{ font-family: Arial, sans-serif; margin: 40px; max-width: 900px; }}
        #word {{ font-size: 56px; margin-top: 40px; }}
        .muted {{ color: #555; }}
      </style>
    </head>
    <body>
      <h2>Part {part_num}</h2>
      <p class="muted"><strong>Instruction:</strong> {cfg["instruction"]}</p>
      <div id="word">Ready</div>

      <script>
        const payload = {json.dumps(payload)};
        const words = payload.words;
        const intervalMs = payload.interval_ms;

        let i = -1;

        function nextWord() {{
          i++;
          if (i >= words.length) {{
            window.location.href = `/rest20/{part_num}?code=${{encodeURIComponent(payload.code)}}&w=${{encodeURIComponent(JSON.stringify(words))}}`;
            return;
          }}
          document.getElementById("word").innerText = words[i];
          setTimeout(nextWord, intervalMs);
        }}

        setTimeout(nextWord, 1500);
      </script>
    </body>
    </html>
    """

@app.route("/rest20/<int:part_num>")
def rest20(part_num):
    code = request.args.get("code", "").strip()
    words_json = request.args.get("w", "[]")
    return f"""
    <!doctype html>
    <html>
    <head>
      <meta charset="utf-8">
      <title>Rest</title>
      <style>
        body {{ font-family: Arial, sans-serif; margin: 40px; max-width: 900px; }}
        #t {{ font-size: 44px; margin-top: 24px; }}
      </style>
    </head>
    <body>
      <h2>Rest (20 seconds)</h2>
      <div id="t">20</div>
      <script>
        let s = 20;
        const el = document.getElementById("t");
        const timer = setInterval(() => {{
          s--;
          el.innerText = s;
          if (s <= 0) {{
            clearInterval(timer);
            window.location.href = `/recall/{part_num}?code={code}&w=${{encodeURIComponent({json.dumps(words_json)})}}`;
          }}
        }}, 1000);
      </script>
    </body>
    </html>
    """

@app.route("/recall/<int:part_num>", methods=["GET", "POST"])
def recall(part_num):
    code = request.args.get("code", "").strip()
    cfg = next((p for p in PARTS if p["part"] == part_num), None)
    if not cfg:
        return "Invalid part", 400

    if request.method == "POST":
        recalled_text = request.form.get("recalled_text", "")
        words_list = json.loads(request.form.get("words_json", "[]"))

        save_recall(
            participant_code=code,
            part=part_num,
            instruction=cfg["instruction"],
            interval_sec=cfg["interval_sec"],
            words_list=words_list,
            recalled_text=recalled_text
        )

        next_part = part_num + 1
        if next_part <= 4:
            return redirect(f"/rest30/{part_num}?code={code}&next={next_part}")
        return redirect(f"/done?code={code}")

    words_json = request.args.get("w", "[]")
    return f"""
    <!doctype html>
    <html>
    <head>
      <meta charset="utf-8">
      <title>Recall Part {part_num}</title>
      <style>
        body {{ font-family: Arial, sans-serif; margin: 40px; max-width: 900px; }}
        textarea {{ width: 100%; max-width: 800px; height: 220px; font-size: 16px; padding: 10px; }}
        button {{ margin-top: 16px; font-size: 16px; padding: 8px 14px; }}
      </style>
    </head>
    <body>
      <h2>Recall (Part {part_num})</h2>
      <p>Type the words you remember (separate by spaces or new lines).</p>

      <form method="post">
        <input type="hidden" name="words_json" value='{words_json}'>
        <textarea name="recalled_text" required></textarea><br>
        <button type="submit">Submit</button>
      </form>
    </body>
    </html>
    """

@app.route("/rest30/<int:just_finished_part>")
def rest30(just_finished_part):
    code = request.args.get("code", "").strip()
    next_part = int(request.args.get("next", "0"))
    return f"""
    <!doctype html>
    <html>
    <head>
      <meta charset="utf-8">
      <title>Rest</title>
      <style>
        body {{ font-family: Arial, sans-serif; margin: 40px; max-width: 900px; }}
        #t {{ font-size: 44px; margin-top: 24px; }}
      </style>
    </head>
    <body>
      <h2>Rest (30 seconds)</h2>
      <div id="t">30</div>
      <script>
        let s = 30;
        const el = document.getElementById("t");
        const timer = setInterval(() => {{
          s--;
          el.innerText = s;
          if (s <= 0) {{
            clearInterval(timer);
            window.location.href = `/part/{next_part}?code={code}`;
          }}
        }}, 1000);
      </script>
    </body>
    </html>
    """

# ✅ done：显示与 admin 完全一致的计分结果
@app.route("/done")
def done():
    code = request.args.get("code", "").strip()

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT * FROM recall WHERE participant_code = ? ORDER BY part ASC",
        (code,)
    ).fetchall()
    conn.close()

    total = 0
    parts_html = ""

    for r in rows:
        part = int(r["part"])
        words = json.loads(r["words_json"]) if r["words_json"] else []
        recalled = r["recalled_text"] or ""
        s = score_recall(words, recalled)

        total += s["correct_count"]

        parts_html += f"""
        <div class="card">
          <h3>Part {part}</h3>
          <p><strong>Correct (DV):</strong> {s["correct_count"]} / {len(words)}</p>
          <p><strong>Correct words:</strong> {", ".join(s["correct_words"])}</p>
        </div>
        """

    return f"""
    <!doctype html>
    <html>
    <head>
      <meta charset="utf-8">
      <title>Results</title>
      <style>
        body {{ font-family: Arial, sans-serif; margin: 40px; max-width: 900px; }}
        .card {{ border: 1px solid #ccc; padding: 16px; margin: 12px 0; }}
      </style>
    </head>
    <body>
      <h2>Experiment completed</h2>
      <p>Thank you for participating.</p>
      <p>Participant Code: <strong>{code}</strong></p>
      <hr>
      {parts_html}
      <hr>
      <h3>Total Correct: {total}</h3>
    </body>
    </html>
    """

@app.route("/debug_token_len")
def debug_token_len():
    return str(len(ADMIN_TOKEN))

@app.route("/admin")
def admin():
    t = request.args.get("t", "")
    if not ADMIN_TOKEN or t != ADMIN_TOKEN:
        return "Forbidden", 403

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    consent_rows = conn.execute("SELECT * FROM consent ORDER BY id DESC").fetchall()
    recall_rows = conn.execute("SELECT * FROM recall ORDER BY id DESC").fetchall()
    conn.close()

    summary = {}
    for r in recall_rows:
        code = r["participant_code"] or ""
        part = int(r["part"])
        words = json.loads(r["words_json"]) if r["words_json"] else []
        recalled = r["recalled_text"] or ""
        s = score_recall(words, recalled)

        if code not in summary:
            summary[code] = {}
        summary[code][part] = s["correct_count"]

    html = "<h2>Admin</h2>"

    html += "<h3>Participant Summary (DV = correct words)</h3>"
    html += "<table border='1' cellpadding='6'>"
    html += "<tr><th>Participant</th><th>Part1</th><th>Part2</th><th>Part3</th><th>Part4</th><th>Total</th></tr>"
    for code in sorted(summary.keys()):
        p1 = summary[code].get(1, "")
        p2 = summary[code].get(2, "")
        p3 = summary[code].get(3, "")
        p4 = summary[code].get(4, "")
        total = 0
        for v in [p1, p2, p3, p4]:
            if isinstance(v, int):
                total += v
        html += f"<tr><td>{code}</td><td>{p1}</td><td>{p2}</td><td>{p3}</td><td>{p4}</td><td>{total}</td></tr>"
    html += "</table>"

    html += "<h3>Consent Records</h3>"
    html += "<table border='1' cellpadding='6'>"
    html += "<tr><th>ID</th><th>Participant Code</th><th>Consent</th><th>Time</th></tr>"
    for r in consent_rows:
        html += f"<tr><td>{r['id']}</td><td>{r['participant_code']}</td>"
        html += f"<td>{'Yes' if r['consent']==1 else 'No'}</td>"
        html += f"<td>{r['created_at']}</td></tr>"
    html += "</table>"

    html += "<h3>Recall Records (Scored)</h3>"
    html += "<table border='1' cellpadding='6'>"
    html += "<tr><th>ID</th><th>Participant</th><th>Part</th><th>IVs</th><th>Correct (DV)</th><th>Correct Words</th><th>Typed</th><th>Time</th></tr>"

    for r in recall_rows:
        words = json.loads(r["words_json"]) if r["words_json"] else []
        recalled = r["recalled_text"] or ""
        s = score_recall(words, recalled)

        mode = "aloud" if int(r["part"]) in (1, 2) else "quiet"
        speed = "slow(6s)" if int(r["interval_sec"]) == 6 else "quick(3s)"
        ivs = f"{mode}, {speed}"

        safe_typed = recalled.replace("<","&lt;").replace(">","&gt;")
        html += "<tr>"
        html += f"<td>{r['id']}</td>"
        html += f"<td>{r['participant_code']}</td>"
        html += f"<td>{r['part']}</td>"
        html += f"<td>{ivs}</td>"
        html += f"<td><strong>{s['correct_count']}</strong>/40</td>"
        html += f"<td>{', '.join(s['correct_words'])}</td>"
        html += f"<td>{safe_typed}</td>"
        html += f"<td>{r['created_at']}</td>"
        html += "</tr>"

    html += "</table>"
    return html

if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=False)


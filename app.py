from flask import Flask, render_template, request, redirect, session, jsonify
from database import init_db, get_db
from werkzeug.security import generate_password_hash, check_password_hash
import json
import time

app = Flask(__name__)
app.secret_key = "CLAVE_SUPER_SECRETA_123"
init_db()

def get_user(user_id):
    db = get_db()
    return db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()

# ---------------------- RUTAS BÁSICAS ----------------------

@app.route("/")
def home():
    if "user_id" in session:
        return redirect("/juego")
    return render_template("index.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"]
        password = generate_password_hash(request.form["password"])

        db = get_db()
        try:
            db.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, password))
            db.commit()
        except:
            return "Error: usuario ya existe"
        return redirect("/login")

    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        db = get_db()
        user = db.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()

        if user and check_password_hash(user["password"], password):
            session["user_id"] = user["id"]
            return redirect("/juego")

        return "Credenciales incorrectas"

    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

@app.route("/juego")
def juego():
    if "user_id" not in session:
        return redirect("/login")
    return render_template("juego.html")

# ---------------------- API STATE (GUARDADO) ----------------------

@app.route("/api/state", methods=["GET", "POST"])
def api_state():
    if "user_id" not in session:
        return jsonify({"error": "not authenticated"}), 401

    db = get_db()
    user = get_user(session["user_id"])
    if not user:
        return jsonify({"error": "user not found"}), 404

    # GET: devolver estado
    if request.method == "GET":
        try:
            state = json.loads(user["upgrades"]) if user["upgrades"] else {}
        except:
            state = {}

        return jsonify({
            "coins": float(user["coins"] or 0),
            "rebirths": int(user["rebirths"] or 0),
            "state": state
        })

    # POST: guardar estado
    payload = request.get_json()
    if not payload:
        return jsonify({"error": "no json payload"}), 400

    coins = float(payload.get("coins", 0))
    rebirths = int(payload.get("rebirths", 0))
    state = payload.get("state", {})

    db.execute("UPDATE users SET coins = ?, rebirths = ?, upgrades = ? WHERE id = ?",
               (coins, rebirths, json.dumps(state), user["id"]))
    db.commit()

    return jsonify({"status": "ok"})

# ===============================================================
#                    API CLICK (ANTIHACK CPS)
# ===============================================================

recent_clicks = {}       # user_id -> [timestamps]
click_penalties = {}     # strikes antes de ban

MAX_HUMAN_CPS = 17       # tu record real humano
CPS_WARNING = 20         # sospechoso
CPS_BAN = 40             # hack/autoclicker
WINDOW = 1.0             # ventana de 1 segundo

@app.route("/api/click", methods=["POST"])
def api_click():
    if "user_id" not in session:
        return jsonify({"error": "not authenticated"}), 401

    user_id = session["user_id"]
    now = time.time()

    data = request.get_json()
    if not data or "ts" not in data:
        return jsonify({"error": "no timestamp"}), 400

    # ------- registrar clicks en memoria -------
    if user_id not in recent_clicks:
        recent_clicks[user_id] = []

    recent_clicks[user_id].append(now)

    # borrar clicks fuera de 1 segundo
    recent_clicks[user_id] = [
        t for t in recent_clicks[user_id] if now - t <= WINDOW
    ]

    cps = len(recent_clicks[user_id])
    db = get_db()

    # ------------------ AUTOBAN POR HACK ------------------
    if cps > CPS_BAN:
        banned_until = int(time.time()) + 3600  # 1 hora
        db.execute("UPDATE users SET banned_until = ? WHERE id = ?", (banned_until, user_id))
        db.commit()

        db.execute("INSERT INTO security_logs (user_id, event, value, timestamp) VALUES (?, ?, ?, ?)",
                   (user_id, "autoban_cps", cps, int(time.time())))
        db.commit()

        return jsonify({"error": f"banned for 1h (CPS={cps})"}), 429

    # ------------------ SOSPECHOSO ------------------
    if cps > CPS_WARNING:
        click_penalties[user_id] = click_penalties.get(user_id, 0) + 1

        db.execute("INSERT INTO security_logs (user_id, event, value, timestamp) VALUES (?, ?, ?, ?)",
                   (user_id, "suspicious_cps", cps, int(time.time())))
        db.commit()

        if click_penalties[user_id] >= 5:
            banned_until = int(time.time()) + 300  # 5 minutos
            db.execute("UPDATE users SET banned_until = ? WHERE id = ?", (banned_until, user_id))
            db.commit()

            return jsonify({"error": "temp ban 5m for suspicious activity"}), 429

    # ------------------ ACTUALIZAR RECORD CPS ------------------
    user = get_user(user_id)
    best = user["best_cps"] or 0
    if cps > best:
        db.execute("UPDATE users SET best_cps = ? WHERE id = ?", (cps, user_id))
        db.commit()

    return jsonify({"status": "ok", "cps": cps})

# ===============================================================
#                    LEADERBOARD (API JSON)
# ===============================================================

@app.route("/api/leaderboard")
def api_leaderboard():
    db = get_db()

    # top 10 por monedas
    top_coins = db.execute("""
        SELECT username, coins 
        FROM users
        WHERE banned_until < ? OR banned_until IS NULL
        ORDER BY coins DESC
        LIMIT 10
    """, (int(time.time()),)).fetchall()

    # top 10 por rebirths
    top_rebirths = db.execute("""
        SELECT username, rebirths
        FROM users
        WHERE banned_until < ? OR banned_until IS NULL
        ORDER BY rebirths DESC, coins DESC
        LIMIT 10
    """, (int(time.time()),)).fetchall()

    # top 10 por CPS (mejor click humano logrado)
    top_cps = db.execute("""
        SELECT username, best_cps
        FROM users
        WHERE best_cps IS NOT NULL
        ORDER BY best_cps DESC
        LIMIT 10
    """).fetchall()

    return jsonify({
        "top_coins": [dict(row) for row in top_coins],
        "top_rebirths": [dict(row) for row in top_rebirths],
        "top_cps": [dict(row) for row in top_cps]
    })

# ===============================================================
#                    LEADERBOARD (PÁGINA HTML)
# ===============================================================

@app.route("/leaderboard")
def leaderboard_page():
    db = get_db()

    # Top por monedas
    coins = db.execute("""
        SELECT username, coins
        FROM users
        ORDER BY coins DESC
        LIMIT 10
    """).fetchall()

    # Top por rebirths
    rebirths = db.execute("""
        SELECT username, rebirths
        FROM users
        ORDER BY rebirths DESC, coins DESC
        LIMIT 10
    """).fetchall()

    # Top por CPS
    cps = db.execute("""
        SELECT username, best_cps
        FROM users
        ORDER BY best_cps DESC
        LIMIT 10
    """).fetchall()

    return render_template("leaderboard.html", 
                           top_coins=coins, 
                           top_rebirths=rebirths,
                           top_cps=cps)

# ---------------------- MAIN ----------------------
if __name__ == "__main__":
    app.run(debug=True)

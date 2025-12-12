from flask import Flask, render_template, request, redirect, session, jsonify
from database import init_db, get_db
from werkzeug.security import generate_password_hash, check_password_hash
import json, time, math

app = Flask(__name__)
app.secret_key = "CLAVE_SUPER_SECRETA_123"  # cámbiala en producción
init_db()

# ---- Configurables de seguridad ----
MAX_COINS_ABSOLUTE = 1e18          # máximo absoluto aceptable
MAX_DELTA_WARN = 1e7               # salto grande que genera flagged (ajusta según tu economía)
MAX_DELTA_BLOCK = 1e12             # salto gigante que causa bloqueo inmediato
MAX_SAVES_PER_MIN = 12             # máximo saves por minuto permitidos
MIN_SAVE_INTERVAL = 0.3            # segundos mínimos entre saves (evita spam)
SUSPICIOUS_THRESHOLD = 3           # cuantas alertas para ban temporal
BAN_SECONDS = 60 * 60              # 1 hora de ban por superar threshold
MAX_REBIRTHS = 10

# ---------------- utilities ----------------
def now():
    return time.time()

def client_ip():
    # obtiene la IP del cliente (confía en X-Forwarded-For si existe)
    xff = request.headers.get("X-Forwarded-For", "")
    if xff:
        return xff.split(",")[0].strip()
    return request.remote_addr or "unknown"

def log_security(user_id, event, detail=""):
    db = get_db()
    db.execute(
        "INSERT INTO security_logs (user_id, event, detail, ip, ts) VALUES (?, ?, ?, ?, ?)",
        (user_id, event, detail, client_ip(), now())
    )
    db.commit()

def get_user(user_id):
    db = get_db()
    return db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()

def update_user_fields(user_id, **fields):
    db = get_db()
    keys = ", ".join([f"{k} = ?" for k in fields.keys()])
    vals = list(fields.values()) + [user_id]
    db.execute(f"UPDATE users SET {keys} WHERE id = ?", vals)
    db.commit()

# ---------------- routes básicos ----------------
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
        except Exception:
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
            # actualizar last_ip al login
            update_user_fields(user["id"], last_ip=client_ip())
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

# ---------------- API segura para estado ----------------
@app.route("/api/state", methods=["GET", "POST"])
def api_state():
    if "user_id" not in session:
        return jsonify({"error": "not authenticated"}), 401

    user = get_user(session["user_id"])
    if not user:
        return jsonify({"error": "user not found"}), 404

    # revisa si está baneado temporalmente
    banned_until = float(user["banned_until"] or 0)
    if banned_until and banned_until > now():
        log_security(user["id"], "blocked_request", f"attempt while banned until {banned_until}")
        return jsonify({"error": "user temporarily banned"}), 403

    db = get_db()

    # GET -> devolver estado guardado
    if request.method == "GET":
        try:
            state = json.loads(user["upgrades"]) if user["upgrades"] else {}
        except Exception:
            state = {}
        return jsonify({
            "coins": float(user["coins"] or 0),
            "rebirths": int(user["rebirths"] or 0),
            "state": state
        })

    # POST -> guardar estado (con muchas validaciones)
    data = request.get_json()
    if not data:
        return jsonify({"error": "invalid json"}), 400

    # timestamps y limites
    ts = now()
    last_save_ts = float(user["last_save_ts"] or 0)
    last_coins = float(user["last_coins"] or 0)
    save_count_min = int(user["save_count_min"] or 0)
    suspicious_count = int(user["suspicious_count"] or 0)

    # rate limit: mínimo intervalo entre saves
    delta_t = ts - last_save_ts
    if delta_t < MIN_SAVE_INTERVAL:
        # registrar intento spam y bloquear temporal si es repetitivo
        suspicious_count += 1
        update_user_fields(user["id"], suspicious_count=suspicious_count)
        log_security(user["id"], "spam_save", f"delta_t={delta_t:.3f}")
        if suspicious_count >= SUSPICIOUS_THRESHOLD:
            banned_until = ts + BAN_SECONDS
            update_user_fields(user["id"], banned_until=banned_until)
            log_security(user["id"], "auto_ban", f"too many spam saves, banned_until={banned_until}")
            return jsonify({"error": "temporarily banned due to suspicious activity"}), 403
        return jsonify({"error": "too many requests"}), 429

    # saves per minuto (simple sliding-window approximation)
    # si el último save fue hace más de 60s, reiniciamos contador
    if delta_t > 60:
        save_count_min = 0
    save_count_min += 1
    if save_count_min > MAX_SAVES_PER_MIN:
        suspicious_count += 1
        update_user_fields(user["id"], save_count_min=save_count_min, suspicious_count=suspicious_count)
        log_security(user["id"], "too_many_saves", f"count={save_count_min}")
        if suspicious_count >= SUSPICIOUS_THRESHOLD:
            banned_until = ts + BAN_SECONDS
            update_user_fields(user["id"], banned_until=banned_until)
            log_security(user["id"], "auto_ban", f"too many saves per minute, banned_until={banned_until}")
            return jsonify({"error": "temporarily banned due to suspicious activity"}), 403
        return jsonify({"error": "too many saves per minute"}), 429

    # validar coins y rebirths
    try:
        coins = float(data.get("coins", 0))
    except:
        coins = 0.0
    coins = max(0.0, min(coins, MAX_COINS_ABSOLUTE))

    try:
        rebirths = int(data.get("rebirths", 0))
    except:
        rebirths = 0
    rebirths = max(0, min(rebirths, MAX_REBIRTHS))

    # analizar delta de coins desde el último guardado
    delta_coins = coins - last_coins
    # si incremento repentino muy grande -> mark suspicious
    if delta_coins > MAX_DELTA_WARN:
        suspicious_count += 1
        update_user_fields(user["id"], suspicious_count=suspicious_count)
        log_security(user["id"], "large_delta", f"delta={delta_coins}, last_coins={last_coins}, coins={coins}")
        # si supera bloque fuerte, ban inmediato
        if delta_coins > MAX_DELTA_BLOCK:
            banned_until = ts + (BAN_SECONDS * 24)  # ban largo
            update_user_fields(user["id"], banned_until=banned_until)
            log_security(user["id"], "auto_ban_large_delta", f"delta={delta_coins}, banned_until={banned_until}")
            return jsonify({"error": "temporarily banned due to suspicious activity (large delta)"}), 403

    # validar estructura state (must be dict)
    state = data.get("state", {})
    if not isinstance(state, dict):
        # posible manipulación — lo limpiamos y registramos
        log_security(user["id"], "invalid_state_format", "state not dict; sanitized")
        state = {}

    # si todo OK -> guardar y resetear contadores ligeros
    try:
        db.execute("""
            UPDATE users
            SET coins = ?, rebirths = ?, upgrades = ?, last_save_ts = ?, last_coins = ?, save_count_min = ?, suspicious_count = ?, last_ip = ?
            WHERE id = ?
        """, (coins, rebirths, json.dumps(state), ts, coins, save_count_min, suspicious_count, client_ip(), user["id"]))
        db.commit()
    except Exception as e:
        log_security(user["id"], "db_error_on_save", str(e))
        return jsonify({"error": "db_error"}), 500

    return jsonify({"status": "ok", "suspicious_count": suspicious_count})

# ---------------- admin helpers (para debugging) ----------------
@app.route("/admin/security_logs")
def admin_logs():
    # NOTA: en producción protege esta ruta con autenticación adicional
    db = get_db()
    rows = db.execute("SELECT * FROM security_logs ORDER BY ts DESC LIMIT 200").fetchall()
    out = []
    for r in rows:
        out.append({"id": r["id"], "user_id": r["user_id"], "event": r["event"], "detail": r["detail"], "ip": r["ip"], "ts": r["ts"]})
    return jsonify(out)

@app.route("/admin/unban/<int:user_id>")
def admin_unban(user_id):
    # NOTA: proteger en producción
    update_user_fields(user_id, banned_until=0, suspicious_count=0)
    log_security(user_id, "manual_unban", "unbanned via admin endpoint")
    return jsonify({"status": "ok"})

if __name__ == "__main__":
    app.run(debug=True)

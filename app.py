from flask import Flask, render_template, request, redirect, session, jsonify
from database import init_db, get_db
from werkzeug.security import generate_password_hash, check_password_hash
import json

app = Flask(__name__)
app.secret_key = "CLAVE_SUPER_SECRETA_123"
init_db()

def get_user(user_id):
    db = get_db()
    return db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()

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
        except Exception as e:
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

# API to get/save user state
@app.route("/api/state", methods=["GET", "POST"])
def api_state():
    if "user_id" not in session:
        return jsonify({"error":"not authenticated"}), 401
    user = get_user(session["user_id"])
    if not user:
        return jsonify({"error":"user not found"}), 404

    db = get_db()
    if request.method == "GET":
        # Return stored state if exists, otherwise initialize default state
        try:
            state = json.loads(user["upgrades"]) if user["upgrades"] else {}
        except Exception:
            state = {}
        # include coins and rebirths and upgrades
        data = {
            "coins": float(user["coins"] or 0),
            "rebirths": int(user["rebirths"] or 0),
            "state": state
        }
        return jsonify(data)

    # POST -> save state
    payload = request.get_json()
    if not payload:
        return jsonify({"error":"no json payload"}), 400
    coins = float(payload.get("coins", 0))
    rebirths = int(payload.get("rebirths", 0))
    state = payload.get("state", {})

    db.execute("UPDATE users SET coins = ?, rebirths = ?, upgrades = ? WHERE id = ?",
               (coins, rebirths, json.dumps(state), user["id"]))
    db.commit()
    return jsonify({"status":"ok"})

if __name__ == "__main__":
    app.run(debug=True)

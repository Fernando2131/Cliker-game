// Juego de Clicks adaptado para guardar/recuperar estado desde /api/state

let rebirthInProgress = false;

let coins = 0;
let clickValue = 0.0000001;
let multiplier = 1; // Multiplicador base, aumenta con rebirth
let rebirthCount = 0;
let rebirthCost = 1000000;
let comboCount = 0;
let comboActive = false;
let lastClickTime = 0;
let rebirthMultiplier = 1;

const workerUpgrades = [];

for (let i = 0; i < 8; i++) {
    workerUpgrades.push({
        id: i,
        name: `Worker ${i}`,
        digitIndex: i,
        

        level: 0,
        cost: 0.01 * Math.pow(10, i),

        baseDuration: 20,
        baseSpeed: 1.0,

        active: false,
        dom: null,
        timer: null,
        button: null
    });
}






// Mejoras activas: multiplicadores x2..x10
let activeUpgrades = [];
// Mejoras activas x2..x10
for (let i = 2; i <= 10; i++) {
    activeUpgrades.push({
        level: 0,
        multiplier: i,
        cost: Math.pow(2, i - 2) * 2
    });
}

// NUEVA MEJORA: Combo Clicker
activeUpgrades.push({
    name: "Combo Clicker",
    level: 0,
    multiplier: 1.5,     // extra
    cost: 0.0009,
    comboEnabled: false  // activado cuando llega a 50 clicks
});


// Mejoras pasivas
let passiveUpgrades = [
    { name: "Generador Básico", level: 0, cost: 0.00009, income: 0.000001, costMultiplier: 1.5 },
    { name: "Generador Avanzado", level: 0, cost: 0.00018, income: 0.000002, costMultiplier: 1.5 },
    { name: "Generador Elite", level: 0, cost: 0.00036, income: 0.000005, costMultiplier: 1.5 },
    { name: "Generador Máximo", level: 0, cost: 0.00072, income: 0.00001, costMultiplier: 1.5 },
    { name: "Generador Supremo", level: 0, cost: 0.00144, income: 0.0001, costMultiplier: 1.5 }
];

function saveState() {
    const payload = {
        coins: coins,
        rebirths: rebirthCount,
        state: {
    activeUpgrades,
    passiveUpgrades,
    workerUpgrades,
    clickValue,
    rebirthCost
}

    };
    fetch("/api/state", {
        method: "POST",
        headers: {"Content-Type":"application/json"},
        body: JSON.stringify(payload)
    }).then(r => r.json()).then(d => {
        // console.log("Guardado", d);
    }).catch(e => {
        // console.warn("No se pudo guardar:", e);
    });
}

function loadStateFromServer(data) {
    coins = data.coins || 0;
    rebirthCount = data.rebirths || 0;
    rebirthMultiplier = 1 + rebirthCount * 0.5;



    if (data.state && Object.keys(data.state).length) {
        const s = data.state;

        if (s.activeUpgrades) activeUpgrades = s.activeUpgrades;
        if (s.passiveUpgrades) passiveUpgrades = s.passiveUpgrades;
        if (s.workerUpgrades) {
            s.workerUpgrades.forEach((sw, i) => {
                Object.assign(workerUpgrades[i], sw);
                if (workerUpgrades[i].level > 0 && !workerUpgrades[i].dom) {
                    spawnWorker(workerUpgrades[i]);
                }
            });
        }
        if (s.clickValue) clickValue = s.clickValue;
        if (s.rebirthCost) rebirthCost = s.rebirthCost;
    }

    updateDisplay();
    renderWorkerShop();
    recalculateMultiplier();

}

function showRebirthAd(callback) {
    if (rebirthInProgress) return;
    rebirthInProgress = true;

    const overlay = document.getElementById("rebirthAdOverlay");
    const container = document.getElementById("rebirthAdContainer");
    const countdownEl = document.getElementById("rebirthCountdown");
    const rebirthInfo = document.getElementById("rebirthInfo");

    // Seguridad
    if (!overlay || !container || !countdownEl) {
        rebirthInProgress = false;
        callback();
        return;
    }

    // 🔒 BLOQUEAR INTERACCIÓN
    document.body.classList.add("rebirth-lock");

    // ✅ TEXTO DE ESTADO
    if (rebirthInfo) {
        rebirthInfo.innerText = "⏳ REBIRTH EN PROGRESO...";
    }

    overlay.style.display = "flex";
    container.innerHTML = "";

    const adScript = document.createElement("script");
    adScript.src = "https://www.effectivegatecpm.com/z8bkwmms?key=d7f2c3a3120142cde0c11f993217db43";
    container.appendChild(adScript);

    let time = 5;
    countdownEl.innerText = time;

    const timer = setInterval(() => {
        time--;
        countdownEl.innerText = time;

        if (time <= 0) {
            clearInterval(timer);

            overlay.style.display = "none";
            container.innerHTML = "";

            // 🔓 DESBLOQUEAR INTERACCIÓN
            document.body.classList.remove("rebirth-lock");
            rebirthInProgress = false;

             // ❌ QUITAR TEXTO TEMPORAL
    if (rebirthInfo) {
        rebirthInfo.innerText =
            `Rebirths: ${rebirthCount}/10 | Costo: ${rebirthCost.toFixed(2)}`;
    }

            callback();
        }
    }, 1000);
}




function renderWorkerShop() {
    const left = document.getElementById("workersLeft");
    const right = document.getElementById("workersRight");



    workerUpgrades.forEach((w, i) => {

        // ⛔ Si el botón ya existe, SOLO actualizamos texto
        if (w.button) {
            updateWorkerButton(w);
            return;
        }

        // ✅ Crear botón SOLO UNA VEZ
        const btn = document.createElement("button");
        w.button = btn;

        btn.onclick = () => {
            if (coins < w.cost) return;

            coins -= w.cost;
            w.level++;
            w.cost *= 10;

            if (!w.dom) spawnWorker(w);

            updateWorkerButton(w);
            updateDisplay();
            saveState();
        };

        updateWorkerButton(w);

        if (i < 4) left.appendChild(btn);
        else right.appendChild(btn);
    });
}


function updateWorkerButton(w) {
    w.button.innerText =
        `🧍 x${Math.pow(10, w.digitIndex)}\n` +
        `Nivel ${w.level}\n` +
        `Costo ${w.cost.toFixed(4)}`;
}

renderWorkerShop();

function spawnWorker(w) {
    const area = document.getElementById("workersArea");

    const worker = document.createElement("div");
    worker.className = "worker walking";
    worker.innerText = "🧍";

    area.appendChild(worker);
    w.dom = worker;

    let x = w.digitIndex < 4 ? -40 : area.offsetWidth + 40;
    let targetX = area.offsetWidth / 2 + (w.digitIndex - 3.5) * 45;

    worker.style.left = x + "px";
    worker.style.bottom = "40px";

    const walk = setInterval(() => {
        x += targetX > x ? 3 : -3;
        worker.style.left = x + "px";

        if (Math.abs(x - targetX) < 4) {
            clearInterval(walk);
            worker.classList.remove("walking");
        }
    }, 30);

    worker.onclick = () => activateWorker(w);
}

function activateWorker(w) {

    // 🔒 BLOQUEO LÓGICO
    if (rebirthInProgress || w.active) return;

    w.active = true;
    w.dom.classList.add("jump");

    setTimeout(() => w.dom.classList.remove("jump"), 400);

    const duration = w.baseDuration + w.level * 5;
    const speed = Math.max(0.3, w.baseSpeed - w.level * 0.1);
    const gain =
    clickValue *
    Math.pow(10, w.digitIndex) *
    9 *
    (1 + w.level * 0.25) *
    multiplier;



    let ticks = Math.floor(duration / speed);

    if (w.timer) clearInterval(w.timer);

w.timer = setInterval(() => {

        coins += gain;
        updateDisplay();

        if (--ticks <= 0) {
            clearInterval(w.timer);
            w.active = false;
        }
    }, speed * 1000);
}



function updateComboDisplay() {
    const comboDiv = document.getElementById("comboDisplay");
    if (!comboDiv) return;

    if (comboActive) {
        comboDiv.innerText = `🔥 COMBO ACTIVO ×1.5 — Clicks: ${comboCount}`;
        comboDiv.style.color = "#ff2200";
        comboDiv.classList.add("comboActiveAnim");
    } else {
        comboDiv.innerText = `Clicks en combo: ${comboCount}/50`;
        comboDiv.style.color = "#ff8800";
        comboDiv.classList.remove("comboActiveAnim");
    }
}



// Función para actualizar la pantalla
function updateDisplay() {
    document.getElementById('coinsDisplay').innerText = `Monedas: ${coins.toFixed(7)}`;
    if (!rebirthInProgress) {
    document.getElementById('rebirthInfo').innerText =
        `Rebirths: ${rebirthCount}/10 | Costo: ${rebirthCost.toFixed(2)}`;
}

    // Mejoras activas
    let activeDiv = document.getElementById('activeUpgrades');
    activeDiv.innerHTML = '';
    activeUpgrades.forEach((upgrade, index) => {
        let button = document.createElement('button');
        button.innerText = `x${upgrade.multiplier} (Nivel: ${upgrade.level}) - Costo: ${upgrade.cost.toFixed(7)}`;
        button.onclick = () => buyActiveUpgrade(index);
        activeDiv.appendChild(button);
    });

    // Mejoras pasivas
    let passiveDiv = document.getElementById('passiveUpgrades');
    passiveDiv.innerHTML = '';
    passiveUpgrades.forEach((upgrade, index) => {
        let button = document.createElement('button');
        button.innerText = `${upgrade.name} (Nivel: ${upgrade.level}) - Income: ${upgrade.income.toFixed(7)}/s - Costo: ${upgrade.cost.toFixed(7)}`;
        button.onclick = () => buyPassiveUpgrade(index);
        passiveDiv.appendChild(button);
    });
    

}
setInterval(() => {
    if (Date.now() - lastClickTime > 1000) {
        if (comboActive) {
            recalculateMultiplier();

        }
        comboActive = false;
        comboCount = 0;
        updateComboDisplay();
    }
}, 200);


    

// Función para hacer click
document.getElementById('clickButton').onclick = () => {

    // 🔒 BLOQUEO LÓGICO
    if (rebirthInProgress) return;

    

    const now = Date.now();

    const comboUpgrade = activeUpgrades.find(u => u.name === "Combo Clicker");

    if (comboUpgrade && comboUpgrade.level > 0) {

        comboCount++;
        lastClickTime = now;

        if (!comboActive && comboCount >= 50) {
    comboActive = true;
    recalculateMultiplier();
}

    }

    updateComboDisplay();

    coins += clickValue * multiplier;
    updateDisplay();

    fetch("/api/click", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ts: Date.now() })
    }).catch(() => {});
};


    


    // Ya NO guardamos en cada click (solo periódico)


    document.getElementById('rebirthButton').onclick = () => {
    if (rebirthInProgress) return;
    if (coins < rebirthCost || rebirthCount >= 10) return;

    const nextMultiplier = 1 + (rebirthCount + 1) * 0.5;

    const ok = confirm(
        `⚠️ REBIRTH\n\n` +
        `Perderás TODAS tus monedas, workers y mejoras.\n\n` +
        `A cambio iniciarás con un multiplicador permanente x${nextMultiplier.toFixed(1)}.\n\n` +
        `¿Deseas continuar?`
    );

    if (!ok) return;

    showRebirthAd(() => {
        coins = 0;
        rebirthCount++;
        rebirthMultiplier = nextMultiplier;

        rebirthCost *= 10;

        // Resetear mejoras activas
        activeUpgrades.forEach(upgrade => {
            upgrade.level = 0;
            upgrade.cost = Math.pow(2, upgrade.multiplier - 2) * 2;
        });

        // Resetear workers
        workerUpgrades.forEach(w => {
            if (w.timer) clearInterval(w.timer);
            w.active = false;
            if (w.dom) {
                w.dom.remove();
                w.dom = null;
            }
            w.level = 0;
            w.cost = 0.01 * Math.pow(10, w.digitIndex);
        });

        comboActive = false;
        comboCount = 0;
        lastClickTime = 0;

        recalculateMultiplier();
        updateComboDisplay();
        updateDisplay();
        saveState();
    });
};


    

    // Inicializar - pedir estado al servidor
    fetch("/api/state").then(r => {
        if (!r.ok) throw new Error("No auth");
        return r.json();
    }).then(data => {
        loadStateFromServer(data);
    }).catch(e => {
        // si no autenticado o error, mantenemos valores por defecto
        console.warn("No se pudo cargar estado:", e);
        updateDisplay();
    });

recalculateMultiplier();

// Comprar mejora activa
function buyActiveUpgrade(index) {
    const up = activeUpgrades[index];
    if (coins < up.cost) return;

    coins -= up.cost;
    up.level++;
    up.cost *= 2;

    recalculateMultiplier();


    updateDisplay();
    saveState();
}

    
function recalculateMultiplier() {
    multiplier = rebirthMultiplier;

    activeUpgrades.forEach(u => {
        if (u.level > 0 && u.name !== "Combo Clicker") {
            multiplier *= Math.pow(u.multiplier, u.level);
        }
    });
    if (comboActive) multiplier *= 1.5;
}


// Comprar mejora pasiva
function buyPassiveUpgrade(index) {
    if (coins >= passiveUpgrades[index].cost) {
        coins -= passiveUpgrades[index].cost;
        passiveUpgrades[index].level++;
        passiveUpgrades[index].income *= 1.1; // Aumenta income ligeramente
        passiveUpgrades[index].cost *= passiveUpgrades[index].costMultiplier; // Aumenta costo
        updateDisplay();
        saveState();
    }
}

// Generación pasiva cada segundo
setInterval(() => {
    let totalPassive = passiveUpgrades.reduce((sum, upgrade) => sum + (upgrade.income * upgrade.level), 0);
    coins += totalPassive;
    updateDisplay();
    // guardado periódico
    saveState();
}, 1000);







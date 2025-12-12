// Juego de Clicks adaptado para guardar/recuperar estado desde /api/state
let stateFromServer = null;
let coins = 0;
let clickValue = 0.0000001;
let multiplier = 1; // Multiplicador base, aumenta con rebirth
let rebirthCount = 0;
let rebirthCost = 1000000;

// Mejoras activas: multiplicadores x2..x10
let activeUpgrades = [];
for (let i = 2; i <= 10; i++) {
    activeUpgrades.push({
        level: 0,
        multiplier: i,
        cost: Math.pow(2, i - 2) * 2 // Precio inicial
    });
}

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
            clickValue,
            multiplier,
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
    // data: { coins, rebirths, state }
    coins = data.coins || 0;
    rebirthCount = data.rebirths || 0;
    if (data.state && Object.keys(data.state).length) {
        try {
            const s = data.state;
            if (s.activeUpgrades) activeUpgrades = s.activeUpgrades;
            if (s.passiveUpgrades) passiveUpgrades = s.passiveUpgrades;
            if (s.clickValue) clickValue = s.clickValue;
            if (s.multiplier) multiplier = s.multiplier;
            if (s.rebirthCost) rebirthCost = s.rebirthCost;
        } catch(e) {
            console.warn("Error parsing state", e);
        }
    }
    updateDisplay();
}

// Función para actualizar la pantalla
function updateDisplay() {
    document.getElementById('coinsDisplay').innerText = `Monedas: ${coins.toFixed(7)}`;
    document.getElementById('rebirthInfo').innerText = `Rebirths: ${rebirthCount}/10 | Costo: ${rebirthCost.toFixed(2)}`;

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

// Función para hacer click
document.addEventListener("DOMContentLoaded", function(){
    
        document.getElementById("leaderboardButton").onclick = () => {
        window.location.href = "/leaderboard";
    };

    document.getElementById('clickButton').onclick = () => {
    coins += clickValue * multiplier;
    updateDisplay();

    // --- ANTI-HACK CLICK / CPS DETECTOR ---
    fetch("/api/click", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ts: Date.now() })
    })
    .then(res => res.json())
    .then(data => {
        if (data.error) {
            console.warn("⚠ Click bloqueado:", data.error);
        } else if (data.cps) {
            // Puedes mostrarlo si quieres: console.log("CPS actual:", data.cps);
        }
    })
    .catch(() => {});

    // Ya NO guardamos en cada click (solo periódico)
};


    document.getElementById('rebirthButton').onclick = () => {
        if (coins >= rebirthCost && rebirthCount < 10) {
            coins = 0;
            multiplier = 1.5; // Multiplicador base después de rebirth
            rebirthCount++;
            rebirthCost *= 10; // Aumenta x10 el costo
            // Resetear mejoras activas y pasivas
            activeUpgrades.forEach(upgrade => {
                upgrade.level = 0;
                upgrade.cost = Math.pow(2, upgrade.multiplier - 2) * 2;
            });
            passiveUpgrades.forEach(upgrade => {
                upgrade.level = 0;
                upgrade.cost = upgrade.cost / Math.pow(upgrade.costMultiplier, upgrade.level);
                upgrade.income = upgrade.income / Math.pow(1.1, upgrade.level);
            });
            updateDisplay();
            saveState();
        }
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
});

// Comprar mejora activa
function buyActiveUpgrade(index) {
    if (coins >= activeUpgrades[index].cost) {
        coins -= activeUpgrades[index].cost;
        activeUpgrades[index].level++;
        multiplier *= activeUpgrades[index].multiplier;
        activeUpgrades[index].cost *= 2; // Aumenta el costo x2
        updateDisplay();
        saveState();
    }
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

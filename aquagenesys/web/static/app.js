const canvas = document.getElementById("pond");
const ctx = canvas.getContext("2d");
const statusEl = document.getElementById("status");
const speed = document.getElementById("speed");
const speedValue = document.getElementById("speedValue");
const deliberation = document.getElementById("deliberation");
const reset = document.getElementById("reset");
const randomize = document.getElementById("randomize");

const FRAME_POLL_MS = 320;
const STATE_POLL_MS = 2600;
const INTERPOLATION_DELAY_MS = 280;

let latestState = null;
let latestEnvironment = null;
let previousFrame = null;
let currentFrame = null;
let fieldCanvas = document.createElement("canvas");
let fieldSignature = "";
let frameFetchInFlight = false;
let stateFetchInFlight = false;
let hoverFishId = null;
let selectedFishId = null;
let renderedFish = [];

function resizeCanvas() {
  const rect = canvas.getBoundingClientRect();
  const ratio = window.devicePixelRatio || 1;
  canvas.width = Math.max(720, Math.floor(rect.width * ratio));
  canvas.height = Math.max(480, Math.floor(rect.height * ratio));
  ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
}

window.addEventListener("resize", resizeCanvas);
resizeCanvas();

canvas.addEventListener("mousemove", (event) => {
  const rect = canvas.getBoundingClientRect();
  const x = event.clientX - rect.left;
  const y = event.clientY - rect.top;
  hoverFishId = hitTestFish(x, y);
});

canvas.addEventListener("mouseleave", () => {
  hoverFishId = null;
});

canvas.addEventListener("click", () => {
  if (hoverFishId !== null) {
    selectedFishId = hoverFishId;
  }
});

async function postControl(payload) {
  const response = await fetch("/api/control", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const state = await response.json();
  applyState(state);
}

speed.addEventListener("input", () => {
  speedValue.textContent = `${speed.value}x`;
});

speed.addEventListener("change", () => {
  postControl({ speed: Number(speed.value) });
});

deliberation.addEventListener("change", () => {
  postControl({ deliberation_enabled: deliberation.checked });
});

reset.addEventListener("click", () => postControl({ action: "reset" }));
randomize.addEventListener("click", () => postControl({ action: "randomize_environment" }));

function syncControls(state) {
  speed.value = state.config.speed;
  speedValue.textContent = `${state.config.speed}x`;
  deliberation.checked = Boolean(state.config.deliberation_enabled);
}

async function fetchState() {
  if (stateFetchInFlight) return;
  stateFetchInFlight = true;
  try {
    const response = await fetch("/api/state");
    applyState(await response.json());
    statusEl.textContent = "live";
  } catch (error) {
    statusEl.textContent = "offline";
  } finally {
    stateFetchInFlight = false;
  }
}

async function fetchFrame() {
  if (frameFetchInFlight) return;
  frameFetchInFlight = true;
  try {
    const response = await fetch("/api/frame");
    applyFrame(await response.json());
    statusEl.textContent = "live";
  } catch (error) {
    statusEl.textContent = "offline";
  } finally {
    frameFetchInFlight = false;
  }
}

function applyState(state) {
  latestState = state;
  latestEnvironment = state.environment;
  syncControls(state);
  applyFrame({
    schema: "aquagenesys.frame.from_state",
    tick: state.tick,
    config: state.config,
    environment: { width: state.environment.width, height: state.environment.height, signature: state.environment.signature },
    fish: state.fish || state.organisms || [],
    telemetry: state.telemetry,
  });
  updateTelemetry(state.telemetry);
}

function applyFrame(frame) {
  if (currentFrame && frame.tick < currentFrame.tick) return;
  previousFrame = currentFrame;
  currentFrame = { ...frame, receivedAt: performance.now() };
  updateTelemetry(frame.telemetry);
}

async function pollState() {
  await fetchState();
  window.setTimeout(pollState, STATE_POLL_MS);
}

async function pollFrame() {
  await fetchFrame();
  window.setTimeout(pollFrame, FRAME_POLL_MS);
}

function updateTelemetry(telemetry) {
  if (!telemetry) return;
  document.getElementById("puddleState").hidden = !telemetry.dead_puddle;
  document.getElementById("tick").textContent = telemetry.tick;
  document.getElementById("population").textContent = telemetry.population;
  document.getElementById("health").textContent = Number(telemetry.average_health || 0).toFixed(2);
  document.getElementById("stress").textContent = Number(telemetry.average_stress || 0).toFixed(2);
  document.getElementById("modelCalls").textContent = telemetry.model?.calls ?? 0;
  document.getElementById("modelPending").textContent = telemetry.model?.pending ?? 0;
  fillList("decisions", telemetry.agent_decisions || [], (item) => [
    `${item.tick} #${item.fish_id} ${item.action}`,
    `${item.source}: ${item.outcome}`,
  ]);
  fillList("events", telemetry.recent_events || [], (item) => [eventLabel(item), eventDetail(item)]);
  fillList("clusters", telemetry.species_clusters || [], (item) => [item.label, `${item.size} ${item.metabolism}`]);
  fillList("deaths", Object.entries(telemetry.deaths_by_cause || {}), (item) => [item[0], item[1]]);
}

function eventLabel(event) {
  return `${event.tick} ${String(event.kind).replaceAll("_", " ")}`;
}

function eventDetail(event) {
  if (event.kind === "birth") return `#${event.child}`;
  if (event.kind === "death") return event.cause || "";
  if (event.kind === "model_deliberation_queued") return `pending ${event.pending}`;
  if (event.kind === "model_deliberation") return `${event.action} ttl ${event.ttl}`;
  if (event.kind === "model_deliberation_failed") return "fallback";
  if (event.kind === "extinction") return event.cause_guess || "dead puddle";
  if (event.kind === "debug_founder_reseed") return `${event.count} debug`;
  if (event.kind === "environment_randomized") return "new chemistry";
  if (event.value !== undefined) return event.value;
  return "";
}

function fillList(id, items, render) {
  const node = document.getElementById(id);
  node.innerHTML = "";
  for (const item of items.slice(0, 8)) {
    const [left, right] = render(item);
    const li = document.createElement("li");
    const label = document.createElement("span");
    const value = document.createElement("b");
    label.textContent = left;
    value.textContent = right;
    li.append(label, value);
    node.appendChild(li);
  }
}

function rebuildField(env) {
  if (!env || !env.fields) return;
  const signature = JSON.stringify(env.signature);
  if (signature === fieldSignature) return;
  fieldSignature = signature;
  const viewWidth = env.view_width || env.width;
  const viewHeight = env.view_height || env.height;
  fieldCanvas.width = viewWidth;
  fieldCanvas.height = viewHeight;
  const fctx = fieldCanvas.getContext("2d");
  const image = fctx.createImageData(viewWidth, viewHeight);
  const fields = env.fields;
  let i = 0;
  for (let y = 0; y < viewHeight; y += 1) {
    for (let x = 0; x < viewWidth; x += 1) {
      const depth = fields.depth[y][x];
      const oxygen = fields.oxygen[y][x];
      const temperature = fields.temperature[y][x];
      const food = fields.food[y][x];
      const plankton = fields.plankton[y][x];
      const toxins = fields.toxins[y][x];
      const turbidity = fields.turbidity[y][x];
      const shelter = fields.shelter[y][x];
      const obstacle = fields.obstacle[y][x];
      const pressure = fields.population_pressure[y][x];
      image.data[i++] = Math.min(255, 18 + temperature * 88 + toxins * 122 + shelter * 44 + obstacle * 80);
      image.data[i++] = Math.min(255, 30 + food * 96 + plankton * 90 + oxygen * 74 - turbidity * 28);
      image.data[i++] = Math.min(255, 46 + depth * 134 + oxygen * 42 + pressure * 80);
      image.data[i++] = 255;
    }
  }
  fctx.putImageData(image, 0, 0);
}

function render() {
  const rect = canvas.getBoundingClientRect();
  ctx.clearRect(0, 0, rect.width, rect.height);
  const frame = currentFrame;
  const env = latestEnvironment || frame?.environment;
  if (!frame || !env) {
    requestAnimationFrame(render);
    return;
  }
  rebuildField(latestEnvironment);
  ctx.imageSmoothingEnabled = false;
  if (fieldCanvas.width > 0) {
    ctx.drawImage(fieldCanvas, 0, 0, rect.width, rect.height);
  }
  ctx.imageSmoothingEnabled = true;

  const sx = rect.width / env.width;
  const sy = rect.height / env.height;
  drawShelters(latestEnvironment?.shelter_centers || [], sx, sy);
  const fishList = interpolatedFish(performance.now());
  drawFish(fishList, sx, sy);
  updateInspector();
  if (frame.telemetry?.dead_puddle) {
    drawDeadPuddle(rect);
  }
  requestAnimationFrame(render);
}

function interpolatedFish(now) {
  const current = currentFrame;
  if (!current) return [];
  const previous = previousFrame;
  const priorById = new Map((previous?.fish || []).map((fish) => [fish.id, fish]));
  const frameDeltaMs = previous ? Math.max(160, current.receivedAt - previous.receivedAt) : 1000;
  const tickDelta = previous ? Math.max(1, current.tick - previous.tick) : 1;
  const ticksPerMs = tickDelta / frameDeltaMs;
  const renderTime = now - INTERPOLATION_DELAY_MS;
  return current.fish.map((fish) => {
    const prior = priorById.get(fish.id);
    let x = fish.x;
    let y = fish.y;
    if (prior && renderTime >= previous.receivedAt && renderTime <= current.receivedAt) {
      const alpha = clamp((renderTime - previous.receivedAt) / frameDeltaMs, 0, 1);
      x = prior.x + (fish.x - prior.x) * alpha;
      y = prior.y + (fish.y - prior.y) * alpha;
    } else if (renderTime > current.receivedAt) {
      const dtTicks = clamp((renderTime - current.receivedAt) * ticksPerMs, 0, 2.4);
      x = fish.x + fish.vx * dtTicks;
      y = fish.y + fish.vy * dtTicks;
    }
    return { ...fish, renderX: x, renderY: y };
  });
}

function drawShelters(centers, sx, sy) {
  ctx.save();
  ctx.strokeStyle = "rgba(210, 220, 190, 0.18)";
  ctx.fillStyle = "rgba(28, 34, 28, 0.18)";
  for (const shelter of centers) {
    ctx.beginPath();
    ctx.ellipse(shelter.x * sx, shelter.y * sy, shelter.radius * sx, shelter.radius * sy * 0.7, 0, 0, Math.PI * 2);
    ctx.fill();
    ctx.stroke();
  }
  ctx.restore();
}

function drawFish(fishList, sx, sy) {
  renderedFish = [];
  for (const fish of fishList) {
    const x = fish.renderX * sx;
    const y = fish.renderY * sy;
    const r = Math.max(3.4, fish.radius * Math.min(sx, sy));
    renderedFish.push({ id: fish.id, x, y, r: r * 1.8, fish });
    const angle = Math.atan2(fish.vy, fish.vx || 0.001);
    const pulse = Math.sin((currentFrame.tick + fish.id * 7) * 0.18);
    const isHover = fish.id === hoverFishId;
    const isSelected = fish.id === selectedFishId;
    ctx.save();
    ctx.translate(x, y);
    ctx.rotate(angle);

    const healthAlpha = 0.46 + fish.health * 0.46;
    ctx.globalAlpha = healthAlpha;
    ctx.strokeStyle = fish.genome.accent_color;
    ctx.lineWidth = Math.max(1, r * 0.20);
    ctx.beginPath();
    ctx.moveTo(-r * 0.9, 0);
    ctx.quadraticCurveTo(-r * (1.6 + fish.hunger * 0.25), pulse * r * 0.55, -r * 2.12, pulse * r * 0.18);
    ctx.stroke();

    ctx.globalAlpha = 1;
    ctx.fillStyle = fish.genome.color;
    ctx.strokeStyle = stateColor(fish.body_state);
    ctx.lineWidth = Math.max(1, r * 0.12);
    ctx.beginPath();
    ctx.ellipse(0, 0, r * (1.16 + fish.genome.body_size * 0.16), r * 0.72, 0, 0, Math.PI * 2);
    ctx.fill();
    ctx.stroke();

    ctx.fillStyle = "rgba(10, 15, 16, 0.74)";
    ctx.beginPath();
    ctx.arc(r * 0.56, -r * 0.16, Math.max(1.1, r * 0.12), 0, Math.PI * 2);
    ctx.fill();

    if (fish.genome.metabolism === "predator") {
      ctx.fillStyle = "rgba(20, 8, 8, 0.75)";
      ctx.beginPath();
      ctx.moveTo(r * 0.82, -r * 0.26);
      ctx.lineTo(r * 1.22, 0);
      ctx.lineTo(r * 0.82, r * 0.26);
      ctx.closePath();
      ctx.fill();
    }

    if (fish.decision.source === "model" || fish.active_intent) {
      ctx.strokeStyle = "rgba(255, 239, 150, 0.82)";
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.arc(0, 0, r * 1.55, 0, Math.PI * 2);
      ctx.stroke();
    }
    if (isHover || isSelected) {
      ctx.strokeStyle = isSelected ? "rgba(255, 255, 255, 0.95)" : "rgba(123, 212, 176, 0.85)";
      ctx.lineWidth = isSelected ? 2 : 1;
      ctx.beginPath();
      ctx.arc(0, 0, r * 1.95, 0, Math.PI * 2);
      ctx.stroke();
    }
    ctx.restore();
  }
}

function hitTestFish(x, y) {
  let best = null;
  let bestDistance = Infinity;
  for (const item of renderedFish) {
    const dx = x - item.x;
    const dy = y - item.y;
    const distance = Math.hypot(dx, dy);
    if (distance <= item.r && distance < bestDistance) {
      best = item.id;
      bestDistance = distance;
    }
  }
  return best;
}

function updateInspector() {
  const fish = findFish(selectedFishId) || findFish(hoverFishId);
  const empty = document.getElementById("emptyInspector");
  const details = document.getElementById("fishInspector");
  if (!fish) {
    empty.hidden = false;
    details.hidden = true;
    return;
  }
  empty.hidden = true;
  details.hidden = false;
  document.getElementById("fishId").textContent = `#${fish.id} L${fish.lineage} G${fish.generation}`;
  document.getElementById("fishSpecies").textContent = `${fish.species_id} / ${fish.genome.archetype}`;
  document.getElementById("fishBody").textContent = `${fish.body_state} ${fish.genome.metabolism}`;
  document.getElementById("fishDecision").textContent = `${fish.decision.source}: ${fish.decision.kind}`;
  document.getElementById("fishIntent").textContent = fish.active_intent
    ? `${fish.active_intent.kind} ttl ${fish.model_intent_ttl}`
    : fish.model_pending
      ? "pending"
      : "none";
  document.getElementById("fishEnergy").textContent = `${Number(fish.energy).toFixed(1)} / h ${Number(fish.hunger).toFixed(2)}`;
}

function findFish(id) {
  if (id === null || !currentFrame) return null;
  return (currentFrame.fish || []).find((fish) => fish.id === id) || null;
}

function stateColor(state) {
  if (state === "failing") return "rgba(255, 110, 116, 0.86)";
  if (state === "starving") return "rgba(235, 185, 84, 0.82)";
  if (state === "panicked") return "rgba(130, 210, 255, 0.82)";
  if (state === "breeding") return "rgba(228, 168, 235, 0.84)";
  return "rgba(236, 250, 244, 0.58)";
}

function drawDeadPuddle(rect) {
  ctx.save();
  ctx.fillStyle = "rgba(30, 10, 12, 0.22)";
  ctx.fillRect(0, 0, rect.width, rect.height);
  ctx.restore();
}

function clamp(value, low, high) {
  return Math.max(low, Math.min(high, value));
}

pollState();
pollFrame();
render();

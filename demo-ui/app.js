const questions = [
  {
    id: "wear",
    label: "Wear duration",
    options: ["7 days continuous", "24 hours", "During workouts only"],
  },
  {
    id: "power",
    label: "Power strategy",
    options: ["Rechargeable LiPo", "Disposable coin cell", "External dock power"],
  },
  {
    id: "priority",
    label: "Layout priority",
    options: ["Patient safety first", "Smallest board", "Strongest BLE range"],
  },
];

const parts = [
  { id: "ELEC_A", label: "E1", type: "electrode", x: 10, y: 15, w: 6, h: 6 },
  { id: "ELEC_B", label: "E2", type: "electrode", x: 26, y: 15, w: 6, h: 6 },
  { id: "AFE", label: "AFE", type: "sensor", x: 34, y: 15, w: 5, h: 5 },
  { id: "REG", label: "REG", type: "power", x: 44, y: 15, w: 3, h: 3 },
  { id: "MCU", label: "MCU", type: "digital", x: 43, y: 24, w: 6, h: 6 },
  { id: "LIPO", label: "CELL", type: "battery", x: 62, y: 15, w: 30, h: 16 },
  { id: "ANT", label: "ANT", type: "rf", x: 85, y: 24, w: 3.2, h: 1.6 },
  { id: "CHARGE", label: "PAD", type: "connector", x: 86, y: 8, w: 8, h: 4 },
];

const constraintStyles = {
  thermal: { label: "Thermal", color: "#d33b2f", fill: "rgba(211,59,47,0.16)" },
  conducted: { label: "Conducted", color: "#9b6a1c", fill: "rgba(155,106,28,0.16)" },
  radiated: { label: "Radiated", color: "#3266c8", fill: "rgba(50,102,200,0.15)" },
  mechanical: { label: "Mechanical", color: "#5e6a73", fill: "rgba(94,106,115,0.15)" },
  safety: { label: "Safety", color: "#16824a", fill: "rgba(22,130,74,0.14)" },
};

const revisions = [
  {
    title: "Naive placement",
    stage: "Review",
    summary: { pass: 21, fail: 6 },
    note: "I placed the board by schematic convenience. Now I am checking the mission constraints.",
    placements: {
      ELEC_A: [10, 15],
      ELEC_B: [26, 15],
      AFE: [34, 15],
      REG: [44, 15],
      MCU: [43, 24],
      LIPO: [62, 15],
      ANT: [85, 24],
      CHARGE: [86, 8],
    },
    findings: [
      {
        id: "thermal-afe",
        category: "thermal",
        status: "fail",
        title: "Heat reaches ECG front end",
        target: ["REG", "AFE"],
        message: "Regulator thermal zone overlaps the 24-bit analog front end.",
        action: "Move sensing away from sustained heat.",
      },
      {
        id: "rf-keepout",
        category: "radiated",
        status: "fail",
        title: "Antenna keep-out obstructed",
        target: ["ANT"],
        message: "Charge trace crosses the 2.4 GHz antenna clearance volume.",
        action: "Rotate antenna toward free space and reroute charge.",
      },
      {
        id: "access",
        category: "mechanical",
        status: "fail",
        title: "Charge pads miss enclosure window",
        target: ["CHARGE"],
        message: "The sealed shell leaves only one reachable charge opening.",
        action: "Move pads to the rear access edge.",
      },
      {
        id: "cell-headroom",
        category: "mechanical",
        status: "fail",
        title: "Cell exceeds enclosure headroom",
        target: ["LIPO"],
        message: "Advisor found varta_cp1254 is 5.6 mm max, but the enclosure allows 4.0 mm.",
        action: "Flag BOM fiction and source a real pilot-safe cell.",
      },
      {
        id: "charger-gap",
        category: "safety",
        status: "fail",
        title: "Charging path is not pilot-ready",
        target: ["LIPO", "CHARGE"],
        message: "No charger or battery protection module is present in the demo BOM.",
        action: "Add charger/protection alternatives before export.",
      },
      {
        id: "rail-architecture",
        category: "conducted",
        status: "fail",
        title: "3.3 V rail loses margin",
        target: ["REG", "LIPO"],
        message: "tps62740 cannot hold 3.3 V once the cell falls below about 4.0 V.",
        action: "Compare tps63020 or another buck-boost option.",
      },
    ],
  },
  {
    title: "Revision 1",
    stage: "Revising",
    summary: { pass: 24, fail: 3 },
    note: "I separated heat from sensing and aligned charging. The RF keep-out still needs attention.",
    placements: {
      ELEC_A: [72, 15],
      ELEC_B: [35, 24],
      AFE: [47, 5],
      REG: [26, 5],
      MCU: [19, 10],
      LIPO: [53, 15],
      ANT: [82, 24],
      CHARGE: [12, 15],
    },
    findings: [
      {
        id: "thermal-afe",
        category: "thermal",
        status: "pass",
        title: "Heat separated from sensing",
        target: ["REG", "AFE"],
        message: "The front end is outside the regulator heat zone.",
        action: "Keep analog island isolated.",
      },
      {
        id: "rf-keepout",
        category: "radiated",
        status: "fail",
        title: "Antenna keep-out still tight",
        target: ["ANT"],
        message: "The keep-out faces crowded board space near the cell.",
        action: "Put the antenna on an exposed edge.",
      },
      {
        id: "cell-headroom",
        category: "mechanical",
        status: "fail",
        title: "Battery height still blocks build",
        target: ["LIPO"],
        message: "Moving the cell does not fix the 1.6 mm enclosure interference.",
        action: "Swap part or thicken enclosure before pilot.",
      },
      {
        id: "charger-gap",
        category: "safety",
        status: "fail",
        title: "Charging protection unresolved",
        target: ["LIPO", "CHARGE"],
        message: "Advisor recommends bq24040 over mcp73831 for thermal pad and TS pin.",
        action: "Ask human to approve charger role change.",
      },
    ],
  },
  {
    title: "MissionPCB layout",
    stage: "Ready",
    summary: { pass: 26, fail: 0 },
    note: "The layout now clears the mission-critical constraints and preserves service access.",
    placements: {
      ELEC_A: [71, 15],
      ELEC_B: [34, 24.5],
      AFE: [46, 4],
      REG: [26, 5],
      MCU: [19.5, 10],
      LIPO: [52.5, 15],
      ANT: [46.1, 24.6],
      CHARGE: [12, 15],
    },
    findings: [
      {
        id: "thermal-afe",
        category: "thermal",
        status: "pass",
        title: "Heat clear",
        target: ["REG", "AFE"],
        message: "ECG sensing is outside the heat zone.",
        action: "Ready for thermal bench validation.",
      },
      {
        id: "rf-keepout",
        category: "radiated",
        status: "pass",
        title: "RF keep-out clear",
        target: ["ANT"],
        message: "The antenna faces free space and the charge path avoids it.",
        action: "Ready for link-margin validation.",
      },
      {
        id: "access",
        category: "mechanical",
        status: "pass",
        title: "Charge access aligned",
        target: ["CHARGE"],
        message: "Pogo pads register with the sealed charge window.",
        action: "Export model package.",
      },
      {
        id: "bom-advisor",
        category: "safety",
        status: "pass",
        title: "Pilot blockers elevated",
        target: ["LIPO", "REG"],
        message: "Advisor records CP1254 certification, charger, protection, and buck-boost choices as open decisions.",
        action: "Export BOM review with citations.",
      },
    ],
  },
];

const considerations = [
  ["Skin contact", "Worn continuously, so heat near electrodes becomes a patient-safety constraint."],
  ["Microvolt signal", "The ECG front end needs separation from switching and digital noise."],
  ["BLE radio", "The antenna needs a keep-out volume, not just a connected trace."],
  ["Sealed charging", "Pogo pads must align to the only accessible enclosure window."],
  ["Human override", "User comments and pins become constraints for the next API call."],
];

let state = {
  revision: 0,
  selectedPart: null,
  selectedFinding: null,
  activeConstraintLayer: "all",
  activeTool: "select",
  camera: { scale: 1, x: 0, y: 0 },
  isPanning: false,
  lastPointer: null,
  pointerMoved: false,
  comments: [
    { anchor: "ANT", text: "Can we keep this edge free for BLE range?" },
  ],
};

const els = {
  canvas: document.querySelector("#modelCanvas"),
  startButton: document.querySelector("#startButton"),
  recommendedButton: document.querySelector("#recommendedButton"),
  interviewList: document.querySelector("#interviewList"),
  chatLog: document.querySelector("#chatLog"),
  considerations: document.querySelector("#considerations"),
  findings: document.querySelector("#findings"),
  comments: document.querySelector("#comments"),
  revisionSlider: document.querySelector("#revisionSlider"),
  prevRevision: document.querySelector("#prevRevision"),
  nextRevision: document.querySelector("#nextRevision"),
  revisionLabel: document.querySelector("#revisionLabel"),
  verdictLabel: document.querySelector("#verdictLabel"),
  selectedLabel: document.querySelector("#selectedLabel"),
  timelineStatus: document.querySelector("#timelineStatus"),
  stagePill: document.querySelector("#stagePill"),
  addCommentButton: document.querySelector("#addCommentButton"),
  exportButton: document.querySelector("#exportButton"),
  exportMenu: document.querySelector("#exportMenu"),
  autoMode: document.querySelector("#autoMode"),
  layerList: document.querySelector("#layerList"),
  constraintChips: document.querySelectorAll(".constraint-chip"),
};

const ctx = els.canvas.getContext("2d");
let hitRegions = [];
const artifactImage = new Image();
artifactImage.src = "./assets/cad-closeup.png";

const artifactPoints = {
  AFE: { x: 395, y: 230 },
  REG: { x: 1205, y: 390 },
  MCU: { x: 540, y: 600 },
  CHARGE: { x: 958, y: 790 },
  LIPO: { x: 1130, y: 382 },
  ANT: { x: 150, y: 72 },
  ELEC_A: { x: 185, y: 185 },
  ELEC_B: { x: 244, y: 140 },
};

function constraintApi(currentState) {
  const rev = revisions[currentState.revision];
  return {
    considerations,
    findings: rev.findings,
    summary: rev.summary,
    stage: rev.stage,
    note: rev.note,
  };
}

function modelApi(currentState) {
  const rev = revisions[currentState.revision];
  return {
    board: { x: 0, y: 0, w: 92, h: 30 },
    enclosure: { x: -4, y: -5, w: 100, h: 40 },
    placements: parts.map((part) => {
      const [x, y] = rev.placements[part.id];
      return { ...part, x, y };
    }),
    heatZones: [{ partId: "REG", radius: 10 }],
    keepouts: [{ partId: "ANT", w: 8, h: 8, direction: "up" }],
  };
}

function addMessage(kind, text) {
  const node = document.createElement("div");
  node.className = `message ${kind}`;
  node.textContent = text;
  els.chatLog.appendChild(node);
  els.chatLog.scrollTop = els.chatLog.scrollHeight;
}

function renderInterview() {
  els.interviewList.innerHTML = "";
  questions.forEach((question) => {
    const node = document.createElement("label");
    node.className = "question";
    node.innerHTML = `<strong>${question.label}</strong><span class="muted">Recommended for the demo is preselected.</span>`;
    const select = document.createElement("select");
    question.options.forEach((option) => {
      const item = document.createElement("option");
      item.value = option;
      item.textContent = option;
      select.appendChild(item);
    });
    node.appendChild(select);
    els.interviewList.appendChild(node);
  });
}

function renderConsiderations(api) {
  els.considerations.innerHTML = "";
  api.considerations.forEach(([title, body]) => {
    const node = document.createElement("div");
    node.className = "consideration";
    node.innerHTML = `<strong>${title}</strong><div class="muted">${body}</div>`;
    els.considerations.appendChild(node);
  });
}

function renderFindings(api) {
  els.findings.innerHTML = "";
  api.findings.forEach((finding) => {
    const node = document.createElement("button");
    node.className = `finding ${finding.status}`;
    node.type = "button";
    const style = constraintStyles[finding.category] || constraintStyles.safety;
    node.innerHTML = `<div class="finding-heading"><span class="category-dot" style="background:${style.color}"></span><strong>${finding.title}</strong></div><div class="finding-meta">${style.label} constraint</div><div class="muted">${finding.message}</div><div class="muted">${finding.action}</div>`;
    node.addEventListener("click", () => {
      state.selectedFinding = finding.id;
      state.selectedPart = finding.target[0];
      state.activeConstraintLayer = finding.category || "all";
      render();
    });
    els.findings.appendChild(node);
  });
}

function renderComments() {
  els.comments.innerHTML = "";
  state.comments.forEach((comment) => {
    const node = document.createElement("div");
    node.className = "comment";
    node.innerHTML = `<strong>${comment.anchor}</strong><div class="muted">${comment.text}</div>`;
    els.comments.appendChild(node);
  });
}

function renderLayers() {
  const layers = [
    ["Board Body", "#2a3c1b", true, ""],
    ["Plated Barrels", "#c99e18", true, ""],
    ["F.Cu", "#c8a600", true, ""],
    ["B.Cu", "#b99d11", true, ""],
    ["Adhesive", "#111111", false, ""],
    ["Solder Paste", "#888888", true, ""],
    ["F.Silkscreen", "#efefef", true, ""],
    ["B.Silkscreen", "#efefef", true, ""],
    ["F.Mask", "#28533a", true, ""],
    ["B.Mask", "#28533a", true, ""],
    ["User.Drawings", "#000000", false, ""],
    ["User.Comments", "#000000", false, ""],
    ["User.1", "#cfcfcf", true, ""],
    ["User.2", "#4a91d9", true, ""],
    ["User.3", "#a5d8d0", true, ""],
    ["User.4", "#e1ce48", true, ""],
    ["Through-hole Models", "#444444", true, "layer-indent"],
    ["SMD Models", "#444444", true, "layer-indent"],
    ["Virtual Models", "#444444", true, "layer-indent"],
    ["Models not in POS File", "#444444", true, "layer-indent"],
    ["Models marked DNP", "#444444", false, "layer-indent"],
    ["Model Bounding Boxes", "#444444", false, "layer-indent"],
    ["Values", "#444444", true, ""],
    ["References", "#444444", true, ""],
    ["Footprint Text", "#444444", true, ""],
    ["Off-board Silkscreen", "#444444", false, ""],
    ["3D Navigator", "#444444", true, ""],
    ["Background Start", "#c5c4df", true, "layer-indent"],
    ["Background End", "#777895", true, "layer-indent"],
  ];
  els.layerList.innerHTML = "";
  layers.forEach(([name, color, visible, extra]) => {
    const row = document.createElement("div");
    row.className = `layer-row ${visible ? "" : "dim"} ${extra}`;
    row.innerHTML = `<span class="swatch" style="background:${color}"></span><span class="eye">${visible ? "◉" : "⊘"}</span><span>${name}</span>`;
    els.layerList.appendChild(row);
  });
}

function canvasPointToBoard(evt) {
  const rect = els.canvas.getBoundingClientRect();
  const x = (evt.clientX - rect.left) * (els.canvas.width / rect.width);
  const y = (evt.clientY - rect.top) * (els.canvas.height / rect.height);
  return { x, y };
}

function resetCameraForImage() {
  if (!artifactImage.naturalWidth || !artifactImage.naturalHeight) return;
  const panelWidth = 218;
  const availableWidth = els.canvas.width - panelWidth;
  const scale = Math.min(availableWidth / artifactImage.naturalWidth, els.canvas.height / artifactImage.naturalHeight) * 1.02;
  state.camera.scale = scale;
  state.camera.x = (availableWidth - artifactImage.naturalWidth * scale) / 2;
  state.camera.y = (els.canvas.height - artifactImage.naturalHeight * scale) / 2;
}

function imageToCanvas(point) {
  return {
    x: state.camera.x + point.x * state.camera.scale,
    y: state.camera.y + point.y * state.camera.scale,
  };
}

function canvasToImage(point) {
  return {
    x: (point.x - state.camera.x) / state.camera.scale,
    y: (point.y - state.camera.y) / state.camera.scale,
  };
}

function getFit(scene) {
  const margin = 86;
  const rightPanel = 218;
  const scale = Math.min(
    (els.canvas.width - rightPanel - margin * 2) / 116,
    (els.canvas.height - margin * 2) / 82,
  );
  return {
    scale,
    ox: (els.canvas.width - rightPanel) / 2,
    oy: els.canvas.height * 0.56,
  };
}

function project(fit, x, y, z = 0) {
  const px = fit.ox + (x - y * 0.72) * fit.scale;
  const py = fit.oy + (x * 0.18 + y * 0.48 - z * 1.25) * fit.scale;
  return [px, py];
}

function poly(points, fill, stroke = "#111", width = 1) {
  ctx.beginPath();
  points.forEach(([x, y], index) => {
    if (index === 0) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
  });
  ctx.closePath();
  ctx.fillStyle = fill;
  ctx.fill();
  ctx.strokeStyle = stroke;
  ctx.lineWidth = width;
  ctx.stroke();
}

function rect3d(fit, x, y, w, h, z, height, fill, stroke = "#111", lineWidth = 1) {
  const top = [
    project(fit, x - w / 2, y - h / 2, z + height),
    project(fit, x + w / 2, y - h / 2, z + height),
    project(fit, x + w / 2, y + h / 2, z + height),
    project(fit, x - w / 2, y + h / 2, z + height),
  ];
  const side = [
    project(fit, x + w / 2, y - h / 2, z),
    project(fit, x + w / 2, y + h / 2, z),
    project(fit, x + w / 2, y + h / 2, z + height),
    project(fit, x + w / 2, y - h / 2, z + height),
  ];
  const front = [
    project(fit, x - w / 2, y + h / 2, z),
    project(fit, x + w / 2, y + h / 2, z),
    project(fit, x + w / 2, y + h / 2, z + height),
    project(fit, x - w / 2, y + h / 2, z + height),
  ];
  poly(side, shade(fill, -28), stroke, lineWidth);
  poly(front, shade(fill, -42), stroke, lineWidth);
  poly(top, fill, stroke, lineWidth);
  return top;
}

function shade(hex, amount) {
  const raw = hex.replace("#", "");
  const num = parseInt(raw, 16);
  const clamp = (v) => Math.max(0, Math.min(255, v));
  const r = clamp((num >> 16) + amount);
  const g = clamp(((num >> 8) & 255) + amount);
  const b = clamp((num & 255) + amount);
  return `rgb(${r}, ${g}, ${b})`;
}

function partColor(type) {
  return {
    electrode: "#e7e7df",
    sensor: "#2c5aa0",
    power: "#c98722",
    digital: "#111111",
    battery: "#315f42",
    rf: "#5c4c86",
    connector: "#b8a15d",
  }[type] || "#777";
}

function drawScene(scene, api) {
  ctx.clearRect(0, 0, els.canvas.width, els.canvas.height);
  hitRegions = [];

  if (artifactImage.complete && artifactImage.naturalWidth) {
    drawCapturedScene(scene, api);
    return;
  }

  const fit = getFit(scene);

  drawBoard(fit, scene);
  drawCopperAndSilk(fit);
  drawTrace(fit, state.revision);
  drawZones(fit, scene, api);
  [...scene.placements].sort((a, b) => a.y - b.y).forEach((part) => drawPart(fit, part, api));
  drawComments(fit, scene);
  drawAxisGizmo();
  drawStatusLine(api);
}

function drawCapturedScene(scene, api) {
  ctx.save();
  ctx.fillStyle = "#7c7e99";
  ctx.fillRect(0, 0, els.canvas.width, els.canvas.height);
  ctx.drawImage(
    artifactImage,
    state.camera.x,
    state.camera.y,
    artifactImage.naturalWidth * state.camera.scale,
    artifactImage.naturalHeight * state.camera.scale,
  );
  ctx.restore();

  Object.entries(artifactPoints).forEach(([id, point]) => {
    const canvas = imageToCanvas(point);
    hitRegions.push({
      id,
      minX: canvas.x - 28,
      maxX: canvas.x + 28,
      minY: canvas.y - 28,
      maxY: canvas.y + 28,
    });
  });

  drawCapturedConstraintOverlays(api);
  drawCapturedComments();
  drawAxisGizmo();
  drawStatusLine(api);
}

function drawCapturedConstraintOverlays(api) {
  const visibleFindings = api.findings.filter((finding) => (
    state.activeConstraintLayer === "all" || finding.category === state.activeConstraintLayer
  ));
  const selected = visibleFindings.find((finding) => finding.id === state.selectedFinding);
  const failing = visibleFindings.filter((finding) => finding.status === "fail");
  const findingsToDraw = selected ? [selected] : failing.length ? failing : visibleFindings;

  findingsToDraw.forEach((finding, index) => {
    const style = constraintStyles[finding.category] || constraintStyles.safety;
    const points = finding.target.map((id) => artifactPoints[id]).filter(Boolean).map(imageToCanvas);
    if (!points.length) return;
    const anchor = points[0];
    ctx.save();
    ctx.strokeStyle = style.color;
    ctx.fillStyle = style.fill;
    ctx.lineWidth = finding.status === "fail" ? 3 : 2;
    ctx.setLineDash(finding.status === "fail" ? [6, 4] : []);
    points.forEach((point) => {
      ctx.beginPath();
      ctx.arc(point.x, point.y, 34, 0, Math.PI * 2);
      ctx.fill();
      ctx.stroke();
    });
    if (points.length > 1) {
      ctx.beginPath();
      ctx.moveTo(points[0].x, points[0].y);
      points.slice(1).forEach((point) => ctx.lineTo(point.x, point.y));
      ctx.stroke();
    }
    ctx.setLineDash([]);
    ctx.restore();
    drawScreenCallout(
      anchor.x + 44,
      anchor.y - 48 - index * 8,
      `${style.label}: ${finding.title}`,
      finding.message,
      finding.category,
      finding.status === "fail",
    );
  });
}

function drawScreenCallout(x, y, title, body, category, failing) {
  const style = constraintStyles[category] || constraintStyles.safety;
  const width = 286;
  const height = 66;
  const rightLimit = els.canvas.width - 238;
  const boxX = Math.max(12, Math.min(x, rightLimit - width));
  const boxY = Math.max(48, Math.min(y, els.canvas.height - 98));
  ctx.save();
  ctx.fillStyle = failing ? "rgba(255,255,255,0.97)" : "rgba(18,18,18,0.88)";
  ctx.strokeStyle = style.color;
  ctx.lineWidth = 1.6;
  ctx.beginPath();
  ctx.roundRect(boxX, boxY, width, height, 6);
  ctx.fill();
  ctx.stroke();
  ctx.fillStyle = style.color;
  ctx.beginPath();
  ctx.arc(boxX + 14, boxY + 18, 5, 0, Math.PI * 2);
  ctx.fill();
  ctx.fillStyle = failing ? "#111" : "#fff";
  ctx.font = "700 12px Inter, system-ui, sans-serif";
  ctx.textAlign = "left";
  ctx.fillText(title, boxX + 26, boxY + 22);
  ctx.fillStyle = failing ? "#4b4b47" : "#d9d9d2";
  ctx.font = "12px Inter, system-ui, sans-serif";
  wrapText(body, boxX + 14, boxY + 42, width - 28, 15, 2);
  ctx.restore();
}

function wrapText(text, x, y, maxWidth, lineHeight, maxLines) {
  const words = text.split(" ");
  let line = "";
  let lines = 0;
  words.forEach((word) => {
    const test = line ? `${line} ${word}` : word;
    if (ctx.measureText(test).width > maxWidth && line) {
      if (lines < maxLines) ctx.fillText(line, x, y + lines * lineHeight);
      line = word;
      lines += 1;
    } else {
      line = test;
    }
  });
  if (line && lines < maxLines) ctx.fillText(line, x, y + lines * lineHeight);
}

function drawCapturedComments() {
  state.comments.forEach((comment, index) => {
    const point = artifactPoints[comment.anchor];
    if (!point) return;
    const canvas = imageToCanvas(point);
    ctx.beginPath();
    ctx.arc(canvas.x + 34, canvas.y - 34, 9, 0, Math.PI * 2);
    ctx.fillStyle = "#111";
    ctx.fill();
    ctx.fillStyle = "#fff";
    ctx.font = "700 10px Inter, system-ui, sans-serif";
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.fillText(String(index + 1), canvas.x + 34, canvas.y - 34);
  });
}

function drawBoard(fit, scene) {
  ctx.save();
  ctx.shadowColor = "rgba(0, 0, 0, 0.30)";
  ctx.shadowBlur = 26;
  ctx.shadowOffsetY = 20;
  rect3d(fit, 46, 15, scene.board.w, scene.board.h, -1.6, 1.6, "#092b18", "#06170e", 1.2);
  ctx.restore();
}

function drawCopperAndSilk(fit) {
  for (let i = 0; i < 22; i += 1) {
    drawPad(fit, 53, 3 + i * 1.05, 0.55);
    drawPad(fit, 62, 3 + i * 1.05, 0.55);
  }
  drawSilkBox(fit, 58, 18, 15, 20, "USB");
  drawSilkBox(fit, 22, 16, 18, 12, "Left / Right");
  ["R6", "R8", "R9", "P1", "P5"].forEach((label, i) => {
    const p = project(fit, 34 + i * 9, 24 - (i % 2) * 12, 0.12);
    ctx.fillStyle = "rgba(235,235,225,0.85)";
    ctx.font = "700 11px Inter, system-ui, sans-serif";
    ctx.fillText(label, p[0], p[1]);
  });
}

function drawPad(fit, x, y, r) {
  const [cx, cy] = project(fit, x, y, 0.16);
  ctx.beginPath();
  ctx.ellipse(cx, cy, r * fit.scale, r * fit.scale * 0.62, 0.2, 0, Math.PI * 2);
  ctx.fillStyle = "#b69a08";
  ctx.strokeStyle = "#554900";
  ctx.lineWidth = 1;
  ctx.fill();
  ctx.stroke();
}

function drawSilkBox(fit, x, y, w, h, label) {
  const pts = [
    project(fit, x - w / 2, y - h / 2, 0.2),
    project(fit, x + w / 2, y - h / 2, 0.2),
    project(fit, x + w / 2, y + h / 2, 0.2),
    project(fit, x - w / 2, y + h / 2, 0.2),
  ];
  ctx.beginPath();
  pts.forEach(([px, py], index) => index ? ctx.lineTo(px, py) : ctx.moveTo(px, py));
  ctx.closePath();
  ctx.strokeStyle = "rgba(235,235,225,0.72)";
  ctx.lineWidth = 1.1;
  ctx.stroke();
  const [cx, cy] = project(fit, x, y, 0.22);
  ctx.fillStyle = "rgba(235,235,225,0.85)";
  ctx.font = "700 11px Inter, system-ui, sans-serif";
  ctx.textAlign = "center";
  ctx.fillText(label, cx, cy);
}

function drawTrace(fit, revision) {
  const trace = revision === 0
    ? [[86, 10], [88, 26], [75, 26], [70, 20]]
    : [[12, 15], [26, 9], [41, 7], [52, 11]];
  ctx.beginPath();
  trace.forEach(([x, y], index) => {
    const [cx, cy] = project(fit, x, y, 0.35);
    if (index === 0) ctx.moveTo(cx, cy);
    else ctx.lineTo(cx, cy);
  });
  ctx.strokeStyle = "#9b6a1c";
  ctx.lineWidth = 4;
  ctx.stroke();
}

function drawZones(fit, scene, api) {
  const visibleFindings = api.findings.filter((finding) => (
    state.activeConstraintLayer === "all" || finding.category === state.activeConstraintLayer
  ));
  const failureTargets = new Set(visibleFindings.filter((f) => f.status === "fail").flatMap((f) => f.target));
  const hasVisible = (category) => state.activeConstraintLayer === "all" || state.activeConstraintLayer === category;

  if (hasVisible("safety")) {
    const electrodeA = scene.placements.find((item) => item.id === "ELEC_A");
    const electrodeB = scene.placements.find((item) => item.id === "ELEC_B");
    drawConstraintBridge(fit, electrodeA, electrodeB, "Safety: patient contact path", "safety", false);
  }

  if (hasVisible("conducted")) {
    const reg = scene.placements.find((item) => item.id === "REG");
    const afe = scene.placements.find((item) => item.id === "AFE");
    drawConstraintBridge(fit, reg, afe, "Conducted: noisy rail separation", "conducted", failureTargets.has("REG") || failureTargets.has("AFE"));
  }

  scene.heatZones.forEach((zone) => {
    if (!hasVisible("thermal")) return;
    const part = scene.placements.find((item) => item.id === zone.partId);
    const [cx, cy] = project(fit, part.x, part.y, 0.45);
    ctx.beginPath();
    ctx.ellipse(cx, cy, zone.radius * fit.scale, zone.radius * fit.scale * 0.48, 0.42, 0, Math.PI * 2);
    const style = constraintStyles.thermal;
    ctx.fillStyle = style.fill;
    ctx.strokeStyle = failureTargets.has("REG") ? style.color : "#bf8d22";
    ctx.setLineDash([6, 5]);
    ctx.fill();
    ctx.stroke();
    ctx.setLineDash([]);
    drawCallout(fit, part.x + 8, part.y - 8, "Thermal: regulator heat plume", "thermal", failureTargets.has("REG"));
  });

  scene.keepouts.forEach((zone) => {
    if (!hasVisible("radiated")) return;
    const part = scene.placements.find((item) => item.id === zone.partId);
    const [cx, cy] = project(fit, part.x, part.y + 5, 0.45);
    const style = constraintStyles.radiated;
    ctx.fillStyle = style.fill;
    ctx.strokeStyle = failureTargets.has("ANT") ? style.color : "#426bb8";
    ctx.setLineDash([5, 4]);
    ctx.fillRect(cx - (zone.w * fit.scale) / 2, cy - (zone.h * fit.scale) / 2, zone.w * fit.scale, zone.h * fit.scale);
    ctx.strokeRect(cx - (zone.w * fit.scale) / 2, cy - (zone.h * fit.scale) / 2, zone.w * fit.scale, zone.h * fit.scale);
    ctx.setLineDash([]);
    drawCallout(fit, part.x - 5, part.y + 11, "Radiated: 2.4 GHz keep-out", "radiated", failureTargets.has("ANT"));
  });

  if (hasVisible("mechanical")) {
    const charge = scene.placements.find((item) => item.id === "CHARGE");
    const cell = scene.placements.find((item) => item.id === "LIPO");
    drawCallout(fit, charge.x - 6, charge.y - 10, "Mechanical: charge-window access", "mechanical", failureTargets.has("CHARGE"));
    drawHeightGauge(fit, cell, failureTargets.has("LIPO"));
  }

  if (hasVisible("safety")) {
    const cell = scene.placements.find((item) => item.id === "LIPO");
    const charge = scene.placements.find((item) => item.id === "CHARGE");
    drawConstraintBridge(fit, cell, charge, "Safety: charger + protection required", "safety", failureTargets.has("LIPO") || failureTargets.has("CHARGE"));
  }
}

function drawConstraintBridge(fit, a, b, label, category, failing) {
  if (!a || !b) return;
  const style = constraintStyles[category];
  const start = project(fit, a.x, a.y, 9);
  const end = project(fit, b.x, b.y, 9);
  ctx.beginPath();
  ctx.moveTo(start[0], start[1]);
  ctx.lineTo(end[0], end[1]);
  ctx.strokeStyle = style.color;
  ctx.lineWidth = failing ? 3 : 2;
  ctx.setLineDash(failing ? [4, 3] : [9, 5]);
  ctx.stroke();
  ctx.setLineDash([]);
  drawCallout(fit, (a.x + b.x) / 2, (a.y + b.y) / 2 - 4, label, category, failing);
}

function drawCallout(fit, x, y, text, category, failing) {
  const style = constraintStyles[category];
  const [cx, cy] = project(fit, x, y, 13);
  const padX = 8;
  const width = Math.min(230, Math.max(132, text.length * 6.4 + padX * 2));
  const height = 24;
  ctx.save();
  ctx.fillStyle = failing ? "rgba(255,255,255,0.96)" : "rgba(21,21,21,0.86)";
  ctx.strokeStyle = style.color;
  ctx.lineWidth = 1.4;
  ctx.beginPath();
  ctx.roundRect(cx - width / 2, cy - height / 2, width, height, 5);
  ctx.fill();
  ctx.stroke();
  ctx.fillStyle = style.color;
  ctx.beginPath();
  ctx.arc(cx - width / 2 + 12, cy, 4, 0, Math.PI * 2);
  ctx.fill();
  ctx.fillStyle = failing ? "#171717" : "#fff";
  ctx.font = "700 11px Inter, system-ui, sans-serif";
  ctx.textAlign = "left";
  ctx.textBaseline = "middle";
  ctx.fillText(text, cx - width / 2 + 22, cy + 0.5);
  ctx.restore();
}

function drawHeightGauge(fit, part, failing) {
  if (!part) return;
  const style = constraintStyles.mechanical;
  const base = project(fit, part.x + part.w / 2 + 4, part.y, 0.4);
  const top = project(fit, part.x + part.w / 2 + 4, part.y, failing ? 5.6 : 3.8);
  const limit = project(fit, part.x + part.w / 2 + 8, part.y, 4.0);
  ctx.save();
  ctx.strokeStyle = failing ? style.color : "#16824a";
  ctx.lineWidth = 2;
  ctx.beginPath();
  ctx.moveTo(base[0], base[1]);
  ctx.lineTo(top[0], top[1]);
  ctx.stroke();
  ctx.strokeStyle = "#111";
  ctx.setLineDash([3, 3]);
  ctx.beginPath();
  ctx.moveTo(limit[0] - 32, limit[1]);
  ctx.lineTo(limit[0] + 32, limit[1]);
  ctx.stroke();
  ctx.setLineDash([]);
  drawCallout(fit, part.x + part.w / 2 + 13, part.y - 5, failing ? "Mechanical: 5.6 mm cell > 4.0 mm headroom" : "Mechanical: enclosure decision tracked", "mechanical", failing);
  ctx.restore();
}

function drawPart(fit, part, api) {
  const active = state.selectedPart === part.id || api.findings.some((f) => f.status === "fail" && f.target.includes(part.id));
  const height = part.type === "connector" || part.type === "electrode" ? 7.5 : part.type === "battery" ? 1.8 : 2.4;
  const top = rect3d(fit, part.x, part.y, part.w, part.h, 0.2, height, partColor(part.type), active ? "#ff4040" : "#111", active ? 2.4 : 1);
  const xs = top.map((p) => p[0]);
  const ys = top.map((p) => p[1]);
  hitRegions.push({ id: part.id, minX: Math.min(...xs) - 12, maxX: Math.max(...xs) + 12, minY: Math.min(...ys) - 12, maxY: Math.max(...ys) + 12 });

  if (part.type === "connector" || part.type === "electrode") {
    drawPins(fit, part);
  }

  const [cx, cy] = project(fit, part.x, part.y, height + 0.4);
  ctx.fillStyle = part.type === "electrode" ? "#111" : "#fff";
  ctx.font = "700 12px Inter, system-ui, sans-serif";
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  ctx.fillText(part.label, cx, cy);
}

function drawPins(fit, part) {
  const count = part.type === "connector" ? 6 : 2;
  for (let i = 0; i < count; i += 1) {
    const offset = count === 1 ? 0 : (i - (count - 1) / 2) * Math.min(2.3, part.h / Math.max(1, count - 1));
    const px = part.x;
    const py = part.y + offset;
    rect3d(fit, px, py, 0.55, 0.55, 7.8, 7.5, "#d2aa43", "#5b4617", 0.7);
  }
}

function drawComments(fit, scene) {
  state.comments.forEach((comment) => {
    const part = scene.placements.find((item) => item.id === comment.anchor);
    if (!part) return;
    const [cx, cy] = project(fit, part.x + part.w / 2 + 2, part.y - part.h / 2 - 2, 10);
    ctx.beginPath();
    ctx.arc(cx, cy, 7, 0, Math.PI * 2);
    ctx.fillStyle = "#111";
    ctx.fill();
    ctx.fillStyle = "#fff";
    ctx.font = "700 10px Inter, system-ui, sans-serif";
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.fillText(String(state.comments.indexOf(comment) + 1), cx, cy);
  });
}

function drawAxisGizmo() {
  const base = { x: 52, y: els.canvas.height - 58 };
  const axes = [
    ["X", "#b72b3a", 38, 10],
    ["Y", "#23a657", -4, -42],
    ["Z", "#3444c6", 0, -72],
  ];
  axes.forEach(([label, color, dx, dy]) => {
    ctx.beginPath();
    ctx.moveTo(base.x, base.y);
    ctx.lineTo(base.x + dx, base.y + dy);
    ctx.strokeStyle = color;
    ctx.lineWidth = 3;
    ctx.stroke();
    ctx.beginPath();
    ctx.arc(base.x + dx, base.y + dy, 11, 0, Math.PI * 2);
    ctx.fillStyle = color;
    ctx.fill();
    ctx.strokeStyle = "#111";
    ctx.stroke();
    ctx.fillStyle = "#111";
    ctx.font = "700 10px Inter, system-ui, sans-serif";
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.fillText(label, base.x + dx, base.y + dy);
  });
  ctx.beginPath();
  ctx.arc(base.x, base.y, 16, 0, Math.PI * 2);
  ctx.fillStyle = "#397845";
  ctx.fill();
  ctx.strokeStyle = "#122916";
  ctx.stroke();
}

function drawStatusLine(api) {
  ctx.fillStyle = "rgba(28, 28, 28, 0.92)";
  ctx.fillRect(0, els.canvas.height - 18, els.canvas.width, 18);
  ctx.fillStyle = "#bfbfbf";
  ctx.font = "11px Inter, system-ui, sans-serif";
  ctx.textAlign = "left";
  ctx.fillText(`Last capture 4 ms    source: Blender CAD render + advisor overlays`, 8, els.canvas.height - 5);
  ctx.textAlign = "right";
  ctx.fillText("dx 0.71    dy -0.83    zoom 0.83", els.canvas.width - 232, els.canvas.height - 5);
}

function selectPart(evt) {
  if (state.pointerMoved) {
    state.pointerMoved = false;
    return;
  }
  const point = canvasPointToBoard(evt);
  const hit = [...hitRegions].reverse().find((region) => (
    point.x >= region.minX &&
    point.x <= region.maxX &&
    point.y >= region.minY &&
    point.y <= region.maxY
  ));
  state.selectedPart = hit ? hit.id : null;
  if (state.activeTool === "comment" && hit) {
    state.comments.push({ anchor: hit.id, text: "Human note: preserve this placement in the next revision." });
  }
  render();
}

function setRevision(index) {
  state.revision = Math.max(0, Math.min(revisions.length - 1, index));
  els.revisionSlider.value = String(state.revision);
  const api = constraintApi(state);
  addMessage("ai", api.note);
  render();
}

function render() {
  const api = constraintApi(state);
  const scene = modelApi(state);
  els.revisionSlider.max = String(revisions.length - 1);
  els.revisionSlider.value = String(state.revision);
  els.revisionLabel.textContent = `${revisions[state.revision].title}`;
  els.verdictLabel.textContent = api.summary.fail === 0 ? "PASS" : `${api.summary.fail} blockers`;
  els.verdictLabel.style.color = api.summary.fail === 0 ? "var(--pass)" : "var(--fail)";
  els.selectedLabel.textContent = state.selectedPart ? `Selected ${state.selectedPart}` : "No selection";
  els.timelineStatus.textContent = `${api.summary.pass} considerations / ${api.summary.fail} blockers`;
  els.stagePill.textContent = api.stage;
  renderConsiderations(api);
  renderFindings(api);
  renderComments();
  renderLayers();
  els.constraintChips.forEach((chip) => {
    chip.classList.toggle("active", chip.dataset.layer === state.activeConstraintLayer);
  });
  drawScene(scene, api);
}

function runMission() {
  els.chatLog.innerHTML = "";
  addMessage("user", document.querySelector("#missionPrompt").value.trim());
  addMessage("ai", "I will ask only the decisions that change the electrical and physical constraints.");
  addMessage("ai", "Using recommended answers: continuous patient contact, rechargeable LiPo, patient safety first.");
  setRevision(0);
  if (els.autoMode.checked) {
    setTimeout(() => setRevision(1), 700);
    setTimeout(() => setRevision(2), 1400);
  }
}

function exportPayload(kind) {
  return {
    kind,
    mission: document.querySelector("#missionPrompt").value.trim(),
    interview: questions.map((q, index) => ({
      id: q.id,
      answer: els.interviewList.querySelectorAll("select")[index].value,
    })),
    revision: state.revision,
    selectedPart: state.selectedPart,
    comments: state.comments,
    constraintApi: "/api/constraints",
    modelApi: "/api/model",
    current: revisions[state.revision],
  };
}

function downloadJson(kind) {
  const blob = new Blob([JSON.stringify(exportPayload(kind), null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `missionpcb-${kind}.json`;
  a.click();
  URL.revokeObjectURL(url);
}

els.startButton.addEventListener("click", runMission);
els.recommendedButton.addEventListener("click", () => {
  els.interviewList.querySelectorAll("select").forEach((select) => {
    select.selectedIndex = 0;
  });
});
els.prevRevision.addEventListener("click", () => setRevision(state.revision - 1));
els.nextRevision.addEventListener("click", () => setRevision(state.revision + 1));
els.revisionSlider.addEventListener("input", (evt) => setRevision(Number(evt.target.value)));
els.canvas.addEventListener("pointerdown", (evt) => {
  state.isPanning = true;
  state.lastPointer = { x: evt.clientX, y: evt.clientY };
  els.canvas.setPointerCapture(evt.pointerId);
});
els.canvas.addEventListener("pointermove", (evt) => {
  if (!state.isPanning || !state.lastPointer) return;
  const dx = evt.clientX - state.lastPointer.x;
  const dy = evt.clientY - state.lastPointer.y;
  state.camera.x += dx * (els.canvas.width / els.canvas.getBoundingClientRect().width);
  state.camera.y += dy * (els.canvas.height / els.canvas.getBoundingClientRect().height);
  state.lastPointer = { x: evt.clientX, y: evt.clientY };
  state.pointerMoved = true;
  render();
});
els.canvas.addEventListener("pointerup", (evt) => {
  if (!state.isPanning) return;
  state.isPanning = false;
  state.lastPointer = null;
  els.canvas.releasePointerCapture(evt.pointerId);
});
els.canvas.addEventListener("click", selectPart);
els.canvas.addEventListener("wheel", (evt) => {
  evt.preventDefault();
  const point = canvasPointToBoard(evt);
  const before = canvasToImage(point);
  const factor = evt.deltaY < 0 ? 1.12 : 0.9;
  state.camera.scale = Math.max(0.25, Math.min(3.5, state.camera.scale * factor));
  state.camera.x = point.x - before.x * state.camera.scale;
  state.camera.y = point.y - before.y * state.camera.scale;
  render();
}, { passive: false });
els.constraintChips.forEach((chip) => {
  chip.addEventListener("click", () => {
    state.activeConstraintLayer = chip.dataset.layer;
    render();
  });
});
els.addCommentButton.addEventListener("click", () => {
  state.comments.push({
    anchor: state.selectedPart || "workspace",
    text: "Human comment: review this before the next revision.",
  });
  render();
});
els.exportButton.addEventListener("click", () => {
  els.exportMenu.classList.toggle("hidden");
});
els.exportMenu.addEventListener("click", (evt) => {
  const button = evt.target.closest("button");
  if (!button) return;
  downloadJson(button.dataset.export);
  els.exportMenu.classList.add("hidden");
});

document.querySelectorAll(".tool-button").forEach((button) => {
  button.addEventListener("click", () => {
    document.querySelectorAll(".tool-button").forEach((item) => item.classList.remove("active"));
    button.classList.add("active");
    state.activeTool = button.dataset.tool;
  });
});

artifactImage.addEventListener("load", () => {
  resetCameraForImage();
  render();
});

renderInterview();
render();

import Alpine from "alpinejs";
import {
  BookOpen,
  Brain,
  ChartNoAxesCombined,
  Check,
  ChevronDown,
  ChevronRight,
  CircleHelp,
  ClipboardCheck,
  Clock3,
  FileText,
  FileCheck2,
  Gauge,
  Library,
  Lightbulb,
  LogOut,
  Menu,
  MessageSquareText,
  Play,
  Search,
  Settings,
  ShieldCheck,
  Sparkles,
  Target,
  User,
  Users,
  X,
  createIcons,
} from "lucide";

window.Alpine = Alpine;
Alpine.start();

const icons = {
  BookOpen,
  Brain,
  ChartNoAxesCombined,
  Check,
  ChevronDown,
  ChevronRight,
  CircleHelp,
  ClipboardCheck,
  Clock3,
  FileText,
  FileCheck2,
  Gauge,
  Library,
  Lightbulb,
  LogOut,
  Menu,
  MessageSquareText,
  Play,
  Search,
  Settings,
  ShieldCheck,
  Sparkles,
  Target,
  User,
  Users,
  X,
};

const renderIcons = () => createIcons({ icons, attrs: { "stroke-width": 1.8 } });
renderIcons();
document.addEventListener("DOMContentLoaded", renderIcons);

const formatTrendDate = (value) => new Intl.DateTimeFormat(undefined, {
  month: "short", day: "numeric", year: "numeric",
}).format(new Date(`${value}T12:00:00`));

const initialiseFailureTrend = () => {
  const chart = document.querySelector("[data-failure-chart]");
  if (!chart) return;
  const canvas = chart.querySelector("canvas");
  const tooltip = chart.querySelector("[data-failure-tooltip]");
  const legend = chart.querySelector("[data-failure-legend]");
  const topicFilter = document.querySelector("[data-failure-topic-filter]");
  const modeFilter = document.querySelector("[data-failure-mode-filter]");
  const points = JSON.parse(chart.dataset.points || "[]");
  const context = canvas.getContext("2d");
  const colours = ["#176b5a", "#4776df", "#b06d1a", "#8a5bbd", "#b34e5e", "#347c91"];
  let plottedLines = [];

  const selectedModes = () => {
    if (modeFilter?.value) return [modeFilter.value];
    return [...new Set(points.flatMap((point) => Object.keys(point.modes || {})))];
  };

  const draw = () => {
    const modes = selectedModes();
    const data = points.map((point) => ({
      ...point,
      values: Object.fromEntries(modes.map((mode) => [mode,
        topicFilter?.value ? (point.mode_topics?.[mode]?.[topicFilter.value] || 0) : (point.modes[mode] || 0),
      ])),
    }));
    const bounds = chart.getBoundingClientRect();
    const ratio = window.devicePixelRatio || 1;
    const width = Math.max(280, Math.floor(bounds.width));
    const height = 240;
    canvas.width = width * ratio;
    canvas.height = height * ratio;
    canvas.style.height = `${height}px`;
    context.setTransform(ratio, 0, 0, ratio, 0, 0);
    context.clearRect(0, 0, width, height);
    const padding = { top: 18, right: 20, bottom: 36, left: 34 };
    const graphWidth = width - padding.left - padding.right;
    const graphHeight = height - padding.top - padding.bottom;
    const maximum = Math.max(1, ...data.flatMap((point) => Object.values(point.values)));
    context.font = "12px system-ui, sans-serif";
    context.fillStyle = "#63767b";
    context.strokeStyle = "rgba(23, 107, 90, 0.13)";
    for (let value = 0; value <= maximum; value += 1) {
      const y = padding.top + graphHeight - (value / maximum) * graphHeight;
      context.beginPath(); context.moveTo(padding.left, y); context.lineTo(width - padding.right, y); context.stroke();
      context.fillText(String(value), 10, y + 4);
    }
    plottedLines = modes.map((mode, lineIndex) => ({
      mode, colour: colours[lineIndex % colours.length], points: data.map((point, index) => ({
        ...point, value: point.values[mode],
        x: padding.left + (data.length === 1 ? graphWidth / 2 : (index / (data.length - 1)) * graphWidth),
        y: padding.top + graphHeight - (point.values[mode] / maximum) * graphHeight,
      })),
    }));
    plottedLines.forEach((line) => {
      context.beginPath(); line.points.forEach((point, index) => index ? context.lineTo(point.x, point.y) : context.moveTo(point.x, point.y));
      context.strokeStyle = line.colour; context.lineWidth = 2.5; context.stroke();
      line.points.forEach((point) => { context.beginPath(); context.arc(point.x, point.y, 3.5, 0, Math.PI * 2); context.fillStyle = line.colour; context.fill(); context.strokeStyle = "#fff"; context.lineWidth = 1.5; context.stroke(); });
    });
    const datePoints = plottedLines[0]?.points || [];
    const labels = datePoints.length === 1 ? [datePoints[0]] : [datePoints[0], datePoints[datePoints.length - 1]].filter(Boolean);
    labels.forEach((point, index) => {
      context.textAlign = labels.length === 1 ? "center" : (index ? "right" : "left");
      context.fillStyle = "#63767b"; context.fillText(formatTrendDate(point.date), point.x, height - 12);
    });
    legend.replaceChildren(...plottedLines.map((line) => {
      const item = document.createElement("span"); item.innerHTML = `<i style="background:${line.colour}"></i>${line.mode}`; return item;
    }));
  };

  const showTooltip = (event) => {
    const rect = canvas.getBoundingClientRect();
    const scale = canvas.width / rect.width / (window.devicePixelRatio || 1);
    const x = (event.clientX - rect.left) * scale;
    const nearest = (plottedLines[0]?.points || []).reduce((current, point) => !current || Math.abs(point.x - x) < Math.abs(current.x - x) ? point : current, null);
    if (!nearest) return;
    const values = plottedLines.map((line) => `${line.mode}: ${line.points.find((point) => point.date === nearest.date)?.value || 0}`).join(" · ");
    tooltip.textContent = `${formatTrendDate(nearest.date)} · ${values}`;
    tooltip.style.left = `${nearest.x}px`; tooltip.style.top = `${nearest.y}px`; tooltip.hidden = false;
  };
  canvas.addEventListener("pointermove", showTooltip);
  canvas.addEventListener("pointerleave", () => { tooltip.hidden = true; });
  topicFilter?.addEventListener("change", () => { tooltip.hidden = true; draw(); });
  modeFilter?.addEventListener("change", () => { tooltip.hidden = true; draw(); });
  new ResizeObserver(draw).observe(chart);
  draw();
};

document.addEventListener("DOMContentLoaded", initialiseFailureTrend);

const activityCopy = (form, submitter) => {
  const action = new URL(form.action || window.location.href, window.location.href).pathname;
  const buttonText = submitter?.textContent?.trim().replace(/\s+/g, " ") || "";
  const explicit = form.dataset.progressLabel;
  if (explicit) {
    return { title: explicit, stages: [form.dataset.progressDetail || "Working locally…"] };
  }
  if (action.endsWith("/ask")) {
    return {
      title: "Finding accepted evidence",
      stages: [
        "Searching the active exam index…",
        "Reading the most relevant passages…",
        "Generating a grounded answer with the local model…",
        "Still working locally — larger answers can take a little longer.",
      ],
    };
  }
  if (/\/trainer\/sessions\/\d+\/answer$/.test(action)) {
    return {
      title: "Evaluating your answer",
      stages: [
        "Checking your answer against accepted evidence…",
        "Assessing must-know coverage and omissions…",
        "Updating learner mastery and feedback…",
        "Still evaluating locally — your answer is safely retained.",
      ],
    };
  }
  if (action.endsWith("/quiz/submit")) {
    return {
      title: "Checking your answer",
      stages: ["Saving this response…", "Updating quiz progress…"],
    };
  }
  if (action.includes("/trainer/")) {
    return {
      title: "Preparing your learning activity",
      stages: ["Selecting a reviewed question…", "Preparing the timed session…"],
    };
  }
  if (/\/admin\/subjects\/\d+\/upload$/.test(action) || action.endsWith("/upload")) {
    return {
      title: "Adding course materials",
      stages: ["Copying files into the isolated exam workspace…", "Checking source records…"],
    };
  }
  if (/\/admin\/subjects\/\d+\/process$/.test(action)) {
    return {
      title: "Starting durable processing",
      stages: ["Creating the resumable processing job…", "Opening the page-by-page progress view…"],
    };
  }
  if (/\/admin\/subjects\/\d+\/index$/.test(action) || action.endsWith("/reindex")) {
    return {
      title: "Building the evidence index",
      stages: [
        "Collecting accepted learning units…",
        "Creating local embeddings…",
        "Writing the isolated search index…",
        "Still embedding locally — large courses can take several minutes.",
      ],
    };
  }
  if (action.includes("reported-questions/import")) {
    return {
      title: "Importing the question bank",
      stages: ["Validating the uploaded JSON…", "Matching questions to course evidence…"],
    };
  }
  if (action.includes("generate") || /generate/i.test(buttonText)) {
    return {
      title: "Generating from accepted evidence",
      stages: [
        "Collecting grounded course material…",
        "Running the local model…",
        "Validating evidence references…",
        "Still working locally — generation time depends on the selected model.",
      ],
    };
  }
  if (action.includes("quiz")) {
    return {
      title: "Preparing your quiz",
      stages: ["Selecting accepted evidence…", "Creating grounded questions…"],
    };
  }
  if (action.includes("summar")) {
    return {
      title: "Distilling your material",
      stages: ["Reading the selected evidence…", "Preparing the local summary…"],
    };
  }
  if (/accept|review|reject|quarantine/i.test(`${action} ${buttonText}`)) {
    return {
      title: "Saving your review decision",
      stages: ["Updating the reviewed learning evidence…"],
    };
  }
  return {
    title: "Saving your changes",
    stages: ["Processing this action locally…", "Finishing the update…"],
  };
};

const createActivityProgress = ({ title, stages }) => {
  const status = document.createElement("div");
  status.className = "activity-progress";
  status.setAttribute("role", "status");
  status.setAttribute("aria-live", "polite");
  status.innerHTML = `
    <div class="activity-progress-heading">
      <span class="activity-progress-spinner" aria-hidden="true"></span>
      <span class="activity-progress-copy">
        <strong></strong>
        <span class="activity-progress-detail"></span>
      </span>
      <span class="activity-progress-time">0s</span>
    </div>
    <div class="activity-progress-track" aria-hidden="true"><span></span></div>
  `;
  status.querySelector("strong").textContent = title;
  status.querySelector(".activity-progress-detail").textContent = stages[0];
  return status;
};

const beginActivityProgress = (form, submitter) => {
  if (form.dataset.activityBusy === "true") return false;
  form.dataset.activityBusy = "true";
  form.setAttribute("aria-busy", "true");
  const copy = activityCopy(form, submitter);
  const progress = createActivityProgress(copy);
  form.appendChild(progress);
  if (submitter) {
    submitter.dataset.originalMarkup = submitter.innerHTML;
    submitter.classList.add("is-processing");
    submitter.setAttribute("aria-disabled", "true");
    const spinner = document.createElement("span");
    spinner.className = "button-spinner";
    spinner.setAttribute("aria-hidden", "true");
    const label = document.createElement("span");
    label.textContent = copy.title;
    submitter.replaceChildren(spinner, label);
  }
  const detail = progress.querySelector(".activity-progress-detail");
  const elapsedNode = progress.querySelector(".activity-progress-time");
  const startedAt = Date.now();
  const stageThresholds = [0, 3, 8, 20];
  form._activityTimer = window.setInterval(() => {
    const elapsed = Math.floor((Date.now() - startedAt) / 1000);
    elapsedNode.textContent = `${elapsed}s`;
    let stage = 0;
    stageThresholds.forEach((threshold, index) => {
      if (elapsed >= threshold && index < copy.stages.length) stage = index;
    });
    detail.textContent = copy.stages[stage];
  }, 1000);
  return true;
};

document.addEventListener("submit", (event) => {
  const form = event.target;
  if (!(form instanceof HTMLFormElement) || form.method.toLowerCase() === "get" || form.dataset.noProgress === "true") return;
  if (!beginActivityProgress(form, event.submitter)) event.preventDefault();
});

window.addEventListener("pageshow", (event) => {
  if (!event.persisted) return;
  document.querySelectorAll('form[data-activity-busy="true"]').forEach((form) => {
    window.clearInterval(form._activityTimer);
    form.dataset.activityBusy = "false";
    form.removeAttribute("aria-busy");
    form.querySelectorAll(".activity-progress").forEach((node) => node.remove());
    form.querySelectorAll(".is-processing").forEach((button) => {
      if (button.dataset.originalMarkup) button.innerHTML = button.dataset.originalMarkup;
      button.classList.remove("is-processing");
      button.removeAttribute("aria-disabled");
    });
    renderIcons();
  });
});

const sourcePageNumber = (button) => {
  const explicit = Number.parseInt(button.dataset.pageNumber || "", 10);
  if (explicit > 0) return explicit;
  const match = (button.dataset.page || "").match(/\b(?:page|seite)\s*(\d+)\b/i);
  return match ? Number.parseInt(match[1], 10) : null;
};

const pdfUrlAtPage = (rawUrl, pageNumber) => {
  if (!rawUrl) return "";
  const url = new URL(rawUrl, window.location.href);
  url.hash = pageNumber ? `page=${pageNumber}&zoom=page-width` : "";
  return url.toString();
};

window.openSourceModal = (button) => {
  const modal = document.getElementById("source-modal");
  if (!modal) return;
  const pageNumber = sourcePageNumber(button);
  const pageLabel = button.dataset.page || (pageNumber ? `Page ${pageNumber}` : "");
  const pdfUrl = pdfUrlAtPage(button.dataset.pdfUrl || "", pageNumber);
  const isPdf = button.dataset.sourceType === "pdf" || /\.pdf(?:$|[?#])/i.test(pdfUrl);
  const frame = document.getElementById("modal-pdf-frame");
  const openLink = document.getElementById("modal-pdf-open");
  const unavailable = document.getElementById("modal-pdf-unavailable");
  document.getElementById("modal-doc-title").textContent = button.dataset.doc || "Source";
  document.getElementById("modal-chunk-meta").textContent = pageNumber
    ? `${pageLabel} · PDF opens at page ${pageNumber}`
    : pageLabel;
  document.getElementById("modal-chunk-preview").textContent = button.dataset.preview || "No preview available.";
  frame.classList.toggle("hidden", !isPdf);
  unavailable.classList.toggle("hidden", isPdf);
  openLink.classList.toggle("hidden", !isPdf);
  if (isPdf) {
    frame.src = pdfUrl;
    openLink.href = pdfUrl;
  } else {
    frame.removeAttribute("src");
    openLink.removeAttribute("href");
  }
  modal.classList.remove("hidden");
  modal.setAttribute("aria-hidden", "false");
  document.body.classList.add("modal-open");
  modal.querySelector(".icon-close")?.focus();
};

window.closeSourceModal = () => {
  const modal = document.getElementById("source-modal");
  if (!modal) return;
  modal.classList.add("hidden");
  modal.setAttribute("aria-hidden", "true");
  document.body.classList.remove("modal-open");
  document.getElementById("modal-pdf-frame")?.removeAttribute("src");
};

document.addEventListener("keydown", (event) => {
  if (event.key === "Escape") window.closeSourceModal();
});

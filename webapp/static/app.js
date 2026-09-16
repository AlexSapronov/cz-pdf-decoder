"use strict";

const drop = document.getElementById("drop");
const fileInput = document.getElementById("files");
const fileList = document.getElementById("filelist");
const decodeBtn = document.getElementById("decode");
const clearBtn = document.getElementById("clear");
const downloadBtn = document.getElementById("download");
const shipmentInput = document.getElementById("shipment");
const progressEl = document.getElementById("progress");
const barFill = document.getElementById("bar-fill");
const progressText = document.getElementById("progress-text");
const errorEl = document.getElementById("error");
const resultCard = document.getElementById("result-card");
const resultBody = document.querySelector("#result tbody");

let pendingFiles = [];     // File[] выбранные/перетащенные, ещё не отправленные
let currentJobId = null;   // job_id после decode

function showError(msg) {
  errorEl.textContent = msg;
  errorEl.hidden = !msg;
}

function setProgress(pct, text) {
  progressEl.hidden = false;
  barFill.style.width = pct + "%";
  progressText.textContent = text || "";
}

function hideProgress() {
  progressEl.hidden = true;
  barFill.style.width = "0%";
  progressText.textContent = "";
}

function renderFileList() {
  fileList.innerHTML = "";
  pendingFiles.forEach((f) => {
    const li = document.createElement("li");
    li.textContent = f.name + " (" + formatBytes(f.size) + ")";
    fileList.appendChild(li);
  });
}

function formatBytes(n) {
  if (n < 1024) return n + " Б";
  if (n < 1024 * 1024) return (n / 1024).toFixed(1) + " КБ";
  return (n / 1024 / 1024).toFixed(1) + " МБ";
}

function addFiles(list) {
  const pdfs = Array.from(list).filter((f) =>
    f.name.toLowerCase().endsWith(".pdf")
  );
  if (pdfs.length === 0) {
    showError("Выберите PDF-файлы (.pdf).");
    return;
  }
  pendingFiles = pendingFiles.concat(pdfs);
  showError("");
  renderFileList();
}

function renderResult(data) {
  resultBody.innerHTML = "";
  (data.rows || []).forEach((r) => {
    const tr = document.createElement("tr");
    ["full_dm", "gtin", "pn", "qty", "file_name", "page_num"].forEach((k) => {
      const td = document.createElement("td");
      td.textContent = r[k] != null ? String(r[k]) : "";
      tr.appendChild(td);
    });
    resultBody.appendChild(tr);
  });
  resultCard.hidden = false;
}

function resetOutput() {
  currentJobId = null;
  downloadBtn.disabled = true;
  resultCard.hidden = true;
  resultBody.innerHTML = "";
}

// --- выбор файлов ---
drop.addEventListener("click", () => fileInput.click());
drop.addEventListener("dragover", (e) => {
  e.preventDefault();
  drop.classList.add("dragover");
});
drop.addEventListener("dragleave", () => drop.classList.remove("dragover"));
drop.addEventListener("drop", (e) => {
  e.preventDefault();
  drop.classList.remove("dragover");
  if (e.dataTransfer && e.dataTransfer.files.length) {
    addFiles(e.dataTransfer.files);
  }
});
fileInput.addEventListener("change", () => {
  addFiles(fileInput.files);
  fileInput.value = "";
});

// --- действия ---
decodeBtn.addEventListener("click", async () => {
  if (pendingFiles.length === 0) {
    showError("Сначала выберите PDF-файлы.");
    return;
  }

  decodeBtn.disabled = true;
  clearBtn.disabled = true;
  resetOutput();
  showError("");
  setProgress(20, "Загрузка и распознавание…");

  const form = new FormData();
  pendingFiles.forEach((f) => form.append("files", f));
  const shipment = shipmentInput.value.trim();
  if (shipment) form.append("shipment", shipment);

  try {
    const resp = await fetch("/api/decode", { method: "POST", body: form });
    const data = await resp.json().catch(() => ({}));
    if (!resp.ok) {
      throw new Error(data.detail || "Ошибка сервера.");
    }

    setProgress(90, "Готово. Формирую результат…");
    currentJobId = data.job_id;
    renderResult(data);
    downloadBtn.disabled = false;

    const rejected = data.rejected_files || [];
    if (rejected.length) {
      showError("Пропущены (не PDF): " + rejected.join(", "));
    } else {
      showError("");
    }
    progressText.textContent =
      "Распознано страниц: " + (data.total_pages || 0);
    barFill.style.width = "100%";
  } catch (err) {
    showError(err.message || "Ошибка обработки.");
    setProgress(0, "");
  } finally {
    decodeBtn.disabled = false;
    clearBtn.disabled = false;
  }
});

clearBtn.addEventListener("click", () => {
  pendingFiles = [];
  renderFileList();
  resetOutput();
  showError("");
  hideProgress();
  shipmentInput.value = "";
});

downloadBtn.addEventListener("click", () => {
  if (!currentJobId) return;
  window.location = "/api/download/" + currentJobId;
});

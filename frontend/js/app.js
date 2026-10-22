// Ponto de entrada da página: liga o gravador, a API e a tela do dia.

import { InactivityWatcher, requestNotificationPermission, shortText } from "./alerts.js";
import { api, flushOutbox, outboxSize, saveEntry } from "./api.js";
import { addDays, DayView, formatDayLabel, todayIn, weekBounds } from "./day.js";
import { Recorder } from "./recorder.js";
import { nowIn, routineStatus } from "./routine.js";

// Guardados no navegador para sobreviver a um F5 ou à aba fechada sem querer
const STATE_KEY = "diario.recorderState";
const PAUSE_KEY = "diario.pauseStartedAt";
const ORDER_KEY = "diario.newestFirst";
const EXPORT_KEY = "diario.exportFormat";

const STATUS_LABELS = {
  idle: "Parado",
  recording: "Gravando",
  paused: "Pausado",
  error: "Erro",
};

const ERROR_MESSAGES = {
  "not-allowed": "Microfone bloqueado. Libere o acesso no cadeado da barra de endereço.",
  "service-not-allowed": "O Chrome não permitiu o reconhecimento de voz nesta página.",
  "language-not-supported": "O idioma pt-BR não está disponível neste navegador.",
  "audio-capture": "Nenhum microfone encontrado. Tentando de novo...",
  network: "Sem conexão com o serviço de voz. Tentando de novo...",
};

// Registros que mostram o que a pessoa está fazendo: zeram o alerta de inatividade
const EXPLICIT_KINDS = new Set(["note", "confirm", "activity_change", "activity_end"]);

const $ = (id) => document.getElementById(id);

const storage = {
  get: (key) => {
    try {
      return localStorage.getItem(key);
    } catch {
      return null;
    }
  },
  set: (key, value) => {
    try {
      if (value === null) localStorage.removeItem(key);
      else localStorage.setItem(key, value);
    } catch {
      // sem armazenamento: o app funciona, só não lembra o estado após recarregar
    }
  },
};

let config;
let dayView;
let currentDay;
let recorder;
let watcher;
let currentActivity = null; // texto completo; a tela mostra a versão curta
let routine = null; // expediente + blocos fixos (carregado da API)

// --- Mensagens e estado visual -------------------------------------------

function showMessage(text, kind = "info") {
  const el = $("message");
  el.textContent = text;
  el.dataset.kind = kind;
  el.hidden = !text;
}

/** "10:05" no fuso configurado */
function formatTime(iso) {
  return new Date(iso).toLocaleTimeString("pt-BR", {
    hour: "2-digit",
    minute: "2-digit",
    timeZone: config.timezone,
  });
}

function renderState(state) {
  const status = $("status");
  status.className = `status status--${state}`;

  const pausedAt = storage.get(PAUSE_KEY);
  $("status-label").textContent =
    state === "paused" && pausedAt ? `Pausado desde ${formatTime(pausedAt)}` : STATUS_LABELS[state];

  // Cada estado mostra só os botões que fazem sentido nele
  $("btn-start").hidden = !["idle", "error"].includes(state);
  $("btn-pause").hidden = state !== "recording";
  $("btn-resume").hidden = state !== "paused";
  $("btn-stop").hidden = !["recording", "paused"].includes(state);

  // O título da aba mostra o estado, útil quando a janela está em segundo plano
  const prefix = { recording: "● ", paused: "❚❚ ", error: "⚠ " }[state] ?? "";
  document.title = `${prefix}Diário de Bordo`;

  if (state !== "error") storage.set(STATE_KEY, state);
  // Começou ou voltou a gravar: o relógio do alerta conta a partir de agora
  if (state === "recording") watcher?.reset();
}

// --- Salvamento ----------------------------------------------------------

async function save(data) {
  const entry = await saveEntry(data);
  if (entry && entry.local_date === currentDay) dayView.append(entry);

  // Servidor fora (entry = null): usamos o que foi enviado, que já está na caixa de saída
  const saved = entry ?? data;
  if (saved.kind === "note" || saved.kind === "activity_change") {
    showActivity({ activity: saved.activity ?? saved.text, since: saved.ts });
  }
  if (EXPLICIT_KINDS.has(saved.kind)) watcher?.reset();

  updateOutboxNotice();
  return entry;
}

function handleFinal(text, startedAt) {
  // O servidor decide se é fala comum ou anotação ("Diário, ...")
  return save({ text, kind: "speech", ts: startedAt.toISOString() });
}

// --- Atividade atual -----------------------------------------------------

function showActivity({ activity, since }) {
  currentActivity = activity || null;
  // Anotações longas aparecem encurtadas; o texto completo fica no "title" (passe o mouse)
  $("activity-text").textContent = currentActivity ? shortText(currentActivity) : "";
  $("activity-text").title = currentActivity ?? "";
  $("activity-since").textContent = currentActivity && since ? `desde ${formatTime(since)}` : "";
  // Caixa amarela e botão "Finalizar" só quando há atividade em andamento
  $("activity").classList.toggle("activity--active", Boolean(currentActivity));
  $("activity-end").hidden = !currentActivity;
}

async function endActivity() {
  const activity = currentActivity;
  if (!activity) return;
  // Some da tela na hora; o registro vai para o servidor (ou para a caixa de saída)
  showActivity({ activity: null });
  await save({ kind: "activity_end", text: `Finalizou: ${activity}`, activity });
}

async function loadActivity() {
  try {
    showActivity(await api.currentActivity(todayIn(config.timezone)));
  } catch {
    // sem atividade carregada a tela continua funcionando
  }
}

async function submitNote(event) {
  event.preventDefault();
  const input = $("note-input");
  const text = input.value.trim();
  if (!text) return;

  input.value = "";
  await save({ text, kind: "note", ts: new Date().toISOString() });
}

function updateOutboxNotice() {
  const pending = outboxSize();
  $("outbox").hidden = pending === 0;
  $("outbox").textContent = `${pending} trecho(s) aguardando o servidor voltar. Nada foi perdido.`;
}

async function retryOutbox() {
  const sent = await flushOutbox();
  updateOutboxNotice();
  if (sent > 0) loadDay(currentDay);
}

// --- Rotina fixa ---------------------------------------------------------

function currentRoutineStatus() {
  return routine ? routineStatus(routine, nowIn(config.timezone)) : { kind: "work" };
}

let wasWatching = null;

/** Só alerta gravando, dentro do expediente e fora dos blocos da rotina fixa. */
function shouldWatchInactivity() {
  const watching = recorder.state === "recording" && currentRoutineStatus().kind === "work";
  // Acabou a daily (ou o intervalo, ou começou o expediente): o relógio recomeça.
  // Sem isso, o alerta pularia no segundo em que a daily termina.
  if (watching && wasWatching === false) watcher.reset();
  wasWatching = watching;
  return watching;
}

/** Mostra quando a rotina está "segurando" o alerta (bloco fixo ou fora do expediente). */
function renderRoutineNow() {
  const status = currentRoutineStatus();
  const el = $("routine-now");
  el.hidden = status.kind === "work";
  if (status.kind === "block") {
    const { activity, end } = status.block;
    el.textContent = `🗓 Agora: ${activity} (rotina, até ${end}). Alerta de inatividade pausado.`;
  } else if (status.kind === "off") {
    el.textContent = `🌙 Fora do expediente (${routine.work_start}–${routine.work_end}). Alerta de inatividade pausado.`;
  }
}

// --- Pausa ---------------------------------------------------------------
// A pausa vira UMA entrada com início e fim, gravada só ao retomar. Até lá,
// o início fica guardado no navegador.

async function closePause() {
  const startedAt = storage.get(PAUSE_KEY);
  if (!startedAt) return;
  storage.set(PAUSE_KEY, null);
  await saveEntry({ kind: "pause", ts: startedAt, ends_at: new Date().toISOString() });
  loadDay(currentDay);
}

// --- Botões --------------------------------------------------------------

function start() {
  showMessage("");
  recorder.start();
  // Aproveita o clique para pedir permissão de notificação (o Chrome exige um clique)
  enableNotifications();
}

async function enableNotifications() {
  await requestNotificationPermission();
  renderNotifyButton();
}

function renderNotifyButton() {
  $("btn-notify").hidden = !("Notification" in window) || Notification.permission !== "default";
}

function pause() {
  storage.set(PAUSE_KEY, new Date().toISOString());
  recorder.pause();
}

async function resume() {
  await closePause();
  recorder.start();
}

async function endDay() {
  if (!confirm("Encerrar a gravação de hoje?")) return;
  recorder.stop();
  await closePause();
  showMessage("Dia encerrado. Bom descanso!");
}

// --- Navegação entre dias --------------------------------------------------

function renderOrderToggle() {
  // O botão mostra a ordem ATUAL; clicar inverte
  $("order-toggle").textContent = dayView.newestFirst
    ? "↓ Mais recentes primeiro"
    : "↑ Mais antigas primeiro";
}

/** Os links de exportação seguem o dia (e a semana) na tela e o formato escolhido. */
function renderExportLinks() {
  const fmt = $("export-format").value;
  const [monday, friday] = weekBounds(currentDay);
  const exportUrl = (start, end) => `/api/export/transcript?start=${start}&end=${end}&fmt=${fmt}`;

  $("export-day").href = exportUrl(currentDay, currentDay);
  $("export-week").href = exportUrl(monday, friday);
  document.querySelectorAll(".export-ext").forEach((el) => (el.textContent = `(.${fmt})`));

  // Diário com IA: abre a tela de revisão já gerando (ou só mostrando o que foi salvo)
  const reviewUrl = (start, end, generate) =>
    `review.html?start=${start}&end=${end}${generate ? "&generate=1" : ""}`;
  $("diary-day").href = reviewUrl(currentDay, currentDay, true);
  $("diary-week").href = reviewUrl(monday, friday, true);
  $("diary-review").href = reviewUrl(monday, friday, false);
}

async function loadDay(day) {
  currentDay = day;
  $("day-label").textContent = formatDayLabel(day);
  $("day-next").disabled = day >= todayIn(config.timezone);

  renderExportLinks();

  try {
    dayView.render(await api.listEntries(day));
  } catch {
    showMessage("Não foi possível carregar o dia. O servidor está rodando?", "error");
  }
}

// --- Inicialização -------------------------------------------------------

async function init() {
  try {
    config = await api.config();
  } catch {
    showMessage("Servidor fora do ar. Rode o uvicorn e recarregue a página.", "error");
    return;
  }

  // Padrão: mais recentes primeiro. A escolha fica salva no navegador.
  const newestFirst = storage.get(ORDER_KEY) !== "false";
  dayView = new DayView({
    listEl: $("entries"),
    emptyEl: $("empty"),
    timeZone: config.timezone,
    newestFirst,
  });
  renderOrderToggle();
  $("order-toggle").addEventListener("click", () => {
    dayView.setNewestFirst(!dayView.newestFirst);
    storage.set(ORDER_KEY, String(dayView.newestFirst));
    renderOrderToggle();
  });

  // Formato de exportação: lembra a última escolha
  const savedFormat = storage.get(EXPORT_KEY);
  if (savedFormat === "txt" || savedFormat === "docx") $("export-format").value = savedFormat;
  $("export-format").addEventListener("change", () => {
    storage.set(EXPORT_KEY, $("export-format").value);
    renderExportLinks();
  });

  $("day-prev").addEventListener("click", () => loadDay(addDays(currentDay, -1)));
  $("day-next").addEventListener("click", () => loadDay(addDays(currentDay, 1)));
  $("day-today").addEventListener("click", () => loadDay(todayIn(config.timezone)));
  await loadDay(todayIn(config.timezone));
  await loadActivity();

  try {
    routine = await api.routine();
  } catch {
    // sem rotina: o alerta funciona o dia todo
  }
  renderRoutineNow();
  setInterval(renderRoutineNow, 30_000);

  $("note-form").addEventListener("submit", submitNote);
  $("activity-end").addEventListener("click", endActivity);
  $("notes-only").hidden = config.save_mode !== "notes_only";

  updateOutboxNotice();
  setInterval(retryOutbox, 15000);
  window.addEventListener("online", retryOutbox);

  if (!Recorder.isSupported()) {
    renderState("error");
    $("btn-start").disabled = true;
    showMessage("Este navegador não tem reconhecimento de voz. Use o Google Chrome.", "error");
    return;
  }

  recorder = new Recorder({
    phraseGapMs: config.phrase_gap_seconds * 1000,
    onFinal: handleFinal,
    onInterim: (text) => ($("interim").textContent = text),
    onStateChange: renderState,
    onError: (code, fatal) =>
      showMessage(ERROR_MESSAGES[code] ?? `Erro no reconhecimento: ${code}`, fatal ? "error" : "warn"),
  });

  $("btn-start").addEventListener("click", start);
  $("btn-pause").addEventListener("click", pause);
  $("btn-resume").addEventListener("click", resume);
  $("btn-stop").addEventListener("click", endDay);
  $("btn-notify").addEventListener("click", enableNotifications);

  // --- Alerta de inatividade ---
  // O service worker recebe os cliques nos botões da notificação (Sim / Não)
  navigator.serviceWorker?.register("/sw.js").catch(() => {});
  renderNotifyButton();
  watcher = new InactivityWatcher({
    minutes: config.inactivity_minutes,
    shouldWatch: shouldWatchInactivity,
    getActivity: () => currentActivity,
    onConfirm: (activity) =>
      save({ kind: "confirm", text: `Continua em: ${activity}`, activity }),
    onChange: (text) => save({ kind: "activity_change", text }),
  });

  // Aba fechando: salva o que ainda estava esperando o silêncio
  window.addEventListener("pagehide", () => recorder.flush());

  // Recupera o estado de antes do F5: se estava gravando, volta a gravar
  const previous = storage.get(STATE_KEY);
  if (previous === "recording") recorder.start();
  else if (previous === "paused" && storage.get(PAUSE_KEY)) {
    recorder.state = "paused";
    renderState("paused");
  } else renderState("idle");
}

init();

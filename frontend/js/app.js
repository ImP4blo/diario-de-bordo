// Ponto de entrada da página: liga o gravador, a API e a tela do dia.

import { api, flushOutbox, outboxSize, saveEntry } from "./api.js";
import { addDays, DayView, formatDayLabel, todayIn, weekBounds } from "./day.js";
import { Recorder } from "./recorder.js";

// Guardados no navegador para sobreviver a um F5 ou à aba fechada sem querer
const STATE_KEY = "diario.recorderState";
const PAUSE_KEY = "diario.pauseStartedAt";
const ORDER_KEY = "diario.newestFirst";

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
}

// --- Salvamento ----------------------------------------------------------

async function save(data) {
  const entry = await saveEntry(data);
  if (entry && entry.local_date === currentDay) dayView.append(entry);
  if (entry?.kind === "note") showActivity({ activity: entry.activity, since: entry.ts });
  updateOutboxNotice();
  return entry;
}

function handleFinal(text, startedAt) {
  // O servidor decide se é fala comum ou anotação ("Diário, ...")
  return save({ text, kind: "speech", ts: startedAt.toISOString() });
}

// --- Atividade atual -----------------------------------------------------

function showActivity({ activity, since }) {
  $("activity-text").textContent = activity ?? "";
  $("activity-since").textContent = activity && since ? `desde ${formatTime(since)}` : "";
  // Caixa amarela e botão "Finalizar" só quando há atividade em andamento
  $("activity").classList.toggle("activity--active", Boolean(activity));
  $("activity-end").hidden = !activity;
}

async function endActivity() {
  const activity = $("activity-text").textContent;
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
  const now = new Date().toISOString();
  const entry = await save({ text, kind: "note", ts: now });
  // Servidor fora: a nota foi para a caixa de saída, mas já vale como atividade atual
  if (!entry) showActivity({ activity: text, since: now });
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

async function loadDay(day) {
  currentDay = day;
  $("day-label").textContent = formatDayLabel(day);
  $("day-next").disabled = day >= todayIn(config.timezone);

  // Os links de exportação acompanham o dia (e a semana) que está na tela
  const [monday, friday] = weekBounds(day);
  const exportUrl = (start, end, fmt) =>
    `/api/export/transcript?start=${start}&end=${end}&fmt=${fmt}`;
  $("export-day").href = exportUrl(day, day, "md");
  $("export-week").href = exportUrl(monday, friday, "md");
  $("export-week-txt").href = exportUrl(monday, friday, "txt");

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

  $("day-prev").addEventListener("click", () => loadDay(addDays(currentDay, -1)));
  $("day-next").addEventListener("click", () => loadDay(addDays(currentDay, 1)));
  $("day-today").addEventListener("click", () => loadDay(todayIn(config.timezone)));
  await loadDay(todayIn(config.timezone));
  await loadActivity();

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

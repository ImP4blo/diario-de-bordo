// Comunicação com o backend.
//
// Inclui uma "caixa de saída" (outbox): se o servidor estiver fora do ar quando uma
// frase for reconhecida, ela fica guardada no navegador e é reenviada depois.
// Assim nada se perde. O horário vai junto, então a frase entra no lugar certo.

const OUTBOX_KEY = "diario.outbox";

class ApiError extends Error {
  constructor(status, body) {
    super(`HTTP ${status}: ${body}`);
    this.status = status;
    this.body = body;
  }

  /** Mensagens de validação do FastAPI ("detail"), prontas para mostrar na tela. */
  get messages() {
    try {
      const { detail } = JSON.parse(this.body);
      if (typeof detail === "string") return [detail];
      return detail.map((error) => error.msg.replace(/^Value error, /, ""));
    } catch {
      return [this.message];
    }
  }
}

async function request(path, { method = "GET", body } = {}) {
  const response = await fetch(path, {
    method,
    // keepalive: a requisição termina mesmo se a aba for fechada no meio dela
    keepalive: method !== "GET",
    headers: body ? { "Content-Type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!response.ok) throw new ApiError(response.status, await response.text());
  return response.status === 204 ? null : response.json();
}

export const api = {
  config: () => request("/api/config"),
  listEntries: (day) => request(`/api/entries?day=${day}`),
  currentActivity: (day) => request(`/api/entries/current-activity?day=${day}`),
  createEntry: (data) => request("/api/entries", { method: "POST", body: data }),
  updateEntry: (id, data) => request(`/api/entries/${id}`, { method: "PATCH", body: data }),
  deleteEntry: (id) => request(`/api/entries/${id}`, { method: "DELETE" }),
  routine: () => request("/api/routine"),
  saveRoutine: (data) => request("/api/routine", { method: "PUT", body: data }),
  diary: (start, end) => request(`/api/diary?start=${start}&end=${end}`),
  generateDiary: (start, end) =>
    request(`/api/diary/generate?start=${start}&end=${end}`, { method: "POST" }),
  saveDiary: (day, blocks) => request(`/api/diary/${day}`, { method: "PUT", body: { blocks } }),
  diaryDocxUrl: (start, end) => `/api/diary/docx?start=${start}&end=${end}`,
};

// --- Caixa de saída -------------------------------------------------------

function readOutbox() {
  try {
    return JSON.parse(localStorage.getItem(OUTBOX_KEY)) ?? [];
  } catch {
    return [];
  }
}

function writeOutbox(items) {
  try {
    localStorage.setItem(OUTBOX_KEY, JSON.stringify(items));
  } catch {
    // Armazenamento indisponível (aba anônima, cota cheia): seguimos sem a caixa
  }
}

// Erro 4xx significa dado inválido: reenviar não adianta, então não vai pra caixa.
const isRetryable = (err) => !(err instanceof ApiError && err.status >= 400 && err.status < 500);

/** Salva uma entrada; se o servidor não responder, guarda para reenviar. */
export async function saveEntry(data) {
  try {
    return await api.createEntry(data);
  } catch (err) {
    if (!isRetryable(err)) throw err;
    writeOutbox([...readOutbox(), data]);
    return null;
  }
}

/** Tenta reenviar o que ficou pendente. Devolve quantas entradas foram enviadas. */
export async function flushOutbox() {
  const pending = readOutbox();
  if (pending.length === 0) return 0;

  const left = [];
  for (const item of pending) {
    try {
      await api.createEntry(item);
    } catch (err) {
      if (isRetryable(err)) left.push(item);
    }
  }
  writeOutbox(left);
  return pending.length - left.length;
}

export const outboxSize = () => readOutbox().length;

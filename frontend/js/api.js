// Comunicação com o backend.
//
// Inclui uma "caixa de saída" (outbox): se o servidor estiver fora do ar quando uma
// frase for reconhecida, ela fica guardada no navegador e é reenviada depois.
// Assim nada se perde. O horário vai junto, então a frase entra no lugar certo.

import { getAccessToken, goToLogin } from "./auth.js";
import { getOwnKey } from "./ownkey.js";

const OUTBOX_KEY = "diario.outbox";

class ApiError extends Error {
  constructor(status, body) {
    super(`HTTP ${status}: ${body}`);
    this.status = status;
    this.body = body;
  }

  get detail() {
    try {
      return JSON.parse(this.body).detail;
    } catch {
      return null;
    }
  }

  /** Código do erro, quando a API manda um (ex.: "quota_exhausted"). */
  get code() {
    return this.detail?.code ?? null;
  }

  /** Mensagens de erro do FastAPI ("detail"), prontas para mostrar na tela. */
  get messages() {
    const detail = this.detail;
    if (typeof detail === "string") return [detail];
    if (detail?.message) return [detail.message];
    if (Array.isArray(detail)) return detail.map((e) => e.msg.replace(/^Value error, /, ""));
    return [this.message];
  }
}

/** Cabeçalhos de toda requisição: o "crachá" de login (modo public) e o tipo do corpo. */
async function headers(body, extra = {}) {
  const result = { ...extra };
  if (body) result["Content-Type"] = "application/json";
  const token = await getAccessToken();
  if (token) result.Authorization = `Bearer ${token}`;
  return result;
}

async function send(path, { method = "GET", body, extraHeaders } = {}) {
  const response = await fetch(path, {
    method,
    // keepalive: a requisição termina mesmo se a aba for fechada no meio dela.
    // Só para salvar falas (pequenas e urgentes); ele tem limite de tamanho.
    keepalive: method === "POST" && path.startsWith("/api/entries"),
    headers: await headers(body, extraHeaders),
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!response.ok) {
    const error = new ApiError(response.status, await response.text());
    if (response.status === 401) goToLogin(); // sessão venceu: entrar de novo
    throw error;
  }
  return response;
}

async function request(path, options) {
  const response = await send(path, options);
  return response.status === 204 ? null : response.json();
}

/** Baixa um arquivo da API. Um link comum (<a href>) não levaria o token de login. */
export async function download(path) {
  const response = await send(path);
  const disposition = response.headers.get("Content-Disposition") ?? "";
  const filename = disposition.match(/filename="([^"]+)"/)?.[1] ?? "arquivo";

  const url = URL.createObjectURL(await response.blob());
  const link = Object.assign(document.createElement("a"), { href: url, download: filename });
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
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
  // Com chave própria salva, ela vai junto (só nesta chamada) e não há limite diário
  generateDiary: (start, end) => {
    const ownKey = getOwnKey();
    return request(`/api/diary/generate?start=${start}&end=${end}`, {
      method: "POST",
      extraHeaders: ownKey ? { "X-User-AI-Key": ownKey } : {},
    });
  },
  usage: () => request("/api/diary/usage"),
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
// Exceção: 401 (sessão vencida). Depois de entrar de novo, o reenvio funciona.
const isRetryable = (err) =>
  !(err instanceof ApiError && err.status >= 400 && err.status < 500 && err.status !== 401);

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

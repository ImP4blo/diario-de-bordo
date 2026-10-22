// Alerta de inatividade.
//
// Se passar X minutos sem nenhum registro explícito (anotação, confirmação, troca ou
// fim de atividade) enquanto a gravação está ligada, pergunta:
//   "Você ainda está em: <atividade>?"  [Sim] [Não]
//
// O alerta aparece em dois lugares ao mesmo tempo:
//   1. notificação do sistema (via service worker), que aparece mesmo com o Chrome minimizado;
//   2. janela (modal) na própria página, que funciona mesmo sem permissão de notificação.

const NOTIFICATION_TAG = "inactivity";
const CHECK_INTERVAL_MS = 30_000;
const MAX_ACTIVITY_WORDS = 10;

/** Encurta textos longos: "comecei o refinamento do card 1234 com o PO e..." */
export function shortText(text, maxWords = MAX_ACTIVITY_WORDS) {
  const words = text.trim().split(/\s+/);
  return words.length <= maxWords ? text.trim() : `${words.slice(0, maxWords).join(" ")}…`;
}

const $ = (id) => document.getElementById(id);

export class InactivityWatcher {
  /**
   * @param {object} options
   * @param {number} options.minutes  tempo sem registro até o alerta
   * @param {() => boolean} options.shouldWatch  false = não alertar (pausado, parado...)
   * @param {() => string | null} options.getActivity  atividade atual (texto completo)
   * @param {(activity: string) => Promise<void>} options.onConfirm  "Sim"
   * @param {(newActivity: string) => Promise<void>} options.onChange  "Não" + nova atividade
   */
  constructor({ minutes, shouldWatch, getActivity, onConfirm, onChange }) {
    this.limitMs = minutes * 60_000;
    this.shouldWatch = shouldWatch;
    this.getActivity = getActivity;
    this.onConfirm = onConfirm;
    this.onChange = onChange;

    this.lastExplicitAt = Date.now();
    this.isOpen = false;
    this.activity = null; // atividade perguntada no alerta aberto

    this.dialog = $("inactivity-dialog");
    $("inactivity-yes").addEventListener("click", () => this.answer("yes"));
    $("inactivity-no").addEventListener("click", () => this.answer("no"));
    $("inactivity-change").addEventListener("submit", (event) => this.#submitChange(event));
    // Fechou com Esc sem responder: conta como "soneca" de mais um período
    this.dialog.addEventListener("close", () => this.#dismiss());

    // Cliques nos botões da notificação chegam do service worker como mensagem
    if ("serviceWorker" in navigator) {
      navigator.serviceWorker.addEventListener("message", (event) => {
        if (event.data?.type === "inactivity-answer") this.answer(event.data.answer);
      });
      navigator.serviceWorker.startMessages();
    }

    setInterval(() => this.check(), CHECK_INTERVAL_MS);
  }

  /** Houve registro explícito (ou a gravação começou): zera o relógio e fecha o alerta. */
  reset() {
    this.lastExplicitAt = Date.now();
    if (this.isOpen) this.dialog.close();
  }

  /** Resposta vinda da página ou da notificação: "yes", "no" ou "open" (clicou no corpo). */
  async answer(answer) {
    if (!this.isOpen) return;
    if (answer === "yes" && this.activity) {
      await this.onConfirm(this.activity);
      this.reset();
    } else if (answer === "no" || !this.activity) {
      this.#showChangeStep();
    }
    // "open": a página já está com o alerta na tela, nada a fazer
  }

  /** Abre o alerta se o tempo sem registro estourou. Roda sozinho a cada 30s. */
  check() {
    if (this.isOpen || !this.shouldWatch()) return;
    if (Date.now() - this.lastExplicitAt >= this.limitMs) this.#open();
  }

  #open() {
    this.isOpen = true;
    this.activity = this.getActivity();
    const minutes = Math.round((Date.now() - this.lastExplicitAt) / 60_000);
    const title = `Já se passaram ${minutes} minutos`;

    $("inactivity-title").textContent = title;
    if (this.activity) {
      $("inactivity-activity").textContent = shortText(this.activity);
      $("inactivity-ask").hidden = false;
      $("inactivity-change").hidden = true;
    } else {
      this.#showChangeStep();
    }
    if (!this.dialog.open) this.dialog.showModal();

    document.title = "⏰ Ainda está aí? · Diário de Bordo";
    this.#notify(title);
  }

  #showChangeStep() {
    $("inactivity-ask").hidden = true;
    $("inactivity-change").hidden = false;
    $("inactivity-change-label").textContent = this.activity
      ? "Qual é a nova atividade?"
      : "Sem registro há um tempo. O que você está fazendo agora?";
    if (!this.dialog.open) this.dialog.showModal();
    $("inactivity-input").focus();
  }

  async #submitChange(event) {
    event.preventDefault();
    const text = $("inactivity-input").value.trim();
    if (!text) return;
    $("inactivity-input").value = "";
    await this.onChange(text);
    this.reset();
  }

  #dismiss() {
    if (!this.isOpen) return;
    this.isOpen = false;
    this.lastExplicitAt = Date.now();
    document.title = document.title.replace("⏰ Ainda está aí? · ", "");
    this.#closeNotifications();
  }

  async #notify(title) {
    if (!("Notification" in window) || Notification.permission !== "granted") return;
    try {
      const registration = await navigator.serviceWorker.ready;
      await registration.showNotification(title, {
        body: this.activity
          ? `Você ainda está em: ${shortText(this.activity)}?`
          : "O que você está fazendo agora?",
        tag: NOTIFICATION_TAG,
        requireInteraction: true, // fica na tela até a pessoa responder
        actions: this.activity
          ? [
              { action: "yes", title: "Sim" },
              { action: "no", title: "Não" },
            ]
          : [],
      });
    } catch {
      // Sem notificação do sistema: o modal na página continua funcionando
    }
  }

  async #closeNotifications() {
    try {
      const registration = await navigator.serviceWorker.ready;
      const open = await registration.getNotifications({ tag: NOTIFICATION_TAG });
      open.forEach((notification) => notification.close());
    } catch {
      // nada a fechar
    }
  }
}

/** Pede permissão de notificação. Só pode ser chamado a partir de um clique. */
export async function requestNotificationPermission() {
  if (!("Notification" in window)) return "unsupported";
  if (Notification.permission !== "default") return Notification.permission;
  return Notification.requestPermission();
}

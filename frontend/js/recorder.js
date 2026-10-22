// Gravador contínuo sobre a Web Speech API do Chrome.
//
// O reconhecimento do Chrome "cai" sozinho com frequência (silêncio longo, rede,
// limite de tempo da sessão). Esta classe esconde isso: enquanto o estado for
// "recording", ela religa automaticamente, esperando um pouco mais a cada falha
// seguida (backoff) para não ficar martelando o serviço.

const Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;

// Erros sem solução automática: precisam de ação da pessoa (ex.: liberar o microfone).
const FATAL_ERRORS = new Set(["not-allowed", "service-not-allowed", "language-not-supported"]);
// Erros que fazem parte do funcionamento normal (silêncio, parada manual).
const IGNORED_ERRORS = new Set(["no-speech", "aborted"]);

// Uma sessão que durou mais que isso "deu certo": zera o contador de falhas.
const HEALTHY_SESSION_MS = 5000;
const MAX_RETRY_DELAY_MS = 30000;

export class Recorder {
  /**
   * @param {object} callbacks
   * @param {(text: string, startedAt: Date) => void} callbacks.onFinal  trecho reconhecido
   * @param {(text: string) => void} callbacks.onInterim  texto parcial, em tempo real
   * @param {(state: string) => void} callbacks.onStateChange  idle | recording | paused | error
   * @param {(code: string, fatal: boolean) => void} callbacks.onError
   */
  constructor({ onFinal, onInterim, onStateChange, onError }) {
    this.onFinal = onFinal;
    this.onInterim = onInterim;
    this.onStateChange = onStateChange;
    this.onError = onError;

    this.state = "idle";
    this.rec = null;
    this.retries = 0;
    this.retryTimer = null;
    this.sessionStartedAt = 0;
    this.phraseStartedAt = null;
  }

  static isSupported() {
    return Boolean(Recognition);
  }

  start() {
    if (this.state === "recording") return;
    this.retries = 0;
    this.#setState("recording");
    this.#listen();
  }

  pause() {
    this.#setState("paused");
    this.#stopListening();
  }

  stop() {
    this.#setState("idle");
    this.#stopListening();
  }

  #setState(state) {
    this.state = state;
    this.onStateChange(state);
  }

  #listen() {
    const rec = new Recognition();
    rec.lang = "pt-BR";
    rec.continuous = true;
    rec.interimResults = true;

    rec.onstart = () => (this.sessionStartedAt = Date.now());
    rec.onresult = (event) => this.#handleResult(event);
    rec.onerror = (event) => this.#handleError(event.error);
    rec.onend = () => this.#handleEnd();

    this.rec = rec;
    try {
      rec.start();
    } catch {
      // start() lança erro se já houver uma sessão ativa; tentamos de novo depois
      this.#scheduleRestart();
    }
  }

  #handleResult(event) {
    let interim = "";
    for (let i = event.resultIndex; i < event.results.length; i++) {
      const result = event.results[i];
      // Guardamos quando a frase COMEÇOU, não quando terminou de ser reconhecida
      this.phraseStartedAt ??= new Date();

      if (result.isFinal) {
        const text = result[0].transcript.trim();
        if (text) this.onFinal(text, this.phraseStartedAt);
        this.phraseStartedAt = null;
      } else {
        interim += result[0].transcript;
      }
    }
    this.onInterim(interim.trim());
  }

  #handleError(code) {
    if (IGNORED_ERRORS.has(code)) return;
    const fatal = FATAL_ERRORS.has(code);
    this.onError(code, fatal);
    if (fatal) this.#setState("error");
    // Erros não fatais (rede, microfone ocupado...) são tratados no onend, que vem logo depois
  }

  #handleEnd() {
    this.rec = null;
    this.phraseStartedAt = null;
    this.onInterim("");
    if (this.state !== "recording") return;

    if (Date.now() - this.sessionStartedAt > HEALTHY_SESSION_MS) this.retries = 0;
    this.#scheduleRestart();
  }

  #scheduleRestart() {
    // 0,5s, 1s, 2s, 4s... até 30s
    const delay = Math.min(500 * 2 ** this.retries, MAX_RETRY_DELAY_MS);
    this.retries++;
    clearTimeout(this.retryTimer);
    this.retryTimer = setTimeout(() => {
      if (this.state === "recording") this.#listen();
    }, delay);
  }

  #stopListening() {
    clearTimeout(this.retryTimer);
    // stop() (e não abort()) ainda entrega a última frase que estava sendo reconhecida
    this.rec?.stop();
    this.onInterim("");
  }
}

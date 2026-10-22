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

// O Chrome finaliza uma frase a cada pausa curta (até uma respirada). Para não picar
// a fala em vários itens, juntamos os trechos num buffer e só entregamos depois de
// alguns segundos de silêncio.
const DEFAULT_PHRASE_GAP_MS = 5000;

// Uma sessão que durou mais que isso "deu certo": zera o contador de falhas.
const HEALTHY_SESSION_MS = 5000;
const MAX_RETRY_DELAY_MS = 30000;

export class Recorder {
  /**
   * @param {object} options
   * @param {(text: string, startedAt: Date) => void} options.onFinal  fala completa
   * @param {(text: string) => void} options.onInterim  texto ainda não salvo, em tempo real
   * @param {(state: string) => void} options.onStateChange  idle | recording | paused | error
   * @param {(code: string, fatal: boolean) => void} options.onError
   * @param {number} [options.phraseGapMs]  silêncio que encerra uma fala
   */
  constructor({ onFinal, onInterim, onStateChange, onError, phraseGapMs }) {
    this.onFinal = onFinal;
    this.onInterim = onInterim;
    this.onStateChange = onStateChange;
    this.onError = onError;
    this.phraseGapMs = phraseGapMs ?? DEFAULT_PHRASE_GAP_MS;

    this.state = "idle";
    this.rec = null;
    this.retries = 0;
    this.retryTimer = null;
    this.sessionStartedAt = 0;
    this.phraseStartedAt = null;

    // Trechos finais aguardando o silêncio para virar uma fala só
    this.buffer = [];
    this.bufferStartedAt = null;
    this.gapTimer = null;
  }

  /** Entrega já o que estiver no buffer (ao pausar, encerrar ou fechar a aba). */
  flush() {
    clearTimeout(this.gapTimer);
    if (this.buffer.length > 0) this.onFinal(this.buffer.join(" "), this.bufferStartedAt);
    this.buffer = [];
    this.bufferStartedAt = null;
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
        if (text) {
          this.bufferStartedAt ??= this.phraseStartedAt;
          this.buffer.push(text);
        }
        this.phraseStartedAt = null;
      } else {
        interim += result[0].transcript;
      }
    }
    this.#showPending(interim);

    // Qualquer som reconhecido reinicia a contagem do silêncio
    clearTimeout(this.gapTimer);
    if (this.buffer.length > 0) {
      this.gapTimer = setTimeout(() => this.flush(), this.phraseGapMs);
    }
  }

  #showPending(interim = "") {
    this.onInterim([...this.buffer, interim.trim()].join(" ").trim());
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
    // O buffer sobrevive ao religamento: a fala continua na próxima sessão
    this.#showPending();
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
    this.flush();
    // stop() (e não abort()) ainda entrega a frase em andamento; ela cai no buffer
    // e o timer de silêncio a salva logo em seguida
    this.rec?.stop();
    this.onInterim("");
  }
}

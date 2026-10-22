// Tela do dia: lista cronológica das entradas, com editar e apagar.

import { api } from "./api.js";

const KIND_LABELS = {
  speech: "Fala",
  note: "Anotação",
  pause: "Pausa",
  confirm: "Confirmação",
  activity_change: "Nova atividade",
  activity_end: "Fim da atividade",
};

/** "2026-10-26" + n dias. Usamos meio-dia UTC para nunca "pular" de dia por causa de fuso. */
export function addDays(day, n) {
  const date = new Date(`${day}T12:00:00Z`);
  date.setUTCDate(date.getUTCDate() + n);
  return date.toISOString().slice(0, 10);
}

/** Segunda e sexta da semana de `day` (mesma regra de week_bounds no backend). */
export function weekBounds(day) {
  const weekday = new Date(`${day}T12:00:00Z`).getUTCDay(); // 0 = domingo
  const monday = addDays(day, -((weekday + 6) % 7));
  return [monday, addDays(monday, 4)];
}

/** Data de hoje ("2026-10-26") no fuso informado. O locale en-CA já formata assim. */
export function todayIn(timeZone) {
  return new Intl.DateTimeFormat("en-CA", { timeZone }).format(new Date());
}

/** "Segunda-feira, 26/10/2026" */
export function formatDayLabel(day) {
  const label = new Intl.DateTimeFormat("pt-BR", {
    timeZone: "UTC",
    weekday: "long",
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  }).format(new Date(`${day}T12:00:00Z`));
  return label.charAt(0).toUpperCase() + label.slice(1);
}

export class DayView {
  constructor({ listEl, emptyEl, timeZone, newestFirst = true }) {
    this.listEl = listEl;
    this.emptyEl = emptyEl;
    this.newestFirst = newestFirst;
    this.timeFormat = new Intl.DateTimeFormat("pt-BR", {
      timeZone,
      hour: "2-digit",
      minute: "2-digit",
    });
  }

  /** `entries` chega da API em ordem cronológica; invertemos se for o caso. */
  render(entries) {
    const ordered = this.newestFirst ? [...entries].reverse() : entries;
    this.listEl.replaceChildren(...ordered.map((entry) => this.#renderEntry(entry)));
    this.#updateEmpty();
  }

  /** Troca a ordem só invertendo os itens que já estão na tela, sem chamar a API. */
  setNewestFirst(newestFirst) {
    if (newestFirst === this.newestFirst) return;
    this.newestFirst = newestFirst;
    this.listEl.replaceChildren(...[...this.listEl.children].reverse());
  }

  /** Item novo entra no topo (mais recentes primeiro) ou no fim da lista. */
  append(entry) {
    const item = this.#renderEntry(entry);
    if (this.newestFirst) this.listEl.prepend(item);
    else this.listEl.append(item);
    this.#updateEmpty();
    item.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }

  #updateEmpty() {
    this.emptyEl.hidden = this.listEl.children.length > 0;
  }

  #time(iso) {
    return this.timeFormat.format(new Date(iso));
  }

  #describe(entry) {
    if (entry.kind === "pause") {
      return entry.ends_at
        ? `Pausado das ${this.#time(entry.ts)} às ${this.#time(entry.ends_at)}`
        : `Pausado desde ${this.#time(entry.ts)}`;
    }
    return entry.text;
  }

  #renderEntry(entry) {
    const li = document.createElement("li");
    li.className = `entry entry--${entry.kind}`;

    const time = document.createElement("time");
    time.className = "entry__time";
    time.dateTime = entry.ts;
    time.textContent = this.#time(entry.ts);

    const badge = document.createElement("span");
    badge.className = "entry__badge";
    badge.textContent = KIND_LABELS[entry.kind] ?? entry.kind;

    // textContent (e nunca innerHTML) para o texto falado jamais virar HTML na página
    const text = document.createElement("p");
    text.className = "entry__text";
    text.textContent = this.#describe(entry);

    const actions = document.createElement("div");
    actions.className = "entry__actions";
    if (entry.kind !== "pause") {
      actions.append(this.#button("Editar", () => this.#startEditing(li, text, entry)));
    }
    actions.append(this.#button("Apagar", () => this.#delete(li, entry)));

    li.append(time, badge, text, actions);
    return li;
  }

  #button(label, onClick) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "btn btn--small btn--ghost";
    button.textContent = label;
    button.addEventListener("click", onClick);
    return button;
  }

  #startEditing(li, textEl, entry) {
    const form = document.createElement("form");
    form.className = "entry__edit";
    const input = document.createElement("input");
    input.value = entry.text;
    input.setAttribute("aria-label", "Texto da entrada");
    const save = this.#button("Salvar", () => {});
    save.type = "submit";
    const cancel = this.#button("Cancelar", () => form.replaceWith(textEl));

    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const updated = await api.updateEntry(entry.id, { text: input.value });
      li.replaceWith(this.#renderEntry(updated));
    });
    form.addEventListener("keydown", (event) => {
      if (event.key === "Escape") form.replaceWith(textEl);
    });

    form.append(input, save, cancel);
    textEl.replaceWith(form);
    input.focus();
  }

  async #delete(li, entry) {
    if (!confirm(`Apagar "${this.#describe(entry)}"?`)) return;
    await api.deleteEntry(entry.id);
    li.remove();
    this.#updateEmpty();
  }
}

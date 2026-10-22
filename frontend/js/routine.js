// Regras da rotina fixa no navegador: "agora estou num bloco fixo ou fora do expediente?"
// Usado para o alerta de inatividade ficar quieto durante a daily, o intervalo etc.

/** Horário e dia da semana agora, no fuso configurado: { clock: "09:20", weekday: 1 } */
export function nowIn(timeZone) {
  const parts = new Intl.DateTimeFormat("en-GB", {
    timeZone,
    hour: "2-digit",
    minute: "2-digit",
    hourCycle: "h23",
    weekday: "short",
  }).formatToParts(new Date());
  const get = (type) => parts.find((part) => part.type === type).value;
  const weekday = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"].indexOf(get("weekday"));
  return { clock: `${get("hour")}:${get("minute")}`, weekday };
}

/**
 * Onde "agora" cai na rotina.
 * Horários "HH:MM" com zero à esquerda podem ser comparados como texto: "09:15" < "10:00".
 * @returns {{kind: "off"} | {kind: "block", block: object} | {kind: "work"}}
 */
export function routineStatus(routine, { clock, weekday }) {
  const isWeekend = weekday === 0 || weekday === 6;
  if (isWeekend || clock < routine.work_start || clock >= routine.work_end) return { kind: "off" };

  const block = routine.blocks.find((b) => clock >= b.start && clock < b.end);
  return block ? { kind: "block", block } : { kind: "work" };
}

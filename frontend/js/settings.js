// Tela de Ajustes: edita o expediente e os blocos da rotina fixa.

import { api } from "./api.js";
import { startPage } from "./session.js";

const $ = (id) => document.getElementById(id);

function showMessage(text, kind = "info") {
  const el = $("settings-message");
  el.textContent = text;
  el.dataset.kind = kind;
  el.hidden = !text;
}

function updateEmpty() {
  $("blocks-empty").hidden = $("blocks").children.length > 0;
}

/** Cria uma linha de bloco a partir do <template> do HTML. */
function addBlock({ start = "", end = "", activity = "" } = {}) {
  const row = $("block-template").content.firstElementChild.cloneNode(true);
  row.querySelector(".block__start").value = start;
  row.querySelector(".block__end").value = end;
  row.querySelector(".block__activity").value = activity;
  row.querySelector(".block__remove").addEventListener("click", () => {
    row.remove();
    updateEmpty();
  });
  $("blocks").append(row);
  updateEmpty();
  return row;
}

/** Lê o formulário no mesmo formato que a API espera. */
function readForm() {
  return {
    work_start: $("work-start").value,
    work_end: $("work-end").value,
    blocks: [...$("blocks").children].map((row) => ({
      start: row.querySelector(".block__start").value,
      end: row.querySelector(".block__end").value,
      activity: row.querySelector(".block__activity").value.trim(),
    })),
  };
}

function render(routine) {
  $("work-start").value = routine.work_start;
  $("work-end").value = routine.work_end;
  $("blocks").replaceChildren();
  routine.blocks.forEach(addBlock);
  updateEmpty();
}

async function save(event) {
  event.preventDefault();
  const data = readForm();
  if (data.blocks.some((b) => !b.start || !b.end || !b.activity)) {
    showMessage("Preencha início, fim e atividade de todos os blocos.", "error");
    return;
  }
  try {
    // A API devolve a rotina já ordenada por horário
    render(await api.saveRoutine(data));
    showMessage("Rotina salva!", "info");
  } catch (err) {
    // Erros de validação (ex.: bloco que termina antes de começar) vêm do servidor
    showMessage(err.messages?.join(" · ") ?? "Não foi possível salvar.", "error");
  }
}

async function init() {
  $("add-block").addEventListener("click", () =>
    addBlock().querySelector(".block__start").focus(),
  );
  $("routine-form").addEventListener("submit", save);
  try {
    await startPage();
    render(await api.routine());
  } catch {
    showMessage("Servidor fora do ar. Rode o uvicorn e recarregue a página.", "error");
  }
}

init();

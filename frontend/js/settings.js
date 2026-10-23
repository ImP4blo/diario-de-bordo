// Tela de Ajustes: edita o expediente e os blocos da rotina fixa.

import { api } from "./api.js";
import { signOut } from "./auth.js";
import {
  getOwnKey,
  maskKey,
  PRIVACY_NOTE,
  removeOwnKey,
  STEPS_HTML,
  saveOwnKey,
} from "./ownkey.js";
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

// --- Chave própria de IA ------------------------------------------------------

function renderOwnKey() {
  const key = getOwnKey();
  $("own-key-saved").hidden = !key;
  $("own-key-new").hidden = Boolean(key);
  $("own-key-masked").textContent = maskKey(key); // nunca a chave inteira
}

function keyMessage(text, kind = "info") {
  $("own-key-message").textContent = text;
  $("own-key-message").dataset.kind = kind;
  $("own-key-message").hidden = !text;
}

function initOwnKey() {
  $("own-key-steps").innerHTML = STEPS_HTML;
  $("own-key-privacy").textContent = `⚠️ ${PRIVACY_NOTE}`;
  renderOwnKey();

  $("own-key-form").addEventListener("submit", (event) => {
    event.preventDefault();
    try {
      saveOwnKey($("own-key-input").value);
      $("own-key-input").value = "";
      keyMessage("Chave salva! Os próximos diários usam a sua chave, sem limite.");
      renderOwnKey();
    } catch (err) {
      keyMessage(err.message, "error");
    }
  });
  $("own-key-remove").addEventListener("click", () => {
    if (!confirm("Remover a sua chave deste navegador?")) return;
    removeOwnKey();
    keyMessage("Chave removida. O app volta a usar o limite diário.");
    renderOwnKey();
  });
}

// --- Apagar a conta (LGPD) -----------------------------------------------------

const CONFIRM_WORD = "APAGAR";

function initDangerZone(config) {
  if (config.app_mode !== "public") return; // no modo local não existe conta
  $("danger-zone").hidden = false;

  // O botão só liga quando a pessoa digita a palavra exata: evita clique sem querer
  $("delete-confirm").addEventListener("input", () => {
    $("delete-button").disabled = $("delete-confirm").value.trim() !== CONFIRM_WORD;
  });

  $("delete-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    if ($("delete-confirm").value.trim() !== CONFIRM_WORD) return;
    $("delete-button").disabled = true;
    try {
      const result = await api.deleteAccount();
      // Limpa o que ficou neste navegador (chave própria, caixa de saída, preferências)
      try {
        Object.keys(localStorage)
          .filter((k) => k.startsWith("diario."))
          .forEach((k) => localStorage.removeItem(k));
      } catch {
        // sem armazenamento: nada a limpar
      }
      $("delete-message").textContent = `${result.message} Saindo...`;
      $("delete-message").hidden = false;
      setTimeout(signOut, 2500);
    } catch (err) {
      $("delete-message").textContent =
        err.messages?.join(" · ") ?? "Não foi possível apagar a conta.";
      $("delete-message").dataset.kind = "error";
      $("delete-message").hidden = false;
      $("delete-button").disabled = false;
    }
  });
}

async function init() {
  initOwnKey();
  $("add-block").addEventListener("click", () =>
    addBlock().querySelector(".block__start").focus(),
  );
  $("routine-form").addEventListener("submit", save);
  try {
    initDangerZone(await startPage());
    render(await api.routine());
  } catch {
    showMessage("Servidor fora do ar. Rode o uvicorn e recarregue a página.", "error");
  }
}

init();

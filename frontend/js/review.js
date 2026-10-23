// Tela de revisão: gera o diário com IA, permite editar cada bloco e salva.
//
// O período vem da URL: review.html?start=2026-10-26&end=2026-10-30
// (com &generate=1 a geração começa sozinha ao abrir).

import { api, download } from "./api.js";
import { formatDayLabel } from "./day.js";
import { startPage } from "./session.js";

const NO_RECORD = "Sem registro";
const STATUS_LABELS = { draft: "Rascunho da IA", reviewed: "Revisado ✔" };

const $ = (id) => document.getElementById(id);
const params = new URLSearchParams(location.search);
const start = params.get("start");
const end = params.get("end") ?? start;

let dirty = false; // há edição não salva?

function showMessage(text, kind = "info") {
  $("message").textContent = text;
  $("message").dataset.kind = kind;
  $("message").hidden = !text;
}

function setDirty(value) {
  dirty = value;
  $("btn-save").disabled = !value;
  if (value) showMessage("Alterações não salvas.", "warn");
}

function formatPeriod() {
  const br = (day) => day.split("-").reverse().join("/");
  return start === end ? formatDayLabel(start) : `${br(start)} a ${br(end)}`;
}

// --- Montagem da tela -------------------------------------------------------

function blockRow(block = { inicio: "", fim: "", atividade: "", descricao: "" }) {
  const row = $("block-template").content.firstElementChild.cloneNode(true);
  row.querySelector(".review-block__start").value = block.inicio;
  row.querySelector(".review-block__end").value = block.fim;
  row.querySelector(".review-block__activity").value = block.atividade;
  row.querySelector(".review-block__description").value = block.descricao;
  row.classList.toggle("review-block--empty", block.atividade === NO_RECORD);

  row.querySelector(".review-block__remove").addEventListener("click", () => {
    row.remove();
    setDirty(true);
  });
  return row;
}

function daySection({ day, blocks, status, provider }) {
  const section = $("day-template").content.firstElementChild.cloneNode(true);
  section.dataset.day = day;
  section.querySelector(".review-day__title").textContent = formatDayLabel(day);
  const badge = section.querySelector(".review-day__status");
  badge.textContent = STATUS_LABELS[status] ?? status;
  badge.dataset.status = status;
  if (provider) badge.title = `Gerado por ${provider}`;

  const list = section.querySelector(".review-blocks");
  list.append(...blocks.map((block) => blockRow(block)));
  section.querySelector(".review-day__add").addEventListener("click", () => {
    const row = blockRow();
    list.append(row);
    row.querySelector(".review-block__start").focus();
    setDirty(true);
  });
  return section;
}

function render(days) {
  $("days").replaceChildren(...days.map(daySection));
  $("btn-word").disabled = days.length === 0;
  setDirty(false);
}

/** Lê os blocos de um dia na tela, no formato da API. */
function readDay(section) {
  return [...section.querySelectorAll(".review-block")].map((row) => ({
    inicio: row.querySelector(".review-block__start").value,
    fim: row.querySelector(".review-block__end").value,
    atividade: row.querySelector(".review-block__activity").value.trim(),
    descricao: row.querySelector(".review-block__description").value.trim(),
  }));
}

// --- Ações --------------------------------------------------------------------

async function generate() {
  const hasReviewed = document.querySelector('[data-status="reviewed"]');
  if ((dirty || hasReviewed) && !confirm("Gerar de novo substitui as suas edições. Continuar?")) {
    return;
  }
  $("btn-generate").disabled = true;
  showMessage("🤖 Gerando com IA... pode levar até 1 minuto por dia.");
  try {
    const days = await api.generateDiary(start, end);
    render(days);
    showMessage(`Pronto! ${days.length} dia(s) gerado(s). Revise e clique em Salvar revisão.`);
  } catch (err) {
    showMessage(err.messages?.join(" · ") ?? "Não foi possível gerar o diário.", "error");
  } finally {
    $("btn-generate").disabled = false;
  }
}

/** Salva todos os dias da tela. Devolve true se deu certo. */
async function save() {
  const sections = [...document.querySelectorAll(".review-day")];
  const invalid = sections.some((section) =>
    readDay(section).some((b) => !b.inicio || !b.fim || !b.atividade),
  );
  if (invalid) {
    showMessage("Preencha início, fim e atividade de todos os blocos.", "error");
    return false;
  }
  try {
    const saved = [];
    for (const section of sections) {
      saved.push(await api.saveDiary(section.dataset.day, readDay(section)));
    }
    render(saved);
    showMessage("Revisão salva!");
    return true;
  } catch (err) {
    showMessage(err.messages?.join(" · ") ?? "Não foi possível salvar.", "error");
    return false;
  }
}

/** Baixa o Word. Se houver edição pendente, salva antes para não baixar versão velha. */
async function downloadWord() {
  if (dirty && !(await save())) return;
  try {
    await download(api.diaryDocxUrl(start, end));
  } catch (err) {
    showMessage(err.messages?.join(" · ") ?? "Não foi possível baixar o Word.", "error");
  }
}

async function init() {
  if (!start) {
    showMessage("Abra esta tela pelos botões de diário da página principal.", "error");
    $("btn-generate").disabled = true;
    return;
  }
  $("period").textContent = formatPeriod();
  document.title = `Revisão ${formatPeriod()} · Diário de Bordo`;
  try {
    await startPage();
  } catch {
    showMessage("Servidor fora do ar. Rode o uvicorn e recarregue a página.", "error");
    return;
  }

  $("btn-generate").addEventListener("click", generate);
  $("btn-save").addEventListener("click", save);
  $("btn-word").addEventListener("click", downloadWord);
  // Qualquer digitação nos campos marca a tela como "alterada"
  $("days").addEventListener("input", () => setDirty(true));
  window.addEventListener("beforeunload", (event) => {
    if (dirty) event.preventDefault(); // o navegador pergunta se quer mesmo sair
  });

  if (params.get("generate") === "1") {
    // Tira o generate=1 da URL: um F5 não gera (e gasta a IA) de novo
    history.replaceState(null, "", `?start=${start}&end=${end}`);
    await generate();
    return;
  }
  try {
    const days = await api.diary(start, end);
    render(days);
    if (days.length === 0) showMessage('Nenhum diário gerado ainda. Clique em "Gerar com IA".');
  } catch {
    showMessage("Servidor fora do ar. Rode o uvicorn e recarregue a página.", "error");
  }
}

init();

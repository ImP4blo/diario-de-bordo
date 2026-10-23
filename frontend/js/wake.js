// "Acordando o servidor...".
//
// No plano gratuito do Render, a API "dorme" depois de ~15 minutos sem uso e leva
// até 1 minuto para acordar. O site em si não dorme, então ele abre na hora e
// mostra este aviso enquanto chama /api/health até a API responder.
// Se a resposta vier rápido (API acordada), o aviso nem aparece.

import { apiUrl } from "./api.js";

const QUICK_MS = 1500; // menos que isso: a API já estava acordada, nada a mostrar
const ATTEMPT_MS = 10_000;
const GIVE_UP_MS = 120_000;

async function ping() {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), ATTEMPT_MS);
  try {
    const response = await fetch(apiUrl("/api/health"), { signal: controller.signal });
    return response.ok;
  } catch {
    return false;
  } finally {
    clearTimeout(timer);
  }
}

function overlay() {
  const el = document.createElement("div");
  el.className = "wake";
  el.setAttribute("role", "status");
  el.innerHTML = `
    <div class="wake__card">
      <div class="wake__spinner" aria-hidden="true"></div>
      <h2 class="wake__title">Acordando o servidor…</h2>
      <p class="wake__text">
        O app fica "dormindo" quando ninguém usa por um tempo (plano gratuito).
        Isso leva até 1 minuto, só na primeira vez.
      </p>
      <p class="wake__timer hint"></p>
    </div>`;
  document.body.append(el);
  return el;
}

/** Espera a API responder. Devolve true quando ela está pronta. */
export async function waitForServer() {
  const quick = await Promise.race([
    ping(),
    new Promise((resolve) => setTimeout(() => resolve(null), QUICK_MS)),
  ]);
  if (quick) return true;

  const el = overlay();
  const began = Date.now();
  const timer = setInterval(() => {
    const seconds = Math.floor((Date.now() - began) / 1000);
    el.querySelector(".wake__timer").textContent = `${seconds}s`;
  }, 500);

  try {
    while (Date.now() - began < GIVE_UP_MS) {
      if (await ping()) return true;
      await new Promise((resolve) => setTimeout(resolve, 2000));
    }
    el.querySelector(".wake__title").textContent = "O servidor não respondeu";
    el.querySelector(".wake__text").textContent =
      "Pode ser instabilidade do serviço. Recarregue a página em alguns minutos.";
    return false;
  } finally {
    clearInterval(timer);
    if (el.querySelector(".wake__title").textContent.startsWith("Acordando")) el.remove();
  }
}

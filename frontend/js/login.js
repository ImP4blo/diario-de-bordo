// Tela de login: Google ou link mágico por e-mail.

import { api } from "./api.js";
import { getAccessToken, initAuth, signInWithEmail, signInWithGoogle } from "./auth.js";
import { initInstallButtons } from "./install.js";

const $ = (id) => document.getElementById(id);

function showMessage(text, kind = "info") {
  $("login-message").textContent = text;
  $("login-message").dataset.kind = kind;
  $("login-message").hidden = !text;
}

async function loginWithGoogle() {
  try {
    await signInWithGoogle(); // o navegador vai para o Google e volta logado
  } catch (err) {
    showMessage(`Não foi possível entrar com o Google: ${err.message}`, "error");
  }
}

async function loginWithEmail(event) {
  event.preventDefault();
  const email = $("login-email").value.trim();
  const button = event.submitter;
  button.disabled = true;
  try {
    await signInWithEmail(email);
    showMessage(`Pronto! Enviamos um link para ${email}. Abra o e-mail e clique nele para entrar.`);
  } catch (err) {
    // O Supabase limita quantos e-mails saem por hora no plano gratuito
    const tooMany = /rate limit/i.test(err.message);
    showMessage(
      tooMany
        ? "Muitos pedidos em pouco tempo. Espere alguns minutos ou entre com o Google."
        : `Não foi possível enviar o link: ${err.message}`,
      "error",
    );
  } finally {
    button.disabled = false;
  }
}

async function init() {
  initInstallButtons();
  let config;
  try {
    config = await api.config();
  } catch {
    showMessage("Servidor acordando ou fora do ar. Tente de novo em instantes.", "error");
    return;
  }
  // Sem login no modo local, ou já logado: vai direto para o app
  if (!(await initAuth(config)) || (await getAccessToken())) {
    location.replace("index.html");
    return;
  }
  $("login-google").addEventListener("click", loginWithGoogle);
  $("login-email-form").addEventListener("submit", loginWithEmail);
}

init();

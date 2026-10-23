// Começo comum de toda página do app: carrega a configuração, prepara o login e
// mostra quem está logado no cabeçalho (com o botão Sair).

import { api } from "./api.js";
import { getUser, initAuth, requireLogin, signOut } from "./auth.js";
import { initInstallButtons } from "./install.js";

/** Devolve a configuração pública. No modo public, sem login, vai para login.html. */
export async function startPage() {
  const config = await api.config();
  await initAuth(config);
  await requireLogin();
  await renderUserBox();
  initInstallButtons();
  return config;
}

async function renderUserBox() {
  const box = document.getElementById("user-box");
  const user = await getUser();
  if (!box || !user) return;

  const name = user.user_metadata?.full_name ?? user.email;
  box.querySelector(".user-box__name").textContent = name;
  box.querySelector(".user-box__name").title = user.email ?? "";
  box.querySelector(".user-box__logout").addEventListener("click", signOut);
  box.hidden = false;
}

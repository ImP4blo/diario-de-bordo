// Chave PRÓPRIA de IA da pessoa (Google AI Studio / Gemini).
//
// Regras de segurança:
// - fica só neste navegador (localStorage), nunca no servidor nem no banco;
// - vai para a API só na hora de gerar o diário, por HTTPS, e não é registrada;
// - na tela, nunca aparece inteira de novo: só mascarada (AIza••••••K0oY).

const KEY = "diario.ownAiKey";

export const AI_STUDIO_URL = "https://aistudio.google.com/apikey";

export function getOwnKey() {
  try {
    return localStorage.getItem(KEY);
  } catch {
    return null;
  }
}

export function saveOwnKey(value) {
  const key = value.trim();
  if (key.length < 20) throw new Error("Essa chave parece incompleta. Copie a chave inteira.");
  try {
    localStorage.setItem(KEY, key);
  } catch {
    throw new Error("O navegador não deixou salvar (aba anônima?).");
  }
}

export function removeOwnKey() {
  try {
    localStorage.removeItem(KEY);
  } catch {
    // nada guardado
  }
}

/** "AIza••••••K0oY": dá para reconhecer a chave sem expor o segredo. */
export function maskKey(key) {
  return key ? `${key.slice(0, 4)}••••••${key.slice(-4)}` : "";
}

/** Passo a passo para leigos (texto fixo, escrito aqui: seguro como HTML). */
export const STEPS_HTML = `
  <li>Abra o <a href="${AI_STUDIO_URL}" target="_blank" rel="noopener">Google AI Studio</a> (abre em outra aba).</li>
  <li>Entre com a sua conta Google.</li>
  <li>Clique em <strong>Get API key</strong> e depois em <strong>Create API key</strong>.</li>
  <li>Copie a chave (começa com <strong>AIza</strong>) e cole no campo abaixo.</li>`;

export const PRIVACY_NOTE =
  "Privacidade: no plano gratuito do Google AI Studio, o Google pode usar o conteúdo " +
  "enviado para melhorar os produtos dele. A chave fica só neste navegador.";

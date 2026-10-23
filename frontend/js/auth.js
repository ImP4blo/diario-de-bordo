// Login com o Supabase Auth (só no modo "public").
//
// O Supabase cuida de tudo que é delicado: Google, link por e-mail, guardar a sessão
// e renovar o token antes de vencer. Aqui só pedimos o token para mandar à API.
//
// A biblioteca só é baixada no modo public (import dinâmico): no modo local o app
// continua funcionando até sem internet para o CDN.

const SUPABASE_JS = "https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2.45.4/+esm";

let client = null;

/** Prepara o cliente do Supabase. Devolve null no modo local (sem login). */
export async function initAuth(config) {
  if (config.app_mode !== "public") return null;
  const { createClient } = await import(SUPABASE_JS);
  client = createClient(config.supabase_url, config.supabase_publishable_key);
  return client;
}

export const isLoginEnabled = () => client !== null;

/** Token atual (ou null). O Supabase renova sozinho quando está perto de vencer. */
export async function getAccessToken() {
  if (!client) return null;
  const { data } = await client.auth.getSession();
  return data.session?.access_token ?? null;
}

export async function getUser() {
  if (!client) return null;
  const { data } = await client.auth.getSession();
  return data.session?.user ?? null;
}

/** Sem sessão no modo public: manda para a tela de login. */
export async function requireLogin() {
  if (client && !(await getAccessToken())) location.replace("login.html");
}

export function goToLogin() {
  if (client) location.replace("login.html");
}

// Depois do login, a pessoa volta para a página principal do app
const appUrl = () => new URL("index.html", location.href).href;

export async function signInWithGoogle() {
  const { error } = await client.auth.signInWithOAuth({
    provider: "google",
    options: { redirectTo: appUrl() },
  });
  if (error) throw error;
}

export async function signInWithEmail(email) {
  const { error } = await client.auth.signInWithOtp({
    email,
    options: { emailRedirectTo: appUrl() },
  });
  if (error) throw error;
}

export async function signOut() {
  await client?.auth.signOut();
  location.replace("login.html");
}

// "Baixar app": instala o site como aplicativo (PWA) no celular ou no PC.
//
// Android/Chrome: o navegador avisa que dá para instalar (evento beforeinstallprompt)
// e nós mostramos a janela oficial de instalação quando a pessoa clica.
// iPhone: a Apple não deixa nenhum site instalar por botão. Mostramos o passo a
// passo do Safari (Compartilhar -> Adicionar à Tela de Início).

let installPrompt = null;

window.addEventListener("beforeinstallprompt", (event) => {
  event.preventDefault(); // guarda para usar no clique, em vez do banner automático
  installPrompt = event;
});

const STEPS = {
  android: {
    title: "Instalar no Android",
    steps: [
      "Abra este site no <strong>Chrome</strong>.",
      "Toque no menu <strong>⋮</strong> (três pontinhos, no canto de cima).",
      "Toque em <strong>Instalar app</strong> (ou <strong>Adicionar à tela inicial</strong>).",
      "Pronto! O Diário de Bordo aparece junto com os seus apps.",
    ],
  },
  ios: {
    title: "Instalar no iPhone",
    steps: [
      "Abra este site no <strong>Safari</strong>.",
      "Toque em <strong>Compartilhar</strong> (o quadrado com a setinha ↑, na barra de baixo).",
      "Role e toque em <strong>Adicionar à Tela de Início</strong>.",
      "Toque em <strong>Adicionar</strong>. O ícone aparece na sua tela.",
    ],
    note: "No iPhone, a gravação por voz funciona melhor com o app aberto na tela.",
  },
};

const isInstalled = () =>
  window.matchMedia("(display-mode: standalone)").matches || navigator.standalone === true;

function dialog() {
  let el = document.getElementById("install-dialog");
  if (el) return el;
  // Criado por código para não repetir o mesmo HTML em todas as páginas
  el = document.createElement("dialog");
  el.id = "install-dialog";
  el.className = "dialog";
  el.innerHTML = `
    <h2 class="dialog__title"></h2>
    <ol class="install-steps"></ol>
    <p class="hint install-note" hidden></p>
    <div class="dialog__actions"><button class="btn btn--primary" type="button">Entendi</button></div>`;
  el.querySelector("button").addEventListener("click", () => el.close());
  document.body.append(el);
  return el;
}

function showSteps(platform) {
  const { title, steps, note } = STEPS[platform];
  const el = dialog();
  el.querySelector(".dialog__title").textContent = title;
  // Os textos dos passos são fixos (escritos aqui), por isso podem ter <strong>
  el.querySelector(".install-steps").innerHTML = steps.map((s) => `<li>${s}</li>`).join("");
  el.querySelector(".install-note").textContent = note ?? "";
  el.querySelector(".install-note").hidden = !note;
  el.showModal();
}

async function install(platform) {
  if (platform === "android" && installPrompt) {
    installPrompt.prompt(); // janela oficial do Chrome
    await installPrompt.userChoice;
    installPrompt = null;
    return;
  }
  showSteps(platform);
}

/** Liga os botões com data-install="android" ou data-install="ios". */
export function initInstallButtons() {
  const buttons = document.querySelectorAll("[data-install]");
  const group = document.querySelector(".install-group");
  if (isInstalled()) {
    group?.setAttribute("hidden", ""); // já está rodando como app
    return;
  }
  buttons.forEach((button) =>
    button.addEventListener("click", () => install(button.dataset.install)),
  );
}

// O service worker é um dos requisitos para o navegador oferecer a instalação
navigator.serviceWorker?.register("/sw.js").catch(() => {});

// Service worker do Diário de Bordo.
//
// Por enquanto ele só cuida dos cliques nas notificações do alerta de inatividade:
// o clique acontece fora da página, então é o service worker que recebe e repassa
// a resposta para a aba aberta. Na Etapa 2 ele também vai deixar o app instalável (PWA).

self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", (event) => event.waitUntil(self.clients.claim()));

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  // "yes" / "no" vêm dos botões; clicar no corpo da notificação não tem action
  const answer = event.action || "open";

  event.waitUntil(
    (async () => {
      const windows = await self.clients.matchAll({ type: "window", includeUncontrolled: true });
      const page = windows[0];
      if (!page) {
        await self.clients.openWindow("/");
        return;
      }
      page.postMessage({ type: "inactivity-answer", answer });
      // "Sim" resolve sem sair do que você está fazendo; o resto precisa da página
      if (answer !== "yes") await page.focus();
    })(),
  );
});

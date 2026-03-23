/**
 * Service Worker — CryptoTradeHub Push Notifications (PEND-07)
 *
 * Handles:
 *  - push events  → display native OS notification
 *  - notificationclick → open / focus the app
 *  - notificationclose → analytics (future)
 */

/* eslint-disable no-restricted-globals */

const APP_NAME = "CryptoTradeHub";
const DEFAULT_ICON = "/favicon.ico";
const DEFAULT_URL = "/";

// ── Push Event ───────────────────────────────────────────────────────────────

self.addEventListener("push", (event) => {
  if (!event.data) return;

  let payload;
  try {
    payload = event.data.json();
  } catch {
    payload = { title: APP_NAME, body: event.data.text() };
  }

  const title = payload.title || APP_NAME;
  const options = {
    body: payload.body || "",
    icon: payload.icon || DEFAULT_ICON,
    badge: payload.badge || DEFAULT_ICON,
    tag: payload.tag || "default",
    renotify: true,
    data: payload.data || { url: DEFAULT_URL },
  };

  event.waitUntil(self.registration.showNotification(title, options));
});

// ── Notification Click ───────────────────────────────────────────────────────

self.addEventListener("notificationclick", (event) => {
  event.notification.close();

  const targetUrl = (event.notification.data && event.notification.data.url) || DEFAULT_URL;

  event.waitUntil(
    self.clients.matchAll({ type: "window", includeUncontrolled: true }).then((clientList) => {
      // If the app is already open, focus it
      for (const client of clientList) {
        if (client.url.includes(self.location.origin) && "focus" in client) {
          client.navigate(targetUrl);
          return client.focus();
        }
      }
      // Otherwise open a new window
      return self.clients.openWindow(targetUrl);
    })
  );
});

// ── Activate: claim clients so SW controls pages immediately ─────────────────

self.addEventListener("activate", (event) => {
  event.waitUntil(self.clients.claim());
});

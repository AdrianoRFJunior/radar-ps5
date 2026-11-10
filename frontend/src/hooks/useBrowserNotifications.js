import { useCallback, useEffect, useState } from 'react';

/**
 * Hook opcional de Notificações do Navegador (Seção 11).
 * Nunca envia mensagens externas (e-mail/Telegram/WhatsApp).
 */
export function useBrowserNotifications(enabled = false) {
  const [permission, setPermission] = useState(
    typeof window !== 'undefined' && 'Notification' in window
      ? Notification.permission
      : 'denied'
  );

  const requestPermission = useCallback(async () => {
    if (typeof window === 'undefined' || !('Notification' in window)) {
      return 'denied';
    }
    const res = await Notification.requestPermission();
    setPermission(res);
    return res;
  }, []);

  useEffect(() => {
    if (enabled && permission === 'default') {
      requestPermission();
    }
  }, [enabled, permission, requestPermission]);

  const notifyBrowser = useCallback(
    (title, body) => {
      if (!enabled) return;
      if (typeof window !== 'undefined' && 'Notification' in window && Notification.permission === 'granted') {
        try {
          new Notification(`RADAR BF 2026: ${title}`, {
            body,
            tag: 'radar-bf-2026-alert',
          });
        } catch {
          // ignore browser notification restrictions
        }
      }
    },
    [enabled]
  );

  return { permission, requestPermission, notifyBrowser };
}

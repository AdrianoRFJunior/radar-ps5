/**
 * Serviço híbrido de comunicação HTTP do RADAR BF 2026:
 * 1. Conecta em tempo real ao backend FastAPI (/api local ou túnel público) quando disponível.
 * 2. Quando hospedado no GitHub Pages e o PC local estiver desligado, faz fallback automático
 *    transparente para os snapshots atualizados na nuvem pelo GitHub Actions (./data/*.json),
 *    mantendo o link 100% online 24/7 sem expiração.
 */
const isGitHubPages =
  typeof window !== 'undefined' && window.location.hostname.endsWith('github.io');

const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api';

const READ_ALERTS_STORAGE_KEY = 'radar_bf_read_alerts_v1';
const ARCHIVED_ALERTS_STORAGE_KEY = 'radar_bf_archived_alerts_v1';

function getStoredIdSet(key) {
  try {
    const raw = localStorage.getItem(key);
    return new Set(raw ? JSON.parse(raw) : []);
  } catch {
    return new Set();
  }
}

function saveStoredIdSet(key, setObj) {
  try {
    localStorage.setItem(key, JSON.stringify(Array.from(setObj)));
  } catch {
    // ignore storage errors
  }
}

async function fetchStaticJson(filename) {
  const res = await fetch(`./data/${filename}?_t=${Date.now()}`);
  if (!res.ok) {
    throw new Error(`Falha ao carregar snapshot estático ${filename}`);
  }
  return res.json();
}

function applyLocalAlertState(alertsList) {
  const readSet = getStoredIdSet(READ_ALERTS_STORAGE_KEY);
  const archSet = getStoredIdSet(ARCHIVED_ALERTS_STORAGE_KEY);
  return (alertsList || []).map((a) => ({
    ...a,
    is_read: Boolean(a.is_read || readSet.has(a.id)),
    is_archived: Boolean(a.is_archived || archSet.has(a.id)),
  }));
}

async function request(path, options = {}, staticFallbackFn = null) {
  // Quando hospedado no GitHub Pages, utiliza diretamente os snapshots estáticos gerados sem depender de túnel
  if (isGitHubPages && staticFallbackFn && (!options.method || options.method === 'GET')) {
    return await staticFallbackFn();
  }

  const controller = new AbortController();
  const timeoutMs = (options.method && options.method !== 'GET') ? 45000 : 5000;
  const timer = setTimeout(() => controller.abort(), timeoutMs);

  try {
    const res = await fetch(`${API_BASE}${path}`, {
      headers: {
        'Content-Type': 'application/json',
        ...(options.headers || {}),
      },
      signal: controller.signal,
      ...options,
    });
    clearTimeout(timer);
    if (!res.ok) {
      let errText = `Erro HTTP ${res.status}`;
      try {
        const errJson = await res.json();
        errText = errJson.detail || errJson.message || errText;
      } catch {
        // ignore
      }
      throw new Error(errText);
    }
    return await res.json();
  } catch (err) {
    clearTimeout(timer);
    if (staticFallbackFn) {
      return await staticFallbackFn();
    }
    throw err;
  }
}

export const radarApi = {
  getDashboard: () =>
    request('/dashboard', {}, async () => {
      const data = await fetchStaticJson('dashboard.json');
      try {
        const alertsData = await fetchStaticJson('alerts.json');
        const merged = applyLocalAlertState(alertsData.alerts);
        const unread = merged.filter((a) => !a.is_read && !a.is_archived).length;
        if (data?.indicators) {
          data.indicators.unread_alerts_count = unread;
        }
      } catch {
        // ignore
      }
      return data;
    }),

  getProducts: () => request('/products', {}, () => fetchStaticJson('products.json')),

  getComparator: (category = 'ALL', includeAlternatives = false, onlyOfficialWarranty = false) =>
    request(
      `/comparator?category=${category}&include_alternatives=${includeAlternatives}&only_official_warranty=${onlyOfficialWarranty}`,
      {},
      async () => {
        const data = await fetchStaticJson('comparator.json');
        let offers = data.offers || [];
        if (category === 'PS5' || category === 'DUALSENSE') {
          offers = offers.filter((o) => o.category === category);
        }
        if (!includeAlternatives) {
          offers = offers.filter((o) => o.is_priority);
        }
        if (onlyOfficialWarranty) {
          offers = offers.filter((o) => o.has_official_warranty && o.is_national);
        }
        return { ...data, offers };
      }
    ),

  getHistory: (category = 'PS5', period = '30d', paymentFilter = 'ALL', includeShipping = true, productId = null) => {
    const pidQuery = productId ? `&product_id=${productId}` : '';
    return request(
      `/history?category=${category}&period=${period}&payment_filter=${paymentFilter}&include_shipping=${includeShipping}${pidQuery}`,
      {},
      () => fetchStaticJson(category === 'DUALSENSE' ? 'history_DUALSENSE.json' : 'history_PS5.json')
    );
  },

  getIntelligence: () => request('/intelligence', {}, () => fetchStaticJson('intelligence.json')),

  getPredictions: () => request('/predictions', {}, () => fetchStaticJson('predictions.json')),

  getBestTimes: (category = '') =>
    request(`/best-times${category ? `?category=${category}` : ''}`, {}, () => fetchStaticJson('best-times.json')),

  getAlerts: (includeArchived = false, onlyUnread = false) =>
    request(
      `/alerts?include_archived=${includeArchived}&only_unread=${onlyUnread}&_t=${Date.now()}`,
      {},
      async () => {
        const data = await fetchStaticJson('alerts.json');
        const allMerged = applyLocalAlertState(data.alerts);
        const unreadCount = allMerged.filter((a) => !a.is_read && !a.is_archived).length;
        const totalActive = allMerged.filter((a) => !a.is_archived).length;
        let filtered = allMerged;
        if (!includeArchived) {
          filtered = filtered.filter((a) => !a.is_archived);
        }
        if (onlyUnread) {
          filtered = filtered.filter((a) => !a.is_read);
        }
        return {
          unread_count: unreadCount,
          total_active: totalActive,
          alerts: filtered,
        };
      }
    ),

  markAlertRead: (alertId, isRead = true) => {
    const readSet = getStoredIdSet(READ_ALERTS_STORAGE_KEY);
    if (isRead) readSet.add(alertId);
    else readSet.delete(alertId);
    saveStoredIdSet(READ_ALERTS_STORAGE_KEY, readSet);
    return request(
      `/alerts/${alertId}/read?is_read=${isRead}`,
      { method: 'POST' },
      async () => ({ status: 'OK', id: alertId, is_read: isRead })
    );
  },

  archiveAlert: (alertId, isArchived = true) => {
    const archSet = getStoredIdSet(ARCHIVED_ALERTS_STORAGE_KEY);
    const readSet = getStoredIdSet(READ_ALERTS_STORAGE_KEY);
    if (isArchived) {
      archSet.add(alertId);
      readSet.add(alertId);
    } else {
      archSet.delete(alertId);
    }
    saveStoredIdSet(ARCHIVED_ALERTS_STORAGE_KEY, archSet);
    saveStoredIdSet(READ_ALERTS_STORAGE_KEY, readSet);
    return request(
      `/alerts/${alertId}/archive?is_archived=${isArchived}`,
      { method: 'POST' },
      async () => ({ status: 'OK', id: alertId, is_archived: isArchived, is_read: true })
    );
  },

  markAllAlertsRead: () =>
    request('/alerts/mark-all-read', { method: 'POST' }, async () => {
      const data = await fetchStaticJson('alerts.json');
      const readSet = getStoredIdSet(READ_ALERTS_STORAGE_KEY);
      (data.alerts || []).forEach((a) => readSet.add(a.id));
      saveStoredIdSet(READ_ALERTS_STORAGE_KEY, readSet);
      return { status: 'OK', unread_count: 0 };
    }),

  getReports: () => request('/reports', {}, () => fetchStaticJson('reports.json')),

  getSettings: () => request('/settings', {}, () => fetchStaticJson('settings.json')),

  updateSettings: (payload) =>
    request('/settings', { method: 'PUT', body: JSON.stringify(payload) }, () => fetchStaticJson('settings.json')),

  triggerMonitoring: (storeSlug = null) =>
    request(
      `/monitoring/run${storeSlug ? `?store_slug=${storeSlug}` : ''}`,
      { method: 'POST' },
      async () => {
        try {
          const freshData = await fetchStaticJson('dashboard.json');
          return { status: 'STATIC_SNAPSHOT_REFRESHED', dashboard: freshData };
        } catch {
          return { status: 'STATIC_SNAPSHOT_REFRESHED' };
        }
      }
    ),

  getMonitoringLogs: () => request('/monitoring/logs', {}, () => fetchStaticJson('logs.json')),

  registerManualOffer: (payload) =>
    request('/offers/manual', { method: 'POST', body: JSON.stringify(payload) }),

  addCoupon: (payload) =>
    request('/coupons', { method: 'POST', body: JSON.stringify(payload) }),

  triggerBackup: () =>
    request('/backups', { method: 'POST' }, async () => ({ status: 'OK' })),

  getBackups: () => request('/backups', {}, () => fetchStaticJson('backups.json')),
};

export function formatBRL(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return '—';
  }
  return new Intl.NumberFormat('pt-BR', {
    style: 'currency',
    currency: 'BRL',
  }).format(Number(value));
}

export function formatDateTimeSP(isoString) {
  if (!isoString) return '—';
  try {
    const dt = new Date(isoString);
    return new Intl.DateTimeFormat('pt-BR', {
      timeZone: 'America/Sao_Paulo',
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    }).format(dt);
  } catch {
    return isoString;
  }
}

export function formatShortDateSP(isoString) {
  if (!isoString) return '';
  try {
    const dt = new Date(isoString);
    return new Intl.DateTimeFormat('pt-BR', {
      timeZone: 'America/Sao_Paulo',
      day: '2-digit',
      month: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    }).format(dt);
  } catch {
    return isoString;
  }
}

export function getScoreBadgeStyle(score) {
  const s = Number(score || 0);
  if (s >= 90) {
    return 'bg-emerald-500/20 text-emerald-300 border-emerald-500/50';
  }
  if (s >= 75) {
    return 'bg-green-500/20 text-green-300 border-green-500/40';
  }
  if (s >= 60) {
    return 'bg-lime-500/20 text-lime-300 border-lime-500/40';
  }
  if (s >= 40) {
    return 'bg-amber-500/20 text-amber-300 border-amber-500/40';
  }
  return 'bg-rose-500/20 text-rose-300 border-rose-500/40';
}

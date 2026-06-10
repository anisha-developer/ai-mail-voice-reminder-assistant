const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

export function getToken() {
  return sessionStorage.getItem("access_token");
}

export function setToken(token) {
  sessionStorage.setItem("access_token", token);
}

export function clearToken() {
  sessionStorage.removeItem("access_token");
}

export async function apiRequest(path, options = {}) {
  const headers = new Headers(options.headers || {});
  headers.set("Content-Type", "application/json");

  const token = getToken();
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers,
  });

  const contentType = response.headers.get("content-type") || "";
  const data = contentType.includes("application/json") ? await response.json() : null;

  if (!response.ok) {
    throw new Error(data?.detail || "Request failed");
  }

  return data;
}

async function fetchAllPages(pathBuilder, pageSize = 100) {
  const items = [];
  let page = 1;

  while (true) {
    const pageItems = await apiRequest(pathBuilder(page, pageSize));
    items.push(...pageItems);

    if (!Array.isArray(pageItems) || pageItems.length < pageSize) {
      break;
    }

    page += 1;
  }

  return items;
}

export const emailApi = {
  syncEmails: (params = {}) => {
    const search = new URLSearchParams();
    if (params.max_results) search.set("max_results", String(params.max_results));
    if (params.max_pages) search.set("max_pages", String(params.max_pages));
    const suffix = search.toString() ? `?${search.toString()}` : "";
    return apiRequest(`/emails/sync${suffix}`, { method: "POST" });
  },
  getEmails: (page = 1, limit = 20) => apiRequest(`/emails?page=${page}&limit=${limit}`),
  getAllEmails: () => fetchAllPages((page, limit) => `/emails?page=${page}&limit=${limit}`),
  getEmail: (id) => apiRequest(`/emails/${id}`),
  getSyncStatus: () => apiRequest("/emails/sync-status"),
  getAutoSyncStatus: () => apiRequest("/emails/auto-sync-status"),
};

export const gmailApi = {
  getStatus: () => apiRequest("/gmail/status"),
};

export const summaryApi = {
  generateAll: () => apiRequest("/summaries/generate-all", { method: "POST" }),
  getSummaries: (page = 1, limit = 20) => apiRequest(`/summaries?page=${page}&limit=${limit}`),
  getAllSummaries: () => fetchAllPages((page, limit) => `/summaries?page=${page}&limit=${limit}`),
  getTodaySummaries: () => apiRequest("/summaries/today"),
  getSummary: (id) => apiRequest(`/summaries/${id}`),
  getDetail: (id) => apiRequest(`/summaries/${id}/detail`),
};

export const mailCallApi = {
  getCountToday: () => apiRequest("/mail-calls/count-today"),
  prepare: () => apiRequest("/mail-calls/prepare", { method: "POST" }),
  markDelivered: (callLogId) => apiRequest(`/mail-calls/${callLogId}/mark-delivered`, { method: "POST" }),
  getHistory: () => apiRequest("/mail-calls/history"),
  getPendingSummaries: () => apiRequest("/mail-calls/pending-summaries"),
  startVoiceCall: (callLogId) => apiRequest(`/voice/mail-calls/${callLogId}/start`, { method: "POST" }),
  getInteractions: (callLogId) => apiRequest(`/voice/mail-calls/${callLogId}/interactions`),
};

export const callPreferencesApi = {
  get: () => apiRequest("/call-preferences"),
  update: (payload) => apiRequest("/call-preferences", { method: "PUT", body: JSON.stringify(payload) }),
};

export const reminderApi = {
  createReminder: (payload) => apiRequest("/reminders", { method: "POST", body: JSON.stringify(payload) }),
  listReminders: (includeCancelled = false) => apiRequest(`/reminders?include_cancelled=${includeCancelled ? "true" : "false"}`),
  getReminder: (id) => apiRequest(`/reminders/${id}`),
  updateReminder: (id, payload) => apiRequest(`/reminders/${id}`, { method: "PATCH", body: JSON.stringify(payload) }),
  cancelReminder: (id) => apiRequest(`/reminders/${id}`, { method: "DELETE" }),
  callAgain: (id) => apiRequest(`/reminders/${id}/call-again`, { method: "POST" }),
  snooze: (id, minutes) => apiRequest(`/reminders/${id}/snooze`, { method: "POST", body: JSON.stringify({ minutes }) }),
  markDone: (id) => apiRequest(`/reminders/${id}/mark-done`, { method: "POST" }),
};

export const recurringReminderApi = {
  list: () => apiRequest("/recurring-reminders"),
  create: (payload) => apiRequest("/recurring-reminders", { method: "POST", body: JSON.stringify(payload) }),
  get: (id) => apiRequest(`/recurring-reminders/${id}`),
  update: (id, payload) => apiRequest(`/recurring-reminders/${id}`, { method: "PUT", body: JSON.stringify(payload) }),
  pause: (id) => apiRequest(`/recurring-reminders/${id}/pause`, { method: "POST" }),
  resume: (id) => apiRequest(`/recurring-reminders/${id}/resume`, { method: "POST" }),
  cancel: (id) => apiRequest(`/recurring-reminders/${id}/cancel`, { method: "POST" }),
  delete: (id) => apiRequest(`/recurring-reminders/${id}`, { method: "DELETE" }),
  occurrences: (id) => apiRequest(`/recurring-reminders/${id}/occurrences`),
};

export const emailReplyApi = {
  list: () => apiRequest("/email-replies"),
  get: (id) => apiRequest(`/email-replies/${id}`),
};

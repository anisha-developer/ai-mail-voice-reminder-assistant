import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import PageShell from "../components/PageShell";
import { emailApi, priorityContactsApi } from "../lib/api";

function formatEmailDate(value) {
  return value ? new Date(value).toLocaleString() : "-";
}

function normalizeEmailAddress(value) {
  if (!value || typeof value !== "string") return "";
  const match = value.match(/[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}/i);
  return (match ? match[0] : value).trim().toLowerCase();
}

function getSenderEmail(sender) {
  return normalizeEmailAddress(sender);
}

function getSenderName(sender) {
  if (!sender || typeof sender !== "string") return "Unknown sender";
  const match = sender.match(/^(.*?)<[^>]+>/);
  const name = match?.[1]?.trim();
  if (name) return name;
  const email = getSenderEmail(sender);
  return email ? email.split("@")[0] : sender.trim();
}

function cleanEmailText(value) {
  if (!value || typeof value !== "string") {
    return "";
  }

  return value
    .replace(/<!doctype[\s\S]*?>/gi, " ")
    .replace(/<style[\s\S]*?<\/style>/gi, " ")
    .replace(/<script[\s\S]*?<\/script>/gi, " ")
    .replace(/<[^>]+>/g, " ")
    .replace(/&nbsp;/gi, " ")
    .replace(/&amp;/gi, "&")
    .replace(/&#39;/gi, "'")
    .replace(/&quot;/gi, '"')
    .replace(/\s+/g, " ")
    .trim();
}

function getDisplayMessage(email) {
  const primary = cleanEmailText(email?.snippet || "");
  if (primary) return primary;

  const fallback = cleanEmailText(email?.plain_body || "");
  return fallback;
}

function getVisibleAttachments(email) {
  const attachments = Array.isArray(email?.attachment_metadata) ? email.attachment_metadata : [];
  return attachments.filter((item) => {
    if (!item) return false;
    if (typeof item === "string") return item.trim().length > 0;
    if (typeof item === "object") {
      return Object.values(item).some((value) => String(value || "").trim().length > 0);
    }
    return false;
  });
}

function EmailDetailModal({ email, onClose }) {
  if (!email) return null;
  const displayMessage = getDisplayMessage(email);
  const attachments = getVisibleAttachments(email);
  return createPortal(
    <div
      className="fixed inset-0 z-[80] bg-slate-950/70 p-4 sm:p-6"
      onClick={onClose}
      role="presentation"
    >
      <div className="flex min-h-full items-center justify-center">
        <div
          className="w-full max-w-3xl overflow-hidden rounded-3xl border border-slate-200 bg-white text-slate-900 shadow-2xl shadow-slate-950/30"
          onClick={(event) => event.stopPropagation()}
          role="dialog"
          aria-modal="true"
          aria-label="Email details"
        >
          <div className="flex items-start justify-between gap-4 border-b border-slate-100 p-6">
            <div className="min-w-0">
              <p className="text-xs uppercase tracking-[0.3em] text-slate-500">Email Details</p>
              <h3 className="mt-2 break-words text-2xl font-semibold">{email.subject || "(No subject)"}</h3>
            </div>
            <button
              type="button"
              onClick={onClose}
              className="shrink-0 rounded-lg border border-slate-200 px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
            >
              Close
            </button>
          </div>
          <div className="max-h-[70vh] space-y-3 overflow-y-auto p-6 text-sm text-slate-600">
            <p>
              <span className="text-slate-400">From:</span> {email.sender || "-"}
            </p>
            {email.recipient ? (
              <p>
                <span className="text-slate-400">To:</span> {email.recipient}
              </p>
            ) : null}
            <p>
              <span className="text-slate-400">Received:</span>{" "}
              {formatEmailDate(email.received_at)}
            </p>
            <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
              <p className="text-xs uppercase tracking-[0.24em] text-slate-400">Message</p>
              <p className="mt-2 whitespace-pre-wrap text-sm leading-relaxed text-slate-700">
                {displayMessage || "No message preview available."}
              </p>
            </div>
            {attachments.length > 0 ? (
              <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                <p className="text-xs uppercase tracking-[0.24em] text-slate-400">Attachments</p>
                <ul className="mt-2 space-y-2 text-sm text-slate-700">
                  {attachments.map((attachment, index) => {
                    const label =
                      typeof attachment === "string"
                        ? attachment
                        : attachment?.filename || attachment?.name || attachment?.mime_type || `Attachment ${index + 1}`;
                    return (
                      <li key={`${label}-${index}`} className="break-words">
                        {label}
                      </li>
                    );
                  })}
                </ul>
              </div>
            ) : null}
          </div>
        </div>
      </div>
    </div>,
    document.body,
  );
}

export default function EmailInboxPage() {
  const [emails, setEmails] = useState([]);
  const [selectedEmail, setSelectedEmail] = useState(null);
  const [priorityMessage, setPriorityMessage] = useState("");
  const [syncStatus, setSyncStatus] = useState({
    gmail_connected: false,
    total_emails_stored: 0,
    last_sync_time: null,
  });
  const [autoSyncStatus, setAutoSyncStatus] = useState({
    auto_sync_enabled: false,
    interval_minutes: 5,
    last_auto_sync_at: null,
    last_auto_sync_status: null,
    last_auto_sync_error: null,
    last_auto_sync_inserted_count: 0,
    gmail_connected: false,
  });
  const [error, setError] = useState("");

  const loadData = async () => {
    const [status, autoStatus, list] = await Promise.all([
      emailApi.getSyncStatus(),
      emailApi.getAutoSyncStatus(),
      emailApi.getAllEmails(),
    ]);
    setSyncStatus(status);
    setAutoSyncStatus(autoStatus);
    setEmails(list);
  };

  useEffect(() => {
    loadData().catch((err) => setError(err.message));
    const refreshTimer = window.setInterval(() => {
      loadData().catch(() => {});
    }, 60000);
    return () => window.clearInterval(refreshTimer);
  }, []);

  const openEmail = async (emailId) => {
    try {
      const detail = await emailApi.getEmail(emailId);
      setSelectedEmail(detail);
    } catch (err) {
      setError(err.message);
    }
  };

  const addPriorityContact = async (email) => {
    const emailAddress = getSenderEmail(email?.sender);
    if (!emailAddress) {
      setPriorityMessage("Could not find a sender email address for this contact.");
      return;
    }
    try {
      await priorityContactsApi.create({
        display_name: getSenderName(email?.sender),
        email_address: emailAddress,
        relationship: "Other",
        priority_level: 1,
        notes: null,
      });
      setPriorityMessage("Added to priority contacts.");
    } catch (err) {
      const text = String(err?.message || "");
      if (text.toLowerCase().includes("already exists")) {
        setPriorityMessage("Priority contact already exists.");
        return;
      }
      setPriorityMessage(text || "Could not save priority contact.");
    }
  };

  return (
    <PageShell title="Email Inbox" description="Sync and browse stored Gmail inbox messages.">
      {priorityMessage ? (
        <div className="rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800">
          {priorityMessage}
        </div>
      ) : null}
      <div className="flex flex-col gap-4 rounded-2xl border border-slate-200 bg-white p-5 text-slate-700 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <p className="text-sm text-slate-400">Gmail connection</p>
          <p className="text-lg font-semibold text-slate-900">{syncStatus.gmail_connected ? "Connected" : "Disconnected"}</p>
          <p className="text-sm text-slate-400">Stored emails: {syncStatus.total_emails_stored}</p>
        </div>
      </div>

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <StatusCard label="Auto sync" value={autoSyncStatus.auto_sync_enabled ? "Enabled" : "Disabled"} />
        <StatusCard
          label="Sync interval"
          value={`${autoSyncStatus.interval_minutes} min`}
        />
        <StatusCard
          label="Last auto sync"
          value={autoSyncStatus.last_auto_sync_at ? new Date(autoSyncStatus.last_auto_sync_at).toLocaleString() : "Not run yet"}
        />
        <StatusCard label="Last inserted count" value={autoSyncStatus.last_auto_sync_inserted_count} />
      </div>

      <div className="rounded-2xl border border-slate-200 bg-white p-5 text-sm text-slate-600">
        <p>Auto sync status: {autoSyncStatus.last_auto_sync_status || "-"}</p>
        <p>Last auto sync error: {autoSyncStatus.last_auto_sync_error || "-"}</p>
      </div>

      {error ? <div className="rounded-xl border border-slate-200 bg-slate-50 p-3 text-slate-700">{error}</div> : null}

      <div className="space-y-3">
        {emails.length === 0 ? (
          <div className="rounded-2xl border border-slate-200 bg-white p-6 text-slate-400">No emails stored yet.</div>
        ) : (
          emails.map((email) => (
            <div key={email.id} className="rounded-2xl border border-slate-200 bg-white p-5">
              <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                <div className="min-w-0">
                  <h3 className="break-words text-lg font-semibold text-slate-900">{email.subject || "(No subject)"}</h3>
                  <p className="text-sm text-slate-600">{email.sender || "-"}</p>
                  <p className="mt-2 text-sm text-slate-400">{email.snippet || "-"}</p>
                  <p className="mt-2 text-xs text-slate-400">
                    {email.received_at ? new Date(email.received_at).toLocaleString() : "Unknown date"}
                    {email.has_attachments ? " • Attachments" : ""}
                  </p>
                </div>
                <div className="flex gap-2">
                  <button
                    type="button"
                    onClick={() => openEmail(email.id)}
                    className="rounded-xl border border-slate-200 px-4 py-2 text-sm font-semibold text-slate-700"
                  >
                    View Details
                  </button>
                  <button
                    type="button"
                    onClick={() => addPriorityContact(email)}
                    className="rounded-xl border border-slate-200 bg-slate-50 px-4 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-100"
                  >
                    + Priority
                  </button>
                </div>
              </div>
            </div>
          ))
        )}
      </div>

      <EmailDetailModal email={selectedEmail} onClose={() => setSelectedEmail(null)} />
    </PageShell>
  );
}

function StatusCard({ label, value }) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-5">
      <p className="text-sm text-slate-400">{label}</p>
      <h3 className="mt-2 text-lg font-semibold text-slate-900">{value}</h3>
    </div>
  );
}

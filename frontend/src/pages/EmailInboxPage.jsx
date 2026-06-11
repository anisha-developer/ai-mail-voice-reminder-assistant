import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import PageShell from "../components/PageShell";
import { emailApi } from "../lib/api";

function EmailDetailModal({ email, onClose }) {
  if (!email) return null;
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
            <p>
              <span className="text-slate-400">To:</span> {email.recipient || "-"}
            </p>
            <p>
              <span className="text-slate-400">Received:</span>{" "}
              {email.received_at ? new Date(email.received_at).toLocaleString() : "-"}
            </p>
            <p>
              <span className="text-slate-400">Snippet:</span> {email.snippet || "-"}
            </p>
            <p>
              <span className="text-slate-400">Plain body:</span>
            </p>
            <pre className="whitespace-pre-wrap rounded-2xl border border-slate-200 bg-slate-50 p-4 text-sm leading-relaxed text-slate-700">
              {email.plain_body || "-"}
            </pre>
            <p>
              <span className="text-slate-400">HTML body:</span>
            </p>
            <pre className="whitespace-pre-wrap rounded-2xl border border-slate-200 bg-slate-50 p-4 text-sm leading-relaxed text-slate-700">
              {email.html_body || "-"}
            </pre>
            <p>
              <span className="text-slate-400">Attachments:</span>
            </p>
            <pre className="whitespace-pre-wrap rounded-2xl border border-slate-200 bg-slate-50 p-4 text-sm leading-relaxed text-slate-700">
              {JSON.stringify(email.attachment_metadata || [], null, 2)}
            </pre>
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

  return (
    <PageShell title="Email Inbox" description="Sync and browse stored Gmail inbox messages.">
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

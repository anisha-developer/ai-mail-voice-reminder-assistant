import { useEffect, useState } from "react";
import PageShell from "../components/PageShell";
import { emailApi, summaryApi } from "../lib/api";

function EmailDetailModal({ email, onClose }) {
  if (!email) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4">
      <div className="max-h-[90vh] w-full max-w-3xl overflow-y-auto rounded-3xl border border-slate-200 bg-white p-6 text-slate-900">
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="text-xs uppercase tracking-[0.3em] text-slate-500">Email Details</p>
            <h3 className="mt-2 text-2xl font-semibold">{email.subject || "(No subject)"}</h3>
          </div>
          <button type="button" onClick={onClose} className="rounded-lg border border-slate-200 px-3 py-2 text-sm">
            Close
          </button>
        </div>
        <div className="mt-6 space-y-3 text-sm text-slate-600">
          <p><span className="text-slate-400">From:</span> {email.sender || "-"}</p>
          <p><span className="text-slate-400">To:</span> {email.recipient || "-"}</p>
          <p><span className="text-slate-400">Received:</span> {email.received_at ? new Date(email.received_at).toLocaleString() : "-"}</p>
          <p><span className="text-slate-400">Snippet:</span> {email.snippet || "-"}</p>
          <p><span className="text-slate-400">Plain body:</span></p>
          <pre className="whitespace-pre-wrap rounded-2xl bg-white p-4 text-sm">{email.plain_body || "-"}</pre>
          <p><span className="text-slate-400">HTML body:</span></p>
          <pre className="whitespace-pre-wrap rounded-2xl bg-white p-4 text-sm">{email.html_body || "-"}</pre>
          <p><span className="text-slate-400">Attachments:</span></p>
          <pre className="whitespace-pre-wrap rounded-2xl bg-white p-4 text-sm">
            {JSON.stringify(email.attachment_metadata || [], null, 2)}
          </pre>
        </div>
      </div>
    </div>
  );
}

function SummaryModal({ summary, onClose }) {
  if (!summary) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4">
      <div className="max-h-[90vh] w-full max-w-3xl overflow-y-auto rounded-3xl border border-slate-200 bg-white p-6 text-slate-900">
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="text-xs uppercase tracking-[0.3em] text-slate-500">Email Summary</p>
            <h3 className="mt-2 text-2xl font-semibold">{summary.subject || "(No subject)"}</h3>
          </div>
          <button type="button" onClick={onClose} className="rounded-lg border border-slate-200 px-3 py-2 text-sm">
            Close
          </button>
        </div>
        <div className="mt-6 space-y-3 text-sm text-slate-600">
          <p><span className="text-slate-400">From:</span> {summary.sender || "-"}</p>
          <p><span className="text-slate-400">Short summary:</span> {summary.short_summary || "-"}</p>
          <p><span className="text-slate-400">Action required:</span> {summary.action_required_text || "-"}</p>
          <p><span className="text-slate-400">Attachment note:</span> {summary.attachment_note || "-"}</p>
          <pre className="whitespace-pre-wrap rounded-2xl bg-white p-4 text-sm">{summary.detailed_summary || "-"}</pre>
        </div>
      </div>
    </div>
  );
}

export default function EmailInboxPage() {
  const [emails, setEmails] = useState([]);
  const [selectedEmail, setSelectedEmail] = useState(null);
  const [selectedSummary, setSelectedSummary] = useState(null);
  const [syncStatus, setSyncStatus] = useState({ gmail_connected: false, total_emails_stored: 0, last_sync_time: null });
  const [autoSyncStatus, setAutoSyncStatus] = useState({
    auto_sync_enabled: false,
    interval_minutes: 5,
    last_auto_sync_at: null,
    last_auto_sync_status: null,
    last_auto_sync_error: null,
    last_auto_sync_inserted_count: 0,
    auto_summarize_after_sync: false,
    last_auto_summary_at: null,
    last_auto_summary_status: null,
    last_auto_summary_error: null,
    last_auto_summary_success_count: 0,
    last_auto_summary_failed_count: 0,
    gmail_connected: false,
    unsummarized_email_count: 0,
  });
  const [syncResult, setSyncResult] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

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

  const handleSync = async () => {
    setLoading(true);
    setError("");
    setSyncResult("");
    try {
      const result = await emailApi.syncEmails({ max_results: 50, max_pages: 3 });
      const latestGmail = result.latest_gmail_received_at ? new Date(result.latest_gmail_received_at).toLocaleString() : "-";
      const latestStored = result.latest_stored_received_at ? new Date(result.latest_stored_received_at).toLocaleString() : "-";
      if (result.synced_count === 0) {
        setSyncResult(
          `Gmail API returned only existing messages. Synced ${result.synced_count}, skipped ${result.skipped_duplicates}, processed ${result.total_processed}. ` +
            `Latest Gmail received: ${latestGmail}. Latest stored received: ${latestStored}.`,
        );
      } else {
        setSyncResult(
          `Synced ${result.synced_count}, skipped ${result.skipped_duplicates}, processed ${result.total_processed}. ` +
            `Latest Gmail received: ${latestGmail}. Latest stored received: ${latestStored}.`,
        );
      }
      await loadData();
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const openEmail = async (emailId) => {
    try {
      const detail = await emailApi.getEmail(emailId);
      setSelectedEmail(detail);
    } catch (err) {
      setError(err.message);
    }
  };

  const openSummary = async (emailId) => {
    try {
      const summaries = await summaryApi.getAllSummaries();
      const match = summaries.find((summary) => summary.email_message_id === emailId);
      if (!match) {
        setError("Summary not available yet.");
        return;
      }
      const detail = await summaryApi.getSummary(match.id);
      setSelectedSummary(detail);
    } catch (err) {
      setError(err.message);
    }
  };

  return (
    <PageShell
      title="Email Inbox"
      description="Sync and browse stored Gmail inbox messages."
    >
      <div className="flex flex-col gap-4 rounded-2xl border border-slate-200 bg-white p-5 text-slate-700 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <p className="text-sm text-slate-400">Gmail connection</p>
          <p className="text-lg font-semibold text-slate-900">{syncStatus.gmail_connected ? "Connected" : "Disconnected"}</p>
          <p className="text-sm text-slate-400">Stored emails: {syncStatus.total_emails_stored}</p>
        </div>
        <button
          type="button"
          onClick={handleSync}
          disabled={loading || !syncStatus.gmail_connected}
          className="rounded-xl bg-slate-900 px-4 py-3 font-semibold text-white disabled:opacity-60"
        >
          {loading ? "Syncing..." : "Sync Emails"}
        </button>
      </div>

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <StatusCard label="Auto sync" value={autoSyncStatus.auto_sync_enabled ? "Enabled" : "Disabled"} />
        <StatusCard label="Auto summarize" value={autoSyncStatus.auto_summarize_after_sync ? "Enabled" : "Disabled"} />
        <StatusCard label="Sync interval" value={`${autoSyncStatus.interval_minutes} min`} />
        <StatusCard
          label="Last auto sync"
          value={autoSyncStatus.last_auto_sync_at ? new Date(autoSyncStatus.last_auto_sync_at).toLocaleString() : "Not run yet"}
        />
        <StatusCard label="Last inserted count" value={autoSyncStatus.last_auto_sync_inserted_count} />
        <StatusCard
          label="Last auto summary"
          value={autoSyncStatus.last_auto_summary_at ? new Date(autoSyncStatus.last_auto_summary_at).toLocaleString() : "Not run yet"}
        />
      </div>

      <div className="rounded-2xl border border-slate-200 bg-white p-5 text-sm text-slate-600">
        <p>Auto sync status: {autoSyncStatus.last_auto_sync_status || "-"}</p>
        <p>Auto summary status: {autoSyncStatus.last_auto_summary_status || "-"}</p>
        <p>Auto summary success count: {autoSyncStatus.last_auto_summary_success_count}</p>
        <p>Auto summary failed count: {autoSyncStatus.last_auto_summary_failed_count}</p>
        <p>Unsummarized emails: {autoSyncStatus.unsummarized_email_count}</p>
        <p>Auto summarize after sync: {autoSyncStatus.auto_summarize_after_sync ? "Enabled" : "Disabled"}</p>
        <p>Last auto sync error: {autoSyncStatus.last_auto_sync_error || "-"}</p>
        <p>Last auto summary error: {autoSyncStatus.last_auto_summary_error || "-"}</p>
      </div>

      {syncResult ? <div className="rounded-xl border border-slate-200 bg-slate-50 p-3 text-slate-700">{syncResult}</div> : null}
      {error ? <div className="rounded-xl border border-slate-200 bg-slate-50 p-3 text-slate-700">{error}</div> : null}

      <div className="space-y-3">
        {emails.length === 0 ? (
          <div className="rounded-2xl border border-slate-200 bg-white p-6 text-slate-400">No emails stored yet.</div>
        ) : (
          emails.map((email) => (
            <div key={email.id} className="rounded-2xl border border-slate-200 bg-white p-5">
              <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                <div>
                  <h3 className="text-lg font-semibold text-slate-900">{email.subject || "(No subject)"}</h3>
                  <p className="text-sm text-slate-600">{email.sender || "-"}</p>
                  <p className="mt-2 text-sm text-slate-400">{email.snippet || "-"}</p>
                  <p className="mt-2 text-xs text-slate-400">
                    {email.received_at ? new Date(email.received_at).toLocaleString() : "Unknown date"}
                    {email.has_attachments ? " • Attachments" : ""}
                  </p>
                  <p className="mt-1 text-xs text-slate-400">{email.is_summarized ? "Summary available" : "Not summarized yet"}</p>
                </div>
                <div className="flex gap-2">
                  <button
                    type="button"
                    onClick={() => openEmail(email.id)}
                    className="rounded-xl border border-slate-200 px-4 py-2 text-sm font-semibold text-slate-700"
                  >
                    View Details
                  </button>
                  {email.is_summarized ? (
                    <button
                      type="button"
                      onClick={() => openSummary(email.id)}
                      className="rounded-xl border border-slate-300 px-4 py-2 text-sm font-semibold text-slate-600"
                    >
                      View Summary
                    </button>
                  ) : null}
                </div>
              </div>
            </div>
          ))
        )}
      </div>

      <EmailDetailModal email={selectedEmail} onClose={() => setSelectedEmail(null)} />
      <SummaryModal summary={selectedSummary} onClose={() => setSelectedSummary(null)} />
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


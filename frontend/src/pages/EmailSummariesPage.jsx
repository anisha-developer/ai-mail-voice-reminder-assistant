import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import PageShell from "../components/PageShell";
import { summaryApi } from "../lib/api";

function SummaryDetailModal({ summary, onClose }) {
  if (!summary) return null;
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
          aria-label="Detailed summary"
        >
          <div className="flex items-start justify-between gap-4 border-b border-slate-100 p-6">
            <div className="min-w-0">
              <p className="text-xs uppercase tracking-[0.3em] text-slate-500">Detailed Summary</p>
              <h3 className="mt-2 break-words text-2xl font-semibold">{summary.subject || "(No subject)"}</h3>
            </div>
            <button type="button" onClick={onClose} className="shrink-0 rounded-lg border border-slate-200 px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50">
              Close
            </button>
          </div>
          <div className="max-h-[70vh] space-y-3 overflow-y-auto p-6 text-sm text-slate-600">
            <p><span className="text-slate-400">From:</span> {summary.sender || "-"}</p>
            <p><span className="text-slate-400">Short summary:</span> {summary.short_summary || "-"}</p>
            <p><span className="text-slate-400">Action required:</span> {summary.action_required_text || "-"}</p>
            <p><span className="text-slate-400">Attachment note:</span> {summary.attachment_note || "-"}</p>
            <p><span className="text-slate-400">Detailed summary:</span></p>
            <pre className="whitespace-pre-wrap rounded-2xl border border-slate-200 bg-slate-50 p-4 text-sm leading-relaxed text-slate-700">
              {summary.detailed_summary || "Detailed summary is not available yet."}
            </pre>
          </div>
        </div>
      </div>
    </div>,
    document.body,
  );
}

export default function EmailSummariesPage() {
  const [summaries, setSummaries] = useState([]);
  const [selectedSummary, setSelectedSummary] = useState(null);
  const [error, setError] = useState("");

  const loadSummaries = async () => {
    const data = await summaryApi.getAllSummaries();
    setSummaries(data);
  };

  useEffect(() => {
    loadSummaries().catch((err) => setError(err.message));
    const refreshTimer = window.setInterval(() => {
      loadSummaries().catch(() => {});
    }, 60000);
    return () => window.clearInterval(refreshTimer);
  }, []);

  const handleOpenDetail = async (summary) => {
    try {
      const [detail, detailText] = await Promise.all([summaryApi.getSummary(summary.id), summaryApi.getDetail(summary.id)]);
      setSelectedSummary({
        ...summary,
        ...detail,
        detailed_summary: detailText?.detailed_summary ?? detail.detailed_summary ?? summary.detailed_summary ?? null,
      });
    } catch (err) {
      setError(err.message);
    }
  };

  return (
    <PageShell
      title="Email Summaries"
      description="Summaries are updated automatically for stored emails."
    >
      <div className="flex flex-col gap-4 rounded-2xl border border-slate-200 bg-white p-5 text-slate-700 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <p className="text-sm text-slate-400">Automatic summaries</p>
          <p className="text-lg font-semibold text-slate-900">Stored emails are summarized automatically after sync</p>
        </div>
      </div>

      {error ? <div className="rounded-xl border border-slate-200 bg-slate-50 p-3 text-slate-700">{error}</div> : null}

      <div className="space-y-3">
        {summaries.length === 0 ? (
          <div className="rounded-2xl border border-slate-200 bg-white p-6 text-slate-400">No summaries yet.</div>
        ) : (
          summaries.map((summary) => (
            <div key={summary.id} className="rounded-2xl border border-slate-200 bg-white p-5">
              <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                <div className="space-y-2">
                  <h3 className="text-lg font-semibold text-slate-900">{summary.subject || "(No subject)"}</h3>
                  <p className="text-sm text-slate-600">{summary.sender || "-"}</p>
                  <p className="text-sm text-slate-700">{summary.short_summary || "-"}</p>
                  <p className="text-sm text-slate-400">Action: {summary.action_required_text || "-"}</p>
                  <p className="text-sm text-slate-400">Attachments: {summary.attachment_note || "-"}</p>
                  <p className="text-sm text-slate-400">
                    Delivery: {summary.is_delivered_in_mail_call ? "Delivered in mail summary call" : "Pending delivery"}
                  </p>
                  <p className="text-xs text-slate-400">{new Date(summary.created_at).toLocaleString()}</p>
                </div>
                <button
                  type="button"
                  onClick={() => handleOpenDetail(summary)}
                  className="rounded-xl border border-slate-200 px-4 py-2 text-sm font-semibold text-slate-700"
                >
                  View detailed summary
                </button>
              </div>
            </div>
          ))
        )}
      </div>

      <SummaryDetailModal summary={selectedSummary} onClose={() => setSelectedSummary(null)} />
    </PageShell>
  );
}


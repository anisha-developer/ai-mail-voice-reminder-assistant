import { useEffect, useState } from "react";
import PageShell from "../components/PageShell";
import { summaryApi } from "../lib/api";

function SummaryDetailModal({ summary, onClose }) {
  if (!summary) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4">
      <div className="max-h-[90vh] w-full max-w-3xl overflow-y-auto rounded-3xl border border-white/10 bg-slate-950 p-6 text-white">
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="text-xs uppercase tracking-[0.3em] text-sky-300">Detailed Summary</p>
            <h3 className="mt-2 text-2xl font-semibold">{summary.subject || "(No subject)"}</h3>
          </div>
          <button type="button" onClick={onClose} className="rounded-lg border border-white/10 px-3 py-2 text-sm">
            Close
          </button>
        </div>
        <div className="mt-6 space-y-3 text-sm text-slate-300">
          <p><span className="text-slate-500">From:</span> {summary.sender || "-"}</p>
          <p><span className="text-slate-500">Short summary:</span> {summary.short_summary || "-"}</p>
          <p><span className="text-slate-500">Action required:</span> {summary.action_required_text || "-"}</p>
          <p><span className="text-slate-500">Attachment note:</span> {summary.attachment_note || "-"}</p>
          <p><span className="text-slate-500">Detailed summary:</span></p>
          <pre className="whitespace-pre-wrap rounded-2xl bg-white/5 p-4 text-sm">{summary.detailed_summary || "-"}</pre>
        </div>
      </div>
    </div>
  );
}

export default function EmailSummariesPage() {
  const [summaries, setSummaries] = useState([]);
  const [selectedSummary, setSelectedSummary] = useState(null);
  const [result, setResult] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

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

  const handleGenerate = async () => {
    setLoading(true);
    setResult("");
    setError("");
    try {
      const data = await summaryApi.generateAll();
      setResult(
        `Processed ${data.processed_count}, success ${data.success_count}, failed ${data.failed_count}, already summarized ${data.already_summarized_count}`,
      );
      await loadSummaries();
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleOpenDetail = async (summaryId) => {
    try {
      const data = await summaryApi.getSummary(summaryId);
      setSelectedSummary(data);
    } catch (err) {
      setError(err.message);
    }
  };

  return (
    <PageShell
      title="Email Summaries"
      description="Generate short and detailed summaries for every stored email."
    >
      <div className="flex flex-col gap-4 rounded-2xl border border-white/10 bg-white/5 p-5 text-slate-200 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <p className="text-sm text-slate-400">Summary generation</p>
          <p className="text-lg font-semibold text-white">All stored emails are eligible for summarization</p>
        </div>
        <button
          type="button"
          onClick={handleGenerate}
          disabled={loading}
          className="rounded-xl bg-sky-400 px-4 py-3 font-semibold text-slate-950 disabled:opacity-60"
        >
          {loading ? "Generating..." : "Generate Summaries"}
        </button>
      </div>

      {result ? <div className="rounded-xl border border-emerald-500/30 bg-emerald-500/10 p-3 text-emerald-200">{result}</div> : null}
      {error ? <div className="rounded-xl border border-red-500/30 bg-red-500/10 p-3 text-red-200">{error}</div> : null}

      <div className="space-y-3">
        {summaries.length === 0 ? (
          <div className="rounded-2xl border border-white/10 bg-white/5 p-6 text-slate-400">No summaries yet.</div>
        ) : (
          summaries.map((summary) => (
            <div key={summary.id} className="rounded-2xl border border-white/10 bg-white/5 p-5">
              <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                <div className="space-y-2">
                  <h3 className="text-lg font-semibold text-white">{summary.subject || "(No subject)"}</h3>
                  <p className="text-sm text-slate-300">{summary.sender || "-"}</p>
                  <p className="text-sm text-slate-200">{summary.short_summary || "-"}</p>
                  <p className="text-sm text-slate-400">Action: {summary.action_required_text || "-"}</p>
                  <p className="text-sm text-slate-400">Attachments: {summary.attachment_note || "-"}</p>
                  <p className="text-sm text-slate-400">
                    Delivery: {summary.is_delivered_in_mail_call ? "Delivered in mail summary call" : "Pending delivery"}
                  </p>
                  <p className="text-xs text-slate-500">{new Date(summary.created_at).toLocaleString()}</p>
                </div>
                <button
                  type="button"
                  onClick={() => handleOpenDetail(summary.id)}
                  className="rounded-xl border border-white/10 px-4 py-2 text-sm font-semibold text-slate-200"
                >
                  View Detailed Summary
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

import { useEffect, useMemo, useState } from "react";
import PageShell from "../components/PageShell";
import { replyStatusApi } from "../lib/api";

function formatIst(value) {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "-";
  return new Intl.DateTimeFormat("en-IN", {
    timeZone: "Asia/Kolkata",
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    hour12: true,
  })
    .format(date)
    .replace(/\bam\b/g, "AM")
    .replace(/\bpm\b/g, "PM");
}

function statusClasses(status) {
  switch ((status || "").toLowerCase()) {
    case "sent":
      return "border-emerald-200 bg-emerald-50 text-emerald-700";
    case "failed":
      return "border-rose-200 bg-rose-50 text-rose-700";
    case "pending":
      return "border-amber-200 bg-amber-50 text-amber-700";
    default:
      return "border-slate-200 bg-slate-50 text-slate-600";
  }
}

function previewText(value, length = 120) {
  const text = (value || "").trim();
  if (!text) return "-";
  return text.length > length ? `${text.slice(0, length).trim()}...` : text;
}

export default function ReplyStatusPage() {
  const [logs, setLogs] = useState([]);
  const [statusFilter, setStatusFilter] = useState("all");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;

    async function loadLogs() {
      setLoading(true);
      setError("");
      try {
        const response = await replyStatusApi.list();
        if (!cancelled) {
          const items = Array.isArray(response?.value) ? response.value : [];
          setLogs(items);
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Failed to load reply status");
          setLogs([]);
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    loadLogs();

    return () => {
      cancelled = true;
    };
  }, []);

  const filteredLogs = useMemo(() => {
    if (statusFilter === "all") return logs;
    return logs.filter((log) => (log.status || "").toLowerCase() === statusFilter);
  }, [logs, statusFilter]);

  const totals = useMemo(() => {
    const total = logs.length;
    const sent = logs.filter((log) => (log.status || "").toLowerCase() === "sent").length;
    const failed = logs.filter((log) => (log.status || "").toLowerCase() === "failed").length;
    const pending = logs.filter((log) => (log.status || "").toLowerCase() === "pending").length;
    return { total, sent, failed, pending };
  }, [logs]);

  return (
    <PageShell title="Reply Status" description="View reply attempts from voice calls and future reply workflows in one place.">
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
          <p className="text-sm text-slate-500">Total replies</p>
          <p className="mt-3 text-3xl font-semibold text-slate-900">{totals.total}</p>
        </div>
        <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
          <p className="text-sm text-slate-500">Sent</p>
          <p className="mt-3 text-3xl font-semibold text-slate-900">{totals.sent}</p>
        </div>
        <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
          <p className="text-sm text-slate-500">Failed</p>
          <p className="mt-3 text-3xl font-semibold text-slate-900">{totals.failed}</p>
        </div>
        <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
          <p className="text-sm text-slate-500">Pending</p>
          <p className="mt-3 text-3xl font-semibold text-slate-900">{totals.pending}</p>
        </div>
      </div>

      <section className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h3 className="text-xl font-semibold text-slate-900">Reply records</h3>
            <p className="mt-1 text-sm text-slate-600">Newest replies appear first.</p>
          </div>
          <label className="inline-flex items-center gap-3 text-sm font-medium text-slate-700">
            Status
            <select
              value={statusFilter}
              onChange={(event) => setStatusFilter(event.target.value)}
              className="rounded-xl border border-slate-300 bg-white px-4 py-2 text-sm text-slate-900 outline-none focus:border-slate-900"
            >
              <option value="all">All</option>
              <option value="sent">Sent</option>
              <option value="failed">Failed</option>
              <option value="pending">Pending</option>
            </select>
          </label>
        </div>

        {error ? <p className="mt-4 rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">{error}</p> : null}
        {loading ? <p className="mt-4 text-sm text-slate-500">Loading reply records...</p> : null}

        {!loading && !error && filteredLogs.length === 0 ? (
          <div className="mt-6 rounded-2xl border border-dashed border-slate-200 bg-slate-50 p-8 text-center">
            <p className="text-lg font-medium text-slate-900">No reply records yet.</p>
            <p className="mt-2 text-sm text-slate-600">Reply attempts from the voice assistant will appear here.</p>
          </div>
        ) : null}

        {!loading && filteredLogs.length > 0 ? (
          <div className="mt-6 overflow-hidden rounded-2xl border border-slate-200">
            <div className="grid grid-cols-6 gap-3 border-b border-slate-200 bg-slate-50 px-4 py-3 text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">
              <span>Status</span>
              <span>Original sender</span>
              <span>Original subject</span>
              <span>Reply text</span>
              <span>Source</span>
              <span>Time</span>
            </div>
            <div className="divide-y divide-slate-200">
              {filteredLogs.map((log) => (
                <div key={log.id} className="grid grid-cols-6 gap-3 px-4 py-4 text-sm text-slate-700">
                  <div>
                    <span className={`inline-flex rounded-full border px-3 py-1 text-xs font-semibold uppercase tracking-[0.16em] ${statusClasses(log.status)}`}>
                      {log.status || "unknown"}
                    </span>
                    {log.failure_reason ? <p className="mt-2 text-xs text-rose-600">{log.failure_reason}</p> : null}
                  </div>
                  <div className="min-w-0 break-words font-medium text-slate-900">{log.original_sender || "-"}</div>
                  <div className="min-w-0 break-words">{log.original_subject || "-"}</div>
                  <div className="min-w-0 break-words text-slate-600">{previewText(log.reply_text, 110)}</div>
                  <div className="capitalize">{(log.source || "-").replace(/_/g, " ")}</div>
                  <div className="text-slate-600">{formatIst(log.sent_at || log.created_at)}</div>
                </div>
              ))}
            </div>
          </div>
        ) : null}
      </section>
    </PageShell>
  );
}

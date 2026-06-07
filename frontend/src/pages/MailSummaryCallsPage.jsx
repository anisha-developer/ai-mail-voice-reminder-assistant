import { useEffect, useState } from "react";
import PageShell from "../components/PageShell";
import { mailCallApi } from "../lib/api";

function selectPreparedCall(history, preferredCallLogId = null) {
  if (!Array.isArray(history) || history.length === 0) {
    return null;
  }

  if (preferredCallLogId) {
    const matchingPreparedCall = history.find(
      (item) => item.id === preferredCallLogId && item.call_status === "prepared",
    );
    if (matchingPreparedCall) {
      return matchingPreparedCall;
    }
  }

  return history.find((item) => item.call_status === "prepared") || null;
}

export default function MailSummaryCallsPage() {
  const [countToday, setCountToday] = useState({
    max_calls_per_day: 3,
    used_calls_today: 0,
    remaining_calls_today: 3,
    date: null,
    total_summaries_in_database: 0,
    today_summaries_count: 0,
    pending_today_summaries_count: 0,
  });
  const [pendingData, setPendingData] = useState({
    pending_count: 0,
    pending_today_count: 0,
    today_summaries_count: 0,
    total_summaries_in_database: 0,
    summaries: [],
  });
  const [history, setHistory] = useState([]);
  const [preparedCall, setPreparedCall] = useState(null);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [delivering, setDelivering] = useState(false);
  const [startingCall, setStartingCall] = useState(false);
  const [interactionsByCallId, setInteractionsByCallId] = useState({});

  const loadData = async (preferredCallLogId = null) => {
    const [countResponse, pendingResponse, historyResponse] = await Promise.all([
      mailCallApi.getCountToday(),
      mailCallApi.getPendingSummaries(),
      mailCallApi.getHistory(),
    ]);
    setCountToday(countResponse);
    setPendingData(pendingResponse);
    setHistory(historyResponse);
    setPreparedCall(selectPreparedCall(historyResponse, preferredCallLogId));
    const interactionEntries = await Promise.all(
      historyResponse.map(async (item) => [item.id, await mailCallApi.getInteractions(item.id)]),
    );
    setInteractionsByCallId(Object.fromEntries(interactionEntries));
  };

  useEffect(() => {
    loadData().catch((err) => setError(err.message));
  }, []);

  const handlePrepare = async () => {
    setLoading(true);
    setMessage("");
    setError("");
    try {
      const result = await mailCallApi.prepare();
      setMessage(`Prepared a mail summary call for ${result.summary_count} summaries.`);
      await loadData(result.call_log_id);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleMarkDelivered = async () => {
    if (!preparedCall?.call_log_id && !preparedCall?.id) return;
    setDelivering(true);
    setMessage("");
    setError("");
    try {
      const callLogId = preparedCall.call_log_id || preparedCall.id;
      const result = await mailCallApi.markDelivered(callLogId);
      setMessage(result.message);
      setPreparedCall(null);
      await loadData();
    } catch (err) {
      setError(err.message);
    } finally {
      setDelivering(false);
    }
  };

  const handleStartVoiceCall = async () => {
    if (!preparedCall?.id) return;
    setStartingCall(true);
    setMessage("");
    setError("");
    try {
      const result = await mailCallApi.startVoiceCall(preparedCall.id);
      setMessage(`Voice call ${result.call_status}. Provider call ID: ${result.provider_call_id}`);
      await loadData(result.call_log_id);
    } catch (err) {
      setError(err.message);
    } finally {
      setStartingCall(false);
    }
  };

  return (
    <PageShell
      title="Mail Summary Calls"
      description="Voice calls summarize only today's received emails, while the daily 3-call limit still applies only to mail summary calls."
    >
      <div className="grid gap-4 md:grid-cols-4">
        <StatCard label="Today's summaries" value={countToday.today_summaries_count} />
        <StatCard label="Pending today summaries" value={countToday.pending_today_summaries_count} />
        <StatCard label="Used mail summary calls today" value={countToday.used_calls_today} />
        <StatCard label="Remaining calls today" value={countToday.remaining_calls_today} />
      </div>

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <StatCard label="Total summaries in database" value={countToday.total_summaries_in_database} />
        <StatCard label="Max mail summary calls per day" value={countToday.max_calls_per_day} />
        <StatCard label="Today's pending preview count" value={pendingData.pending_today_count} />
        <StatCard label="Today date" value={countToday.date || "-"} />
      </div>

      <div className="flex flex-col gap-4 rounded-2xl border border-slate-200 bg-white p-5 text-slate-700">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <p className="text-sm text-slate-400">Mail summary call preparation</p>
            <p className="text-lg font-semibold text-slate-900">Only today's received emails are included in the voice call</p>
            <p className="text-sm text-slate-400">Reminder calls are not included in the daily mail summary call limit.</p>
          </div>
          <button
            type="button"
            onClick={handlePrepare}
            disabled={loading}
            className="rounded-xl bg-slate-900 px-4 py-3 font-semibold text-white disabled:opacity-60"
          >
            {loading ? "Preparing..." : "Prepare Mail Summary Call"}
          </button>
        </div>
        <p className="text-sm text-slate-400">
          The voice call reads a practical subset of today's emails and supports limited detail follow-up during the call.
        </p>
      </div>

      {message ? <div className="rounded-xl border border-slate-200 bg-slate-50 p-3 text-slate-700">{message}</div> : null}
      {error ? <div className="rounded-xl border border-slate-200 bg-slate-50 p-3 text-slate-700">{error}</div> : null}

      <div className="grid gap-6 xl:grid-cols-[1.3fr,0.7fr]">
        <div className="rounded-2xl border border-slate-200 bg-white p-5">
          <div className="mb-4 flex items-center justify-between gap-4">
            <div>
              <p className="text-sm text-slate-400">Prepared script preview</p>
              <h3 className="text-lg font-semibold text-slate-900">Latest prepared mail summary call</h3>
            </div>
            <div className="flex gap-2">
              <button
                type="button"
                onClick={handleStartVoiceCall}
                disabled={!preparedCall || preparedCall.call_status !== "prepared" || startingCall}
                className="rounded-xl bg-slate-900 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50"
              >
                {startingCall ? "Starting..." : "Start Voice Call"}
              </button>
              <button
                type="button"
                onClick={handleMarkDelivered}
                disabled={!preparedCall || delivering}
                className="rounded-xl border border-slate-200 px-4 py-2 text-sm font-semibold text-slate-700 disabled:opacity-50"
              >
                {delivering ? "Marking..." : "Mark as Delivered"}
              </button>
            </div>
          </div>
          {preparedCall?.script_text ? (
            <div className="space-y-4">
              <div className="grid gap-3 md:grid-cols-2">
                <MiniStat label="Provider" value={preparedCall.provider || "Not started"} />
                <MiniStat label="Provider call ID" value={preparedCall.provider_call_id || "-"} />
                <MiniStat label="Call status" value={preparedCall.call_status || "-"} />
                <MiniStat label="Delivery status" value={preparedCall.delivery_status || "-"} />
                <MiniStat label="Today's summaries in call" value={preparedCall.summary_count} />
                <MiniStat label="Duration" value={preparedCall.call_duration_seconds ? `${preparedCall.call_duration_seconds}s` : "-"} />
                <MiniStat label="Failure reason" value={preparedCall.failure_reason || preparedCall.provider_error_message || "-"} />
              </div>
              <pre className="whitespace-pre-wrap rounded-2xl bg-white p-4 text-sm text-slate-700">
                {preparedCall.script_text}
              </pre>
            </div>
          ) : (
            <div className="rounded-2xl border border-dashed border-slate-200 p-6 text-slate-400">
              No prepared mail summary call yet.
            </div>
          )}
        </div>

        <div className="rounded-2xl border border-slate-200 bg-white p-5">
          <p className="text-sm text-slate-400">Pending today delivery</p>
          <h3 className="mb-4 text-lg font-semibold text-slate-900">Today's summaries waiting for a voice call</h3>
          <div className="space-y-3">
            {pendingData.summaries.length === 0 ? (
              <div className="rounded-xl border border-dashed border-slate-200 p-4 text-slate-400">No emails received today.</div>
            ) : (
              pendingData.summaries.slice(0, 8).map((summary) => (
                <div key={summary.id} className="rounded-xl border border-slate-200 p-4">
                  <p className="font-medium text-slate-900">{summary.subject || "(No subject)"}</p>
                  <p className="text-sm text-slate-600">{summary.sender || "-"}</p>
                  <p className="mt-2 text-sm text-slate-400">{summary.short_summary || "-"}</p>
                </div>
              ))
            )}
          </div>
        </div>
      </div>

      <div className="rounded-2xl border border-slate-200 bg-white p-5">
        <p className="text-sm text-slate-400">Mail summary call history</p>
        <h3 className="mb-4 text-lg font-semibold text-slate-900">Newest first</h3>
        <div className="space-y-3">
          {history.length === 0 ? (
            <div className="rounded-xl border border-dashed border-slate-200 p-4 text-slate-400">No mail summary calls yet.</div>
          ) : (
            history.map((item) => (
              <div key={item.id} className="rounded-xl border border-slate-200 p-4">
                <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                  <div>
                    <p className="font-medium text-slate-900">Call #{item.id}</p>
                    <p className="text-sm text-slate-600">
                      {item.call_date} at {item.call_time}
                    </p>
                  </div>
                  <div className="text-sm text-slate-600">
                    <p>Status: {item.call_status}</p>
                    <p>Delivery: {item.delivery_status}</p>
                    <p>Today's summaries delivered: {item.summary_count}</p>
                    <p>Provider: {item.provider || "-"}</p>
                    <p>Provider call ID: {item.provider_call_id || "-"}</p>
                    <p>Duration: {item.call_duration_seconds ? `${item.call_duration_seconds}s` : "-"}</p>
                    <p>Failure: {item.failure_reason || item.provider_error_message || "-"}</p>
                  </div>
                </div>
                <div className="mt-4 rounded-xl border border-slate-200 bg-slate-50 p-4">
                  <p className="text-xs uppercase tracking-[0.2em] text-slate-400">Voice interactions</p>
                  <div className="mt-3 space-y-3">
                    {(interactionsByCallId[item.id] || []).length === 0 ? (
                      <p className="text-sm text-slate-400">No captured speech interactions yet.</p>
                    ) : (
                      (interactionsByCallId[item.id] || []).map((interaction) => (
                        <div key={interaction.id} className="rounded-lg border border-slate-200 p-3 text-sm text-slate-600">
                          <p>Order: {interaction.interaction_order}</p>
                          <p>Transcript: {interaction.user_transcript || "-"}</p>
                          <p>Detected intent: {interaction.detected_intent}</p>
                          <p>Email reference: {interaction.email_reference || "-"}</p>
                          <p>Confidence: {interaction.confidence || "-"}</p>
                          <p>System response: {interaction.system_response_text || "-"}</p>
                        </div>
                      ))
                    )}
                  </div>
                </div>
              </div>
            ))
          )}
        </div>
      </div>
    </PageShell>
  );
}

function StatCard({ label, value }) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-5">
      <p className="text-sm text-slate-400">{label}</p>
      <h3 className="mt-2 text-lg font-semibold text-slate-900">{value}</h3>
    </div>
  );
}

function MiniStat({ label, value }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-3">
      <p className="text-xs uppercase tracking-[0.2em] text-slate-400">{label}</p>
      <p className="mt-2 text-sm text-slate-700">{value}</p>
    </div>
  );
}


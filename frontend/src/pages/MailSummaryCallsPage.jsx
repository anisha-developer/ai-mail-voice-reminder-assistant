import { useEffect, useState } from "react";
import PageShell from "../components/PageShell";
import { callPreferencesApi, mailCallApi } from "../lib/api";

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

function callTimestamp(item) {
  if (!item) return 0;
  const callDate = item.call_date ? String(item.call_date) : "";
  const callTime = item.call_time ? String(item.call_time) : "00:00:00";
  const parsed = Date.parse(`${callDate}T${callTime}`);
  if (!Number.isNaN(parsed)) return parsed;
  const fallback = Date.parse(item.updated_at || item.created_at || 0);
  return Number.isNaN(fallback) ? 0 : fallback;
}

function getCallStatusLabel(item) {
  if (!item) return "Not scheduled";
  if (item.call_status === "delivered" || item.delivery_status === "delivered") return "Delivered";
  if (["prepared", "queued", "calling", "initiated", "ringing", "in_progress"].includes(item.call_status)) return "Pending";
  if (item.call_status === "enabled" || item.call_status === "disabled") {
    return item.delivery_status === "delivered" ? "Delivered" : "Pending";
  }
  if (item.call_status === "completed") return "Delivered";
  return item.call_status ? item.call_status.replaceAll("_", " ") : "Pending";
}



function formatTimeForDisplay(value) {
  if (!value) return "Not scheduled";
  const date = new Date(`1970-01-01T${value.length === 5 ? `${value}:00` : value}`);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("en-IN", {
    timeZone: "Asia/Kolkata",
    hour: "2-digit",
    minute: "2-digit",
    hour12: true,
  })
    .format(date)
    .replace(/\bam\b/g, "AM")
    .replace(/\bpm\b/g, "PM");
}

function formatISTDateTime(value) {
  if (!value) return "No scheduled call";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "No scheduled call";
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
  const [callPrefs, setCallPrefs] = useState({
    next_scheduled_summary_call_at: null,
    next_scheduled_summary_call_status: null,
    next_slot_label: null,
    next_slot_time: null,
    pending_new_email_summaries: 0,
  });
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [delivering, setDelivering] = useState(false);
  const [startingCall, setStartingCall] = useState(false);
  const [interactionsByCallId, setInteractionsByCallId] = useState({});
  const todayCallLabelById = new Map(
    (Array.isArray(history) ? history : [])
      .filter((item) => !countToday.date || String(item.call_date) === String(countToday.date))
      .slice()
      .sort((left, right) => callTimestamp(left) - callTimestamp(right))
      .map((item, index) => [item.id, `Summary Call ${index + 1}`]),
  );

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

  useEffect(() => {
    callPreferencesApi.get()
      .then((prefs) => setCallPrefs(prefs))
      .catch((err) => setError(err.message));
  }, []);

  const todayHistory = (Array.isArray(history) ? history : [])
    .filter((item) => !countToday.date || String(item.call_date) === String(countToday.date))
    .slice()
    .sort((left, right) => callTimestamp(left) - callTimestamp(right));

  const summaryCallSlots = [
    { slotNumber: 1, label: "Summary Call 1", enabled: callPrefs.call_slot_1_enabled, time: formatTimeForDisplay(callPrefs.call_slot_1_time) },
    { slotNumber: 2, label: "Summary Call 2", enabled: callPrefs.call_slot_2_enabled, time: formatTimeForDisplay(callPrefs.call_slot_2_time) },
    { slotNumber: 3, label: "Summary Call 3", enabled: callPrefs.call_slot_3_enabled, time: formatTimeForDisplay(callPrefs.call_slot_3_time) },
  ].map((slot) => {
    const matchingHistory = todayHistory.find((item) => String(item.call_time || "").slice(0, 5) === callPrefs[`call_slot_${slot.slotNumber}_time`]);
    const status = matchingHistory ? getCallStatusLabel(matchingHistory) : slot.enabled ? "Pending" : "Not scheduled";
    const exactTime = callPrefs[`call_slot_${slot.slotNumber}_time`] ? formatTimeForDisplay(callPrefs[`call_slot_${slot.slotNumber}_time`]) : "Not scheduled";
    return {
      ...slot,
      status,
      exactTime,
    };
  });
  const activeSummarySlots = summaryCallSlots.filter((slot) => slot.enabled);
  const deliveredSummarySlots = activeSummarySlots.filter((slot) => slot.status === "Delivered");
  const pendingSummarySlots = activeSummarySlots.filter((slot) => slot.status === "Pending");
  const summaryCallStatusText =
    activeSummarySlots.length === 0
      ? "No enabled summary call slots"
      : `${deliveredSummarySlots.length} delivered, ${pendingSummarySlots.length} pending`;

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

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        <StatCard label="Max mail summary calls per day" value={countToday.max_calls_per_day} />
        <StatCard label="Today's pending preview count" value={pendingData.pending_today_count} />
        <StatCard label="Today date" value={countToday.date || "-"} />
      </div>

      {message ? <div className="rounded-xl border border-slate-200 bg-slate-50 p-3 text-slate-700">{message}</div> : null}
      {error ? <div className="rounded-xl border border-slate-200 bg-slate-50 p-3 text-slate-700">{error}</div> : null}

      <div className="rounded-2xl border border-slate-200 bg-white p-5">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div className="min-w-0">
            <p className="text-sm text-slate-400">Summary call status</p>
            <h3 className="break-words text-lg font-semibold text-slate-900">
              {summaryCallStatusText}
            </h3>
            <p className="mt-1 max-w-3xl break-words text-sm text-slate-500">
              These are the fixed daily summary slots. Reminder calls do not affect this quota.
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              onClick={handlePrepare}
              disabled={loading}
              className="rounded-xl border border-slate-200 px-4 py-2 text-sm font-semibold text-slate-700 disabled:opacity-50"
            >
              {loading ? "Preparing..." : "Prepare mail summary call"}
            </button>
            <button
              type="button"
              onClick={handleStartVoiceCall}
              disabled={!preparedCall || preparedCall.call_status !== "prepared" || startingCall}
              className="rounded-xl bg-slate-900 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50"
            >
              {startingCall ? "Starting..." : "Start voice call"}
            </button>
            <button
              type="button"
              onClick={handleMarkDelivered}
              disabled={!preparedCall || delivering}
              className="rounded-xl border border-slate-200 px-4 py-2 text-sm font-semibold text-slate-700 disabled:opacity-50"
            >
              {delivering ? "Marking..." : "Mark as delivered"}
            </button>
          </div>
        </div>

        <div className="mt-5">
          <div className="grid gap-3 md:grid-cols-3">
            {summaryCallSlots.map((slot) => (
              <div key={slot.slotNumber} className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                <p className="text-xs uppercase tracking-[0.24em] text-slate-500">{slot.label}</p>
                <p className="mt-2 text-lg font-semibold text-slate-900">{slot.status}</p>
                <p className="mt-1 break-words text-sm text-slate-600">{slot.exactTime}</p>
                <p className="mt-2 break-words text-xs text-slate-400">Exact schedule from Settings</p>
              </div>
            ))}
          </div>
        </div>

        {preparedCall ? (
          <div className="mt-5 rounded-2xl border border-slate-200 bg-slate-50 p-4">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <p className="text-sm text-slate-400">Latest prepared call</p>
                <p className="mt-1 break-words text-lg font-semibold text-slate-900">
                  {preparedCall.summary_count} summaries ready for delivery
                </p>
              </div>
              <div className="grid gap-2 sm:grid-cols-3">
                <MiniStat label="Provider" value={preparedCall.provider || "Not started"} />
                <MiniStat label="Status" value={preparedCall.call_status || "-"} />
                <MiniStat label="Delivery" value={preparedCall.delivery_status || "-"} />
              </div>
            </div>
          </div>
        ) : null}
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
                    <p className="font-medium text-slate-900">{todayCallLabelById.get(item.id) || "Mail Summary Call"}</p>
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
                {(interactionsByCallId[item.id] || []).length > 0 ? (
                  <div className="mt-4 rounded-xl border border-slate-200 bg-slate-50 p-4">
                    <p className="text-xs uppercase tracking-[0.2em] text-slate-400">Speech interactions</p>
                    <div className="mt-3 space-y-3">
                      {(interactionsByCallId[item.id] || []).map((interaction) => (
                        <div key={interaction.id} className="rounded-lg border border-slate-200 bg-white p-3 text-sm text-slate-600">
                          <p>Interaction {interaction.interaction_order}</p>
                          <p>Transcript: {interaction.user_transcript || "-"}</p>
                          <p>Detected intent: {interaction.detected_intent}</p>
                          <p>Email reference: {interaction.email_reference || "-"}</p>
                          <p>Confidence: {interaction.confidence || "-"}</p>
                          <p>System response: {interaction.system_response_text || "-"}</p>
                        </div>
                      ))}
                    </div>
                  </div>
                ) : null}
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


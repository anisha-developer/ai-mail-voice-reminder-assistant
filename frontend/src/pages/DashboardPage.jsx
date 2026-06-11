import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import PageShell from "../components/PageShell";
import { useAuth } from "../context/AuthContext";
import { callPreferencesApi, emailApi, emailReplyApi, gmailApi, mailCallApi, recurringReminderApi, reminderApi, summaryApi } from "../lib/api";

const STATUS_STYLES = {
  success: "border-emerald-400/30 bg-slate-50 text-slate-700",
  warning: "border-slate-200 bg-slate-50 text-slate-700",
  danger: "border-red-400/30 bg-slate-50 text-slate-700",
  neutral: "border-slate-200 bg-white text-slate-700",
};

function SectionCard({ eyebrow, title, description, children, actions, compact = false }) {
  return (
    <section className="rounded-3xl border border-slate-200 bg-white p-5 shadow-soft sm:p-6">
      <div className="mb-5 flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          <p className="text-xs uppercase tracking-[0.28em] text-slate-500">{eyebrow}</p>
          <h2 className="mt-2 break-words text-2xl font-semibold text-slate-900">{title}</h2>
          {description ? <p className="mt-2 max-w-3xl break-words text-sm text-slate-400">{description}</p> : null}
        </div>
        {actions ? <div className="flex flex-wrap gap-2">{actions}</div> : null}
      </div>
      <div className={compact ? "space-y-4" : "space-y-5"}>{children}</div>
    </section>
  );
}

function StatusBadge({ children, tone = "neutral" }) {
  return <span className={`inline-flex rounded-full border px-3 py-1 text-xs font-medium ${STATUS_STYLES[tone] || STATUS_STYLES.neutral}`}>{children}</span>;
}

function MetricCard({ label, value, hint, status, truncateValue = false, title }) {
  return (
    <div className="min-w-0 rounded-2xl border border-slate-200 bg-slate-50 p-4">
      <p className="text-sm text-slate-400">{label}</p>
      <div className="mt-2 flex flex-wrap items-center gap-2">
        <h3
          className={`min-w-0 text-xl font-semibold leading-tight text-slate-900 ${truncateValue ? "truncate whitespace-nowrap overflow-hidden" : "break-normal"}`}
          title={title || (typeof value === "string" ? value : undefined)}
        >
          {value}
        </h3>
        {status ? <StatusBadge tone={status.tone || "neutral"}>{status.label}</StatusBadge> : null}
      </div>
      {hint ? <p className="mt-2 break-words text-xs text-slate-400">{hint}</p> : null}
    </div>
  );
}

function PreferenceStat({ label, value, hint, status, wide = false }) {
  return (
    <div className={`min-w-0 rounded-2xl border border-slate-200 ${wide ? "bg-white p-4 sm:col-span-2" : "bg-slate-50 p-4"}`}>
      <p className="text-sm text-slate-400">{label}</p>
      <div className="mt-2 flex flex-wrap items-center gap-2">
        <p className="min-w-0 break-words whitespace-normal text-base font-semibold leading-relaxed text-slate-900">{value}</p>
        {status ? <StatusBadge tone={status.tone || "neutral"}>{status.label}</StatusBadge> : null}
      </div>
      {hint ? <p className="mt-2 break-words whitespace-normal text-sm leading-relaxed text-slate-500">{hint}</p> : null}
    </div>
  );
}

function CallSlotRow({ label, time, enabled }) {
  return (
    <div className="flex flex-col items-start justify-between gap-3 rounded-2xl border border-slate-200 bg-white p-4 sm:flex-row sm:items-center">
      <div className="min-w-0">
        <p className="text-xs uppercase tracking-[0.24em] text-slate-500">{label}</p>
        <p className="mt-1 break-words whitespace-normal text-lg font-semibold text-slate-900">{time}</p>
      </div>
      {enabled ? null : <span className="text-xs font-medium text-slate-400">Disabled</span>}
    </div>
  );
}

function formatDateTime(value) {
  if (!value) return "—";
  try {
    return new Intl.DateTimeFormat("en-IN", {
      timeZone: "Asia/Kolkata",
      year: "numeric",
      month: "short",
      day: "2-digit",
      hour: "numeric",
      minute: "2-digit",
      hour12: true,
    })
      .format(new Date(value))
      .replace(/\b(am|pm)\b/gi, (match) => match.toUpperCase());
  } catch {
    return "—";
  }
}

function formatISTTime(value) {
  if (!value) return "Never";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Never";

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

function normalizeStatusLabel(value) {
  if (!value) return "";
  return String(value).replaceAll("_", " ").trim().toLowerCase();
}

function titleCaseStatus(value) {
  const normalized = normalizeStatusLabel(value);
  if (!normalized) return "";
  return normalized
    .split(" ")
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function getLatestMailSummaryCallStatus(call) {
  if (!call) return "No recent call status";

  const callStatus = normalizeStatusLabel(call.call_status);
  const deliveryStatus = normalizeStatusLabel(call.delivery_status);

  if (!callStatus && !deliveryStatus) {
    return "No recent call status";
  }

  if (callStatus === "failed") {
    return "Call failed";
  }

  if (deliveryStatus === "failed") {
    return "Delivery failed";
  }

  if (deliveryStatus === "delivered" || callStatus === "delivered" || callStatus === "completed") {
    return "Delivered";
  }

  const pendingStates = new Set(["prepared", "queued", "calling", "initiated", "ringing", "in progress", "enabled", "pending"]);
  if (pendingStates.has(callStatus) || pendingStates.has(deliveryStatus)) {
    if (callStatus === "completed" && deliveryStatus === "pending") {
      return "Call completed, delivery pending";
    }
    if (callStatus === "pending" && deliveryStatus === "delivered") {
      return "Call pending, delivery delivered";
    }
    if (callStatus && deliveryStatus && callStatus !== deliveryStatus) {
      return `Call ${titleCaseStatus(callStatus)}, delivery ${titleCaseStatus(deliveryStatus).toLowerCase()}`;
    }
    return titleCaseStatus(callStatus || deliveryStatus || "pending");
  }

  if (callStatus && deliveryStatus && callStatus !== deliveryStatus) {
    return `Call ${titleCaseStatus(callStatus)}, delivery ${titleCaseStatus(deliveryStatus).toLowerCase()}`;
  }

  return titleCaseStatus(callStatus || deliveryStatus || "pending") || "No recent call status";
}

function formatScheduleTime(value) {
  if (!value) return "-";
  return formatISTTime(`1970-01-01T${value}:00`);
}

function parseSummaryCallMoment(callDate, callTime) {
  if (!callDate || !callTime) return null;
  const parsed = Date.parse(`${String(callDate)}T${String(callTime).slice(0, 8)}`);
  if (!Number.isNaN(parsed)) return new Date(parsed);
  return null;
}

function getSummaryCallStatus(call) {
  if (!call) return "Pending";

  const callStatus = normalizeStatusLabel(call.call_status);
  const deliveryStatus = normalizeStatusLabel(call.delivery_status);

  if (deliveryStatus === "delivered" || callStatus === "delivered" || callStatus === "completed") {
    return "Delivered";
  }

  if (["failed", "missed", "cancelled"].includes(callStatus)) {
    return titleCaseStatus(callStatus);
  }

  if (["prepared", "queued", "calling", "initiated", "ringing", "in progress", "pending"].includes(callStatus)) {
    return "Pending";
  }

  return callStatus ? titleCaseStatus(callStatus) : "Pending";
}

function buildSummaryCallSlots(callPreferences, mailCallHistory, todayDate) {
  const slotDefinitions = [
    { slotNumber: 1, label: "Call 1", time: callPreferences.call_slot_1_time, enabled: callPreferences.call_slot_1_enabled },
    { slotNumber: 2, label: "Call 2", time: callPreferences.call_slot_2_time, enabled: callPreferences.call_slot_2_enabled },
    { slotNumber: 3, label: "Call 3", time: callPreferences.call_slot_3_time, enabled: callPreferences.call_slot_3_enabled },
  ];

  const todayCalls = (Array.isArray(mailCallHistory) ? mailCallHistory : [])
    .filter((item) => !todayDate || String(item.call_date) === String(todayDate))
    .slice()
    .sort((left, right) => new Date(left.updated_at || left.created_at || 0) - new Date(right.updated_at || right.created_at || 0));

  const slots = slotDefinitions.map((slot) => {
    const historyItem = todayCalls.find((item) => String(item.call_time || "").slice(0, 5) === String(slot.time || "").slice(0, 5));
    const status = slot.enabled ? getSummaryCallStatus(historyItem) : "Disabled";
    const moment = parseSummaryCallMoment(todayDate, slot.time);
    const delivered = status === "Delivered";
    return {
      ...slot,
      status,
      moment,
      delivered,
      displayTime: formatScheduleTime(slot.time),
    };
  });

  const nextSlot = slots.find((slot) => slot.enabled && !slot.delivered) || null;
  const enabledSlots = slots.filter((slot) => slot.enabled);
  const deliveredSlots = enabledSlots.filter((slot) => slot.delivered);
  const pendingSlots = enabledSlots.filter((slot) => !slot.delivered);

  return {
    slots,
    nextSlot,
    enabledSlots,
    deliveredSlots,
    pendingSlots,
    completedToday: enabledSlots.length > 0 && pendingSlots.length === 0,
  };
}

function formatSummaryUpdateResult(successCount, failedCount) {
  const success = Number(successCount) || 0;
  const failed = Number(failedCount) || 0;

  const successLabel = success === 1 ? "1 email summarized successfully" : success > 1 ? `${success} emails summarized successfully` : "";
  const failureLabel = failed === 1 ? "1 summary failed" : failed > 1 ? `${failed} summaries failed` : "";

  if (success && failed) {
    return `${success === 1 ? "1 email" : `${success} emails`} summarized, ${failureLabel}`;
  }

  if (success) return successLabel;
  if (failed) return failureLabel;
  return "No new summaries generated";
}

function describeRecurringRule(rule) {
  if (!rule) return "Unknown";
  const formattedTime = formatScheduleTime(rule.time_of_day);
  if (rule.repeat_type === "daily") return `Daily at ${formattedTime}`;
  if (rule.repeat_type === "weekdays") return `Weekdays at ${formattedTime}`;
  if (rule.repeat_type === "weekly") {
    const days = Array.isArray(rule.days_of_week) ? rule.days_of_week.join(", ") : "-";
    return `Weekly on ${days} at ${formattedTime}`;
  }
  if (rule.repeat_type === "custom_days") {
    const days = Array.isArray(rule.days_of_week) ? rule.days_of_week.join(", ") : "-";
    return `Custom days (${days}) at ${formattedTime}`;
  }
  if (rule.repeat_type === "monthly") return `Monthly on day ${rule.day_of_month || "-"} at ${formattedTime}`;
  if (rule.repeat_type === "custom_interval") return `Every ${rule.interval_value || "-"} ${rule.interval_unit || "unit"}`;
  return rule.repeat_type || "Unknown";
}

function getReminderTone(reminder) {
  if (reminder.status === "completed") return "success";
  if (["retry_scheduled", "missed", "failed", "snoozed"].includes(reminder.status)) return "warning";
  if (reminder.status === "cancelled") return "neutral";
  if (reminder.status === "calling") return "warning";
  return "neutral";
}

function getReminderUpcomingMoment(reminder) {
  if (!reminder) return null;

  const preferredValue =
    reminder.status === "retry_scheduled"
      ? reminder.next_retry_at || reminder.reminder_at
      : reminder.status === "snoozed"
        ? reminder.snoozed_until || reminder.next_retry_at || reminder.reminder_at
        : reminder.reminder_at || reminder.next_retry_at || reminder.snoozed_until || reminder.next_occurrence_at;

  if (!preferredValue) return null;

  const moment = new Date(preferredValue);
  return Number.isNaN(moment.getTime()) ? null : moment;
}

function cleanDisplayTitle(value) {
  if (!value) return "Untitled";
  return String(value)
    .replace(/\s+[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i, "")
    .replace(/\s+[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4,}$/i, "")
    .replace(/\s+[0-9a-f]{6,}$/i, "")
    .trim() || "Untitled";
}

function getNextUpcomingReminder(remindersList) {
  const now = Date.now();
  const excludedStatuses = new Set(["completed", "missed", "failed", "cancelled", "inactive"]);

  return (
    remindersList
      .map((reminder) => {
        const moment = getReminderUpcomingMoment(reminder);
        return { reminder, moment };
      })
      .filter(({ reminder, moment }) => moment && moment.getTime() > now && !excludedStatuses.has(reminder?.status))
      .sort((left, right) => left.moment.getTime() - right.moment.getTime())[0]?.reminder || null
  );
}

function buildRecentActivity({ sync, autoSync, mailCallHistory, reminders, recentReplies, todaySummaryCount }) {
  const activity = [];

  if (sync?.last_sync_time) {
    activity.push({
      label: "Gmail sync completed",
      detail: `${sync.total_emails_stored || 0} synced inbox emails so far.`,
      at: sync.last_sync_time,
    });
  }

  if (autoSync?.last_auto_summary_at) {
    activity.push({
      label: "Email summaries updated",
      detail: formatSummaryUpdateResult(autoSync.last_auto_summary_success_count, autoSync.last_auto_summary_failed_count),
      at: autoSync.last_auto_summary_at,
    });
  } else if (todaySummaryCount) {
    activity.push({
      label: "Today’s summaries ready",
      detail: `${todaySummaryCount} summaries available for voice calls.`,
      at: sync?.last_sync_time || new Date().toISOString(),
    });
  }

  if (mailCallHistory?.[0]) {
    const latest = mailCallHistory[0];
    activity.push({
      label: "Latest mail-summary call",
      detail: `${getLatestMailSummaryCallStatus(latest)}.`,
      at: latest.updated_at || latest.created_at,
    });
  }

  const latestReminder = reminders
    .slice()
    .sort((a, b) => new Date(b.updated_at || b.created_at || 0) - new Date(a.updated_at || a.created_at || 0))[0];
  if (latestReminder) {
    activity.push({
      label: `Reminder ${latestReminder.status}`,
      detail: latestReminder.title,
      at: latestReminder.updated_at || latestReminder.created_at,
    });
  }

  const latestReply = recentReplies?.[0];
  if (latestReply) {
    activity.push({
      label: "Latest reply action",
      detail: latestReply.subject || latestReply.status || "Email reply activity",
      at: latestReply.sent_at || latestReply.created_at || new Date().toISOString(),
    });
  }

  return activity
    .filter((item) => item.at)
    .sort((a, b) => new Date(b.at) - new Date(a.at))
    .slice(0, 6);
}

export default function DashboardPage() {
  const { user } = useAuth();
  const [loading, setLoading] = useState(true);
  const [syncStatus, setSyncStatus] = useState({ last_sync_time: null, total_emails_stored: 0, gmail_connected: false });
  const [gmailStatus, setGmailStatus] = useState({ is_connected: false, gmail_email: null, connected_at: null, can_send_replies: false });
  const [summaryStats, setSummaryStats] = useState({ total: 0, unsummarized: 0, today: 0 });
  const [mailCallStats, setMailCallStats] = useState({ used: 0, remaining: 3, pending: 0, lastCall: null, todaySummaries: 0, date: null });
  const [callPreferences, setCallPreferences] = useState({
    timezone: "Asia/Kolkata",
    call_slot_1_time: "09:00",
    call_slot_1_enabled: true,
    call_slot_2_time: "13:00",
    call_slot_2_enabled: true,
    call_slot_3_time: "19:00",
    call_slot_3_enabled: true,
    minimum_new_emails_to_call: 1,
    next_scheduled_summary_call_status: null,
    pending_new_email_summaries: 0,
    would_call_next_slot: false,
    next_slot_label: null,
    next_slot_time: null,
  });
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
    unsummarized_email_count: 0,
  });
  const [reminders, setReminders] = useState([]);
  const [recurringRules, setRecurringRules] = useState([]);
  const [recentReplies, setRecentReplies] = useState([]);
  const [recentActivity, setRecentActivity] = useState([]);
  const [mailCallHistory, setMailCallHistory] = useState([]);

  const recoveryStatuses = useMemo(() => new Set(["retry_scheduled", "missed", "snoozed", "failed"]), []);

  const loadDashboard = async () => {
    setLoading(true);
    try {
      const [sync, gmail, autoSync, summaries, emails, counts, pending, history, remindersData, repliesData, prefs, recurringData] =
        await Promise.all([
          emailApi.getSyncStatus(),
          gmailApi.getStatus().catch(() => ({ is_connected: false, gmail_email: null, connected_at: null, can_send_replies: false })),
          emailApi.getAutoSyncStatus(),
          summaryApi.getAllSummaries(),
          emailApi.getAllEmails(),
          mailCallApi.getCountToday(),
          mailCallApi.getPendingSummaries(),
          mailCallApi.getHistory(),
          reminderApi.listReminders(true),
          emailReplyApi.list(),
          callPreferencesApi.get(),
          recurringReminderApi.list(),
        ]);

      setSyncStatus(sync);
      setGmailStatus(gmail);
      setAutoSyncStatus(autoSync);
      setSummaryStats({
        total: summaries.length,
        unsummarized: emails.filter((email) => !email.is_summarized).length,
        today: counts.today_summaries_count,
      });
      setMailCallStats({
        used: counts.used_calls_today,
        remaining: counts.remaining_calls_today,
        pending: pending.pending_count,
        lastCall: history[0] || null,
        todaySummaries: counts.today_summaries_count,
        date: counts.date || null,
      });
      setReminders(remindersData.value || []);
      setRecurringRules(recurringData.value || []);
      setRecentReplies(repliesData.value || []);
      setCallPreferences(prefs);
      setMailCallHistory(history);
      setRecentActivity(
        buildRecentActivity({
          sync,
          autoSync,
          mailCallHistory: history,
          reminders: remindersData.value || [],
          recurringRules: recurringData.value || [],
          recentReplies: repliesData.value || [],
          todaySummaryCount: counts.today_summaries_count,
        }),
      );
    } catch {
      // Keep the dashboard usable even if one section fails.
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadDashboard();
  }, []);

  const summaryCallPreview = useMemo(
    () => buildSummaryCallSlots(callPreferences, mailCallHistory, mailCallStats.date),
    [callPreferences, mailCallHistory, mailCallStats.date],
  );

  const callPreferencesPreview = useMemo(() => {
    const nextSlot = summaryCallPreview.nextSlot;
    const pending = callPreferences.pending_new_email_summaries ?? 0;
    const deliveredCount = summaryCallPreview.deliveredSlots.length;
    const pendingCount = summaryCallPreview.pendingSlots.length;

    return {
      nextSlot,
      pending,
      completedToday: summaryCallPreview.completedToday,
      deliveredCount,
      pendingCount,
      nextCallLabel: summaryCallPreview.completedToday
        ? "All summary calls completed today"
        : pending === 0
          ? "No pending summaries for the next call"
          : nextSlot
            ? `${nextSlot.label} at ${formatScheduleTime(nextSlot.time)}`
            : "No scheduled call",
      summaryProgressLabel:
        deliveredCount || pendingCount
          ? `${deliveredCount} delivered, ${pendingCount} pending today`
          : "No summary call activity yet today",
    };
  }, [callPreferences, summaryCallPreview]);

  const nextUpcomingReminder = useMemo(() => getNextUpcomingReminder(reminders), [reminders]);

  return (
    <PageShell
      title="Dashboard"
      description="A compact overview of Gmail sync, email summaries, voice calls, and reminders."
    >
      <div className="grid gap-4">
        <div className="rounded-3xl border border-slate-200 bg-slate-50 p-5">
          <h3 className="break-words text-2xl font-semibold text-slate-900">{user?.name || user?.email || "User"}</h3>
          <p className="mt-2 max-w-3xl break-words text-sm text-slate-700">
            Here is a quick overview of your email summaries, Gmail sync, calls, and reminders.
          </p>
          <div className="mt-4 flex flex-wrap gap-2">
            <StatusBadge tone={gmailStatus.is_connected ? "success" : "warning"}>{gmailStatus.is_connected ? "Gmail connected" : "Gmail disconnected"}</StatusBadge>
            <StatusBadge tone={autoSyncStatus.auto_sync_enabled ? "success" : "warning"}>Email sync {autoSyncStatus.auto_sync_enabled ? "enabled" : "disabled"}</StatusBadge>
            <StatusBadge tone={autoSyncStatus.auto_summarize_after_sync ? "success" : "warning"}>Automatic summaries {autoSyncStatus.auto_summarize_after_sync ? "enabled" : "disabled"}</StatusBadge>
          </div>
        </div>
      </div>

      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <MetricCard label="Gmail connection" value={gmailStatus.is_connected ? "Connected" : "Disconnected"} status={{ tone: gmailStatus.is_connected ? "success" : "warning", label: gmailStatus.is_connected ? "Live" : "Needs setup" }} hint={gmailStatus.gmail_email || "No Gmail account connected yet."} />
        <MetricCard label="Synced inbox emails" value={syncStatus.total_emails_stored} hint={syncStatus.last_sync_time ? `Last sync: ${formatDateTime(syncStatus.last_sync_time)}` : "Not synced yet."} />
        <MetricCard label="Summaries today" value={summaryStats.today} hint={`Emails waiting for summary: ${autoSyncStatus.unsummarized_email_count ?? summaryStats.unsummarized}`} />
        <MetricCard label="Summary calls used today" value={`${mailCallStats.used} of ${mailCallStats.remaining + mailCallStats.used}`} hint="Reminder calls do not affect this limit." />
      </section>

      <div className="grid gap-4 xl:grid-cols-2">

        <SectionCard eyebrow="Today’s Email Summary" title="Email Summary Status" description="Your email sync and summary status for today." actions={[<Link key="summaries" to="/summaries" className="rounded-xl border border-slate-200 px-4 py-2 text-sm font-semibold text-slate-700 transition hover:bg-slate-50">Open Summaries</Link>]}>
          <div className="grid gap-3 sm:grid-cols-2">
            <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
              <p className="text-sm text-slate-400">Email sync</p>
              <p className="mt-2 text-lg font-semibold text-slate-900">{autoSyncStatus.auto_sync_enabled ? "Enabled" : "Disabled"}</p>
            </div>
            <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
              <p className="text-sm text-slate-400">Automatic summaries</p>
              <p className="mt-2 text-lg font-semibold text-slate-900">{autoSyncStatus.auto_summarize_after_sync ? "Enabled" : "Disabled"}</p>
              <p className="mt-1 text-xs text-slate-400">Emails waiting for summary: {autoSyncStatus.unsummarized_email_count ?? summaryStats.unsummarized}</p>
            </div>
            <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
              <p className="text-sm text-slate-400">Last sync</p>
              <p className="mt-2 text-lg font-semibold text-slate-900">{formatDateTime(autoSyncStatus.last_auto_sync_at)}</p>
              <p className="mt-1 break-words text-xs text-slate-400">
                {autoSyncStatus.last_auto_sync_status === "success" ? "Sync completed" : autoSyncStatus.last_auto_sync_status || "—"}
              </p>
            </div>
            <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
              <p className="text-sm text-slate-400">Last summary update</p>
              <p className="mt-2 text-lg font-semibold text-slate-900">{formatDateTime(autoSyncStatus.last_auto_summary_at)}</p>
              <p className="mt-1 text-xs text-slate-400">
                {formatSummaryUpdateResult(
                  autoSyncStatus.last_auto_summary_success_count,
                  autoSyncStatus.last_auto_summary_failed_count,
                )}
              </p>
            </div>
          </div>
          {autoSyncStatus.last_auto_sync_error || autoSyncStatus.last_auto_summary_error ? (
            <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4 text-sm text-slate-700">
              {autoSyncStatus.last_auto_sync_error ? <p className="break-words">Last auto sync error: {autoSyncStatus.last_auto_sync_error}</p> : null}
              {autoSyncStatus.last_auto_summary_error ? <p className="break-words">Last auto summary error: {autoSyncStatus.last_auto_summary_error}</p> : null}
            </div>
          ) : null}
        </SectionCard>

        <SectionCard eyebrow="Voice Mail Calls" title="Call quota and latest call status" description="The call preparation and start controls stay on the dedicated mail-summary calls page." actions={[<Link key="calls" to="/mail-calls" className="rounded-xl border border-slate-200 px-4 py-2 text-sm font-semibold text-slate-700 transition hover:bg-slate-50">Open calls page</Link>]}>
          <div className="grid gap-3 md:grid-cols-3">
            <MetricCard label="Used today" value={mailCallStats.used} hint={`Remaining today: ${mailCallStats.remaining}`} />
            <MetricCard label="Pending summaries" value={mailCallStats.pending} hint="Ready for mail summary delivery." />
            <MetricCard label="Today's summaries" value={mailCallStats.todaySummaries || summaryStats.today} hint="Prepared from today's Gmail messages." />
          </div>
          <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
            <p className="text-sm text-slate-400">Latest mail summary call</p>
            <p className="mt-2 break-words text-lg font-semibold text-slate-900">{getLatestMailSummaryCallStatus(mailCallStats.lastCall)}</p>
            <p className="mt-1 text-xs text-slate-400">{mailCallStats.lastCall?.updated_at ? `Updated: ${formatDateTime(mailCallStats.lastCall.updated_at)}` : "Start a call to see provider updates here."}</p>
          </div>
        </SectionCard>

        <SectionCard
          eyebrow="Call Preferences"
          title="Daily Email Summary Call Schedule"
          description="Calls happen only when new pending emails meet your preferences."
          actions={[
            <Link
              key="manage-preferences"
              to="/settings"
              className="rounded-xl border border-slate-200 px-4 py-2 text-sm font-semibold text-slate-700 transition hover:bg-slate-50"
            >
              Manage preferences
            </Link>,
          ]}
        >
          <div className="grid gap-4 xl:grid-cols-[1.2fr_0.8fr]">
            <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
              <p className="text-sm text-slate-400">Summary</p>
              <div className="mt-3 grid grid-cols-1 gap-3 lg:grid-cols-2">
                <PreferenceStat label="Next call" value={callPreferencesPreview.nextCallLabel} />
                <PreferenceStat label="Pending new summaries" value={String(callPreferencesPreview.pending)} />
                <PreferenceStat label="Summary progress" value={callPreferencesPreview.summaryProgressLabel} wide />
              </div>
            </div>
            <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
              <p className="text-sm text-slate-400">Call slots</p>
              <div className="mt-3 space-y-3">
                <CallSlotRow label="Call 1" time={formatScheduleTime(callPreferences.call_slot_1_time)} enabled={callPreferences.call_slot_1_enabled} />
                <CallSlotRow label="Call 2" time={formatScheduleTime(callPreferences.call_slot_2_time)} enabled={callPreferences.call_slot_2_enabled} />
                <CallSlotRow label="Call 3" time={formatScheduleTime(callPreferences.call_slot_3_time)} enabled={callPreferences.call_slot_3_enabled} />
              </div>
            </div>
          </div>
        </SectionCard>

        <SectionCard eyebrow="Reminders" title="Reminder overview" description="The dashboard stays compact here and points you to the dedicated reminders page for full management." actions={[<Link key="reminders" to="/reminders" className="rounded-xl border border-slate-200 px-4 py-2 text-sm font-semibold text-slate-700 transition hover:bg-slate-50">View all reminders</Link>]}>
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            <MetricCard label="Upcoming reminders" value={reminders.filter((reminder) => reminder.status === "scheduled").length} />
            <MetricCard label="Missed / retry" value={reminders.filter((reminder) => recoveryStatuses.has(reminder.status)).length} />
            <MetricCard label="Completed today" value={reminders.filter((reminder) => reminder.status === "completed").length} />
            <MetricCard label="Next reminder" value={nextUpcomingReminder ? formatDateTime(getReminderUpcomingMoment(nextUpcomingReminder)) : "No upcoming reminders"} />
          </div>
          <p className="text-sm text-slate-500">Use the dedicated reminders page for full reminder history, retry details, and actions.</p>
        </SectionCard>

        <SectionCard eyebrow="Recurring Reminders" title="Recurring Reminders" description="Manage reminders that repeat automatically." actions={[<Link key="recurring-link" to="/recurring-reminders" className="rounded-xl border border-slate-200 px-4 py-2 text-sm font-semibold text-slate-700 transition hover:bg-slate-50">View recurring reminders</Link>]} compact>
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            <MetricCard label="Active recurring reminders" value={recurringRules.filter((rule) => rule.status === "active").length} />
            <MetricCard label="Paused recurring reminders" value={recurringRules.filter((rule) => rule.status === "paused").length} />
            <MetricCard label="Next scheduled reminder" value={formatDateTime(recurringRules[0]?.next_occurrence_at)} />
            <MetricCard
              label="Latest recurring reminder"
              value={cleanDisplayTitle(recurringRules[0]?.title) || "None"}
              truncateValue
              hint={recurringRules[0] ? describeRecurringRule(recurringRules[0]) : "No recurring reminders yet."}
              title={recurringRules[0]?.title || undefined}
            />
          </div>
          <p className="text-sm text-slate-500">Use the dedicated recurring reminders page for full repeat-rule history and actions.</p>
        </SectionCard>

        <SectionCard eyebrow="Reminder Follow-ups" title="Reminder Follow-ups" description="Reminders that were missed or need another attempt." compact>
          <div className="grid gap-3 sm:grid-cols-2">
            <MetricCard label="Reminders needing attention" value={reminders.filter((reminder) => recoveryStatuses.has(reminder.status)).length} />
            <MetricCard label="Next retry time" value={formatDateTime(reminders.filter((reminder) => recoveryStatuses.has(reminder.status))[0]?.next_retry_at)} />
          </div>
          <div className="flex justify-end">
            <Link to="/reminders" className="rounded-xl border border-slate-200 px-4 py-2 text-sm font-semibold text-slate-700 transition hover:bg-slate-50">
              View all reminders
            </Link>
          </div>
        </SectionCard>

        <SectionCard eyebrow="Recent Activity" title="Recent Activity" description="A compact feed of the most recent dashboard-relevant changes across Gmail, summaries, voice calls, and reminders." compact>
          <div className="space-y-3">
            {recentActivity.length === 0 ? (
              <p className="text-sm text-slate-400">No recent activity yet.</p>
            ) : (
              recentActivity.slice(0, 3).map((item, index) => (
                <div key={`${item.label}-${index}`} className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                  <div className="flex flex-col gap-1 sm:flex-row sm:items-start sm:justify-between">
                    <div className="min-w-0">
                      <p className="break-words text-sm font-semibold text-slate-900">{item.label}</p>
                      <p className="break-words text-xs text-slate-400">{item.detail}</p>
                    </div>
                    <p className="text-xs text-slate-400">{formatDateTime(item.at)}</p>
                  </div>
                </div>
              ))
            )}
            {recentActivity.length > 3 ? (
              <div className="flex justify-end">
                <Link to="/reminders" className="text-sm font-semibold text-slate-700 underline decoration-slate-300 underline-offset-4 hover:text-slate-900">
                  View more
                </Link>
              </div>
            ) : null}
          </div>
        </SectionCard>

        <SectionCard eyebrow="Recent Email Replies" title="Recent Email Replies" description="Recent replies sent from the app." compact>
          <div className="space-y-3">
            {recentReplies.length === 0 ? (
              <p className="text-sm text-slate-400">No email replies yet.</p>
            ) : (
              recentReplies.slice(0, 5).map((reply) => (
                <div key={reply.id} className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                  <p className="break-words text-sm font-semibold text-slate-900">{reply.subject || "Reply"}</p>
                  <div className="mt-1 flex flex-wrap gap-x-4 gap-y-1 text-xs text-slate-400">
                    <span>Status: {reply.status}</span>
                    {reply.sent_at ? <span>Sent: {formatDateTime(reply.sent_at)}</span> : null}
                    {reply.error_message ? <span className="break-words text-red-300">{reply.error_message}</span> : null}
                  </div>
                </div>
              ))
            )}
          </div>
        </SectionCard>
      </div>
      {loading ? <p className="text-xs text-slate-400">Refreshing dashboard data...</p> : null}
    </PageShell>
  );
}

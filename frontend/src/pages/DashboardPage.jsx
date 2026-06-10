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

function MetricCard({ label, value, hint, status, truncateValue = false }) {
  return (
    <div className="min-w-0 rounded-2xl border border-slate-200 bg-slate-50 p-4">
      <p className="text-sm text-slate-400">{label}</p>
      <div className="mt-2 flex flex-wrap items-center gap-2">
        <h3
          className={`min-w-0 text-xl font-semibold leading-tight text-slate-900 ${truncateValue ? "truncate whitespace-nowrap overflow-hidden" : "break-normal"}`}
          title={typeof value === "string" ? value : undefined}
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
      <StatusBadge tone={enabled ? "success" : "warning"}>{enabled ? "Enabled" : "Disabled"}</StatusBadge>
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

function describeRecurringRule(rule) {
  if (!rule) return "Unknown";
  if (rule.repeat_type === "daily") return `Daily at ${rule.time_of_day || "-"}`;
  if (rule.repeat_type === "weekdays") return `Weekdays at ${rule.time_of_day || "-"}`;
  if (rule.repeat_type === "weekly") {
    const days = Array.isArray(rule.days_of_week) ? rule.days_of_week.join(", ") : "-";
    return `Weekly on ${days} at ${rule.time_of_day || "-"}`;
  }
  if (rule.repeat_type === "custom_days") {
    const days = Array.isArray(rule.days_of_week) ? rule.days_of_week.join(", ") : "-";
    return `Custom days (${days}) at ${rule.time_of_day || "-"}`;
  }
  if (rule.repeat_type === "monthly") return `Monthly on day ${rule.day_of_month || "-"} at ${rule.time_of_day || "-"}`;
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

function buildRecentActivity({ sync, autoSync, mailCallHistory, reminders, recentReplies, todaySummaryCount }) {
  const activity = [];

  if (sync?.last_sync_time) {
    activity.push({
      label: "Gmail sync completed",
      detail: `${sync.total_emails_stored || 0} emails stored so far.`,
      at: sync.last_sync_time,
    });
  }

  if (autoSync?.last_auto_summary_at) {
    activity.push({
      label: "Auto-summary run",
      detail: `Success: ${autoSync.last_auto_summary_success_count || 0}, failed: ${autoSync.last_auto_summary_failed_count || 0}.`,
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
      detail: `${latest.call_status} / ${latest.delivery_status}${latest.provider_status ? ` / ${latest.provider_status}` : ""}.`,
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
  const [mailCallStats, setMailCallStats] = useState({ used: 0, remaining: 3, pending: 0, lastCall: null, todaySummaries: 0 });
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

  const recoveryStatuses = useMemo(() => new Set(["retry_scheduled", "missed", "snoozed", "failed"]), []);

  const loadDashboard = async () => {
    setLoading(true);
    try {
      const [sync, gmail, autoSync, summaries, todaySummaries, emails, counts, pending, history, remindersData, repliesData, prefs, recurringData] =
        await Promise.all([
          emailApi.getSyncStatus(),
          gmailApi.getStatus().catch(() => ({ is_connected: false, gmail_email: null, connected_at: null, can_send_replies: false })),
          emailApi.getAutoSyncStatus(),
          summaryApi.getAllSummaries(),
          summaryApi.getTodaySummaries(),
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
        today: todaySummaries.length,
      });
      setMailCallStats({
        used: counts.used_calls_today,
        remaining: counts.remaining_calls_today,
        pending: pending.pending_count,
        lastCall: history[0] || null,
        todaySummaries: todaySummaries.length,
      });
      setReminders(remindersData.value || []);
      setRecurringRules(recurringData.value || []);
      setRecentReplies(repliesData.value || []);
      setCallPreferences(prefs);
      setRecentActivity(
        buildRecentActivity({
          sync,
          autoSync,
          mailCallHistory: history,
          reminders: remindersData.value || [],
          recurringRules: recurringData.value || [],
          recentReplies: repliesData.value || [],
          todaySummaryCount: todaySummaries.length,
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

  const callPreferencesPreview = useMemo(() => {
    const slots = [
      { label: "Call 1", time: callPreferences.call_slot_1_time, enabled: callPreferences.call_slot_1_enabled },
      { label: "Call 2", time: callPreferences.call_slot_2_time, enabled: callPreferences.call_slot_2_enabled },
      { label: "Call 3", time: callPreferences.call_slot_3_time, enabled: callPreferences.call_slot_3_enabled },
    ].filter((slot) => slot.enabled);
    return {
      nextSlot: slots[0] || null,
      status: callPreferences.next_scheduled_summary_call_status,
      pending: callPreferences.pending_new_email_summaries ?? 0,
      wouldCall: callPreferences.would_call_next_slot,
    };
  }, [callPreferences]);

  return (
    <PageShell
      title="Dashboard"
      description="A compact command center for Gmail status, summaries, voice mail calls, reminders, recurring reminders, and system health."
    >
      <div className="grid gap-4">
        <div className="rounded-3xl border border-slate-200 bg-slate-50 p-5">
          <h3 className="break-words text-2xl font-semibold text-slate-900">{user?.name || user?.email || "User"}</h3>
          <p className="mt-2 max-w-3xl break-words text-sm text-slate-700">
            This dashboard surfaces the essentials. The detailed workflows live on their dedicated pages so the layout stays compact and readable.
          </p>
          <div className="mt-4 flex flex-wrap gap-2">
            <StatusBadge tone={gmailStatus.is_connected ? "success" : "warning"}>{gmailStatus.is_connected ? "Gmail connected" : "Gmail disconnected"}</StatusBadge>
            <StatusBadge tone={autoSyncStatus.auto_sync_enabled ? "success" : "warning"}>Auto sync {autoSyncStatus.auto_sync_enabled ? "on" : "off"}</StatusBadge>
            <StatusBadge tone={autoSyncStatus.auto_summarize_after_sync ? "success" : "warning"}>Auto summary {autoSyncStatus.auto_summarize_after_sync ? "on" : "off"}</StatusBadge>
          </div>
        </div>
      </div>

      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <MetricCard label="Gmail connection" value={gmailStatus.is_connected ? "Connected" : "Disconnected"} status={{ tone: gmailStatus.is_connected ? "success" : "warning", label: gmailStatus.is_connected ? "Live" : "Needs setup" }} hint={gmailStatus.gmail_email || "No Gmail account connected yet."} />
        <MetricCard label="Emails stored" value={syncStatus.total_emails_stored} hint={syncStatus.last_sync_time ? `Last sync: ${formatDateTime(syncStatus.last_sync_time)}` : "Not synced yet."} />
        <MetricCard label="Summaries today" value={summaryStats.today} hint={`Unsummarized: ${autoSyncStatus.unsummarized_email_count ?? summaryStats.unsummarized}`} />
        <MetricCard label="Mail-summary quota" value={`${mailCallStats.used}/${mailCallStats.remaining + mailCallStats.used}`} hint="Reminder calls do not affect this limit." />
      </section>

      <div className="grid gap-4 xl:grid-cols-2">
        <SectionCard eyebrow="Gmail Connection" title="Connection and sync status" description="Detailed sync actions live on the Email Inbox page." actions={[<Link key="inbox" to="/inbox" className="rounded-xl border border-slate-200 px-4 py-2 text-sm font-semibold text-slate-700 transition hover:bg-slate-50">Open Inbox</Link>, <Link key="settings" to="/settings" className="rounded-xl border border-slate-200 px-4 py-2 text-sm font-semibold text-slate-700 transition hover:bg-slate-50">Manage Gmail</Link>]}>
          <div className="grid gap-3 sm:grid-cols-2">
            <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
              <p className="text-sm text-slate-400">Connection</p>
              <p className="mt-2 text-lg font-semibold text-slate-900">{gmailStatus.is_connected ? "Connected" : "Disconnected"}</p>
              <p className="mt-1 break-words text-xs text-slate-400">{gmailStatus.gmail_email || "Connect Gmail from Settings to enable reading and voice features."}</p>
            </div>
            <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
              <p className="text-sm text-slate-400">Last sync</p>
              <p className="mt-2 text-lg font-semibold text-slate-900">{formatDateTime(syncStatus.last_sync_time)}</p>
            </div>
          </div>
          {gmailStatus.is_connected && !gmailStatus.can_send_replies ? (
            <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4 text-sm text-slate-700">
              Gmail is connected, but reply permission is missing. Reconnect Gmail if you want voice replies enabled.
            </div>
          ) : null}
        </SectionCard>

        <SectionCard eyebrow="Today’s Email Summary" title="Summary readiness and automation" description="This section is status-focused; generation controls live on the summaries page." actions={[<Link key="summaries" to="/summaries" className="rounded-xl border border-slate-200 px-4 py-2 text-sm font-semibold text-slate-700 transition hover:bg-slate-50">Open Summaries</Link>]}>
          <div className="grid gap-3 sm:grid-cols-2">
            <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
              <p className="text-sm text-slate-400">Auto sync</p>
              <p className="mt-2 text-lg font-semibold text-slate-900">{autoSyncStatus.auto_sync_enabled ? "Enabled" : "Disabled"}</p>
              <p className="mt-1 text-xs text-slate-400">Interval: {autoSyncStatus.interval_minutes} minute(s)</p>
            </div>
            <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
              <p className="text-sm text-slate-400">Auto summarize after sync</p>
              <p className="mt-2 text-lg font-semibold text-slate-900">{autoSyncStatus.auto_summarize_after_sync ? "Enabled" : "Disabled"}</p>
              <p className="mt-1 text-xs text-slate-400">Unsummarized: {autoSyncStatus.unsummarized_email_count ?? summaryStats.unsummarized}</p>
            </div>
            <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
              <p className="text-sm text-slate-400">Last auto sync</p>
              <p className="mt-2 text-lg font-semibold text-slate-900">{formatDateTime(autoSyncStatus.last_auto_sync_at)}</p>
              <p className="mt-1 break-words text-xs text-slate-400">Status: {autoSyncStatus.last_auto_sync_status || "—"}</p>
            </div>
            <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
              <p className="text-sm text-slate-400">Last auto summary</p>
              <p className="mt-2 text-lg font-semibold text-slate-900">{formatDateTime(autoSyncStatus.last_auto_summary_at)}</p>
              <p className="mt-1 text-xs text-slate-400">Success: {autoSyncStatus.last_auto_summary_success_count} | Failed: {autoSyncStatus.last_auto_summary_failed_count}</p>
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
            <p className="text-sm text-slate-400">Latest delivery result</p>
            <p className="mt-2 break-words text-lg font-semibold text-slate-900">{mailCallStats.lastCall ? `${mailCallStats.lastCall.call_status} / ${mailCallStats.lastCall.delivery_status}${mailCallStats.lastCall.provider_status ? ` / ${mailCallStats.lastCall.provider_status}` : ""}` : "No voice delivery yet"}</p>
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
                <PreferenceStat
                  label="Next call slot"
                  value={
                    callPreferencesPreview.nextSlot
                      ? `${callPreferencesPreview.nextSlot.label}: ${formatISTTime(`1970-01-01T${callPreferencesPreview.nextSlot.time}:00`)}`
                      : "No enabled slots"
                  }
                />
                <PreferenceStat label="Pending new summaries" value={String(callPreferencesPreview.pending)} />
                <PreferenceStat
                  label="Scheduler status"
                  value={callPreferencesPreview.status || "Unknown"}
                  hint={
                    callPreferencesPreview.wouldCall
                      ? `Will call because minimum is ${callPreferences.minimum_new_emails_to_call}`
                      : "Will skip because there are no pending summaries."
                  }
                  wide
                />
                <PreferenceStat
                  label="Timezone"
                  value={callPreferences.timezone || "UTC"}
                  hint="Controls the summary call slots."
                />
              </div>
            </div>
            <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
              <p className="text-sm text-slate-400">Call slots</p>
              <div className="mt-3 space-y-3">
                <CallSlotRow label="Call 1" time={formatISTTime(`1970-01-01T${callPreferences.call_slot_1_time}:00`)} enabled={callPreferences.call_slot_1_enabled} />
                <CallSlotRow label="Call 2" time={formatISTTime(`1970-01-01T${callPreferences.call_slot_2_time}:00`)} enabled={callPreferences.call_slot_2_enabled} />
                <CallSlotRow label="Call 3" time={formatISTTime(`1970-01-01T${callPreferences.call_slot_3_time}:00`)} enabled={callPreferences.call_slot_3_enabled} />
              </div>
            </div>
          </div>
        </SectionCard>

        <SectionCard eyebrow="Reminders" title="Reminder overview" description="The dashboard stays compact here and points you to the dedicated reminders page for full management." actions={[<Link key="reminders" to="/reminders" className="rounded-xl border border-slate-200 px-4 py-2 text-sm font-semibold text-slate-700 transition hover:bg-slate-50">View all reminders</Link>]}>
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            <MetricCard label="Upcoming reminders" value={reminders.filter((reminder) => reminder.status === "scheduled").length} />
            <MetricCard label="Missed / retry" value={reminders.filter((reminder) => recoveryStatuses.has(reminder.status)).length} />
            <MetricCard label="Completed today" value={reminders.filter((reminder) => reminder.status === "completed").length} />
            <MetricCard label="Next reminder" value={formatDateTime(reminders[0]?.reminder_at)} />
          </div>
          <p className="text-sm text-slate-500">Use the dedicated reminders page for full reminder history, retry details, and actions.</p>
        </SectionCard>

        <SectionCard eyebrow="Recurring Reminders" title="Repeat rules and future occurrences" description="Keep this section compact and use the dedicated recurring reminders page for full management." actions={[<Link key="recurring-link" to="/recurring-reminders" className="rounded-xl border border-slate-200 px-4 py-2 text-sm font-semibold text-slate-700 transition hover:bg-slate-50">View recurring reminders</Link>]} compact>
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            <MetricCard label="Active rules" value={recurringRules.filter((rule) => rule.status === "active").length} />
            <MetricCard label="Paused rules" value={recurringRules.filter((rule) => rule.status === "paused").length} />
            <MetricCard label="Next occurrence" value={formatDateTime(recurringRules[0]?.next_occurrence_at)} />
            <MetricCard
              label="Latest summary"
              value={recurringRules[0]?.title || "None"}
              truncateValue
              hint={recurringRules[0] ? describeRecurringRule(recurringRules[0]) : "No recurring reminders yet."}
            />
          </div>
          <p className="text-sm text-slate-500">Use the dedicated recurring reminders page for full repeat-rule history and actions.</p>
        </SectionCard>

        <SectionCard eyebrow="Missed / Retry Reminders" title="Recovery queue" description="These reminders are scheduled, missed, retrying, or need follow-up." compact>
          <div className="grid gap-3 sm:grid-cols-2">
            <MetricCard label="Recovery items" value={reminders.filter((reminder) => recoveryStatuses.has(reminder.status)).length} />
            <MetricCard label="Next retry" value={formatDateTime(reminders.filter((reminder) => recoveryStatuses.has(reminder.status))[0]?.next_retry_at)} hint="Detailed retry history lives on the reminders page." />
          </div>
          <div className="flex justify-end">
            <Link to="/reminders" className="rounded-xl border border-slate-200 px-4 py-2 text-sm font-semibold text-slate-700 transition hover:bg-slate-50">
              View all reminders
            </Link>
          </div>
        </SectionCard>

        <SectionCard eyebrow="Recent Activity" title="Latest meaningful events" description="A compact feed of the most recent dashboard-relevant changes across Gmail, summaries, voice calls, and reminders." compact>
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

        <SectionCard eyebrow="System Status" title="Service health and operational notes" description="A quick operational view that helps confirm the app is healthy and ready for live use." compact>
          <div className="grid gap-3 md:grid-cols-2">
            <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
              <p className="text-sm text-slate-400">Backend health</p>
              <p className="mt-2 text-lg font-semibold text-slate-900">See sidebar status</p>
              <p className="mt-1 text-xs text-slate-400">The layout checks /health automatically on load.</p>
            </div>
            <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
              <p className="text-sm text-slate-400">Reminder quota note</p>
              <p className="mt-2 text-lg font-semibold text-slate-900">3 mail-summary calls per day</p>
              <p className="mt-1 text-xs text-slate-400">Reminder calls are tracked separately and do not reduce this quota.</p>
            </div>
          </div>
        </SectionCard>

        <SectionCard eyebrow="Recent Replies" title="Latest email reply actions" description="This section stays compact so the dashboard focuses on the highest-value operational data." compact>
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

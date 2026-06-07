import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import PageShell from "../components/PageShell";
import { useAuth } from "../context/AuthContext";
import { emailApi, emailReplyApi, gmailApi, mailCallApi, reminderApi, summaryApi } from "../lib/api";

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
        <div>
          <p className="text-xs uppercase tracking-[0.28em] text-slate-500">{eyebrow}</p>
          <h2 className="mt-2 text-2xl font-semibold text-slate-900">{title}</h2>
          {description ? <p className="mt-2 max-w-3xl text-sm text-slate-400">{description}</p> : null}
        </div>
        {actions ? <div className="flex flex-wrap gap-2">{actions}</div> : null}
      </div>
      <div className={compact ? "space-y-4" : "space-y-5"}>{children}</div>
    </section>
  );
}

function StatusBadge({ children, tone = "neutral" }) {
  return (
    <span className={`inline-flex rounded-full border px-3 py-1 text-xs font-medium ${STATUS_STYLES[tone] || STATUS_STYLES.neutral}`}>
      {children}
    </span>
  );
}

function MetricCard({ label, value, hint, tone = "neutral" }) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
      <p className="text-sm text-slate-400">{label}</p>
      <div className="mt-2 flex items-center gap-2">
        <h3 className="text-xl font-semibold text-slate-900">{value}</h3>
        {tone ? <StatusBadge tone={tone}>{tone === "success" ? "OK" : tone === "warning" ? "Needs attention" : tone === "danger" ? "Issue" : "Info"}</StatusBadge> : null}
      </div>
      {hint ? <p className="mt-2 text-xs text-slate-400">{hint}</p> : null}
    </div>
  );
}

function formatDateTime(value) {
  if (!value) return "—";
  try {
    return new Date(value).toLocaleString();
  } catch {
    return "—";
  }
}

function getReminderTone(reminder) {
  if (["completed"].includes(reminder.status)) return "success";
  if (["retry_scheduled", "missed", "failed", "snoozed"].includes(reminder.status)) return "warning";
  if (["cancelled"].includes(reminder.status)) return "neutral";
  if (["calling"].includes(reminder.status)) return "warning";
  return "neutral";
}

function ReminderActionButton({ onClick, children, tone = "neutral", disabled = false }) {
  const classes = {
    success: "border-emerald-400/30 text-slate-700 hover:bg-slate-50",
    warning: "border-slate-200 text-slate-700 hover:bg-slate-50",
    danger: "border-red-400/30 text-slate-700 hover:bg-slate-50",
    neutral: "border-slate-200 text-slate-700 hover:bg-slate-50",
  };
  return (
    <button
      type="button"
      disabled={disabled}
      onClick={onClick}
      className={`rounded-xl border px-3 py-2 text-sm transition disabled:cursor-not-allowed disabled:opacity-60 ${classes[tone] || classes.neutral}`}
    >
      {children}
    </button>
  );
}

export default function DashboardPage() {
  const { user } = useAuth();
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState({
    sync: false,
    summarize: false,
    prepareCall: false,
  });
  const [syncStatus, setSyncStatus] = useState({
    last_sync_time: null,
    total_emails_stored: 0,
    gmail_connected: false,
  });
  const [gmailStatus, setGmailStatus] = useState({
    is_connected: false,
    gmail_email: null,
    connected_at: null,
    can_send_replies: false,
  });
  const [summaryStats, setSummaryStats] = useState({
    total: 0,
    unsummarized: 0,
    today: 0,
  });
  const [mailCallStats, setMailCallStats] = useState({
    used: 0,
    remaining: 3,
    pending: 0,
    lastCall: null,
    todaySummaries: 0,
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
  const [recentReplies, setRecentReplies] = useState([]);
  const [recentActivity, setRecentActivity] = useState([]);
  const [reminderForm, setReminderForm] = useState({
    title: "",
    notes: "",
    reminder_date: "",
    reminder_time: "",
    timezone: Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC",
    phone_number: "",
  });
  const [reminderMessage, setReminderMessage] = useState("");
  const [reminderError, setReminderError] = useState("");

  const recoveryStatuses = useMemo(() => new Set(["retry_scheduled", "missed", "snoozed", "failed"]), []);

  const loadDashboard = async () => {
    setLoading(true);
    try {
      const [sync, gmail, autoSync, summaries, todaySummaries, emails, counts, pending, history, remindersData, repliesData] =
        await Promise.all([
          emailApi.getSyncStatus(),
          gmailApi.getStatus().catch(() => ({
            is_connected: false,
            gmail_email: null,
            connected_at: null,
            can_send_replies: false,
          })),
          emailApi.getAutoSyncStatus(),
          summaryApi.getAllSummaries(),
          summaryApi.getTodaySummaries(),
          emailApi.getAllEmails(),
          mailCallApi.getCountToday(),
          mailCallApi.getPendingSummaries(),
          mailCallApi.getHistory(),
          reminderApi.listReminders(true),
          emailReplyApi.list(),
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
      setRecentReplies(repliesData.value || []);
      setRecentActivity(buildRecentActivity({
        sync,
        autoSync,
        mailCallHistory: history,
        reminders: remindersData.value || [],
        recentReplies: repliesData.value || [],
        todaySummaryCount: todaySummaries.length,
      }));
    } catch {
      // Keep the dashboard usable even if one section fails.
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadDashboard();
  }, []);

  const loadReminders = async () => {
    const data = await reminderApi.listReminders(true);
    setReminders(data.value || []);
    setRecentActivity((current) =>
      buildRecentActivity({
        sync: syncStatus,
        autoSync: autoSyncStatus,
        mailCallHistory: mailCallStats.lastCall ? [mailCallStats.lastCall] : [],
        reminders: data.value || [],
        recentReplies,
        todaySummaryCount: mailCallStats.todaySummaries,
      })
    );
  };

  const refreshSummaryStats = async () => {
    const [summaries, todaySummaries, emails] = await Promise.all([
      summaryApi.getAllSummaries(),
      summaryApi.getTodaySummaries(),
      emailApi.getAllEmails(),
    ]);
    setSummaryStats({
      total: summaries.length,
      unsummarized: emails.filter((email) => !email.is_summarized).length,
      today: todaySummaries.length,
    });
  };

  const refreshMailCalls = async () => {
    const [countData, pendingData, historyData] = await Promise.all([
      mailCallApi.getCountToday(),
      mailCallApi.getPendingSummaries(),
      mailCallApi.getHistory(),
    ]);
    setMailCallStats((current) => ({
      ...current,
      used: countData.used_calls_today,
      remaining: countData.remaining_calls_today,
      pending: pendingData.pending_count,
      lastCall: historyData[0] || null,
      todaySummaries: current.todaySummaries,
    }));
  };

  const runAction = async (key, action) => {
    setActionLoading((current) => ({ ...current, [key]: true }));
    setReminderError("");
    try {
      await action();
      await loadDashboard();
    } catch (err) {
      setReminderError(err.message || "Something went wrong.");
    } finally {
      setActionLoading((current) => ({ ...current, [key]: false }));
    }
  };

  const handleReminderSubmit = async (event) => {
    event.preventDefault();
    setReminderMessage("");
    setReminderError("");
    try {
      await reminderApi.createReminder({
        title: reminderForm.title,
        notes: reminderForm.notes,
        reminder_date: reminderForm.reminder_date,
        reminder_time: reminderForm.reminder_time,
        timezone: reminderForm.timezone,
        phone_number: reminderForm.phone_number || undefined,
      });
      setReminderMessage("Reminder created successfully.");
      setReminderForm((current) => ({ ...current, title: "", notes: "" }));
      await loadReminders();
      await refreshMailCalls();
    } catch (err) {
      setReminderError(err.message || "Could not create reminder.");
    }
  };

  const handleCancelReminder = async (reminderId) => {
    await runAction(`reminder-${reminderId}-cancel`, async () => {
      await reminderApi.cancelReminder(reminderId);
      await loadReminders();
    });
  };

  const handleCallAgain = async (reminderId) => {
    await runAction(`reminder-${reminderId}-call-again`, async () => {
      await reminderApi.callAgain(reminderId);
      await loadReminders();
    });
  };

  const handleSnooze = async (reminderId) => {
    await runAction(`reminder-${reminderId}-snooze`, async () => {
      await reminderApi.snooze(reminderId, 10);
      await loadReminders();
    });
  };

  const handleMarkDone = async (reminderId) => {
    await runAction(`reminder-${reminderId}-done`, async () => {
      await reminderApi.markDone(reminderId);
      await loadReminders();
    });
  };

  const handleSyncNow = async () => {
    await runAction("sync", async () => {
      await emailApi.syncEmails({ max_results: 20, max_pages: 1 });
      await refreshSummaryStats();
      await refreshMailCalls();
    });
  };

  const handleGenerateTodaySummaries = async () => {
    await runAction("summarize", async () => {
      await summaryApi.generateAll();
      await refreshSummaryStats();
      await refreshMailCalls();
    });
  };

  const handlePrepareCall = async () => {
    await runAction("prepareCall", async () => {
      await mailCallApi.prepare();
      await refreshMailCalls();
      await loadDashboard();
    });
  };

  return (
    <PageShell
      title="Dashboard"
      description="A clean command center for Gmail status, summaries, voice mail calls, reminders, and recent activity."
    >
      <div className="grid gap-4 xl:grid-cols-[1.3fr_0.7fr]">
        <div className="rounded-3xl border border-sky-400/20 bg-slate-50 p-5 text-sky-50">
          <p className="text-xs uppercase tracking-[0.32em] text-slate-600">Signed in</p>
          <h3 className="mt-2 text-2xl font-semibold text-slate-900">{user?.name || user?.email || "User"}</h3>
          <p className="mt-2 max-w-3xl text-sm text-slate-700/90">
            This dashboard keeps Gmail, summaries, mail-summary calls, and reminders visible in one place so you can monitor the whole workflow at a glance.
          </p>
          <div className="mt-4 flex flex-wrap gap-2">
            <StatusBadge tone={gmailStatus.is_connected ? "success" : "warning"}>
              {gmailStatus.is_connected ? "Gmail connected" : "Gmail disconnected"}
            </StatusBadge>
            <StatusBadge tone={autoSyncStatus.auto_sync_enabled ? "success" : "warning"}>
              Auto sync {autoSyncStatus.auto_sync_enabled ? "on" : "off"}
            </StatusBadge>
            <StatusBadge tone={autoSyncStatus.auto_summarize_after_sync ? "success" : "warning"}>
              Auto summary {autoSyncStatus.auto_summarize_after_sync ? "on" : "off"}
            </StatusBadge>
          </div>
        </div>
        <div className="rounded-3xl border border-slate-200 bg-white p-5">
          <p className="text-sm text-slate-400">Quick links</p>
          <div className="mt-3 grid gap-2 sm:grid-cols-2 xl:grid-cols-1">
            <Link to="/inbox" className="rounded-xl border border-slate-200 px-4 py-3 text-sm font-medium text-slate-700 transition hover:bg-slate-50">
              Open Email Inbox
            </Link>
            <Link to="/summaries" className="rounded-xl border border-slate-200 px-4 py-3 text-sm font-medium text-slate-700 transition hover:bg-slate-50">
              Open Email Summaries
            </Link>
            <Link to="/mail-calls" className="rounded-xl border border-slate-200 px-4 py-3 text-sm font-medium text-slate-700 transition hover:bg-slate-50">
              Open Mail Summary Calls
            </Link>
            <Link to="/settings" className="rounded-xl border border-slate-200 px-4 py-3 text-sm font-medium text-slate-700 transition hover:bg-slate-50">
              Open Settings / Profile
            </Link>
          </div>
        </div>
      </div>

      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <MetricCard label="Gmail connection" value={gmailStatus.is_connected ? "Connected" : "Disconnected"} tone={gmailStatus.is_connected ? "success" : "warning"} hint={gmailStatus.gmail_email || "No Gmail account connected yet."} />
        <MetricCard label="Emails stored" value={syncStatus.total_emails_stored} tone="neutral" hint={syncStatus.last_sync_time ? `Last sync: ${formatDateTime(syncStatus.last_sync_time)}` : "Not synced yet."} />
        <MetricCard label="Summaries today" value={summaryStats.today} tone="neutral" hint={`Unsummarized: ${autoSyncStatus.unsummarized_email_count ?? summaryStats.unsummarized}`} />
        <MetricCard label="Mail-summary calls today" value={`${mailCallStats.used}/${mailCallStats.remaining + mailCallStats.used}`} tone={mailCallStats.remaining > 0 ? "success" : "warning"} hint="Reminder calls do not affect this quota." />
      </section>

      <div className="grid gap-4 xl:grid-cols-2">
        <SectionCard
          eyebrow="Gmail Connection"
          title="Connection and sync status"
          description="Keep the Gmail connection healthy and visible. Use the buttons below to reconnect or sync on demand."
          actions={[
            <button
              key="sync"
              type="button"
              disabled={actionLoading.sync}
              onClick={handleSyncNow}
              className="rounded-xl bg-slate-900 px-4 py-2 text-sm font-semibold text-white transition hover:bg-sky-300 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {actionLoading.sync ? "Syncing..." : "Sync now"}
            </button>,
            <Link
              key="settings"
              to="/settings"
              className="rounded-xl border border-slate-200 px-4 py-2 text-sm font-semibold text-slate-700 transition hover:bg-slate-50"
            >
              Manage Gmail
            </Link>,
          ]}
        >
          <div className="grid gap-3 sm:grid-cols-2">
            <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
              <p className="text-sm text-slate-400">Connection</p>
              <p className="mt-2 text-lg font-semibold text-slate-900">{gmailStatus.is_connected ? "Connected" : "Disconnected"}</p>
              <p className="mt-1 text-xs text-slate-400">{gmailStatus.gmail_email || "Connect Gmail from Settings to enable reading and voice features."}</p>
            </div>
            <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
              <p className="text-sm text-slate-400">Last sync</p>
              <p className="mt-2 text-lg font-semibold text-slate-900">{formatDateTime(syncStatus.last_sync_time)}</p>
              <p className="mt-1 text-xs text-slate-400">Stored emails: {syncStatus.total_emails_stored}</p>
            </div>
          </div>
          <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4 text-sm text-slate-600">
            {gmailStatus.is_connected && !gmailStatus.can_send_replies ? (
              <p className="text-slate-700">Gmail is connected, but reply permission is missing. Reconnect Gmail if you want voice replies enabled.</p>
            ) : (
              <p>Gmail is ready for inbox sync, summaries, and voice workflows.</p>
            )}
          </div>
        </SectionCard>

        <SectionCard
          eyebrow="Today’s Email Summary"
          title="Summary readiness and automation"
          description="See what has already been summarized today and whether auto-sync or auto-summary is active."
          actions={[
            <button
              key="summarize"
              type="button"
              disabled={actionLoading.summarize}
              onClick={handleGenerateTodaySummaries}
              className="rounded-xl bg-white px-4 py-2 text-sm font-semibold text-slate-900 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {actionLoading.summarize ? "Generating..." : "Generate today’s summaries"}
            </button>,
          ]}
        >
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
              <p className="mt-1 text-xs text-slate-400">Status: {autoSyncStatus.last_auto_sync_status || "—"}</p>
            </div>
            <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
              <p className="text-sm text-slate-400">Last auto summary</p>
              <p className="mt-2 text-lg font-semibold text-slate-900">{formatDateTime(autoSyncStatus.last_auto_summary_at)}</p>
              <p className="mt-1 text-xs text-slate-400">Success: {autoSyncStatus.last_auto_summary_success_count} | Failed: {autoSyncStatus.last_auto_summary_failed_count}</p>
            </div>
          </div>
          <div className={`rounded-2xl border p-4 text-sm ${STATUS_STYLES[autoSyncStatus.last_auto_sync_error || autoSyncStatus.last_auto_summary_error ? "warning" : "neutral"]}`}>
            <p>Last auto sync error: {autoSyncStatus.last_auto_sync_error || "None"}</p>
            <p>Last auto summary error: {autoSyncStatus.last_auto_summary_error || "None"}</p>
          </div>
        </SectionCard>

        <SectionCard
          eyebrow="Voice Mail Calls"
          title="Call quota, pending delivery, and latest call status"
          description="Track the daily mail-summary call budget and the latest delivery result before starting a call."
          actions={[
            <button
              key="prepare"
              type="button"
              disabled={actionLoading.prepareCall}
              onClick={handlePrepareCall}
              className="rounded-xl bg-slate-900 px-4 py-2 text-sm font-semibold text-white transition hover:bg-sky-300 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {actionLoading.prepareCall ? "Preparing..." : "Prepare mail summary call"}
            </button>,
            <Link
              key="calls"
              to="/mail-calls"
              className="rounded-xl border border-slate-200 px-4 py-2 text-sm font-semibold text-slate-700 transition hover:bg-slate-50"
            >
              Open calls page
            </Link>,
          ]}
        >
          <div className="grid gap-3 md:grid-cols-3">
            <MetricCard
              label="Used today"
              value={mailCallStats.used}
              tone="neutral"
              hint={`Remaining today: ${mailCallStats.remaining}`}
            />
            <MetricCard
              label="Pending summaries"
              value={mailCallStats.pending}
              tone={mailCallStats.pending > 0 ? "success" : "warning"}
              hint="These are ready for mail summary delivery."
            />
            <MetricCard
              label="Today’s summaries"
              value={mailCallStats.todaySummaries || summaryStats.today}
              tone="neutral"
              hint="Prepared from today’s Gmail messages."
            />
          </div>
          <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
            <p className="text-sm text-slate-400">Latest delivery result</p>
            <p className="mt-2 text-lg font-semibold text-slate-900">
              {mailCallStats.lastCall
                ? `${mailCallStats.lastCall.call_status} / ${mailCallStats.lastCall.delivery_status}${mailCallStats.lastCall.provider_status ? ` / ${mailCallStats.lastCall.provider_status}` : ""}`
                : "No voice delivery yet"}
            </p>
            <p className="mt-1 text-xs text-slate-400">
              {mailCallStats.lastCall?.updated_at ? `Updated: ${formatDateTime(mailCallStats.lastCall.updated_at)}` : "Start a call to see provider updates here."}
            </p>
          </div>
        </SectionCard>

        <SectionCard
          eyebrow="Reminders"
          title="Scheduled reminder management"
          description="Create reminders and manage follow-up actions directly from the dashboard."
          compact
        >
          <form onSubmit={handleReminderSubmit} className="grid gap-4 md:grid-cols-2">
            <input
              className="rounded-xl border border-slate-200 bg-white px-4 py-3 text-slate-900 outline-none transition placeholder:text-slate-400 focus:border-slate-300"
              placeholder="Reminder title"
              value={reminderForm.title}
              onChange={(e) => setReminderForm({ ...reminderForm, title: e.target.value })}
              required
            />
            <input
              className="rounded-xl border border-slate-200 bg-white px-4 py-3 text-slate-900 outline-none transition placeholder:text-slate-400 focus:border-slate-300"
              placeholder="Phone number (optional)"
              value={reminderForm.phone_number}
              onChange={(e) => setReminderForm({ ...reminderForm, phone_number: e.target.value })}
            />
            <textarea
              className="rounded-xl border border-slate-200 bg-white px-4 py-3 text-slate-900 outline-none transition placeholder:text-slate-400 focus:border-slate-300 md:col-span-2"
              placeholder="Notes"
              rows="3"
              value={reminderForm.notes}
              onChange={(e) => setReminderForm({ ...reminderForm, notes: e.target.value })}
            />
            <input
              type="date"
              className="rounded-xl border border-slate-200 bg-white px-4 py-3 text-slate-900 outline-none transition focus:border-slate-300"
              value={reminderForm.reminder_date}
              onChange={(e) => setReminderForm({ ...reminderForm, reminder_date: e.target.value })}
              required
            />
            <input
              type="time"
              className="rounded-xl border border-slate-200 bg-white px-4 py-3 text-slate-900 outline-none transition focus:border-slate-300"
              value={reminderForm.reminder_time}
              onChange={(e) => setReminderForm({ ...reminderForm, reminder_time: e.target.value })}
              required
            />
            <input
              className="rounded-xl border border-slate-200 bg-white px-4 py-3 text-slate-900 outline-none transition placeholder:text-slate-400 focus:border-slate-300 md:col-span-2"
              placeholder="Timezone"
              value={reminderForm.timezone}
              onChange={(e) => setReminderForm({ ...reminderForm, timezone: e.target.value })}
            />
            <button type="submit" className="rounded-xl bg-slate-900 px-4 py-3 font-semibold text-white transition hover:bg-sky-300 md:col-span-2">
              Create reminder
            </button>
          </form>

          {reminderMessage ? <div className="rounded-xl border border-slate-200 bg-slate-50 p-3 text-slate-700">{reminderMessage}</div> : null}
          {reminderError ? <div className="rounded-xl border border-slate-200 bg-slate-50 p-3 text-slate-700">{reminderError}</div> : null}

          <div className="space-y-3">
            {reminders.length === 0 ? (
              <p className="text-sm text-slate-400">No reminders scheduled yet.</p>
            ) : (
              reminders.slice(0, 8).map((reminder) => (
                <div key={reminder.id} className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                  <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                    <div className="space-y-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <h3 className="text-lg font-semibold text-slate-900">{reminder.title}</h3>
                        <StatusBadge tone={getReminderTone(reminder)}>{reminder.status}</StatusBadge>
                      </div>
                      <p className="text-sm text-slate-600">{reminder.notes || "No notes provided."}</p>
                      <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-slate-400">
                        <span>Due: {formatDateTime(reminder.reminder_at)}</span>
                        <span>Retry: {reminder.retry_count || 0}/{reminder.max_retry_attempts || 3}</span>
                        {reminder.next_retry_at ? <span>Next retry: {formatDateTime(reminder.next_retry_at)}</span> : null}
                        {reminder.snoozed_until ? <span>Snoozed until: {formatDateTime(reminder.snoozed_until)}</span> : null}
                        {reminder.last_call_status ? <span>Last call: {reminder.last_call_status}</span> : null}
                      </div>
                      {reminder.status === "missed" ? <p className="text-xs text-slate-600">You missed this reminder. A retry may be scheduled.</p> : null}
                    </div>
                    <div className="flex flex-wrap gap-2">
                      {(reminder.status === "scheduled" || reminder.status === "retry_scheduled" || reminder.status === "snoozed" || reminder.status === "failed" || reminder.status === "missed") ? (
                        <ReminderActionButton disabled={actionLoading[`reminder-${reminder.id}-call-again`]} onClick={() => handleCallAgain(reminder.id)} tone="neutral">
                          Call again
                        </ReminderActionButton>
                      ) : null}
                      {recoveryStatuses.has(reminder.status) ? (
                        <ReminderActionButton disabled={actionLoading[`reminder-${reminder.id}-snooze`]} onClick={() => handleSnooze(reminder.id)} tone="warning">
                          Snooze 10 minutes
                        </ReminderActionButton>
                      ) : null}
                      {(recoveryStatuses.has(reminder.status) || reminder.status === "calling" || reminder.status === "scheduled") ? (
                        <ReminderActionButton disabled={actionLoading[`reminder-${reminder.id}-done`]} onClick={() => handleMarkDone(reminder.id)} tone="success">
                          Mark done
                        </ReminderActionButton>
                      ) : null}
                      {reminder.status !== "completed" ? (
                        <ReminderActionButton disabled={actionLoading[`reminder-${reminder.id}-cancel`]} onClick={() => handleCancelReminder(reminder.id)} tone="danger">
                          Cancel
                        </ReminderActionButton>
                      ) : null}
                    </div>
                  </div>
                </div>
              ))
            )}
          </div>
        </SectionCard>

        <SectionCard
          eyebrow="Missed / Retry Reminders"
          title="Recovery queue"
          description="These reminders are scheduled, missed, retrying, or need follow-up."
          compact
        >
          <div className="space-y-3">
            {reminders.filter((reminder) => recoveryStatuses.has(reminder.status)).length === 0 ? (
              <p className="text-sm text-slate-400">No missed or retrying reminders right now.</p>
            ) : (
              reminders
                .filter((reminder) => recoveryStatuses.has(reminder.status))
                .slice(0, 6)
                .map((reminder) => (
                  <div key={`recovery-${reminder.id}`} className="rounded-2xl border border-amber-400/20 bg-amber-500/5 p-4">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <div>
                        <p className="text-sm font-semibold text-slate-900">{reminder.title}</p>
                        <p className="text-xs text-slate-400">{reminder.notes || "No notes provided."}</p>
                      </div>
                      <StatusBadge tone="warning">{reminder.status}</StatusBadge>
                    </div>
                    <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-xs text-slate-400">
                      <span>Retry count: {reminder.retry_count || 0}</span>
                      {reminder.next_retry_at ? <span>Next retry: {formatDateTime(reminder.next_retry_at)}</span> : null}
                      {reminder.last_call_status ? <span>Last call: {reminder.last_call_status}</span> : null}
                    </div>
                  </div>
                ))
            )}
          </div>
        </SectionCard>

        <SectionCard
          eyebrow="Recent Activity"
          title="Latest meaningful events"
          description="A compact feed of the most recent dashboard-relevant changes across Gmail, summaries, voice calls, and reminders."
          compact
        >
          <div className="space-y-3">
            {recentActivity.length === 0 ? (
              <p className="text-sm text-slate-400">No recent activity yet.</p>
            ) : (
              recentActivity.map((item, index) => (
                <div key={`${item.label}-${index}`} className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                  <div className="flex flex-col gap-1 sm:flex-row sm:items-start sm:justify-between">
                    <div>
                      <p className="text-sm font-semibold text-slate-900">{item.label}</p>
                      <p className="text-xs text-slate-400">{item.detail}</p>
                    </div>
                    <p className="text-xs text-slate-400">{formatDateTime(item.at)}</p>
                  </div>
                </div>
              ))
            )}
          </div>
        </SectionCard>

        <SectionCard
          eyebrow="System Status"
          title="Service health and operational notes"
          description="A quick operational view that helps confirm the app is healthy and ready for live use."
          compact
        >
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
            <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
              <p className="text-sm text-slate-400">Auto sync error</p>
              <p className="mt-2 text-sm text-slate-900">{autoSyncStatus.last_auto_sync_error || "None"}</p>
            </div>
            <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
              <p className="text-sm text-slate-400">Auto summary error</p>
              <p className="mt-2 text-sm text-slate-900">{autoSyncStatus.last_auto_summary_error || "None"}</p>
            </div>
          </div>
        </SectionCard>

        <SectionCard
          eyebrow="Recent Replies"
          title="Latest email reply actions"
          description="This section stays compact so the dashboard focuses on the highest-value operational data."
          compact
        >
          <div className="space-y-3">
            {recentReplies.length === 0 ? (
              <p className="text-sm text-slate-400">No email replies yet.</p>
            ) : (
              recentReplies.slice(0, 5).map((reply) => (
                <div key={reply.id} className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                  <p className="text-sm font-semibold text-slate-900">{reply.subject || "Reply"}</p>
                  <div className="mt-1 flex flex-wrap gap-x-4 gap-y-1 text-xs text-slate-400">
                    <span>Status: {reply.status}</span>
                    {reply.sent_at ? <span>Sent: {formatDateTime(reply.sent_at)}</span> : null}
                    {reply.error_message ? <span className="text-red-300">{reply.error_message}</span> : null}
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


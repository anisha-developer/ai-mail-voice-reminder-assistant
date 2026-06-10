import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import PageShell from "../components/PageShell";
import { apiRequest, callPreferencesApi } from "../lib/api";
import { useAuth } from "../context/AuthContext";

export default function SettingsPage() {
  const [searchParams] = useSearchParams();
  const { user, setUser } = useAuth();
  const [form, setForm] = useState({
    name: "",
    phone_number: "",
    timezone: "",
    preferred_language: "",
  });
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [gmailStatus, setGmailStatus] = useState({ is_connected: false, gmail_email: null, connected_at: null, can_send_replies: false });
  const [gmailMessage, setGmailMessage] = useState("");
  const [gmailError, setGmailError] = useState("");
  const [gmailLoading, setGmailLoading] = useState(false);
  const [callPrefs, setCallPrefs] = useState({
    timezone: "Asia/Kolkata",
    call_slot_1_time: "09:00",
    call_slot_1_enabled: true,
    call_slot_2_time: "13:00",
    call_slot_2_enabled: true,
    call_slot_3_time: "19:00",
    call_slot_3_enabled: true,
    minimum_new_emails_to_call: 1,
    skip_if_no_new_emails: true,
    avoid_repeating_delivered_emails: true,
    next_scheduled_summary_call_at: null,
    next_scheduled_summary_call_status: null,
    pending_new_email_summaries: 0,
    would_call_next_slot: false,
    next_slot_label: null,
    next_slot_time: null,
  });
  const [callPrefsMessage, setCallPrefsMessage] = useState("");
  const [callPrefsError, setCallPrefsError] = useState("");
  const [callPrefsLoading, setCallPrefsLoading] = useState(false);

  useEffect(() => {
    const loadProfile = async () => {
      try {
        const profile = await apiRequest("/users/me");
        setForm({
          name: profile.name || "",
          phone_number: profile.phone_number || "",
          timezone: profile.timezone || "",
          preferred_language: profile.preferred_language || "",
        });
        setUser(profile);
      } catch (err) {
        setError(err.message);
      }
    };

    loadProfile();
  }, [setUser]);

  useEffect(() => {
    if (searchParams.get("gmail") === "connected") {
      setGmailMessage("Gmail connected successfully.");
    } else if (searchParams.get("gmail") === "error") {
      setGmailError(searchParams.get("message") || "Gmail connection failed.");
    }
  }, [searchParams]);

  useEffect(() => {
    const loadGmailStatus = async () => {
      try {
        const status = await apiRequest("/gmail/status");
        setGmailStatus(status);
      } catch (err) {
        setGmailError(err.message);
      }
    };

    loadGmailStatus();
  }, []);

  useEffect(() => {
    const loadCallPreferences = async () => {
      try {
        const prefs = await callPreferencesApi.get();
        setCallPrefs(prefs);
      } catch (err) {
        setCallPrefsError(err.message);
      }
    };

    loadCallPreferences();
  }, []);

  const handleSubmit = async (event) => {
    event.preventDefault();
    setMessage("");
    setError("");
    try {
      const updated = await apiRequest("/users/me", {
        method: "PUT",
        body: JSON.stringify(form),
      });
      setUser(updated);
      setMessage("Profile updated successfully.");
    } catch (err) {
      setError(err.message);
    }
  };

  const handleConnectGmail = async () => {
    setGmailLoading(true);
    setGmailError("");
    setGmailMessage("");
    try {
      const data = await apiRequest("/gmail/connect");
      window.location.href = data.authorization_url;
    } catch (err) {
      setGmailError(err.message);
      setGmailLoading(false);
    }
  };

  const handleDisconnectGmail = async () => {
    setGmailLoading(true);
    setGmailError("");
    setGmailMessage("");
    try {
      const data = await apiRequest("/gmail/disconnect", { method: "DELETE" });
      setGmailMessage(data.message);
      setGmailStatus({ is_connected: false, gmail_email: null, connected_at: null, can_send_replies: false });
    } catch (err) {
      setGmailError(err.message);
    } finally {
      setGmailLoading(false);
    }
  };

  const refreshGmailStatus = async () => {
    try {
      const status = await apiRequest("/gmail/status");
      setGmailStatus(status);
    } catch (err) {
      setGmailError(err.message);
    }
  };

  const handleSaveCallPreferences = async (event) => {
    event.preventDefault();
    setCallPrefsMessage("");
    setCallPrefsError("");
    setCallPrefsLoading(true);
    try {
      const updated = await callPreferencesApi.update({
        timezone: callPrefs.timezone,
        call_slot_1_time: callPrefs.call_slot_1_time,
        call_slot_1_enabled: callPrefs.call_slot_1_enabled,
        call_slot_2_time: callPrefs.call_slot_2_time,
        call_slot_2_enabled: callPrefs.call_slot_2_enabled,
        call_slot_3_time: callPrefs.call_slot_3_time,
        call_slot_3_enabled: callPrefs.call_slot_3_enabled,
        minimum_new_emails_to_call: Number(callPrefs.minimum_new_emails_to_call),
        skip_if_no_new_emails: callPrefs.skip_if_no_new_emails,
        avoid_repeating_delivered_emails: callPrefs.avoid_repeating_delivered_emails,
      });
      setCallPrefs(updated);
      setCallPrefsMessage("Call preferences saved successfully.");
    } catch (err) {
      setCallPrefsError(err.message);
    } finally {
      setCallPrefsLoading(false);
    }
  };

  return (
    <PageShell
      title="Settings"
      description="Update your profile details and profile defaults."
    >
      <form className="grid gap-4 md:grid-cols-2" onSubmit={handleSubmit}>
        <div className="md:col-span-2 rounded-2xl border border-slate-200 bg-slate-50 p-5 text-slate-600">
          Signed in as <span className="font-medium text-slate-900">{user?.email}</span>
        </div>
        {[
          ["name", "Full name"],
          ["phone_number", "Phone number"],
          ["timezone", "Timezone"],
          ["preferred_language", "Preferred language"],
        ].map(([key, label]) => (
          <input
            key={key}
            value={form[key]}
            onChange={(e) => setForm({ ...form, [key]: e.target.value })}
            placeholder={label}
            className="rounded-xl border border-slate-300 bg-white px-4 py-3 text-slate-900 outline-none placeholder:text-slate-400 focus:border-slate-900"
          />
        ))}
        <div className="md:col-span-2 space-y-3">
          {message ? <p className="rounded-xl border border-slate-200 bg-slate-50 p-3 text-sm text-slate-700">{message}</p> : null}
          {error ? <p className="rounded-xl border border-slate-200 bg-slate-50 p-3 text-sm text-slate-700">{error}</p> : null}
          <button className="rounded-xl bg-slate-900 px-4 py-3 font-semibold text-white">Save changes</button>
        </div>
      </form>

      <section className="mt-8 rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <p className="text-xs uppercase tracking-[0.3em] text-slate-500">Gmail Connection</p>
            <h3 className="mt-2 text-xl font-semibold text-slate-900">
              {gmailStatus.is_connected ? "Connected" : "Disconnected"}
            </h3>
            <p className="mt-1 text-sm text-slate-600">
              {gmailStatus.gmail_email ? `Connected Gmail: ${gmailStatus.gmail_email}` : "No Gmail account connected yet."}
            </p>
            {gmailStatus.connected_at ? (
              <p className="mt-1 text-xs text-slate-500">Connected at {new Date(gmailStatus.connected_at).toLocaleString()}</p>
            ) : null}
            {gmailStatus.is_connected && !gmailStatus.can_send_replies ? (
              <p className="mt-2 rounded-xl border border-slate-200 bg-slate-50 p-3 text-sm text-slate-700">
                Gmail is connected, but send permission is missing. Reconnect Gmail to enable voice replies.
              </p>
            ) : null}
          </div>
          <div className="flex gap-3">
            {gmailStatus.is_connected ? (
              <button
                type="button"
                onClick={handleDisconnectGmail}
                disabled={gmailLoading}
                className="rounded-xl border border-slate-300 bg-white px-4 py-3 text-sm font-semibold text-slate-700 disabled:opacity-60"
              >
                Disconnect Gmail
              </button>
            ) : (
              <button
                type="button"
                onClick={handleConnectGmail}
                disabled={gmailLoading}
                className="rounded-xl bg-slate-900 px-4 py-3 text-sm font-semibold text-white disabled:opacity-60"
              >
                Connect Gmail
              </button>
            )}
            <button
              type="button"
              onClick={refreshGmailStatus}
              className="rounded-xl border border-slate-300 bg-white px-4 py-3 text-sm font-semibold text-slate-700"
            >
              Refresh Status
            </button>
          </div>
        </div>
        <div className="mt-4 space-y-3">
          {gmailMessage ? <p className="rounded-xl border border-slate-200 bg-slate-50 p-3 text-sm text-slate-700">{gmailMessage}</p> : null}
          {gmailError ? <p className="rounded-xl border border-slate-200 bg-slate-50 p-3 text-sm text-slate-700">{gmailError}</p> : null}
        </div>
      </section>

      <section className="mt-8 rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
        <div className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <p className="text-xs uppercase tracking-[0.3em] text-slate-500">Call Preferences</p>
            <h3 className="mt-2 text-xl font-semibold text-slate-900">Daily Email Summary Call Schedule</h3>
            <p className="mt-1 text-sm text-slate-600">
              Email summary calls only happen at these times if there are new pending emails. Reminder calls do not affect this limit.
            </p>
          </div>
          <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-700">
            <p>Next call: {callPrefs.next_slot_time ? `${callPrefs.next_slot_time} (${callPrefs.next_slot_label || "slot"})` : "No enabled slots"}</p>
            <p>Pending new summaries: {callPrefs.pending_new_email_summaries ?? 0}</p>
            <p>Status: {callPrefs.next_scheduled_summary_call_status || "Unknown"}</p>
          </div>
        </div>
        <form className="mt-6 grid gap-4 md:grid-cols-2" onSubmit={handleSaveCallPreferences}>
          <input
            value={callPrefs.timezone}
            onChange={(e) => setCallPrefs({ ...callPrefs, timezone: e.target.value })}
            placeholder="Timezone"
            className="rounded-xl border border-slate-300 bg-white px-4 py-3 text-slate-900 outline-none placeholder:text-slate-400 focus:border-slate-900"
          />
          <div className="rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-600">
            Minimum new emails required to call
            <select
              value={callPrefs.minimum_new_emails_to_call}
              onChange={(e) => setCallPrefs({ ...callPrefs, minimum_new_emails_to_call: Number(e.target.value) })}
              className="mt-2 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-slate-900"
            >
              {[1, 3, 5].map((value) => (
                <option key={value} value={value}>
                  {value}
                </option>
              ))}
            </select>
          </div>
          {[
            ["call_slot_1_time", "call_slot_1_enabled", "Call 1"],
            ["call_slot_2_time", "call_slot_2_enabled", "Call 2"],
            ["call_slot_3_time", "call_slot_3_enabled", "Call 3"],
          ].map(([timeKey, enabledKey, label]) => (
            <div key={timeKey} className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <p className="text-xs uppercase tracking-[0.25em] text-slate-500">{label}</p>
                  <p className="mt-1 text-sm text-slate-600">Set the scheduled mail summary call time.</p>
                </div>
                <label className="inline-flex items-center gap-2 text-sm text-slate-700">
                  <input
                    type="checkbox"
                    checked={callPrefs[enabledKey]}
                    onChange={(e) => setCallPrefs({ ...callPrefs, [enabledKey]: e.target.checked })}
                  />
                  Enabled
                </label>
              </div>
              <input
                type="time"
                value={callPrefs[timeKey]}
                onChange={(e) => setCallPrefs({ ...callPrefs, [timeKey]: e.target.value })}
                className="mt-3 w-full rounded-xl border border-slate-300 bg-white px-4 py-3 text-slate-900 outline-none"
              />
            </div>
          ))}
          <label className="flex items-center gap-3 rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-700">
            <input
              type="checkbox"
              checked={callPrefs.skip_if_no_new_emails}
              onChange={(e) => setCallPrefs({ ...callPrefs, skip_if_no_new_emails: e.target.checked })}
            />
            Skip call if no new emails
          </label>
          <label className="flex items-center gap-3 rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-700">
            <input
              type="checkbox"
              checked={callPrefs.avoid_repeating_delivered_emails}
              onChange={(e) => setCallPrefs({ ...callPrefs, avoid_repeating_delivered_emails: e.target.checked })}
            />
            Avoid repeating already delivered emails
          </label>
          <div className="md:col-span-2 space-y-3">
            {callPrefsMessage ? <p className="rounded-xl border border-slate-200 bg-slate-50 p-3 text-sm text-slate-700">{callPrefsMessage}</p> : null}
            {callPrefsError ? <p className="rounded-xl border border-slate-200 bg-slate-50 p-3 text-sm text-slate-700">{callPrefsError}</p> : null}
            <button
              type="submit"
              disabled={callPrefsLoading}
              className="rounded-xl bg-slate-900 px-4 py-3 font-semibold text-white disabled:opacity-60"
            >
              {callPrefsLoading ? "Saving..." : "Save preferences"}
            </button>
          </div>
        </form>
      </section>
    </PageShell>
  );
}

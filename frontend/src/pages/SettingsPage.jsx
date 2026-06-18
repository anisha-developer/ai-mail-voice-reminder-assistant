import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import PageShell from "../components/PageShell";
import { apiRequest, callPreferencesApi } from "../lib/api";
import { useAuth } from "../context/AuthContext";

function to12HourTime(value) {
  if (!value) return "";
  const [hoursRaw, minutesRaw] = String(value).split(":");
  const hours = Number(hoursRaw);
  const minutes = Number(minutesRaw);
  if (Number.isNaN(hours) || Number.isNaN(minutes)) return "";
  const period = hours >= 12 ? "PM" : "AM";
  const normalizedHour = hours % 12 || 12;
  return `${String(normalizedHour).padStart(2, "0")}:${String(minutes).padStart(2, "0")} ${period}`;
}

function from12HourTime(hour, minute, period) {
  const hourNum = Number(hour);
  const minuteNum = Number(minute);
  if (Number.isNaN(hourNum) || Number.isNaN(minuteNum)) return "";
  let normalizedHour = hourNum % 12;
  if (period === "PM") normalizedHour += 12;
  return `${String(normalizedHour).padStart(2, "0")}:${String(minuteNum).padStart(2, "0")}`;
}

function buildTimePickerState(value) {
  const [hoursRaw = "09", minutesRaw = "00"] = String(value || "09:00").split(":");
  const hours24 = Number(hoursRaw);
  const hour12 = hours24 % 12 || 12;
  return {
    hour: String(hour12).padStart(2, "0"),
    minute: String(Number(minutesRaw) || 0).padStart(2, "0"),
    period: hours24 >= 12 ? "PM" : "AM",
  };
}

export default function SettingsPage() {
  const [searchParams] = useSearchParams();
  const { setUser } = useAuth();
  const [form, setForm] = useState({
    name: "",
  });
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [gmailStatus, setGmailStatus] = useState({ is_connected: false, gmail_email: null, connected_at: null, can_send_replies: false });
  const [gmailMessage, setGmailMessage] = useState("");
  const [gmailError, setGmailError] = useState("");
  const [gmailLoading, setGmailLoading] = useState(false);
  const [callPrefs, setCallPrefs] = useState({
    phone_number: "",
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
        console.error("Failed to load Gmail status", err);
        setGmailError("Could not refresh Gmail status. Please try again.");
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
        body: JSON.stringify({ name: form.name }),
      });
      const phoneSaved = await callPreferencesApi.update({
        phone_number: callPrefs.phone_number,
      });
      setUser(updated);
      setCallPrefs((current) => ({ ...current, phone_number: phoneSaved.phone_number || current.phone_number }));
      setMessage("Profile and phone number saved successfully.");
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
      setGmailError("");
    } catch (err) {
      console.error("Failed to refresh Gmail status", err);
      setGmailError("Could not refresh Gmail status. Please try again.");
    }
  };

  const handleSaveCallPreferences = async (event) => {
    event.preventDefault();
    setCallPrefsMessage("");
    setCallPrefsError("");
    setCallPrefsLoading(true);
    try {
      const updated = await callPreferencesApi.update({
        phone_number: callPrefs.phone_number,
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

  const timePickers = {
    call_slot_1_time: buildTimePickerState(callPrefs.call_slot_1_time),
    call_slot_2_time: buildTimePickerState(callPrefs.call_slot_2_time),
    call_slot_3_time: buildTimePickerState(callPrefs.call_slot_3_time),
  };

  return (
    <PageShell
      title="Settings"
      description="Update your preferences."
    >
      <form className="grid gap-4 md:grid-cols-2" onSubmit={handleSubmit}>
        <div>
          <label className="mb-2 block text-sm font-medium text-slate-700">Name</label>
          <input
            value={form.name}
            onChange={(e) => setForm({ ...form, name: e.target.value })}
            placeholder="Full name"
            className="h-12 w-full rounded-xl border border-slate-300 bg-white px-4 text-slate-900 outline-none placeholder:text-slate-400 focus:border-slate-900"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-slate-700">Phone number for voice calls</label>
          <input
            type="tel"
            inputMode="tel"
            autoComplete="tel"
            value={callPrefs.phone_number || ""}
            onChange={(e) => setCallPrefs({ ...callPrefs, phone_number: e.target.value })}
            placeholder="+91 **********"
            className="mt-2 h-12 w-full rounded-xl border border-slate-300 bg-white px-4 text-slate-900 outline-none placeholder:text-slate-400 focus:border-slate-900"
          />
          <p className="mt-2 text-xs text-slate-500">Use international format, example +91 **********.</p>
        </div>
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
            <p className="mt-1 text-sm text-slate-600">You can schedule up to 3 email summary calls per day.</p>
          </div>
        </div>
        <form className="mt-6 grid gap-4 md:grid-cols-2" onSubmit={handleSaveCallPreferences}>
          {[
            ["call_slot_1_time", "call_slot_1_enabled", "Call 1"],
            ["call_slot_2_time", "call_slot_2_enabled", "Call 2"],
            ["call_slot_3_time", "call_slot_3_enabled", "Call 3"],
          ].map(([timeKey, enabledKey, label]) => (
            <div key={timeKey} className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <p className="text-xs uppercase tracking-[0.25em] text-slate-500">{label}</p>
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
              <div className="mt-3 grid grid-cols-[1fr_1fr_auto] gap-2">
                <select
                  value={timePickers[timeKey].hour}
                  onChange={(e) =>
                    setCallPrefs({
                      ...callPrefs,
                      [timeKey]: from12HourTime(e.target.value, timePickers[timeKey].minute, timePickers[timeKey].period),
                    })
                  }
                  className="rounded-xl border border-slate-300 bg-white px-4 py-3 text-slate-900 outline-none"
                >
                  {Array.from({ length: 12 }, (_, index) => index + 1).map((hour) => (
                    <option key={hour} value={String(hour).padStart(2, "0")}>
                      {String(hour).padStart(2, "0")}
                    </option>
                  ))}
                </select>
                <select
                  value={timePickers[timeKey].minute}
                  onChange={(e) =>
                    setCallPrefs({
                      ...callPrefs,
                      [timeKey]: from12HourTime(timePickers[timeKey].hour, e.target.value, timePickers[timeKey].period),
                    })
                  }
                  className="rounded-xl border border-slate-300 bg-white px-4 py-3 text-slate-900 outline-none"
                >
                  {Array.from({ length: 60 }, (_, index) => String(index).padStart(2, "0")).map((minute) => (
                    <option key={minute} value={minute}>
                      {minute}
                    </option>
                  ))}
                </select>
                <select
                  value={timePickers[timeKey].period}
                  onChange={(e) =>
                    setCallPrefs({
                      ...callPrefs,
                      [timeKey]: from12HourTime(timePickers[timeKey].hour, timePickers[timeKey].minute, e.target.value),
                    })
                  }
                  className="rounded-xl border border-slate-300 bg-white px-4 py-3 text-slate-900 outline-none"
                >
                  {["AM", "PM"].map((period) => (
                    <option key={period} value={period}>
                      {period}
                    </option>
                  ))}
                </select>
              </div>
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

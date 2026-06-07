import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import PageShell from "../components/PageShell";
import { apiRequest } from "../lib/api";
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

  return (
    <PageShell
      title="Settings / Profile"
      description="Update your profile details and profile defaults."
    >
      <form className="grid gap-4 md:grid-cols-2" onSubmit={handleSubmit}>
        <div className="md:col-span-2 rounded-2xl border border-white/10 bg-white/5 p-5 text-slate-300">
          Signed in as <span className="text-white">{user?.email}</span>
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
            className="rounded-xl border border-white/10 bg-slate-950 px-4 py-3 text-white outline-none"
          />
        ))}
        <div className="md:col-span-2 space-y-3">
          {message ? <p className="rounded-xl border border-emerald-500/30 bg-emerald-500/10 p-3 text-sm text-emerald-200">{message}</p> : null}
          {error ? <p className="rounded-xl border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-200">{error}</p> : null}
          <button className="rounded-xl bg-sky-400 px-4 py-3 font-semibold text-slate-950">Save changes</button>
        </div>
      </form>

      <section className="mt-8 rounded-3xl border border-white/10 bg-white/5 p-5">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <p className="text-xs uppercase tracking-[0.3em] text-sky-300">Gmail Connection</p>
            <h3 className="mt-2 text-xl font-semibold text-white">
              {gmailStatus.is_connected ? "Connected" : "Disconnected"}
            </h3>
            <p className="mt-1 text-sm text-slate-300">
              {gmailStatus.gmail_email ? `Connected Gmail: ${gmailStatus.gmail_email}` : "No Gmail account connected yet."}
            </p>
            {gmailStatus.connected_at ? (
              <p className="mt-1 text-xs text-slate-400">Connected at {new Date(gmailStatus.connected_at).toLocaleString()}</p>
            ) : null}
            {gmailStatus.is_connected && !gmailStatus.can_send_replies ? (
              <p className="mt-2 rounded-xl border border-amber-400/30 bg-amber-500/10 p-3 text-sm text-amber-200">
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
                className="rounded-xl border border-red-400/40 bg-red-500/10 px-4 py-3 text-sm font-semibold text-red-200 disabled:opacity-60"
              >
                Disconnect Gmail
              </button>
            ) : (
              <button
                type="button"
                onClick={handleConnectGmail}
                disabled={gmailLoading}
                className="rounded-xl bg-sky-400 px-4 py-3 text-sm font-semibold text-slate-950 disabled:opacity-60"
              >
                Connect Gmail
              </button>
            )}
            <button
              type="button"
              onClick={refreshGmailStatus}
              className="rounded-xl border border-white/10 px-4 py-3 text-sm font-semibold text-slate-200"
            >
              Refresh Status
            </button>
          </div>
        </div>
        <div className="mt-4 space-y-3">
          {gmailMessage ? <p className="rounded-xl border border-emerald-500/30 bg-emerald-500/10 p-3 text-sm text-emerald-200">{gmailMessage}</p> : null}
          {gmailError ? <p className="rounded-xl border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-200">{gmailError}</p> : null}
        </div>
      </section>
    </PageShell>
  );
}

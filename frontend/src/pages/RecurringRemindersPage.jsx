import { useEffect, useMemo, useState } from "react";
import PageShell from "../components/PageShell";
import { recurringReminderApi } from "../lib/api";

const DAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"];

const initialForm = {
  title: "",
  notes: "",
  timezone: Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC",
  repeat_type: "daily",
  interval_value: 1,
  interval_unit: "days",
  days_of_week: ["monday"],
  day_of_month: 1,
  time_of_day: "09:00",
  source_type: "manual",
};

function describeRule(rule) {
  if (!rule) return "-";
  if (rule.repeat_type === "daily") return `Daily at ${rule.time_of_day || "-"}`;
  if (rule.repeat_type === "weekdays") return `Weekdays at ${rule.time_of_day || "-"}`;
  if (rule.repeat_type === "weekly") return `Weekly on ${(rule.days_of_week || []).join(", ")} at ${rule.time_of_day || "-"}`;
  if (rule.repeat_type === "custom_days") return `Custom days ${(rule.days_of_week || []).join(", ")} at ${rule.time_of_day || "-"}`;
  if (rule.repeat_type === "monthly") return `Monthly on day ${rule.day_of_month || "-"} at ${rule.time_of_day || "-"}`;
  if (rule.repeat_type === "custom_interval") return `Every ${rule.interval_value || "-"} ${rule.interval_unit || "-"}`;
  return rule.repeat_type || "-";
}

function Field({ label, children }) {
  return (
    <label className="block min-w-0">
      <span className="mb-2 block text-sm font-medium text-slate-700">{label}</span>
      {children}
    </label>
  );
}

function Input({ className = "", ...props }) {
  return <input {...props} className={`w-full rounded-xl border border-slate-300 bg-white px-4 py-3 text-slate-900 outline-none placeholder:text-slate-400 focus:border-slate-900 ${className}`} />;
}

function Textarea({ className = "", ...props }) {
  return <textarea {...props} className={`w-full rounded-xl border border-slate-300 bg-white px-4 py-3 text-slate-900 outline-none placeholder:text-slate-400 focus:border-slate-900 ${className}`} />;
}

export default function RecurringRemindersPage() {
  const [rules, setRules] = useState([]);
  const [form, setForm] = useState(initialForm);
  const [editingRuleId, setEditingRuleId] = useState(null);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [selectedRuleId, setSelectedRuleId] = useState(null);
  const selectedRule = useMemo(() => rules.find((rule) => rule.id === selectedRuleId) || null, [rules, selectedRuleId]);

  const loadRules = async () => {
    const data = await recurringReminderApi.list();
    setRules(data.value || []);
  };

  useEffect(() => {
    loadRules().catch((err) => setError(err.message));
  }, []);

  const resetForm = () => {
    setForm(initialForm);
    setEditingRuleId(null);
  };

  const handleSubmit = async (event) => {
    event.preventDefault();
    setLoading(true);
    setMessage("");
    setError("");
    try {
      const payload = {
        title: form.title,
        notes: form.notes || undefined,
        timezone: form.timezone,
        repeat_type: form.repeat_type,
        interval_value: form.repeat_type === "custom_interval" ? Number(form.interval_value) : undefined,
        interval_unit: form.repeat_type === "custom_interval" ? form.interval_unit : undefined,
        days_of_week: ["weekly", "custom_days"].includes(form.repeat_type) ? form.days_of_week : undefined,
        day_of_month: form.repeat_type === "monthly" ? Number(form.day_of_month) : undefined,
        time_of_day: ["daily", "weekly", "weekdays", "custom_days", "monthly"].includes(form.repeat_type) ? form.time_of_day : undefined,
        source_type: form.source_type,
      };
      if (editingRuleId) {
        await recurringReminderApi.update(editingRuleId, payload);
        setMessage("Recurring reminder updated successfully.");
      } else {
        await recurringReminderApi.create(payload);
        setMessage("Recurring reminder saved successfully.");
      }
      resetForm();
      await loadRules();
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleAction = async (ruleId, action) => {
    setLoading(true);
    setMessage("");
    setError("");
    try {
      if (action === "pause") await recurringReminderApi.pause(ruleId);
      if (action === "resume") await recurringReminderApi.resume(ruleId);
      if (action === "cancel") await recurringReminderApi.cancel(ruleId);
      await loadRules();
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const startEdit = (rule) => {
    setEditingRuleId(rule.id);
    setForm({
      title: rule.title || "",
      notes: rule.notes || "",
      timezone: rule.timezone || Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC",
      repeat_type: rule.repeat_type || "daily",
      interval_value: rule.interval_value || 1,
      interval_unit: rule.interval_unit || "days",
      days_of_week: Array.isArray(rule.days_of_week) && rule.days_of_week.length ? rule.days_of_week : ["monday"],
      day_of_month: rule.day_of_month || 1,
      time_of_day: rule.time_of_day || "09:00",
      source_type: rule.source_type || "manual",
    });
  };

  return (
    <PageShell title="Recurring Reminders" description="Create, edit, pause, resume, and cancel repeat rules without crowding the dashboard.">
      <section className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
        <div className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
          <div className="min-w-0">
            <p className="text-xs uppercase tracking-[0.3em] text-slate-500">Recurring reminders</p>
            <h3 className="mt-2 break-words text-xl font-semibold text-slate-900">{editingRuleId ? "Edit repeat rule" : "Create repeat rule"}</h3>
          </div>
          {editingRuleId ? (
            <button type="button" onClick={resetForm} className="rounded-xl border border-slate-200 px-4 py-2 text-sm font-semibold text-slate-700">
              Cancel edit
            </button>
          ) : null}
        </div>

        <form className="mt-5 grid gap-4 md:grid-cols-2" onSubmit={handleSubmit}>
          <Field label="Reminder title">
            <Input value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} placeholder="Drink water" required />
          </Field>
          <Field label="Timezone">
            <Input value={form.timezone} onChange={(e) => setForm({ ...form, timezone: e.target.value })} placeholder="Asia/Kolkata" required />
          </Field>
          <div className="md:col-span-2">
            <Field label="Notes">
              <Textarea rows="3" value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} placeholder="Take a short break and drink water." />
            </Field>
          </div>
          <Field label="Repeat type">
            <select
              value={form.repeat_type}
              onChange={(e) => setForm({ ...form, repeat_type: e.target.value })}
              className="w-full rounded-xl border border-slate-300 bg-white px-4 py-3 text-slate-900 outline-none"
            >
              <option value="daily">Daily</option>
              <option value="weekly">Weekly</option>
              <option value="monthly">Monthly</option>
              <option value="weekdays">Weekdays</option>
              <option value="custom_days">Custom days</option>
              <option value="custom_interval">Custom interval</option>
            </select>
          </Field>
          {form.repeat_type === "custom_interval" ? (
            <>
              <Field label="Every">
                <Input type="number" min="1" value={form.interval_value} onChange={(e) => setForm({ ...form, interval_value: e.target.value })} />
              </Field>
              <Field label="Interval unit">
                <select
                  value={form.interval_unit}
                  onChange={(e) => setForm({ ...form, interval_unit: e.target.value })}
                  className="w-full rounded-xl border border-slate-300 bg-white px-4 py-3 text-slate-900 outline-none"
                >
                  <option value="minutes">Minutes</option>
                  <option value="hours">Hours</option>
                  <option value="days">Days</option>
                  <option value="weeks">Weeks</option>
                  <option value="months">Months</option>
                </select>
              </Field>
            </>
          ) : null}
          {["daily", "weekly", "weekdays", "custom_days", "monthly"].includes(form.repeat_type) ? (
            <Field label="Time of day">
              <Input type="time" value={form.time_of_day} onChange={(e) => setForm({ ...form, time_of_day: e.target.value })} />
            </Field>
          ) : null}
          {form.repeat_type === "weekly" || form.repeat_type === "custom_days" ? (
            <div className="md:col-span-2 rounded-2xl border border-slate-200 bg-slate-50 p-4">
              <p className="text-sm font-medium text-slate-700">Days of week</p>
              <div className="mt-3 grid grid-cols-2 gap-2 sm:grid-cols-4">
                {DAYS.map((day) => (
                  <label key={day} className="flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700">
                    <input
                      type="checkbox"
                      checked={form.days_of_week.includes(day)}
                      onChange={(e) => {
                        const next = e.target.checked ? [...form.days_of_week, day] : form.days_of_week.filter((item) => item !== day);
                        setForm({ ...form, days_of_week: next });
                      }}
                    />
                    {day}
                  </label>
                ))}
              </div>
            </div>
          ) : null}
          {form.repeat_type === "monthly" ? (
            <Field label="Day of month">
              <Input type="number" min="1" max="31" value={form.day_of_month} onChange={(e) => setForm({ ...form, day_of_month: e.target.value })} />
            </Field>
          ) : null}
          <div className="md:col-span-2 flex flex-wrap gap-3">
            <button type="submit" disabled={loading} className="rounded-xl bg-slate-900 px-4 py-3 font-semibold text-white disabled:opacity-60">
              {loading ? "Saving..." : editingRuleId ? "Save changes" : "Save recurring reminder"}
            </button>
            <button type="button" onClick={resetForm} className="rounded-xl border border-slate-200 px-4 py-3 font-semibold text-slate-700">
              Reset
            </button>
          </div>
        </form>
      </section>

      {message ? <div className="rounded-xl border border-slate-200 bg-slate-50 p-3 text-slate-700">{message}</div> : null}
      {error ? <div className="rounded-xl border border-slate-200 bg-slate-50 p-3 text-slate-700">{error}</div> : null}

      <section className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
        <div className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <p className="text-xs uppercase tracking-[0.3em] text-slate-500">Recurring reminders</p>
            <h3 className="mt-2 text-xl font-semibold text-slate-900">Saved repeat rules</h3>
          </div>
          <p className="text-sm text-slate-500">Pause, resume, edit, or cancel a series without affecting one-time reminders.</p>
        </div>
        <div className="mt-5 space-y-3">
          {rules.length === 0 ? (
            <p className="text-sm text-slate-400">No recurring reminders yet.</p>
          ) : (
            rules.map((rule) => (
              <div key={rule.id} className="min-w-0 rounded-2xl border border-slate-200 bg-slate-50 p-4">
                <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                  <div className="min-w-0 space-y-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <h4 className="break-words text-lg font-semibold text-slate-900">{rule.title}</h4>
                      <span className="rounded-full border border-slate-200 px-3 py-1 text-xs text-slate-600">{rule.status}</span>
                    </div>
                    <p className="break-words text-sm text-slate-600">{rule.notes || "No notes provided."}</p>
                    <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-slate-500">
                      <span className="break-words">{describeRule(rule)}</span>
                      <span className="break-words">Next: {rule.next_occurrence_at ? new Date(rule.next_occurrence_at).toLocaleString() : "None"}</span>
                      <span className="break-words">Timezone: {rule.timezone}</span>
                    </div>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <button type="button" onClick={() => startEdit(rule)} className="rounded-xl border border-slate-200 px-4 py-2 text-sm font-semibold text-slate-700">
                      Edit
                    </button>
                    {rule.status === "active" ? (
                      <button type="button" onClick={() => handleAction(rule.id, "pause")} className="rounded-xl border border-slate-200 px-4 py-2 text-sm font-semibold text-slate-700">
                        Pause
                      </button>
                    ) : null}
                    {rule.status === "paused" ? (
                      <button type="button" onClick={() => handleAction(rule.id, "resume")} className="rounded-xl border border-slate-200 px-4 py-2 text-sm font-semibold text-slate-700">
                        Resume
                      </button>
                    ) : null}
                    {rule.status !== "cancelled" ? (
                      <button type="button" onClick={() => handleAction(rule.id, "cancel")} className="rounded-xl border border-red-200 px-4 py-2 text-sm font-semibold text-slate-700">
                        Cancel series
                      </button>
                    ) : null}
                    <button type="button" onClick={() => setSelectedRuleId(rule.id)} className="rounded-xl border border-slate-200 px-4 py-2 text-sm font-semibold text-slate-700">
                      View occurrences
                    </button>
                  </div>
                </div>
              </div>
            ))
          )}
        </div>
      </section>

      {selectedRule ? (
        <section className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
          <div className="flex items-center justify-between gap-4">
            <div>
              <p className="text-xs uppercase tracking-[0.3em] text-slate-500">Occurrences</p>
              <h3 className="mt-2 text-xl font-semibold text-slate-900">{selectedRule.title}</h3>
            </div>
            <button type="button" onClick={() => setSelectedRuleId(null)} className="rounded-xl border border-slate-200 px-4 py-2 text-sm font-semibold text-slate-700">
              Close
            </button>
          </div>
          <div className="mt-4 rounded-2xl border border-slate-200 bg-slate-50 p-4 text-sm text-slate-700">
            <p>Future occurrence rows are generated automatically by the scheduler and appear in the main reminder list when due.</p>
          </div>
        </section>
      ) : null}
    </PageShell>
  );
}

import { useEffect, useMemo, useState } from "react";
import PageShell from "../components/PageShell";
import { emailApi, priorityContactsApi } from "../lib/api";

const RELATIONSHIP_OPTIONS = ["Family", "Mentor", "Client", "Manager", "Other"];

function normalizeEmailAddress(value) {
  if (!value || typeof value !== "string") return "";
  const match = value.match(/[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}/i);
  return (match ? match[0] : value).trim().toLowerCase();
}

function getDisplayNameFromSender(sender) {
  if (!sender || typeof sender !== "string") return "Unknown sender";
  const match = sender.match(/^(.*?)<[^>]+>/);
  const name = match?.[1]?.trim();
  if (name) return name;
  const email = normalizeEmailAddress(sender);
  return email ? email.split("@")[0] : sender.trim();
}

function emptyForm() {
  return {
    id: null,
    displayName: "",
    emailAddress: "",
    relationship: "Other",
    priorityLevel: 1,
    notes: "",
  };
}

export default function PriorityContactsPage() {
  const [contacts, setContacts] = useState([]);
  const [emails, setEmails] = useState([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState(emptyForm());
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  const loadData = async () => {
    setLoading(true);
    try {
      const [contactList, emailList] = await Promise.all([
        priorityContactsApi.list(),
        emailApi.getAllEmails(),
      ]);
      setContacts(Array.isArray(contactList) ? contactList : []);
      setEmails(Array.isArray(emailList) ? emailList : []);
    } catch (err) {
      setError(err.message || "Could not load priority contacts.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData().catch(() => {});
  }, []);

  const priorityMail = useMemo(() => {
    const priorityEmails = new Map(
      contacts
        .map((contact) => [normalizeEmailAddress(contact.email_address), contact])
        .filter(([email]) => Boolean(email)),
    );

    return emails.filter((email) => priorityEmails.has(normalizeEmailAddress(email.sender)));
  }, [contacts, emails]);

  const resetForm = () => {
    setForm(emptyForm());
    setError("");
    setMessage("");
  };

  const beginEdit = (contact) => {
    setForm({
      id: contact.id,
      displayName: contact.display_name || "",
      emailAddress: contact.email_address || "",
      relationship: contact.relationship || "Other",
      priorityLevel: contact.priority_level || 1,
      notes: contact.notes || "",
    });
    setError("");
    setMessage("");
  };

  const handleSubmit = async (event) => {
    event.preventDefault();
    setSaving(true);
    setError("");
    setMessage("");
    try {
      const payload = {
        display_name: form.displayName.trim(),
        email_address: form.emailAddress.trim(),
        relationship: form.relationship,
        priority_level: form.priorityLevel,
        notes: form.notes.trim() || null,
      };
      if (form.id) {
        await priorityContactsApi.update(form.id, payload);
        setMessage("Priority contact updated.");
      } else {
        await priorityContactsApi.create(payload);
        setMessage("Priority contact saved.");
      }
      resetForm();
      await loadData();
    } catch (err) {
      setError(err.message || "Could not save priority contact.");
    } finally {
      setSaving(false);
    }
  };

  const removeContact = async (contact) => {
    setSaving(true);
    setError("");
    setMessage("");
    try {
      await priorityContactsApi.delete(contact.id);
      setMessage("Priority contact removed.");
      if (form.id === contact.id) {
        resetForm();
      }
      await loadData();
    } catch (err) {
      setError(err.message || "Could not delete priority contact.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <PageShell
      title="Priority Contacts"
      description="Mark important senders so their emails can be handled with higher priority."
    >
      {message ? (
        <div className="rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800">
          {message}
        </div>
      ) : null}
      {error ? (
        <div className="rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
          {error}
        </div>
      ) : null}

      <section className="rounded-2xl border border-slate-200 bg-white p-5">
        <div className="mb-4">
          <h2 className="text-lg font-semibold text-slate-900">Add priority contact</h2>
          <p className="mt-1 text-sm text-slate-500">
            Save family, mentors, clients, managers, and other important contacts here.
          </p>
        </div>
        <form onSubmit={handleSubmit} className="grid gap-4 md:grid-cols-2">
          <label className="space-y-2">
            <span className="text-sm font-medium text-slate-700">Display name</span>
            <input
              type="text"
              value={form.displayName}
              onChange={(event) => setForm((current) => ({ ...current, displayName: event.target.value }))}
              className="w-full rounded-xl border border-slate-300 px-4 py-3 text-slate-900 outline-none focus:border-slate-900"
              placeholder="Aunty, Mentor, Client"
            />
          </label>
          <label className="space-y-2">
            <span className="text-sm font-medium text-slate-700">Email address</span>
            <input
              type="email"
              value={form.emailAddress}
              onChange={(event) => setForm((current) => ({ ...current, emailAddress: event.target.value }))}
              className="w-full rounded-xl border border-slate-300 px-4 py-3 text-slate-900 outline-none focus:border-slate-900"
              placeholder="name@example.com"
            />
          </label>
          <label className="space-y-2">
            <span className="text-sm font-medium text-slate-700">Relationship</span>
            <select
              value={form.relationship}
              onChange={(event) => setForm((current) => ({ ...current, relationship: event.target.value }))}
              className="w-full rounded-xl border border-slate-300 px-4 py-3 text-slate-900 outline-none focus:border-slate-900"
            >
              {RELATIONSHIP_OPTIONS.map((option) => (
                <option key={option} value={option}>
                  {option}
                </option>
              ))}
            </select>
          </label>
          <label className="space-y-2">
            <span className="text-sm font-medium text-slate-700">Priority level</span>
            <select
              value={form.priorityLevel}
              onChange={(event) => setForm((current) => ({ ...current, priorityLevel: Number(event.target.value) }))}
              className="w-full rounded-xl border border-slate-300 px-4 py-3 text-slate-900 outline-none focus:border-slate-900"
            >
              {[1, 2, 3].map((level) => (
                <option key={level} value={level}>
                  {level}
                </option>
              ))}
            </select>
          </label>
          <label className="space-y-2 md:col-span-2">
            <span className="text-sm font-medium text-slate-700">Notes</span>
            <textarea
              value={form.notes}
              onChange={(event) => setForm((current) => ({ ...current, notes: event.target.value }))}
              rows={3}
              className="w-full rounded-xl border border-slate-300 px-4 py-3 text-slate-900 outline-none focus:border-slate-900"
              placeholder="Important context for this contact"
            />
          </label>
          <div className="flex flex-wrap gap-3 md:col-span-2">
            <button
              type="submit"
              disabled={saving}
              className="rounded-xl bg-slate-900 px-5 py-3 text-sm font-semibold text-white hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {form.id ? "Update" : "Save"}
            </button>
            {form.id ? (
              <button
                type="button"
                onClick={resetForm}
                className="rounded-xl border border-slate-200 px-5 py-3 text-sm font-semibold text-slate-700 hover:bg-slate-50"
              >
                Cancel
              </button>
            ) : null}
          </div>
        </form>
      </section>

      <section className="rounded-2xl border border-slate-200 bg-white p-5">
        <div className="mb-4 flex items-center justify-between gap-3">
          <div>
            <h2 className="text-lg font-semibold text-slate-900">Saved contacts</h2>
            <p className="mt-1 text-sm text-slate-500">These contacts are used for priority handling.</p>
          </div>
          <span className="rounded-full border border-slate-200 px-3 py-1 text-xs font-medium text-slate-500">
            {contacts.length} saved
          </span>
        </div>

        {loading ? (
          <div className="rounded-2xl border border-slate-200 bg-slate-50 p-6 text-sm text-slate-500">
            Loading priority contacts...
          </div>
        ) : contacts.length === 0 ? (
          <div className="rounded-2xl border border-dashed border-slate-200 bg-slate-50 p-6 text-sm text-slate-500">
            No priority contacts added yet.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full text-left text-sm">
              <thead className="text-xs uppercase tracking-[0.2em] text-slate-400">
                <tr>
                  <th className="px-4 py-3">Display name</th>
                  <th className="px-4 py-3">Email address</th>
                  <th className="px-4 py-3">Relationship</th>
                  <th className="px-4 py-3">Priority</th>
                  <th className="px-4 py-3">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {contacts.map((contact) => (
                  <tr key={contact.id} className="text-slate-700">
                    <td className="px-4 py-3 font-medium text-slate-900">{contact.display_name || "-"}</td>
                    <td className="px-4 py-3">{contact.email_address}</td>
                    <td className="px-4 py-3">{contact.relationship || "Other"}</td>
                    <td className="px-4 py-3">{contact.priority_level || 1}</td>
                    <td className="px-4 py-3">
                      <div className="flex flex-wrap gap-2">
                        <button
                          type="button"
                          onClick={() => beginEdit(contact)}
                          className="rounded-lg border border-slate-200 px-3 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-50"
                        >
                          Edit
                        </button>
                        <button
                          type="button"
                          onClick={() => removeContact(contact)}
                          className="rounded-lg border border-slate-200 px-3 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-50"
                        >
                          Delete
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <section className="rounded-2xl border border-slate-200 bg-white p-5">
        <div className="mb-4">
          <h2 className="text-lg font-semibold text-slate-900">Priority Mail</h2>
          <p className="mt-1 text-sm text-slate-500">
            Emails from saved priority contacts are highlighted here for the demo.
          </p>
        </div>

        {loading ? (
          <div className="rounded-2xl border border-slate-200 bg-slate-50 p-6 text-sm text-slate-500">
            Loading priority mail...
          </div>
        ) : priorityMail.length === 0 ? (
          <div className="rounded-2xl border border-dashed border-slate-200 bg-slate-50 p-6 text-sm text-slate-500">
            {contacts.length === 0
              ? "Add a priority contact to see matching emails here."
              : "No matching priority emails found in the current inbox."}
          </div>
        ) : (
          <div className="space-y-3">
            {priorityMail.map((email) => (
              <div key={email.id} className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                <p className="text-sm font-semibold text-slate-900">{email.subject || "(No subject)"}</p>
                <p className="mt-1 text-sm text-slate-600">{email.sender || "-"}</p>
                <p className="mt-2 text-sm text-slate-500">{email.snippet || "No preview available."}</p>
              </div>
            ))}
          </div>
        )}
      </section>
    </PageShell>
  );
}

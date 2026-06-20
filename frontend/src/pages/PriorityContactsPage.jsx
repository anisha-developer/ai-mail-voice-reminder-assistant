import { useEffect, useMemo, useState } from "react";
import PageShell from "../components/PageShell";
import { emailApi } from "../lib/api";

const PRIORITY_CONTACTS_KEY = "priority_contacts";
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

function readPriorityContacts() {
  try {
    const raw = localStorage.getItem(PRIORITY_CONTACTS_KEY);
    const parsed = raw ? JSON.parse(raw) : [];
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

function writePriorityContacts(contacts) {
  try {
    localStorage.setItem(PRIORITY_CONTACTS_KEY, JSON.stringify(contacts));
  } catch {
    // ignore storage issues
  }
}

function savePriorityContact(contact) {
  const contacts = readPriorityContacts();
  const email = normalizeEmailAddress(contact.email);
  if (!email) {
    return { ok: false, message: "Please enter a valid email address." };
  }

  const nextContact = {
    displayName: contact.displayName?.trim() || getDisplayNameFromSender(contact.email),
    email,
    relationship: contact.relationship || "Other",
    addedAt: new Date().toISOString(),
  };

  const existingIndex = contacts.findIndex((item) => normalizeEmailAddress(item.email) === email);
  if (existingIndex >= 0) {
    contacts[existingIndex] = { ...contacts[existingIndex], ...nextContact };
  } else {
    contacts.push(nextContact);
  }

  writePriorityContacts(contacts);
  return { ok: true, message: existingIndex >= 0 ? "Priority contact updated." : "Priority contact saved." };
}

export default function PriorityContactsPage() {
  const [contacts, setContacts] = useState([]);
  const [emails, setEmails] = useState([]);
  const [loading, setLoading] = useState(true);
  const [form, setForm] = useState({
    displayName: "",
    email: "",
    relationship: "Other",
  });
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  const reloadContacts = () => {
    setContacts(readPriorityContacts());
  };

  useEffect(() => {
    reloadContacts();
    emailApi
      .getAllEmails()
      .then((list) => setEmails(Array.isArray(list) ? list : []))
      .catch(() => setEmails([]))
      .finally(() => setLoading(false));
  }, []);

  const priorityMail = useMemo(() => {
    const priorityEmails = new Set(contacts.map((contact) => normalizeEmailAddress(contact.email)).filter(Boolean));
    return emails.filter((email) => priorityEmails.has(normalizeEmailAddress(email.sender)));
  }, [contacts, emails]);

  const handleSubmit = (event) => {
    event.preventDefault();
    setError("");
    setMessage("");
    const result = savePriorityContact(form);
    if (!result.ok) {
      setError(result.message);
      return;
    }
    setMessage(result.message);
    setForm({ displayName: "", email: "", relationship: "Other" });
    reloadContacts();
  };

  const removeContact = (email) => {
    const nextContacts = readPriorityContacts().filter((contact) => normalizeEmailAddress(contact.email) !== normalizeEmailAddress(email));
    writePriorityContacts(nextContacts);
    reloadContacts();
    setMessage("Priority contact removed.");
    setError("");
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
              value={form.email}
              onChange={(event) => setForm((current) => ({ ...current, email: event.target.value }))}
              className="w-full rounded-xl border border-slate-300 px-4 py-3 text-slate-900 outline-none focus:border-slate-900"
              placeholder="name@example.com"
            />
          </label>
          <label className="space-y-2 md:col-span-2">
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
          <div className="md:col-span-2">
            <button
              type="submit"
              className="rounded-xl bg-slate-900 px-5 py-3 text-sm font-semibold text-white hover:bg-slate-800"
            >
              Save
            </button>
          </div>
        </form>
      </section>

      <section className="rounded-2xl border border-slate-200 bg-white p-5">
        <div className="mb-4 flex items-center justify-between gap-3">
          <div>
            <h2 className="text-lg font-semibold text-slate-900">Saved contacts</h2>
            <p className="mt-1 text-sm text-slate-500">These contacts will be marked as priority in the Inbox demo view.</p>
          </div>
          <span className="rounded-full border border-slate-200 px-3 py-1 text-xs font-medium text-slate-500">
            {contacts.length} saved
          </span>
        </div>

        {contacts.length === 0 ? (
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
                  <th className="px-4 py-3">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {contacts.map((contact) => (
                  <tr key={contact.email} className="text-slate-700">
                    <td className="px-4 py-3 font-medium text-slate-900">{contact.displayName || "-"}</td>
                    <td className="px-4 py-3">{contact.email}</td>
                    <td className="px-4 py-3">{contact.relationship || "Other"}</td>
                    <td className="px-4 py-3">
                      <button
                        type="button"
                        onClick={() => removeContact(contact.email)}
                        className="rounded-lg border border-slate-200 px-3 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-50"
                      >
                        Delete
                      </button>
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

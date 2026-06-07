import PageShell from "../components/PageShell";

export default function RemindersPage() {
  return (
    <PageShell
      title="Reminders"
      description="Track reminder templates and status in a lightweight placeholder screen."
    >
      <div className="rounded-2xl border border-white/10 bg-white/5 p-5 text-slate-300">
        No reminders configured yet.
      </div>
    </PageShell>
  );
}


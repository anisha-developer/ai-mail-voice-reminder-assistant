export default function PageShell({ title, description, children }) {
  return (
    <section className="min-w-0 w-full max-w-none space-y-6">
      <div>
        <p className="text-xs uppercase tracking-[0.28em] text-slate-500">Workspace</p>
        <h2 className="mt-2 break-words text-3xl font-semibold text-slate-900">{title}</h2>
        <p className="mt-2 max-w-2xl break-words text-sm text-slate-600">{description}</p>
      </div>
      {children}
    </section>
  );
}

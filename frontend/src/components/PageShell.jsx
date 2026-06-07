export default function PageShell({ title, description, children }) {
  return (
    <section className="space-y-6">
      <div>
        <p className="text-xs uppercase tracking-[0.28em] text-sky-300">Workspace</p>
        <h2 className="mt-2 text-3xl font-semibold text-white">{title}</h2>
        <p className="mt-2 max-w-2xl text-sm text-slate-400">{description}</p>
      </div>
      {children}
    </section>
  );
}


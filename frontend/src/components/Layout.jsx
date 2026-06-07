import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { useEffect, useState } from "react";
import { useAuth } from "../context/AuthContext";

const navItems = [
  { to: "/", label: "Dashboard" },
  { to: "/inbox", label: "Email Inbox" },
  { to: "/summaries", label: "Email Summaries" },
  { to: "/mail-calls", label: "Mail Summary Calls" },
  { to: "/settings", label: "Settings / Profile" },
];

export default function Layout() {
  const [health, setHealth] = useState("Checking...");
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  useEffect(() => {
    const baseUrl = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";
    fetch(`${baseUrl}/health`)
      .then((response) => response.json())
      .then((data) => setHealth(data.status === "ok" ? "Backend connected" : "Backend unavailable"))
      .catch(() => setHealth("Backend unavailable"));
  }, []);

  return (
    <div className="min-h-screen bg-[radial-gradient(circle_at_top,_rgba(59,130,246,0.18),_transparent_35%),linear-gradient(180deg,_#020617_0%,_#0f172a_100%)]">
      <div className="mx-auto flex min-h-screen max-w-7xl flex-col lg:flex-row">
        <aside className="border-r border-white/10 bg-slate-950/70 p-6 backdrop-blur lg:w-72">
          <div className="mb-8">
            <p className="text-xs uppercase tracking-[0.35em] text-sky-300">AI Mail Assistant</p>
            <h1 className="mt-3 text-2xl font-semibold text-white">
              Welcome{user?.name ? `, ${user.name}` : ""}
            </h1>
            <p className="mt-2 text-sm text-slate-400">{health}</p>
            <button
              type="button"
              onClick={() => {
                logout();
                navigate("/login");
              }}
              className="mt-4 rounded-xl border border-white/10 px-4 py-2 text-sm text-slate-200 hover:bg-white/5"
            >
              Logout
            </button>
          </div>
          <nav className="space-y-2">
            {navItems.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.to === "/"}
                className={({ isActive }) =>
                  `block rounded-xl px-4 py-3 text-sm transition ${
                    isActive ? "bg-sky-500 text-slate-950 font-semibold" : "text-slate-300 hover:bg-white/5"
                  }`
                }
              >
                {item.label}
              </NavLink>
            ))}
          </nav>
        </aside>
        <main className="flex-1 p-4 sm:p-6 lg:p-8">
          <div className="rounded-3xl border border-white/10 bg-slate-900/70 p-5 shadow-soft backdrop-blur sm:p-8">
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  );
}

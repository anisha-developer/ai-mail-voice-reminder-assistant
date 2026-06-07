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
    <div className="min-h-screen bg-[linear-gradient(180deg,_#ffffff_0%,_#f8fafc_100%)] text-slate-900">
      <div className="mx-auto flex min-h-screen max-w-7xl flex-col lg:flex-row">
        <aside className="border-r border-slate-200 bg-white/90 p-6 backdrop-blur lg:w-72">
          <div className="mb-8">
            <p className="text-xs uppercase tracking-[0.35em] text-slate-500">AI Mail Assistant</p>
            <h1 className="mt-3 text-2xl font-semibold text-slate-900">
              Welcome{user?.name ? `, ${user.name}` : ""}
            </h1>
            <p className="mt-2 text-sm text-slate-600">{health}</p>
            <button
              type="button"
              onClick={() => {
                logout();
                navigate("/login");
              }}
              className="mt-4 rounded-xl border border-slate-300 bg-white px-4 py-2 text-sm text-slate-700 hover:bg-slate-50"
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
                    isActive ? "bg-slate-900 text-white font-semibold" : "text-slate-700 hover:bg-slate-100"
                  }`
                }
              >
                {item.label}
              </NavLink>
            ))}
          </nav>
        </aside>
        <main className="flex-1 p-4 sm:p-6 lg:p-8">
          <div className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm backdrop-blur sm:p-8">
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  );
}

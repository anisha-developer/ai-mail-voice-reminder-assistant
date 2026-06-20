import { NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import { useEffect, useMemo, useState } from "react";
import { useAuth } from "../context/AuthContext";
import { APP_NAME } from "../constants/app";

const navItems = [
  { to: "/", label: "Dashboard" },
  { to: "/inbox", label: "Email Inbox" },
  { to: "/priority-contacts", label: "Priority Contacts" },
  { to: "/summaries", label: "Email Summaries" },
  { to: "/mail-calls", label: "Mail Summary Calls" },
  { to: "/reminders", label: "Reminders" },
  { to: "/settings", label: "Settings" },
];

export default function Layout() {
  const location = useLocation();
  const [isCollapsed, setIsCollapsed] = useState(() => {
    try {
      return localStorage.getItem("sidebarCollapsed") === "true";
    } catch {
      return false;
    }
  });
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const navShortcuts = useMemo(
    () =>
      navItems.map((item) => ({
        ...item,
        shortLabel: item.label
          .split(" ")
          .map((part) => part[0])
          .join("")
          .slice(0, 2)
          .toUpperCase(),
      })),
    [],
  );

  useEffect(() => {
    document.title = APP_NAME;
  }, []);

  useEffect(() => {
    const baseUrl = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";
    fetch(`${baseUrl}/health`)
      .then((response) => response.json())
      .catch(() => null);
  }, []);

  useEffect(() => {
    try {
      localStorage.setItem("sidebarCollapsed", String(isCollapsed));
    } catch {
      // ignore storage issues
    }
  }, [isCollapsed]);

  useEffect(() => {
    setMobileMenuOpen(false);
  }, [location.pathname]);

  return (
    <div className="min-h-screen w-full overflow-x-hidden bg-[linear-gradient(180deg,_#ffffff_0%,_#f8fafc_100%)] text-slate-900">
      <div className="flex min-h-screen w-full flex-col lg:flex-row">
        <div className="sticky top-0 z-30 flex items-center justify-between border-b border-slate-200 bg-white/90 px-4 py-3 backdrop-blur lg:hidden">
          <button
            type="button"
            onClick={() => setMobileMenuOpen((current) => !current)}
            className="rounded-xl border border-slate-200 bg-white px-4 py-2 text-sm font-semibold text-slate-700"
            aria-expanded={mobileMenuOpen}
            aria-label="Toggle navigation menu"
          >
            Menu
          </button>
          <div className="min-w-0 text-right">
            <p className="max-w-[14rem] whitespace-normal text-right text-sm leading-4 font-medium text-slate-500">
              {APP_NAME}
            </p>
          </div>
        </div>
        <aside
          className={`fixed inset-y-0 left-0 z-40 flex w-72 flex-col border-r border-slate-200 bg-white/95 p-4 shadow-xl backdrop-blur transition-transform duration-200 lg:sticky lg:top-0 lg:z-20 lg:h-screen lg:shadow-none ${
            mobileMenuOpen ? "translate-x-0" : "-translate-x-full lg:translate-x-0"
          } ${isCollapsed ? "lg:w-20" : "lg:w-72"}`}
        >
          <div className="mb-6 flex items-start justify-between gap-3">
            <div className={`min-w-0 ${isCollapsed ? "lg:hidden" : ""}`}>
              <p className="max-w-[11rem] whitespace-normal text-sm leading-5 font-medium text-slate-500">
                {APP_NAME}
              </p>
              <h1 className="mt-3 break-words text-2xl font-semibold text-slate-900">
                Welcome{user?.name ? `, ${user.name}` : ""}
              </h1>
            </div>
            <div className={`flex shrink-0 gap-2 ${isCollapsed ? "w-full justify-between lg:flex-col lg:items-stretch" : ""}`}>
              <button
                type="button"
                onClick={() => setIsCollapsed((current) => !current)}
                className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm font-semibold text-slate-700"
                aria-label={isCollapsed ? "Expand sidebar" : "Collapse sidebar"}
              >
                {isCollapsed ? "›" : "‹"}
              </button>
              <button
                type="button"
                onClick={() => {
                  logout();
                  navigate("/login");
                }}
                className={`${isCollapsed ? "lg:hidden" : ""} rounded-xl border border-slate-300 bg-white px-4 py-2 text-sm text-slate-700 hover:bg-slate-50`}
              >
                Logout
              </button>
            </div>
          </div>

          <div className={`mb-6 rounded-2xl border border-slate-200 bg-slate-50 p-3 ${isCollapsed ? "lg:hidden" : ""}`}>
            <p className="text-xs uppercase tracking-[0.25em] text-slate-500">Account</p>
            <p className="mt-2 break-words text-sm font-medium text-slate-900">{user?.name || user?.email || "User"}</p>
            <p className="mt-1 break-words text-xs text-slate-500">{user?.email || "No account"}</p>
          </div>

          <nav className="flex-1 space-y-2">
            {navItems.map((item) => {
              const shortcut = navShortcuts.find((nav) => nav.to === item.to)?.shortLabel || item.label.slice(0, 2).toUpperCase();
              return (
                <NavLink
                  key={item.to}
                  to={item.to}
                  end={item.to === "/"}
                  title={item.label}
                  className={({ isActive }) =>
                    `flex min-w-0 items-center gap-3 rounded-xl px-4 py-3 text-sm transition ${
                      isActive ? "bg-slate-900 text-white font-semibold" : "text-slate-700 hover:bg-slate-100"
                    } ${isCollapsed ? "lg:justify-center lg:px-3" : ""}`
                  }
                >
                  <span className="inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-full border border-current/10 bg-white/10 text-xs font-semibold">
                    {shortcut}
                  </span>
                  <span className={`${isCollapsed ? "lg:hidden" : ""} min-w-0 break-words`}>{item.label}</span>
                </NavLink>
              );
            })}
          </nav>
        </aside>
        {mobileMenuOpen ? (
          <button
            type="button"
            className="fixed inset-0 z-30 bg-slate-950/30 lg:hidden"
            onClick={() => setMobileMenuOpen(false)}
            aria-label="Close navigation"
          />
        ) : null}
        <main className="min-w-0 flex-1 p-4 sm:p-6 lg:p-8 lg:pl-0">
          <div className="min-w-0 w-full rounded-3xl border border-slate-200 bg-white p-5 shadow-sm backdrop-blur sm:p-8">
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  );
}

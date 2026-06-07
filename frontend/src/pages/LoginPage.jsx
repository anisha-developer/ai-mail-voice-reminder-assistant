import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { apiRequest } from "../lib/api";
import { useAuth } from "../context/AuthContext";

export default function LoginPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();
  const { login } = useAuth();

  const handleSubmit = async (event) => {
    event.preventDefault();
    setError("");
    setLoading(true);
    try {
      const data = await apiRequest("/auth/login", {
        method: "POST",
        body: JSON.stringify({ email, password }),
      });
      login(data.access_token, data.user);
      navigate("/");
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-950 px-4">
      <div className="w-full max-w-md rounded-3xl border border-white/10 bg-slate-900/80 p-8 shadow-soft">
        <p className="text-xs uppercase tracking-[0.35em] text-sky-300">Authentication</p>
        <h1 className="mt-3 text-3xl font-semibold text-white">Sign in</h1>
        <p className="mt-2 text-sm text-slate-400">Access your dashboard and profile.</p>
        <form className="mt-8 space-y-4" onSubmit={handleSubmit}>
          <input
            className="w-full rounded-xl border border-white/10 bg-slate-950 px-4 py-3 text-white outline-none"
            placeholder="Email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
          <input
            className="w-full rounded-xl border border-white/10 bg-slate-950 px-4 py-3 text-white outline-none"
            placeholder="Password"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
          {error ? <p className="rounded-xl border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-200">{error}</p> : null}
          <button disabled={loading} className="w-full rounded-xl bg-sky-400 px-4 py-3 font-semibold text-slate-950 disabled:opacity-60">
            {loading ? "Signing in..." : "Sign in"}
          </button>
        </form>
        <div className="mt-6 text-center text-sm text-slate-400">
          Need an account? <Link className="text-sky-300" to="/signup">Sign up</Link>
        </div>
      </div>
    </div>
  );
}

import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useEffect } from "react";
import { apiRequest } from "../lib/api";
import { useAuth } from "../context/AuthContext";
import { APP_NAME } from "../constants/app";

export default function LoginPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();
  const { login } = useAuth();

  useEffect(() => {
    document.title = APP_NAME;
  }, []);

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
    <div className="flex min-h-screen items-center justify-center bg-[linear-gradient(180deg,_#ffffff_0%,_#f8fafc_100%)] px-4">
      <div className="w-full max-w-md rounded-3xl border border-slate-200 bg-white p-8 shadow-sm">
        <p className="max-w-full break-words text-sm font-medium leading-5 text-slate-500">{APP_NAME}</p>
        <p className="mt-3 text-xs uppercase tracking-[0.35em] text-slate-400">Authentication</p>
        <h1 className="mt-3 text-3xl font-semibold text-slate-900">Sign in</h1>
        <p className="mt-2 text-sm text-slate-600">Access your dashboard and profile.</p>
        <form className="mt-8 space-y-4" onSubmit={handleSubmit}>
          <input
            className="w-full rounded-xl border border-slate-300 bg-white px-4 py-3 text-slate-900 outline-none placeholder:text-slate-400 focus:border-slate-900"
            placeholder="Email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
          <input
            className="w-full rounded-xl border border-slate-300 bg-white px-4 py-3 text-slate-900 outline-none placeholder:text-slate-400 focus:border-slate-900"
            placeholder="Password"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
          {error ? <p className="rounded-xl border border-slate-300 bg-slate-50 p-3 text-sm text-slate-700">{error}</p> : null}
          <button disabled={loading} className="w-full rounded-xl bg-slate-900 px-4 py-3 font-semibold text-white disabled:opacity-60">
            {loading ? "Signing in..." : "Sign in"}
          </button>
        </form>
        <div className="mt-6 text-center text-sm text-slate-600">
          Need an account? <Link className="font-medium text-slate-900 underline decoration-slate-300 underline-offset-4" to="/signup">Sign up</Link>
        </div>
      </div>
    </div>
  );
}

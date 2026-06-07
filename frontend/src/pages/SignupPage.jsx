import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { apiRequest } from "../lib/api";
import { useAuth } from "../context/AuthContext";

const initialForm = {
  name: "",
  email: "",
  password: "",
  phone_number: "",
  timezone: "",
  preferred_language: "",
};

export default function SignupPage() {
  const [form, setForm] = useState(initialForm);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();
  const { login } = useAuth();

  const handleSubmit = async (event) => {
    event.preventDefault();
    setError("");
    setLoading(true);
    try {
      const data = await apiRequest("/auth/signup", {
        method: "POST",
        body: JSON.stringify(form),
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
    <div className="flex min-h-screen items-center justify-center bg-slate-950 px-4 py-10">
      <div className="w-full max-w-2xl rounded-3xl border border-white/10 bg-slate-900/80 p-8 shadow-soft">
        <p className="text-xs uppercase tracking-[0.35em] text-sky-300">Create Account</p>
        <h1 className="mt-3 text-3xl font-semibold text-white">Sign up</h1>
        <p className="mt-2 text-sm text-slate-400">Create your workspace and profile.</p>
        <form className="mt-8 grid gap-4 md:grid-cols-2" onSubmit={handleSubmit}>
          {[
            ["name", "Full name"],
            ["email", "Email"],
            ["password", "Password", "password"],
            ["phone_number", "Phone number"],
            ["timezone", "Timezone"],
            ["preferred_language", "Preferred language"],
          ].map(([key, label, type = "text"]) => (
            <input
              key={key}
              type={type}
              value={form[key]}
              onChange={(e) => setForm({ ...form, [key]: e.target.value })}
              placeholder={label}
              className="w-full rounded-xl border border-white/10 bg-slate-950 px-4 py-3 text-white outline-none"
            />
          ))}
          <div className="md:col-span-2">
            {error ? <p className="mb-3 rounded-xl border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-200">{error}</p> : null}
            <button disabled={loading} className="w-full rounded-xl bg-sky-400 px-4 py-3 font-semibold text-slate-950 disabled:opacity-60">
              {loading ? "Creating account..." : "Sign up"}
            </button>
          </div>
        </form>
        <div className="mt-6 text-center text-sm text-slate-400">
          Already have an account? <Link className="text-sky-300" to="/login">Login</Link>
        </div>
      </div>
    </div>
  );
}


import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useEffect } from "react";
import { apiRequest } from "../lib/api";
import { useAuth } from "../context/AuthContext";
import { APP_NAME } from "../constants/app";

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

  useEffect(() => {
    document.title = APP_NAME;
  }, []);

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
    <div className="flex min-h-screen items-center justify-center bg-[linear-gradient(180deg,_#ffffff_0%,_#f8fafc_100%)] px-4 py-10">
      <div className="w-full max-w-2xl rounded-3xl border border-slate-200 bg-white p-8 shadow-sm">
        <p className="max-w-full break-words text-sm font-medium leading-5 text-slate-500">{APP_NAME}</p>
        <p className="mt-3 text-xs uppercase tracking-[0.35em] text-slate-400">Create Account</p>
        <h1 className="mt-3 text-3xl font-semibold text-slate-900">Sign up</h1>
        <p className="mt-2 text-sm text-slate-600">Create your workspace and profile.</p>
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
              className="w-full rounded-xl border border-slate-300 bg-white px-4 py-3 text-slate-900 outline-none placeholder:text-slate-400 focus:border-slate-900"
            />
          ))}
          <div className="md:col-span-2">
            {error ? <p className="mb-3 rounded-xl border border-slate-300 bg-slate-50 p-3 text-sm text-slate-700">{error}</p> : null}
            <button disabled={loading} className="w-full rounded-xl bg-slate-900 px-4 py-3 font-semibold text-white disabled:opacity-60">
              {loading ? "Creating account..." : "Sign up"}
            </button>
          </div>
        </form>
        <div className="mt-6 text-center text-sm text-slate-600">
          Already have an account? <Link className="font-medium text-slate-900 underline decoration-slate-300 underline-offset-4" to="/login">Login</Link>
        </div>
      </div>
    </div>
  );
}

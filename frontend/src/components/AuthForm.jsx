import { useState } from "react";
import { login, register } from "../api/client.js";

// Login / register screen. Calls onAuthed(user) once a token is obtained.
export default function AuthForm({ onAuthed, notice }) {
  const [mode, setMode] = useState("login"); // "login" | "register"
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const isRegister = mode === "register";

  async function handleSubmit(e) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const user = isRegister
        ? await register(email, password)
        : await login(email, password);
      onAuthed(user);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="auth-screen">
      <div className="auth-card">
        <h1>📰 Newsletter Generator</h1>
        <p className="auth-sub">
          {isRegister ? "Create an account to get started." : "Welcome back."}
        </p>

        {notice && <p className="auth-notice">{notice}</p>}

        <form onSubmit={handleSubmit} className="auth-form">
          <label>
            Email
            <input
              type="email"
              autoComplete="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
          </label>
          <label>
            Password
            <span className="password-field">
              <input
                type={showPassword ? "text" : "password"}
                autoComplete={isRegister ? "new-password" : "current-password"}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                minLength={isRegister ? 6 : undefined}
                required
              />
              <button
                type="button"
                className="password-toggle"
                onClick={() => setShowPassword((s) => !s)}
                aria-label={showPassword ? "Hide password" : "Show password"}
              >
                {showPassword ? "Hide" : "Show"}
              </button>
            </span>
          </label>

          {error && <p className="error">{error}</p>}

          <button type="submit" className="generate-btn" disabled={loading}>
            {loading ? "…" : isRegister ? "Create account" : "Log in"}
          </button>
        </form>

        <p className="auth-toggle">
          {isRegister ? "Already have an account?" : "No account yet?"}{" "}
          <button
            type="button"
            className="linkish"
            onClick={() => {
              setMode(isRegister ? "login" : "register");
              setError("");
            }}
          >
            {isRegister ? "Log in" : "Sign up"}
          </button>
        </p>
      </div>
    </div>
  );
}

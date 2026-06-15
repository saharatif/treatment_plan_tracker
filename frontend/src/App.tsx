import { LogOut, Moon, Sun, UploadCloud, LayoutDashboard } from "lucide-react";
import { FormEvent, useEffect, useState } from "react";
import { supabase } from "./api/supabase";
import { useCurrentUser } from "./api/client";
import { useTheme } from "./hooks/useTheme";
import type { Session } from "@supabase/supabase-js";
import Dashboard from "./pages/Dashboard";
import PatientDetail from "./pages/PatientDetail";
import Upload from "./pages/Upload";

type View = "dashboard" | "upload" | "patient";

export default function App() {
  const [session, setSession] = useState<Session | null>(null);
  const [loading, setLoading] = useState(true);
  const [view, setView] = useState<View>("dashboard");
  const [patientId, setPatientId] = useState<string | null>(null);
  const { theme, toggleTheme } = useTheme();

  useEffect(() => {
    supabase.auth.getSession().then(({ data }) => {
      setSession(data.session);
      setLoading(false);
    });

    const { data: subscription } = supabase.auth.onAuthStateChange((_event, newSession) => {
      setSession(newSession);
    });

    const expire = () => setSession(null);
    window.addEventListener("auth-expired", expire);
    return () => {
      subscription.subscription.unsubscribe();
      window.removeEventListener("auth-expired", expire);
    };
  }, []);

  if (loading) return null;
  if (!session) return <Login theme={theme} onToggleTheme={toggleTheme} />;

  return (
    <div className="app-shell">
      <aside>
        <div className="brand">Cohera Health</div>
        <button className={view === "dashboard" ? "nav active" : "nav"} onClick={() => setView("dashboard")}><LayoutDashboard size={18} /> Dashboard</button>
        <button className={view === "upload" ? "nav active" : "nav"} onClick={() => setView("upload")}><UploadCloud size={18} /> Upload</button>
        <div className="sidebar-footer">
          <button className="theme-toggle" onClick={toggleTheme}>
            {theme === "dark" ? <Sun size={18} /> : <Moon size={18} />}
            {theme === "dark" ? "Light mode" : "Dark mode"}
          </button>
          <UserSummary />
          <button className="nav" onClick={() => supabase.auth.signOut()}><LogOut size={18} /> Sign out</button>
        </div>
      </aside>
      <main>
        {view === "dashboard" ? <Dashboard onSelectPatient={(id) => { setPatientId(id); setView("patient"); }} /> : null}
        {view === "upload" ? <Upload /> : null}
        {view === "patient" ? <PatientDetail patientId={patientId} onBack={() => setView("dashboard")} /> : null}
      </main>
    </div>
  );
}

function UserSummary() {
  const { data } = useCurrentUser();
  if (!data) return null;
  return (
    <div className="sidebar-user">
      <div className="sidebar-user-email">{data.username}</div>
      <div className="sidebar-user-role">{data.role}</div>
    </div>
  );
}

function Login({ theme, onToggleTheme }: { theme: "dark" | "light"; onToggleTheme: () => void }) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setSubmitting(true);
    setError(null);
    const { error: signInError } = await supabase.auth.signInWithPassword({ email, password });
    setSubmitting(false);
    if (signInError) setError(signInError.message);
  }

  return (
    <div className="login-screen">
      <button className="theme-toggle login-theme-toggle" onClick={onToggleTheme}>
        {theme === "dark" ? <Sun size={18} /> : <Moon size={18} />}
        {theme === "dark" ? "Light mode" : "Dark mode"}
      </button>
      <form className="login-panel" onSubmit={submit}>
        <h1>Cohera Health Clinic Console</h1>
        <input value={email} onChange={(event) => setEmail(event.target.value)} type="email" placeholder="Email" autoComplete="username" />
        <input value={password} onChange={(event) => setPassword(event.target.value)} type="password" placeholder="Password" autoComplete="current-password" />
        <button className="primary" disabled={submitting}>{submitting ? "Signing in..." : "Sign in"}</button>
        {error ? <p className="error-text">{error}</p> : null}
      </form>
    </div>
  );
}

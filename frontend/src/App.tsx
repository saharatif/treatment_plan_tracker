import { LogOut, UploadCloud, LayoutDashboard } from "lucide-react";
import { FormEvent, useEffect, useState } from "react";
import { clearToken, getToken, setToken, useLogin } from "./api/client";
import Dashboard from "./pages/Dashboard";
import PatientDetail from "./pages/PatientDetail";
import Upload from "./pages/Upload";

type View = "dashboard" | "upload" | "patient";

export default function App() {
  const [authed, setAuthed] = useState(Boolean(getToken()));
  const [view, setView] = useState<View>("dashboard");
  const [patientId, setPatientId] = useState<string | null>(null);

  useEffect(() => {
    const expire = () => setAuthed(false);
    window.addEventListener("auth-expired", expire);
    return () => window.removeEventListener("auth-expired", expire);
  }, []);

  if (!authed) return <Login onLogin={() => setAuthed(true)} />;

  return (
    <div className="app-shell">
      <aside>
        <div className="brand">10 Orbs</div>
        <button className={view === "dashboard" ? "nav active" : "nav"} onClick={() => setView("dashboard")}><LayoutDashboard size={18} /> Dashboard</button>
        <button className={view === "upload" ? "nav active" : "nav"} onClick={() => setView("upload")}><UploadCloud size={18} /> Upload</button>
        <button className="nav" onClick={() => { clearToken(); setAuthed(false); }}><LogOut size={18} /> Sign out</button>
      </aside>
      <main>
        {view === "dashboard" ? <Dashboard onSelectPatient={(id) => { setPatientId(id); setView("patient"); }} /> : null}
        {view === "upload" ? <Upload /> : null}
        {view === "patient" ? <PatientDetail patientId={patientId} onBack={() => setView("dashboard")} /> : null}
      </main>
    </div>
  );
}

function Login({ onLogin }: { onLogin: () => void }) {
  const login = useLogin();
  const [username, setUsername] = useState("clinician");
  const [password, setPassword] = useState("");
  const [patientId, setPatientId] = useState("");

  function submit(event: FormEvent) {
    event.preventDefault();
    login.mutate({ username, password, patient_id: patientId || undefined }, {
      onSuccess: (data) => {
        setToken(data.access_token);
        onLogin();
      }
    });
  }

  return (
    <div className="login-screen">
      <form className="login-panel" onSubmit={submit}>
        <h1>10 Orbs Clinic Console</h1>
        <select value={username} onChange={(event) => setUsername(event.target.value)}>
          <option value="clinician">Clinician</option>
          <option value="coordinator">Coordinator</option>
          <option value="billing">Billing</option>
          <option value="patient">Patient</option>
        </select>
        <input value={password} onChange={(event) => setPassword(event.target.value)} type="password" placeholder="Password" />
        <input value={patientId} onChange={(event) => setPatientId(event.target.value)} placeholder="Patient token" />
        <button className="primary">Sign in</button>
        {login.error ? <p className="error-text">Sign in failed.</p> : null}
      </form>
    </div>
  );
}

import { Download, RotateCcw } from "lucide-react";
import { downloadReport, useCompleteOrb, usePatientDetail, useSetOrbStatus } from "../api/client";
import OrbRow from "../components/OrbRow";
import StatusBadge from "../components/StatusBadge";

export default function PatientDetail({ patientId, onBack }: { patientId: string | null; onBack: () => void }) {
  const detail = usePatientDetail(patientId);
  const complete = useCompleteOrb();
  const setStatus = useSetOrbStatus();
  const plan = detail.data?.plan;
  const orbs = detail.data?.orbs ?? [];

  if (!patientId) return null;

  return (
    <section className="panel wide">
      <div className="toolbar">
        <button className="icon-button" onClick={onBack} title="Back"><RotateCcw size={18} /></button>
        <div>
          <div className="panel-title">{patientId}</div>
          {plan ? <p className="muted">{plan.plan_id} · <StatusBadge value={String(plan.status)} /></p> : null}
        </div>
        {plan?.status === "closed" ? (
          <button className="icon-button" title="Report" onClick={() => downloadReport(String(plan.plan_id))}>
            <Download size={18} />
          </button>
        ) : null}
      </div>
      <OrbRow orbs={orbs} />
      <div className="stack">
        {orbs.map((orb) => (
          <div className="orb-card" key={String(orb.orb_ref)}>
            <div>
              <strong>{orb.orb_number}. {orb.title ?? orb.catalog_code ?? orb.orb_ref}</strong>
              <p className="muted">{orb.category ?? "Unmapped"} · target {orb.target_date ?? "N/A"}</p>
              {orb.notes ? <p>{orb.notes}</p> : null}
            </div>
            <div className="orb-actions">
              <StatusBadge value={String(orb.status)} />
              <button className="small-button" onClick={() => complete.mutate({ orbRef: String(orb.orb_ref) })}>Complete</button>
              <button className="small-button" onClick={() => setStatus.mutate({ orbRef: String(orb.orb_ref), status: "in_progress" })}>Start</button>
              <button className="small-button" onClick={() => setStatus.mutate({ orbRef: String(orb.orb_ref), status: "skipped" })}>Skip</button>
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}

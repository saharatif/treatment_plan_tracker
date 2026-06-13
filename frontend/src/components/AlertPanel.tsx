import { AlertTriangle } from "lucide-react";
import type { DashboardPlan } from "../api/client";

export default function AlertPanel({ items }: { items: DashboardPlan[] }) {
  return (
    <section className="panel">
      <div className="panel-title">
        <AlertTriangle size={18} />
        At Risk
      </div>
      <div className="stack">
        {items.length === 0 ? <p className="muted">No at-risk active plans.</p> : null}
        {items.map((item) => (
          <div className="alert-item" key={item.plan_id}>
            <strong>{item.patient_id}</strong>
            <span>{item.completed}/10 complete</span>
            <span>{item.days_remaining ?? item.days_left} days</span>
          </div>
        ))}
      </div>
    </section>
  );
}

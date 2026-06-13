import { Activity, CalendarClock, ClipboardList } from "lucide-react";
import { DashboardPlan, useAtRisk, useDashboard } from "../api/client";
import AlertPanel from "../components/AlertPanel";
import MetricCard from "../components/MetricCard";
import StatusBadge from "../components/StatusBadge";

export default function Dashboard({ onSelectPatient }: { onSelectPatient: (patientId: string) => void }) {
  const dashboard = useDashboard();
  const atRisk = useAtRisk();
  const plans = dashboard.data ?? [];
  const completed = plans.reduce((sum, plan) => sum + Number(plan.completed), 0);

  return (
    <div className="page-grid">
      <section className="main-col">
        <div className="metrics-grid">
          <MetricCard label="Active Plans" value={plans.length} icon={<ClipboardList size={18} />} />
          <MetricCard label="Completed Orbs" value={completed} icon={<Activity size={18} />} />
          <MetricCard label="At Risk" value={(atRisk.data ?? []).length} icon={<CalendarClock size={18} />} />
        </div>
        <div className="panel">
          <div className="panel-title">Clinic Dashboard</div>
          <div className="table">
            <div className="table-head grid-cols-6">
              <span>Patient</span><span>Plan</span><span>State</span><span>Orbs</span><span>Days</span><span>Status</span>
            </div>
            {plans.map((plan: DashboardPlan) => (
              <button className="table-row grid-cols-6" key={plan.plan_id} onClick={() => onSelectPatient(plan.patient_id)}>
                <span>{plan.patient_id}</span>
                <span>{plan.plan_id}</span>
                <span><StatusBadge value={plan.status} /></span>
                <span>{plan.completed}/10</span>
                <span>{plan.days_remaining}</span>
                <span><StatusBadge value={plan.plan_status} /></span>
              </button>
            ))}
          </div>
        </div>
      </section>
      <AlertPanel items={atRisk.data ?? []} />
    </div>
  );
}

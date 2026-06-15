function daysBetween(a: Date, b: Date) {
  const ms = b.setHours(0, 0, 0, 0) - a.setHours(0, 0, 0, 0);
  return Math.round(ms / (1000 * 60 * 60 * 24));
}

function clampPct(value: number) {
  return Math.min(100, Math.max(0, value));
}

export default function PlanProgress({
  completed,
  total,
  planStart,
  targetDate,
  hardStop
}: {
  completed: number;
  total: number;
  planStart: string;
  targetDate: string;
  hardStop: string;
}) {
  const start = new Date(planStart);
  const target = new Date(targetDate);
  const stop = new Date(hardStop);
  const today = new Date();

  const totalSpan = Math.max(daysBetween(new Date(start), new Date(stop)), 1);
  const targetPct = clampPct((daysBetween(new Date(start), new Date(target)) / totalSpan) * 100);
  const todayPct = clampPct((daysBetween(new Date(start), new Date(today)) / totalSpan) * 100);
  const completionPct = total ? clampPct((completed / total) * 100) : 0;
  const daysLeft = daysBetween(new Date(today), new Date(target));
  const overdue = daysLeft < 0;

  return (
    <div className="plan-progress">
      <div className="plan-progress-header">
        <span><strong>{completed}/{total}</strong> orbs complete</span>
        <span className={overdue ? "error-text" : "muted"}>
          {overdue ? `${Math.abs(daysLeft)} days overdue` : `${daysLeft} days left`}
        </span>
      </div>
      <div className="plan-progress-track">
        <div className="plan-progress-zone" style={{ left: `${targetPct}%`, right: 0 }} />
        <div className="plan-progress-fill" style={{ width: `${completionPct}%` }} />
        <div
          className={`plan-progress-marker ${overdue ? "danger" : ""}`}
          style={{ left: `${todayPct}%` }}
          title={`Today (day ${daysBetween(new Date(start), new Date(today))})`}
        />
      </div>
      <div className="plan-progress-labels">
        <span style={{ left: `${targetPct}%` }}>2wk · target</span>
        <span className="end">3wk · extended period start</span>
      </div>
    </div>
  );
}

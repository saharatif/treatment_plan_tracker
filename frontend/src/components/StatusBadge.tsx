const tones: Record<string, string> = {
  "ON TRACK": "bg-emerald-100 text-emerald-800",
  "IN GRACE": "bg-amber-100 text-amber-800",
  OVERDUE: "bg-rose-100 text-rose-800",
  active: "bg-sky-100 text-sky-800",
  pending_enrollment: "bg-slate-100 text-slate-700",
  complete: "bg-emerald-100 text-emerald-800",
  completed: "bg-emerald-100 text-emerald-800",
  in_progress: "bg-blue-100 text-blue-800",
  skipped: "bg-amber-100 text-amber-800",
  locked: "bg-zinc-200 text-zinc-700",
  closed: "bg-zinc-200 text-zinc-700",
  extended: "bg-rose-100 text-rose-800",
  in_grace: "bg-amber-100 text-amber-800"
};

export default function StatusBadge({ value }: { value: string }) {
  return <span className={`badge ${tones[value] ?? "bg-slate-100 text-slate-700"}`}>{value.replace("_", " ")}</span>;
}

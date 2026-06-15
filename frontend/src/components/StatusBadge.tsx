const tones: Record<string, string> = {
  "ON TRACK": "tone-success",
  "IN GRACE": "tone-warning",
  OVERDUE: "tone-danger",
  active: "tone-accent",
  pending_enrollment: "tone-neutral",
  complete: "tone-success",
  completed: "tone-success",
  in_progress: "tone-info",
  skipped: "tone-warning",
  locked: "tone-neutral",
  closed: "tone-neutral",
  extended: "tone-danger",
  in_grace: "tone-warning"
};

export default function StatusBadge({ value }: { value: string }) {
  return <span className={`badge ${tones[value] ?? "tone-neutral"}`}>{value.replace("_", " ")}</span>;
}

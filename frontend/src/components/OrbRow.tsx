const colors: Record<string, string> = {
  pending: "bg-slate-300",
  in_progress: "bg-blue-500",
  complete: "bg-emerald-500",
  skipped: "bg-amber-500",
  locked: "bg-zinc-700"
};

export default function OrbRow({ orbs }: { orbs: Array<Record<string, string | number | null>> }) {
  return (
    <div className="orb-row" aria-label="orb progress">
      {orbs.map((orb) => (
        <span
          key={String(orb.orb_ref)}
          title={`${orb.orb_number}: ${orb.status}`}
          className={`orb-dot ${colors[String(orb.status)] ?? "bg-slate-300"}`}
        />
      ))}
    </div>
  );
}

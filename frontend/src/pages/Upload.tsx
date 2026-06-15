import { FileUp, Send } from "lucide-react";
import { FormEvent, useState } from "react";
import { useConfirmBilling, useReviewQueue, useReviewQueueItem, useUploadPlan } from "../api/client";

const EMPTY_PII = { name: "", dob: "", address: "", phone: "", email: "" };

export default function Upload() {
  const [file, setFile] = useState<File | null>(null);
  const [pii, setPii] = useState(EMPTY_PII);
  const upload = useUploadPlan();
  const confirm = useConfirmBilling();
  const result = upload.data as Record<string, any> | undefined;

  function updatePii(field: keyof typeof EMPTY_PII, value: string) {
    setPii((current) => ({ ...current, [field]: value }));
  }

  function submit(event: FormEvent) {
    event.preventDefault();
    if (!file) return;
    const hasPii = Object.values(pii).some((value) => value.trim() !== "");
    upload.mutate({ file, piiJson: hasPii ? JSON.stringify(pii) : undefined });
  }

  return (
    <section className="panel wide">
      <div className="panel-title"><FileUp size={18} /> Upload Processing PDF</div>
      <form className="upload-form" onSubmit={submit}>
        <input className="file-input" type="file" accept="application/pdf" onChange={(event) => setFile(event.target.files?.[0] ?? null)} />
        <div className="pii-fields">
          <input placeholder="Patient name" value={pii.name} onChange={(event) => updatePii("name", event.target.value)} />
          <input type="date" placeholder="Date of birth" value={pii.dob} onChange={(event) => updatePii("dob", event.target.value)} />
          <input placeholder="Address" value={pii.address} onChange={(event) => updatePii("address", event.target.value)} />
          <input placeholder="Phone" value={pii.phone} onChange={(event) => updatePii("phone", event.target.value)} />
          <input type="email" placeholder="Email" value={pii.email} onChange={(event) => updatePii("email", event.target.value)} />
        </div>
        <button className="primary" disabled={!file || upload.isPending}><Send size={18} /> Submit</button>
      </form>
      {upload.error ? <pre className="error-box">{String(upload.error)}</pre> : null}
      {result ? (
        <div className="result-box">
          <strong>{String(result.status)}</strong>
          <pre>{JSON.stringify(result, null, 2)}</pre>
          {result.plan_id ? (
            <button className="primary" disabled={confirm.isPending} onClick={() => confirm.mutate(String(result.plan_id))}>
              {confirm.isPending ? "Confirming..." : "Confirm Billing"}
            </button>
          ) : null}
          {confirm.error ? <pre className="error-box">{String(confirm.error)}</pre> : null}
          {confirm.data ? <pre className="confirm-result">{JSON.stringify(confirm.data, null, 2)}</pre> : null}
        </div>
      ) : null}
      <ReviewQueue />
    </section>
  );
}

function ReviewQueue() {
  const queue = useReviewQueue();
  const [selected, setSelected] = useState<string | null>(null);
  const detail = useReviewQueueItem(selected);
  const items = queue.data ?? [];

  if (items.length === 0) return null;

  return (
    <div className="review-queue">
      <div className="panel-title">Needs Review ({items.length})</div>
      <ul>
        {items.map((item) => (
          <li key={item.review_id}>
            <button className="link" onClick={() => setSelected(item.review_id)}>{item.filename}</button>
            <span className="muted"> — {item.review_id}</span>
            <ul>
              {item.errors.map((error, index) => (
                <li key={index} className="error-text">{error}</li>
              ))}
            </ul>
          </li>
        ))}
      </ul>
      {detail.data ? (
        <pre className="result-box">{JSON.stringify(detail.data.parsed_plan, null, 2)}</pre>
      ) : null}
    </div>
  );
}

import { FileUp, Send } from "lucide-react";
import { FormEvent, useState } from "react";
import { useConfirmBilling, useUploadPlan } from "../api/client";

export default function Upload() {
  const [file, setFile] = useState<File | null>(null);
  const [piiJson, setPiiJson] = useState("");
  const upload = useUploadPlan();
  const confirm = useConfirmBilling();
  const result = upload.data as Record<string, any> | undefined;

  function submit(event: FormEvent) {
    event.preventDefault();
    if (file) upload.mutate({ file, piiJson: piiJson.trim() || undefined });
  }

  return (
    <section className="panel wide">
      <div className="panel-title"><FileUp size={18} /> Upload Processing PDF</div>
      <form className="upload-form" onSubmit={submit}>
        <input className="file-input" type="file" accept="application/pdf" onChange={(event) => setFile(event.target.files?.[0] ?? null)} />
        <textarea value={piiJson} onChange={(event) => setPiiJson(event.target.value)} placeholder='{"name":"","dob":"","address":"","phone":"","email":""}' />
        <button className="primary" disabled={!file || upload.isPending}><Send size={18} /> Submit</button>
      </form>
      {upload.error ? <pre className="error-box">{String(upload.error)}</pre> : null}
      {result ? (
        <div className="result-box">
          <strong>{String(result.status)}</strong>
          <pre>{JSON.stringify(result, null, 2)}</pre>
          {result.plan_id ? <button className="primary" onClick={() => confirm.mutate(String(result.plan_id))}>Confirm Billing</button> : null}
        </div>
      ) : null}
    </section>
  );
}

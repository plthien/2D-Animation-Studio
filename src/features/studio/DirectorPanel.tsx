import {useState} from 'react';
import {apiClient,type Artifact,type DirectorPackage,type DirectorValidation} from '../../api/client';

const button='rounded-xl border border-white/15 px-3 py-2 text-sm text-slate-100 hover:bg-white/10 disabled:opacity-40';
export function DirectorPanel({projectId,headRevision,onUpdate}:{projectId:string;headRevision:number;onUpdate:()=>void}){
 const [pkg,setPkg]=useState<DirectorPackage|null>(null);
 const [json,setJson]=useState('');
 const [report,setReport]=useState<DirectorValidation|null>(null);
 const [draft,setDraft]=useState<Artifact|null>(null);
 const [history,setHistory]=useState<Artifact[]>([]);
 const [busy,setBusy]=useState(false);
 const [status,setStatus]=useState('');
 const [error,setError]=useState('');
 const run=async(action:()=>Promise<void>)=>{
  setBusy(true);setError('');
  try{await action();}catch(e){setError(e instanceof Error?e.message:String(e));}
  finally{setBusy(false);}
 };
 const newPrompt=()=>run(async()=>{const data=await apiClient.directorPrompt(projectId);
  setPkg(data);setJson('');setDraft(null);setReport(null);setStatus('Source-bound Director prompt reserved');});
 const copy=async()=>{
  if(!pkg)return;
  setError('');
  try{await navigator.clipboard.writeText(pkg.prompt_text);setStatus('Complete Director prompt copied');}
  catch(e){setError('Clipboard permission denied: '+String(e));}
 };
 const check=()=>run(async()=>{
  if(!pkg)throw Error('Reserve a Director prompt first');
  const result=await apiClient.directorValidate(projectId,pkg.reservation_id,JSON.parse(json) as Record<string,unknown>);
  setReport(result);setStatus(result.valid?'Director JSON validated':'Director JSON rejected');
 });
 const save=()=>run(async()=>{
  if(!pkg)throw Error('Reserve a Director prompt first');
  const doc=JSON.parse(json) as Record<string,unknown>;
  const valid=await apiClient.directorValidate(projectId,pkg.reservation_id,doc);
  setReport(valid);
  if(!valid.valid){setStatus('Validation failed');return;}
  setDraft(await apiClient.directorImport(projectId,pkg.reservation_id,doc));
  onUpdate();setStatus('Immutable Director draft imported; approval required');
 });
 const approve=()=>run(async()=>{
  if(!draft)throw Error('Import a valid draft');
  await apiClient.directorApprove(projectId,draft.artifact_id,headRevision,draft.sha256);
  setStatus('Approved current AnimationPlan');setDraft(null);
  onUpdate();setHistory((await apiClient.directorHistory(projectId)).items);
 });
 const load=()=>run(async()=>{setHistory((await apiClient.directorHistory(projectId)).items);});
 const open=(a:Artifact)=>run(async()=>{
  const res=await apiClient.directorRead(projectId,a.artifact_id);
  setJson(JSON.stringify(res.document,null,2));setPkg(null);setReport(null);
  setDraft(a.approval_status==='draft'?a:null);setStatus('Opened immutable revision');
 });
 return <section className="space-y-4" data-testid="c5-director">
  <p className="text-sm text-slate-300">External Animation Director: generate the exact frozen prompt, author JSON outside the app, validate, import, review and approve. No hidden AI API.</p>
  <div className="flex flex-wrap gap-2">
   <button className={button} disabled={busy} onClick={newPrompt}>Create Director prompt</button>
   <button className={button} disabled={busy} onClick={load}>Revision history</button>
  </div>
  {pkg&&<div className="space-y-2 rounded-xl border border-white/10 p-3 text-sm text-slate-300">
   <p>Reserved: {pkg.reservation_id} · Revision {pkg.revision}</p>
   <p className="break-all text-xs">Source fingerprint: {pkg.source_fingerprint}</p>
   <button className={button} onClick={()=>void copy()}>Copy complete Director prompt</button>
  </div>}
  <label className="block text-sm text-slate-300">AnimationPlan JSON
   <textarea rows={13} value={json} onChange={e=>{setJson(e.target.value);setReport(null);}} placeholder="Paste animation_plan.v1 JSON"
    className="mt-2 w-full rounded-xl border border-white/10 bg-slate-950 p-3 font-mono text-xs text-slate-100"/>
  </label>
  <div className="flex flex-wrap gap-2">
   <button className={button} disabled={busy||!pkg||!json} onClick={check}>Validate plan</button>
   <button className={button} disabled={busy||!pkg||!json} onClick={save}>Import immutable draft</button>
   <button className={button} disabled={busy||!draft} onClick={approve}>Approve draft</button>
  </div>
  {report&&<div className="space-y-1 text-xs text-amber-200">
   <p className={report.valid?'text-emerald-300':'text-amber-300'}>{report.valid?'Valid':'Rejected'}</p>
   {report.issues.map((i,j)=><p key={j}>{i.path}: {i.message}</p>)}
  </div>}
  {error&&<p role="alert" className="text-sm text-red-300">{error}</p>}
  {status&&<p role="status" className="text-sm text-emerald-300">{status}</p>}
  {history.map(a=><button key={a.artifact_id} className="block w-full rounded-lg border border-white/10 p-3 text-left text-xs text-slate-200"
     onClick={()=>void open(a)}>Revision {a.revision} · {a.approval_status} · {a.artifact_id}</button>)}
 </section>;
}

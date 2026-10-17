import {useState} from 'react';
import {apiClient,type Artifact,type AuthoringPackage,type ValidationReport} from '../../api/client';

const KINDS=[{value:'topic-ideas',label:'Topic Ideas'},{value:'script',label:'Script'},
  {value:'script-analysis',label:'Script Analysis (optional)'},{value:'shot-plan',label:'ShotPlan'}];
export function AuthoringPanel({projectId,headRevision,onCommitted}:{projectId:string;headRevision:number;onCommitted:()=>void}){
 const [kind,setKind]=useState('topic-ideas');
 const [pkg,setPkg]=useState<AuthoringPackage|null>(null);
 const [json,setJson]=useState('');
 const [report,setReport]=useState<ValidationReport|null>(null);
 const [draft,setDraft]=useState<Artifact|null>(null);
 const [history,setHistory]=useState<Artifact[]>([]);
 const [error,setError]=useState('');
 const [busy,setBusy]=useState(false);
 const [copyResult,setCopyResult]=useState('');
 const go=async(fn:()=>Promise<void>)=>{
  setBusy(true);setError('');
  try{await fn();}catch(err){setError(err instanceof Error?err.message:String(err));}
  finally{setBusy(false);}
 };
 const newPrompt=()=>go(async()=>{
  const result=await apiClient.authoringPrompt(projectId,kind);
  setPkg(result);setJson('');setReport(null);setDraft(null);setCopyResult('');
 });
 const check=()=>go(async()=>{
  if(!pkg)throw new Error('Create a source-bound prompt first');
  setReport(await apiClient.authoringValidate(projectId,kind,pkg.reservation_id,JSON.parse(json)));
 });
 const save=()=>go(async()=>{
  if(!pkg)throw new Error('Create a source-bound prompt first');
  const doc=JSON.parse(json) as Record<string,unknown>;
  const validation=await apiClient.authoringValidate(projectId,kind,pkg.reservation_id,doc);
  setReport(validation);
  if(!validation.valid)return;
  const result=await apiClient.authoringImport(projectId,kind,pkg.reservation_id,doc);
  setDraft(result);onCommitted();
 });
 const approve=()=>go(async()=>{
  if(!draft)throw new Error('Select a draft first');
  const liveHead=(await apiClient.workflow(projectId)).stages.find(x=>x.stage_key==='authoring');
  await apiClient.authoringApprove(projectId,kind,draft.artifact_id,liveHead?.head_revision??headRevision,draft.sha256);
  setDraft(null);onCommitted();
  setHistory((await apiClient.authoringHistory(projectId,kind)).items);
 });
 const loadHistory=()=>go(async()=>{setHistory((await apiClient.authoringHistory(projectId,kind)).items);});
 const open=(a:Artifact)=>go(async()=>{
  const entry=await apiClient.authoringDocument(projectId,a.artifact_id);
  setPkg(null);setJson(JSON.stringify(entry.document,null,2));setDraft(a.approval_status==='draft'?a:null);
  setReport(null);
 });
 const btn='rounded-xl border border-white/15 px-4 py-2 text-sm text-slate-100 hover:bg-white/10 disabled:opacity-40';
 return <div className="space-y-4" data-testid="c3-authoring">
  <p className="text-sm text-slate-400">External LLM workflow: generate a frozen prompt, obtain JSON externally, validate, review and approve its immutable revision. Script Analysis is optional.</p>
  <div className="flex flex-wrap items-center gap-2">
   <label htmlFor="authoring-kind" className="text-xs text-slate-300">Artifact</label>
   <select id="authoring-kind" value={kind} onChange={e=>{setKind(e.target.value);setPkg(null);setDraft(null);setReport(null);setJson('');setHistory([]);setCopyResult('');}} className="rounded-lg bg-slate-800 px-3 py-2 text-slate-100">
    {KINDS.map(k=><option value={k.value} key={k.value}>{k.label}</option>)}
   </select>
   <button className={btn} disabled={busy} onClick={newPrompt}>Create prompt reservation</button>
   <button className={btn} disabled={busy} onClick={loadHistory}>Revision history</button>
  </div>
  {error&&<p role="alert" className="text-sm text-red-300">{error}</p>}
  {pkg&&<div className="space-y-2 rounded-xl border border-cyan-500/20 p-4">
   <p className="text-sm text-cyan-200">Reserved revision {pkg.revision} · {pkg.reservation_id}</p>
   <p className="text-xs text-slate-400">Expires {pkg.expires_at}</p>
   <button className={btn} onClick={()=>void (async()=>{
    try{await navigator.clipboard.writeText(pkg.prompt_text);setCopyResult('Complete prompt copied');}
    catch(err){setCopyResult('Clipboard write failed: '+(err instanceof Error?err.message:String(err)));}
   })()}>Copy complete prompt</button>
   {copyResult&&<p role="status" className="text-xs text-slate-300">{copyResult}</p>}
  </div>}
  <label className="block text-sm text-slate-300">External JSON response
   <textarea value={json} onChange={e=>{setJson(e.target.value);setReport(null);}} rows={12}
    className="mt-2 w-full rounded-xl border border-white/10 bg-slate-950 p-3 font-mono text-xs text-slate-100"
    placeholder="Paste JSON returned by the external LLM"/>
  </label>
  <div className="flex flex-wrap gap-2">
   <button className={btn} disabled={busy||!pkg||!json} onClick={check}>Validate JSON</button>
   <button className={btn} disabled={busy||!pkg||!json} onClick={save}>Import immutable draft</button>
   <button className={btn} disabled={busy||!draft||draft.approval_status!=='draft'} onClick={approve}>Approve selected draft</button>
  </div>
  {report&&<div className="rounded-xl border border-white/10 p-3 text-sm">
   <p className={report.valid?'text-emerald-300':'text-amber-300'}>{report.valid?'JSON valid':'Validation failed'}</p>
   {report.issues.map((issue,i)=><p key={i} className="text-slate-300">{issue.path}: {issue.message}</p>)}
  </div>}
  {draft&&<p className="text-sm text-slate-200">Selected draft: {draft.artifact_id} · SHA {draft.sha256}</p>}
  {history.length>0&&<div className="space-y-2">
   <h4 className="text-sm font-semibold text-slate-100">Stored revisions</h4>
   {history.map(a=><button className="block w-full rounded-lg border border-white/10 p-3 text-left text-xs text-slate-300 hover:bg-white/5" onClick={()=>open(a)} key={a.artifact_id}>
    {a.kind} · r{a.revision} · {a.approval_status} · {a.artifact_id}
   </button>)}
  </div>}
 </div>;
}

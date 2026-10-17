import {useEffect,useState} from 'react';
import {apiClient,type AssetRequirement,type GLabsConfig,type GLabsOperation,type GLabsQuote,type ImageCandidate} from '../../api/client';
export function GLabsPanel({projectId,requirement,onCandidate}:{projectId:string;requirement?:AssetRequirement;onCandidate:(v:ImageCandidate)=>void}){
 const [config,setConfig]=useState<GLabsConfig|null>(null);
 const [prompt,setPrompt]=useState('');
 const [cost,setCost]=useState('1');
 const [model,setModel]=useState('nano_banana_2');
 const [ratio,setRatio]=useState('1:1');
 const [quote,setQuote]=useState<GLabsQuote|null>(null);
 const [approved,setApproved]=useState(false);
 const [key,setKey]=useState('');
 const [operation,setOperation]=useState<GLabsOperation|null>(null);
 const [error,setError]=useState('');
 const [providerTaskId,setProviderTaskId]=useState('');
 const [busy,setBusy]=useState(false);
 useEffect(()=>{void Promise.all([apiClient.glabsConfig(projectId),apiClient.glabsOperations(projectId)]).then(async([cfg,ops])=>{
  setConfig(cfg);
  if(ops.items.length){const x=await apiClient.glabsStatus(projectId,ops.items[0].operation_id);
   setOperation(x);if(x.result?.candidate)onCandidate(x.result.candidate);}
 }).catch(e=>setError(String(e)));},[projectId]);
 useEffect(()=>{setQuote(null);setApproved(false);},[requirement?.requirement_id]);
 const act=async(run:()=>Promise<void>)=>{
  setBusy(true);setError('');
  try{await run();}catch(e){setError(e instanceof Error?e.message:String(e));}
  finally{setBusy(false);}
 };
 const btn='rounded-xl border border-white/15 px-3 py-2 text-sm text-slate-100 disabled:opacity-40';
 return <section className="space-y-3 rounded-xl border border-white/10 p-4" data-testid="c3-glabs">
  <h4 className="font-semibold">G-Labs image generation (optional paid provider)</h4>
  <p className="text-xs text-slate-400">Donor protocol; live test deferred to C7. No paid requests on app startup, quote preparation, or project creation.</p>
  <p className="text-xs text-slate-300">Provider: {config===null?'Checking…':config.configured?'Configured, not live-verified':'Not configured — set local GLABS_API_KEY and GLABS_BASE_URL'}</p>
  {error&&<p role="alert" className="text-red-300">{error}</p>}
  <textarea aria-label="G-Labs prompt" className="w-full rounded-lg bg-slate-900 p-3" rows={3} placeholder="Image prompt for selected requirement" value={prompt} onChange={e=>{setPrompt(e.target.value);setQuote(null);}}/>
  <div className="flex flex-wrap gap-2 text-xs">
   <select aria-label="G-Labs model" className="rounded-lg bg-slate-800 p-2" value={model} onChange={e=>{setModel(e.target.value);setQuote(null);}}><option value="nano_banana_2">Nano Banana 2</option><option value="nano_banana_pro">Nano Banana Pro</option></select>
   <select aria-label="Aspect ratio" className="rounded-lg bg-slate-800 p-2" value={ratio} onChange={e=>{setRatio(e.target.value);setQuote(null);}}>{['1:1','3:4','4:3','9:16','16:9'].map(v=><option key={v}>{v}</option>)}</select>
   <label className="text-slate-300">Cost ceiling (USD) <input aria-label="Cost ceiling USD" type="number" min="0.01" max="100" step="0.01" className="w-20 rounded-lg bg-slate-800 p-2" value={cost} onChange={e=>{setCost(e.target.value);setQuote(null);}}/></label>
  </div>
  <button className={btn} disabled={busy||!config?.configured||!requirement||!prompt.trim()} onClick={()=>void act(async()=>{
   const x=await apiClient.glabsPrepare(projectId,{requirement_id:requirement!.requirement_id,prompt,negative_prompt:'',model,aspect_ratio:ratio,cost_ceiling_usd:Number(cost)});
   setQuote(x);setKey(crypto.randomUUID());setApproved(false);
  })}>Prepare frozen paid quote</button>
  {quote&&<div className="space-y-2 rounded-lg border border-amber-500/20 p-3 text-xs">
   <p className="text-amber-200">Provider cost estimate unavailable. Owner authorization limit: USD {quote.cost_ceiling_usd.toFixed(2)}. This is NOT a provider-enforced billing cap; confirm actual provider pricing before spending.</p>
   <p className="break-all font-mono">Attempt fingerprint: {quote.fingerprint}</p>
   <label className="flex items-start gap-2"><input type="checkbox" checked={approved} onChange={e=>setApproved(e.target.checked)}/> I explicitly authorize ONE paid G-Labs request with the displayed exact input and ceiling.</label>
   <button className={btn} disabled={busy||!approved} onClick={()=>void act(async()=>{
    const item=await apiClient.glabsConfirm(projectId,quote,key);
    setQuote(null);setOperation(item);
    const updated=await apiClient.glabsAdvance(projectId,item.operation_id);
    setOperation(updated);if(updated.result?.candidate)onCandidate(updated.result.candidate);
   })}>Confirm and submit this paid attempt</button>
  </div>}
  {operation&&<div className="space-y-2 text-xs">
   <p>Durable operation: {operation.operation_id} · {operation.status}</p>
   {operation.status==='unknown'&&<div className="space-y-2">
    <p className="text-amber-200">Submission acknowledgement unknown. No automatic resubmit; retrieve the exact task ID from your local G-Labs service first.</p>
    <input aria-label="Known G-Labs task ID" placeholder="8-character provider hex task ID" value={providerTaskId} onChange={e=>setProviderTaskId(e.target.value)} className="w-full rounded-lg bg-slate-800 p-2 font-mono"/>
    <button className={btn} disabled={busy||!/^[0-9a-fA-F]{8}$/.test(providerTaskId)} onClick={()=>void act(async()=>{
     const x=await apiClient.glabsReconcile(projectId,operation.operation_id,providerTaskId);
     setOperation(x);if(x.result?.candidate)onCandidate(x.result.candidate);
    })}>Verify this existing provider task (no new paid submit)</button>
   </div>}
   {operation.error&&<p className="text-red-300">Error: {operation.error.code}</p>}
   <div className="flex flex-wrap gap-2">
    <button className={btn} disabled={busy} onClick={()=>void act(async()=>{setOperation(await apiClient.glabsStatus(projectId,operation.operation_id));})}>Refresh</button>
    {operation.status==='running'&&<button className={btn} disabled={busy} onClick={()=>void act(async()=>{
     const x=await apiClient.glabsAdvance(projectId,operation.operation_id);
     setOperation(x);if(x.result?.candidate)onCandidate(x.result.candidate);
    })}>Poll existing provider task</button>}
    {(operation.status==='queued'||operation.status==='running'||operation.status==='unknown')&&<button className={btn} disabled={busy} onClick={()=>void act(async()=>{setOperation(await apiClient.glabsCancel(projectId,operation.operation_id));})}>Cancel</button>}
   </div>
  </div>}
 </section>;
}

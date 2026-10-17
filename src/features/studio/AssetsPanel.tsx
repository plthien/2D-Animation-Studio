import {useEffect,useState} from 'react';
import {apiClient,type AssetResolution,type AssetVersion,type ImageCandidate} from '../../api/client';
import {GLabsPanel} from './GLabsPanel';
export function AssetsPanel({projectId,channelId,mode}:{projectId:string;channelId:string;mode:'resolver'|'generation'}){
 const [state,setState]=useState<AssetResolution|null>(null);
 const [versions,setVersions]=useState<AssetVersion[]>([]);
 const [candidate,setCandidate]=useState<ImageCandidate|null>(null);
 const [selected,setSelected]=useState('');
 const [error,setError]=useState('');
 const [busy,setBusy]=useState(false);
 const [choice,setChoice]=useState<Record<string,string>>({});
 const refresh=async()=>{
  try{
   const [resolution,existing]=await Promise.all([apiClient.assetResolution(projectId),apiClient.assetVersions(channelId)]);
   setState(resolution);setVersions(existing.items);setError('');
  }catch(err){setError(err instanceof Error?err.message:String(err));}
 };
 useEffect(()=>{void refresh();},[projectId,channelId]);
 const act=async(task:()=>Promise<unknown>)=>{
  setBusy(true);setError('');
  try{await task();await refresh();}
  catch(err){setError(err instanceof Error?err.message:String(err));}
  finally{setBusy(false);}
 };
 const selectedRequirement=state?.requirements.find(x=>x.requirement.requirement_id===selected)?.requirement;
 const btn='rounded-xl border border-white/15 px-3 py-2 text-sm text-slate-100 disabled:opacity-40 hover:bg-white/10';
 return <div className="space-y-4" data-testid={'c3-'+mode}>
  {error&&<p role="alert" className="text-red-300">{error}</p>}
  <div className="flex items-center justify-between gap-2">
   <p className="text-sm text-slate-300">{state?state.resolved_count+' of '+state.total_count+' exact asset pins resolved':'Loading approved ShotPlan requirements…'}</p>
   <button className={btn} disabled={busy} onClick={()=>void refresh()}>Refresh</button>
  </div>
  {mode==='resolver'&&state?.requirements.map(({requirement:r,binding,state:status,reason})=>{
   const options=versions.filter(v=>state.compatible_versions[r.requirement_id]?.includes(v.asset_version_id));
   return <div key={r.requirement_id} className="rounded-xl border border-white/10 p-3">
    <div className="flex flex-wrap justify-between gap-2 text-sm text-slate-200">
     <strong>{r.kind}: {r.semantic_key} ({r.view})</strong>
     <span className={status==='resolved'?'text-emerald-300':'text-amber-300'}>{status}</span>
    </div>
    <p className="mt-1 text-xs text-slate-400">{r.shot_ids.join(', ')} · {reason||binding?.asset_version_id}</p>
    {binding?<button className={btn} disabled={busy} onClick={()=>void act(()=>apiClient.unbindAsset(projectId,binding.binding_id,state.requirements_fingerprint))}>Unpin exact version</button>:
    <div className="mt-2 flex flex-wrap gap-2">
     <select className="max-w-full rounded-lg bg-slate-800 p-2 text-xs" value={choice[r.requirement_id]||''}
      onChange={e=>setChoice(prev=>({...prev,[r.requirement_id]:e.target.value}))}>
      <option value="">Select approved channel version</option>
      {options.map(v=><option value={v.asset_version_id} key={v.asset_version_id}>{v.asset_version_id} · r{v.revision}</option>)}
     </select>
     <button className={btn} disabled={busy||!choice[r.requirement_id]}
      onClick={()=>void act(()=>apiClient.bindAsset(projectId,r.requirement_id,choice[r.requirement_id],state.requirements_fingerprint))}>Pin version</button>
    </div>}
   </div>;
  })}
  {mode==='generation'&&<>
   <p className="text-sm text-slate-400">Import local images without G-Labs or explicitly authorize a paid G-Labs attempt. Rig capabilities remain pending C4 validation.</p>
   <label className="block text-xs text-slate-300">Asset requirement
    <select className="mt-2 w-full rounded-xl bg-slate-800 p-3" value={selected} onChange={e=>setSelected(e.target.value)}>
     <option value="">Choose a requirement</option>
     {state?.requirements.map(({requirement:r})=><option key={r.requirement_id} value={r.requirement_id}>{r.kind} · {r.semantic_key} · {r.view}</option>)}
    </select>
   </label>
   <input aria-label="Import local image" type="file" accept="image/png,image/jpeg,image/webp" disabled={busy||!selected}
    onChange={e=>{const file=e.target.files?.[0];const requirement=state?.requirements.find(x=>x.requirement.requirement_id===selected)?.requirement;
     if(file&&requirement)void act(async()=>{setCandidate(await apiClient.uploadImage(projectId,requirement.kind,requirement.semantic_key,requirement.view,file));});}}/>
   <GLabsPanel projectId={projectId} requirement={selectedRequirement} onCandidate={setCandidate}/>
   {candidate&&<div className="space-y-3 rounded-xl border border-white/10 p-3">
    <p className="text-sm text-slate-300">Candidate {candidate.asset_version_id} · {candidate.width}×{candidate.height}</p>
    <img className="max-h-72 rounded-lg object-contain" src={apiClient.imageSrc(projectId,candidate.asset_version_id)} alt="Imported user-owned asset candidate"/>
    <div className="flex gap-2">
     <button className={btn} disabled={busy} onClick={()=>void act(async()=>{await apiClient.reviewImage(projectId,candidate.asset_version_id,'approved');setCandidate(null);})}>Approve version</button>
     <button className={btn} disabled={busy} onClick={()=>void act(async()=>{await apiClient.reviewImage(projectId,candidate.asset_version_id,'rejected');setCandidate(null);})}>Reject</button>
    </div>
   </div>}
   <div className="space-y-2">
    <h4 className="text-sm font-semibold">Stored channel versions</h4>
    {versions.map(v=><div className="flex flex-wrap gap-2 items-center text-xs text-slate-300" key={v.asset_version_id}>
     <span>{v.kind}/{v.semantic_key}/{v.view_key} · r{v.revision} · {v.status}</span>
     <a className="text-cyan-300 underline" href={apiClient.imageSrc(projectId,v.asset_version_id)} target="_blank" rel="noreferrer">View image</a>
     {v.status==='candidate'&&<button className={btn} disabled={busy} onClick={()=>void act(()=>apiClient.reviewImage(projectId,v.asset_version_id,'approved'))}>Approve</button>}
    </div>)}
   </div>
  </>}
 </div>;
}

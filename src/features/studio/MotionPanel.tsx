import {useEffect,useState} from 'react';
import {apiClient,type Artifact,type CompiledFilm,type MotionFrame} from '../../api/client';
import {MotionSpineViewport} from './MotionSpineViewport';
const button='rounded-xl border border-white/15 px-3 py-2 text-sm text-slate-100 hover:bg-white/10 disabled:opacity-40';
export function MotionPanel({projectId,channelId,onUpdate}:{projectId:string;channelId:string;onUpdate:()=>void}){
 const [compiled,setCompiled]=useState<{artifact:Artifact;document:CompiledFilm}|null>(null);
 const [shot,setShot]=useState('');
 const [frame,setFrame]=useState(0);
 const [playing,setPlaying]=useState(false);
 const [busy,setBusy]=useState(false);
 const [status,setStatus]=useState('No approved current compilation loaded');
 const [error,setError]=useState('');
 const [observed,setObserved]=useState<MotionFrame|null>(null);
 const selected=compiled?.document.shots.find(x=>x.shot_id===shot);
 const length=selected?.frame_count||0;
 const compile=async()=>{
  setBusy(true);setError('');setStatus('Compiling verified current AnimationPlan…');setPlaying(false);
  try{
   const result=await apiClient.motionCompile(projectId);
   const record=await apiClient.motionRead(projectId,result.artifact_id);
   setCompiled(record);setShot(record.document.shots[0]?.shot_id||'');setFrame(0);
   setStatus('Compiled immutable motion '+result.artifact_id);onUpdate();
  }catch(e){setError(e instanceof Error?e.message:String(e));setStatus('Compilation rejected');}
  finally{setBusy(false);}
 };
 const load=async(id:string)=>{
  setBusy(true);setError('');
  try{
   const record=await apiClient.motionRead(projectId,id);
   setCompiled(record);setShot(record.document.shots[0]?.shot_id||'');setFrame(0);
   setStatus('Loaded verified compilation '+id);
  }catch(e){setError(String(e));}
  finally{setBusy(false);}
 };
 useEffect(()=>{
  let active=true;
  void apiClient.motionStatus(projectId).then(result=>{
   if(active&&result.artifact_id)void load(result.artifact_id);
  }).catch(e=>{if(active)setError(String(e));});
  return()=>{active=false;};
 },[projectId]);
 useEffect(()=>{
  if(!playing||length<2)return;
  const timer=setInterval(()=>setFrame(v=>{
   if(v>=length-1){setPlaying(false);return 0;}
   return v+1;
  }),1000/24);
  return()=>clearInterval(timer);
 },[playing,length,shot]);
 return <div className="space-y-4" data-testid="c5-motion">
  <p className="text-sm text-slate-300">Compile an approved, source-current AnimationPlan; seek actual articulated rigs at any integer frame using official Spine/Pixi.</p>
  <button className={button} disabled={busy} onClick={()=>void compile()}>
   {busy?'Checking all frames…':'Compile current AnimationPlan'}</button>
  {status&&<p role="status" className="text-sm text-slate-300">{status}</p>}
  {error&&<p role="alert" className="text-sm text-rose-300">{error}</p>}
  {compiled&&<div className="space-y-3">
   <p className="break-all text-xs text-slate-400">Compiled: {compiled.artifact.artifact_id} · SHA {compiled.artifact.sha256}</p>
   <label className="text-sm text-slate-300">Shot
    <select value={shot} onChange={e=>{setShot(e.target.value);setFrame(0);setPlaying(false);}}
      className="ml-2 rounded-lg bg-slate-800 px-3 py-2">
     {compiled.document.shots.map(sh=><option key={sh.shot_id} value={sh.shot_id}>
      {sh.shot_id} · {sh.frame_count} frames
     </option>)}
    </select>
   </label>
   {selected&&<div className="space-y-3">
    <div className="flex flex-wrap items-center gap-2">
     <button className={button} onClick={()=>setPlaying(v=>!v)}>{playing?'Pause':'Play'}</button>
     <button className={button} onClick={()=>{setFrame(0);setPlaying(false);}}>Restart at frame 0</button>
     <button className={button} disabled={frame===0} onClick={()=>{setPlaying(false);setFrame(f=>Math.max(0,f-1));}}>−1 frame</button>
     <button className={button} disabled={frame>=length-1} onClick={()=>{setPlaying(false);setFrame(f=>Math.min(length-1,f+1));}}>+1 frame</button>
     <span className="font-mono text-xs text-slate-300" data-testid="c5-frame-counter">{frame} / {length-1} · 24fps</span>
    </div>
    <input type="range" aria-label="Exact motion frame" className="w-full" value={frame} min={0} max={length-1} step={1}
     onChange={e=>{setPlaying(false);setFrame(Number(e.target.value));}}/>
    <MotionSpineViewport projectId={projectId} channelId={channelId} shotId={shot}
      compilationId={compiled.artifact.artifact_id} frame={frame} onState={setObserved}/>
    {observed&&<p className="text-xs text-slate-400">Evaluated {observed.shot_id}, frame {observed.frame}, exact fingerpint: {observed.fingerprint}</p>}
   </div>}
  </div>}
 </div>;
}

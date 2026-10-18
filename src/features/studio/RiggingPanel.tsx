import {useEffect,useMemo,useRef,useState} from 'react';
import {useQueryClient} from '@tanstack/react-query';
import {apiClient,type RigDraft,type RigExport,type RigStroke} from '../../api/client';
import {SpineViewport} from './SpineViewport';

const btn='rounded-xl border border-white/15 px-3 py-2 text-sm text-slate-100 disabled:opacity-40 hover:bg-white/10';
export function RiggingPanel({projectId,channelId}:{projectId:string;channelId:string}){
 const queryClient=useQueryClient();
 const [source,setSource]=useState('');
 const [sources,setSources]=useState<Array<{asset_version_id:string;status:string;kind:string;semantic_key:string}>>([]);
 const [rigs,setRigs]=useState<Array<{rig_id:string;rig_version_id:string|null;status:string|null;revision:number|null;editable:number}>>([]);
 const [rigId,setRigId]=useState('');
 const [draft,setDraft]=useState<RigDraft|null>(null);
 const [selected,setSelected]=useState('head');
 const [mode,setMode]=useState<'paint'|'erase'|'pivot'>('paint');
 const [brush,setBrush]=useState(.015);
 const [candidate,setCandidate]=useState<RigExport|null>(null);
 const [proofId,setProofId]=useState('');
 const [approvedId,setApprovedId]=useState('');
 const [readonlyPreview,setReadonlyPreview]=useState<{candidate:RigExport;sourceSha:string}|null>(null);
 const [rigResolution,setRigResolution]=useState<{revision:number;readiness:string;actor_requirements:Array<{requirement_id:string;semantic_key:string;asset_version_id:string|null}>;bindings:Array<{requirement_id:string;rig_version_id:string}>}|null>(null);
 const [actorRequirement,setActorRequirement]=useState('');
 const [imageEpoch,setImageEpoch]=useState(0);
 const [busy,setBusy]=useState(false);
 const [error,setError]=useState('');
 const [showMask,setShowMask]=useState(true);
 const [showPart,setShowPart]=useState(true);
 const canvas=useRef<HTMLCanvasElement>(null);
 const overlay=useRef<HTMLImageElement>(null);
 const selectedPart=draft?.parts[selected];
 const srcUrl=source?apiClient.imageSrc(projectId,source):'';
 const previewUrl=draft?apiClient.rigPartImage(projectId,rigId,selected,'sprite')+'?v='+imageEpoch:'';
 const maskUrl=draft?apiClient.rigPartImage(projectId,rigId,selected,'mask')+'?v='+imageEpoch:'';
 const roles=useMemo(()=>draft?Object.keys(draft.parts):[],[draft]);
 const loadRigResolution=async()=>{
  const response=await fetch('http://127.0.0.1:8000/api/v1/projects/'+projectId+'/rigging/resolution');
  if(!response.ok){setRigResolution(null);return;}
  const data=await response.json();setRigResolution(data.data);
 };
 const refresh=async()=>{
  const [assets,items]=await Promise.all([apiClient.assetVersions(channelId),apiClient.rigList(projectId)]);
  setSources(assets.items.filter(x=>x.kind==='actor'&&x.status==='approved'));
  setRigs(items.items.filter(x=>x.rig_id));
  await loadRigResolution();
 };
 useEffect(()=>{void refresh().catch(e=>setError(String(e)));},[projectId,channelId]);
 const operation=async(f:()=>Promise<void>)=>{
  setBusy(true);setError('');
  try{await f();await refresh();}catch(e){setError(e instanceof Error?e.message:String(e));}
  finally{setBusy(false);}
 };
 const reopen=async(id:string)=>{
  const doc=await apiClient.rigDraft(projectId,id);
  setDraft(doc);setRigId(id);setSource(doc.source_version);setSelected('head');setImageEpoch(x=>x+1);
  setCandidate(null);setReadonlyPreview(null);setProofId('');setApprovedId('');
 };
 const openVersion=async(id:string,version:string,revision:number,status:string)=>{
  const res=await fetch('http://127.0.0.1:8000/api/v1/channels/'+channelId+'/rigs/'+id+'/versions/'+version+'/info',{cache:'no-store'});
  if(!res.ok)throw new Error('Verified rig metadata cannot be opened');
  const body=await res.json() as {data:{source_sha256:string;manifest:RigExport['manifest']}};
  const rigData={rig_id:id,rig_version_id:version,revision,
   candidate:status==='candidate',loader_verified:status==='approved',manifest:body.data.manifest};
  // A channel-owned approved rig can be previewed without Project A's editable draft.
  setReadonlyPreview({candidate:rigData,sourceSha:body.data.source_sha256});
  setRigId(id);setCandidate(null);
 };
 const edit=async(extra:Record<string,unknown>)=>{
  if(!draft)return;
  await operation(async()=>{
   await apiClient.rigEdit(projectId,rigId,selected,{expected_revision:draft.draft_revision,...extra});
   await reopen(rigId);setSelected(selected);
  });
 };
 const stroke=(event:React.PointerEvent<HTMLCanvasElement>)=>{
  if(!draft||busy)return;
  const box=event.currentTarget.getBoundingClientRect();
  const x=Math.max(0,Math.min(1,(event.clientX-box.left)/box.width));
  const y=Math.max(0,Math.min(1,(event.clientY-box.top)/box.height));
  if(mode==='pivot'){
   void edit({pivot:{x,y}});
  }else{
   const brushStroke:RigStroke={x,y,radius:brush,mode};
   void edit({strokes:[brushStroke]});
  }
 };
 const loadMasks=()=>{
  const c=canvas.current;if(!c||!draft)return;
  const ctx=c.getContext('2d');if(!ctx)return;
  const image=new Image();
  const expected=selected;
  image.onload=()=>{
   if(!canvas.current||expected!==selected)return;
   const rect=canvas.current;
   rect.width=image.width;rect.height=image.height;
   const c2=rect.getContext('2d');if(!c2)return;
   c2.clearRect(0,0,image.width,image.height);
   if(showMask){c2.globalAlpha=.40;c2.drawImage(image,0,0);c2.globalAlpha=1;}
   if(selectedPart){
    c2.fillStyle='#22d3ee';
    const cx=selectedPart.pivot.x*image.width,cy=selectedPart.pivot.y*image.height;
    c2.beginPath();c2.arc(cx,cy,Math.max(3,image.width*.01),0,Math.PI*2);c2.fill();
   }
  };
  image.src=maskUrl;
 };
 useEffect(loadMasks,[maskUrl,showMask,selectedPart?.pivot.x,selectedPart?.pivot.y]);
 return <section className="space-y-4" data-testid="c4-rigging-workshop">
  {error&&<p role="alert" className="text-rose-300">{error}</p>}
  <p className="text-sm text-slate-400">Pixel-assisted extraction. Every region is an uncertain proposal until you review, correct and accept it. Occluded limbs must be reconstructed or supplied explicitly.</p>
  <div className="flex flex-wrap items-center gap-2">
   <select className="rounded-lg bg-slate-800 p-2" value={source} onChange={e=>setSource(e.target.value)} aria-label="Approved actor image">
    <option value="">Select approved actor image</option>
    {sources.map(v=><option key={v.asset_version_id} value={v.asset_version_id}>{v.semantic_key} · {v.asset_version_id.slice(0,13)}</option>)}
   </select>
   <button className={btn} disabled={busy||!source} onClick={()=>void operation(async()=>{const r=await apiClient.rigStart(projectId,source);await reopen(r.rig_id);})}>Extract / create source revision</button>
   <button className={btn} disabled={busy} onClick={()=>void refresh()}>Refresh</button>
  </div>
  {source&&!draft&&<div className="max-w-56 overflow-hidden rounded-xl border border-white/10"><img src={srcUrl} alt="Selected exact approved source" className="w-full"/></div>}
  {rigs.length>0&&<div className="space-y-2">
   <h4 className="text-sm font-semibold text-slate-200">Channel rig versions</h4>
   <div className="flex flex-wrap gap-2">
    {[...new Set(rigs.filter(r=>Boolean(r.editable)).map(r=>r.rig_id))].map(id=><button type="button" className={btn} key={id} disabled={busy} onClick={()=>void operation(()=>reopen(id))}>Edit draft {id.slice(0,14)}</button>)}
    {rigs.filter(r=>r.rig_version_id).map(r=><button type="button" key={r.rig_version_id} className={btn} disabled={busy}
     onClick={()=>void operation(()=>openVersion(r.rig_id,r.rig_version_id!,r.revision!,r.status!))}>
     {r.status==='approved'?'Play approved':'Inspect '+r.status} {r.rig_version_id?.slice(0,13)}
    </button>)}
   </div>
  </div>}
  {rigResolution&&<section className="space-y-2 rounded-xl border border-white/10 p-3" data-testid="c4-project-rig-selection">
    <h4 className="font-semibold text-slate-100">Project actor → approved rig mapping</h4>
    <p className="text-xs text-slate-400">Current project readiness: {rigResolution.readiness}. Every pinned ShotPlan actor needs an exact approved compatible rig.</p>
    <div className="flex flex-wrap gap-2">
     <select aria-label="Required project actor" className="rounded bg-slate-800 p-2" value={actorRequirement}
      onChange={e=>setActorRequirement(e.target.value)}>
      <option value="">Select required actor</option>
      {rigResolution.actor_requirements.map(x=><option key={x.requirement_id} value={x.requirement_id}>
       {x.semantic_key} — {x.asset_version_id?.slice(0,14)??'not pinned'}
      </option>)}
     </select>
     <button type="button" className={btn} disabled={busy||!actorRequirement||!readonlyPreview||readonlyPreview.candidate.candidate}
      onClick={()=>void operation(async()=>{
       const response=await fetch('http://127.0.0.1:8000/api/v1/projects/'+projectId+'/rigging/resolution/select',{
        method:'POST',headers:{'Content-Type':'application/json'},
        body:JSON.stringify({requirement_id:actorRequirement,
         rig_version_id:readonlyPreview!.candidate.rig_version_id,
         expected_revision:rigResolution.revision})});
       const data=await response.json();
       if(!response.ok)throw new Error(JSON.stringify(data));
       await queryClient.invalidateQueries({queryKey:['workflow',projectId]});
      })}>Use previewed rig in this project</button>
    </div>
    {rigResolution.bindings.map(x=><p key={x.requirement_id} className="text-xs text-slate-300">
     {x.requirement_id.slice(0,16)} → {x.rig_version_id}</p>)}
   </section>}
  {readonlyPreview&&<section data-testid="c4-readonly-rig-preview" className="space-y-3">
   <h4 className="text-sm text-slate-100">Verified channel rig {readonlyPreview.candidate.rig_version_id} (read-only)</h4>
   <SpineViewport channelId={channelId} rigId={readonlyPreview.candidate.rig_id}
    candidate={readonlyPreview.candidate} sourceSha={readonlyPreview.sourceSha}/>
  </section>}
  {draft&&<>
   <div className="flex flex-wrap items-center gap-3 text-xs text-slate-300">
    <span>Draft revision {draft.draft_revision}</span>
    <span>Source SHA {draft.source_sha.slice(0,16)}</span>
    <span>Reviewed {roles.filter(x=>draft.parts[x].reviewed).length}/{roles.length}</span>
   </div>
   <div className="grid gap-4 lg:grid-cols-[260px_minmax(0,1fr)]">
    <div className="space-y-2 overflow-auto max-h-[650px]">
     {roles.map(role=>{const p=draft.parts[role];return <button key={role} onClick={()=>setSelected(role)} type="button"
      className={'w-full rounded-lg border p-2 text-left text-xs '+(role===selected?'border-cyan-400 bg-cyan-900/20':'border-white/10')}>
      <div className="flex justify-between gap-2"><strong className="text-slate-100">{role}</strong><span className={p.reviewed?'text-emerald-300':'text-amber-300'}>{p.reviewed?'Accepted':p.occluded?'Missing':'Review needed'}</span></div>
      <div className="text-slate-400">{p.provenance} · {p.reason}</div>
     </button>})}
    </div>
    <div className="space-y-3">
     <div className="relative mx-auto max-w-[720px] overflow-hidden rounded-xl border border-white/10 bg-slate-900">
      <img src={srcUrl} className="w-full" alt="Exact approved character source"/>
      {showPart&&<img ref={overlay} src={previewUrl} className="pointer-events-none absolute inset-0 h-full w-full object-fill opacity-75" alt="Real extracted sprite overlay"/>}
      <canvas ref={canvas} onPointerDown={stroke} role="img" aria-label="Interactive source mask editor"
       className="absolute inset-0 h-full w-full touch-none cursor-crosshair"/>
     </div>
     <div className="flex flex-wrap gap-3 items-center text-xs">
      <label><input type="checkbox" checked={showMask} onChange={e=>setShowMask(e.target.checked)}/> Mask overlay</label>
      <label><input type="checkbox" checked={showPart} onChange={e=>setShowPart(e.target.checked)}/> Sprite overlay</label>
      <label>Tool <select className="ml-1 rounded bg-slate-800 p-2" value={mode} onChange={e=>setMode(e.target.value as typeof mode)}>
       <option value="paint">Paint mask</option><option value="erase">Erase mask</option><option value="pivot">Move pivot</option>
      </select></label>
      <label>Brush radius <input aria-label="Brush radius" type="range" min=".002" max=".08" step=".002" value={brush} onChange={e=>setBrush(Number(e.target.value))}/></label>
     </div>
     <div className="flex flex-wrap gap-3 items-center text-sm">
      <label>Pivot X <input aria-label="Pivot X" className="w-20 rounded bg-slate-800 p-2" type="number" min="0" max="1" step=".01" value={selectedPart?.pivot.x??0} onChange={e=>{if(selectedPart)void edit({pivot:{x:Number(e.target.value),y:selectedPart.pivot.y}});}}/></label>
      <label>Pivot Y <input aria-label="Pivot Y" className="w-20 rounded bg-slate-800 p-2" type="number" min="0" max="1" step=".01" value={selectedPart?.pivot.y??0} onChange={e=>{if(selectedPart)void edit({pivot:{x:selectedPart.pivot.x,y:Number(e.target.value)}});}}/></label>
      <label>Layer <input aria-label="Sprite layer" className="w-16 rounded bg-slate-800 p-2" type="number" min="0" max="100" value={selectedPart?.layer??0} onChange={e=>void edit({layer:Number(e.target.value)})}/></label>
      <button className={btn} disabled={busy} onClick={()=>void edit({reset:true})}>Reset part</button>
      <button className={btn} disabled={busy} onClick={()=>void edit({reviewed:!selectedPart?.reviewed})}>{selectedPart?.reviewed?'Unreview':'Review & accept'}</button>
      <label className={btn}>Replace transparent PNG<input type="file" className="hidden" accept="image/png" disabled={busy}
       onChange={e=>{const file=e.target.files?.[0];if(file)void operation(async()=>{await apiClient.rigReplace(projectId,rigId,selected,draft.draft_revision,file);await reopen(rigId);setSelected(selected);});}}/></label>
     </div>
     {selectedPart?.replacement&&selectedPart.placement&&<div className="flex flex-wrap gap-3 text-xs" data-testid="c4-replacement-placement">
      {(['x','y','width','height'] as const).map(axis=><label key={axis}>Replacement {axis}
       <input type="number" min="0" max="1" step=".01" aria-label={'Replacement '+axis}
        className="ml-1 w-20 rounded bg-slate-800 p-2" value={selectedPart.placement![axis]}
        onChange={e=>{if(selectedPart.placement)void edit({placement:{...selectedPart.placement,[axis]:Number(e.target.value)}});}}/>
      </label>)}
     </div>}
     {selectedPart&&<p className="text-xs text-slate-400">Selected {selected} · pivot normalized top-left ({selectedPart.pivot.x.toFixed(3)}, {selectedPart.pivot.y.toFixed(3)}), Z {selectedPart.layer}</p>}
    </div>
   </div>
   <button className={btn} disabled={busy||roles.some(r=>!draft.parts[r].reviewed)} onClick={()=>void operation(async()=>{
    const result=await apiClient.rigExport(projectId,rigId,draft.draft_revision);setCandidate(result);
    setProofId('');setApprovedId('');
   })}>Export immutable Spine 4.2 candidate</button>
   {candidate&&<SpineViewport channelId={channelId} rigId={rigId} candidate={candidate}
    sourceSha={draft.source_sha} onVerified={evidence=>setProofId(evidence.proof_artifact_id)}/>}
   {candidate&&candidate.candidate&&<>
    <p className="text-amber-200 text-sm">Candidate {candidate.rig_version_id}: complete the real five-pose verification, then approve its exact immutable version.</p>
    <button type="button" className={btn} disabled={busy||!proofId} onClick={()=>void operation(async()=>{
     const result=await apiClient.rigReview(channelId,rigId,candidate.rig_version_id,candidate.revision,'approved');
     if(result.status!=='approved')throw new Error('Rig approval was not committed');
     setApprovedId(candidate.rig_version_id);
     setCandidate({...candidate,candidate:false,loader_verified:true});
     await queryClient.invalidateQueries({queryKey:['workflow',projectId]});
    })}>Approve verified rig version</button>
   </>}
   {candidate&&(!candidate.candidate||approvedId===candidate.rig_version_id)&&
    <p className="text-emerald-300 text-sm" data-testid="c4-rig-approved">Approved immutable playable Spine rig: {candidate.rig_version_id}</p>}
  </>}
 </section>;
}

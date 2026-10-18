import {useEffect,useState} from 'react';
import {useQuery} from '@tanstack/react-query';
import {apiClient,type StageProjection} from '../api/client';
import type {AppView,WorkspaceContext} from '../app/workspace';
import {PipelineStepper,type PipelineStep} from '../layout/PipelineStepper';
import {StatusBadge} from '../components/ui/StatusBadge';
import {ErrorBanner} from '../components/ui/ErrorBanner';
import {EmptyState} from '../components/ui/EmptyState';
import {Clapperboard} from 'lucide-react';
import {AuthoringPanel} from '../features/studio/AuthoringPanel';
import {AssetsPanel} from '../features/studio/AssetsPanel';
import {RiggingPanel} from '../features/studio/RiggingPanel';
import {DirectorPanel} from '../features/studio/DirectorPanel';
import {MotionPanel} from '../features/studio/MotionPanel';
import {useQueryClient} from '@tanstack/react-query';
const LABELS:Record<string,string>={
 authoring:'Authoring',resolver:'Resolver',generation:'Generation',
 rigging:'Rigging',director:'Director',motion:'Motion',delivery:'Delivery'
};
export function StudioPage({workspace,onNavigate}:{workspace:WorkspaceContext;onNavigate:(v:AppView)=>void}){
 const [selected,setSelected]=useState('authoring');
 const queryClient=useQueryClient();
 const proj=workspace.selectedProject;
 const result=useQuery({queryKey:['workflow',proj?.project_id],
  queryFn:()=>apiClient.workflow(proj!.project_id),enabled:Boolean(proj),refetchInterval:30000});
 useEffect(()=>setSelected('authoring'),[proj?.project_id]);
 if(!proj)return <section className="panel-surface p-5"><EmptyState icon={Clapperboard}
  title="Select an animation project" body="Choose a channel and project to inspect its seven-stage workflow."
  actionLabel="Go to Projects" onAction={()=>onNavigate('projects')}/></section>;
 if(result.error)return <ErrorBanner message={String(result.error)}/>;
 if(!result.data)return <div className="panel-surface p-6 text-slate-400">Loading persisted workflow…</div>;
 const stages=result.data.stages;
 const current:StageProjection=stages.find(x=>x.stage_key===selected)??stages[0];
 const steps:PipelineStep[]=stages.map(stage=>({
  id:stage.stage_key,label:LABELS[stage.stage_key],status:stage.readiness,
  hint:stage.blocker_codes.join(', ')||stage.readiness
 }));
 return <div className="space-y-4" data-testid="animation-studio">
  <PipelineStepper steps={steps} activeStepId={current.stage_key} onSelect={setSelected}/>
  <section className="panel-surface space-y-5 p-5">
   <div className="flex flex-wrap items-start justify-between gap-4">
    <div><p className="text-xs font-semibold uppercase tracking-[0.24em] text-cyan-300">{current.owner_phase} · Animation pipeline</p>
     <h2 className="mt-2 text-2xl font-semibold text-slate-50">{LABELS[current.stage_key]}</h2>
     <p className="mt-2 text-sm text-slate-400">
      Persisted approval and computed readiness are tracked independently.
     </p></div>
    <div className="flex gap-2"><StatusBadge status={current.approval_status} label={'Approval: '+current.approval_status}/>
     <StatusBadge status={current.readiness} label={'Readiness: '+current.readiness}/></div>
   </div>
   <div className="grid gap-3 md:grid-cols-3">
    <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-4 text-sm text-slate-300">
     <p className="mb-2 text-xs uppercase tracking-widest text-slate-500">Head revision</p>
     {current.head_artifact_id??'No artifact head'} · {current.head_revision}
    </div>
    <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-4 text-sm text-slate-300">
     <p className="mb-2 text-xs uppercase tracking-widest text-slate-500">Stored dependency fingerprint</p>
     <code className="break-all text-xs">{current.stored_dependency_fingerprint}</code>
    </div>
    <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-4 text-sm text-slate-300">
     <p className="mb-2 text-xs uppercase tracking-widest text-slate-500">Computed fingerprint</p>
     <code className="break-all text-xs">{current.computed_dependency_fingerprint}</code>
    </div>
   </div>
   {current.stage_key==='authoring'?<AuthoringPanel key={proj.project_id} projectId={proj.project_id} headRevision={current.head_revision} onCommitted={()=>void queryClient.invalidateQueries({queryKey:['workflow',proj.project_id]})}/>:current.stage_key==='resolver'||current.stage_key==='generation'?<AssetsPanel key={proj.project_id+'-'+current.stage_key} projectId={proj.project_id} channelId={proj.channel_id} mode={current.stage_key}/>:current.stage_key==='rigging'?<RiggingPanel key={proj.project_id} projectId={proj.project_id} channelId={proj.channel_id}/>:current.stage_key==='director'?<DirectorPanel key={proj.project_id} projectId={proj.project_id} headRevision={current.head_revision} onUpdate={()=>void queryClient.invalidateQueries({queryKey:['workflow',proj.project_id]})}/>:current.stage_key==='motion'?<MotionPanel key={proj.project_id} projectId={proj.project_id} channelId={proj.channel_id} onUpdate={()=>void queryClient.invalidateQueries({queryKey:['workflow',proj.project_id]})}/>:<div className="rounded-2xl border border-amber-500/20 bg-amber-500/[0.04] p-5">
    <h3 className="font-semibold text-amber-100">Stage execution not yet implemented</h3>
    <p className="mt-2 text-sm text-slate-300">Implementation owner: {current.owner_phase}. This stage remains blocked until its required feature phase is implemented and approved.</p>
    <div className="mt-3 flex flex-wrap gap-2">{(current.blocker_codes.length?current.blocker_codes:[current.owner_phase+'_ACTION_NOT_IMPLEMENTED']).map(code=>
     <span key={code} className="rounded-full border border-amber-500/20 px-3 py-1 font-mono text-xs text-amber-200">{code}</span>)}</div>
    <button type="button" disabled className="mt-4 rounded-2xl border border-white/10 px-4 py-2 text-sm text-slate-500 opacity-50">Generate / Execute (not available)</button>
   </div>}
  </section>
 </div>;
}
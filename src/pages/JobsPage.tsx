import {useQuery} from '@tanstack/react-query';
import type {WorkspaceContext} from '../app/workspace';
import {apiClient} from '../api/client';
import {SectionCard} from '../components/ui/SectionCard';
import {StatusBadge} from '../components/ui/StatusBadge';
import {ErrorBanner} from '../components/ui/ErrorBanner';
export function JobsPage({workspace}:{workspace:WorkspaceContext}){
 const pid=workspace.selectedProjectId;
 const result=useQuery({queryKey:['jobs',pid],queryFn:()=>apiClient.jobs(pid),enabled:Boolean(pid)});
 return <SectionCard title="Jobs" description="Only persisted animation job projections are listed.">
  {!pid?<p className="text-slate-400">Select a project to inspect jobs.</p>:
   result.error?<ErrorBanner message={String(result.error)}/>:
   !result.data?.items.length?<p className="text-slate-400">No animation jobs have been submitted. C2 does not start background workers.</p>:
   <div className="space-y-3">{result.data.items.map(job=><article key={job.job_id} className="rounded-2xl border border-white/10 p-4">
    <div className="flex justify-between"><span className="font-medium text-slate-100">{job.kind}</span>
    <StatusBadge status={job.status}/></div>
    <p className="mt-2 font-mono text-xs text-slate-500">{job.job_id}</p>
    <p className="mt-2 text-sm text-slate-400">{job.progress_message} · {job.progress_percent}%</p>
   </article>)}</div>}
 </SectionCard>;
}
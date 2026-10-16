import {useQuery} from '@tanstack/react-query';
import {apiClient} from '../api/client';
import {SectionCard} from '../components/ui/SectionCard';
import {ErrorBanner} from '../components/ui/ErrorBanner';
import {StatusBadge} from '../components/ui/StatusBadge';
export function SettingsPage(){
 const state=useQuery({queryKey:['system'],queryFn:apiClient.system});
 return <SectionCard title="Animation system" description="Local-only application readiness. Provider execution is intentionally not available in C2.">
  {state.error&&<ErrorBanner message={String(state.error)}/>}
  {state.data?<div className="space-y-4 text-sm text-slate-300">
   <div className="flex flex-wrap gap-3"><StatusBadge status="approved" label="API / DB ready"/>
    <StatusBadge status="unavailable" label="Generation not configured"/></div>
   <div>Product: {state.data.product}</div>
   <div>Schema: {state.data.database_revision}</div>
   <div>Stages: {state.data.stages.join(' → ')}</div>
   <p>No paid operations, provider polling, YTB workers or rendering hosts run on startup.</p>
  </div>:<p className="text-slate-400">Checking system…</p>}
 </SectionCard>;
}
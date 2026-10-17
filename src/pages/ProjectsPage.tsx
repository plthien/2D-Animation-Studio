import {useRef,useState} from 'react';
import {useQueryClient} from '@tanstack/react-query';
import {FolderPlus,Search} from 'lucide-react';
import {apiClient} from '../api/client';
import type {AppView,WorkspaceContext} from '../app/workspace';
import {ProjectCardGrid} from '../features/projects/ProjectCardGrid';
import {CreateProjectModal} from '../features/projects/CreateProjectModal';
import {TextInput} from '../features/channels/forms';
import {ErrorBanner} from '../components/ui/ErrorBanner';
export function ProjectsPage({workspace,onNavigate}:{workspace:WorkspaceContext;onNavigate:(v:AppView)=>void}){
 const qc=useQueryClient();const [open,setOpen]=useState(false);
 const [n,setN]=useState('');const [slug,setSlug]=useState('');const [search,setSearch]=useState('');
 const [error,setError]=useState('');const [busy,setBusy]=useState(false);
 const pending=useRef<string|null>(null);
 const channel=workspace.selectedChannel;
 const canCreate=Boolean(channel&&channel.status==='active'&&channel.current_dna_artifact_id);
 const projectList=workspace.projects.filter(p=>p.name.toLowerCase().includes(search.toLowerCase()));
 async function create(){
  if(!channel)return;
  setBusy(true);setError('');
  try{
   if(!pending.current)pending.current=crypto.randomUUID();
   const p=await apiClient.createProject({channel_id:channel.channel_id,name:n.trim(),slug:slug.trim()},pending.current);
   pending.current=null;
   await qc.invalidateQueries({queryKey:['projects',channel.channel_id]});
   workspace.setSelectedProjectId(p.project_id);setOpen(false);setN('');setSlug('');onNavigate('studio');
  }catch(e){setError(String(e));}finally{setBusy(false);}
 }
 return <div className="space-y-4">
  <section className="panel-surface p-5">
   <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
    <div><h2 className="text-2xl font-semibold text-slate-50">Projects</h2>
     <p className="mt-2 text-sm text-slate-400">Open a project to inspect seven stages and their real readiness blockers.</p></div>
    <div className="flex gap-3"><label className="relative"><Search size={16} className="absolute left-3 top-3 text-slate-500"/>
     <TextInput data-testid="project-search-input" className="pl-10" placeholder="Search projects" value={search} onChange={e=>setSearch(e.target.value)}/></label>
     <button data-testid="new-project-button" disabled={!canCreate} onClick={()=>{pending.current=null;setOpen(true);setError('');}}
      className="flex items-center gap-2 rounded-2xl border border-cyan-400/30 bg-cyan-500/15 px-4 py-2 text-cyan-100 disabled:opacity-40">
      <FolderPlus size={16}/>New Project</button></div>
   </div>
  </section>
  {!channel?<ErrorBanner message="Select a channel before creating a project."/>:
   !channel.current_dna_artifact_id?<ErrorBanner message="Approve ChannelDNA v2 before creating projects."/>:null}
  <ProjectCardGrid projects={projectList} selectedProjectId={workspace.selectedProjectId}
   onOpenProject={id=>{workspace.setSelectedProjectId(id);onNavigate('studio');}}/>
  <CreateProjectModal open={open} channelName={channel?.name??''} name={n} slug={slug}
   error={error} busy={busy} onName={setN} onSlug={setSlug} onSubmit={create} onClose={()=>setOpen(false)}/>
 </div>;
}
import {Clapperboard,FolderKanban} from 'lucide-react';
import type {Project} from '../../api/client';
import {CardGrid} from '../../components/ui/CardGrid';
import {StatusBadge} from '../../components/ui/StatusBadge';
import {cx} from '../../lib/cx';
export function ProjectCardGrid({projects,selectedProjectId,onOpenProject}:{
 projects:Project[];selectedProjectId:string;onOpenProject:(id:string)=>void
}) {
 return <div data-testid="project-card-grid">
  {projects.length===0?<div className="rounded-[1.5rem] border border-dashed border-white/10 p-8 text-slate-400">No projects for this channel.</div>:
  <CardGrid>{projects.map(project=>{
   const selected=project.project_id===selectedProjectId;
   return <article key={project.project_id} className={cx('group overflow-hidden rounded-[1.5rem] border shadow-soft',
    selected?'border-cyan-400/40 bg-cyan-500/[0.08]':'border-white/10 bg-white/[0.03] hover:border-cyan-400/20')}>
    <button type="button" data-testid="open-studio-project" onClick={()=>onOpenProject(project.project_id)} className="w-full text-left">
     <div className="relative h-36 border-b border-white/10 bg-[radial-gradient(circle_at_top_left,rgba(34,211,238,0.22),transparent_40%),linear-gradient(145deg,rgba(15,23,42,0.96),rgba(30,41,59,0.82))]">
      <div className="absolute left-4 top-4 rounded-full border border-white/10 bg-black/20 px-3 py-1 font-mono text-xs text-slate-300">{project.project_id}</div>
      <div className="absolute right-4 top-4"><StatusBadge status={project.status==='active'?'draft':'unavailable'} label={project.status}/></div>
      <div className="absolute bottom-4 left-4 flex items-center gap-3"><Clapperboard className="text-cyan-200"/> <span className="text-sm text-slate-200">Animation pipeline</span></div>
     </div>
     <div className="space-y-4 p-4">
      <h3 className="text-lg font-semibold text-slate-50">{project.name}</h3>
      <p className="text-sm text-slate-500">{project.slug}</p>
      <div data-testid="project-progress" className="grid grid-cols-7 gap-1.5">{Array.from({length:7},(_,i)=><div key={i} className="h-2 rounded-full bg-slate-800"/>)}</div>
      <p className="text-xs text-slate-400">Seven stage projections are owned by the backend.</p>
      <div className="flex items-center justify-between border-t border-white/10 pt-4 text-xs text-slate-500">
       <span>{new Date(project.updated_at).toLocaleString()}</span>
       <span className="flex items-center gap-1 text-slate-200"><FolderKanban size={16}/>Open Studio →</span>
      </div>
     </div>
    </button>
   </article>;
  })}</CardGrid>}
 </div>;
}
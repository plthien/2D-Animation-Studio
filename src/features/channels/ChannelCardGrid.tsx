import type {Channel} from '../../api/client';
import {StatusBadge} from '../../components/ui/StatusBadge';
import {CardGrid} from '../../components/ui/CardGrid';
import {cx} from '../../lib/cx';
import {FolderKanban} from 'lucide-react';

export function ChannelCardGrid({channels,selectedChannelId,onSelect,onViewProjects}:{
 channels:Channel[];selectedChannelId:string;onSelect:(id:string)=>void;onViewProjects:(id:string)=>void;
}) {
 return <section className="panel-surface overflow-hidden" data-testid="channel-card-grid">
  <div className="border-b border-white/10 px-5 py-4">
   <div className="text-[11px] font-semibold uppercase tracking-[0.24em] text-slate-500">Channel Grid</div>
   <h2 className="text-lg font-semibold text-slate-100">Channels</h2>
   <p className="text-sm leading-6 text-slate-400">Select a channel to review its persisted ChannelDNA v2.</p>
  </div>
  <div className="max-h-[calc(100vh-15rem)] overflow-y-auto p-5" data-testid="channel-grid-scroll">
   {channels.length===0?<p className="p-6 text-slate-400">No channels yet. Create one to begin.</p>:
   <CardGrid>{channels.map(ch=><article key={ch.channel_id}
    className={cx('overflow-hidden rounded-[1.5rem] border p-4 shadow-soft transition',
     ch.channel_id===selectedChannelId?'border-cyan-400/40 bg-cyan-500/[0.08]':'border-white/10 bg-white/[0.03] hover:border-cyan-400/20')}>
    <button type="button" onClick={()=>onSelect(ch.channel_id)} className="w-full space-y-3 text-left" data-testid="select-channel">
     <div className="flex items-center justify-between">
      <div className="rounded-xl border border-white/10 bg-slate-950/40 p-3 text-cyan-200"><FolderKanban size={20}/></div>
      <StatusBadge status={ch.status==='archived'?'unavailable':ch.current_dna_artifact_id?'approved':'draft'}
       label={ch.status==='archived'?'Archived':ch.current_dna_artifact_id?'DNA approved':'DNA missing'}/>
     </div>
     <h3 className="text-lg font-semibold text-slate-50">{ch.name}</h3>
     <p className="font-mono text-xs text-slate-500">{ch.slug}</p>
     <p className="text-xs text-slate-500">Updated: {new Date(ch.updated_at).toLocaleString()}</p>
    </button>
    <button type="button" onClick={()=>onViewProjects(ch.channel_id)}
     className="mt-4 rounded-2xl border border-white/10 bg-white/[0.03] px-3 py-2 text-sm text-slate-200 hover:border-cyan-400/20">
     View projects →
    </button>
   </article>)}</CardGrid>}
  </div>
 </section>;
}
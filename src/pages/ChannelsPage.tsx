import {useEffect,useRef,useState} from 'react';
import {useQuery,useQueryClient} from '@tanstack/react-query';
import {Plus} from 'lucide-react';
import {apiClient,type DnaSource,type Artifact} from '../api/client';
import type {AppView,WorkspaceContext} from '../app/workspace';
import {ChannelCardGrid} from '../features/channels/ChannelCardGrid';
import {CreateChannelModal} from '../features/channels/CreateChannelModal';
import {ChannelDnaEditor,draftFromHead} from '../features/channels/ChannelDnaEditor';
import {TextInput} from '../features/channels/forms';

export function ChannelsPage({workspace,onNavigate}:{workspace:WorkspaceContext;onNavigate:(v:AppView)=>void}){
 const qc=useQueryClient();const [search,setSearch]=useState('');
 const [modal,setModal]=useState(false);const [name,setName]=useState('');const [slug,setSlug]=useState('');
 const [error,setError]=useState('');const [busy,setBusy]=useState(false);
 const [draft,setDraft]=useState<DnaSource>(draftFromHead(null,''));
 const [candidate,setCandidate]=useState<Artifact|null>(null);
 const idempotency=useRef<string|null>(null);
 const dna=useQuery({queryKey:['dna',workspace.selectedChannelId],
  queryFn:()=>apiClient.dnaHead(workspace.selectedChannelId),enabled:Boolean(workspace.selectedChannelId)});
 useEffect(()=>{setDraft(draftFromHead(dna.data??null,workspace.selectedChannel?.name??''));setCandidate(null);},
  [workspace.selectedChannelId,workspace.selectedChannel?.name,dna.data?.head_artifact_id,dna.data?.channel_dna?.revision]);
 function select(id:string){workspace.setSelectedChannelId(id);setError('');}
 async function create(){
  setBusy(true);setError('');
  try{
   if(!idempotency.current)idempotency.current=crypto.randomUUID();
   const created=await apiClient.createChannel({name:name.trim(),slug:slug.trim()},idempotency.current);
   idempotency.current=null;
   await qc.invalidateQueries({queryKey:['channels']});
   select(created.channel_id);setModal(false);setName('');setSlug('');
  }catch(e){setError(String(e));}finally{setBusy(false);}
 }
 async function save(){
  if(!workspace.selectedChannelId)return;
  setBusy(true);setError('');
  try{
   const saved=await apiClient.saveDna(workspace.selectedChannelId,{
    channel_dna:draft,expected_head_revision:dna.data?.head_revision??null,
    expected_head_artifact_id:dna.data?.head_artifact_id??null
   },crypto.randomUUID());
   setCandidate(saved);
  }catch(e){setError(String(e));}finally{setBusy(false);}
 }
 async function approve(){
  if(!candidate||!workspace.selectedChannelId)return;
  setBusy(true);setError('');
  try{
   await apiClient.approveDna(workspace.selectedChannelId,candidate.artifact_id,{
    expected_head_revision:dna.data?.head_revision??null,expected_sha256:candidate.sha256,
    actor:'local-user',reviewed_at:new Date().toISOString()});
   setCandidate(null);
   await Promise.all([qc.invalidateQueries({queryKey:['dna',workspace.selectedChannelId]}),
     qc.invalidateQueries({queryKey:['channels']})]);
  }catch(e){setError(String(e));}finally{setBusy(false);}
 }
 const filtered=workspace.channels.filter(c=>c.name.toLowerCase().includes(search.toLowerCase()));
 return <div className="space-y-4">
  <section className="panel-surface flex flex-wrap items-center justify-between gap-4 p-5">
   <div><h2 className="text-2xl font-semibold text-slate-50">Channel workspace</h2>
    <p className="text-sm text-slate-400">Create, select, edit and approve animation style identities.</p></div>
   <div className="flex gap-3"><TextInput placeholder="Search channels" value={search} onChange={e=>setSearch(e.target.value)}/>
    <button data-testid="new-channel-button" onClick={()=>{idempotency.current=null;setError('');setModal(true);}} type="button"
     className="flex items-center gap-2 rounded-2xl border border-cyan-400/30 bg-cyan-500/15 px-4 py-2 text-sm text-cyan-50">
     <Plus size={16}/>New Channel</button></div>
  </section>
  <div className="grid items-start gap-4 2xl:grid-cols-2">
   <ChannelCardGrid channels={filtered} selectedChannelId={workspace.selectedChannelId}
    onSelect={select} onViewProjects={id=>{select(id);onNavigate('projects');}}/>
   <ChannelDnaEditor channel={workspace.selectedChannel} draft={draft} onChange={setDraft}
    candidate={candidate} onSave={save} onApprove={approve} busy={busy} error={error}/>
  </div>
  <CreateChannelModal open={modal} name={name} slug={slug} error={error} busy={busy}
   onName={setName} onSlug={setSlug} onSubmit={create} onClose={()=>setModal(false)}/>
 </div>;
}
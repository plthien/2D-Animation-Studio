import {useState} from 'react';
import {useQuery} from '@tanstack/react-query';
import type {WorkspaceContext} from '../app/workspace';
import {apiClient} from '../api/client';
import {SectionCard} from '../components/ui/SectionCard';
import {StatusBadge} from '../components/ui/StatusBadge';
import {ErrorBanner} from '../components/ui/ErrorBanner';
import {TextInput} from '../features/channels/forms';
export function ArtifactsPage({workspace}:{workspace:WorkspaceContext}){
 const [id,setId]=useState('');const [lookup,setLookup]=useState('');
 const data=useQuery({queryKey:['artifact',lookup,workspace.selectedChannelId],
  queryFn:()=>apiClient.artifact(lookup,workspace.selectedChannelId),enabled:Boolean(lookup&&workspace.selectedChannelId),retry:false});
 return <SectionCard title="Immutable artifact metadata" description="Find an artifact by its exact ID. No unreviewed filesystem path is opened.">
  <form onSubmit={e=>{e.preventDefault();setLookup(id.trim());}} className="flex gap-3">
   <TextInput placeholder="Artifact ID" value={id} onChange={e=>setId(e.target.value)}/>
   <button type="submit" className="rounded-2xl border border-cyan-400/30 bg-cyan-500/15 px-4 py-2 text-cyan-100">Inspect</button>
  </form>
  {!workspace.selectedChannelId&&<p className="mt-3 text-slate-400">Select a channel first.</p>}
  {data.error&&<ErrorBanner message={String(data.error)}/>}
  {data.data&&<div className="mt-4 space-y-3 rounded-2xl border border-white/10 p-4 text-sm text-slate-300">
   <div className="flex justify-between"><strong>{data.data.kind}</strong><StatusBadge status={data.data.approval_status}/></div>
   <div>ID: {data.data.artifact_id} · Revision {data.data.revision}</div>
   <div>SHA-256: <code className="break-all text-xs">{data.data.sha256}</code></div>
   <div>Size: {data.data.byte_size} bytes</div>
   <div>Relative handle: {data.data.relative_artifact_handle}</div>
  </div>}
 </SectionCard>;
}
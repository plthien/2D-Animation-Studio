import {X} from 'lucide-react';
import {FieldLabel,TextInput} from '../channels/forms';
export function CreateProjectModal({open,name,slug,channelName,error,busy,onName,onSlug,onSubmit,onClose}:{
 open:boolean;name:string;slug:string;channelName:string;error:string;busy:boolean;
 onName:(v:string)=>void;onSlug:(v:string)=>void;onSubmit:()=>void;onClose:()=>void;
}){
 if(!open)return null;
 return <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/80 p-4 backdrop-blur-sm">
  <form data-testid="create-project-modal" onSubmit={e=>{e.preventDefault();onSubmit();}}
    className="panel-surface w-full max-w-xl overflow-hidden">
   <div className="flex justify-between border-b border-white/10 px-5 py-4">
    <div><h2 className="text-lg font-semibold text-slate-50">New animation project</h2>
     <p className="text-sm text-slate-400">Owner: {channelName}</p></div>
    <button type="button" aria-label="Close" onClick={onClose}><X size={20}/></button>
   </div>
   <div className="space-y-4 p-5">
    <div className="space-y-2"><FieldLabel>Project name</FieldLabel><TextInput value={name} onChange={e=>onName(e.target.value)} required autoFocus/></div>
    <div className="space-y-2"><FieldLabel>Unique slug</FieldLabel><TextInput value={slug} onChange={e=>onSlug(e.target.value)} required/></div>
    {error&&<p className="text-sm text-rose-300">{error}</p>}
   </div>
   <div className="flex justify-end gap-3 border-t border-white/10 p-4">
    <button type="button" onClick={onClose} className="rounded-2xl border border-white/10 px-4 py-2 text-slate-100">Cancel</button>
    <button type="submit" disabled={busy} className="rounded-2xl border border-cyan-400/30 bg-cyan-500/15 px-4 py-2 text-cyan-100 disabled:opacity-50">{busy?'Creating…':'Create project'}</button>
   </div>
  </form>
 </div>;
}
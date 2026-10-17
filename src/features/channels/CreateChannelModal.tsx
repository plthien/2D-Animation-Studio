import {X} from 'lucide-react';
import {FieldLabel,TextInput} from './forms';
export function CreateChannelModal({open,name,slug,error,busy,onName,onSlug,onSubmit,onClose}:{
 open:boolean;name:string;slug:string;error:string;busy:boolean;
 onName:(value:string)=>void;onSlug:(value:string)=>void;onSubmit:()=>void;onClose:()=>void;
}) {
 if(!open)return null;
 return <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/80 p-4 backdrop-blur-sm">
  <form onSubmit={e=>{e.preventDefault();onSubmit();}} data-testid="create-channel-modal"
   className="panel-surface flex w-full max-w-xl flex-col overflow-hidden">
   <div className="flex items-center justify-between border-b border-white/10 px-5 py-4">
    <div><h2 className="text-xl font-semibold text-slate-100">Create channel</h2>
     <p className="mt-1 text-sm text-slate-400">A channel stores animation identity and revisions.</p></div>
    <button type="button" onClick={onClose} aria-label="Close"><X size={20}/></button>
   </div>
   <div className="space-y-4 p-5">
    <div className="space-y-2"><FieldLabel>Channel name</FieldLabel><TextInput value={name} onChange={e=>onName(e.target.value)} required autoFocus/></div>
    <div className="space-y-2"><FieldLabel>Unique slug</FieldLabel><TextInput value={slug} onChange={e=>onSlug(e.target.value)} required/></div>
    {error&&<p role="alert" className="text-sm text-rose-300">{error}</p>}
   </div>
   <div className="flex justify-end gap-3 border-t border-white/10 p-4">
    <button type="button" onClick={onClose} className="rounded-2xl border border-white/10 px-4 py-2 text-slate-200">Cancel</button>
    <button type="submit" disabled={busy} className="rounded-2xl border border-cyan-400/30 bg-cyan-500/15 px-4 py-2 text-cyan-50 disabled:opacity-50">{busy?'Creating…':'Create channel'}</button>
   </div>
  </form>
 </div>;
}
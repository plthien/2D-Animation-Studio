import type {Channel,DnaSource,DnaHead,Artifact} from '../../api/client';
import {FieldLabel,TextArea,TextInput} from './forms';
import {StatusBadge} from '../../components/ui/StatusBadge';

export function emptyDna(name:string):DnaSource {
 return {schema_version:'channel_dna.v2', identity:{name,audience:''},
   visual:{style:'',palette:['#3B82F6']},performance:{tone:'',motion_density:'medium'},
   narration:{language:'en',voice_character:''}};
}
export function draftFromHead(head:DnaHead|null,name:string):DnaSource {
 if(!head?.channel_dna)return emptyDna(name);
 const {schema_version,identity,visual,performance,narration}=head.channel_dna;
 return {schema_version,identity,visual,performance,narration};
}
export function ChannelDnaEditor({channel,draft,onChange,onSave,onApprove,candidate,busy,error}:{
 channel:Channel|null;draft:DnaSource;onChange:(source:DnaSource)=>void;
 onSave:()=>void;onApprove:()=>void;candidate:Artifact|null;busy:boolean;error:string;
}) {
 const input=(label:string,value:string,set:(v:string)=>void,area=false)=> <div className="space-y-2" key={label}>
   <FieldLabel>{label}</FieldLabel>
   {area?<TextArea value={value} onChange={e=>set(e.target.value)} rows={2}/>:
    <TextInput value={value} onChange={e=>set(e.target.value)}/>}
 </div>;
 return <section className="panel-surface overflow-hidden" data-testid="channel-dna-editor">
  <div className="flex items-center justify-between gap-3 border-b border-white/10 px-5 py-4">
   <div><h2 className="text-lg font-semibold text-slate-50">ChannelDNA v2</h2>
    <p className="mt-1 text-sm text-slate-400">Visual, performance and narration are independent style identities.</p></div>
   <StatusBadge status={channel?.current_dna_artifact_id?'approved':'draft'} label={channel?.current_dna_artifact_id?'Approved head':'No approved head'}/>
  </div>
  {!channel?<p className="p-6 text-sm text-slate-400">Select a channel to edit its animation DNA.</p>:
   <div className="space-y-4 p-5">
    {input('Identity name',draft.identity.name,v=>onChange({...draft,identity:{...draft.identity,name:v}}))}
    {input('Audience',draft.identity.audience,v=>onChange({...draft,identity:{...draft.identity,audience:v}}),true)}
    {input('Visual style',draft.visual.style,v=>onChange({...draft,visual:{...draft.visual,style:v}}),true)}
    {input('Palette (hex colors, comma separated)',draft.visual.palette.join(', '),v=>onChange({...draft,visual:{...draft.visual,palette:v.split(',').map(x=>x.trim()).filter(Boolean)}}))}
    {input('Performance tone',draft.performance.tone,v=>onChange({...draft,performance:{...draft.performance,tone:v}}),true)}
    <div className="space-y-2"><FieldLabel>Motion density</FieldLabel>
     <select value={draft.performance.motion_density} onChange={e=>onChange({...draft,performance:{...draft.performance,motion_density:e.target.value as DnaSource['performance']['motion_density']}})}
      className="w-full rounded-2xl border border-white/10 bg-cockpit-950 px-4 py-3 text-slate-100">
      <option value="low">Low</option><option value="medium">Medium</option><option value="high">High</option>
     </select>
    </div>
    {input('Narration language',draft.narration.language,v=>onChange({...draft,narration:{...draft.narration,language:v}}))}
    {input('Voice character',draft.narration.voice_character,v=>onChange({...draft,narration:{...draft.narration,voice_character:v}}),true)}
    {candidate&&<p className="text-xs text-amber-200">Draft revision {candidate.revision} saved. Approve this exact SHA to make it the active head.</p>}
    {error&&<p role="alert" className="text-sm text-rose-300">{error}</p>}
    <div className="flex flex-wrap gap-3">
     <button type="button" onClick={onSave} disabled={busy} data-testid="save-dna"
      className="rounded-2xl border border-cyan-400/30 bg-cyan-500/15 px-4 py-2 text-sm text-cyan-50 disabled:opacity-50">{busy?'Saving…':'Save draft revision'}</button>
     <button type="button" onClick={onApprove} disabled={busy||!candidate} data-testid="approve-dna"
      className="rounded-2xl border border-emerald-400/30 bg-emerald-500/10 px-4 py-2 text-sm text-emerald-100 disabled:opacity-50">Approve selected revision</button>
    </div>
   </div>}
 </section>;
}
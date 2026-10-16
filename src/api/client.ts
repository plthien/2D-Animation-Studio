/* Only the nineteen accepted animation C2 endpoints. */
const BASE = 'http://127.0.0.1:8000';

export class ApiError extends Error {
  constructor(public readonly errorCode: string, message: string, public readonly status: number) { super(message); }
}
export type Channel = {
  channel_id: string; name: string; slug: string; status: 'active'|'archived';
  current_dna_artifact_id: string|null; current_dna_revision: number|null;
  visual_style_hash: string; performance_style_hash: string; narration_identity_hash: string;
  created_at: string; updated_at: string;
};
export type Project = {
  project_id: string; channel_id: string; name: string; slug: string;
  status: 'active'|'archived'; created_at: string; updated_at: string;
};
export type DnaSource = {
  schema_version: 'channel_dna.v2';
  identity: {name:string; audience:string};
  visual: {style:string; palette:string[]};
  performance: {tone:string; motion_density:'low'|'medium'|'high'};
  narration: {language:string; voice_character:string};
};
export type DnaDocument = DnaSource & {
  artifact_id:string; channel_id:string; revision:number; created_at:string;
  visual_style_hash:string; performance_style_hash:string; narration_identity_hash:string;
};
export type DnaHead = {channel:Channel;head_artifact_id:string|null;head_revision:number|null;channel_dna:DnaDocument|null};
export type Artifact = {
  artifact_id:string; channel_id:string; project_id:string|null; kind:string;
  schema_version:string; logical_key:string; revision:number; approval_status:string;
  sha256:string; byte_size:number; relative_artifact_handle:string; created_at:string;
  metadata:Record<string,unknown>;
};
export type StageProjection = {
  stage_key:'authoring'|'resolver'|'generation'|'rigging'|'director'|'motion'|'delivery';
  approval_status:'draft'|'approved'|'rejected';
  readiness:'blocked'|'ready'|'draft'|'approved'|'stale'|'running'|'failed';
  head_artifact_id:string|null; head_revision:number;
  stored_dependency_fingerprint:string; computed_dependency_fingerprint:string;
  blocker_codes:string[]; owner_phase:string;
};
export type Workflow = {project_id:string; channel_id:string;dependency_fingerprint_algorithm_version:string; stages:StageProjection[]};
export type Job = {job_id:string;operation_id:string|null;project_id:string;channel_id:string;kind:string;status:string;progress_message:string;progress_percent:number;created_at:string;updated_at:string};
export type Page<T> = {items:T[];next_cursor:string|null};

type Envelope<T> = {data:T;meta:{request_id:string;schema_version:string}};
function query(params:Record<string,string|number|null|undefined>):string {
  const p=new URLSearchParams();
  for(const [key,value] of Object.entries(params)) if(value!==null&&value!==undefined) p.set(key,String(value));
  return '?' + p.toString();
}
async function request<T>(method:string,path:string, body?:unknown,key?:string):Promise<T> {
  const response = await fetch(BASE+path, {
    method, headers:{'Content-Type':'application/json', ...(key?{'Idempotency-Key':key}:{})},
    ...(body===undefined?{}:{body:JSON.stringify(body)}),
  });
  const payload = await response.json() as Envelope<T>|{error:{code:string;message:string;details:unknown;request_id:string}};
  if(!response.ok) {
    const err='error' in payload? payload.error:null;
    throw new ApiError(err?.code??'HTTP_ERROR',err?.message??response.statusText,response.status);
  }
  if(!('data' in payload)) throw new ApiError('RESPONSE_INVALID','Expected data envelope',502);
  return payload.data;
}
export const apiClient = {
  health:()=>request<{status:string;product:string}>('GET','/health'),
  system:()=>request<{product:string;database_revision:string;stages:string[];animation_generation_ready:boolean}>('GET','/api/v1/system'),
  listChannels:(limit=50,cursor?:string)=>request<Page<Channel>>('GET','/api/v1/channels'+query({limit,cursor})),
  createChannel:(body:{name:string;slug:string},key:string)=>request<Channel>('POST','/api/v1/channels',body,key),
  getChannel:(id:string)=>request<Channel>('GET',\`/api/v1/channels/\${id}\`),
  updateChannel:(id:string,body:{expected_updated_at:string;name?:string;slug?:string})=>request<Channel>('PATCH',\`/api/v1/channels/\${id}\`,body),
  archiveChannel:(id:string,expected_updated_at:string)=>request<Channel>('DELETE',\`/api/v1/channels/\${id}\`,{expected_updated_at}),
  dnaHead:(id:string)=>request<DnaHead>('GET',\`/api/v1/channels/\${id}/dna\`),
  saveDna:(id:string,body:{channel_dna:DnaSource;expected_head_revision:number|null;expected_head_artifact_id:string|null},key:string)=>request<Artifact>('PUT',\`/api/v1/channels/\${id}/dna\`,body,key),
  approveDna:(id:string,aid:string,body:{expected_head_revision:number|null;expected_sha256:string;actor:string;reviewed_at:string})=>request<DnaHead>('POST',\`/api/v1/channels/\${id}/dna/\${aid}/approve\`,body),
  listProjects:(channel_id:string)=>request<Page<Project>>('GET','/api/v1/projects'+query({channel_id,limit:100})),
  createProject:(body:{channel_id:string;name:string;slug:string},key:string)=>request<Project>('POST','/api/v1/projects',body,key),
  getProject:(id:string)=>request<Project>('GET',\`/api/v1/projects/\${id}\`),
  updateProject:(id:string,body:{expected_updated_at:string;name?:string;slug?:string})=>request<Project>('PATCH',\`/api/v1/projects/\${id}\`,body),
  archiveProject:(id:string,expected_updated_at:string)=>request<Project>('DELETE',\`/api/v1/projects/\${id}\`,{expected_updated_at}),
  workflow:(pid:string)=>request<Workflow>('GET',\`/api/v1/projects/\${pid}/workflow\`),
  jobs:(pid:string)=>request<Page<Job>>('GET','/api/v1/jobs'+query({project_id:pid})),
  job:(jid:string)=>request<Job>('GET',\`/api/v1/jobs/\${jid}\`),
  artifact:(aid:string,cid?:string)=>request<Artifact>('GET',\`/api/v1/artifacts/\${aid}\`+query({channel_id:cid})),
};

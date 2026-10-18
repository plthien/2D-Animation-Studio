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
  getChannel:(id:string)=>request<Channel>('GET',`/api/v1/channels/${id}`),
  updateChannel:(id:string,body:{expected_updated_at:string;name?:string;slug?:string})=>request<Channel>('PATCH',`/api/v1/channels/${id}`,body),
  archiveChannel:(id:string,expected_updated_at:string)=>request<Channel>('DELETE',`/api/v1/channels/${id}`,{expected_updated_at}),
  dnaHead:(id:string)=>request<DnaHead>('GET',`/api/v1/channels/${id}/dna`),
  saveDna:(id:string,body:{channel_dna:DnaSource;expected_head_revision:number|null;expected_head_artifact_id:string|null},key:string)=>request<Artifact>('PUT',`/api/v1/channels/${id}/dna`,body,key),
  approveDna:(id:string,aid:string,body:{expected_head_revision:number|null;expected_sha256:string;actor:string;reviewed_at:string})=>request<DnaHead>('POST',`/api/v1/channels/${id}/dna/${aid}/approve`,body),
  listProjects:(channel_id:string)=>request<Page<Project>>('GET','/api/v1/projects'+query({channel_id,limit:100})),
  createProject:(body:{channel_id:string;name:string;slug:string},key:string)=>request<Project>('POST','/api/v1/projects',body,key),
  getProject:(id:string)=>request<Project>('GET',`/api/v1/projects/${id}`),
  updateProject:(id:string,body:{expected_updated_at:string;name?:string;slug?:string})=>request<Project>('PATCH',`/api/v1/projects/${id}`,body),
  archiveProject:(id:string,expected_updated_at:string)=>request<Project>('DELETE',`/api/v1/projects/${id}`,{expected_updated_at}),
  workflow:(pid:string)=>request<Workflow>('GET',`/api/v1/projects/${pid}/workflow`),
  jobs:(pid:string)=>request<Page<Job>>('GET','/api/v1/jobs'+query({project_id:pid})),
  job:(jid:string)=>request<Job>('GET',`/api/v1/jobs/${jid}`),
  authoringPrompt:(pid:string,kind:string)=>request<AuthoringPackage>('POST',`/api/v1/projects/${pid}/authoring/${kind}/prompt`,{}),
  authoringValidate:(pid:string,kind:string,reservation_id:string,document:Record<string,unknown>)=>request<ValidationReport>('POST',`/api/v1/projects/${pid}/authoring/${kind}/validate`,{reservation_id,document}),
  authoringImport:(pid:string,kind:string,reservation_id:string,document:Record<string,unknown>)=>request<Artifact>('POST',`/api/v1/projects/${pid}/authoring/${kind}/import`,{reservation_id,document}),
  authoringApprove:(pid:string,kind:string,aid:string,expected_head_revision:number,expected_sha256:string)=>request<{artifact_id:string;revision:number;sha256:string}>('POST',`/api/v1/projects/${pid}/authoring/${kind}/${aid}/approve`,{expected_head_revision,expected_sha256}),
  authoringHistory:(pid:string,kind:string)=>request<Page<Artifact>>('GET',`/api/v1/projects/${pid}/authoring/${kind}/history`),
  authoringDocument:(pid:string,aid:string)=>request<{artifact:Artifact;document:Record<string,unknown>}>('GET',`/api/v1/projects/${pid}/authoring/revisions/${aid}`),
  resolverRequirements:(pid:string)=>request<AssetRequirements>('GET',`/api/v1/projects/${pid}/resolver/requirements`),
  assetResolution:(pid:string)=>request<AssetResolution>('GET',`/api/v1/projects/${pid}/resolver/resolution`),
  assetVersions:(cid:string)=>request<Page<AssetVersion>>('GET',`/api/v1/channels/${cid}/assets`),
  bindAsset:(pid:string,requirement_id:string,asset_version_id:string,expected_fingerprint:string)=>request<AssetBinding>('POST',`/api/v1/projects/${pid}/asset-bindings`,{requirement_id,asset_version_id,expected_fingerprint}),
  unbindAsset:(pid:string,binding_id:string,expected_fingerprint:string)=>request<{removed_binding_id:string}>('DELETE',`/api/v1/projects/${pid}/asset-bindings/${binding_id}`,{expected_fingerprint}),
  reviewImage:(pid:string,version:string,decision:'approved'|'rejected')=>request<{asset_version_id:string;status:string}>('POST',`/api/v1/projects/${pid}/assets/${version}/review`,{decision}),
  imageSrc:(pid:string,version:string)=>BASE+`/api/v1/projects/${pid}/assets/${version}/image`,
  uploadImage:async(pid:string,kind:string,semantic_key:string,view:string,file:File)=>{
    const form=new FormData();form.set('file',file);form.set('kind',kind);form.set('semantic_key',semantic_key);form.set('view',view);
    const response=await fetch(BASE+`/api/v1/projects/${pid}/images/import`,{method:'POST',body:form});
    const value=await response.json() as Envelope<ImageCandidate>|{error:{code:string;message:string}};
    if(!response.ok||!('data' in value))throw new ApiError('error' in value?value.error.code:'HTTP_ERROR','error' in value?value.error.message:'Upload failed',response.status);
    return value.data;
  },
  glabsConfig:(pid:string)=>request<GLabsConfig>('GET',`/api/v1/projects/${pid}/generation/provider`),
  glabsPrepare:(pid:string,body:{requirement_id:string;prompt:string;negative_prompt:string;model:string;aspect_ratio:string;cost_ceiling_usd:number})=>request<GLabsQuote>('POST',`/api/v1/projects/${pid}/generation/prepare`,body),
  glabsConfirm:(pid:string,quote:GLabsQuote, key:string)=>request<GLabsOperation>('POST',`/api/v1/projects/${pid}/generation/confirm`,{quote:quote.quote,fingerprint:quote.fingerprint,explicitly_approved:true},key),
  glabsAdvance:(pid:string,oid:string)=>request<GLabsOperation>('POST',`/api/v1/projects/${pid}/generation/operations/${oid}/advance`,{}),
  glabsReconcile:(pid:string,oid:string,provider_task_id:string)=>request<GLabsOperation>('POST',`/api/v1/projects/${pid}/generation/operations/${oid}/reconcile`,{provider_task_id,confirmed_owner_match:true}),
  glabsCancel:(pid:string,oid:string)=>request<GLabsOperation>('POST',`/api/v1/projects/${pid}/generation/operations/${oid}/cancel`,{}),
  glabsStatus:(pid:string,oid:string)=>request<GLabsOperation>('GET',`/api/v1/projects/${pid}/generation/operations/${oid}`),
  glabsOperations:(pid:string)=>request<Page<Pick<GLabsOperation,'operation_id'|'status'>>>('GET',`/api/v1/projects/${pid}/generation/operations`),

  rigList:(pid:string)=>request<{items:RigRecord[]}>('GET',`/api/v1/projects/${pid}/rigging/rigs`),
  rigStart:(pid:string,asset_version_id:string)=>request<{rig_id:string;draft_revision:number}>('POST',`/api/v1/projects/${pid}/rigging/rigs`,{asset_version_id}),
  rigDraft:(pid:string,rig:string)=>request<RigDraft>('GET',`/api/v1/projects/${pid}/rigging/rigs/${rig}`),
  rigEdit:(pid:string,rig:string,role:string,body:{expected_revision:number;strokes?:RigStroke[];pivot?:{x:number;y:number};layer?:number;reviewed?:boolean;reset?:boolean})=>request<{draft_revision:number}>('POST',`/api/v1/projects/${pid}/rigging/rigs/${rig}/parts/${role}`,body),
  rigExport:(pid:string,rig:string,expected_revision:number)=>request<RigExport>('POST',`/api/v1/projects/${pid}/rigging/rigs/${rig}/export`,{expected_revision}),
  rigPartImage:(pid:string,rig:string,role:string,kind:'mask'|'sprite')=>BASE+`/api/v1/projects/${pid}/rigging/rigs/${rig}/parts/${role}/${kind}`,
  rigOutput:(cid:string,rig:string,version:string,file:string)=>BASE+`/api/v1/channels/${cid}/rigs/${rig}/versions/${version}/${file}`,
  rigVerify:(cid:string,rig:string,version:string,body:RigProofPayload)=>request<RigProofResult>('POST',`/api/v1/channels/${cid}/rigs/${rig}/versions/${version}/verify`,body),
  rigReview:(cid:string,rig:string,version:string,expected_revision:number,decision:'approved'|'rejected')=>request<{status:string}>('POST',`/api/v1/channels/${cid}/rigs/${rig}/versions/${version}/review`,{expected_revision,decision}),
  rigReplace:async(pid:string,rig:string,role:string,expected_revision:number,file:File)=>{
    const form=new FormData();form.set('file',file);form.set('expected_revision',String(expected_revision));
    const res=await fetch(BASE+`/api/v1/projects/${pid}/rigging/rigs/${rig}/parts/${role}/replacement`,{method:'POST',body:form});
    const payload=await res.json();
    if(!res.ok)throw new ApiError(payload?.error?.code??'UPLOAD_FAILED',payload?.error?.message??'Replacement failed',res.status);
    return payload.data as {draft_revision:number};
  },
  artifact:(aid:string,cid?:string)=>request<Artifact>('GET',`/api/v1/artifacts/${aid}`+query({channel_id:cid})),
};

export type ValidationReport={valid:boolean;issues:Array<{path:string;message:string}>;source_fingerprint:string};
export type AuthoringPackage={prompt_text:string;source_metadata:Artifact|null;dna_metadata:Artifact;source_inputs:Record<string,unknown>;analysis_metadata:Artifact|null;analysis:Record<string,unknown>|null;reservation_id:string;reserved_artifact_id:string;revision:number;expires_at:string;source_fingerprint:string;schema:Record<string,unknown>;source:unknown;channel_dna:unknown;instructions:string;reserved_fields:Record<string,unknown>};

export type AssetRequirement={requirement_id:string;kind:'actor'|'prop'|'location'|'background';semantic_key:string;view:string;shot_ids:string[];required_capabilities:string[]};
export type AssetRequirements={project_id:string;channel_id:string;fingerprint:string;requirements:AssetRequirement[]};
export type AssetBinding={binding_id:string;asset_version_id:string;source_fingerprint:string};
export type AssetResolution={compatible_versions:Record<string,string[]>;rig_capability_status:string;requirements_fingerprint:string;requirements:Array<{requirement:AssetRequirement;binding:AssetBinding|null;state:'resolved'|'unresolved';reason:string|null}>;resolved_count:number;total_count:number};
export type AssetVersion={asset_version_id:string;asset_id:string;kind:string;semantic_key:string;view_key:string;revision:number;status:'candidate'|'approved'|'rejected';visual_style_hash:string;capability_hash:string;source_sha256:string};
export type ImageCandidate={asset_version_id:string;asset_id:string;artifact_id:string;source_image_artifact_id:string;width:number;height:number;status:'candidate';source_sha256:string};

export type GLabsConfig={provider:string;configured:boolean;base_url:string;live_test:string};
export type GLabsQuote={quote:Record<string,unknown>;fingerprint:string;cost_ceiling_usd:number;estimated_cost_usd:null;explicit_confirmation_required:boolean};
export type GLabsOperation={operation_id:string;status:'queued'|'running'|'unknown'|'completed'|'failed'|'cancelled';result?:{candidate?:ImageCandidate};error?:{code:string};task?:Record<string,unknown>};

export type RigStroke={x:number;y:number;radius:number;mode:'paint'|'erase'};
export type RigPart={role:string;layer:number;reviewed:boolean;provenance:string;confidence:number;uncertain:boolean;occluded:boolean;reason:string;pivot:{x:number;y:number;coordinate_system:string};mask:string;replacement:string|null};
export type RigDraft={rig_id:string;draft_revision:number;source_version:string;source_sha:string;style_hash:string;size:[number,number];parts:Record<string,RigPart>};
export type RigRecord={rig_id:string;channel_id:string;asset_id:string;semantic_key:string;rig_version_id:string|null;status:string|null;revision:number|null};
export type RigExport={rig_id:string;rig_version_id:string;revision:number;candidate:boolean;loader_verified:boolean;manifest:{skeleton_sha256:string;atlas_sha256:string}};

export type RigPoseProof={pose:'idle'|'walk'|'reach'|'grab'|'neutral_return';png_base64:string;bones:Record<string,number>;bone_count:number;slot_count:number;attached_slot_count:number};
export type RigProofPayload={source_sha256:string;skeleton_sha256:string;atlas_sha256:string;runtime_package:string;runtime_version:string;pixi_version:string;poses:RigPoseProof[]};
export type RigProofResult={rig_version_id:string;proof_artifact_id:string;pose_png_sha256:Record<string,string>;verified_images:number};

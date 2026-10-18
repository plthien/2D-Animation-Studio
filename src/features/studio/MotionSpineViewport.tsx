import {useCallback,useEffect,useRef,useState} from 'react';
import {Application,Assets,Sprite,Texture} from 'pixi.js';
import {Spine} from '@esotericsoftware/spine-pixi-v8';
import {apiClient,type MotionFrame,type AssetResolution} from '../../api/client';
type Identity={rig_id:string;rig_version_id:string};
const REQUIRED=['root','hip','chest','head','left_upper_arm','left_lower_arm','left_hand',
 'right_upper_arm','right_lower_arm','right_hand','left_upper_leg','left_lower_leg','left_foot',
 'right_upper_leg','right_lower_leg','right_foot'];
export function MotionSpineViewport({projectId,channelId,shotId,compilationId,frame,onState}:
 {projectId:string;channelId:string;shotId:string;compilationId:string;frame:number;
  onState?:(frame:MotionFrame)=>void}){
 const mount=useRef<HTMLDivElement>(null);
 const app=useRef<Application|null>(null);
 const figures=useRef<Record<string,Spine>>({});
 const propSprites=useRef<Record<string,Sprite>>({});
 const loadedRig=useRef<Record<string,Identity>>({});
 const [ready,setReady]=useState(false);
 const [error,setError]=useState('');
 const [identity,setIdentity]=useState('');
 const epoch=useRef(0);
 useEffect(()=>{
  const ticket=++epoch.current;let disposed=false;let instance:Application|null=null;
  let initialized=false;
  const cleanupInstance=()=>{
   if(!initialized||!instance)return;
   if(app.current===instance)app.current=null;
   instance.destroy(true);
   initialized=false;
  };
  figures.current={};propSprites.current={};loadedRig.current={};
  setReady(false);setError('');setIdentity('');
  const setup=async()=>{
   instance=new Application();
   await instance.init({width:1280,height:720,background:0x111827,
    preference:'webgl',antialias:true,preserveDrawingBuffer:true});
   initialized=true;
   if(disposed||ticket!==epoch.current){cleanupInstance();return;}
   mount.current?.replaceChildren(instance.canvas);
   instance.ticker.stop();app.current=instance;setReady(true);
  };
  void setup().catch(e=>{if(!disposed)setError(String(e));});
  return()=>{disposed=true;epoch.current++;figures.current={};propSprites.current={};
   loadedRig.current={};cleanupInstance();};
 },[projectId,channelId,compilationId,shotId]);

 const renderFrame=useCallback(async(index:number)=>{
  const ticket=epoch.current;const application=app.current;
  if(!application||!ready)return;
  const data=await apiClient.motionFrame(projectId,compilationId,shotId,index);
  if(ticket!==epoch.current||!app.current)return;
  const resolution:AssetResolution=await apiClient.assetResolution(projectId);
  const figuresNow=figures.current;
  for(const [actor,rig] of Object.entries(data.rigs)){
   let spine=figuresNow[actor];
   if(!spine){
    const skeleton=apiClient.rigOutput(channelId,rig.rig_id,rig.rig_version_id,'skeleton.json');
    const atlas=apiClient.rigOutput(channelId,rig.rig_id,rig.rig_version_id,'skeleton.atlas');
    const response=await fetch(skeleton,{cache:'no-store'});
    if(!response.ok)throw new Error('Rig skeleton HTTP '+response.status);
    const skeletonJson=await response.json() as {skeleton:{spine:string};bones:Array<{name:string}>};
    if(!skeletonJson.skeleton.spine.startsWith('4.2.'))throw new Error('Only Spine 4.2 rigs supported');
    for(const bone of REQUIRED)if(!skeletonJson.bones.some(x=>x.name===bone))
      throw new Error('Rig is missing required bone: '+bone);
    const asset='c5_'+rig.rig_version_id;
    Assets.add({alias:asset+'_skeleton',src:skeleton});
    Assets.add({alias:asset+'_atlas',src:atlas});
    await Assets.load([asset+'_skeleton',asset+'_atlas']);
    if(ticket!==epoch.current)return;
    spine=Spine.from({skeleton:asset+'_skeleton',atlas:asset+'_atlas',autoUpdate:false});
    application.stage.addChild(spine);figuresNow[actor]=spine;
    loadedRig.current[actor]=rig;
   }
   spine.state.clearTracks();
   spine.skeleton.setToSetupPose();
   const pose=data.poses[actor];
   if(!pose)throw Error('Motion frame omitted actor '+actor);
   for(const [role,degrees] of Object.entries(pose.bones)){
    const bone=spine.skeleton.findBone(role);
    if(!bone)throw Error('Motion bone missing from actual rig: '+role);
    bone.rotation=bone.data.rotation+degrees;
   }
   const worldScale=0.8;
   spine.scale.set(worldScale);
   spine.position.set(640+worldScale*pose.root.x,590-worldScale*pose.root.y);
   spine.update(0);
  }
  for(const [propId,prop] of Object.entries(data.props)){
   let sprite=propSprites.current[propId];
   if(!sprite){
    const binding=resolution.requirements.find(row=>
      row.requirement.kind==='prop'&&row.requirement.semantic_key===propId)?.binding;
    if(!binding)throw Error('Exact approved prop image binding missing: '+propId);
    const image=apiClient.imageSrc(projectId,binding.asset_version_id);
    // Version-image URLs are extensionless API routes. Pixi Assets.load selects a
    // parser using the extension and can return null for this real PNG endpoint.
    // Decode the browser image first, then build the Pixi v8 ImageSource texture.
    const resource=new Image();
    // The Studio runs on :5173 while the local image API runs on :8000.
    // Request CORS-clean pixels BEFORE setting src or WebGL will reject upload.
    resource.crossOrigin='anonymous';
    resource.src=image;
    await resource.decode();
    if(ticket!==epoch.current)return;
    const tex=Texture.from(resource);
    if(!tex||!tex.source||tex.width<=0||tex.height<=0){
     throw new Error('PROPS_TEXTURE_INVALID: '+propId);
    }
    sprite=new Sprite(tex);sprite.anchor.set(0.5,0.5);sprite.scale.set(.4);
    propSprites.current[propId]=sprite;application.stage.addChild(sprite);
   }
   sprite.position.set(640+0.8*prop.x,590-0.8*prop.y);
  }
  if(ticket!==epoch.current)return;
  application.renderer.render({container:application.stage});
  setIdentity(data.fingerprint);onState?.(data);
 },[ready,projectId,channelId,compilationId,shotId,onState]);
 useEffect(()=>{
  if(!ready)return;
  void renderFrame(frame).catch(e=>setError(e instanceof Error?(e.stack||e.message):String(e)));
 },[ready,frame,renderFrame]);
 return <div className="space-y-2" data-testid="c5-spine-pixi-viewport">
  <div ref={mount} className="max-w-full overflow-auto rounded-xl border border-white/10"/>
  {ready?<p className="text-xs text-emerald-300">Official Spine 4.2 / PixiJS 8 WebGL viewport</p>:
   <p className="text-xs text-amber-300">Initializing official Spine/Pixi renderer…</p>}
  {error&&<p role="alert" className="text-rose-300">{error}</p>}
  {identity&&<p className="break-all font-mono text-xs text-slate-500">Deterministic frame: {identity}</p>}
  <button disabled={!identity} className="rounded-xl border border-white/10 px-3 py-2 text-sm text-slate-200"
    onClick={()=>{const link=document.createElement('a');link.download='c5-'+shotId+'-'+frame+'.png';
      link.href=app.current?.canvas.toDataURL('image/png')||'';link.click();}}>
   Save real WebGL frame PNG
  </button>
 </div>;
}

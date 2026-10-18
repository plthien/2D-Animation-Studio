import {useEffect,useRef,useState} from 'react';
import {Application,Assets} from 'pixi.js';
import {Spine} from '@esotericsoftware/spine-pixi-v8';
import {apiClient,type RigExport} from '../../api/client';

type Pose='idle'|'walk'|'reach'|'grab'|'neutral_return';
const poses:Record<Pose,Record<string,number>>={
 idle:{},walk:{left_upper_leg:23,right_upper_leg:-23,left_lower_leg:-16,right_lower_leg:16,left_upper_arm:-15,right_upper_arm:15},
 reach:{left_upper_arm:-45,left_lower_arm:-35,left_hand:10},
 grab:{left_upper_arm:-50,left_lower_arm:-40,left_hand:35},neutral_return:{}
};
export function SpineViewport({channelId,rigId,candidate}:{channelId:string;rigId:string;candidate:RigExport}){
 const mount=useRef<HTMLDivElement>(null);
 const [pose,setPose]=useState<Pose>('idle');
 const [error,setError]=useState('');
 const [loaded,setLoaded]=useState(false);
 const rig=useRef<Spine|null>(null);
 const application=useRef<Application|null>(null);
 useEffect(()=>{
  let live=true;let instance:Application|null=null;
  setError('');setLoaded(false);
  const init=async()=>{
   const id=candidate.rig_version_id;
   const prefix=apiClient.rigOutput(channelId,rigId,id,'');
   const skeleton=prefix+'skeleton.json',atlas=prefix+'skeleton.atlas';
   const [skeletonResponse,atlasResponse]=await Promise.all([fetch(skeleton,{cache:'no-store'}),fetch(atlas,{cache:'no-store'})]);
   if(!skeletonResponse.ok||!atlasResponse.ok)throw new Error('Export files not accessible');
   const json=await skeletonResponse.json() as {bones:Array<{name:string}>;slots:Array<{name:string}>;skeleton:{spine:string}};
   if(!json.skeleton.spine.startsWith('4.2.'))throw new Error('SPINE_VERSION_MISMATCH');
   const needed=['root','hip','chest','head','left_upper_arm','left_lower_arm','left_hand','right_upper_arm','right_lower_arm','right_hand','left_upper_leg','left_lower_leg','left_foot','right_upper_leg','right_lower_leg','right_foot'];
   for(const bone of needed)if(!json.bones.some(row=>row.name===bone))throw new Error('REQUIRED_BONE_MISSING: '+bone);
   const atlasText=await atlasResponse.text();
   for(const slot of json.slots)if(!atlasText.includes('\n'+slot.name+'\n'))throw new Error('ATLAS_REGION_MISSING: '+slot.name);
   instance=new Application();
   await instance.init({width:720,height:540,background:0x161e2c,preference:'webgl',antialias:true});
   if(!live){instance.destroy();return;}
   if(!mount.current)throw new Error('Viewport is not mounted');
   mount.current.appendChild(instance.canvas);
   instance.ticker.stop();
   const identity='c4_'+id;
   Assets.add({alias:identity+'_skeleton',src:skeleton});
   Assets.add({alias:identity+'_atlas',src:atlas});
   await Assets.load([identity+'_skeleton',identity+'_atlas']);
   if(!live)return;
   const spine=Spine.from({skeleton:identity+'_skeleton',atlas:identity+'_atlas',autoUpdate:false});
   if(!spine.skeleton.bones.length)throw new Error('SPINE_LOADER_EMPTY');
   for(const bone of needed)if(!spine.skeleton.findBone(bone))throw new Error('SPINE_MISSING_BONE: '+bone);
   spine.position.set(360,480);
   spine.scale.set(.70);
   instance.stage.addChild(spine);
   application.current=instance;rig.current=spine;
   setLoaded(true);
  };
  void init().catch(e=>{if(live)setError(String(e));});
  return()=>{live=false;rig.current=null;application.current=null;instance?.destroy(true);};
 },[channelId,rigId,candidate.rig_version_id]);
 useEffect(()=>{
  const spine=rig.current,app=application.current;
  if(!spine||!app||!loaded)return;
  spine.state.clearTracks();
  spine.skeleton.setToSetupPose();
  for(const [name,degree] of Object.entries(poses[pose])){
   const bone=spine.skeleton.findBone(name);
   if(bone)bone.rotation=bone.data.rotation+degree;
  }
  spine.update(0);
  app.renderer.render({container:app.stage});
 },[loaded,pose]);
 return <div className="space-y-2 rounded-xl border border-white/10 p-3" data-testid="c4-official-runtime">
  <h4 className="font-semibold text-slate-100">Official Spine/PixiJS pose preview</h4>
  <div ref={mount} className="overflow-hidden rounded-lg max-w-full"/>
  {error&&<p className="text-rose-300" role="alert">{error}</p>}
  <p className={loaded?'text-emerald-300':'text-amber-300'}>{loaded?'Official loader succeeded in current browser session (not backend approval proof)':'Loading or blocked'}</p>
  <div className="flex flex-wrap gap-2">
   {(['idle','walk','reach','grab','neutral_return'] as Pose[]).map(key=><button type="button" key={key} onClick={()=>setPose(key)} disabled={!loaded}
    className={'rounded-lg border px-3 py-1 text-sm '+(pose===key?'border-cyan-400 text-cyan-200':'border-white/10 text-slate-300')}>{key}</button>)}
  </div>
  <button type="button" disabled={!loaded} onClick={()=>{const canvas=application.current?.canvas;if(canvas){const link=document.createElement('a');link.download='c4-'+candidate.rig_version_id+'-'+pose+'.png';link.href=canvas.toDataURL('image/png');link.click();}}}
   className="rounded-lg border border-white/20 p-2 text-sm text-slate-200">Save real pose screenshot</button>
  <p className="text-xs text-slate-400">A browser render does not grant rig approval until a trusted runtime verification flow is complete.</p>
 </div>;
}

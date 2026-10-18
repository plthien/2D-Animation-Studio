import {useEffect,useRef,useState} from 'react';
import {Application,Assets} from 'pixi.js';
import {Spine} from '@esotericsoftware/spine-pixi-v8';
import {apiClient,type MotionCapabilityStatus,type MotionCapabilitySample} from '../../api/client';

const poses:Record<string,{angles:Record<string,number>;x:number}>={
 idle:{angles:{},x:0},
 walk_to:{angles:{left_upper_leg:24,right_upper_leg:-24,left_lower_leg:-12,right_lower_leg:12},x:40},
 look_at:{angles:{head:20},x:0},
 reach_for:{angles:{left_upper_arm:-40,left_lower_arm:-26},x:0},
 grab:{angles:{left_upper_arm:-48,left_lower_arm:-33,left_hand:30},x:0},
 carry_to:{angles:{left_upper_leg:18,right_upper_leg:-18,left_upper_arm:-36,left_lower_arm:-20,left_hand:25},x:65},
 place_at:{angles:{left_upper_arm:-28,left_lower_arm:-45,left_hand:-10},x:0},
 point_at:{angles:{right_upper_arm:55,right_lower_arm:20},x:0},
 react:{angles:{chest:22,head:-13,left_upper_arm:15},x:0}
};
const button='rounded-lg border border-white/15 px-3 py-2 text-xs text-slate-200 disabled:opacity-40 hover:bg-white/10';
export function CapabilityProofPanel({projectId,channelId,onChanged}:{projectId:string;channelId:string;onChanged:()=>void}){
 const mount=useRef<HTMLDivElement>(null);
 const [info,setInfo]=useState<MotionCapabilityStatus|null>(null);
 const [busy,setBusy]=useState(false);
 const [error,setError]=useState('');
 const [message,setMessage]=useState('');
 const refresh=()=>apiClient.motionCapabilities(projectId).then(setInfo).catch(e=>setError(String(e)));
 useEffect(()=>{void refresh();},[projectId]);
 const prove=async(rig:{rig_id:string;rig_version_id:string})=>{
  setBusy(true);setError('');setMessage('Loading official Spine/Pixi rig for nine-action proof…');
  const app=new Application();
  try{
   await app.init({width:420,height:380,background:0x111827,preference:'webgl',antialias:true,preserveDrawingBuffer:true});
   mount.current?.replaceChildren(app.canvas);
   app.ticker.stop();
   const id='c5_cert_'+rig.rig_version_id;
   const skeleton=apiClient.rigOutput(channelId,rig.rig_id,rig.rig_version_id,'skeleton.json');
   const atlas=apiClient.rigOutput(channelId,rig.rig_id,rig.rig_version_id,'skeleton.atlas');
   Assets.add({alias:id+'_skeleton',src:skeleton});
   Assets.add({alias:id+'_atlas',src:atlas});
   await Assets.load([id+'_skeleton',id+'_atlas']);
   const spine=Spine.from({skeleton:id+'_skeleton',atlas:id+'_atlas',autoUpdate:false});
   for(const key of Object.keys(poses))for(const bone of Object.keys(poses[key].angles))
    if(!spine.skeleton.findBone(bone))throw Error('Mandatory pose bone missing: '+bone);
   app.stage.addChild(spine);
   const captures:MotionCapabilitySample[]=[];
   for(const [action,target] of Object.entries(poses)){
    spine.state.clearTracks();spine.skeleton.setToSetupPose();
    for(const [name,delta] of Object.entries(target.angles)){
     const bone=spine.skeleton.findBone(name);
     if(!bone)throw Error('Spine runtime missing bone '+name);
     bone.rotation=bone.data.rotation+delta;
    }
    spine.position.set(210+target.x,365);spine.scale.set(.62);
    spine.update(0);app.renderer.render({container:app.stage});
    const png=app.canvas.toDataURL('image/png');
    if(!png.startsWith('data:image/png;base64,'))throw Error('Official WebGL canvas cannot capture PNG');
    captures.push({action,png_base64:png.split(',')[1],root:{x:target.x,y:0},
      bones:Object.fromEntries(spine.skeleton.bones.map(b=>[b.data.name,b.rotation])),
      bone_count:spine.skeleton.bones.length,
      attached_slot_count:spine.skeleton.slots.filter(slot=>slot.getAttachment()).length});
   }
   setMessage('Checking screenshot and bone evidence against approved C4 rig…');
   const result=await apiClient.motionVerifyCapabilities(projectId,rig.rig_version_id,captures);
   setMessage('Approved immutable C5 capability certificate: '+result.artifact_id);
   onChanged();await refresh();
  }catch(e){setError(e instanceof Error?e.message:String(e));setMessage('Certification rejected');}
  finally{app.destroy(true);mount.current?.replaceChildren();setBusy(false);}
 };
 return <section className="space-y-3 rounded-xl border border-white/10 p-4" data-testid="c5-capability-proof">
  <h4 className="font-semibold text-slate-100">C4 Rig → C5 Motion capability certification</h4>
  <p className="text-xs text-slate-400">Existing immutable C4 rigs retain their original capabilities. Additional semantic actions require explicit runtime proof for the exact version; rig atlases are never rewritten.</p>
  <div ref={mount} className="overflow-hidden rounded-lg"/>
  {info?.rigs.map(rig=><div key={rig.rig_version_id} className="flex flex-wrap justify-between gap-2 rounded-lg border border-white/10 p-3 text-xs text-slate-300">
   <span className="break-all">{rig.rig_version_id} · {rig.certified?'Nine certified actions':'Original C4 capabilities only'}</span>
   <button className={button} disabled={busy||rig.certified} onClick={()=>void prove(rig)}>
    {rig.certified?'Certified':'Verify nine official Spine poses'}</button>
  </div>)}
  {info?.readiness==='blocked'&&<p className="text-xs text-amber-300">Select and approve every required actor rig first.</p>}
  {message&&<p role="status" className="text-sm text-slate-300">{message}</p>}
  {error&&<p role="alert" className="text-xs text-red-300">{error}</p>}
 </section>;
}

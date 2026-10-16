import {QueryClient,QueryClientProvider,useQuery} from '@tanstack/react-query';
import {useEffect,useState} from 'react';
import {apiClient} from './api/client';
import {type AppView,type WorkspaceContext,readStoredSelection,writeStoredSelection,SELECTED_CHANNEL_STORAGE_KEY,SELECTED_PROJECT_STORAGE_KEY} from './app/workspace';
import {CockpitShell} from './layout/CockpitShell';
import {PageHeader} from './layout/PageHeader';
import {StatusBadge} from './components/ui/StatusBadge';
import {ErrorBanner} from './components/ui/ErrorBanner';
import {ChannelsPage} from './pages/ChannelsPage';
import {ProjectsPage} from './pages/ProjectsPage';
import {StudioPage} from './pages/StudioPage';
import {SettingsPage} from './pages/SettingsPage';
import {JobsPage} from './pages/JobsPage';
import {ArtifactsPage} from './pages/ArtifactsPage';

const routes:{id:AppView;path:string;label:string;description:string}[]=[
  {id:'channels',path:'/',label:'Channels',description:'Manage reusable animation styles and ChannelDNA v2.'},
  {id:'projects',path:'/projects',label:'Projects',description:'Channel-owned animation productions.'},
  {id:'studio',path:'/studio',label:'Studio',description:'Authoring → Resolver → Generation → Rigging → Director → Motion → Delivery.'},
  {id:'jobs',path:'/jobs',label:'Jobs',description:'Persisted operations only; no background producers in C2.'},
  {id:'artifacts',path:'/artifacts',label:'Artifacts',description:'Inspect immutable artifact metadata and lineage.'},
  {id:'settings',path:'/settings',label:'Settings',description:'Local-only runtime readiness and production boundaries.'}
];
function pathView():AppView{return routes.find(r=>r.path===window.location.pathname)?.id??'channels';}
function Shell() {
  const [view,setView]=useState<AppView>(pathView);
  const [channelId,setChannelState]=useState(()=>readStoredSelection(SELECTED_CHANNEL_STORAGE_KEY));
  const [projectId,setProjectState]=useState(()=>readStoredSelection(SELECTED_PROJECT_STORAGE_KEY));
  const [notice,setNotice]=useState('');
  const health=useQuery({queryKey:['health'],queryFn:apiClient.health,refetchInterval:30000,retry:1});
  const channels=useQuery({queryKey:['channels'],queryFn:()=>apiClient.listChannels(100)});
  const projects=useQuery({queryKey:['projects',channelId],queryFn:()=>apiClient.listProjects(channelId),enabled:Boolean(channelId)});
  const allChannels=channels.data?.items??[];
  const allProjects=projects.data?.items??[];
  const selectedChannel=allChannels.find(c=>c.channel_id===channelId)??null;
  const selectedProject=allProjects.find(p=>p.project_id===projectId)??null;
  function changeProject(id:string){setProjectState(id);writeStoredSelection(SELECTED_PROJECT_STORAGE_KEY,id);}
  function changeChannel(id:string){
    setChannelState(id);writeStoredSelection(SELECTED_CHANNEL_STORAGE_KEY,id);
    if(id!==channelId)changeProject('');
  }
  useEffect(()=>{
    if(!channels.isSuccess||!channelId)return;
    if(!allChannels.some(c=>c.channel_id===channelId)){changeChannel('');setNotice('Selected channel no longer exists.');}
  },[channels.isSuccess,channels.data,channelId]);
  useEffect(()=>{
    if(!projects.isSuccess||!projectId)return;
    if(!allProjects.some(p=>p.project_id===projectId)){changeProject('');setNotice('Selected project no longer belongs to this channel.');}
  },[projects.isSuccess,projects.data,projectId]);
  useEffect(()=>{
    const onPop=()=>setView(pathView());
    window.addEventListener('popstate',onPop);
    return ()=>window.removeEventListener('popstate',onPop);
  },[]);
  function navigate(next:AppView){
    setView(next);
    const path=routes.find(r=>r.id===next)?.path??'/';
    if(window.location.pathname!==path)window.history.pushState({},'',path);
  }
  const workspace:WorkspaceContext={
    channels:allChannels,projects:allProjects,
    selectedChannelId:channelId,selectedProjectId:projectId,
    selectedChannel,selectedProject,setSelectedChannelId:changeChannel,setSelectedProjectId:changeProject
  };
  const route=routes.find(r=>r.id===view)!;
  return <CockpitShell activeView={view} onNavigate={navigate} routes={routes}
    channelName={selectedChannel?.name??'No channel selected'}
    projectName={selectedProject?.name??'No project selected'}
    healthLabel={health.data?.status==='ok'?'Animation API ready':'API not ready'}>
    <PageHeader eyebrow="2D Animation Studio · C2" title={route.label} description={route.description}
      context={<>
        <div className="rounded-2xl border border-white/10 bg-white/[0.03] px-4 py-3 text-sm text-slate-100">Channel: {selectedChannel?.name??'Not selected'}</div>
        <div className="rounded-2xl border border-white/10 bg-white/[0.03] px-4 py-3 text-sm text-slate-100">Project: {selectedProject?.name??'Not selected'}</div>
        <StatusBadge status={selectedChannel?.current_dna_artifact_id?'approved':'draft'} label={selectedChannel?.current_dna_artifact_id?'DNA approved':'DNA missing'}/>
      </>}
      actions={<StatusBadge status={health.data?.status==='ok'?'approved':'failed'} label={health.data?.status==='ok'?'Backend ready':'Backend unavailable'}/>}
    />
    <div className="space-y-4">
      {notice&&<div className="rounded-2xl border border-amber-400/30 px-4 py-3 text-amber-200">{notice}</div>}
      {channels.error&&<ErrorBanner message={String(channels.error)}/>}
      {projects.error&&<ErrorBanner message={String(projects.error)}/>}
      {health.error&&<ErrorBanner message={String(health.error)}/>}
      {view==='channels'&&<ChannelsPage workspace={workspace} onNavigate={navigate}/>}
      {view==='projects'&&<ProjectsPage workspace={workspace} onNavigate={navigate}/>}
      {view==='studio'&&<StudioPage workspace={workspace} onNavigate={navigate}/>}
      {view==='jobs'&&<JobsPage workspace={workspace}/>}
      {view==='artifacts'&&<ArtifactsPage workspace={workspace}/>}
      {view==='settings'&&<SettingsPage/>}
    </div>
  </CockpitShell>;
}
const client=new QueryClient({defaultOptions:{queries:{retry:1,staleTime:2500}}});
export default function App(){return <QueryClientProvider client={client}><Shell/></QueryClientProvider>;}

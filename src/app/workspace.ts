import type { Channel, Project } from '../api/client';

export type AppView='settings'|'channels'|'projects'|'studio'|'jobs'|'artifacts';
export type WorkspaceContext={
  channels:Channel[]; projects:Project[];
  selectedChannelId:string;selectedProjectId:string;
  selectedChannel:Channel|null;selectedProject:Project|null;
  setSelectedChannelId:(id:string)=>void;
  setSelectedProjectId:(id:string)=>void;
};
export const SELECTED_CHANNEL_STORAGE_KEY='animationSelectedChannelId';
export const SELECTED_PROJECT_STORAGE_KEY='animationSelectedProjectId';
export const readStoredSelection=(key:string):string=>window.localStorage.getItem(key)??'';
export const writeStoredSelection=(key:string,value:string)=>{
  if(value) window.localStorage.setItem(key,value);
  else window.localStorage.removeItem(key);
};

/** Only the separate loopback reader may receive a live-guide handoff. */
export function connectedReaderUrl(site:{id?:string;reader_url?:string}){
 const candidate=site.reader_url||(site.id&&/^[a-f0-9]{32}$/.test(site.id)?`http://127.0.0.1:8001/site/${site.id}/`:'');
 if(!candidate)return '';
 try{
  const url=new URL(candidate);
  if(url.protocol!=='http:'||!['127.0.0.1','localhost'].includes(url.hostname)||url.port!=='8001'||url.username||url.password||url.search||!/^\/site\/[a-f0-9]{32}\/$/.test(url.pathname))return '';
  url.hash='ask';return url.href;
 }catch{return '';}
}

/** Draft chat is same-origin and bound to exactly the workspace being previewed. */
export function ownerChatTarget(site:{owner_chat?:{url:string;snapshot_id:string;approved_at?:string}},location:{port:string;pathname:string}){
 const workspace=/^\/portfolio-preview\/([a-f0-9]{32})\/(?:index\.html)?$/.exec(location.pathname)?.[1];
 const chat=site.owner_chat;
 if(location.port!=='8000'||!workspace||!chat||!/^[a-f0-9]{32}$/.test(chat.snapshot_id)||chat.url!==`/api/workspaces/${workspace}/portfolio-chat`)return null;
 return chat;
}

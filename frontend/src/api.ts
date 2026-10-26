const BASE = (import.meta.env.VITE_API_BASE_URL || '').replace(/\/$/, '')
export type Employee = Record<string, unknown>
export type Session = {session_id:string;chat_title:string;created_at?:string;pinned_at?:string|null}
export type Message = {role:string;content:string}
export type Citation = {filename:string;page:number;score?:number}
export type HRRecord = Record<string, unknown>

export class ApiError extends Error {constructor(message:string, public status:number){super(message)}}
async function parseError(response:Response){const text=await response.text();try {const parsed=JSON.parse(text);return typeof parsed.detail==='string'?parsed.detail:typeof parsed.error==='string'?parsed.error:`Request failed (${response.status})`}catch{return text||`Request failed (${response.status})`}}
export async function request<T>(path:string,token:string,init:RequestInit={}):Promise<T>{
 const response=await fetch(`${BASE}${path}`,{...init,headers:{...(token?{Authorization:`Bearer ${token}`} : {}),...(init.headers||{})}})
 if(!response.ok) throw new ApiError(await parseError(response),response.status)
 return response.json() as Promise<T>
}
export async function login(email:string,password:string){const form=new URLSearchParams({username:email,password});const r=await fetch(`${BASE}/api/hr/auth/login`,{method:'POST',headers:{'Content-Type':'application/x-www-form-urlencoded'},body:form});if(!r.ok)throw new ApiError(await parseError(r),r.status);return r.json() as Promise<{access_token:string;role:string}>}
export const getEmployee=(token:string)=>request<Employee>('/api/hr/auth/employees/current_employee',token)
export const getSessions=(token:string)=>request<Session[]>('/api/hr/chat/all',token)
export const getSession=(token:string,id:string)=>request<{chat_data:Message[];chat_title:string;session_id:string}>(`/api/hr/chat/${encodeURIComponent(id)}`,token)
export const getLeaves=(token:string)=>request<HRRecord[]>('/api/hr/chat/leave_requests',token)
export const getTickets=(token:string)=>request<HRRecord[]>('/api/hr/chat/tickets',token)
export const editSession=(token:string,id:string,payload:{chat_title?:string;pinned?:boolean})=>request<Session>(`/api/hr/chat/${encodeURIComponent(id)}`,token,{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)})
export const deleteSession=(token:string,id:string)=>request<{deleted:string}>(`/api/hr/chat/${encodeURIComponent(id)}`,token,{method:'DELETE'})

export async function sendChat(args:{token:string;sessionId:string|null;query:string;attachment?:File;signal:AbortSignal;onChunk:(fragment:string)=>void;onDone:(sessionId:string,sources:Citation[])=>void;onStatus?:(status:string)=>void}){
 const form=new FormData();form.set('user_query',args.query);form.set('chat_history','[]');form.set('stream_events','true');if(args.sessionId)form.set('session_id',args.sessionId);if(args.attachment)form.set('attachment',args.attachment)
 const r=await fetch(`${BASE}/api/hr/chat/get_response`,{method:'POST',headers:{Authorization:`Bearer ${args.token}`},body:form,signal:args.signal})
 if(!r.ok)throw new ApiError(await parseError(r),r.status)
 if(!r.body)throw new Error('The server did not return a stream.')
 const reader=r.body.getReader();const decoder=new TextDecoder();let buffer='';let completed=false
 const processEvent=(block:string)=>{
  let event='message';const data:string[]=[]
  for(const line of block.split('\n')){if(line.startsWith('event:'))event=line.slice(6).trim();if(line.startsWith('data:'))data.push(line.slice(5).trimStart())}
  if(!data.length)return
  let payload:Record<string,unknown>;try{payload=JSON.parse(data.join('\n'))}catch{return}
  if(event==='chunk')args.onChunk(String(payload.text||''))
  if(event==='status')args.onStatus?.(String(payload.loading||'Thinking…'))
  if(event==='done'){completed=true;args.onDone(String(payload.session_id||args.sessionId||''),Array.isArray(payload.sources)?payload.sources as Citation[]:[])}
  if(event==='error')throw new Error(String(payload.error||'The assistant could not complete this request.'))
 }
 try{while(true){const {done,value}=await reader.read();if(done)break;buffer+=decoder.decode(value,{stream:true}).replace(/\r\n/g,'\n');let cut;while((cut=buffer.indexOf('\n\n'))!==-1){const block=buffer.slice(0,cut);buffer=buffer.slice(cut+2);processEvent(block)}}if(buffer.trim())processEvent(buffer);if(!completed)throw new Error('The connection closed before the assistant finished.')}finally{reader.releaseLock()}
}


export type OPDClaim = {
 id:number; amount:string; treatment_date:string; description:string; filename:string;
 file_size:number; content_type:string; status:string; created_at:string; attachment_url:string
}
export const getOPDClaims=(token:string)=>request<OPDClaim[]>('/api/hr/chat/opd_claims',token)
export async function createOPDClaim(token:string,details:{amount:string;treatment_date:string;description:string;attachment:File}):Promise<OPDClaim>{
 const form=new FormData()
 form.set('amount',details.amount);form.set('treatment_date',details.treatment_date)
 form.set('description',details.description);form.set('attachment',details.attachment)
 return request<OPDClaim>('/api/hr/chat/opd_claims',token,{method:'POST',body:form})
}
export async function downloadOPDAttachment(token:string,claim:OPDClaim):Promise<void>{
 // Fetch privately with JWT. Never open the authenticated URL directly or put tokens in query strings.
 const response=await fetch(`${BASE}/api/hr/chat/opd_claims/${encodeURIComponent(String(claim.id))}/attachment`,{headers:{Authorization:`Bearer ${token}`}})
 if(!response.ok)throw new ApiError(await parseError(response),response.status)
 const blob=await response.blob()
 const objectUrl=URL.createObjectURL(blob)
 try{
  const a=document.createElement('a');a.href=objectUrl;a.download=claim.filename||`opd-claim-${claim.id}`
  document.body.appendChild(a);a.click();a.remove()
 }finally{setTimeout(()=>URL.revokeObjectURL(objectUrl),60000)}
}

import {useCallback,useEffect,useState} from 'react'
import {Activity,ArrowUpRight,Download,FileText,LoaderCircle,ShieldCheck,Stethoscope,Wallet,X} from 'lucide-react'
import {ApiError,downloadOPDAttachment,getOPDClaims,type OPDClaim} from './api'
const formatDate=(date:string)=>{const dt=new Date(`${date.slice(0,10)}T12:00:00`);return Number.isNaN(dt.getTime())?date:dt.toLocaleDateString(undefined,{year:'numeric',month:'short',day:'numeric'})}
const currency=(amount:string)=>`PKR ${Number(amount).toLocaleString(undefined,{minimumFractionDigits:2,maximumFractionDigits:2})}`
export function OPDClaimsPage({token,onAuthExpired,onOpenAssistant}:{token:string;onAuthExpired:()=>void;onOpenAssistant:()=>void}){
 const [claims,setClaims]=useState<OPDClaim[]>([])
 const [loading,setLoading]=useState(true)
 const [downloading,setDownloading]=useState<number|null>(null)
 const [error,setError]=useState('')
 const refresh=useCallback(async()=>{setLoading(true);setError('');try{setClaims(await getOPDClaims(token))}catch(err){if(err instanceof ApiError&&err.status===401)onAuthExpired();else setError(err instanceof Error?err.message:'Could not load your claims.')}finally{setLoading(false)}},[token,onAuthExpired])
 useEffect(()=>{void refresh()},[refresh])
 const download=async(claim:OPDClaim)=>{setDownloading(claim.id);setError('');try{await downloadOPDAttachment(token,claim)}catch(err){if(err instanceof ApiError&&err.status===401)onAuthExpired();else setError(err instanceof Error?err.message:'Unable to download attachment.')}finally{setDownloading(null)}}
 const total=claims.reduce((sum,c)=>sum+Number(c.amount||0),0)
 return <div className="opd-page">
  <div className="opd-heading"><div><div className="records-kicker">EMPLOYEE SELF-SERVICE / MEDICAL</div><h1>OPD claims</h1><p>Track submitted reimbursements and securely access your uploaded receipts.</p></div><span className="opd-secure"><ShieldCheck size={15}/> Private employee records</span></div>
  <div className="opd-overview">
   <div className="opd-stat"><div className="opd-stat-icon violet"><FileText size={20}/></div><div><span>Total claims</span><strong>{claims.length}</strong><small>Submission history</small></div></div>
   <div className="opd-stat"><div className="opd-stat-icon amber"><Activity size={20}/></div><div><span>Pending review</span><strong>{claims.filter(c=>c.status==='pending').length}</strong><small>Awaiting review</small></div></div>
   <div className="opd-stat"><div className="opd-stat-icon mint"><Wallet size={20}/></div><div><span>Total claimed</span><strong>{currency(String(total))}</strong><small>Not approved or paid</small></div></div>
  </div>
  {error&&<div className="opd-alert opd-error" role="alert"><X size={17}/><span>{error}</span><button type="button" onClick={()=>setError('')} aria-label="Dismiss error"><X size={16}/></button></div>}
  <div className="opd-history-banner"><div className="opd-history-banner-icon"><Stethoscope size={24}/></div><div><strong>Submit your claim in AI Assistant</strong><p>Attach a PDF or image using the paperclip beside the chat input. Enter claim details there—this page is for history and status only.</p></div><button type="button" onClick={onOpenAssistant}>Open assistant <ArrowUpRight size={16}/></button></div>
  <section className="opd-panel opd-history-only"><div className="opd-history-head"><div><h2>Claim history</h2><p>Your previous medical reimbursement submissions and their status.</p></div><button className="refresh-btn" type="button" onClick={()=>void refresh()} disabled={loading}><Activity size={15}/> Refresh</button></div>
   {loading?<div className="opd-history-empty"><LoaderCircle className="spin" size={22}/><p>Loading your claims…</p></div>:claims.length===0?<div className="opd-history-empty"><div className="opd-empty-icon"><FileText size={25}/></div><h3>No claims yet</h3><p>Submit a claim through AI Assistant to see it here.</p><button type="button" className="opd-history-start" onClick={onOpenAssistant}>Open AI Assistant <ArrowUpRight size={15}/></button></div>:<div className="opd-claim-list">{claims.map(c=><article className="opd-claim" key={c.id}><div className="opd-claim-top"><div className="opd-claim-icon"><FileText size={18}/></div><div className="opd-claim-title"><strong>Claim #{c.id}</strong><span>Treatment: {formatDate(c.treatment_date)}</span></div><span className={`status-tag ${c.status.toLowerCase()}`}>{c.status}</span></div><p className="opd-claim-desc">{c.description}</p><div className="opd-claim-bottom"><strong>{currency(c.amount)}</strong><button type="button" onClick={()=>void download(c)} disabled={downloading!==null} title={`Download ${c.filename}`}>{downloading===c.id?<LoaderCircle size={14} className="spin"/>:<Download size={14}/>} Download slip <span className="opd-download-filename">· {c.filename}</span></button></div></article>)}</div>}
  </section>
 </div>
}

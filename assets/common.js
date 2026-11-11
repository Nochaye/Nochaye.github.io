export const $ = s => document.querySelector(s);
export const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
export const today = () => new Intl.DateTimeFormat('sv-SE', {timeZone:'Asia/Shanghai',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date());
export function readLocal(key, fallback) { try { return JSON.parse(localStorage.getItem(key)) ?? fallback; } catch { return fallback; } }
export function writeLocal(key, value) { try { localStorage.setItem(key, JSON.stringify(value)); return true; } catch { return false; } }
export async function json(url) { const response=await fetch(url,{cache:'no-store'}); if(!response.ok) throw new Error(`加载失败 (${response.status})`); return response.json(); }
export function safeURL(url) { try { const u=new URL(url,location.href); return ['https:','http:'].includes(u.protocol) ? u.href : ''; } catch {return '';} }
export function viewCount(id) { const value=readLocal('starcape-views',{})[id]; return Number.isSafeInteger(value)&&value>0 ? value : 0; }
export function countView(id) { const views=readLocal('starcape-views',{}); views[id]=viewCount(id)+1; return writeLocal('starcape-views',views); }

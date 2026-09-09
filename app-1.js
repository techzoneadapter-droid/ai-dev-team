const STORAGE_KEY = 'aiDevTeamWebV2';
const roles = ['Developer', 'Reviewer', 'Tester'];
const builtins = [
  {id:'github',name:'GitHub',keywords:['github','repository','repo','pull request','commit','branch'],url:'https://github.com/',why:'Source control, repository files, branches, commits and pull requests.',permissions:['Read repository metadata/files','Write files or commits only after explicit task approval','Create/update pull requests only after explicit task approval']},
  {id:'vercel',name:'Vercel',keywords:['vercel','deployment','deploy','preview deployment'],url:'https://vercel.com/',why:'Deploy and inspect web projects, previews and production builds.',permissions:['Read project/deployment metadata','Read build status/log summaries','Create deployment only after explicit task approval']},
  {id:'gmail',name:'Gmail',keywords:['gmail','email','mail','inbox'],url:'https://mail.google.com/',why:'Read or draft email when a task explicitly requires mailbox access.',permissions:['Read/search requested messages','Create drafts only when needed','Send mail only after an explicit send action']},
  {id:'calendar',name:'Google Calendar',keywords:['google calendar','calendar','meeting','schedule'],url:'https://calendar.google.com/',why:'Read schedules or create/update events for tasks that require calendar work.',permissions:['Read event/free-busy data','Create/update events only after explicit action']},
  {id:'drive',name:'Google Drive',keywords:['google drive','drive file','google docs','google sheet'],url:'https://drive.google.com/',why:'Read project files or save generated artifacts when Drive is explicitly requested.',permissions:['Read explicitly selected files/folders','Create/update files only after explicit action']},
  {id:'slack',name:'Slack',keywords:['slack','channel','workspace message'],url:'https://slack.com/',why:'Read or post workspace messages for collaboration workflows.',permissions:['Read requested channels/messages','Post only after explicit action']},
  {id:'notion',name:'Notion',keywords:['notion','notion page','notion database'],url:'https://www.notion.so/',why:'Read or update project docs/databases in Notion.',permissions:['Read selected pages/databases','Create/update content only after explicit action']},
  {id:'supabase',name:'Supabase',keywords:['supabase','postgres','supabase database'],url:'https://supabase.com/',why:'Database/auth/storage integration for web projects.',permissions:['Read project metadata/schema','Database/storage writes only after explicit action']},
  {id:'firebase',name:'Firebase',keywords:['firebase','firestore','firebase auth'],url:'https://console.firebase.google.com/',why:'Firebase project, database, auth or hosting workflows.',permissions:['Read project metadata','Write/deploy only after explicit action']},
  {id:'openai',name:'OpenAI API',keywords:['openai api','openai key','gpt api'],url:'https://platform.openai.com/',why:'Optional API integration for model calls outside the browser ChatGPT workflow.',permissions:['Use user-provided API configuration','Never expose or store secrets in this web app']},
  {id:'gemini',name:'Gemini API',keywords:['gemini api','google ai studio','gemini key'],url:'https://aistudio.google.com/',why:'Optional Gemini model integration.',permissions:['Use user-provided API configuration','Never expose or store secrets in this web app']},
];

const defaultState = () => ({
  version: 2,
  projects: [{id:id(), name:'Default Project', createdAt:now()}],
  selectedProjectId: null,
  tasks: [],
  selectedTaskId: null,
  agents: {
    Developer:{label:'Developer account',chatUrl:'https://chatgpt.com/',note:'Chrome profile dùng cho Developer'},
    Reviewer:{label:'Reviewer account',chatUrl:'https://chatgpt.com/',note:'Chrome profile dùng cho Reviewer'},
    Tester:{label:'Tester account',chatUrl:'https://chatgpt.com/',note:'Chrome profile dùng cho Tester'},
  },
  integrations: builtins.map(p => ({...p,approval:'pending',requested:false,connection:'Not checked',custom:false})),
  activity: [],
  settings:{autoOpenNext:false}
});

let state = load();
if (!state.selectedProjectId) state.selectedProjectId = state.projects[0]?.id || null;
let modalSaveHandler = null;
const $ = s => document.querySelector(s);
const $$ = s => [...document.querySelectorAll(s)];

function id(){ return (crypto.randomUUID ? crypto.randomUUID() : `${Date.now()}-${Math.random()}`); }
function now(){ return new Date().toISOString(); }
function load(){
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return defaultState();
    const parsed = JSON.parse(raw);
    const fresh = defaultState();
    parsed.agents = {...fresh.agents, ...(parsed.agents||{})};
    parsed.settings = {...fresh.settings, ...(parsed.settings||{})};
    const oldInts = new Map((parsed.integrations||[]).map(x=>[x.id,x]));
    const customInts = (parsed.integrations||[]).filter(x=>x.custom);
    parsed.integrations = fresh.integrations.map(x=>({...x,...oldInts.get(x.id)}));
    for(const x of customInts) if(!parsed.integrations.some(f=>f.id===x.id)) parsed.integrations.push(x);
    return {...fresh,...parsed};
  } catch { return defaultState(); }
}
function save(){ localStorage.setItem(STORAGE_KEY, JSON.stringify(state)); }
function toast(msg){ const el=$('#toast'); el.textContent=msg; el.classList.add('show'); clearTimeout(toast.t); toast.t=setTimeout(()=>el.classList.remove('show'),2200); }
function escapeHtml(s=''){ return s.replace(/[&<>'"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#039;','"':'&quot;'}[c])); }
function selectedTask(){ return state.tasks.find(t=>t.id===state.selectedTaskId) || null; }
function selectedProject(){ return state.projects.find(p=>p.id===state.selectedProjectId) || null; }
function integration(id){ return state.integrations.find(x=>x.id===id); }
function log(taskId, role, action, detail=''){ state.activity.unshift({id:id(),taskId,role,action,detail,at:now()}); }

function scanIntegrations(text, taskId){
  const low=(text||'').toLowerCase();
  let changed=false;
  for(const p of state.integrations){
    const matched=(p.keywords||[]).some(k=>low.includes(k.toLowerCase()));
    if(matched && !p.requested){ p.requested=true; changed=true; log(taskId,null,'Integration requested',p.name); }
  }
  if(changed) toast('Đã phát hiện integration cần review');
}

function buildPrompt(task){
  if(!task) return '';
  const history=task.results.slice(-8).map(r=>`[${r.iteration}] ${r.role} ${r.outcome}:\n${r.text}`).join('\n\n');
  const approved=state.integrations.filter(x=>x.requested && x.approval==='approved').map(x=>x.name);
  const pending=state.integrations.filter(x=>x.requested && x.approval!=='approved').map(x=>`${x.name} (${x.approval})`);
  const common=`You are the ${task.currentRole} in AI Dev Team.\n\nOVERALL TASK:\n${task.body}\n\nIteration: ${task.iteration}\n\nApproved integrations: ${approved.join(', ') || 'None'}\nIntegrations still blocked: ${pending.join(', ') || 'None'}\n\nPrevious handoffs:\n${history || 'None yet'}\n`;
  if(task.currentRole==='Developer') return `${common}\nYour job: implement/fix the task. Be concrete. Report changed files, decisions, tests performed, and remaining risks. End with a concise HANDOFF TO REVIEWER section.`;
  if(task.currentRole==='Reviewer') return `${common}\nYour job: review the Developer result for correctness, completeness, security, regressions, and maintainability. FIRST LINE MUST BE exactly PASS or FAIL. If FAIL, give actionable fixes. If PASS, explain why it is ready for testing.`;
  return `${common}\nYour job: test the implementation against the original requirements and likely edge cases. FIRST LINE MUST BE exactly PASS or FAIL. If FAIL, describe reproducible failures and expected behavior. If PASS, summarize validation performed.`;
}

function allowedOutcomes(role){ return role==='Developer' ? ['Submitted'] : ['Pass','Fail']; }
function detectOutcome(text, role){
  if(role==='Developer') return 'Submitted';
  const first=(text||'').trim().split(/\r?\n/)[0].trim().toUpperCase();
  if(first.startsWith('PASS')) return 'Pass';
  if(first.startsWith('FAIL')) return 'Fail';
  return null;
}
function transition(task,outcome){
  if(task.currentRole==='Developer' && outcome==='Submitted'){ task.currentRole='Reviewer'; return; }
  if(task.currentRole==='Reviewer' && outcome==='Pass'){ task.currentRole='Tester'; return; }
  if(task.currentRole==='Reviewer' && outcome==='Fail'){ task.currentRole='Developer'; task.iteration++; return; }
  if(task.currentRole==='Tester' && outcome==='Fail'){ task.currentRole='Developer'; task.iteration++; return; }
  if(task.currentRole==='Tester' && outcome==='Pass'){ task.status='Done'; return; }
  throw new Error('Invalid transition');
}

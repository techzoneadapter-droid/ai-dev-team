function render(){ renderProjects(); renderTasks(); renderWorkflow(); renderPlugins(); renderHistory(); renderSettings(); save(); }
function renderProjects(){
  const sel=$('#projectSelect'); sel.innerHTML=state.projects.map(p=>`<option value="${p.id}" ${p.id===state.selectedProjectId?'selected':''}>${escapeHtml(p.name)}</option>`).join('');
}
function renderTasks(){
  const q=$('#taskSearch').value?.toLowerCase()||'';
  const list=state.tasks.filter(t=>t.projectId===state.selectedProjectId && (`${t.title} ${t.body}`.toLowerCase().includes(q)));
  $('#taskCount').textContent=`${list.length} task${list.length===1?'':'s'}`;
  $('#taskList').innerHTML=list.map(t=>`<div class="task-item ${t.id===state.selectedTaskId?'active':''}" data-task-id="${t.id}"><div class="task-item-title">${escapeHtml(t.title)}</div><div class="task-meta"><span>${t.currentRole}</span><span>${t.status} · #${t.iteration}</span></div></div>`).join('') || '<div class="muted">Chưa có task.</div>';
  $$('.task-item').forEach(el=>el.onclick=()=>{state.selectedTaskId=el.dataset.taskId; render();});
}
function renderWorkflow(){
  const t=selectedTask();
  $('#currentRole').textContent=t?.currentRole||'—'; $('#iteration').textContent=t?.iteration||'—'; $('#taskStatus').textContent=t?.status||'—';
  $('#selectedTaskTitle').textContent=t?.title||'Chưa chọn task'; $('#originalTask').textContent=t?.body||'Tạo task mới để bắt đầu.'; $('#promptRole').textContent=t?.currentRole||'—'; $('#promptOutput').value=t?buildPrompt(t):'';
  const pills=roles.map(r=>{let cls=''; if(t){if(t.status==='Done') cls='pass'; else if(r===t.currentRole) cls='active'; else if(roles.indexOf(r)<roles.indexOf(t.currentRole)) cls='pass';} return `<span class="pill ${cls}">${r}</span>`}).join(''); $('#agentPills').innerHTML=pills;
  const outcomes=t?allowedOutcomes(t.currentRole):[]; $('#outcomeSelect').innerHTML=outcomes.map(o=>`<option>${o}</option>`).join('');
  const blockers=t?state.integrations.filter(x=>x.requested && x.approval!=='approved'):[];
  const nb=$('#pluginBlockers'); if(blockers.length){nb.classList.remove('hidden'); nb.innerHTML=`<strong>Integration đang bị chặn:</strong> ${blockers.map(x=>`${escapeHtml(x.name)} (${x.approval})`).join(', ')}. Vào Plugin Center để duyệt.`}else nb.classList.add('hidden');
  const disabled=!t; ['#copyPromptBtn','#openChatBtn','#recordOnlyBtn','#sendNextBtn','#editTaskBtn','#deleteTaskBtn'].forEach(s=>$(s).disabled=disabled); $('#reopenTaskBtn').disabled=!t||t.status!=='Done';
  $('#sendNextBtn').disabled=!t||t.status==='Done'; $('#recordOnlyBtn').disabled=!t||t.status==='Done';
}
function renderPlugins(){
  const pending=state.integrations.filter(x=>x.requested && x.approval==='pending').length; const approved=state.integrations.filter(x=>x.requested&&x.approval==='approved').length; const denied=state.integrations.filter(x=>x.requested&&x.approval==='denied').length;
  $('#pendingBadge').textContent=pending; $('#pendingBadge').classList.toggle('hidden',pending===0);
  $('#pluginSummary').innerHTML=`<span class="summary-chip">Requested ${state.integrations.filter(x=>x.requested).length}</span><span class="summary-chip">Pending ${pending}</span><span class="summary-chip">Approved ${approved}</span><span class="summary-chip">Denied ${denied}</span>`;
  const q=($('#pluginSearch').value||'').toLowerCase(); const f=$('#pluginFilter').value;
  const items=state.integrations.filter(p=>{
    if(q && !`${p.name} ${p.why}`.toLowerCase().includes(q)) return false;
    if(f==='requested'&&!p.requested)return false; if(['pending','approved','denied'].includes(f)&&(!p.requested||p.approval!==f))return false; return true;
  });
  $('#pluginList').innerHTML=items.map(p=>`<article class="plugin-card ${p.requested?'requested':''}"><div class="plugin-top"><div><div class="plugin-name">${escapeHtml(p.name)} ${p.requested?'<span title="Task đang yêu cầu">●</span>':''}</div><div class="muted" style="font-size:11px">${escapeHtml(p.connection||'Not checked')}</div></div><span class="plugin-state ${p.approval}">${p.approval.toUpperCase()}</span></div><p>${escapeHtml(p.why||'Custom integration')}</p><div class="permissions">${(p.permissions||[]).map(x=>'• '+escapeHtml(x)).join('\n')}</div><div class="plugin-actions"><button class="primary" data-action="approve" data-id="${p.id}">Approve</button><button class="ghost danger" data-action="deny" data-id="${p.id}">Deny</button><button class="ghost" data-action="pending" data-id="${p.id}">Pending</button><button class="ghost" data-action="connect" data-id="${p.id}">Mark connected</button>${p.url?`<button class="ghost" data-action="open" data-id="${p.id}">Open provider</button>`:''}${p.custom?`<button class="ghost danger" data-action="remove" data-id="${p.id}">Remove</button>`:''}</div></article>`).join('')||'<div class="muted">Không có integration phù hợp bộ lọc.</div>';
  $$('[data-action]').forEach(btn=>btn.onclick=()=>pluginAction(btn.dataset.action,btn.dataset.id));
}
function renderHistory(){
  const t=selectedTask(); if(!t){$('#historyList').innerHTML='<div class="muted">Chọn task để xem lịch sử.</div>';return;}
  const rows=[...t.results].reverse(); $('#historyList').innerHTML=rows.map(r=>`<div class="history-item"><span>${new Date(r.at).toLocaleString()}</span><span class="history-role">${r.role}</span><span class="history-outcome">${r.outcome}</span><span>${escapeHtml(r.text.slice(0,400))}</span></div>`).join('')||'<div class="muted">Chưa có kết quả nào.</div>';
}
function renderSettings(){
  $('#agentSettings').innerHTML=roles.map(r=>{const a=state.agents[r]; return `<div class="agent-card"><h3>${r}</h3><label>Tên/nhãn tài khoản</label><input data-agent="${r}" data-field="label" value="${escapeHtml(a.label)}"><label>Chat URL</label><input data-agent="${r}" data-field="chatUrl" value="${escapeHtml(a.chatUrl)}"><label>Ghi chú Chrome profile</label><input data-agent="${r}" data-field="note" value="${escapeHtml(a.note)}"></div>`}).join('');
  $$('[data-agent]').forEach(i=>i.onchange=()=>{state.agents[i.dataset.agent][i.dataset.field]=i.value.trim(); save(); toast('Đã lưu agent setting');}); $('#autoOpenNext').checked=!!state.settings.autoOpenNext;
}

function pluginAction(action,pid){ const p=integration(pid); if(!p)return; if(action==='approve'){p.approval='approved'; p.requested=true; toast(`${p.name}: Approved`);} if(action==='deny'){p.approval='denied'; p.requested=true; toast(`${p.name}: Denied`);} if(action==='pending'){p.approval='pending'; p.requested=true;} if(action==='connect'){p.connection='Connected (manual)'; toast(`${p.name}: marked connected`);} if(action==='open'&&p.url) window.open(p.url,'_blank','noopener'); if(action==='remove'&&p.custom){state.integrations=state.integrations.filter(x=>x.id!==pid);} render(); }

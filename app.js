let currentLastUpdate = null;
let currentRunId = null;

async function fetchData() {
    try {
        const timestamp = new Date().getTime();
        const [dashRes, historyRes] = await Promise.all([
            fetch(`dashboard_data.json?t=${timestamp}`),
            fetch(`history_log.csv?t=${timestamp}`)
        ]);

        const dashboardData = await dashRes.json();
        const historyText = await historyRes.text();
        
        let isNewData = false;
        if (currentLastUpdate !== dashboardData.last_update) {
            currentLastUpdate = dashboardData.last_update;
            isNewData = true;
            updateDashboard(dashboardData, historyText);
        }
        
        if (currentRunId === null && dashboardData.github_run_id) {
            currentRunId = dashboardData.github_run_id;
        } else if (currentRunId && dashboardData.github_run_id && currentRunId !== dashboardData.github_run_id) {
            currentRunId = dashboardData.github_run_id;
            const actionStatus = document.getElementById('action-status');
            if (actionStatus && actionStatus.innerHTML.includes('⏳ 執行中...')) {
                actionStatus.innerHTML = `✅ 最新 Run 已完成 <a href="https://github.com/fuyoung205122/company-line-notify/actions/runs/${currentRunId}" target="_blank">查看紀錄</a>`;
                const runBtn = document.getElementById('run-btn');
                if(runBtn) runBtn.disabled = false;
            }
        }
        
        return { success: true, isNewData: isNewData };
    } catch (error) {
        console.error("Error fetching data:", error);
        document.getElementById('status-title').innerText = "連線異常";
        document.getElementById('status-subtitle').innerText = "無法取得最新狀態，請稍後再試。";
        
        const sysCard = document.getElementById('sys-status-card');
        sysCard.className = 'health-card error';
        document.getElementById('sys-status-title').innerHTML = '<span class="status-dot red"></span> 🔴 系統連線失敗';
        
        return { success: false, isNewData: false };
    }
}

function updateDashboard(data, historyCsv) {
    const timeStr = data.last_update;
    const isCovered = data.is_covered;
    
    // Calculate delay
    const updateTime = new Date(
        timeStr.replace(' ', 'T')
    );
    const now = new Date();
    const diffMs = now - updateTime;
    const diffMins = Math.floor(diffMs / 60000);
    
    const sysCard = document.getElementById('sys-status-card');
    const sysTitle = document.getElementById('sys-status-title');
    const sysDelay = document.getElementById('sys-delay');
    const sysNextRun = document.getElementById('sys-next-run');
    
    document.getElementById('sys-last-update').innerText = `最後更新：${timeStr}`;
    
    function calculateNextRun() {
        const now = new Date();
        let nextRun = new Date(now);
        const mins = now.getMinutes();
        if (mins < 7) {
            nextRun.setMinutes(7, 0, 0);
        } else if (mins < 37) {
            nextRun.setMinutes(37, 0, 0);
        } else {
            nextRun.setHours(now.getHours() + 1);
            nextRun.setMinutes(7, 0, 0);
        }
        return nextRun.toLocaleTimeString('zh-TW', { hour: '2-digit', minute: '2-digit', hour12: false });
    }
    
    if (sysNextRun) {
        sysNextRun.innerText = `🕒 下次自動檢查：${calculateNextRun()}`;
    }
    
    let heartbeatDotHtml = '';
    if (data.system_status === 'error') {
        sysCard.className = 'health-card error';
        heartbeatDotHtml = '<span class="status-dot red heartbeat"></span>';
        sysTitle.innerHTML = `${heartbeatDotHtml} 🔴 系統異常<br><span style="font-size:0.8em; color:#ef4444;">請檢查 GitHub Actions</span>`;
        sysDelay.innerText = '請檢查執行日誌';
    } else if (diffMins >= 90) {
        sysCard.className = 'health-card error';
        heartbeatDotHtml = '<span class="status-dot red"></span>';
        sysTitle.innerHTML = `${heartbeatDotHtml} 🔴 排程停止<br><span style="font-size:0.8em; color:#ef4444;">超過 90 分鐘未更新</span>`;
        sysDelay.innerText = `資料延遲：${diffMins} 分鐘`;
    } else if (diffMins >= 45) {
        sysCard.className = 'health-card warning';
        heartbeatDotHtml = '<span class="status-dot yellow heartbeat"></span>';
        sysTitle.innerHTML = `${heartbeatDotHtml} 🟡 資料延遲<br><span style="font-size:0.8em; color:#f59e0b;">排程可能壅塞</span>`;
        sysDelay.innerText = `資料延遲：${diffMins} 分鐘`;
    } else {
        sysCard.className = 'health-card normal';
        heartbeatDotHtml = '<span class="status-dot green heartbeat"></span>';
        let sourceHtml = data.source || '中央氣象署';
        if (sourceHtml.includes('異常')) {
            sysTitle.innerHTML = `${heartbeatDotHtml} 🟡 雨量站異常<br><span style="font-size:0.8em; color:#f59e0b;">目前使用雷達模式</span>`;
        } else {
            sysTitle.innerHTML = `${heartbeatDotHtml} 🟢 正常運作<br><span style="font-size:0.8em; color:#10b981;">資料來源：${sourceHtml}</span>`;
        }
        sysDelay.innerText = `資料延遲：${diffMins} 分鐘`;
    }
    
    document.getElementById('sys-last-success').innerText = `最後成功：${data.last_success_time || '--'}`;
    document.getElementById('sys-duration').innerText = data.execution_duration_sec !== undefined ? `${data.execution_duration_sec} 秒` : '--';
    
    // Calculate health status
    const healthStatusEl = document.getElementById('sys-health-status');
    const successRateEl = document.getElementById('sys-success-rate');
    if (data.total_runs !== undefined && data.total_runs < 50) {
        healthStatusEl.innerText = '🟢 資料蒐集中';
        successRateEl.innerText = '';
    } else if (data.success_rate && data.success_rate !== '--' && data.success_rate !== '0%') {
        successRateEl.innerText = `成功率：${data.success_rate}`;
        const rate = parseFloat(data.success_rate);
        if (rate >= 99) {
            healthStatusEl.innerText = '🟢 優秀';
        } else if (rate >= 95) {
            healthStatusEl.innerText = '🟡 注意';
        } else {
            healthStatusEl.innerText = '🔴 異常';
        }
    } else {
        healthStatusEl.innerText = '--';
        successRateEl.innerText = `成功率：--`;
    }
    
    const runIdEl = document.getElementById('sys-run-id');
    if (data.github_run_id && data.github_run_id !== '未知' && data.github_run_id !== '--') {
        runIdEl.innerText = '📄 查看本次執行紀錄';
        runIdEl.href = `https://github.com/fuyoung205122/company-line-notify/actions/runs/${data.github_run_id}`;
    } else {
        runIdEl.innerText = '--';
        runIdEl.removeAttribute('href');
    }
    
    // Update Status Card
    const statusCard = document.getElementById('status-card');
    const statusTitle = document.getElementById('status-title');
    const statusSubtitle = document.getElementById('status-subtitle');
    
    statusCard.className = 'status-card ' + (isCovered ? 'cover' : 'uncover');
    statusTitle.innerText = isCovered ? "🔴 建議加蓋帆布" : "🟢 暫不需加蓋";
    
    if (isCovered) {
        statusSubtitle.innerText = "目前判定為下雨狀態或雲層籠罩中";
    } else {
        statusSubtitle.innerText = "目前判定為無雨狀態";
    }
    
    // Update Details Grid
    document.getElementById('val-rain').innerText = data.rainfall || '--';
    document.getElementById('val-radar').innerText = data.radar_pixels !== undefined ? `${data.radar_pixels} 點` : '--';
    document.getElementById('val-dbz').innerText = data.max_dbz !== undefined ? `${data.max_dbz} dBZ` : '--';
    document.getElementById('val-weather').innerText = data.weather_description || '--';
    
    let sourceLightHtml = '';
    if (data.source && data.source.includes('中央氣象署')) {
        sourceLightHtml = '🟢 中央氣象署';
    } else if (data.source && data.source.includes('Open-Meteo')) {
        sourceLightHtml = '🟡 Open-Meteo';
    } else {
        sourceLightHtml = '🔴 無資料來源';
    }
    document.getElementById('val-source').innerHTML = sourceLightHtml;
    
    // Update Reason
    const reasonList = document.getElementById('val-reason-list');
    reasonList.innerHTML = '';
    if (data.reasons && data.reasons.length > 0) {
        data.reasons.forEach(r => {
            const li = document.createElement('li');
            li.innerText = r;
            reasonList.appendChild(li);
        });
    } else {
        reasonList.innerHTML = '<li>無詳細原因</li>';
    }
    
    // Parse CSV
    const rows = historyCsv.trim().split('\n').slice(1); // skip header
    if (rows.length === 0) return;
    
    // Update History Table (Last 24 items max)
    const tbody = document.querySelector('#history-table tbody');
    tbody.innerHTML = '';
    
    // Reverse rows to show newest first, limit to 24
    const recentRows = rows.reverse().slice(0, 24);
    
    recentRows.forEach(rowStr => {
        const cols = rowStr.split(',');
        if (cols.length < 8) return;
        
        const tr = document.createElement('tr');
        
        const action = cols[7];
        let badgeClass = 'keep';
        if (action.includes('發佈加蓋')) badgeClass = 'cover';
        if (action.includes('發佈解除')) badgeClass = 'uncover';
        
        // reason is in the 9th column (index 8)
        let reason = cols[8] || '--';
        
        tr.innerHTML = `
            <td>${cols[0].split(' ')[1]}</td>
            <td>${cols[1]}</td>
            <td>${cols[3]}</td>
            <td>${cols[4]}</td>
            <td><span class="badge ${badgeClass}">${action}</span></td>
            <td style="font-size: 0.9rem; color: #cbd5e1;">${reason}</td>
        `;
        tbody.appendChild(tr);
    });
}

// Initial fetch
fetchData();

// Auto refresh every 5 minutes
setInterval(fetchData, 5 * 60 * 1000);

async function forceRefresh() {
    const btn = document.getElementById('refresh-btn');
    const status = document.getElementById('refresh-status');

    btn.disabled = true;
    btn.innerText = '更新中...';
    status.innerText = '正在取得最新資料';

    try {
        const result = await fetchData();
        if (result.success) {
            if (result.isNewData) {
                status.innerText = '✅ 更新完成 ' + new Date().toLocaleTimeString();
            } else {
                status.innerText = '⚠️ 目前尚無新資料';
            }
        } else {
            status.innerText = '❌ 更新失敗';
        }
    } catch (err) {
        status.innerText = '❌ 更新失敗';
    }

    btn.disabled = false;
    btn.innerText = '🔄 立即更新';
}

document.getElementById('refresh-btn').addEventListener('click', forceRefresh);

function waitForNewRun() {
    let attempts = 0;
    const interval = setInterval(async () => {
        attempts++;
        if (attempts > 30) {
            clearInterval(interval);
            document.getElementById('action-status').innerHTML = '⚠️ 檢查超時，請手動更新';
            document.getElementById('run-btn').disabled = false;
            return;
        }
        await fetchData();
        const actionStatus = document.getElementById('action-status');
        if (!actionStatus.innerHTML.includes('⏳ 執行中...')) {
            clearInterval(interval);
        }
    }, 5000);
}

async function triggerGitHubAction() {
    const status = document.getElementById('action-status');
    const btn = document.getElementById('run-btn');

    let ghPat = prompt("安全提示：請輸入您的 GitHub PAT (為保護安全，此金鑰不會被儲存)：");
    if (!ghPat) {
        return;
    }
    ghPat = ghPat.trim();

    btn.disabled = true;
    status.innerHTML = '🚀 已送出執行請求...';

    try {
        const response = await fetch('https://api.github.com/repos/fuyoung205122/company-line-notify/actions/workflows/monitor.yml/dispatches', {
            method: 'POST',
            headers: {
                'Accept': 'application/vnd.github+json',
                'Authorization': `Bearer ${ghPat}`,
                'X-GitHub-Api-Version': '2022-11-28',
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ 
                ref: 'master',
                inputs: {
                    run_mode: 'force-weather-check'
                }
            })
        });

        if (!response.ok) {
            if (response.status === 401 || response.status === 404) {
                throw new Error('Token 無效或沒有權限');
            }
            throw new Error(`API 錯誤: ${response.status}`);
        }

        status.innerHTML = '✅ 已觸發 GitHub Actions';
        setTimeout(() => {
            status.innerHTML = '⏳ 執行中...';
            waitForNewRun();
        }, 3000);

    } catch (err) {
        status.innerHTML = `❌ 觸發失敗 (${err.message})`;
        btn.disabled = false;
    }
}

document.getElementById('run-btn').addEventListener('click', triggerGitHubAction);



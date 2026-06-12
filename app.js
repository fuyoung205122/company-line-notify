async function fetchData() {
    try {
        const timestamp = new Date().getTime();
        const [dashRes, historyRes] = await Promise.all([
            fetch(`dashboard_data.json?t=${timestamp}`),
            fetch(`history_log.csv?t=${timestamp}`)
        ]);

        const dashboardData = await dashRes.json();
        const historyText = await historyRes.text();
        
        updateDashboard(dashboardData, historyText);
    } catch (error) {
        console.error("Error fetching data:", error);
        document.getElementById('status-title').innerText = "連線異常";
        document.getElementById('status-subtitle').innerText = "無法取得最新狀態，請稍後再試。";
        
        const sysCard = document.getElementById('sys-status-card');
        sysCard.className = 'health-card error';
        document.getElementById('sys-status-title').innerHTML = '<span class="status-dot red"></span> 🔴 系統連線失敗';
    }
}

function updateDashboard(data, historyCsv) {
    const timeStr = data.last_update;
    const isCovered = data.is_covered;
    
    // Calculate delay
    const updateTime = new Date(timeStr.replace(/-/g, '/'));
    const now = new Date();
    const diffMs = now - updateTime;
    const diffMins = Math.floor(diffMs / 60000);
    
    const sysCard = document.getElementById('sys-status-card');
    const sysTitle = document.getElementById('sys-status-title');
    const sysDelay = document.getElementById('sys-delay');
    
    document.getElementById('sys-last-update').innerText = `最後更新：${timeStr}`;
    
    let heartbeatDotHtml = '';
    if (data.system_status === 'error') {
        sysCard.className = 'health-card error';
        heartbeatDotHtml = '<span class="status-dot red heartbeat"></span>';
        sysTitle.innerHTML = `${heartbeatDotHtml} 🔴 系統異常`;
        sysDelay.innerText = `錯誤：${data.error_message}`;
    } else if (diffMins >= 30) {
        sysCard.className = 'health-card error';
        heartbeatDotHtml = '<span class="status-dot red"></span>';
        sysTitle.innerHTML = `${heartbeatDotHtml} 🔴 系統異常`;
        sysDelay.innerText = `資料已超過 ${diffMins} 分鐘未更新，排程可能已停止`;
    } else if (diffMins >= 15) {
        sysCard.className = 'health-card warning';
        heartbeatDotHtml = '<span class="status-dot yellow heartbeat"></span>';
        sysTitle.innerHTML = `${heartbeatDotHtml} 🟡 資料延遲`;
        sysDelay.innerText = `資料延遲：${diffMins} 分鐘 (排程可能壅塞)`;
    } else {
        sysCard.className = 'health-card normal';
        heartbeatDotHtml = '<span class="status-dot green heartbeat"></span>';
        sysTitle.innerHTML = `${heartbeatDotHtml} 🟢 正常運作`;
        sysDelay.innerText = `資料延遲：${diffMins} 分鐘`;
    }
    
    document.getElementById('sys-success-rate').innerText = data.success_rate || '--';
    document.getElementById('sys-last-success').innerText = `最後成功：${data.last_success_time || '--'}`;
    document.getElementById('sys-duration').innerText = data.execution_duration_sec !== undefined ? `${data.execution_duration_sec} 秒` : '--';
    
    const runIdEl = document.getElementById('sys-run-id');
    if (data.github_run_id && data.github_run_id !== '未知' && data.github_run_id !== '--') {
        runIdEl.innerText = data.github_run_id;
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
        sourceLightHtml = '<span class="status-dot green"></span>';
    } else if (data.source && data.source.includes('Open-Meteo')) {
        sourceLightHtml = '<span class="status-dot yellow"></span>';
    } else {
        sourceLightHtml = '<span class="status-dot red"></span>';
    }
    document.getElementById('val-source').innerHTML = `${sourceLightHtml} ${data.source || '--'}`;
    
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

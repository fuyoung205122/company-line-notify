async function fetchData() {
    try {
        // Fetch state and history concurrently (cache busting with timestamp)
        const timestamp = new Date().getTime();
        const [stateRes, historyRes] = await Promise.all([
            fetch(`state.json?t=${timestamp}`),
            fetch(`history_log.csv?t=${timestamp}`)
        ]);

        const stateData = await stateRes.json();
        const historyText = await historyRes.text();
        
        updateDashboard(stateData, historyText);
    } catch (error) {
        console.error("Error fetching data:", error);
        document.getElementById('status-title').innerText = "連線異常";
        document.getElementById('status-subtitle').innerText = "無法取得最新狀態，請稍後再試。";
    }
}

function updateDashboard(state, historyCsv) {
    // Parse CSV
    const rows = historyCsv.trim().split('\n').slice(1); // skip header
    if (rows.length === 0) return;
    
    // Get latest row
    const latestRow = rows[rows.length - 1].split(',');
    // 執行時間,雨量值,雷達點數(2km),雷達點數(5km),最大dBZ,符合Cover條件,符合Uncover條件,最終通知結果
    const time = latestRow[0];
    const rain = latestRow[1];
    const radar5km = latestRow[3];
    const maxDbz = latestRow[4];
    const isCovered = state.is_covered;
    
    // Update Header
    document.getElementById('last-update').innerText = `最後更新時間: ${time}`;
    
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
    document.getElementById('val-rain').innerText = rain;
    document.getElementById('val-radar').innerText = `${radar5km} 點`;
    document.getElementById('val-dbz').innerText = `${maxDbz} dBZ`;
    
    // Update Reason
    let reasonText = "";
    if (isCovered) {
        reasonText = `因為 5km 內雷達回波點數達到 ${radar5km} 點（或測站有雨），系統為了安全起見，判定為加蓋狀態。`;
    } else {
        reasonText = `測站雨量為 0，且雷達回波強度低於門檻，符合無雨標準。`;
    }
    document.getElementById('val-reason').innerText = reasonText;
    
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
        
        tr.innerHTML = `
            <td>${cols[0].split(' ')[1]}</td>
            <td>${cols[1]}</td>
            <td>${cols[3]}</td>
            <td>${cols[4]}</td>
            <td><span class="badge ${badgeClass}">${action}</span></td>
        `;
        tbody.appendChild(tr);
    });
}

// Initial fetch
fetchData();

// Auto refresh every 5 minutes
setInterval(fetchData, 5 * 60 * 1000);

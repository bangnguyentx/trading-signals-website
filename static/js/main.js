// trading-signals-website/static/js/main.js

document.addEventListener('DOMContentLoaded', () => {

    // Lấy các element
    const signalTableBody = document.getElementById('signal-table-body');
    const comboModal = new bootstrap.Modal(document.getElementById('comboModal'));
    const comboModalLabel = document.getElementById('comboModalLabel');
    const comboModalBody = document.getElementById('comboModalBody');

    // Biến lưu trữ (cache)
    let currentSignals = [];
    const votedSignalsKey = 'votedSignals';

    /**
     * Lấy danh sách các tín hiệu đã vote từ localStorage
     */
    function getVotedSignals() {
        return JSON.parse(localStorage.getItem(votedSignalsKey)) || [];
    }

    /**
     * Lưu tín hiệu đã vote vào localStorage
     */
    function addVotedSignal(signalId) {
        const voted = getVotedSignals();
        if (!voted.includes(signalId)) {
            voted.push(signalId);
            localStorage.setItem(votedSignalsKey, JSON.stringify(voted));
        }
    }

    /**
     * Định dạng thời gian (UTC) sang giờ địa phương
     */
    function formatTime(isoTimestamp) {
        const date = new Date(isoTimestamp);
        return date.toLocaleString(); // Chuyển sang giờ địa phương
    }
    
    /**
     * Render bảng tín hiệu
     */
    function renderTable(signals) {
        // Lưu tín hiệu để dùng cho modal
        currentSignals = signals; 
        
        // Lấy danh sách đã vote
        const votedSignals = getVotedSignals();

        // Xóa nội dung cũ (loading...)
        signalTableBody.innerHTML = '';

        if (signals.length === 0) {
            signalTableBody.innerHTML = `
                <tr>
                    <td colspan="9" class="text-center p-4">
                        <i class="bi bi-moon-stars fs-3 text-secondary"></i>
                        <p class="mt-2 text-secondary">Chưa có tín hiệu nào đang hoạt động. Vui lòng quay lại sau.</p>
                    </td>
                </tr>
            `;
            return;
        }

        signals.forEach(sig => {
            const tr = document.createElement('tr');
            
            // Đã vote hay chưa?
            const hasVoted = votedSignals.includes(sig.id);

            // Xác định màu sắc
            const directionClass = sig.direction === 'LONG' ? 'direction-long' : 'direction-short';
            const tpClass = sig.direction === 'LONG' ? 'text-success' : 'text-danger';
            const slClass = sig.direction === 'LONG' ? 'text-danger' : 'text-success';

            tr.innerHTML = `
                <td>${formatTime(sig.timestamp)}</td>
                <td class="fw-bold">${sig.coin.replace('USDT', '')}</td>
                <td class="${directionClass}">${sig.direction}</td>
                <td class="fw-bold">${sig.entry.toFixed(4)}</td>
                <td class="${tpClass}">${sig.tp.toFixed(4)}</td>
                <td class="${slClass}">${sig.sl.toFixed(4)}</td>
                <td>1:${sig.rr.toFixed(1)}</td>
                <td>
                    ${sig.combo_name}
                    <i class="bi bi-info-circle-fill btn-combo-details ms-1" 
                       data-signal-id="${sig.id}" 
                       title="Xem chi tiết combo"></i>
                </td>
                <td>
                    <div class="vote-buttons" data-signal-id="${sig.id}">
                        <button class="btn btn-sm btn-outline-success btn-vote" data-vote-type="win" ${hasVoted ? 'disabled' : ''}>
                            <i class="bi bi-check-lg"></i> Win (${sig.votes_win})
                        </button>
                        <button class="btn btn-sm btn-outline-danger btn-vote" data-vote-type="lose" ${hasVoted ? 'disabled' : ''}>
                            <i class="bi bi-x-lg"></i> Lose (${sig.votes_lose})
                        </button>
                        ${hasVoted ? '<small class="d-block text-muted mt-1">Đã vote</small>' : ''}
                    </div>
                </td>
            `;
            signalTableBody.appendChild(tr);
        });
    }

    /**
     * Render thẻ thống kê
     */
    function renderStats(stats) {
        // Hôm nay
        document.getElementById('stats-today-total').textContent = stats.today.total;
        document.getElementById('stats-today-win').textContent = stats.today.wins;
        document.getElementById('stats-today-lose').textContent = stats.today.losses;
        document.getElementById('stats-today-wr').textContent = stats.today.win_rate;

        // Tuần này
        document.getElementById('stats-week-total').textContent = stats.week.total;
        document.getElementById('stats-week-win').textContent = stats.week.wins;
        document.getElementById('stats-week-lose').textContent = stats.week.losses;
        document.getElementById('stats-week-wr').textContent = stats.week.win_rate;

        // Tháng này
        document.getElementById('stats-month-total').textContent = stats.month.total;
        document.getElementById('stats-month-win').textContent = stats.month.wins;
        document.getElementById('stats-month-lose').textContent = stats.month.losses;
        document.getElementById('stats-month-wr').textContent = stats.month.win_rate;
    }

    /**
     * API: Lấy tín hiệu
     */
    async function fetchSignals() {
        try {
            const response = await fetch('/api/signals');
            if (!response.ok) throw new Error('Network response was not ok');
            const signals = await response.json();
            renderTable(signals);
        } catch (error) {
            console.error('Lỗi khi tải tín hiệu:', error);
            signalTableBody.innerHTML = `
                <tr>
                    <td colspan="9" class="text-center p-4 text-danger">
                        <i class="bi bi-exclamation-triangle-fill fs-3"></i>
                        <p class="mt-2">Không thể kết nối đến máy chủ. Vui lòng thử lại sau.</p>
                    </td>
                </tr>
            `;
        }
    }

    /**
     * API: Lấy thống kê
     */
    async function fetchStats() {
        try {
            const response = await fetch('/api/stats');
            if (!response.ok) throw new Error('Network response was not ok');
            const stats = await response.json();
            renderStats(stats);
        } catch (error) {
            console.error('Lỗi khi tải thống kê:', error);
        }
    }

    /**
     * Xử lý khi nhấn nút Vote
     */
    async function handleVote(signalId, voteType) {
        try {
            const response = await fetch(`/api/vote/${signalId}/${voteType}`, {
                method: 'POST'
            });
            const result = await response.json();
            
            if (!response.ok) {
                alert(`Lỗi: ${result.error || 'Không thể vote'}`);
                return;
            }

            // Vote thành công
            alert(result.message);
            addVotedSignal(signalId); // Lưu vào localStorage

            // Cập nhật UI ngay lập tức
            const buttonContainer = document.querySelector(`.vote-buttons[data-signal-id="${signalId}"]`);
            if (buttonContainer) {
                const winBtn = buttonContainer.querySelector('[data-vote-type="win"]');
                const loseBtn = buttonContainer.querySelector('[data-vote-type="lose"]');
                winBtn.textContent = `Win (${result.votes_win})`;
                loseBtn.textContent = `Lose (${result.votes_lose})`;
                winBtn.disabled = true;
                loseBtn.disabled = true;
                
                // Thêm text "Đã vote"
                if (!buttonContainer.querySelector('small')) {
                     buttonContainer.innerHTML += '<small class="d-block text-muted mt-1">Đã vote</small>';
                }

                // Nếu tín hiệu bị đóng, xóa nó khỏi bảng sau 2 giây
                if (result.status === 'closed') {
                    setTimeout(() => {
                        buttonContainer.closest('tr').remove();
                        // Tải lại thống kê
                        fetchStats();
                    }, 2000);
                }
            }

        } catch (error) {
            console.error('Lỗi khi vote:', error);
            alert('Đã xảy ra lỗi kết nối khi vote.');
        }
    }

    /**
     * Xử lý khi nhấn nút chi tiết Combo
     */
    function showComboDetails(signalId) {
        const signal = currentSignals.find(s => s.id === signalId);
        if (signal) {
            comboModalLabel.textContent = `Chi tiết: ${signal.combo_name}`;
            comboModalBody.textContent = signal.combo_details;
            comboModal.show();
        }
    }

    // === LẮNG NGHE SỰ KIỆN ===

    // Sử dụng Event Delegation cho các nút trong bảng
    signalTableBody.addEventListener('click', (e) => {
        const target = e.target;

        // 1. Nhấn nút Vote
        if (target.classList.contains('btn-vote')) {
            const signalId = target.closest('.vote-buttons').dataset.signalId;
            const voteType = target.dataset.voteType;
            handleVote(signalId, voteType);
        }

        // 2. Nhấn nút chi tiết Combo
        if (target.classList.contains('btn-combo-details')) {
            const signalId = target.dataset.signalId;
            showComboDetails(signalId);
        }
    });

    // === CHẠY LẦN ĐẦU ===
    fetchSignals();
    fetchStats();

    // Tự động cập nhật 60 giây một lần
    setInterval(fetchSignals, 60000); // 60 giây
    setInterval(fetchStats, 300000); // 5 phút

});

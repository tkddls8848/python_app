/**
 * 조달청 입찰공고 조회 - 프론트엔드 로직 (필터 기능 포함)
 */

// 전역 변수
let allBidData = [];  // 전체 데이터 저장
let filteredBidData = [];  // 필터링된 데이터

// 엔터키 이벤트
document.getElementById('queryInput').addEventListener('keypress', (e) => {
    if (e.key === 'Enter') {
        search();
    }
});

/**
 * 검색 실행
 */
async function search() {
    const query = document.getElementById('queryInput').value.trim();
    
    if (!query) {
        showError('검색어를 입력해주세요');
        return;
    }

    setLoading(true);
    hideError();
    hideResults();
    showLoadingIndicator();

    const pageNo = parseInt(document.getElementById('pageNo').value) || 1;
    const numOfRows = parseInt(document.getElementById('numOfRows').value) || 100;

    try {
        const response = await fetch('/api/search', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                query: query,
                page_no: pageNo,
                num_of_rows: numOfRows
            })
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail?.error || error.detail || '검색 중 오류가 발생했습니다');
        }

        const data = await response.json();
        
        // 전역 변수에 저장
        allBidData = data.items;
        
        displayResults(data);
        
        // 필터 표시
        document.getElementById('filterContainer').classList.remove('hidden');

    } catch (error) {
        console.error('Error:', error);
        showError(error.message);
        hideLoadingIndicator();
    } finally {
        setLoading(false);
    }
}

/**
 * 결과 표시
 */
function displayResults(data) {
    hideLoadingIndicator();
    
    if (!data.success || data.total_count === 0) {
        showEmptyResult();
        return;
    }

    showResultHeader(data);
    
    // 초기 표시는 전체 데이터
    filteredBidData = [...allBidData];
    renderBidCards(filteredBidData);
}

/**
 * 입찰공고 카드 렌더링
 */
function renderBidCards(items) {
    const cardsContainer = document.getElementById('bidCards');
    
    if (items.length === 0) {
        showEmptyResult();
        cardsContainer.innerHTML = '';
        return;
    }
    
    hideEmptyResult();
    
    const cardsHTML = items.map(item => createBidCardHTML(item)).join('');
    cardsContainer.innerHTML = cardsHTML;
    
    // 필터링된 개수 표시
    updateFilteredCount(items.length);
}

/**
 * 필터링된 개수 업데이트
 */
function updateFilteredCount(count) {
    const filteredCountElem = document.getElementById('filteredCount');
    
    if (count === allBidData.length) {
        filteredCountElem.classList.add('hidden');
    } else {
        filteredCountElem.textContent = `필터링: ${count}건`;
        filteredCountElem.classList.remove('hidden');
    }
}

/**
 * 필터 적용
 */
function applyFilters() {
    // 체크된 필터 값 수집
    const selectedStatuses = getSelectedFilters('status');
    const selectedBusinesses = getSelectedFilters('business');
    const selectedContracts = getSelectedFilters('contract');
    const selectedAmounts = getSelectedFilters('amount');
    const searchKeyword = document.getElementById('searchKeyword').value.trim().toLowerCase();
    
    // 필터링 실행
    filteredBidData = allBidData.filter(item => {
        // 공고 상태 필터
        if (!selectedStatuses.includes('all') && !selectedStatuses.includes(item.bidNtceSttusNm)) {
            return false;
        }
        
        // 업무 구분 필터
        if (!selectedBusinesses.includes('all') && !selectedBusinesses.includes(item.bsnsDivNm)) {
            return false;
        }
        
        // 계약 방법 필터
        if (!selectedContracts.includes('all')) {
            const hasMatch = selectedContracts.some(contract => 
                item.cntrctCnclsMthdNm.includes(contract)
            );
            if (!hasMatch) return false;
        }
        
        // 금액 범위 필터
        if (!selectedAmounts.includes('all')) {
            const amount = parseAmount(item.asignBdgtAmt);
            const inRange = selectedAmounts.some(range => {
                if (range === 'all') return true;
                const [min, max] = range.split('-').map(Number);
                return amount >= min && amount <= max;
            });
            if (!inRange) return false;
        }
        
        // 검색어 필터
        if (searchKeyword && !item.bidNtceNm.toLowerCase().includes(searchKeyword)) {
            return false;
        }
        
        return true;
    });
    
    // 정렬 적용
    applySorting();
}

/**
 * 선택된 필터 값 가져오기
 */
function getSelectedFilters(name) {
    const checkboxes = document.querySelectorAll(`input[name="${name}"]:checked`);
    return Array.from(checkboxes).map(cb => cb.value);
}

/**
 * 금액 문자열을 숫자로 변환
 */
function parseAmount(amountStr) {
    // "1억 2천만원" 같은 형식을 숫자로 변환
    const match = amountStr.match(/[\d,]+/g);
    if (!match) return 0;
    
    const numStr = match.join('').replace(/,/g, '');
    return parseInt(numStr) || 0;
}

/**
 * 정렬 적용
 */
function applySorting() {
    const sortValue = document.getElementById('sortSelect').value;
    
    let sorted = [...filteredBidData];
    
    switch (sortValue) {
        case 'date-desc':
            sorted.sort((a, b) => b.bidNtceDate.localeCompare(a.bidNtceDate));
            break;
        case 'date-asc':
            sorted.sort((a, b) => a.bidNtceDate.localeCompare(b.bidNtceDate));
            break;
        case 'amount-desc':
            sorted.sort((a, b) => parseAmount(b.asignBdgtAmt) - parseAmount(a.asignBdgtAmt));
            break;
        case 'amount-asc':
            sorted.sort((a, b) => parseAmount(a.asignBdgtAmt) - parseAmount(b.asignBdgtAmt));
            break;
        case 'deadline-asc':
            sorted.sort((a, b) => a.bidClseDate.localeCompare(b.bidClseDate));
            break;
        default:
            // 기본 순서 유지
            break;
    }
    
    filteredBidData = sorted;
    renderBidCards(filteredBidData);
}

/**
 * 공고 상태 필터 처리
 */
function handleStatusFilter(checkbox) {
    handleFilterChange('status', checkbox);
    applyFilters();
}

/**
 * 업무 구분 필터 처리
 */
function handleBusinessFilter(checkbox) {
    handleFilterChange('business', checkbox);
    applyFilters();
}

/**
 * 계약 방법 필터 처리
 */
function handleContractFilter(checkbox) {
    handleFilterChange('contract', checkbox);
    applyFilters();
}

/**
 * 금액 필터 처리
 */
function handleAmountFilter(checkbox) {
    handleFilterChange('amount', checkbox);
    applyFilters();
}

/**
 * 필터 변경 처리 (전체/개별 토글)
 */
function handleFilterChange(filterName, checkbox) {
    const allCheckbox = document.querySelector(`input[name="${filterName}"][value="all"]`);
    const otherCheckboxes = document.querySelectorAll(`input[name="${filterName}"]:not([value="all"])`);
    
    if (checkbox.value === 'all') {
        // 전체 선택/해제
        if (checkbox.checked) {
            otherCheckboxes.forEach(cb => cb.checked = false);
        }
    } else {
        // 개별 선택
        if (checkbox.checked) {
            allCheckbox.checked = false;
        } else {
            // 모든 개별 항목이 해제되면 전체 선택
            const anyChecked = Array.from(otherCheckboxes).some(cb => cb.checked);
            if (!anyChecked) {
                allCheckbox.checked = true;
            }
        }
    }
}

/**
 * 필터 초기화
 */
function resetFilters() {
    // 모든 체크박스 초기화
    document.querySelectorAll('.filter-checkbox input[type="checkbox"]').forEach(cb => {
        cb.checked = cb.value === 'all';
    });
    
    // 검색어 초기화
    document.getElementById('searchKeyword').value = '';
    
    // 정렬 초기화
    document.getElementById('sortSelect').value = 'default';
    
    // 필터 재적용
    applyFilters();
    
    showToast('필터가 초기화되었습니다');
}

/**
 * 입찰공고 카드 HTML 생성
 */
function createBidCardHTML(item) {
    const statusClass = getStatusClass(item.bidNtceSttusNm);
    
    return `
        <div class="bid-card">
            <div class="bid-card-header">
                <span class="bid-status ${statusClass}">${item.bidNtceSttusNm}</span>
                <span class="bid-number">${item.bidNtceNo}-${item.bidNtceOrd}</span>
            </div>

            <h3 class="bid-title">${item.bidNtceNm}</h3>

            <div class="bid-info">
                ${createInfoItems([
                    { icon: '🏢', label: '공고기관', value: item.ntceInsttNm },
                    { icon: '📅', label: '공고일', value: formatDate(item.bidNtceDate) },
                    { icon: '⏰', label: '마감일', value: formatDate(item.bidClseDate) },
                    { icon: '📂', label: '개찰일', value: formatDate(item.opengDate) }
                ])}
            </div>

            <div class="bid-meta">
                <span class="bid-tag">📦 ${item.bsnsDivNm}</span>
                <span class="bid-tag">📋 ${item.cntrctCnclsMthdNm}</span>
            </div>

            <div class="bid-amounts">
                ${createAmountItems([
                    { label: '배정예산', value: item.asignBdgtAmt },
                    { label: '추정가격', value: item.presmptPrce }
                ])}
            </div>

            <div class="bid-actions">
                <button class="bid-button primary" onclick="openBidUrl('${item.bidNtceUrl}')">
                    🔗 공고 보기
                </button>
                <button class="bid-button secondary" onclick="copyBidInfo('${item.bidNtceNo}', '${escapeHtml(item.bidNtceNm)}')">
                    📋 복사
                </button>
            </div>
        </div>
    `;
}

/**
 * 정보 아이템 생성
 */
function createInfoItems(items) {
    return items.map(item => `
        <div class="bid-info-item">
            <span class="bid-info-label">${item.icon} ${item.label}</span>
            <span class="bid-info-value">${item.value}</span>
        </div>
    `).join('');
}

/**
 * 금액 아이템 생성
 */
function createAmountItems(items) {
    return items.map(item => `
        <div class="amount-item">
            <span class="amount-label">${item.label}</span>
            <span class="amount-value">${item.value}</span>
        </div>
    `).join('');
}

/**
 * 상태에 따른 CSS 클래스
 */
function getStatusClass(status) {
    if (status.includes('취소')) return 'cancel';
    if (status.includes('재입찰') || status.includes('재공고')) return 'retry';
    return 'normal';
}

/**
 * 날짜 포맷팅
 */
function formatDate(dateStr) {
    if (!dateStr || dateStr.length < 8) return dateStr;
    
    const cleaned = dateStr.replace(/[^0-9]/g, '');
    if (cleaned.length >= 8) {
        const year = cleaned.substring(0, 4);
        const month = cleaned.substring(4, 6);
        const day = cleaned.substring(6, 8);
        return `${year}.${month}.${day}`;
    }
    return dateStr;
}

/**
 * HTML 이스케이프
 */
function escapeHtml(text) {
    const map = {
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#039;'
    };
    return text.replace(/[&<>"']/g, m => map[m]);
}

/**
 * 입찰공고 URL 열기
 */
function openBidUrl(url) {
    if (url) {
        window.open(url, '_blank');
    }
}

/**
 * 입찰정보 복사
 */
function copyBidInfo(bidNo, bidName) {
    const text = `공고번호: ${bidNo}\n공고명: ${bidName}`;
    
    navigator.clipboard.writeText(text)
        .then(() => showToast('복사되었습니다!'))
        .catch(err => {
            console.error('복사 실패:', err);
            showToast('복사에 실패했습니다', 'error');
        });
}

/**
 * 토스트 메시지 표시
 */
function showToast(message, type = 'success') {
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.textContent = message;
    toast.style.cssText = `
        position: fixed;
        bottom: 30px;
        right: 30px;
        background: ${type === 'success' ? '#10b981' : '#ef4444'};
        color: white;
        padding: 12px 24px;
        border-radius: 8px;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        z-index: 1000;
        animation: slideIn 0.3s ease;
    `;
    
    document.body.appendChild(toast);
    
    setTimeout(() => {
        toast.style.animation = 'slideOut 0.3s ease';
        setTimeout(() => toast.remove(), 300);
    }, 2000);
}

/**
 * 결과 헤더 표시
 */
function showResultHeader(data) {
    document.getElementById('resultCount').textContent = `${data.total_count}건`;
    document.getElementById('searchPeriod').textContent = 
        `검색 기간: ${data.search_period.start_display} ~ ${data.search_period.end_display}`;
    document.getElementById('resultHeader').classList.remove('hidden');
}

/**
 * 예시 쿼리 설정
 */
function setQuery(query) {
    document.getElementById('queryInput').value = query;
    document.getElementById('queryInput').focus();
}

/**
 * 로딩 상태 설정
 */
function setLoading(isLoading) {
    const btn = document.getElementById('searchBtn');
    const btnText = document.getElementById('btnText');
    const btnSpinner = document.getElementById('btnSpinner');

    btn.disabled = isLoading;
    btnText.classList.toggle('hidden', isLoading);
    btnSpinner.classList.toggle('hidden', !isLoading);
}

/**
 * 로딩 인디케이터 표시/숨기기
 */
function showLoadingIndicator() {
    document.getElementById('loadingIndicator').classList.remove('hidden');
}

function hideLoadingIndicator() {
    document.getElementById('loadingIndicator').classList.add('hidden');
}

/**
 * 결과 숨기기
 */
function hideResults() {
    document.getElementById('resultHeader').classList.add('hidden');
    document.getElementById('bidCards').innerHTML = '';
    document.getElementById('emptyResult').classList.add('hidden');
    document.getElementById('filterContainer').classList.add('hidden');
}

/**
 * 빈 결과 표시
 */
function showEmptyResult() {
    document.getElementById('emptyResult').classList.remove('hidden');
}

/**
 * 빈 결과 숨기기
 */
function hideEmptyResult() {
    document.getElementById('emptyResult').classList.add('hidden');
}

/**
 * 에러 표시/숨기기
 */
function showError(message) {
    document.getElementById('errorMessage').textContent = message;
    document.getElementById('errorContainer').classList.remove('hidden');
    
    setTimeout(() => hideError(), 5000);
}

function hideError() {
    document.getElementById('errorContainer').classList.add('hidden');
}

// 토스트 애니메이션 CSS
const style = document.createElement('style');
style.textContent = `
    @keyframes slideIn {
        from { transform: translateX(100%); opacity: 0; }
        to { transform: translateX(0); opacity: 1; }
    }
    
    @keyframes slideOut {
        from { transform: translateX(0); opacity: 1; }
        to { transform: translateX(100%); opacity: 0; }
    }
`;
document.head.appendChild(style);

// 초기화
document.addEventListener('DOMContentLoaded', () => {
    console.log('조달청 입찰공고 조회 시스템 준비 완료 (필터 기능 포함)');
    document.getElementById('queryInput').focus();
});
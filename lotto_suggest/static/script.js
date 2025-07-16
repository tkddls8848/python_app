document.addEventListener('DOMContentLoaded', function() {
    // 색상 배열 (로또 공 색상)
    const ballColors = [
        '#f56565', '#ed8936', '#ecc94b', '#48bb78', 
        '#38b2ac', '#4299e1', '#667eea', '#9f7aea'
    ];

    // 단일 번호 생성
    document.querySelectorAll('.method-btn').forEach(btn => {
        btn.addEventListener('click', async function() {
            const method = this.dataset.method;
            const methodName = this.textContent;
            
            try {
                const response = await fetch(`/api/generate/${method}`);
                const data = await response.json();
                
                if (data.error) {
                    alert(data.error);
                    return;
                }
                
                displaySingleResult(data.numbers, methodName);
            } catch (error) {
                console.error('Error:', error);
                alert('번호 생성 중 오류가 발생했습니다.');
            }
        });
    });

    // 연속 생성
    document.getElementById('generate-multiple-btn').addEventListener('click', async function() {
        const method = document.getElementById('multiple-method').value;
        const count = parseInt(document.getElementById('count-input').value);
        
        if (count < 1 || count > 20) {
            alert('생성 개수는 1~20 사이로 입력해주세요.');
            return;
        }
        
        try {
            const response = await fetch(`/api/generate-multiple/${method}/${count}`);
            const data = await response.json();
            
            if (data.error) {
                alert(data.error);
                return;
            }
            
            displayMultipleResults(data.results, method);
        } catch (error) {
            console.error('Error:', error);
            alert('번호 생성 중 오류가 발생했습니다.');
        }
    });

    // 분석 보기
    document.getElementById('show-analysis-btn').addEventListener('click', async function() {
        try {
            const response = await fetch('/api/analysis');
            const data = await response.json();
            
            displayAnalysis(data);
        } catch (error) {
            console.error('Error:', error);
            alert('분석 데이터를 불러오는 중 오류가 발생했습니다.');
        }
    });

    // 단일 결과 표시
    function displaySingleResult(numbers, methodName) {
        const resultBox = document.getElementById('single-result');
        const numbersDisplay = document.getElementById('numbers-display');
        
        numbersDisplay.innerHTML = '';
        
        numbers.forEach((num, index) => {
            const ball = document.createElement('div');
            ball.className = 'lotto-ball';
            ball.textContent = num;
            ball.style.backgroundColor = ballColors[index % ballColors.length];
            ball.style.animationDelay = `${index * 0.1}s`;
            numbersDisplay.appendChild(ball);
        });
        
        resultBox.classList.remove('hidden');
        resultBox.scrollIntoView({ behavior: 'smooth' });
    }

    // 연속 결과 표시
    function displayMultipleResults(results, method) {
        const resultsContainer = document.getElementById('multiple-results');
        
        resultsContainer.innerHTML = '';
        
        results.forEach((result, index) => {
            const item = document.createElement('div');
            item.className = 'multiple-item';
            
            const title = document.createElement('h4');
            title.textContent = `${result.id}번째 조합`;
            
            const numbersDisplay = document.createElement('div');
            numbersDisplay.className = 'numbers-display';
            
            result.numbers.forEach((num, numIndex) => {
                const ball = document.createElement('div');
                ball.className = 'lotto-ball';
                ball.textContent = num;
                ball.style.backgroundColor = ballColors[numIndex % ballColors.length];
                ball.style.width = '35px';
                ball.style.height = '35px';
                ball.style.fontSize = '0.9rem';
                numbersDisplay.appendChild(ball);
            });
            
            item.appendChild(title);
            item.appendChild(numbersDisplay);
            resultsContainer.appendChild(item);
        });
        
        resultsContainer.classList.remove('hidden');
        resultsContainer.scrollIntoView({ behavior: 'smooth' });
    }

    // 분석 데이터 표시
    function displayAnalysis(data) {
        const analysisContent = document.getElementById('analysis-content');
        
        // 최근 번호 표시
        const recentNumbersDisplay = document.getElementById('recent-numbers-display');
        recentNumbersDisplay.innerHTML = '';
        
        data.recent_numbers.forEach((numbers, index) => {
            const roundDiv = document.createElement('div');
            roundDiv.className = 'round-numbers';
            
            const roundTitle = document.createElement('span');
            roundTitle.textContent = `${1179 - index}회차: `;
            roundTitle.style.fontWeight = 'bold';
            roundDiv.appendChild(roundTitle);
            
            numbers.forEach(num => {
                const numBall = document.createElement('div');
                numBall.className = 'round-number';
                numBall.textContent = num;
                roundDiv.appendChild(numBall);
            });
            
            recentNumbersDisplay.appendChild(roundDiv);
        });
        
        // 빈도 분석 표시
        const frequencyDisplay = document.getElementById('frequency-display');
        frequencyDisplay.innerHTML = '';
        
        const sortedFreq = Object.entries(data.frequency)
            .sort((a, b) => b[1] - a[1])
            .filter(([num, freq]) => freq > 0);
        
        sortedFreq.forEach(([num, freq]) => {
            const freqItem = document.createElement('div');
            freqItem.className = 'frequency-item';
            
            const numSpan = document.createElement('span');
            numSpan.textContent = `번호 ${num}`;
            numSpan.style.fontWeight = 'bold';
            
            const freqSpan = document.createElement('span');
            freqSpan.textContent = `${freq}회 출현`;
            
            freqItem.appendChild(numSpan);
            freqItem.appendChild(freqSpan);
            frequencyDisplay.appendChild(freqItem);
        });
        
        // 미출현 번호 표시
        const notAppearedDisplay = document.getElementById('not-appeared-display');
        notAppearedDisplay.innerHTML = '';
        
        const notAppearedContainer = document.createElement('div');
        notAppearedContainer.className = 'not-appeared-numbers';
        
        data.not_appeared.forEach(num => {
            const numBall = document.createElement('div');
            numBall.className = 'not-appeared-number';
            numBall.textContent = num;
            notAppearedContainer.appendChild(numBall);
        });
        
        notAppearedDisplay.appendChild(notAppearedContainer);
        
        analysisContent.classList.remove('hidden');
        analysisContent.scrollIntoView({ behavior: 'smooth' });
    }
});

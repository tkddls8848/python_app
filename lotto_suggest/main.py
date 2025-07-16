from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import random
import time
from collections import Counter
from typing import List, Dict
import json

app = FastAPI(title="로또 번호 생성기", description="최근 10회차 회피 기능이 있는 로또 번호 생성기")

# 정적 파일과 템플릿 설정
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

class LottoGenerator:
    """로또 번호 생성 클래스"""
    
    def __init__(self):
        self.min_num = 1
        self.max_num = 45
        self.count = 6
        
        # 최근 10회차 로또 당첨번호 (1170회~1179회)
        self.recent_numbers = [
            [3, 16, 18, 24, 40, 44],  # 1179회
            [5, 6, 11, 27, 43, 44],   # 1178회
            [3, 7, 15, 16, 19, 43],   # 1177회
            [7, 9, 11, 21, 30, 35],   # 1176회
            [3, 4, 6, 8, 32, 42],     # 1175회
            [8, 11, 14, 17, 36, 39],  # 1174회
            [1, 5, 18, 20, 30, 35],   # 1173회
            [7, 9, 24, 40, 42, 44],   # 1172회
            [3, 6, 7, 11, 12, 17],    # 1171회
            [3, 13, 28, 34, 38, 42]   # 1170회
        ]
        
        self.recent_frequency = self._calculate_frequency()
        self.weights = self._calculate_weights()
    
    def _calculate_frequency(self):
        """최근 10회차에서 각 번호의 출현 빈도 계산"""
        all_numbers = []
        for round_numbers in self.recent_numbers:
            all_numbers.extend(round_numbers)
        return Counter(all_numbers)
    
    def _calculate_weights(self):
        """각 번호별 가중치 계산"""
        weights = {}
        base_weight = 1.0
        
        for num in range(self.min_num, self.max_num + 1):
            frequency = self.recent_frequency.get(num, 0)
            if frequency == 0:
                weights[num] = base_weight
            else:
                weight_reduction = min(0.7, frequency * 0.15)
                weights[num] = base_weight - weight_reduction
        
        return weights
    
    def generate_basic(self) -> List[int]:
        """기본 랜덤 생성"""
        numbers = random.sample(range(self.min_num, self.max_num + 1), self.count)
        return sorted(numbers)
    
    def generate_weighted(self) -> List[int]:
        """가중치 적용 생성"""
        selected = set()
        
        while len(selected) < self.count:
            numbers = list(range(self.min_num, self.max_num + 1))
            weights = [self.weights[num] for num in numbers]
            
            for i, num in enumerate(numbers):
                if num in selected:
                    weights[i] = 0
            
            if sum(weights) > 0:
                num = random.choices(numbers, weights=weights, k=1)[0]
                selected.add(num)
        
        return sorted(list(selected))
    
    def generate_anti_frequency(self) -> List[int]:
        """반빈도 알고리즘"""
        not_recent = []
        recent = set()
        
        for round_numbers in self.recent_numbers:
            recent.update(round_numbers)
        
        for num in range(self.min_num, self.max_num + 1):
            if num not in recent:
                not_recent.append(num)
        
        selected = []
        available_not_recent = not_recent.copy()
        
        while len(selected) < self.count and available_not_recent:
            num = random.choice(available_not_recent)
            selected.append(num)
            available_not_recent.remove(num)
        
        if len(selected) < self.count:
            remaining = set(range(self.min_num, self.max_num + 1)) - set(selected)
            
            while len(selected) < self.count:
                remaining_list = list(remaining)
                weights = [self.weights[num] for num in remaining_list]
                num = random.choices(remaining_list, weights=weights, k=1)[0]
                selected.append(num)
                remaining.remove(num)
        
        return sorted(selected)
    
    def generate_time_decay(self) -> List[int]:
        """시간 감쇠 가중치"""
        selected = set()
        
        while len(selected) < self.count:
            numbers = list(range(self.min_num, self.max_num + 1))
            weights = []
            
            for num in numbers:
                if num in selected:
                    weights.append(0)
                    continue
                
                weight = 1.0
                for i, round_numbers in enumerate(self.recent_numbers):
                    if num in round_numbers:
                        decay_factor = 0.9 - (i * 0.08)
                        weight *= (1 - decay_factor)
                
                weights.append(weight)
            
            if sum(weights) > 0:
                num = random.choices(numbers, weights=weights, k=1)[0]
                selected.add(num)
        
        return sorted(list(selected))
    
    def get_analysis(self) -> Dict:
        """분석 데이터 반환"""
        not_appeared = []
        for num in range(self.min_num, self.max_num + 1):
            if num not in self.recent_frequency:
                not_appeared.append(num)
        
        return {
            "recent_numbers": self.recent_numbers,
            "frequency": dict(self.recent_frequency),
            "weights": self.weights,
            "not_appeared": not_appeared
        }

# 전역 로또 생성기 인스턴스
lotto_gen = LottoGenerator()

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """메인 페이지"""
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/api/generate/{method}")
async def generate_numbers(method: str):
    """번호 생성 API"""
    methods = {
        "basic": lotto_gen.generate_basic,
        "weighted": lotto_gen.generate_weighted,
        "anti_frequency": lotto_gen.generate_anti_frequency,
        "time_decay": lotto_gen.generate_time_decay
    }
    
    if method not in methods:
        return {"error": "잘못된 방법입니다."}
    
    numbers = methods[method]()
    return {"numbers": numbers, "method": method}

@app.get("/api/analysis")
async def get_analysis():
    """분석 데이터 API"""
    return lotto_gen.get_analysis()

@app.get("/api/generate-multiple/{method}/{count}")
async def generate_multiple(method: str, count: int):
    """여러 번 생성 API"""
    if count > 20:  # 최대 20개로 제한
        count = 20
    
    methods = {
        "basic": lotto_gen.generate_basic,
        "weighted": lotto_gen.generate_weighted,
        "anti_frequency": lotto_gen.generate_anti_frequency,
        "time_decay": lotto_gen.generate_time_decay
    }
    
    if method not in methods:
        return {"error": "잘못된 방법입니다."}
    
    results = []
    for i in range(count):
        numbers = methods[method]()
        results.append({"id": i+1, "numbers": numbers})
    
    return {"results": results, "method": method, "count": count}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 
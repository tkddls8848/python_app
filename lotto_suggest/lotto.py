import random
import time
from collections import Counter


class RandomNumberGenerator:
    """1~45 사이의 숫자를 중복 없이 6개 선택하는 5가지 알고리즘"""
    
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
        
        # 최근 번호들의 출현 빈도 계산
        self.recent_frequency = self._calculate_frequency()
        
        # 가중치 설정 (최근 번호일수록 낮은 확률)
        self.weights = self._calculate_weights()
    
    def _calculate_frequency(self):
        """최근 10회차에서 각 번호의 출현 빈도 계산"""
        all_numbers = []
        for round_numbers in self.recent_numbers:
            all_numbers.extend(round_numbers)
        return Counter(all_numbers)
    
    def _calculate_weights(self):
        """각 번호별 가중치 계산 (최근 번호는 낮은 가중치)"""
        weights = {}
        base_weight = 1.0
        
        for num in range(self.min_num, self.max_num + 1):
            frequency = self.recent_frequency.get(num, 0)
            # 출현 빈도가 높을수록 가중치를 낮춤 (0.3 ~ 1.0)
            if frequency == 0:
                weights[num] = base_weight  # 안 나온 번호는 기본 가중치
            else:
                # 빈도에 따라 가중치 감소 (최대 70% 감소)
                weight_reduction = min(0.7, frequency * 0.15)
                weights[num] = base_weight - weight_reduction
        
        return weights
    
    def method1_random_sample(self):
        """방법 1: random.sample() 사용 (가장 효율적)"""
        numbers = random.sample(range(self.min_num, self.max_num + 1), self.count)
        return sorted(numbers)
    
    def method2_set_based(self):
        """방법 2: set을 이용한 중복 제거"""
        numbers = set()
        while len(numbers) < self.count:
            num = random.randint(self.min_num, self.max_num)
            numbers.add(num)
        return sorted(list(numbers))
    
    def method3_fisher_yates_shuffle(self):
        """방법 3: Fisher-Yates 셔플 알고리즘"""
        numbers = list(range(self.min_num, self.max_num + 1))
        
        # Fisher-Yates 셔플
        for i in range(len(numbers) - 1, 0, -1):
            j = random.randint(0, i)
            numbers[i], numbers[j] = numbers[j], numbers[i]
        
        # 처음 6개 선택
        return sorted(numbers[:self.count])
    
    def method4_linear_congruential(self):
        """방법 4: 선형 합동 생성기 (LCG) 사용"""
        # LCG 파라미터 (Park and Miller의 값)
        a = 16807
        m = 2**31 - 1
        seed = int(time.time() * 1000) % m
        
        numbers = set()
        while len(numbers) < self.count:
            seed = (a * seed) % m
            num = (seed % self.max_num) + self.min_num
            numbers.add(num)
        
        return sorted(list(numbers))
    
    def method5_list_pop(self):
        """방법 5: 리스트에서 pop으로 제거하는 방법"""
        numbers = list(range(self.min_num, self.max_num + 1))
        selected = []
        
        for _ in range(self.count):
            index = random.randint(0, len(numbers) - 1)
            selected.append(numbers.pop(index))
        
        return sorted(selected)
    
    def method6_weighted_random(self):
        """방법 6: 최근 번호 회피 가중치 적용"""
        selected = set()
        
        while len(selected) < self.count:
            # 가중치를 적용한 번호 선택
            numbers = list(range(self.min_num, self.max_num + 1))
            weights = [self.weights[num] for num in numbers]
            
            # 이미 선택된 번호는 가중치를 0으로 설정
            for i, num in enumerate(numbers):
                if num in selected:
                    weights[i] = 0
            
            # 가중치가 모두 0이 아닌 경우에만 선택
            if sum(weights) > 0:
                num = random.choices(numbers, weights=weights, k=1)[0]
                selected.add(num)
        
        return sorted(list(selected))
    
    def method7_anti_frequency(self):
        """방법 7: 반빈도 알고리즘 (최근 안 나온 번호 우선)"""
        # 최근에 안 나온 번호들을 우선적으로 선택
        not_recent = []
        recent = set()
        
        for round_numbers in self.recent_numbers:
            recent.update(round_numbers)
        
        for num in range(self.min_num, self.max_num + 1):
            if num not in recent:
                not_recent.append(num)
        
        selected = []
        
        # 최근에 안 나온 번호 중에서 먼저 선택
        available_not_recent = not_recent.copy()
        while len(selected) < self.count and available_not_recent:
            num = random.choice(available_not_recent)
            selected.append(num)
            available_not_recent.remove(num)
        
        # 부족한 개수만큼 나머지에서 선택 (가중치 적용)
        if len(selected) < self.count:
            remaining = set(range(self.min_num, self.max_num + 1)) - set(selected)
            
            while len(selected) < self.count:
                remaining_list = list(remaining)
                weights = [self.weights[num] for num in remaining_list]
                num = random.choices(remaining_list, weights=weights, k=1)[0]
                selected.append(num)
                remaining.remove(num)
        
        return sorted(selected)
    
    def method8_hybrid_avoidance(self):
        """방법 8: 하이브리드 회피 알고리즘"""
        # 최근 3회차는 강력 회피, 4~10회차는 약간 회피
        strong_avoid = set()
        weak_avoid = set()
        
        # 최근 3회차 번호는 강력 회피
        for i in range(3):
            strong_avoid.update(self.recent_numbers[i])
        
        # 4~10회차 번호는 약간 회피
        for i in range(3, 10):
            weak_avoid.update(self.recent_numbers[i])
        
        selected = []
        available = set(range(self.min_num, self.max_num + 1))
        
        for _ in range(self.count):
            # 가능한 선택지 중에서 가중치 적용하여 선택
            current_available = available - set(selected)
            
            if current_available:
                available_list = list(current_available)
                weights = []
                
                for num in available_list:
                    if num in strong_avoid:
                        weight = 0.2  # 강력 회피 (80% 감소)
                    elif num in weak_avoid:
                        weight = 0.6  # 약간 회피 (40% 감소)
                    else:
                        weight = 1.0  # 기본 가중치
                    weights.append(weight)
                
                num = random.choices(available_list, weights=weights, k=1)[0]
                selected.append(num)
        
        return sorted(selected)
    
    def method9_time_decay_weight(self):
        """방법 9: 시간 감쇠 가중치 (최근일수록 더 강하게 회피)"""
        selected = set()
        
        while len(selected) < self.count:
            numbers = list(range(self.min_num, self.max_num + 1))
            weights = []
            
            for num in numbers:
                if num in selected:
                    weights.append(0)
                    continue
                
                weight = 1.0
                # 각 회차별로 시간 감쇠 적용
                for i, round_numbers in enumerate(self.recent_numbers):
                    if num in round_numbers:
                        # 최근일수록 더 강한 가중치 감소 (1회차: 90% 감소, 10회차: 10% 감소)
                        decay_factor = 0.9 - (i * 0.08)
                        weight *= (1 - decay_factor)
                
                weights.append(weight)
            
            if sum(weights) > 0:
                num = random.choices(numbers, weights=weights, k=1)[0]
                selected.add(num)
        
        return sorted(list(selected))
    
    def generate_all_methods(self):
        """모든 방법으로 번호 생성"""
        print("=" * 70)
        print("9가지 알고리즘으로 1~45 중 6개 번호 생성 (최근 10회차 회피 적용)")
        print("=" * 70)
        
        methods = [
            ("기본 1: random.sample()", self.method1_random_sample),
            ("기본 2: set 기반 중복제거", self.method2_set_based),
            ("기본 3: Fisher-Yates 셔플", self.method3_fisher_yates_shuffle),
            ("기본 4: 선형 합동 생성기", self.method4_linear_congruential),
            ("기본 5: 리스트 pop 방식", self.method5_list_pop),
            ("회피 6: 가중치 적용", self.method6_weighted_random),
            ("회피 7: 반빈도 알고리즘", self.method7_anti_frequency),
            ("회피 8: 하이브리드 회피", self.method8_hybrid_avoidance),
            ("회피 9: 시간 감쇠 가중치", self.method9_time_decay_weight)
        ]
        
        for name, method in methods:
            start_time = time.time()
            result = method()
            end_time = time.time()
            
            # 최근 번호와의 중복 개수 계산
            recent_overlap = self._count_recent_overlap(result)
            overlap_info = f"(최근중복: {recent_overlap}개)"
            
            print(f"{name:25} : {result} {overlap_info} (실행시간: {(end_time-start_time)*1000:.3f}ms)")
        
        print("=" * 70)
    
    def _count_recent_overlap(self, selected_numbers):
        """선택된 번호와 최근 10회차 번호의 중복 개수 계산"""
        recent_set = set()
        for round_numbers in self.recent_numbers:
            recent_set.update(round_numbers)
        
        return len(set(selected_numbers) & recent_set)
    
    def show_recent_analysis(self):
        """최근 10회차 분석 정보 출력"""
        print("\n" + "=" * 50)
        print("최근 10회차 로또 당첨번호 분석")
        print("=" * 50)
        
        for i, numbers in enumerate(self.recent_numbers):
            round_num = 1179 - i
            print(f"{round_num}회차: {numbers}")
        
        print(f"\n📊 번호별 출현 빈도:")
        sorted_freq = sorted(self.recent_frequency.items(), key=lambda x: x[1], reverse=True)
        
        for num, freq in sorted_freq:
            if freq > 0:
                weight = self.weights[num]
                print(f"번호 {num:2d}: {freq}회 출현 (가중치: {weight:.2f})")
        
        # 최근에 전혀 안 나온 번호들
        not_appeared = []
        for num in range(self.min_num, self.max_num + 1):
            if num not in self.recent_frequency:
                not_appeared.append(num)
        
        if not_appeared:
            print(f"\n🎯 최근 10회차 미출현 번호: {not_appeared}")
        
        print("=" * 50)


def main():
    """메인 실행 함수"""
    generator = RandomNumberGenerator()
    
    while True:
        print("\n[ 로또 번호 생성기 - 최근 10회차 회피 기능 ]")
        print("1. 모든 방법으로 번호 생성")
        print("2. 특정 방법 선택")
        print("3. 최근 회피 알고리즘만 비교")
        print("4. 연속 생성 (10회)")
        print("5. 최근 10회차 분석 보기")
        print("0. 종료")
        
        choice = input("\n선택하세요: ").strip()
        
        if choice == "1":
            generator.generate_all_methods()
            
        elif choice == "2":
            print("\n방법을 선택하세요:")
            print("1) random.sample() - 기본")
            print("2) set 기반 - 기본")
            print("3) Fisher-Yates 셔플 - 기본")
            print("4) 선형 합동 생성기 - 기본")
            print("5) 리스트 pop - 기본")
            print("6) 가중치 적용 - 최근 회피")
            print("7) 반빈도 알고리즘 - 최근 회피")
            print("8) 하이브리드 회피 - 최근 회피")
            print("9) 시간 감쇠 가중치 - 최근 회피")
            
            method_choice = input("번호 입력: ").strip()
            methods = {
                "1": generator.method1_random_sample,
                "2": generator.method2_set_based,
                "3": generator.method3_fisher_yates_shuffle,
                "4": generator.method4_linear_congruential,
                "5": generator.method5_list_pop,
                "6": generator.method6_weighted_random,
                "7": generator.method7_anti_frequency,
                "8": generator.method8_hybrid_avoidance,
                "9": generator.method9_time_decay_weight
            }
            
            if method_choice in methods:
                result = methods[method_choice]()
                overlap = generator._count_recent_overlap(result)
                print(f"\n생성된 번호: {result}")
                print(f"최근 10회차와 중복: {overlap}개")
            else:
                print("잘못된 선택입니다.")
        
        elif choice == "3":
            print("\n=" * 50)
            print("최근 회피 알고리즘 4종 비교")
            print("=" * 50)
            
            avoid_methods = [
                ("가중치 적용", generator.method6_weighted_random),
                ("반빈도 알고리즘", generator.method7_anti_frequency),
                ("하이브리드 회피", generator.method8_hybrid_avoidance),
                ("시간 감쇠 가중치", generator.method9_time_decay_weight)
            ]
            
            for name, method in avoid_methods:
                result = method()
                overlap = generator._count_recent_overlap(result)
                print(f"{name:15} : {result} (최근중복: {overlap}개)")
            
            print("=" * 50)
                
        elif choice == "4":
            print("\n어떤 방법으로 연속 생성하시겠습니까?")
            print("1) 기본 알고리즘 (random.sample)")
            print("2) 최적 회피 알고리즘 (시간 감쇠 가중치)")
            
            gen_choice = input("선택: ").strip()
            
            if gen_choice == "1":
                print("\n연속 10회 생성 (기본 알고리즘):")
                for i in range(1, 11):
                    result = generator.method1_random_sample()
                    overlap = generator._count_recent_overlap(result)
                    print(f"{i:2d}회차: {result} (최근중복: {overlap}개)")
            elif gen_choice == "2":
                print("\n연속 10회 생성 (최적 회피 알고리즘):")
                for i in range(1, 11):
                    result = generator.method9_time_decay_weight()
                    overlap = generator._count_recent_overlap(result)
                    print(f"{i:2d}회차: {result} (최근중복: {overlap}개)")
            else:
                print("잘못된 선택입니다.")
        
        elif choice == "5":
            generator.show_recent_analysis()
            
        elif choice == "0":
            print("프로그램을 종료합니다.")
            break
            
        else:
            print("잘못된 선택입니다.")


if __name__ == "__main__":
    main()
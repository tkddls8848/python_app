import argparse
import requests
import json
import os
import concurrent.futures
from datetime import datetime
from tqdm import tqdm
import time
import sys
import threading

class BaseMetadataScanner:
    """공공데이터포털 메타데이터 스캐너 베이스 클래스"""
    
    def __init__(self, scan_type, start_num, end_num, max_workers=50, 
                 max_retries=3, retry_delay=1, timeout=5):
        self.start_num = start_num
        self.end_num = end_num
        self.max_workers = max_workers
        self.scan_type = scan_type
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.timeout = timeout
        self.base_url = f"https://www.data.go.kr/catalog/{{}}/{self.scan_type}.json"
        self.results = {
            'total': 0,
            'with_data': 0,
            'without_data': 0,
            'failed': 0,
            'retried': 0,
            'retry_success': 0,
            'waiting_room_detected': 0,
            'data_numbers': [],
            'data_types': {},
            'details': {}
        }
        
        # 대기실 제어용 변수
        self.waiting_room_active = False
        self.waiting_room_lock = threading.Lock()
        self.paused_futures = []
    
    def is_waiting_room_response(self, response):
        """대기실 응답인지 확인"""
        try:
            # 1. URL 리다이렉션 확인
            if 'waitingroom' in response.url.lower():
                print(f"🚨 대기실 감지 (URL): {response.url}")
                return True
            
            # 2. JSON 파싱 시도
            try:
                data = response.json()
                if isinstance(data, dict):
                    if data.get('description') == '해당 데이터는 존재하지 않습니다.':
                        return False
                    if data.get('title') or data.get('organization'):
                        return False
                    if isinstance(data, dict) and len(data) == 0:
                        return False
                elif isinstance(data, list):
                    return False
                
                return False
                
            except (json.JSONDecodeError, ValueError):
                pass
            
            # 3. Content-Type이 HTML이고 응답 내용에서 대기실 키워드 확인
            content_type = response.headers.get('Content-Type', '').lower()
            if 'text/html' in content_type:
                try:
                    response_text = response.text.lower()
                    waiting_room_patterns = [
                        ('waitingroom', 'main.html'),
                        ('대기실', '접속'),
                        ('대기실', '트래픽'),
                        ('접속 대기', ''),
                        ('잠시 대기', ''),
                        ('트래픽 과부하', ''),
                        ('서비스 대기', ''),
                        ('please wait', 'traffic'),
                        ('waiting room', ''),
                        ('대기 중', '과부하'),
                        ('서비스 점검', '대기')
                    ]
                    
                    for primary, secondary in waiting_room_patterns:
                        if primary in response_text:
                            if not secondary or secondary in response_text:
                                print(f"🚨 대기실 감지 (패턴 '{primary}'+'{secondary}'): {response.url}")
                                return True
                except:
                    pass
                
                print(f"⚠️  메타데이터 JSON이 아닌 HTML 사이트 수신 - URL: {response.url}")
                return False
            
            return False
                
        except Exception:
            return False
        
        return False
    
    def wait_for_site_recovery(self, test_num):
        """사이트 복구를 기다림"""
        print(f"\n🚨 대기실 감지! 사이트 복구 대기 중...")
        print(f"   📍 테스트 번호: {test_num}")
        
        recovery_check_interval = 30
        max_wait_time = 1800
        elapsed_time = 0
        
        while elapsed_time < max_wait_time:
            try:
                test_url = self.base_url.format(test_num)
                response = requests.get(test_url, timeout=self.timeout)
                
                if response.status_code == 200 and not self.is_waiting_room_response(response):
                    try:
                        response.json()
                        print(f"✅ 사이트 복구 완료! ({elapsed_time}초 경과)")
                        return True
                    except (json.JSONDecodeError, ValueError):
                        pass
                
                print(f"⏳ 대기 중... ({elapsed_time}초 경과)")
                time.sleep(recovery_check_interval)
                elapsed_time += recovery_check_interval
                
            except Exception as e:
                print(f"⚠️ 복구 확인 중 오류: {str(e)}")
                time.sleep(recovery_check_interval)
                elapsed_time += recovery_check_interval
        
        print(f"❌ 최대 대기 시간 초과 ({max_wait_time}초)")
        return False
    
    def extract_data_info(self, data, num, has_data, retry_count):
        """데이터 정보 추출 - 하위 클래스에서 구현"""
        raise NotImplementedError("하위 클래스에서 구현해야 합니다")
    
    def check_metadata(self, num, retry_count=0):
        """단일 메타데이터 조회"""
        url = self.base_url.format(num)
        
        try:
            response = requests.get(url, timeout=self.timeout)
            
            if response.status_code == 200:
                # 대기실 응답인지 확인
                if self.is_waiting_room_response(response):
                    with self.waiting_room_lock:
                        if not self.waiting_room_active:
                            self.waiting_room_active = True
                            self.results['waiting_room_detected'] += 1
                            
                            # 사이트 복구 대기
                            if self.wait_for_site_recovery(self.end_num):
                                self.waiting_room_active = False
                                # 복구 후 재시도
                                return self.check_metadata(num, retry_count)
                            else:
                                return {
                                    'number': num,
                                    'has_data': False,
                                    'status': 'waiting_room_timeout',
                                    'error': '대기실 복구 대기 시간 초과',
                                    'retry_count': retry_count
                                }
                        else:
                            # 다른 스레드가 이미 대기실 처리 중
                            time.sleep(30)
                            return self.check_metadata(num, retry_count)
                
                data = response.json()
                
                # 데이터셋 존재 여부 확인
                if (
                    'description' in data and 
                    data['description'] == '해당 데이터는 존재하지 않습니다.'
                ):
                    return {
                        'number': num,
                        'has_data': False,
                        'status': 'not_found',
                        'error': f'{self.scan_type} 메타데이터 없음',
                        'retry_count': retry_count
                    }
                
                # 데이터 존재 여부 확인
                has_data = bool(data)
                
                # 데이터 정보 추출 (하위 클래스에서 구현)
                data_info = self.extract_data_info(data, num, has_data, retry_count)
                
                # 데이터 타입 통계 업데이트
                data_type_key = f"{self.scan_type}_type"
                if data_info.get(data_type_key):
                    data_type = data_info[data_type_key].upper()
                    self.results['data_types'][data_type] = self.results['data_types'].get(data_type, 0) + 1
                
                if has_data and (data_info.get('url') or data_info.get('title')):
                    self.results['data_numbers'].append(num)
                    
                return data_info
                
            elif response.status_code == 404:
                return {
                    'number': num,
                    'has_data': False,
                    'status': 'not_found',
                    'error': f'{self.scan_type} 메타데이터 없음',
                    'retry_count': retry_count
                }
            else:
                return {
                    'number': num,
                    'has_data': False,
                    'status': 'error',
                    'error': f'HTTP {response.status_code}',
                    'retry_count': retry_count
                }
                
        except requests.exceptions.Timeout:
            if retry_count < self.max_retries:
                time.sleep(self.retry_delay)
                return self.check_metadata(num, retry_count + 1)
            else:
                return {
                    'number': num,
                    'has_data': False,
                    'status': 'timeout',
                    'error': f'요청 시간 초과 (재시도 {retry_count}회 후 실패)',
                    'retry_count': retry_count
                }
        except requests.exceptions.RequestException as e:
            return {
                'number': num,
                'has_data': False,
                'status': 'error',
                'error': str(e),
                'retry_count': retry_count
            }
        except json.JSONDecodeError:
            print(f"⚠️  JSON 파싱 실패 - 번호: {num}")
            print(f"📄 응답 내용 (처음 500자):")
            print(response.text[:500])
            print("=" * 50)
            
            return {
                'number': num,
                'has_data': False,
                'status': 'error',
                'error': '잘못된 JSON 형식',
                'response_content': response.text[:500],
                'retry_count': retry_count
            }
        except Exception as e:
            return {
                'number': num,
                'has_data': False,
                'status': 'error',
                'error': str(e),
                'retry_count': retry_count
            }
    
    def scan_range(self):
        """지정된 범위의 메타데이터 스캔"""
        total_numbers = self.end_num - self.start_num + 1
        self.results['total'] = total_numbers
        
        print(f"\n🔍 {self.scan_type} 메타데이터 스캔 시작")
        print(f"   📋 범위: {self.start_num} ~ {self.end_num}")
        print(f"   📊 총 {total_numbers:,}개 번호")
        print(f"   👥 동시 작업자: {self.max_workers}개")
        print(f"   🌐 Base URL: {self.base_url}")
        
        # 시작 시간 기록
        start_time = datetime.now()
        
        # 병렬 처리로 메타데이터 조회
        numbers = list(range(self.start_num, self.end_num + 1))
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_num = {
                executor.submit(self.check_metadata, num): num 
                for num in numbers
            }
            
            with tqdm(total=total_numbers, desc="스캔 진행") as pbar:
                for future in concurrent.futures.as_completed(future_to_num):
                    num = future_to_num[future]
                    
                    try:
                        result = future.result()
                        
                        # 결과 저장
                        self.results['details'][num] = result
                        
                        # 통계 업데이트
                        if result['status'] == 'success':
                            if result['has_data']:
                                self.results['with_data'] += 1
                            else:
                                self.results['without_data'] += 1
                            
                            if result.get('retry_count', 0) > 0:
                                self.results['retry_success'] += 1
                        else:
                            self.results['failed'] += 1
                        
                        if result.get('retry_count', 0) > 0:
                            self.results['retried'] += 1
                        
                    except Exception as e:
                        self.results['failed'] += 1
                        self.results['details'][num] = {
                            'number': num,
                            'has_data': False,
                            'status': 'exception',
                            'error': str(e)
                        }
                    
                    pbar.update(1)
                    
                    if pbar.n % 100 == 0:
                        success_rate = (self.results['with_data'] / pbar.n * 100) if pbar.n > 0 else 0
                        pbar.set_postfix({
                            '데이터있음': self.results['with_data'],
                            '데이터없음': self.results['without_data'],
                            '실패': self.results['failed'],
                            '성공률': f"{success_rate:.1f}%"
                        })
        
        # 종료 시간 및 소요 시간 계산
        end_time = datetime.now()
        elapsed_time = (end_time - start_time).total_seconds()
        
        # 최종 결과 저장
        self.results['scan_time'] = {
            'start': start_time.strftime('%Y-%m-%d %H:%M:%S'),
            'end': end_time.strftime('%Y-%m-%d %H:%M:%S'),
            'elapsed_seconds': elapsed_time,
            'elapsed_formatted': self._format_elapsed_time(elapsed_time)
        }
        
        # 데이터 번호 정렬
        self.results['data_numbers'].sort()
        
        return self.results
    
    def _format_elapsed_time(self, seconds):
        """초를 시:분:초 형식으로 변환"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        
        if hours > 0:
            return f"{hours}시간 {minutes}분 {secs}초"
        elif minutes > 0:
            return f"{minutes}분 {secs}초"
        else:
            return f"{secs}초"
    
    def save_results(self, output_dir="/data/metadata_results"):
        """스캔 결과 저장"""
        # 결과 저장 디렉토리 생성
        type_dir = os.path.join(output_dir, self.scan_type)
        os.makedirs(type_dir, exist_ok=True)
        
        # 1. 전체 결과 저장 (요약 포함)
        summary_file = os.path.join(type_dir, "summary.json")
        with open(summary_file, 'w', encoding='utf-8') as f:
            json.dump({
                'scan_range': f"{self.start_num}-{self.end_num}",
                'total_scanned': self.results['total'],
                'data_found': self.results['with_data'],
                'data_not_found': self.results['without_data'],
                'failed': self.results['failed'],
                'retried': self.results['retried'],
                'retry_success': self.results['retry_success'],
                'retry_success_rate': f"{(self.results['retry_success'] / self.results['retried'] * 100):.2f}%" if self.results['retried'] > 0 else "0.00%",
                'waiting_room_detected': self.results['waiting_room_detected'],
                'success_rate': f"{(self.results['with_data'] / self.results['total'] * 100):.2f}%",
                'data_types': self.results['data_types'],
                'scan_time': self.results.get('scan_time', {}),
                'data_count': len(self.results['data_numbers'])
            }, f, ensure_ascii=False, indent=2)
        
        # 2. 데이터가 있는 번호만 별도 저장
        numbers_file = os.path.join(type_dir, f"{self.scan_type}_numbers.json")
        with open(numbers_file, 'w', encoding='utf-8') as f:
            json.dump({
                f'{self.scan_type}_numbers': self.results['data_numbers'],
                'count': len(self.results['data_numbers']),
                'scan_info': {
                    'range': f"{self.start_num}-{self.end_num}"
                }
            }, f, ensure_ascii=False, indent=2)
        
        # 3. 번호 목록을 텍스트 파일로도 저장
        list_file = os.path.join(type_dir, f"{self.scan_type}_numbers.txt")
        with open(list_file, 'w', encoding='utf-8') as f:
            for num in self.results['data_numbers']:
                f.write(f"{num}\n")
        
        # 4. 상세 메타데이터 저장 (데이터가 있는 것만)
        metadata_file = os.path.join(type_dir, f"{self.scan_type}_metadata.json")
        metadata = {
            num: details for num, details in self.results['details'].items()
            if details.get('has_data', False)
        }
        with open(metadata_file, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)
        
        # 5. 타입별 번호 목록 저장
        for data_type, count in self.results['data_types'].items():
            if count > 0:
                type_numbers = []
                type_key = f"{self.scan_type}_type"
                for num, details in self.results['details'].items():
                    if details.get(type_key, '').upper() == data_type:
                        type_numbers.append(num)
                
                if type_numbers:
                    type_file = os.path.join(type_dir, f"{self.scan_type}_type_{data_type}.json")
                    with open(type_file, 'w', encoding='utf-8') as f:
                        json.dump({
                            f'{self.scan_type}_type': data_type,
                            'numbers': type_numbers,
                            'count': len(type_numbers)
                        }, f, ensure_ascii=False, indent=2)
        
        # 6. 실패한 번호들 저장
        failed_numbers = [
            num for num, details in self.results['details'].items()
            if details.get('status') != 'success' and details.get('status') != 'not_found'
        ]
        failed_file = None
        if failed_numbers:
            failed_file = os.path.join(type_dir, "failed_numbers.json")
            with open(failed_file, 'w', encoding='utf-8') as f:
                json.dump({
                    'failed_numbers': failed_numbers,
                    'count': len(failed_numbers),
                    'details': {num: self.results['details'][num] for num in failed_numbers}
                }, f, ensure_ascii=False, indent=2)
        
        return {
            'summary_file': summary_file,
            'numbers_file': numbers_file,
            'list_file': list_file,
            'metadata_file': metadata_file,
            'failed_file': failed_file if failed_numbers else None
        }
    
    def print_summary(self):
        """스캔 결과 요약 출력"""
        data_type_name = self._get_data_type_name()
        
        print("\n" + "=" * 60)
        print(f"📊 {self.scan_type} 메타데이터 스캔 완료!")
        print("=" * 60)
        print(f"🔍 스캔 범위: {self.start_num:,} ~ {self.end_num:,}")
        print(f"📋 총 스캔: {self.results['total']:,}개")
        print(f"✅ {data_type_name} 있음: {self.results['with_data']:,}개 ({self.results['with_data'] / self.results['total'] * 100:.1f}%)")
        print(f"❌ {data_type_name} 없음: {self.results['without_data']:,}개")
        print(f"⚠️  실패: {self.results['failed']:,}개")
        
        # 재시도 통계 표시
        if self.results['retried'] > 0:
            print(f"🔄 재시도: {self.results['retried']:,}개")
            print(f"✅ 재시도 성공: {self.results['retry_success']:,}개")
            retry_success_rate = (self.results['retry_success'] / self.results['retried'] * 100) if self.results['retried'] > 0 else 0
            print(f"📈 재시도 성공률: {retry_success_rate:.1f}%")
        
        # 대기실 감지 통계 표시
        if self.results['waiting_room_detected'] > 0:
            print(f"🚨 대기실 감지: {self.results['waiting_room_detected']:,}회")
        
        if self.results.get('scan_time'):
            print(f"\n⏱️  소요 시간: {self.results['scan_time']['elapsed_formatted']}")
            print(f"📅 시작: {self.results['scan_time']['start']}")
            print(f"📅 종료: {self.results['scan_time']['end']}")
        
        # 데이터 타입별 통계
        if self.results['data_types']:
            type_name = self._get_type_name()
            print(f"\n{type_name}:")
            sorted_types = sorted(self.results['data_types'].items(), key=lambda x: x[1], reverse=True)
            for data_type, count in sorted_types[:10]:
                percentage = count / self.results['with_data'] * 100 if self.results['with_data'] > 0 else 0
                print(f"   - {data_type}: {count}개 ({percentage:.1f}%)")
        
        # 상위 5개 기관 통계
        org_stats = {}
        for details in self.results['details'].values():
            if details.get('has_data') and details.get('organization'):
                org = details['organization']
                org_stats[org] = org_stats.get(org, 0) + 1
        
        if org_stats:
            print(f"\n🏢 상위 제공 기관:")
            sorted_orgs = sorted(org_stats.items(), key=lambda x: x[1], reverse=True)[:5]
            for org, count in sorted_orgs:
                print(f"   - {org}: {count}개")
    
    def _get_data_type_name(self):
        """데이터 타입 이름 반환"""
        names = {
            'fileData': '파일',
            'openapi': 'API',
            'standard': '표준'
        }
        return names.get(self.scan_type, '데이터')
    
    def _get_type_name(self):
        """타입 이름 반환"""
        names = {
            'fileData': '📁 파일 타입별 분포',
            'openapi': '🔌 API 타입별 분포',
            'standard': '📋 표준 타입별 분포'
        }
        return names.get(self.scan_type, '📊 타입별 분포')
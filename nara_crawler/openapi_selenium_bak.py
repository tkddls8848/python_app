from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import json
import time
import re
import os
import argparse
from datetime import datetime
import sys
from tqdm import tqdm
from parser import NaraParser, DataExporter
from metadata_openapi import OpenAPIMetadataScanner
import concurrent.futures
import threading
import queue
import psutil
import gc
from selenium.webdriver.chrome.service import Service
from selenium.common.exceptions import TimeoutException, WebDriverException

# 전역 변수
driver_pool = None

class OptimizedDriverPool:
    """최적화된 WebDriver 풀 관리 클래스"""
    def __init__(self, pool_size=10):
        self.pool_size = pool_size
        self.drivers = queue.Queue(maxsize=pool_size)
        self.lock = threading.Lock()
        self._initialize_pool()
    
    def _initialize_pool(self):
        """드라이버 풀 초기화"""
        for _ in range(self.pool_size):
            driver = self._create_driver()
            self.drivers.put(driver)
    
    def _create_driver(self):
        """최적화된 WebDriver 생성"""
        opts = Options()
        opts.add_argument("--headless")
        opts.add_argument("--no-sandbox")
        opts.add_argument("--disable-dev-shm-usage")
        opts.add_argument("--disable-gpu")
        opts.add_argument("--disable-extensions")
        opts.add_argument("--disable-plugins")
        opts.add_argument("--disable-background-timer-throttling")
        opts.add_argument("--disable-renderer-backgrounding")
        opts.add_argument("--disable-backgrounding-occluded-windows")
        opts.add_argument("--disable-features=TranslateUI")
        opts.add_argument("--disable-ipc-flooding-protection")
        opts.add_argument("--disable-images")
        opts.add_argument("--disable-css")
        opts.add_argument("--log-level=3")
        opts.add_argument("--no-default-browser-check")
        opts.add_argument("--no-first-run")
        opts.add_argument("--disable-default-apps")
        
        opts.add_experimental_option('excludeSwitches', ['enable-logging'])
        opts.add_experimental_option('useAutomationExtension', False)
        
        return webdriver.Chrome(options=opts)
    
    def get_driver(self):
        """사용 가능한 드라이버 반환"""
        try:
            return self.drivers.get(timeout=5)
        except queue.Empty:
            return self._create_driver()
    
    def return_driver(self, driver):
        """드라이버를 풀에 반환"""
        try:
            driver.get("about:blank")
            driver.delete_all_cookies()
            if self.drivers.qsize() < self.pool_size:
                self.drivers.put(driver)
            else:
                driver.quit()
        except:
            try:
                driver.quit()
            except:
                pass
    
    def close_all(self):
        """모든 드라이버 종료"""
        while not self.drivers.empty():
            try:
                driver = self.drivers.get_nowait()
                driver.quit()
            except:
                pass

class MemoryManager:
    """메모리 관리 클래스"""
    @staticmethod
    def get_memory_usage():
        """현재 메모리 사용량 반환"""
        process = psutil.Process()
        return process.memory_info().rss / 1024 / 1024  # MB 단위
    
    @staticmethod
    def check_memory_threshold(threshold_mb=2000):
        """메모리 사용량이 임계값을 초과하는지 확인"""
        return MemoryManager.get_memory_usage() > threshold_mb
    
    @staticmethod
    def cleanup():
        """메모리 정리"""
        gc.collect()

def get_api_id(url):
    """URL에서 API ID 추출"""
    m = re.search(r'/data/(\d+)/openapi', url)
    return m.group(1) if m else f"api_{url.replace('https://', '').replace('/', '_')}"

def crawl_url(url, output_dir, formats, driver_pool, timing_results=None):
    """단일 URL 크롤링 - 개선된 순서"""
    if timing_results is not None:
        start_time = time.time()
    os.makedirs(output_dir, exist_ok=True)
    api_id = get_api_id(url)
    
    driver = driver_pool.get_driver()
    
    crawling_result = {
        'success': False,
        'data': None,
        'saved_files': [],
        'errors': [],
        'api_id': api_id,
        'url': url
    }
    
    try:
        driver.get(url)
        
        # 페이지 로딩 대기
        WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
        
        parser = NaraParser(driver)
        
        # 결과 데이터 초기화
        result = {
            'api_id': api_id,
            'crawled_url': url,
            'crawled_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        
        # Step 1: 우선적으로 테이블 정보 추출
        table_info = parser.extract_table_info()
        result['info'] = table_info
        
        # API 유형 확인
        api_type_field = table_info.get('API 유형', '').upper()
        
        # Step 2: API 유형이 LINK인 경우 테이블 크롤링만 하고 종료
        if 'LINK' in api_type_field:
            result['api_type'] = 'link'
            result['skip_reason'] = 'LINK 타입 API는 테이블 정보만 수집'
            
            crawling_result['data'] = result
            crawling_result['success'] = True
            
            # 데이터 저장
            saved_files, save_errors = DataExporter.save_crawling_result(result, output_dir, api_id, formats)
            
            crawling_result['saved_files'] = saved_files
            crawling_result['errors'] = save_errors
            
            if timing_results is not None:
                timing_results[url] = time.time() - start_time
            return crawling_result['success']
        
        # Step 3: REST API인 경우 Swagger JSON 추출 시도
        swagger_json = parser.extract_swagger_json()
        
        if swagger_json and isinstance(swagger_json, dict) and swagger_json:
            # Swagger JSON이 존재하는 경우
            # API 정보 추출
            api_info = parser.extract_api_info(swagger_json)
            
            # Base URL 추출
            base_url = parser.extract_base_url(swagger_json)
            api_info['base_url'] = base_url
            
            # Schemes 추출
            api_info['schemes'] = swagger_json.get('schemes', ['https'])
            
            # 엔드포인트 추출
            endpoints = parser.extract_endpoints(swagger_json)
            
            # 결과 데이터 구성
            result.update({
                'api_info': api_info,
                'endpoints': endpoints,
                'swagger_json': swagger_json,
                'api_type': 'swagger'
            })
            
        else:
            # Step 4: Swagger JSON이 없는 경우 일반 API 정보 추출
            general_api_info = parser.extract_general_api_info()
            
            if general_api_info and (general_api_info.get('detail_info') or 
                                   general_api_info.get('request_parameters') or 
                                   general_api_info.get('response_elements')):
                # 결과 데이터 구성
                result.update({
                    'general_api_info': general_api_info,
                    'api_type': 'general'
                })
            else:
                # 정보부족 URL을 별도 파일에 저장
                failed_urls_file = os.path.join(output_dir, "failed_urls.txt")
                os.makedirs(output_dir, exist_ok=True)
                with open(failed_urls_file, 'a', encoding='utf-8') as f:
                    f.write(f"{url}\n")
                
                crawling_result['errors'].append("API 정보를 찾을 수 없어 failed_urls.txt에 기록")
                if timing_results is not None:
                    timing_results[url] = time.time() - start_time
                return False
        
        crawling_result['data'] = result
        crawling_result['success'] = True
        
        # 데이터 저장
        saved_files, save_errors = DataExporter.save_crawling_result(result, output_dir, api_id, formats)
        
        crawling_result['saved_files'] = saved_files
        crawling_result['errors'] = save_errors
        
        # 메모리 정리
        MemoryManager.cleanup()
        if timing_results is not None:
            timing_results[url] = time.time() - start_time
        return crawling_result['success']
    
    except Exception as e:
        error_msg = f"크롤링 실패: {str(e)}"
        print(f"❌ {error_msg}")
        crawling_result['errors'].append(error_msg)
        if timing_results is not None:
            timing_results[url] = time.time() - start_time
        return False
    finally:
        driver_pool.return_driver(driver)

def generate_urls_from_numbers(numbers):
    """숫자 리스트에서 URL 생성"""
    base_url = "https://www.data.go.kr/data/{}/openapi.do"
    return [base_url.format(num) for num in numbers]

def generate_urls(start_num, end_num):
    """시작번호와 끝번호 사이의 모든 URL 생성"""
    base_url = "https://www.data.go.kr/data/{}/openapi.do"
    return [base_url.format(num) for num in range(start_num, end_num + 1)]

def check_metadata_and_get_valid_numbers(start_num, end_num):
    """메타데이터를 체크하여 유효한 번호들만 반환"""
    print(f"\n🔍 메타데이터 스캔 시작: {start_num} ~ {end_num}")
    
    # 메타데이터 스캐너 생성
    scanner = OpenAPIMetadataScanner(
        start_num=start_num,
        end_num=end_num,
        max_workers=50
    )
    
    # 메타데이터 스캔 실행
    results = scanner.scan_range()
    
    # 결과 저장
    scanner.save_results()
    
    # 요약 출력
    scanner.print_summary()
    
    # 파일 데이터가 있는 번호들 반환
    valid_numbers = results['file_numbers']
    
    print(f"\n✅ 메타데이터 스캔 완료!")
    print(f"   📋 전체 스캔: {results['total']}개")
    print(f"   ✅ 유효한 번호: {len(valid_numbers)}개")
    print(f"   📊 필터링 비율: {(len(valid_numbers) / results['total'] * 100):.1f}%")
    
    return valid_numbers

def batch_crawl(urls, output_dir="/data/download_openapi", formats=['json', 'xml', 'md', 'csv'], max_workers=40):
    """범위 내의 모든 API 문서 크롤링"""
    total_urls = len(urls)
    
    print(f"\n🚀 배치 크롤링 시작")
    print(f"   📋 총 {total_urls}개 URL")
    print(f"   👥 동시 작업자: {max_workers}개")
    print(f"   📁 출력 디렉토리: {output_dir}")
    print(f"   💾 저장 형식: {', '.join(formats)}")
    
    # 드라이버 풀 초기화
    driver_pool = OptimizedDriverPool(pool_size=max_workers)
    
    # 결과 저장용 변수
    results = {
        'total': total_urls,
        'success': 0,
        'failed': 0,
        'link_type': 0,
        'swagger_type': 0,
        'general_type': 0,
        'insufficient_info': 0,  # 정보부족 카운트 추가
        'failed_urls': [],
        'start_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }
    
    timing_results = {}
    
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_url = {
                executor.submit(crawl_url, url, output_dir, formats, driver_pool, timing_results): url 
                for url in urls
            }
            
            with tqdm(concurrent.futures.as_completed(future_to_url), total=total_urls, desc="크롤링 진행") as pbar:
                for future in pbar:
                    url = future_to_url[future]
                    
                    if MemoryManager.check_memory_threshold():
                        print("\n⚠️ 메모리 사용량이 높습니다. 정리 중...")
                        MemoryManager.cleanup()
                    
                    try:
                        result = future.result()
                        if result:
                            results['success'] += 1
                        else:
                            results['failed'] += 1
                    except Exception as e:
                        results['failed'] += 1
                        results['failed_urls'].append(url)
                        print(f"\n⚠️ 예외 발생: {url} - {str(e)}")
                    
                    pbar.update(0)
                    
                    if timing_results:
                        avg_time = sum(timing_results.values()) / len(timing_results)
                        pbar.set_postfix({'평균소요(s)': f'{avg_time:.1f}'})
                    if pbar.n % 10 == 0:
                        MemoryManager.cleanup()
    
    finally:
        driver_pool.close_all()
    
    # 결과 요약
    results['end_time'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    results['success_rate'] = f"{(results['success'] / total_urls * 100):.1f}%" if total_urls > 0 else "0%"
    results['timing_per_url'] = timing_results
    
    # 결과 저장
    summary_file = os.path.join(output_dir, "crawling_summary.json")
    with open(summary_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    
    # 실패한 URL 목록 저장 (예외 발생한 URL만)
    if results['failed_urls']:
        exception_urls_file = os.path.join(output_dir, "exception_urls.txt")
        with open(exception_urls_file, 'w', encoding='utf-8') as f:
            for url in results['failed_urls']:
                f.write(f"{url}\n")
    
    # failed_urls.txt 파일 존재 여부 확인 (정보부족 URL들)
    failed_urls_file = os.path.join(output_dir, "failed_urls.txt")
    insufficient_info_count = 0
    if os.path.exists(failed_urls_file):
        with open(failed_urls_file, 'r', encoding='utf-8') as f:
            insufficient_info_count = len(f.readlines())
        results['insufficient_info'] = insufficient_info_count
    
    # 최종 결과 출력
    print("\n" + "=" * 50)
    print("🏁 배치 크롤링 완료!")
    print("=" * 50)
    print(f"📊 전체 결과:")
    print(f"   📋 총 처리: {results['total']}개 URL")
    print(f"   ✅ 성공: {results['success']}개 ({results['success_rate']})")
    print(f"   ❌ 실패: {results['failed']}개")
    if insufficient_info_count > 0:
        print(f"   📝 정보부족: {insufficient_info_count}개 (failed_urls.txt에 기록)")
    print(f"   📁 결과 위치: {output_dir}")
    print(f"   📋 요약 파일: crawling_summary.json")
    if results['failed'] > 0:
        print(f"   📄 예외 목록: exception_urls.txt")
    if insufficient_info_count > 0:
        print(f"   📄 정보부족 목록: failed_urls.txt")

def main():
    """메인 함수"""
    parser = argparse.ArgumentParser(description='나라장터 API 크롤러')
    parser.add_argument('-s', '--start', type=int, required=True, help='시작 문서 번호')
    parser.add_argument('-e', '--end', type=int, required=True, help='끝 문서 번호')
    parser.add_argument('-o', '--output-dir', default='/data/download_openapi', help='출력 디렉토리 (기본값: /data/download_openapi)')
    parser.add_argument('--formats', nargs='+', default=['json', 'xml', 'md', 'csv'],
                      choices=['json', 'xml', 'md', 'csv'], help='저장할 파일 형식')
    parser.add_argument('-w', '--workers', type=int, default=20, help='동시 작업자 수 (기본값: 20)')
    parser.add_argument('--no-headless', action='store_true', help='헤드리스 모드 비활성화')
    parser.add_argument('--timeout', type=int, default=5, help='페이지 로드 타임아웃 (초)')
    parser.add_argument('--skip-metadata', action='store_true', help='메타데이터 스캔 건너뛰기 (모든 번호 크롤링)')
    parser.add_argument('--scan-type', choices=['openapi'], default='openapi',
                      help='메타데이터 스캔 타입 (기본값: openapi)')
    
    args = parser.parse_args()
    
    # 입력값 검증
    if args.start > args.end:
        print("❌ 시작 번호가 끝 번호보다 클 수 없습니다.")
        sys.exit(1)
    
    if args.workers < 10 or args.workers > 40:
        print("⚠️ 동시 작업자 수는 10-40 사이로 설정해주세요.")
        args.workers = 20
    
    # 메타데이터 스캔 여부에 따라 처리
    if args.skip_metadata:
        print("⚠️ 메타데이터 스캔을 건너뛰고 모든 번호를 크롤링합니다.")
        urls = generate_urls(args.start, args.end)
    else:
        # 메타데이터 스캔을 통해 유효한 번호만 추출
        valid_numbers = check_metadata_and_get_valid_numbers(
            args.start, args.end
        )
        
        if not valid_numbers:
            print("❌ 유효한 번호가 없습니다. 크롤링을 종료합니다.")
            sys.exit(1)
        
        # 유효한 번호들로 URL 생성
        urls = generate_urls_from_numbers(valid_numbers)
    
    # 배치 크롤링 실행
    batch_crawl(
        urls,
        args.output_dir,
        args.formats,
        args.workers
    )

if __name__ == '__main__':
    main()
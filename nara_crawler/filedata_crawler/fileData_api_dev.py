# -*- coding: utf-8 -*-
import requests
import json
import os
import argparse
from datetime import datetime
import sys
from tqdm import tqdm
import concurrent.futures
import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException


class OdcloudCrawler:
    """infuser.odcloud.kr API crawler with table info extraction capability"""
    
    def __init__(self, timeout=30):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        self.timeout = timeout
        self.driver = None
        # 항상 driver를 설정하여 테이블 정보 추출 가능하도록 함
        self._setup_driver()
    
    def _setup_driver(self):
        """Setup Chrome driver for table info extraction"""
        try:
            chrome_options = Options()
            chrome_options.add_argument("--headless")
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--disable-gpu")
            
            self.driver = webdriver.Chrome(options=chrome_options)
            
        except Exception as e:
            print(f"Failed to setup Chrome driver: {e}")
            self.driver = None
    

    

    
    def extract_table_info(self, namespace_id):
        """테이블 정보 추출 - dataset-table과 fileDataDetail 표 요소에서 키:값 형태로 추출"""
        try:
            if not self.driver:
                return {}
            
            table_info = {}
            
            # data.go.kr 상세 페이지 URL (openapi 탭 포함)
            detail_url = f"https://www.data.go.kr/data/{namespace_id}/fileData.do#tab-layer-openapi"
            
            try:
                # 상세 페이지 방문
                self.driver.get(detail_url)
                
                # 페이지 로딩 대기
                WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.TAG_NAME, "body"))
                )
                
                # 동적 콘텐츠 로딩 대기
                time.sleep(2)
                
                # 정확한 테이블 찾기 (테스트 결과 기반)
                table_selectors = [
                    "table.dataset-table.fileDataDetail#apiDetailTableArea-pc",  # 정확한 선택자
                    "table#apiDetailTableArea-pc",  # ID만으로
                    "table.dataset-table.fileDataDetail",  # 클래스만으로
                    "table.dataset-table",  # parser.py 방식
                    "table"  # 모든 테이블 (마지막 수단)
                ]
                
                tables = []
                used_selector = ""
                
                for selector in table_selectors:
                    try:
                        tables = self.driver.find_elements(By.CSS_SELECTOR, selector)
                        if tables:
                            used_selector = selector
                            print(f"테이블 찾음 ({namespace_id}): {selector} ({len(tables)}개)")
                            break
                    except Exception as e:
                        continue
                
                if tables:
                    print(f"테이블 찾음 ({namespace_id}): table.dataset-table ({len(tables)}개)")
                    # 모든 테이블에서 정보 추출
                    for table in tables:
                        # 테이블 내용 추출
                        rows = table.find_elements(By.TAG_NAME, "tr")
                        
                        for row in rows:
                            try:
                                # th와 td 셀을 분리해서 찾기
                                th_cells = row.find_elements(By.TAG_NAME, "th")
                                td_cells = row.find_elements(By.TAG_NAME, "td")
                                
                                # th-td 쌍으로 처리
                                for i in range(min(len(th_cells), len(td_cells))):
                                    key_cell = th_cells[i]
                                    value_cell = td_cells[i]
                                    
                                    # 키 추출
                                    key = key_cell.get_attribute("textContent").strip()
                                    
                                    # 값 추출
                                    value = value_cell.get_attribute("textContent").strip()
                                    
                                    # 전화번호의 경우 span 태그에서 추출
                                    if "전화번호" in key:
                                        try:
                                            span = value_cell.find_element(By.TAG_NAME, "span")
                                            value = span.get_attribute("textContent").strip()
                                        except:
                                            pass
                                    
                                    # 링크가 있는 경우 링크 텍스트만 추출
                                    if not value:
                                        try:
                                            link = value_cell.find_element(By.TAG_NAME, "a")
                                            value = link.get_attribute("textContent").strip()
                                        except:
                                            pass
                                    
                                    if key and value:
                                        table_info[key] = value
                                            
                            except Exception as e:
                                continue
                else:
                    print(f"테이블을 찾을 수 없음 ({namespace_id})")
                    return {}
                
                return table_info
                
            except Exception as e:
                print(f"테이블 정보 추출 중 오류 발생 ({namespace_id}): {str(e)}")
                return {}
                
        except Exception as e:
            print(f"테이블 정보 추출 실패 ({namespace_id}): {str(e)}")
            return {}
    

    
    def crawl_namespace(self, namespace_id):
        """Crawl OAS document for specific namespace"""
        url = f"https://infuser.odcloud.kr/oas/docs?namespace={namespace_id}/v1"
        
        try:
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()
            
            # Check Content-Type
            content_type = response.headers.get('content-type', '')
            
            # 테이블 정보 추출 (항상 수행)
            table_info = {}
            if self.driver:
                table_info = self.extract_table_info(namespace_id)
            
            if 'application/json' in content_type:
                # JSON response
                result = {
                    'success': True,
                    'data': response.json(),
                    'namespace_id': namespace_id,
                    'url': url,
                    'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'status_code': response.status_code
                }
                
                # 테이블 정보가 있으면 추가
                if table_info and len(table_info) > 0:
                    result['table_info'] = table_info
                
                return result
            else:
                # Non-JSON response - save as text
                result = {
                    'success': True,
                    'data': response.text,
                    'namespace_id': namespace_id,
                    'url': url,
                    'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'status_code': response.status_code,
                    'content_type': content_type
                }
                
                # 테이블 정보가 있으면 추가
                if table_info and len(table_info) > 0:
                    result['table_info'] = table_info
                
                return result
                
        except requests.exceptions.RequestException as e:
            return {
                'success': False,
                'error': str(e),
                'namespace_id': namespace_id,
                'url': url,
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
    
    def close(self):
        """Close session and driver"""
        self.session.close()
        if self.driver:
            try:
                self.driver.quit()
            except:
                pass

def save_result(result, output_dir):
    """Save result to JSON file"""
    os.makedirs(output_dir, exist_ok=True)
    
    namespace_id = result['namespace_id']
    filename = f"{namespace_id}.json"
    filepath = os.path.join(output_dir, filename)
    
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    
    return filepath

def generate_namespace_range(start_num, end_num):
    """Generate namespace IDs between start and end numbers"""
    return [str(num) for num in range(start_num, end_num + 1)]

def batch_crawl(namespace_ids, output_dir="download_fileData_api", max_workers=10):
    """Batch crawling with optional table info extraction"""
    total_count = len(namespace_ids)
    
    print(f"\nOdcloud OAS Document Crawling Started")
    print(f"   Total {total_count} namespaces")
    print(f"   Workers: {max_workers}")
    print(f"   Output directory: {output_dir}")
    
    # Result storage
    results = {
        'total': total_count,
        'success': 0,
        'failed': 0,
        'table_extracted': 0,
        'table_failed': 0,
        'failed_namespaces': [],
        'start_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }
    
    crawler = OdcloudCrawler()
    
    def crawl_single_namespace(namespace_id):
        """Crawl single namespace with optional table info extraction"""
        try:
            result = crawler.crawl_namespace(namespace_id)
            
            if result['success']:
                saved_file = save_result(result, output_dir)
                print(f"SUCCESS {namespace_id} - Saved JSON: {saved_file}")
                
                # 테이블 정보 추출 결과 로깅
                if 'table_info' in result and result['table_info'] and len(result['table_info']) > 0:
                    table_count = len(result['table_info'])
                    print(f"TABLE INFO {namespace_id} - Extracted {table_count} items")
                else:
                    print(f"TABLE INFO {namespace_id} - No table info available (table not found or empty)")
                
                has_table_info = 'table_info' in result and len(result.get('table_info', {})) > 0
                return {'json': True, 'table': has_table_info}
            else:
                print(f"FAILED {namespace_id} - Error: {result.get('error', 'Unknown error')}")
                return {'json': False, 'table': False}
        except Exception as e:
            print(f"ERROR {namespace_id} - Exception: {str(e)}")
            return {'json': False, 'table': False}
    
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_namespace = {
                executor.submit(crawl_single_namespace, namespace_id): namespace_id 
                for namespace_id in namespace_ids
            }
            
            with tqdm(total=total_count, desc="Crawling Progress") as pbar:
                for future in concurrent.futures.as_completed(future_to_namespace):
                    namespace_id = future_to_namespace[future]
                    
                    try:
                        result = future.result()
                        if isinstance(result, dict):
                            if result.get('json'):
                                results['success'] += 1
                            else:
                                results['failed'] += 1
                                results['failed_namespaces'].append(namespace_id)
                            
                            # Count table extraction results
                            if result.get('table'):
                                results['table_extracted'] += 1
                            elif result.get('table') is False:
                                results['table_failed'] += 1
                        else:
                            # Legacy boolean result
                            if result:
                                results['success'] += 1
                            else:
                                results['failed'] += 1
                                results['failed_namespaces'].append(namespace_id)
                    except Exception as e:
                        results['failed'] += 1
                        results['failed_namespaces'].append(namespace_id)
                        print(f"\nException occurred: {namespace_id} - {str(e)}")
                    
                    pbar.update(1)
                    time.sleep(0.1)  # Prevent server overload
    
    finally:
        crawler.close()
    
    # Results summary
    results['end_time'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    results['success_rate'] = f"{(results['success'] / total_count * 100):.1f}%" if total_count > 0 else "0%"
    results['table_success_rate'] = f"{(results['table_extracted'] / total_count * 100):.1f}%" if total_count > 0 else "0%"
    
    # Save results
    os.makedirs(output_dir, exist_ok=True)
    summary_file = os.path.join(output_dir, "crawling_summary.json")
    with open(summary_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    
    # Save failed namespaces list
    if results['failed_namespaces']:
        failed_file = os.path.join(output_dir, "failed_namespaces.txt")
        with open(failed_file, 'w', encoding='utf-8') as f:
            for namespace_id in results['failed_namespaces']:
                f.write(f"{namespace_id}\n")
    
    # Final results output
    print("\n" + "=" * 50)
    print("Odcloud OAS Document Crawling Completed!")
    print("=" * 50)
    print(f"Overall Results:")
    print(f"   Total processed: {results['total']} namespaces")
    print(f"   JSON Success: {results['success']} ({results['success_rate']})")
    print(f"   JSON Failed: {results['failed']}")
    print(f"   Table Info Extracted: {results['table_extracted']} ({results.get('table_success_rate', '0%')})")
    print(f"   Table Info Failed: {results['table_failed']}")
    print(f"   Results location: {output_dir}")
    print(f"   Summary file: crawling_summary.json")
    if results['failed']:
        print(f"   Failed list: failed_namespaces.txt")

def check_metadata_and_get_valid_numbers(start_num, end_num, scan_type='fileData'):
    """메타데이터를 체크하여 유효한 번호들만 반환"""
    print(f"\n🔍 메타데이터 스캔 시작: {start_num} ~ {end_num}")
    
    # 메타데이터 스캐너 생성
    from metadata_fileData import FileDataMetadataScanner
    scanner = FileDataMetadataScanner(
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

def main():
    """Main function"""
    parser = argparse.ArgumentParser(description='Odcloud OAS Document Crawler with Metadata Check')
    parser.add_argument('-s', '--start', type=int, required=True, help='Start document number')
    parser.add_argument('-e', '--end', type=int, required=True, help='End document number')
    parser.add_argument('-o', '--output-dir', default='download_fileData_api', help='Output directory (default: download_fileData_api)')
    parser.add_argument('-w', '--workers', type=int, default=10, help='Number of workers (default: 10)')
    parser.add_argument('--timeout', type=int, default=30, help='Request timeout in seconds (default: 30)')
    parser.add_argument('--skip-metadata', action='store_true', help='Skip metadata check and crawl all numbers')
    parser.add_argument('--scan-type', choices=['openapi', 'fileData', 'standard'], default='fileData',
                      help='Metadata scan type (default: fileData)')

    
    args = parser.parse_args()
    
    # Input validation
    if args.start > args.end:
        print("ERROR: Start number cannot be greater than end number.")
        sys.exit(1)
    
    if args.workers < 1 or args.workers > 50:
        print("WARNING: Number of workers should be between 1-50. Setting to 10.")
        args.workers = 10
    

    
    # Metadata check and filtering
    if args.skip_metadata:
        print("⚠️ Skipping metadata check and crawling all numbers.")
        namespace_ids = generate_namespace_range(args.start, args.end)
    else:
        # Check metadata first to get valid numbers
        valid_numbers = check_metadata_and_get_valid_numbers(
            args.start, args.end, args.scan_type
        )
        
        if not valid_numbers:
            print("❌ No valid numbers found. Exiting.")
            sys.exit(1)
        
        # Convert to strings for namespace IDs
        namespace_ids = [str(num) for num in valid_numbers]
    
    # Execute batch crawling
    batch_crawl(
        namespace_ids,
        args.output_dir,
        args.workers
    )

if __name__ == '__main__':
    main()
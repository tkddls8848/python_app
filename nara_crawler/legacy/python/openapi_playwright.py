import asyncio
import argparse
import os
from datetime import datetime
from tqdm import tqdm
from parser import DataExporter
from metadata_openapi import OpenAPIMetadataScanner
import json
from playwright.async_api import async_playwright
import time
import re

# 문자열 정제 함수: 모든 이스케이프 문자 및 HTML 태그 완전 제거
def clean_text(text):
    if not isinstance(text, str):
        return text
    # \n, \r, \t 등 모든 이스케이프 문자 → 공백
    text = re.sub(r'[\n\r\t]+', ' ', text)
    # HTML 태그 제거
    text = re.sub(r'<[^>]+>', '', text)
    # 연속된 공백 → 한 칸
    text = re.sub(r' +', ' ', text)
    text = text.strip()
    return text

# dict/list 전체에 clean_text 재귀 적용 함수

def clean_all_text(obj):
    if isinstance(obj, dict):
        return {k: clean_all_text(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [clean_all_text(v) for v in obj]
    elif isinstance(obj, str):
        return clean_text(obj)
    else:
        return obj

# Playwright 기반 테이블/Swagger/일반 API 정보 추출 함수
async def extract_api_info(page, url):
    result = {
        'success': False,
        'data': None,
        'saved_files': [],
        'errors': [],
        'api_id': None,
        'url': url
    }
    try:
        await page.goto(url, timeout=15000)
        await page.wait_for_selector('body', timeout=7000)
        # --- 테이블 정보 추출 (parser.py의 extract_table_info를 playwright로 변환) ---
        table_info = {}
        tables = await page.query_selector_all('table.dataset-table')
        for table in tables:
            rows = await table.query_selector_all('tr')
            for row in rows:
                try:
                    th = await row.query_selector('th')
                    td = await row.query_selector('td')
                    if th and td:
                        key = clean_text(await th.inner_text())
                        value = clean_text(await td.inner_text())
                        if '전화번호' in key:
                            tel_div = await td.query_selector('#telNoDiv')
                            if tel_div:
                                value = clean_text(await tel_div.inner_text())
                        if not value:
                            link = await td.query_selector('a')
                            if link:
                                value = clean_text(await link.inner_text())
                        if key and value:
                            table_info[key] = value
                except:
                    continue
        # API ID 추출
        m = re.search(r'/data/(\d+)/openapi', url)
        api_id = m.group(1) if m else f"api_{url.replace('https://', '').replace('/', '_')}"
        result['api_id'] = api_id
        # API 유형 확인
        api_type_field = table_info.get('API 유형', '').upper()
        # LINK 타입 처리
        if 'LINK' in api_type_field:
            result['data'] = {
                'api_id': api_id,
                'crawled_url': url,
                'crawled_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'info': table_info,
                'api_type': 'link',
                'skip_reason': 'LINK 타입 API는 테이블 정보만 수집'
            }
            result['success'] = True
            return result
        # Swagger JSON 추출 (JS 변수/스크립트 등)
        swagger_json = None
        # 1. window 전역 swaggerJson 변수 시도
        swagger_json = await page.evaluate('''() => {
            try {
                if (typeof swaggerJson !== 'undefined' && swaggerJson !== null) {
                    if (typeof swaggerJson === 'string') {
                        if (swaggerJson.trim() === '') return null;
                        return JSON.parse(swaggerJson);
                    } else if (typeof swaggerJson === 'object') {
                        return swaggerJson;
                    }
                }
                return null;
            } catch (e) { return null; }
        }''')
        # 2. script 태그에서 직접 파싱 (셀레니움 방식)
        if not (swagger_json and isinstance(swagger_json, dict) and swagger_json):
            scripts = await page.query_selector_all('script')
            import re as _re, json as _json
            for script in scripts:
                try:
                    content = await script.inner_text()
                    # 객체 패턴
                    match = _re.search(r'var\s+swaggerJson\s*=\s*(\{.*?\})\s*;', content, _re.DOTALL)
                    if match:
                        try:
                            swagger_json = _json.loads(match.group(1))
                            break
                        except Exception:
                            continue
                    # 문자열 패턴 (백틱)
                    match2 = _re.search(r'var\s+swaggerJson\s*=\s*`(\{.*?\})`', content, _re.DOTALL)
                    if match2:
                        try:
                            swagger_json = _json.loads(match2.group(1))
                            break
                        except Exception:
                            continue
                    # 문자열 패턴 (따옴표)
                    match3 = _re.search(r'var\s+swaggerJson\s*=\s*"(\{.*?\})"', content, _re.DOTALL)
                    if match3:
                        try:
                            swagger_json = _json.loads(match3.group(1))
                            break
                        except Exception:
                            continue
                except Exception:
                    continue
        if swagger_json and isinstance(swagger_json, dict) and swagger_json:
            # Swagger API
            from parser import NaraParser
            parser = NaraParser(None)  # driver 없이 사용
            api_info = parser.extract_api_info(swagger_json)
            base_url = parser.extract_base_url(swagger_json)
            api_info['base_url'] = base_url
            api_info['schemes'] = swagger_json.get('schemes', ['https'])
            endpoints = parser.extract_endpoints(swagger_json)
            result['data'] = {
                'api_id': api_id,
                'crawled_url': url,
                'crawled_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'info': table_info,
                'api_info': api_info,
                'endpoints': endpoints,
                'swagger_json': swagger_json,
                'api_type': 'swagger'
            }
            result['success'] = True
            return result
        # 일반 API 정보 추출 (상세기능/요청변수/출력결과)
        # (간단화: 상세기능 div, 요청변수/출력결과 테이블 등)
        general_api_info = {}
        # 상세기능
        try:
            detail_div = await page.query_selector('#open-api-detail-result')
            if detail_div:
                desc_elem = await detail_div.query_selector('h4.tit')
                description = (await desc_elem.inner_text()).strip() if desc_elem else ''
                general_api_info['detail_info'] = {'description': description}
        except:
            pass
        # 요청변수/출력결과는 생략(필요시 parser.py 참고해 추가)
        if general_api_info:
            result['data'] = {
                'api_id': api_id,
                'crawled_url': url,
                'crawled_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'info': table_info,
                'general_api_info': general_api_info,
                'api_type': 'general'
            }
            result['success'] = True
            return result
        # 정보 부족
        result['errors'].append('API 정보를 찾을 수 없음')
        return result
    except Exception as e:
        result['errors'].append(f'크롤링 실패: {str(e)}')
        return result

# 단일 URL 크롤링 (컨텍스트 풀 구조)
async def crawl_url_playwright(browser, url, output_dir, formats, semaphore, timing_results):
    async with semaphore:
        start_time = time.time()
        context = await browser.new_context()
        page = await context.new_page()
        result = await extract_api_info(page, url)
        await context.close()
        elapsed = time.time() - start_time
        timing_results[url] = elapsed
        # 저장
        if result['success']:
            # clean_all_text 적용
            result['data'] = clean_all_text(result['data'])
            saved_files, save_errors = DataExporter.save_crawling_result(result['data'], output_dir, result['api_id'], formats)
            result['saved_files'] = saved_files
            result['errors'].extend(save_errors)
        return result

# 병렬 배치 크롤링 (브라우저 1개만 생성)
async def batch_crawl_playwright(urls, output_dir, formats, max_workers):
    semaphore = asyncio.Semaphore(max_workers)
    timing_results = {}
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        tasks = [crawl_url_playwright(browser, url, output_dir, formats, semaphore, timing_results) for url in urls]
        results = []
        with tqdm(asyncio.as_completed(tasks), total=len(tasks), desc="크롤링 진행") as pbar:
            for f in pbar:
                res = await f
                results.append(res)
                # 평균 소요 시간 표시
                if timing_results:
                    avg_time = sum(timing_results.values()) / len(timing_results)
                    pbar.set_postfix({'평균소요(s)': f'{avg_time:.1f}'})
        await browser.close()
    # 요약 저장
    summary = {
        'total': len(urls),
        'success': sum(1 for r in results if r['success']),
        'failed': sum(1 for r in results if not r['success']),
        'start_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'end_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'success_rate': f"{(sum(1 for r in results if r['success']) / len(urls) * 100):.1f}%" if urls else '0%',
        'timing_per_url': timing_results
    }
    os.makedirs(output_dir, exist_ok=True)
    # clean_all_text 적용
    summary_cleaned = clean_all_text(summary)
    with open(os.path.join(output_dir, 'crawling_summary.json'), 'w', encoding='utf-8') as f:
        json.dump(summary_cleaned, f, ensure_ascii=False, indent=2)
    return results

def generate_urls_from_numbers(numbers):
    base_url = "https://www.data.go.kr/data/{}/openapi.do"
    return [base_url.format(num) for num in numbers]

def generate_urls(start_num, end_num):
    base_url = "https://www.data.go.kr/data/{}/openapi.do"
    return [base_url.format(num) for num in range(start_num, end_num + 1)]

def check_metadata_and_get_valid_numbers(start_num, end_num):
    print(f"\n🔍 메타데이터 스캔 시작: {start_num} ~ {end_num}")
    scanner = OpenAPIMetadataScanner(start_num=start_num, end_num=end_num, max_workers=50)
    results = scanner.scan_range()
    scanner.save_results()
    scanner.print_summary()
    valid_numbers = results['file_numbers']
    print(f"\n✅ 메타데이터 스캔 완료! 유효 번호: {len(valid_numbers)}개")
    return valid_numbers

def main():
    parser = argparse.ArgumentParser(description='나라장터 API 크롤러 (Playwright 기반)')
    parser.add_argument('-s', '--start', type=int, required=True, help='시작 문서 번호')
    parser.add_argument('-e', '--end', type=int, required=True, help='끝 문서 번호')
    parser.add_argument('-o', '--output-dir', default='/data/download_openapi', help='출력 디렉토리 (기본값: /data/download_openapi)')
    parser.add_argument('--formats', nargs='+', default=['json', 'xml', 'md', 'csv'],
                      choices=['json', 'xml', 'md', 'csv'], help='저장할 파일 형식')
    parser.add_argument('-w', '--workers', type=int, default=15, help='동시 작업자 수 (기본값: 15, 허용범위: 10~20)')
    parser.add_argument('--skip-metadata', action='store_true', help='메타데이터 스캔 건너뛰기 (모든 번호 크롤링)')
    args = parser.parse_args()
    if args.start > args.end:
        print("❌ 시작 번호가 끝 번호보다 클 수 없습니다.")
        return
    if args.workers < 10 or args.workers > 20:
        print("⚠️ 동시 작업자 수는 10~20 사이로 설정해주세요. 기본값(15)로 진행합니다.")
        args.workers = 15
    if args.skip_metadata:
        print("⚠️ 메타데이터 스캔을 건너뛰고 모든 번호를 크롤링합니다.")
        urls = generate_urls(args.start, args.end)
    else:
        valid_numbers = check_metadata_and_get_valid_numbers(args.start, args.end)
        if not valid_numbers:
            print("❌ 유효한 번호가 없습니다. 크롤링을 종료합니다.")
            return
        urls = generate_urls_from_numbers(valid_numbers)
    asyncio.run(batch_crawl_playwright(urls, args.output_dir, args.formats, args.workers))

if __name__ == '__main__':
    main() 
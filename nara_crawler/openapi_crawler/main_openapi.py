"""
메인 크롤러 제어 파일
BeautifulSoup과 Playwright를 효율적으로 조합하여 사용

메타데이터 스캔은 util/scanner/base_scanner.py 기반으로 처리:
- util/scanner/metadata_fileData.py: FileData 스캔
- util/scanner/metadata_openapi.py: OpenAPI 스캔
- util/scanner/metadata_standard.py: Standard 스캔
"""

import asyncio
import argparse
import os
import json
from datetime import datetime
from typing import List, Dict, Tuple
import time

from bs_crawler import BSCrawler
from playwright_crawler import PlaywrightCrawler
from util.parser import DataExporter
from util.scanner.metadata_openapi import OpenAPIMetadataScanner

class HybridCrawler:
    def __init__(self, output_dir: str, formats: List[str], max_workers: int = 40):
        self.output_dir = output_dir
        self.formats = formats
        self.max_workers = max_workers
        
        # BS는 더 많은 동시 작업 가능
        self.bs_crawler = BSCrawler(max_workers=max_workers * 2)
        # Playwright는 리소스 제한
        self.pw_crawler = PlaywrightCrawler(max_workers=max(max_workers // 2, 5))
        
        # 통계 정보
        self.stats = {
            'bs_success': 0,
            'bs_failed': 0,
            'pw_success': 0,
            'pw_failed': 0,
            'total_time': 0,
            'url_timings': {}
        }
    
    def save_results(self, results: List[Dict]) -> Dict:
        """결과 저장"""
        saved_info = {
            'total_saved': 0,
            'failed_saves': 0,
            'saved_files': []
        }
        
        os.makedirs(self.output_dir, exist_ok=True)
        
        for result in results:
            if result.get('success') and result.get('data'):
                api_id = result.get('api_id', 'unknown')
                saved_files, save_errors = DataExporter.save_crawling_result(
                    result['data'], 
                    self.output_dir, 
                    api_id, 
                    self.formats
                )
                
                if saved_files:
                    saved_info['total_saved'] += 1
                    saved_info['saved_files'].extend(saved_files)
                else:
                    saved_info['failed_saves'] += 1
        
        return saved_info
    
    async def crawl_with_fallback(self, urls: List[str]) -> List[Dict]:
        """
        BeautifulSoup 우선 시도, 실패시 Playwright로 fallback
        """
        print(f"\n📊 크롤링 시작: 총 {len(urls)}개 URL")
        print(f"   - BeautifulSoup 우선 시도 (빠른 처리)")
        print(f"   - 필요시 Playwright fallback (동적 콘텐츠)")
        
        all_results = []
        start_time = time.time()
        
        # 1단계: BeautifulSoup으로 시도
        print("\n🚀 1단계: BeautifulSoup 크롤링...")
        bs_results, failed_urls = await self.bs_crawler.crawl_batch(urls)
        
        # BS 결과 처리
        for result in bs_results:
            all_results.append(result)
            self.stats['bs_success'] += 1
            self.stats['url_timings'][result['url']] = {
                'method': 'beautifulsoup',
                'success': True
            }
        
        print(f"   ✅ BeautifulSoup 성공: {len(bs_results)}개")
        print(f"   ⚠️  BeautifulSoup 실패: {len(failed_urls)}개")
        
        # 2단계: 실패한 URL을 Playwright로 재시도
        if failed_urls:
            print(f"\n🔄 2단계: Playwright로 {len(failed_urls)}개 재시도...")
            pw_results = await self.pw_crawler.crawl_batch(failed_urls)
            
            for result in pw_results:
                all_results.append(result)
                if result['success']:
                    self.stats['pw_success'] += 1
                else:
                    self.stats['pw_failed'] += 1
                
                self.stats['url_timings'][result['url']] = {
                    'method': 'playwright',
                    'success': result['success']
                }
            
            print(f"   ✅ Playwright 성공: {self.stats['pw_success']}개")
            print(f"   ❌ Playwright 실패: {self.stats['pw_failed']}개")
        
        self.stats['total_time'] = time.time() - start_time
        
        return all_results
    

    
    async def smart_crawl(self, urls: List[str]) -> List[Dict]:
        """
        URL 패턴 분석으로 스마트 크롤링
        동적 콘텐츠가 예상되는 URL은 바로 Playwright 사용
        """
        # URL 패턴으로 분류
        static_urls = []
        dynamic_urls = []
        
        # 동적 콘텐츠 힌트 패턴
        dynamic_patterns = [
            'swagger-ui',
            'api-docs',
            'interactive',
            'dynamic',
            '/v2/api',
            '/v3/api'
        ]
        
        for url in urls:
            # URL 패턴 체크
            is_dynamic = any(pattern in url.lower() for pattern in dynamic_patterns)
            
            if is_dynamic:
                dynamic_urls.append(url)
            else:
                static_urls.append(url)
        
        print(f"\n📊 스마트 크롤링 분석:")
        print(f"   - 정적 예상 (BS): {len(static_urls)}개")
        print(f"   - 동적 예상 (PW): {len(dynamic_urls)}개")
        
        all_results = []
        
        # BeautifulSoup 배치
        if static_urls:
            print("\n🚀 정적 콘텐츠 크롤링 (BeautifulSoup)...")
            bs_results, failed_urls = await self.bs_crawler.crawl_batch(static_urls)
            all_results.extend(bs_results)
            
            # 실패한 것은 dynamic_urls에 추가
            dynamic_urls.extend(failed_urls)
            
            for result in bs_results:
                self.stats['bs_success'] += 1
        
        # Playwright 배치
        if dynamic_urls:
            print(f"\n🔄 동적 콘텐츠 크롤링 (Playwright): {len(dynamic_urls)}개...")
            pw_results = await self.pw_crawler.crawl_batch(dynamic_urls)
            all_results.extend(pw_results)

            for result in pw_results:
                if result['success']:
                    self.stats['pw_success'] += 1
                else:
                    self.stats['pw_failed'] += 1

        return all_results

    async def optimized_crawl(self, urls: List[str]) -> List[Dict]:
        """
        최적화된 크롤링: LINK는 정적, 나머지는 동적
        1. 모든 URL을 빠르게 스캔하여 LINK 타입 분류
        2. LINK 타입 → BeautifulSoup으로 크롤링
        3. 나머지(Swagger, General) → Playwright로 크롤링
        """
        print(f"\n📊 크롤링 시작: 총 {len(urls)}개 URL")
        print(f"   - 1단계: LINK 타입 분류")
        print(f"   - 2단계: LINK → 정적 크롤링 (BS)")
        print(f"   - 3단계: Swagger/General → 동적 크롤링 (PW)")

        all_results = []
        start_time = time.time()

        # 1단계: LINK 타입 분류
        print("\n🔍 1단계: URL 타입 분류 중...")
        link_urls, other_urls = await self.bs_crawler.classify_urls_by_type(urls)

        print(f"   - LINK 타입: {len(link_urls)}개")
        print(f"   - Swagger/General: {len(other_urls)}개")

        # 2단계: LINK 타입은 BeautifulSoup으로 크롤링
        if link_urls:
            print(f"\n🚀 2단계: LINK 타입 크롤링 (BeautifulSoup): {len(link_urls)}개...")
            bs_results, failed_urls = await self.bs_crawler.crawl_batch(link_urls)
            all_results.extend(bs_results)

            for result in bs_results:
                self.stats['bs_success'] += 1

            # LINK인데 실패한 것도 동적으로 재시도
            if failed_urls:
                print(f"   ⚠️  LINK 타입 실패: {len(failed_urls)}개 → Playwright로 재시도")
                other_urls.extend(failed_urls)

        # 3단계: 나머지는 Playwright로 크롤링
        if other_urls:
            print(f"\n🔄 3단계: Swagger/General 크롤링 (Playwright): {len(other_urls)}개...")
            pw_results = await self.pw_crawler.crawl_batch(other_urls)
            all_results.extend(pw_results)

            for result in pw_results:
                if result['success']:
                    self.stats['pw_success'] += 1
                else:
                    self.stats['pw_failed'] += 1

            print(f"   ✅ Playwright 성공: {self.stats['pw_success']}개")
            print(f"   ❌ Playwright 실패: {self.stats['pw_failed']}개")

        self.stats['total_time'] = time.time() - start_time

        return all_results

    def generate_summary_report(self, results: List[Dict], saved_info: Dict) -> Dict:
        """상세 요약 리포트 생성"""
        # API 타입별 분류
        api_types = {}
        for result in results:
            if result.get('success') and result.get('data'):
                api_type = result['data'].get('api_type', 'unknown')
                api_types[api_type] = api_types.get(api_type, 0) + 1
        
        # 메소드별 성능
        method_performance = {
            'beautifulsoup': {
                'success': self.stats['bs_success'],
                'failed': self.stats.get('bs_failed', 0),
                'success_rate': (
                    f"{(self.stats['bs_success'] / (self.stats['bs_success'] + self.stats.get('bs_failed', 0)) * 100):.1f}%" 
                    if (self.stats['bs_success'] + self.stats.get('bs_failed', 0)) > 0 
                    else '0%'
                )
            },
            'playwright': {
                'success': self.stats['pw_success'],
                'failed': self.stats['pw_failed'],
                'success_rate': (
                    f"{(self.stats['pw_success'] / (self.stats['pw_success'] + self.stats['pw_failed']) * 100):.1f}%"
                    if (self.stats['pw_success'] + self.stats['pw_failed']) > 0
                    else '0%'
                )
            }
        }
        
        summary = {
            'crawling_summary': {
                'total_urls': len(results),
                'total_success': sum(1 for r in results if r.get('success')),
                'total_failed': sum(1 for r in results if not r.get('success')),
                'overall_success_rate': (
                    f"{(sum(1 for r in results if r.get('success')) / len(results) * 100):.1f}%"
                    if results else '0%'
                ),
                'total_time_seconds': round(self.stats['total_time'], 2),
                'avg_time_per_url': round(self.stats['total_time'] / len(results), 2) if results else 0
            },
            'method_performance': method_performance,
            'api_types_found': api_types,
            'save_summary': saved_info,
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'failed_urls': [
                r['url'] for r in results 
                if not r.get('success')
            ],
            'error_details': {
                r['url']: r.get('errors', [])
                for r in results
                if not r.get('success') and r.get('errors')
            }
        }
        
        return summary
    
    async def run(self, urls: List[str], strategy: str = 'optimized'):
        """
        메인 실행 함수

        Args:
            urls: 크롤링할 URL 리스트
            strategy: 'optimized' (LINK 정적, 나머지 동적) or 'fallback' (BS 우선) or 'smart' (패턴 분석)
        """
        print(f"\n{'='*60}")
        print(f"🤖 하이브리드 크롤러 시작")
        print(f"   전략: {strategy}")
        print(f"   URL 수: {len(urls)}")
        print(f"   출력 디렉토리: {self.output_dir}")
        print(f"   파일 형식: {', '.join(self.formats)}")
        print(f"{'='*60}")

        # 크롤링 실행
        if strategy == 'optimized':
            results = await self.optimized_crawl(urls)
        elif strategy == 'smart':
            results = await self.smart_crawl(urls)
        else:  # fallback
            results = await self.crawl_with_fallback(urls)
        
        # 결과 저장
        print("\n💾 결과 저장 중...")
        saved_info = self.save_results(results)
        
        # 요약 리포트 생성
        summary = self.generate_summary_report(results, saved_info)
        
        # 요약 파일 저장
        current_time = datetime.now().strftime('%Y%m%d_%H%M%S')
        summary_file = os.path.join(self.output_dir, f'crawling_summary_{current_time}.json')
        with open(summary_file, 'w', encoding='utf-8') as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)
        
        # 결과 출력
        self.print_summary(summary)
        
        return results, summary
    
    def print_summary(self, summary: Dict):
        """요약 정보 출력"""
        print(f"\n{'='*60}")
        print("📊 크롤링 완료 요약")
        print(f"{'='*60}")
        
        cs = summary['crawling_summary']
        print(f"\n📈 전체 통계:")
        print(f"   - 총 URL: {cs['total_urls']}개")
        print(f"   - 성공: {cs['total_success']}개")
        print(f"   - 실패: {cs['total_failed']}개")
        print(f"   - 성공률: {cs['overall_success_rate']}")
        print(f"   - 소요 시간: {cs['total_time_seconds']}초")
        print(f"   - 평균 처리 시간: {cs['avg_time_per_url']}초/URL")
        
        print(f"\n🔧 메소드별 성능:")
        mp = summary['method_performance']
        print(f"   BeautifulSoup:")
        print(f"      - 성공: {mp['beautifulsoup']['success']}개")
        print(f"      - 성공률: {mp['beautifulsoup']['success_rate']}")
        print(f"   Playwright:")
        print(f"      - 성공: {mp['playwright']['success']}개")
        print(f"      - 실패: {mp['playwright']['failed']}개")
        print(f"      - 성공률: {mp['playwright']['success_rate']}")
        
        if summary['api_types_found']:
            print(f"\n📦 API 타입별 분포:")
            for api_type, count in summary['api_types_found'].items():
                print(f"   - {api_type}: {count}개")
        
        print(f"\n💾 저장 결과:")
        ss = summary['save_summary']
        print(f"   - 저장 성공: {ss['total_saved']}개")
        print(f"   - 저장 실패: {ss['failed_saves']}개")
        print(f"   - 생성 파일: {len(ss['saved_files'])}개")
        
        if summary['failed_urls']:
            print(f"\n⚠️ 실패 URL: {len(summary['failed_urls'])}개")
            if len(summary['failed_urls']) <= 5:
                for url in summary['failed_urls']:
                    print(f"   - {url}")
            else:
                for url in summary['failed_urls'][:5]:
                    print(f"   - {url}")
                print(f"   ... 외 {len(summary['failed_urls'])-5}개")
        
        print(f"\n✅ 요약 파일 저장: {self.output_dir}/crawling_summary.json")
        print(f"{'='*60}\n")


def generate_urls_from_numbers(numbers: List[int]) -> List[str]:
    """번호 리스트로 URL 생성"""
    base_url = "https://www.data.go.kr/data/{}/openapi.do"
    return [base_url.format(num) for num in numbers]

def generate_urls(start_num: int, end_num: int) -> List[str]:
    """번호 범위로 URL 생성"""
    base_url = "https://www.data.go.kr/data/{}/openapi.do"
    return [base_url.format(num) for num in range(start_num, end_num + 1)]

def check_metadata_and_get_valid_numbers(start_num: int, end_num: int) -> List[int]:
    """메타데이터 스캔으로 유효 번호 확인"""
    print(f"\n🔍 메타데이터 스캔 시작: {start_num} ~ {end_num}")
    scanner = OpenAPIMetadataScanner(
        start_num=start_num, 
        end_num=end_num, 
        max_workers=150
    )
    results = scanner.scan_range()
    scanner.save_results()
    scanner.print_summary()
    
    valid_numbers = results['data_numbers']
    print(f"\n✅ 메타데이터 스캔 완료! 유효 번호: {len(valid_numbers)}개")
    return valid_numbers

async def main():
    parser = argparse.ArgumentParser(
        description='하이브리드 API 크롤러 (BeautifulSoup + Playwright)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
예제:
  # 기본 사용 (optimized 전략 - LINK 정적, 나머지 동적)
  python main_openapi.py -s 1000 -e 1100

  # Fallback 전략 (모든 URL을 BS 우선 시도)
  python main_openapi.py -s 1000 -e 1100 --strategy fallback

  # Smart 전략 (URL 패턴 분석)
  python main_openapi.py -s 1000 -e 1100 --strategy smart

  # 메타데이터 스캔 건너뛰기
  python main_openapi.py -s 1000 -e 1100 --skip-metadata

  # 특정 형식만 저장
  python main_openapi.py -s 1000 -e 1100 --formats json xml
        """
    )

    parser.add_argument('-s', '--start', type=int, required=True,
                       help='시작 문서 번호')
    parser.add_argument('-e', '--end', type=int, required=True,
                       help='끝 문서 번호')
    parser.add_argument('-o', '--output-dir',
                       default='./data',
                       help='출력 디렉토리 (기본값: ./data)')
    parser.add_argument('--formats', nargs='+',
                       default=['json', 'xml', 'csv'],
                       choices=['json', 'xml', 'csv'],
                       help='저장할 파일 형식 (기본값: 모든 형식)')
    parser.add_argument('-w', '--workers', type=int, default=30,
                       help='동시 작업자 수 (기본값: 30)')
    parser.add_argument('--skip-metadata', action='store_true',
                       help='메타데이터 스캔 건너뛰기')
    parser.add_argument('--strategy', choices=['optimized', 'fallback', 'smart'],
                       default='optimized',
                       help='크롤링 전략 (optimized: LINK정적/나머지동적, fallback: BS우선, smart: 패턴분석)')
    
    args = parser.parse_args()
    
    # 유효성 검사
    if args.start > args.end:
        print("❌ 오류: 시작 번호가 끝 번호보다 클 수 없습니다.")
        return
    
    if args.workers < 5 or args.workers > 40:
        print(f"⚠️ 경고: 작업자 수를 5-40 사이로 조정합니다. (입력값: {args.workers})")
        args.workers = max(5, min(40, args.workers))
    
    # URL 생성
    if args.skip_metadata:
        print("⚠️ 메타데이터 스캔을 건너뛰고 모든 번호를 크롤링합니다.")
        urls = generate_urls(args.start, args.end)
    else:
        valid_numbers = check_metadata_and_get_valid_numbers(args.start, args.end)
        if not valid_numbers:
            print("❌ 유효한 번호가 없습니다. 종료합니다.")
            return
        urls = generate_urls_from_numbers(valid_numbers)
    
    # 크롤러 실행
    crawler = HybridCrawler(
        output_dir=args.output_dir,
        formats=args.formats,
        max_workers=args.workers
    )
    
    await crawler.run(urls, strategy=args.strategy)

if __name__ == '__main__':
    asyncio.run(main())
import argparse
import requests
import json
import os
import concurrent.futures
from datetime import datetime
from tqdm import tqdm
import time
import sys

class FileDataMetadataScanner:
    """공공데이터포털 파일데이터 메타데이터 스캐너"""
    
    def __init__(self, start_num, end_num, max_workers=50, scan_type='fileData', 
                 max_retries=3, retry_delay=1, timeout=5):
        self.start_num = start_num
        self.end_num = end_num
        self.max_workers = max_workers
        self.scan_type = scan_type
        self.max_retries = max_retries  # 최대 재시도 횟수
        self.retry_delay = retry_delay  # 재시도 간 대기 시간 (초)
        self.timeout = timeout  # 요청 타임아웃 (초)
        self.base_url = f"https://www.data.go.kr/catalog/{{}}/{scan_type}.json"
        self.results = {
            'total': 0,
            'with_data': 0,
            'without_data': 0,
            'failed': 0,
            'retried': 0,  # 재시도된 요청 수
            'retry_success': 0,  # 재시도로 성공한 요청 수
            'file_numbers': [],
            'file_types': {},  # 파일 타입별 통계
            'details': {}
        }
        
    def check_metadata(self, num, retry_count=0):
        """단일 파일데이터 메타데이터 조회 (재시도 로직 포함)"""
        url = self.base_url.format(num)
        
        try:
            response = requests.get(url, timeout=self.timeout)
            
            if response.status_code == 200:
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
                        'error': '파일데이터 메타데이터 없음',
                        'retry_count': retry_count
                    }
                
                # 파일 데이터 존재 여부 확인
                has_data = bool(data)  # 데이터가 있으면 True
                
                # 파일 관련 정보 추출
                file_info = {
                    'number': num,
                    'has_data': has_data,
                    'title': data.get('title', ''),
                    'organization': data.get('organization', ''),
                    'description': data.get('description', ''),
                    'file_type': data.get('fileType', data.get('format', '')),
                    'file_size': data.get('fileSize', ''),
                    'download_url': data.get('url', ''),
                    'update_date': data.get('updateDate', data.get('modified', '')),
                    'license': data.get('license', ''),
                    'status': 'success',
                    'metadata': data,
                    'retry_count': retry_count
                }
                
                # 파일 타입 통계 업데이트
                if file_info['file_type']:
                    file_type = file_info['file_type'].upper()
                    self.results['file_types'][file_type] = self.results['file_types'].get(file_type, 0) + 1
                
                if has_data and (file_info['download_url'] or file_info['title']):
                    self.results['file_numbers'].append(num)
                    
                return file_info
                
            elif response.status_code == 404:
                return {
                    'number': num,
                    'has_data': False,
                    'status': 'not_found',
                    'error': '파일데이터 메타데이터 없음',
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
            # 재시도 가능한 경우 재시도
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
            return {
                'number': num,
                'has_data': False,
                'status': 'error',
                'error': '잘못된 JSON 형식',
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
        """지정된 범위의 파일데이터 메타데이터 스캔"""
        total_numbers = self.end_num - self.start_num + 1
        self.results['total'] = total_numbers
        
        print(f"\n🔍 파일데이터 메타데이터 스캔 시작")
        print(f"   📋 범위: {self.start_num} ~ {self.end_num}")
        print(f"   📊 총 {total_numbers:,}개 번호")
        print(f"   👥 동시 작업자: {self.max_workers}개")
        print(f"   🌐 Base URL: {self.base_url}")
        
        # 시작 시간 기록
        start_time = datetime.now()
        
        # 병렬 처리로 메타데이터 조회
        numbers = list(range(self.start_num, self.end_num + 1))
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # 모든 작업 제출
            future_to_num = {
                executor.submit(self.check_metadata, num): num 
                for num in numbers
            }
            
            # 진행 상황 표시와 함께 결과 처리
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
                            
                            # 재시도로 성공한 경우 카운트
                            if result.get('retry_count', 0) > 0:
                                self.results['retry_success'] += 1
                        else:
                            self.results['failed'] += 1
                        
                        # 재시도된 요청 카운트
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
                    
                    # 진행 상황 업데이트
                    if pbar.n % 100 == 0:
                        success_rate = (self.results['with_data'] / pbar.n * 100) if pbar.n > 0 else 0
                        pbar.set_postfix({
                            '파일있음': self.results['with_data'],
                            '파일없음': self.results['without_data'],
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
        
        # 파일 번호 정렬
        self.results['file_numbers'].sort()
        
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
    
    def save_results(self, output_dir="results"):
        """스캔 결과 저장"""
        # results/[type명] 폴더 생성
        type_dir = os.path.join(output_dir, self.scan_type)
        os.makedirs(type_dir, exist_ok=True)
        
        # 타임스탬프 생성
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # [타임스탬프] 폴더 생성
        timestamp_dir = os.path.join(type_dir, timestamp)
        os.makedirs(timestamp_dir, exist_ok=True)
        
        # 1. 전체 결과 저장 (요약 포함)
        summary_file = os.path.join(timestamp_dir, "summary.json")
        with open(summary_file, 'w', encoding='utf-8') as f:
            json.dump({
                'scan_range': f"{self.start_num}-{self.end_num}",
                'total_scanned': self.results['total'],
                'file_data_found': self.results['with_data'],
                'file_data_not_found': self.results['without_data'],
                'failed': self.results['failed'],
                'retried': self.results['retried'],
                'retry_success': self.results['retry_success'],
                'retry_success_rate': f"{(self.results['retry_success'] / self.results['retried'] * 100):.2f}%" if self.results['retried'] > 0 else "0.00%",
                'success_rate': f"{(self.results['with_data'] / self.results['total'] * 100):.2f}%",
                'file_types': self.results['file_types'],
                'scan_time': self.results.get('scan_time', {}),
                'file_count': len(self.results['file_numbers'])
            }, f, ensure_ascii=False, indent=2)
        
        # 2. 파일데이터가 있는 번호만 별도 저장
        file_numbers_file = os.path.join(timestamp_dir, "file_numbers.json")
        with open(file_numbers_file, 'w', encoding='utf-8') as f:
            json.dump({
                'file_numbers': self.results['file_numbers'],
                'count': len(self.results['file_numbers']),
                'scan_info': {
                    'range': f"{self.start_num}-{self.end_num}",
                    'timestamp': timestamp
                }
            }, f, ensure_ascii=False, indent=2)
        
        # 3. 파일 번호 목록을 텍스트 파일로도 저장
        file_list_file = os.path.join(timestamp_dir, "file_numbers.txt")
        with open(file_list_file, 'w', encoding='utf-8') as f:
            for num in self.results['file_numbers']:
                f.write(f"{num}\n")
        
        # 4. 상세 파일데이터 메타데이터 저장 (파일이 있는 것만)
        file_metadata_file = os.path.join(timestamp_dir, "file_metadata.json")
        file_metadata = {
            num: details for num, details in self.results['details'].items()
            if details.get('has_data', False)
        }
        with open(file_metadata_file, 'w', encoding='utf-8') as f:
            json.dump(file_metadata, f, ensure_ascii=False, indent=2)
        
        # 5. 파일 타입별 번호 목록 저장
        for file_type, count in self.results['file_types'].items():
            if count > 0:
                type_numbers = []
                for num, details in self.results['details'].items():
                    if details.get('file_type', '').upper() == file_type:
                        type_numbers.append(num)
                
                if type_numbers:
                    type_file = os.path.join(timestamp_dir, f"file_type_{file_type}.json")
                    with open(type_file, 'w', encoding='utf-8') as f:
                        json.dump({
                            'file_type': file_type,
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
            failed_file = os.path.join(timestamp_dir, "failed_numbers.json")
            with open(failed_file, 'w', encoding='utf-8') as f:
                json.dump({
                    'failed_numbers': failed_numbers,
                    'count': len(failed_numbers),
                    'details': {num: self.results['details'][num] for num in failed_numbers}
                }, f, ensure_ascii=False, indent=2)
        
        return {
            'summary_file': summary_file,
            'file_numbers_file': file_numbers_file,
            'file_list_file': file_list_file,
            'file_metadata_file': file_metadata_file,
            'failed_file': failed_file if failed_numbers else None
        }
    
    def print_summary(self):
        """스캔 결과 요약 출력"""
        print("\n" + "=" * 60)
        print("📊 파일데이터 메타데이터 스캔 완료!")
        print("=" * 60)
        print(f"🔍 스캔 범위: {self.start_num:,} ~ {self.end_num:,}")
        print(f"📋 총 스캔: {self.results['total']:,}개")
        print(f"✅ 파일 있음: {self.results['with_data']:,}개 ({self.results['with_data'] / self.results['total'] * 100:.1f}%)")
        print(f"❌ 파일 없음: {self.results['without_data']:,}개")
        print(f"⚠️  실패: {self.results['failed']:,}개")
        
        # 재시도 통계 표시
        if self.results['retried'] > 0:
            print(f"🔄 재시도: {self.results['retried']:,}개")
            print(f"✅ 재시도 성공: {self.results['retry_success']:,}개")
            retry_success_rate = (self.results['retry_success'] / self.results['retried'] * 100) if self.results['retried'] > 0 else 0
            print(f"📈 재시도 성공률: {retry_success_rate:.1f}%")
        
        if self.results.get('scan_time'):
            print(f"\n⏱️  소요 시간: {self.results['scan_time']['elapsed_formatted']}")
            print(f"📅 시작: {self.results['scan_time']['start']}")
            print(f"📅 종료: {self.results['scan_time']['end']}")
        
        # 파일 타입별 통계
        if self.results['file_types']:
            print(f"\n📁 파일 타입별 분포:")
            sorted_types = sorted(self.results['file_types'].items(), key=lambda x: x[1], reverse=True)
            for file_type, count in sorted_types[:10]:  # 상위 10개만 표시
                percentage = count / self.results['with_data'] * 100 if self.results['with_data'] > 0 else 0
                print(f"   - {file_type}: {count}개 ({percentage:.1f}%)")
        
        # 상위 5개 기관 통계 (파일이 있는 것만)
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


def main():
    """메인 함수"""
    parser = argparse.ArgumentParser(
        description='공공데이터포털 파일데이터 메타데이터 스캐너',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
예제:
  python metadata_filedata.py -s 1 -e 1000
  python metadata_filedata.py -s 1 -e 10000 -w 100
  python metadata_filedata.py -s 1 -e 100000 -o filedata_scan_results
  python metadata_filedata.py -s 1 -e 1000 -t openapi
  python metadata_filedata.py -s 1 -e 1000 -t fileData
  python metadata_filedata.py -s 1 -e 1000 -t standard
  python metadata_filedata.py -s 1 -e 1000 -r 5 -d 2.0 --timeout 10
        """
    )
    
    parser.add_argument('-s', '--start', type=int, required=True, 
                       help='시작 문서 번호')
    parser.add_argument('-e', '--end', type=int, required=True, 
                       help='끝 문서 번호')
    parser.add_argument('-w', '--workers', type=int, default=30,
                       help='동시 작업자 수 (기본값: 30)')
    parser.add_argument('-o', '--output', type=str, default='results',
                       help='결과 저장 디렉토리 (기본값: results)')
    parser.add_argument('-t', '--type', type=str, choices=['openapi', 'fileData', 'standard'],
                       help='스캔할 타입 (openapi, fileData, standard). 지정하지 않으면 모든 타입을 순차적으로 스캔')
    parser.add_argument('-r', '--retries', type=int, default=3,
                       help='최대 재시도 횟수 (기본값: 3)')
    parser.add_argument('-d', '--delay', type=float, default=1.0,
                       help='재시도 간 대기 시간(초) (기본값: 1.0)')
    parser.add_argument('--timeout', type=int, default=5,
                       help='요청 타임아웃(초) (기본값: 5)')
    
    args = parser.parse_args()
    
    # 입력값 검증
    if args.start < 1:
        print("❌ 시작 번호는 1 이상이어야 합니다.")
        sys.exit(1)
    
    if args.start > args.end:
        print("❌ 시작 번호가 끝 번호보다 클 수 없습니다.")
        sys.exit(1)
    
    if args.workers < 1 or args.workers > 100:
        print("⚠️  동시 작업자 수는 1-100 사이로 설정해주세요.")
        args.workers = 30
    
    # 스캔할 타입 결정
    scan_types = ['openapi', 'fileData', 'standard'] if args.type is None else [args.type]
    
    # 각 타입별로 스캔 실행
    for scan_type in scan_types:
        print(f"\n{'='*60}")
        print(f"🔍 {scan_type.upper()} 타입 스캔 시작")
        print(f"{'='*60}")
        
        # 스캐너 생성 및 실행
        scanner = FileDataMetadataScanner(
            args.start, args.end, args.workers, scan_type,
            max_retries=args.retries,
            retry_delay=args.delay,
            timeout=args.timeout
        )
        
        try:
            # 메타데이터 스캔
            scanner.scan_range()
            
            # 결과 저장 (results/[type명]/[타임스탬프]/ 형태로 저장)
            saved_files = scanner.save_results(args.output)
            
            # 요약 출력
            scanner.print_summary()
            
            # 저장된 파일 정보 출력
            print(f"\n💾 저장된 파일:")
            for key, filepath in saved_files.items():
                if filepath:
                    print(f"   - {os.path.basename(filepath)}")
            
            print(f"\n📁 결과 위치: {args.output}/{scan_type}/")
            
            # 파일이 있는 번호들 샘플 출력
            if scanner.results['file_numbers']:
                print(f"\n🔍 발견된 {scan_type} 번호 샘플 (처음 10개):")
                for num in scanner.results['file_numbers'][:10]:
                    details = scanner.results['details'].get(num, {})
                    title = details.get('title', 'N/A')[:50]
                    file_type = details.get('file_type', 'N/A')
                    print(f"   - {num}: [{file_type}] {title}...")
                    
        except KeyboardInterrupt:
            print(f"\n\n⚠️  {scan_type} 스캔이 사용자에 의해 중단되었습니다.")
            sys.exit(1)
        except Exception as e:
            print(f"\n❌ {scan_type} 스캔 중 오류 발생: {str(e)}")
            continue  # 다음 타입으로 계속 진행
    
    print(f"\n{'='*60}")
    print("🎉 모든 타입 스캔 완료!")
    print(f"{'='*60}")


if __name__ == '__main__':
    main()
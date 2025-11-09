##주기성 과거 데이터 추출 작업 필요
##URL Link로 데이터 주는 케이스 작업 필요

import requests
from bs4 import BeautifulSoup
import json
import os
import argparse
from datetime import datetime
import time
from metadata_fileData import FileDataMetadataScanner
import pandas as pd
import glob


class FileDataCSVCrawler:
    """data.go.kr 파일데이터 CSV 다운로드 및 메타데이터 저장"""
    
    def __init__(self, timeout=30):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        self.timeout = timeout
    
    def save_metadata(self, doc_num, metadata):
        """메타데이터를 JSON 파일로 저장"""
        try:
            save_dir = "/data/download_fileData"
            os.makedirs(save_dir, exist_ok=True)
            metadata_filename = f"{doc_num}_metadata.json"
            metadata_save_path = os.path.join(save_dir, metadata_filename)
            
            metadata_data = {
                'doc_num': doc_num,
                'url': f"https://www.data.go.kr/data/{doc_num}/fileData.do",
                'metadata': metadata,
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'item_count': len(metadata) if isinstance(metadata, dict) else 0
            }
            
            with open(metadata_save_path, 'w', encoding='utf-8') as f:
                json.dump(metadata_data, f, ensure_ascii=False, indent=2)
            
            print(f"메타데이터 저장 완료: {metadata_save_path} ({len(metadata)}개 항목)")
            return metadata_save_path
            
        except Exception as e:
            print(f"메타데이터 저장 실패 ({doc_num}): {str(e)}")
            return None
    
    def download_csv_and_save_metadata(self, doc_num, metadata):
        """파일 다운로드 및 메타데이터 저장"""
        url = f"https://www.data.go.kr/data/{doc_num}/fileData.do"
        print(f"문서번호 {doc_num} 처리 중: {url}")
        
        result = {
            'doc_num': doc_num,
            'url': url,
            'file_downloaded': False,
            'metadata_saved': False,
            'file_path': None,
            'metadata_file': None,
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'error': None
        }
        
        try:
            # 파일 다운로드
            response = self.session.get(url)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")
            scripts = soup.find_all("script", type="application/ld+json")
            
            file_downloaded = False
            for script in scripts:
                try:
                    data = json.loads(script.string)
                    if "distribution" in data and isinstance(data["distribution"], list):
                        for dist in data["distribution"]:
                            if "contentUrl" in dist:
                                file_url = dist["contentUrl"]
                                encoding_format = dist.get("encodingFormat", "").upper()
                                
                                print(f"파일 다운로드 URL: {file_url}")
                                print(f"파일 형식: {encoding_format}")
                                
                                # contentUrl 패턴 분석
                                if "data.go.kr" in file_url:
                                    # data.go.kr 도메인인 경우 - 기존 로직대로 파일 다운로드
                                    file_extension = self.get_extension_from_format(encoding_format)
                                    print(f"data.go.kr 도메인 감지 -> 파일 다운로드: {file_extension}")
                                    
                                    # contentUrl에서 파일 다운로드
                                    file_response = self.session.get(file_url)
                                    file_response.raise_for_status()
                                    
                                    save_dir = "/data/download_fileData"
                                    os.makedirs(save_dir, exist_ok=True)
                                    filename = f"file_{doc_num}{file_extension}"
                                    save_path = os.path.join(save_dir, filename)
                                    
                                    with open(save_path, "wb") as f:
                                        f.write(file_response.content)
                                    
                                    print(f"파일 다운로드 완료: {save_path}")
                                    result['file_downloaded'] = True
                                    result['file_path'] = save_path
                                    result['file_extension'] = file_extension
                                    result['encoding_format'] = encoding_format
                                    result['download_type'] = 'file_download'
                                    
                                else:
                                    # 다른 기관 주소인 경우 - URL을 텍스트 파일로 저장
                                    print(f"외부 기관 주소 감지 -> URL 텍스트 저장")
                                    
                                    save_dir = "/data/download_fileData"
                                    os.makedirs(save_dir, exist_ok=True)
                                    filename = f"file_{doc_num}.txt"
                                    save_path = os.path.join(save_dir, filename)
                                    
                                    # URL 정보를 텍스트 파일로 저장
                                    url_info = f"""문서번호: {doc_num}
원본 URL: {url}
파일 다운로드 URL: {file_url}
파일 형식: {encoding_format}
저장 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

파일 다운로드 링크:
{file_url}

참고: 이 파일은 외부 기관에서 제공하는 자료로, 직접 다운로드가 불가능합니다.
위 URL을 브라우저에서 열어 수동으로 다운로드하시기 바랍니다.
"""
                                    
                                    with open(save_path, "w", encoding="utf-8") as f:
                                        f.write(url_info)
                                    
                                    print(f"URL 정보 저장 완료: {save_path}")
                                    result['file_downloaded'] = True
                                    result['file_path'] = save_path
                                    result['file_extension'] = '.txt'
                                    result['encoding_format'] = encoding_format
                                    result['download_type'] = 'url_info'
                                
                                file_downloaded = True
                                break
                        
                        if file_downloaded:
                            break
                            
                except Exception as e:
                    print(f"문서번호 {doc_num} 내 스크립트 처리 에러: {e}")
                    continue
            
            # 메타데이터 저장
            if metadata:
                metadata_file = self.save_metadata(doc_num, metadata)
                if metadata_file:
                    result['metadata_saved'] = True
                    result['metadata_file'] = metadata_file
                    result['metadata_item_count'] = len(metadata) if isinstance(metadata, dict) else 0
                else:
                    print(f"메타데이터 저장 실패 ({doc_num})")
            
        except Exception as e:
            error_msg = f"문서번호 {doc_num} 처리 실패: {e}"
            print(error_msg)
            result['error'] = str(e)
        
        return result
    
    def get_extension_from_format(self, encoding_format):
        """encodingFormat을 기반으로 파일 확장자를 반환"""
        format_to_ext = {
            'CSV': '.csv',
            'XLS': '.xls',
            'XLSX': '.xlsx',
            'PPT': '.ppt',
            'PPTX': '.pptx',
            'DOC': '.doc',
            'DOCX': '.docx',
            'PDF': '.pdf',
            'ZIP': '.zip',
            'TXT': '.txt',
            'XML': '.xml',
            'JSON': '.json',
            'HWP': '.hwp',
            'JPG': '.jpg',
            'JPEG': '.jpeg',
            'PNG': '.png',
            'GIF': '.gif',
            'BMP': '.bmp',
            'TIFF': '.tiff',
            'AVI': '.avi',
            'MP4': '.mp4',
            'MP3': '.mp3',
            'WAV': '.wav',
            'RAR': '.rar',
            '7Z': '.7z',
            'TAR': '.tar',
            'GZ': '.gz'
        }
        
        return format_to_ext.get(encoding_format, '.bin')
    
    def close(self):
        """Close session"""
        self.session.close()
    
    def convert_metadata_to_csv(self, metadata_dir="/data/download_fileData"):
        """메타데이터 JSON 파일들을 구조화된 CSV로 변환"""
        try:
            # JSON 파일들 찾기
            json_pattern = os.path.join(metadata_dir, "*_metadata.json")
            json_files = glob.glob(json_pattern)
            
            if not json_files:
                print("❌ 변환할 메타데이터 JSON 파일이 없습니다.")
                return None
            
            print(f"\n🔄 메타데이터 JSON → CSV 변환 시작: {len(json_files)}개 파일")
            
            # 메타데이터 데이터 수집
            metadata_list = []
            
            for json_file in json_files:
                try:
                    with open(json_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    
                    # 기본 정보 추출
                    doc_num = data.get('doc_num', '')
                    url = data.get('url', '')
                    timestamp = data.get('timestamp', '')
                    item_count = data.get('item_count', 0)
                    
                    # 메타데이터 정보 추출
                    metadata = data.get('metadata', {})
                    
                    # 평면화된 데이터 구조 생성
                    flat_data = {
                        'doc_num': doc_num,
                        'url': url,
                        'timestamp': timestamp,
                        'item_count': item_count,
                        'name': metadata.get('name', ''),
                        'alternateName': metadata.get('alternateName', ''),
                        'description': metadata.get('description', ''),
                        'keywords': metadata.get('keywords', ''),
                        'license': metadata.get('license', ''),
                        'dateCreated': metadata.get('dateCreated', ''),
                        'dateModified': metadata.get('dateModified', ''),
                        'datePublished': metadata.get('datePublished', ''),
                        'additionalType': metadata.get('additionalType', ''),
                        'datasetTimeInterval': metadata.get('datasetTimeInterval', ''),
                        'encodingFormat': metadata.get('encodingFormat', ''),
                        'legislation': metadata.get('legislation', ''),
                        'creator_name': metadata.get('creator', {}).get('name', ''),
                        'creator_contactType': metadata.get('creator', {}).get('contactPoint', {}).get('contactType', ''),
                        'creator_telephone': metadata.get('creator', {}).get('contactPoint', {}).get('telephone', ''),
                        '@context': metadata.get('@context', ''),
                        '@type': metadata.get('@type', '')
                    }
                    
                    metadata_list.append(flat_data)
                    
                except Exception as e:
                    print(f"⚠️ JSON 파일 처리 실패 ({json_file}): {str(e)}")
                    continue
            
            if not metadata_list:
                print("❌ 변환할 데이터가 없습니다.")
                return None
            
            # DataFrame 생성
            df = pd.DataFrame(metadata_list)
            
            # CSV 파일로 저장
            csv_filename = "metadata_summary.csv"
            csv_path = os.path.join(metadata_dir, csv_filename)
            
            df.to_csv(csv_path, index=False, encoding='utf-8-sig')
            
            print(f"✅ 메타데이터 CSV 변환 완료: {csv_path}")
            print(f"   📊 총 {len(metadata_list)}개 레코드")
            print(f"   📋 컬럼 수: {len(df.columns)}개")
            
            # 컬럼 정보 출력
            print(f"\n📋 CSV 컬럼 정보:")
            for i, col in enumerate(df.columns, 1):
                print(f"   {i:2d}. {col}")
            
            return csv_path
            
        except Exception as e:
            print(f"❌ 메타데이터 CSV 변환 실패: {str(e)}")
            return None


def main():
    """Main function"""
    parser = argparse.ArgumentParser(description="data.go.kr 문서번호 범위별 파일데이터 csv 다운로드 및 메타데이터 저장")
    parser.add_argument('-s', '--start', type=int, required=True, help='시작 문서번호')
    parser.add_argument('-e', '--end', type=int, required=True, help='끝 문서번호')
    parser.add_argument('--timeout', type=int, default=30, help='Request timeout in seconds (default: 30)')
    
    args = parser.parse_args()
    
    # Input validation
    if args.start > args.end:
        print("ERROR: Start number cannot be greater than end number.")
        return
    
    # 결과 저장용
    results = {
        'total_scanned': args.end - args.start + 1,
        'valid_numbers': 0,
        'file_success': 0,
        'file_failed': 0,
        'metadata_success': 0,
        'metadata_failed': 0,
        'start_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'details': []
    }
    
    crawler = FileDataCSVCrawler(timeout=args.timeout)
    
    try:
        # 메타데이터 스캔을 통해 유효한 문서번호 확인
        scanner = FileDataMetadataScanner(args.start, args.end)
        scanner.scan_range()
        
        # 결과 저장
        scanner.save_results()
        
        # 요약 출력
        scanner.print_summary()
        
        # 파일 데이터가 있는 번호들 반환
        valid_numbers = scanner.results['file_numbers']
        
        print(f"\n✅ 메타데이터 스캔 완료!")
        print(f"   📋 전체 스캔: {scanner.results['total']}개")
        print(f"   ✅ 유효한 번호: {len(valid_numbers)}개")
        print(f"   📊 필터링 비율: {(len(valid_numbers) / scanner.results['total'] * 100):.1f}%")
        
        results['valid_numbers'] = len(valid_numbers)
        
        if not valid_numbers:
            print("❌ 유효한 번호가 없습니다. 처리를 종료합니다.")
            return
        
        print(f"\n📋 크롤링 시작: {len(valid_numbers)}개 유효한 문서번호")
        
        for doc_num in valid_numbers:
            # 해당 번호의 메타데이터 가져오기
            metadata = scanner.results['details'].get(doc_num, {}).get('metadata', {})
            result = crawler.download_csv_and_save_metadata(doc_num, metadata)
            results['details'].append(result)
            
            if result['file_downloaded']:
                results['file_success'] += 1
            else:
                results['file_failed'] += 1
            
            if result['metadata_saved']:
                results['metadata_success'] += 1
            else:
                results['metadata_failed'] += 1
            
            # 서버 부하 방지를 위한 대기
            time.sleep(0.5)
    
    finally:
        crawler.close()
    
    # 결과 요약 저장
    results['end_time'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    results['metadata_filter_rate'] = f"{(results['valid_numbers'] / results['total_scanned'] * 100):.1f}%" if results['total_scanned'] > 0 else "0%"
    results['file_success_rate'] = f"{(results['file_success'] / results['valid_numbers'] * 100):.1f}%" if results['valid_numbers'] > 0 else "0%"
    results['metadata_success_rate'] = f"{(results['metadata_success'] / results['valid_numbers'] * 100):.1f}%" if results['valid_numbers'] > 0 else "0%"
    
    # 결과 저장
    save_dir = "/data/download_fileData"
    os.makedirs(save_dir, exist_ok=True)
    summary_file = os.path.join(save_dir, "processing_summary.json")
    with open(summary_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    
    # 최종 결과 출력
    print("\n" + "=" * 50)
    print("파일데이터 다운로드 및 메타데이터 저장 완료!")
    print("=" * 50)
    print(f"전체 스캔: {results['total_scanned']}개")
    print(f"유효한 번호: {results['valid_numbers']}개 ({results['metadata_filter_rate']})")
    print(f"파일 다운로드 성공: {results['file_success']}개 ({results['file_success_rate']})")
    print(f"파일 다운로드 실패: {results['file_failed']}개")
    print(f"메타데이터 저장 성공: {results['metadata_success']}개 ({results['metadata_success_rate']})")
    print(f"메타데이터 저장 실패: {results['metadata_failed']}개")
    print(f"결과 위치: {save_dir}")
    print(f"요약 파일: processing_summary.json")
    
    # 메타데이터 JSON을 CSV로 변환
    if results['metadata_success'] > 0:
        csv_path = crawler.convert_metadata_to_csv(save_dir)
        if csv_path:
            print(f"📊 메타데이터 요약 CSV: {os.path.basename(csv_path)}")


if __name__ == '__main__':
    main()
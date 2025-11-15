from .base_scanner import BaseMetadataScanner

class FileDataMetadataScanner(BaseMetadataScanner):
    """공공데이터포털 FileData 메타데이터 스캐너"""
    
    def __init__(self, start_num, end_num, max_workers=50, 
                 max_retries=3, retry_delay=1, timeout=5):
        super().__init__('fileData', start_num, end_num, max_workers, 
                        max_retries, retry_delay, timeout)
    
    def extract_data_info(self, data, num, has_data, retry_count):
        """FileData 정보 추출"""
        file_info = {
            'number': num,
            'has_data': has_data,
            'title': data.get('title', ''),
            'organization': data.get('organization', ''),
            'description': data.get('description', ''),
            'file_type': data.get('fileType', data.get('format', '')),
            'file_size': data.get('fileSize', ''),
            'url': data.get('url', ''),  # base_scanner 호환성을 위한 키
            'download_url': data.get('url', ''),
            'update_date': data.get('updateDate', data.get('modified', '')),
            'license': data.get('license', ''),
            'status': 'success',
            'metadata': data,
            'retry_count': retry_count
        }
        return file_info


def main():
    """메인 함수"""
    parser = argparse.ArgumentParser(
        description='공공데이터포털 FileData 메타데이터 스캐너',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
예제:
  python metadata_fileData.py -s 1 -e 1000
  python metadata_fileData.py -s 1 -e 10000 -w 100
  python metadata_fileData.py -s 1 -e 100000 -o filedata_scan_results
  python metadata_fileData.py -s 1 -e 1000 -r 5 -d 2.0 --timeout 10
        """
    )
    
    parser.add_argument('-s', '--start', type=int, required=True, 
                       help='시작 문서 번호')
    parser.add_argument('-e', '--end', type=int, required=True, 
                       help='끝 문서 번호')
    parser.add_argument('-w', '--workers', type=int, default=30,
                       help='동시 작업자 수 (기본값: 30)')
    parser.add_argument('-o', '--output', type=str, default='/data/metadata_results',
                       help='결과 저장 디렉토리 (기본값: /data/metadata_results)')
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
    
    # 스캐너 생성 및 실행
    scanner = FileDataMetadataScanner(
        args.start, args.end, args.workers,
        max_retries=args.retries,
        retry_delay=args.delay,
        timeout=args.timeout
    )
    
    try:
        # 메타데이터 스캔
        scanner.scan_range()
        
        # 결과 저장
        saved_files = scanner.save_results(args.output)
        
        # 요약 출력
        scanner.print_summary()
        
        # 저장된 파일 정보 출력
        print(f"\n💾 저장된 파일:")
        for key, filepath in saved_files.items():
            if filepath:
                print(f"   - {os.path.basename(filepath)}")
        
        print(f"\n📁 결과 위치: {args.output}/fileData/")
        
    except KeyboardInterrupt:
        print(f"\n\n⚠️  FileData 스캔이 사용자에 의해 중단되었습니다.")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ FileData 스캔 중 오류 발생: {str(e)}")
        sys.exit(1)


if __name__ == '__main__':
    main()
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
데이터포털 활용신청 자동화 워크플로우
유틸리티 함수 모듈
"""

import logging
import os
from datetime import datetime
from typing import Dict, Any


def setup_logging():
    """로깅 설정"""
    log_filename = "data_portal_automation.log"
    
    # 로그 포맷 설정
    log_format = "%(asctime)s - %(levelname)s - %(message)s"
    date_format = "%Y-%m-%d %H:%M:%S"
    
    # 파일과 콘솔 모두에 로그 출력
    logging.basicConfig(
        level=logging.INFO,
        format=log_format,
        datefmt=date_format,
        handlers=[
            logging.FileHandler(log_filename, encoding='utf-8'),
            # 콘솔 출력은 ERROR 레벨만 (메인 출력과 중복 방지)
            logging.StreamHandler()
        ]
    )
    
    # 콘솔 핸들러는 ERROR 레벨만 출력하도록 설정
    console_handler = logging.getLogger().handlers[1]
    console_handler.setLevel(logging.ERROR)
    
    logging.info("="*60)
    logging.info("데이터포털 활용신청 자동화 워크플로우 시작")
    logging.info("="*60)


def print_banner():
    """프로그램 시작 배너 출력"""
    banner = """
╔══════════════════════════════════════════════════════════════╗
║                                                              ║
║           데이터포털 활용신청 자동화 워크플로우               ║
║                                                              ║
║                    🚀 자동화 도구 v2.0                       ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝

📋 주요 기능:
  • UDDI 파일 기반 일괄 처리
  • 직접 폼 페이지 접근으로 처리 속도 향상
  • 자동 폼 작성 및 제출
  • 상세한 처리 결과 리포트

⚠️  주의사항:
  • uddi.txt 파일에 처리할 UDDI 목록을 준비해주세요
  • 브라우저에서 수동 로그인이 필요합니다
  • 처리 과정에서 브라우저를 닫지 마세요

""".strip()
    
    print(banner)
    print()


def print_results(results: Dict[str, Any]):
    """
    처리 결과 출력
    
    Args:
        results: 처리 결과 딕셔너리
    """
    print("\n" + "="*60)
    print("📊 활용신청 처리 결과")
    print("="*60)
    
    print(f"📈 전체 통계:")
    print(f"   • 총 UDDI 수: {results['total']}개")
    print(f"   • 성공: {results['success']}개")
    print(f"   • 실패: {len(results['failed'])}개")
    
    if results['success'] > 0:
        success_rate = (results['success'] / results['total']) * 100
        print(f"   • 성공률: {success_rate:.1f}%")
    
    # 실패한 항목 상세 출력
    if results['failed']:
        print(f"\n❌ 실패한 UDDI 목록:")
        for i, uddi in enumerate(results['failed'], 1):
            reason = results['failed_details'].get(uddi, '알 수 없는 오류')
            print(f"   {i}. {uddi}")
            print(f"      사유: {reason}")
    
    print("="*60)
    
    # 로그에도 결과 기록
    logging.info(f"처리 완료 - 전체: {results['total']}, 성공: {results['success']}, 실패: {len(results['failed'])}")
    for uddi in results['failed']:
        reason = results['failed_details'].get(uddi, '알 수 없는 오류')
        logging.error(f"실패: {uddi} - {reason}")


def create_sample_uddi_file():
    """
    샘플 UDDI 파일 생성
    """
    sample_content = """# 데이터포털 활용신청 UDDI 목록
# '#'으로 시작하는 줄은 주석입니다
# 각 줄에 하나씩 UDDI를 입력하세요

# 예시 UDDI (실제 사용할 UDDI로 교체해주세요)
uddi:52e786d0-501c-4784-a05c-ef0b06c95958_202012021116
uddi:a1b2c3d4-5e6f-7890-abcd-ef1234567890_202301151030
uddi:98765432-1098-7654-3210-fedcba987654_202205201445

# 더 많은 UDDI를 추가하려면 아래에 입력하세요
# uddi:11111111-2222-3333-4444-555555555555_202304101200
"""
    
    with open('uddi_sample.txt', 'w', encoding='utf-8') as f:
        f.write(sample_content)
    
    print("📄 샘플 UDDI 파일 생성: uddi_sample.txt")
    print("   이 파일을 참고하여 uddi.txt 파일을 생성해주세요.")


def check_requirements():
    """
    필수 요구사항 확인
    """
    missing_requirements = []
    
    # Selenium 확인
    try:
        import selenium
        print(f"✅ Selenium 버전: {selenium.__version__}")
    except ImportError:
        missing_requirements.append("selenium")
    
    # ChromeDriver 확인은 실제 실행 시 확인됨
    
    if missing_requirements:
        print("❌ 누락된 패키지:")
        for req in missing_requirements:
            print(f"   • {req}")
        print("\n설치 명령어:")
        print("pip install selenium")
        return False
    
    return True


def get_timestamp():
    """
    현재 타임스탬프 반환
    
    Returns:
        포맷된 타임스탬프 문자열
    """
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def validate_uddi_format(uddi: str) -> bool:
    """
    UDDI 형식 검증
    
    Args:
        uddi: 검증할 UDDI 문자열
        
    Returns:
        유효한 형식인지 여부
    """
    if not uddi or not isinstance(uddi, str):
        return False
    
    # 기본 형식: uddi:로 시작하고 충분한 길이
    if not uddi.startswith('uddi:'):
        return False
    
    # 최소 길이 확인 (uddi: + UUID + timestamp 형태)
    if len(uddi) < 50:  # 대략적인 최소 길이
        return False
    
    # UUID 패턴과 타임스탬프 포함 확인
    uddi_content = uddi[5:]  # 'uddi:' 제거
    
    # 하이픈과 언더스코어 포함 확인 (UUID와 타임스탬프 구분자)
    if '-' not in uddi_content or '_' not in uddi_content:
        return False
    
    return True


def safe_filename(filename: str) -> str:
    """
    안전한 파일명 생성
    
    Args:
        filename: 원본 파일명
        
    Returns:
        안전한 파일명
    """
    import re
    # 위험한 문자 제거
    safe_name = re.sub(r'[<>:"/\\|?*]', '_', filename)
    return safe_name


def format_file_size(size_bytes: int) -> str:
    """
    파일 크기 포맷팅
    
    Args:
        size_bytes: 바이트 단위 크기
        
    Returns:
        포맷된 크기 문자열
    """
    if size_bytes == 0:
        return "0 B"
    
    size_names = ["B", "KB", "MB", "GB"]
    i = 0
    while size_bytes >= 1024 and i < len(size_names) - 1:
        size_bytes /= 1024.0
        i += 1
    
    return f"{size_bytes:.1f} {size_names[i]}"


def log_system_info():
    """시스템 정보 로깅"""
    import platform
    import sys
    
    logging.info("시스템 정보:")
    logging.info(f"  - 운영체제: {platform.system()} {platform.release()}")
    logging.info(f"  - Python 버전: {sys.version}")
    logging.info(f"  - 작업 디렉토리: {os.getcwd()}")


def cleanup_temp_files():
    """임시 파일 정리"""
    temp_patterns = [
        "*.tmp",
        "chromedriver.log",
        "debug.log"
    ]
    
    import glob
    
    cleaned_files = 0
    for pattern in temp_patterns:
        for file_path in glob.glob(pattern):
            try:
                os.remove(file_path)
                cleaned_files += 1
                logging.info(f"임시 파일 삭제: {file_path}")
            except Exception as e:
                logging.warning(f"임시 파일 삭제 실패 ({file_path}): {e}")
    
    if cleaned_files > 0:
        print(f"🧹 {cleaned_files}개의 임시 파일을 정리했습니다.")


def print_help():
    """도움말 출력"""
    help_text = """
🔧 사용법 안내
═══════════════════════════════════════════════════════════════

📁 1. UDDI 파일 준비
   • 파일명: uddi.txt
   • 형식: 한 줄에 하나씩 UDDI 입력
   • 예시:
     uddi:52e786d0-501c-4784-a05c-ef0b06c95958_202012021116
     uddi:a1b2c3d4-5e6f-7890-abcd-ef1234567890_202301151030
   • 주석: '#'으로 시작하는 줄은 무시됨

🚀 2. 프로그램 실행
   • 명령어: python main.py
   • 자동으로 uddi.txt 파일을 읽어서 처리

🌐 3. 로그인
   • SSO 페이지가 자동으로 열림
   • 브라우저에서 수동으로 로그인
   • 로그인 완료 후 Enter 키 입력

⚡ 4. 자동 처리
   • 모든 UDDI에 대해 자동으로 활용신청 진행
   • 실시간 처리 상황 확인 가능
   • 오류 발생 시 자동으로 다음 항목 처리

📊 5. 결과 확인
   • 처리 완료 후 상세한 결과 리포트 출력
   • 성공/실패 통계 및 실패 사유 제공
   • 로그 파일에 모든 처리 과정 기록

═══════════════════════════════════════════════════════════════

❓ 문제 해결
• Chrome 드라이버 오류: ChromeDriver 최신 버전 설치 필요
• 로그인 실패: 수동 로그인 후 충분한 시간 대기
• 폼 작성 실패: 페이지 구조 변경 가능성, 로그 파일 확인
• 네트워크 오류: 안정적인 인터넷 연결 확인

💡 팁
• 대량 처리 시 네트워크 상태 안정성 확인
• 로그 파일을 통한 상세한 오류 분석 가능
• 브라우저 개발자 도구로 추가 디버깅 가능
"""
    print(help_text)


# 메인 모듈에서 직접 실행된 경우 도움말 출력
if __name__ == "__main__":
    print_help()
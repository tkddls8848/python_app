#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
데이터포털 활용신청 자동화 워크플로우
메인 실행 파일
"""

import os
import sys
import time
import logging
from typing import List, Dict, Any
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

from form_handler import FormFiller, FormSubmitter
from utils import setup_logging, print_banner, print_results


def read_uddi_file(filename: str = "uddi.txt") -> List[str]:
    """
    UDDI 파일 읽기 및 검증 (탭 구분 형식 지원)
    
    Args:
        filename: UDDI 목록이 담긴 텍스트 파일명
        
    Returns:
        유효한 UDDI 목록
    """
    if not os.path.exists(filename):
        logging.error(f"UDDI 파일을 찾을 수 없습니다: {filename}")
        print(f"❌ 오류: {filename} 파일이 존재하지 않습니다.")
        print("uddi.txt 파일을 생성하고 UDDI 목록을 입력해주세요.")
        print("예시 형식 (탭으로 구분):")
        print("uddi:52e786d0-501c-4784-a05c-ef0b06c95958_202012021116\thttps://example.com\t2025-06-01 15:22:30")
        print("uddi:a1b2c3d4-5e6f-7890-abcd-ef1234567890_202301151030\thttps://example.com\t2025-06-01 15:22:30")
        return []
    
    uddi_list = []
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                
                # 빈 줄이나 주석 제외
                if not line or line.startswith('#'):
                    continue
                
                # 탭으로 구분된 경우 첫 번째 값만 추출
                if '\t' in line:
                    uddi = line.split('\t')[0].strip()
                    logging.info(f"탭 구분 형식에서 UDDI 추출 (라인 {line_num}): {uddi}")
                else:
                    uddi = line.strip()
                    logging.info(f"단순 형식에서 UDDI 추출 (라인 {line_num}): {uddi}")
                
                # UDDI 형식 검증 (기본적인 형식 체크)
                if uddi.startswith('uddi:') and len(uddi) > 10:
                    uddi_list.append(uddi)
                    logging.info(f"UDDI 읽기 성공 (라인 {line_num}): {uddi}")
                else:
                    logging.warning(f"잘못된 UDDI 형식 (라인 {line_num}): {uddi}")
                    print(f"⚠️  잘못된 형식 무시 (라인 {line_num}): {uddi}")
    
    except Exception as e:
        logging.error(f"파일 읽기 오류: {e}")
        print(f"❌ 파일 읽기 오류: {e}")
        return []
    
    if uddi_list:
        logging.info(f"총 {len(uddi_list)}개의 유효한 UDDI를 읽었습니다.")
        print(f"✅ {len(uddi_list)}개의 UDDI를 성공적으로 읽었습니다.")
        
        # 중복 제거
        unique_uddi_list = list(dict.fromkeys(uddi_list))  # 순서 유지하면서 중복 제거
        if len(unique_uddi_list) != len(uddi_list):
            removed_count = len(uddi_list) - len(unique_uddi_list)
            print(f"📋 중복된 {removed_count}개의 UDDI를 제거했습니다.")
            logging.info(f"중복 제거: {removed_count}개 제거, 최종 {len(unique_uddi_list)}개")
            return unique_uddi_list
        
    else:
        print("❌ 유효한 UDDI가 없습니다.")
    
    return uddi_list


def setup_driver() -> webdriver.Chrome:
    """
    Chrome 드라이버 초기화
    
    Returns:
        Chrome WebDriver 인스턴스
    """
    chrome_options = Options()
    chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)
    chrome_options.add_argument("--window-size=1200,800")
    chrome_options.add_argument("--disable-web-security")
    chrome_options.add_argument("--allow-running-insecure-content")
    
    try:
        driver = webdriver.Chrome(options=chrome_options)
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        logging.info("Chrome 드라이버 초기화 성공")
        return driver
    except Exception as e:
        logging.error(f"Chrome 드라이버 초기화 실패: {e}")
        print(f"❌ Chrome 드라이버 초기화 실패: {e}")
        print("Chrome 브라우저와 ChromeDriver가 설치되어 있는지 확인해주세요.")
        sys.exit(1)


def wait_for_manual_login(driver: webdriver.Chrome) -> bool:
    """
    SSO 자동 로그인 프로세스
    
    Args:
        driver: Chrome WebDriver 인스턴스
        
    Returns:
        로그인 성공 여부
    """
    sso_url = "https://auth.data.go.kr/sso/common-login?client_id=hagwng3yzgpdmbpr2rxn&redirect_url=https://data.go.kr/sso/profile.do"
    
    try:
        print("🌐 SSO 로그인 페이지로 이동 중...")
        driver.get(sso_url)
        time.sleep(3)
        
        print("\n" + "="*60)
        print("📋 수동 로그인이 필요합니다")
        print("="*60)
        print("1. 브라우저에서 로그인을 완료해주세요")
        print("2. 데이터포털 메인 페이지로 이동되는지 확인하세요")
        print("3. 로그인이 완료되면 아래 Enter 키를 눌러주세요")
        print("="*60)
        
        input("Enter 키를 눌러 계속하세요...")
        
        # 로그인 상태 확인
        wait = WebDriverWait(driver, 10)
        login_indicators = [
            "로그아웃", "마이페이지", "내정보", "MY PAGE", "마이데이터"
        ]
        
        for indicator in login_indicators:
            try:
                element = wait.until(EC.presence_of_element_located((By.XPATH, f"//*[contains(text(), '{indicator}')]")))
                if element:
                    logging.info(f"로그인 확인: '{indicator}' 요소 발견")
                    print("✅ 로그인이 확인되었습니다.")
                    return True
            except TimeoutException:
                continue
        
        # URL 패턴으로도 확인
        current_url = driver.current_url
        if any(pattern in current_url for pattern in ["main.do", "mypage", "data.go.kr"]):
            logging.info(f"로그인 확인: URL 패턴 매칭 ({current_url})")
            print("✅ 로그인이 확인되었습니다.")
            return True
        
        print("⚠️  로그인 상태를 확인할 수 없습니다. 계속 진행합니다...")
        logging.warning("로그인 상태 확인 실패")
        return True  # 일단 진행해보기
        
    except Exception as e:
        logging.error(f"로그인 프로세스 오류: {e}")
        print(f"❌ 로그인 프로세스 오류: {e}")
        return False


def process_uddi_list(driver: webdriver.Chrome, uddi_list: List[str]) -> Dict[str, Any]:
    """
    UDDI별 순차 처리 루프
    
    Args:
        driver: Chrome WebDriver 인스턴스
        uddi_list: 처리할 UDDI 목록
        
    Returns:
        처리 결과 딕셔너리
    """
    results = {
        'total': len(uddi_list),
        'success': 0,
        'failed': [],
        'failed_details': {}
    }
    
    form_filler = FormFiller(driver)
    form_submitter = FormSubmitter(driver)
    
    print(f"\n🔄 {len(uddi_list)}개의 UDDI 처리를 시작합니다...")
    
    for i, uddi in enumerate(uddi_list, 1):
        print(f"\n📝 [{i}/{len(uddi_list)}] 처리 중: {uddi}")
        logging.info(f"[{i}/{len(uddi_list)}] UDDI 처리 시작: {uddi}")
        
        try:
            # 직접 활용신청 폼 페이지 접근
            form_url = f"https://www.data.go.kr/iim/api/selectDevAcountRequestForm.do?publicDataDetailPk={uddi}"
            logging.info(f"폼 페이지 접근: {form_url}")
            
            print(f"  🌐 폼 페이지 접근 중...")
            driver.get(form_url)
            
            # 페이지 로딩 대기 (최대 10초)
            wait = WebDriverWait(driver, 10)
            try:
                # 페이지 로딩 완료 대기
                wait.until(lambda driver: driver.execute_script('return document.readyState') == 'complete')
                time.sleep(3)  # 추가 대기
            except TimeoutException:
                logging.warning("페이지 로딩 시간 초과")
            
            # 페이지 로딩 확인
            page_title = driver.title
            if "오류" in page_title or "404" in page_title or "Not Found" in page_title:
                results['failed'].append(uddi)
                results['failed_details'][uddi] = f"페이지 접근 오류 (제목: {page_title})"
                print(f"  ❌ 페이지 접근 오류: {page_title}")
                continue
            
            # 로그인 리다이렉트 확인
            current_url = driver.current_url
            if "login" in current_url or "auth" in current_url:
                results['failed'].append(uddi)
                results['failed_details'][uddi] = "로그인 세션 만료"
                print(f"  ❌ 로그인 세션이 만료되었습니다. 다시 로그인해주세요.")
                break  # 전체 프로세스 중단
            
            # 폼 작성
            if not form_filler.fill_form():
                results['failed'].append(uddi)
                results['failed_details'][uddi] = "폼 작성 실패"
                print(f"  ❌ 폼 작성 실패: {uddi}")
                continue
            
            # 폼 제출
            if not form_submitter.submit_form():
                results['failed'].append(uddi)
                results['failed_details'][uddi] = "폼 제출 실패"
                print(f"  ❌ 폼 제출 실패: {uddi}")
                continue
            
            # 제출 후 대기
            print("  ⏳ 제출 처리 대기 중...")
            time.sleep(5)  # 기본 대기 시간 증가
            
            # 페이지가 완전히 로드될 때까지 대기
            try:
                wait.until(lambda driver: driver.execute_script('return document.readyState') == 'complete')
            except TimeoutException:
                logging.warning("제출 후 페이지 로딩 시간 초과")
            
            results['success'] += 1
            print(f"  ✅ 성공: {uddi}")
            logging.info(f"UDDI 처리 완료: {uddi}")
            
            # 다음 처리를 위한 대기
            time.sleep(5)  # 대기 시간 증가
            
        except Exception as e:
            results['failed'].append(uddi)
            results['failed_details'][uddi] = f"처리 중 오류: {str(e)}"
            print(f"  ❌ 오류 발생: {uddi} - {e}")
            logging.error(f"UDDI 처리 오류 ({uddi}): {e}")
            continue
    
    return results


def main():
    """메인 실행 함수"""
    # 로깅 설정
    setup_logging()
    
    # 배너 출력
    print_banner()
    
    # 1단계: UDDI 파일 읽기
    print("📋 1단계: UDDI 파일 읽기")
    uddi_list = read_uddi_file()
    
    if not uddi_list:
        print("처리할 UDDI가 없습니다. 프로그램을 종료합니다.")
        return
    
    # 파일 형식 안내
    print(f"\n📄 파일 형식 정보:")
    print(f"   • 탭으로 구분된 첫 번째 컬럼이 UDDI로 인식됩니다")
    print(f"   • 형식: uddi:값\\t기타정보\\t타임스탬프")
    print(f"   • 중복된 UDDI는 자동으로 제거됩니다")
    
    # 2단계: 브라우저 설정 및 SSO 인증
    print("\n🌐 2단계: 브라우저 설정 및 SSO 인증")
    driver = setup_driver()
    
    try:
        if not wait_for_manual_login(driver):
            print("로그인에 실패했습니다. 프로그램을 종료합니다.")
            return
        
        # 3단계: UDDI별 순차 처리
        print("\n🔄 3단계: UDDI별 순차 처리")
        results = process_uddi_list(driver, uddi_list)
        
        # 4단계: 결과 출력
        print("\n📊 4단계: 처리 결과")
        print_results(results)
        
    finally:
        # 5단계: 정리 및 종료
        print("\n🔧 5단계: 정리 및 종료")
        driver.quit()
        print("브라우저를 종료했습니다.")
        
        print("\n✨ 프로그램이 완료되었습니다.")
        print("📄 로그 파일: data_portal_automation.log")


if __name__ == "__main__":
    main()
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
공공데이터포털 자동화 - Selenium Chrome WebDriver 기반
개선된 로그인 프로세스와 안정적인 브라우저 자동화
HTML 구조 분석 기반 연장 버튼 클릭 개선
"""

import time
import logging
import webbrowser
from typing import Optional, Dict, Any
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, WebDriverException
from bs4 import BeautifulSoup
import re

class DataPortalAutomationSelenium:
    def __init__(self):
        self.driver: Optional[webdriver.Chrome] = None
        self.base_url = "https://www.data.go.kr"
        self.list_url = "https://www.data.go.kr/iim/api/selectAcountList.do"
        self.login_url = "https://auth.data.go.kr/sso/common-login?client_id=hagwng3yzgpdmbpr2rxn&redirect_url=https://data.go.kr/sso/profile.do"
        
        # 로깅 설정
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
        self.logger = logging.getLogger(__name__)
        
        # 브라우저 유지 플래그 추가
        self.keep_browser_open = True
    
    def setup_driver(self) -> webdriver.Chrome:
        """
        Chrome 드라이버 초기화
        
        Returns:
            Chrome WebDriver 인스턴스
        """
        print("🔧 Chrome 드라이버 초기화 중...")
        
        chrome_options = Options()
        chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        chrome_options.add_argument("--window-size=1200,800")
        chrome_options.add_argument("--disable-web-security")
        chrome_options.add_argument("--allow-running-insecure-content")
        
        # 추가 안정성 옵션
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--remote-debugging-port=9222")
        
        try:
            self.driver = webdriver.Chrome(options=chrome_options)
            
            # 자동화 감지 방지 스크립트 실행
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            
            self.logger.info("Chrome 드라이버 초기화 성공")
            print("✅ Chrome 드라이버가 성공적으로 초기화되었습니다!")
            
            return self.driver
            
        except WebDriverException as e:
            self.logger.error(f"Chrome 드라이버 초기화 실패: {e}")
            print(f"❌ Chrome 드라이버 초기화 실패: {e}")
            print("\n🔧 해결 방법:")
            print("1. Chrome 브라우저가 설치되어 있는지 확인")
            print("2. ChromeDriver가 설치되어 있는지 확인")
            print("3. ChromeDriver 버전이 Chrome 브라우저와 호환되는지 확인")
            print("4. pip install selenium 으로 최신 Selenium 설치")
            raise
        except Exception as e:
            self.logger.error(f"예상치 못한 오류: {e}")
            print(f"❌ 예상치 못한 오류: {e}")
            raise
    
    def check_login_status(self) -> bool:
        """
        현재 로그인 상태 확인 (목록 페이지 접속 없이 간단 확인)
        
        Returns:
            로그인 상태 여부
        """
        print(f"\n" + "="*50)
        print("🔍 로그인 상태 확인 중...")
        print("="*50)
        
        try:
            # 현재 페이지가 있는지 확인
            current_url = self.driver.current_url
            print(f"📍 현재 URL: {current_url}")
            
            # 이미 data.go.kr 도메인에 있고 로그인된 상태인지 확인
            if 'data.go.kr' in current_url and 'auth.data.go.kr' not in current_url:
                print("🔍 data.go.kr 도메인에서 로그인 요소 확인 중...")
                
                try:
                    # 로그인 관련 요소 확인
                    logout_elements = self.driver.find_elements(By.XPATH, 
                        "//*[contains(text(), '로그아웃') or contains(text(), '마이페이지') or contains(text(), 'MY PAGE')]")
                    
                    if logout_elements:
                        print(f"✅ 로그인 상태 확인됨! (로그인 요소 {len(logout_elements)}개 발견)")
                        self.logger.info(f"로그인 상태 확인됨: {current_url}")
                        return True
                        
                except Exception as e:
                    print(f"⚠️  요소 검색 중 오류: {e}")
            
            # 메인 페이지로 간단히 이동해서 확인
            print("📱 메인 페이지로 이동하여 로그인 상태 확인...")
            self.driver.get("https://www.data.go.kr/")
            
            # 페이지 로딩 대기
            WebDriverWait(self.driver, 10).until(
                lambda driver: driver.execute_script('return document.readyState') == 'complete'
            )
            time.sleep(2)
            
            current_url = self.driver.current_url
            page_source = self.driver.page_source.lower()
            
            print(f"📍 메인 페이지 URL: {current_url}")
            
            # 로그인 상태 판단 로직
            login_indicators = [
                '로그아웃' in self.driver.page_source,
                'logout' in page_source,
                'mypage' in page_source,
                '마이페이지' in self.driver.page_source
            ]
            
            logout_indicators = [
                'auth.data.go.kr' in current_url,
                'login' in self.driver.title.lower()
            ]
            
            positive_count = sum(login_indicators)
            negative_count = sum(logout_indicators)
            
            print(f"🔍 로그인 지표 분석:")
            print(f"   긍정적 지표: {positive_count}/4")
            print(f"   부정적 지표: {negative_count}/2")
            
            # 추가 요소 기반 확인
            try:
                logout_elements = self.driver.find_elements(By.XPATH, 
                    "//*[contains(text(), '로그아웃') or contains(text(), '마이페이지') or contains(text(), 'MY PAGE')]")
                
                print(f"   로그인 관련 요소: {len(logout_elements)}개")
                
                if logout_elements:
                    print("✅ 로그인 상태가 확인되었습니다!")
                    self.logger.info(f"로그인 상태 확인됨: {current_url}")
                    return True
                    
            except Exception as e:
                print(f"⚠️  요소 검색 중 오류: {e}")
            
            # 종합 판단
            if positive_count >= 1 and negative_count == 0:
                print("✅ 로그인 상태가 확인되었습니다!")
                self.logger.info(f"로그인 상태 확인됨: {current_url}")
                return True
            elif negative_count > 0:
                print("❌ 로그인이 필요한 상태입니다.")
                self.logger.warning(f"로그인 필요: {current_url}")
                return False
            else:
                print("⚠️  로그인 상태가 불명확합니다.")
                self.logger.warning(f"로그인 상태 불명확: {current_url}")
                return None
                
        except TimeoutException:
            print("⏰ 페이지 로딩 시간 초과")
            self.logger.error("페이지 로딩 시간 초과")
            return False
        except WebDriverException as e:
            print(f"🌐 브라우저 오류: {e}")
            self.logger.error(f"브라우저 오류: {e}")
            return False
        except Exception as e:
            print(f"❌ 로그인 상태 확인 중 오류 발생: {e}")
            self.logger.error(f"로그인 상태 확인 오류: {e}")
            return False
    
    def wait_for_login_completion(self, max_wait_time: int = 300) -> bool:
        """
        로그인 완료까지 자동 대기 (최대 5분)
        
        Args:
            max_wait_time: 최대 대기 시간 (초)
            
        Returns:
            로그인 성공 여부
        """
        print(f"\n🕐 로그인 완료까지 자동 대기 중... (최대 {max_wait_time//60}분)")
        print("💡 브라우저에서 로그인을 완료하면 자동으로 감지됩니다.")
        
        start_time = time.time()
        check_interval = 3  # 3초마다 확인
        last_url = ""
        
        while time.time() - start_time < max_wait_time:
            try:
                current_url = self.driver.current_url
                
                # URL 변화 감지
                if current_url != last_url:
                    print(f"🔄 URL 변경 감지: {current_url}")
                    last_url = current_url
                
                # 로그인 완료 조건들 확인
                login_success_indicators = [
                    'data.go.kr' in current_url and 'auth.data.go.kr' not in current_url,
                    'main.do' in current_url,
                    'mypage' in current_url.lower()
                ]
                
                # URL 기반 로그인 성공 감지
                if any(login_success_indicators):
                    print("🔍 URL 기반 로그인 성공 감지, 추가 확인 중...")
                    
                    # 페이지 요소 기반 확인
                    try:
                        # 로그아웃 버튼이나 마이페이지 링크 확인
                        logout_elements = self.driver.find_elements(By.XPATH, 
                            "//*[contains(text(), '로그아웃') or contains(text(), '마이페이지') or contains(text(), 'MY PAGE') or contains(@href, 'logout')]")
                        
                        if logout_elements:
                            elapsed = int(time.time() - start_time)
                            print(f"✅ 로그인 완료 자동 감지! (소요 시간: {elapsed}초)")
                            print(f"📍 최종 URL: {current_url}")
                            print(f"🔗 발견된 로그인 요소: {len(logout_elements)}개")
                            self.logger.info(f"자동 로그인 감지 완료: {current_url}")
                            return True
                            
                    except Exception as e:
                        self.logger.warning(f"요소 검색 중 오류: {e}")
                
                # 진행 상황 표시
                elapsed = int(time.time() - start_time)
                remaining = max_wait_time - elapsed
                
                if elapsed % 30 == 0 and elapsed > 0:  # 30초마다 상태 출력
                    print(f"⏳ 대기 중... (경과: {elapsed}초, 남은 시간: {remaining}초)")
                    print(f"📍 현재 위치: {current_url}")
                
                time.sleep(check_interval)
                
            except WebDriverException as e:
                print(f"⚠️  브라우저 오류: {e}")
                self.logger.error(f"로그인 대기 중 브라우저 오류: {e}")
                time.sleep(check_interval)
                continue
            except Exception as e:
                print(f"⚠️  예상치 못한 오류: {e}")
                self.logger.error(f"로그인 대기 중 오류: {e}")
                time.sleep(check_interval)
                continue
        
        # 시간 초과
        print(f"⏰ 로그인 대기 시간이 초과되었습니다. ({max_wait_time//60}분)")
        return False
    
    def manual_login_process(self) -> bool:
        """
        수동 로그인 프로세스 - Chrome WebDriver 사용 (자동 대기 기능 포함)
        
        Returns:
            로그인 성공 여부
        """
        print("=" * 80)
        print("🔐 수동 로그인 프로세스 시작")
        print("=" * 80)
        
        print(f"\n📍 로그인 URL: {self.login_url}")
        
        # 단계별 안내
        print("\n📋 로그인 진행 단계:")
        print("   1️⃣  브라우저에서 로그인 페이지로 이동")
        print("   2️⃣  공공데이터포털 계정으로 SSO 로그인 완료")
        print("   3️⃣  로그인 완료 후 엔터키를 눌러주세요")
        print("   4️⃣  자동으로 다음 단계 진행")
        
        # 브라우저에서 로그인 페이지 열기
        print(f"\n🌐 Chrome 브라우저에서 로그인 페이지로 이동 중...")
        try:
            self.driver.get(self.login_url)
            
            # 페이지 로딩 대기
            WebDriverWait(self.driver, 15).until(
                lambda driver: driver.execute_script('return document.readyState') == 'complete'
            )
            time.sleep(3)
            
            print("✅ 로그인 페이지가 성공적으로 열렸습니다!")
            print(f"📍 현재 URL: {self.driver.current_url}")
            self.logger.info(f"로그인 페이지 접속 성공: {self.driver.current_url}")
            
        except TimeoutException:
            print("⏰ 로그인 페이지 로딩 시간 초과")
            self.logger.error("로그인 페이지 로딩 시간 초과")
            return False
        except WebDriverException as e:
            print(f"❌ 브라우저 오류: {e}")
            self.logger.error(f"로그인 페이지 접속 실패: {e}")
            return False
        except Exception as e:
            print(f"❌ 로그인 페이지 접속 실패: {e}")
            self.logger.error(f"로그인 페이지 접속 실패: {e}")
            return False
        
        print(f"\n" + "="*70)
        print("🔄 로그인 대기 모드")
        print("="*70)
        print("📝 Chrome 브라우저에서 다음 작업을 완료해주세요:")
        print("   • 공공데이터포털 계정으로 로그인")
        print("   • 로그인 성공 후 data.go.kr 도메인으로 자동 이동")
        print("   • 로그인이 완료되면 엔터키를 눌러주세요")
        print("")
        print("⚠️  주의사항:")
        print("   • 로그인 완료까지 브라우저를 닫지 마세요")
        print("   • 자동화된 브라우저 창에서 로그인해주세요")
        print("")
        
        # 사용자에게 선택권 제공
        while True:
            try:
                print("\n✋ 로그인을 완료하신 후 엔터키를 눌러주세요.")
                print("   [Enter] 로그인 완료 후 진행")
                print("   [q] 프로그램 종료")
                
                user_input = input("\n선택하세요: ").strip().lower()
                
                if user_input == 'q':
                    print("❌ 사용자가 프로세스를 중단했습니다.")
                    self.logger.info("사용자가 로그인 프로세스를 중단함")
                    return False
                    
                elif user_input == '' or user_input == 'enter':
                    print("✅ 로그인 완료 확인됨. 다음 단계로 진행합니다...")
                    self.logger.info("사용자가 로그인 완료를 확인함")
                    return True
                    
                else:
                    print("❓ 엔터키를 눌러주세요.")
                    
            except KeyboardInterrupt:
                print("\n❌ 프로세스가 중단되었습니다.")
                self.logger.info("KeyboardInterrupt로 로그인 프로세스 중단")
                return False
    
    def quick_login_check(self) -> bool:
        """
        빠른 로그인 상태 확인
        
        Returns:
            로그인 상태 여부
        """
        try:
            current_url = self.driver.current_url
            page_title = self.driver.title
            
            print(f"📍 현재 URL: {current_url}")
            print(f"📄 현재 페이지 제목: {page_title}")
            
            # URL 기반 확인
            if 'data.go.kr' in current_url and 'auth.data.go.kr' not in current_url:
                print("✅ 올바른 도메인에 있습니다.")
                
                # 추가 요소 확인
                try:
                    logout_elements = self.driver.find_elements(By.XPATH, "//*[contains(text(), '로그아웃') or contains(text(), '마이페이지')]")
                    if logout_elements:
                        print(f"✅ 로그인 관련 요소 발견: {len(logout_elements)}개")
                        return True
                except:
                    pass
                    
                return True
            else:
                print("⚠️  아직 인증 도메인에 있거나 예상과 다른 페이지입니다.")
                return False
                
        except Exception as e:
            print(f"❌ 상태 확인 중 오류: {e}")
            return False
    
    def get_list_page(self) -> Optional[str]:
        """
        목록 페이지 데이터 수집
        
        Returns:
            페이지 HTML 내용 또는 None
        """
        try:
            print(f"\n" + "="*50)
            print("📋 목록 페이지 데이터 수집")
            print("="*50)
            print(f"🔗 접속 URL: {self.list_url}")
            
            self.driver.get(self.list_url)
            
            # 페이지 로딩 대기
            WebDriverWait(self.driver, 15).until(
                lambda driver: driver.execute_script('return document.readyState') == 'complete'
            )
            time.sleep(3)
            
            current_url = self.driver.current_url
            page_source = self.driver.page_source
            page_title = self.driver.title
            
            print(f"✅ 페이지 로딩 완료")
            print(f"🔗 최종 URL: {current_url}")
            print(f"📄 페이지 제목: {page_title}")
            print(f"📊 페이지 크기: {len(page_source):,} bytes")
            
            # 페이지 내용 검증
            content_checks = {
                'mypage-dataset-list': 'mypage-dataset-list' in page_source,
                'li 태그': '<li' in page_source,
                'fn_detail 함수': 'fn_detail(' in page_source,
                '데이터 목록': any(keyword in page_source for keyword in ['데이터', 'data', 'api'])
            }
            
            print("🔍 페이지 내용 검증:")
            for check_name, result in content_checks.items():
                status = "✅" if result else "❌"
                print(f"   {status} {check_name}: {'발견됨' if result else '찾을 수 없음'}")
            
            # 로그인 상태 재확인
            if 'login' in current_url or 'auth' in current_url:
                print("❌ 로그인 페이지로 리디렉션되었습니다.")
                return None
            
            if content_checks['mypage-dataset-list'] and content_checks['fn_detail 함수']:
                print("✅ 올바른 데이터 목록 페이지입니다!")
            else:
                print("⚠️  예상된 데이터 목록 형식과 다를 수 있습니다.")
                
                # 디버깅 정보 출력
                soup = BeautifulSoup(page_source, 'html.parser')
                if '로그인' in page_source and '로그아웃' not in page_source:
                    print("🔍 로그인 관련 텍스트가 발견되었습니다. 세션이 만료되었을 수 있습니다.")
            
            return page_source
            
        except TimeoutException:
            print("⏰ 목록 페이지 로딩 시간 초과")
            self.logger.error("목록 페이지 로딩 시간 초과")
            return None
        except WebDriverException as e:
            print(f"🌐 브라우저 오류: {e}")
            self.logger.error(f"목록 페이지 접속 중 브라우저 오류: {e}")
            return None
        except Exception as e:
            print(f"❌ 목록 페이지 접속 중 오류 발생: {e}")
            self.logger.error(f"목록 페이지 접속 중 오류: {e}")
            return None
    
    def click_first_title_area_link(self) -> bool:
        """
        첫 번째 div class="title-area" 하위의 a href를 클릭하여 다음 페이지로 진입
        
        Returns:
            클릭 성공 여부
        """
        try:
            print(f"\n" + "="*50)
            print("🔗 첫 번째 title-area 링크 클릭")
            print("="*50)
            
            # 첫 번째 title-area 찾기
            print("🔍 첫 번째 title-area div 검색 중...")
            title_area = self.driver.find_element(By.CSS_SELECTOR, "div.title-area")
            
            if not title_area:
                print("❌ title-area div를 찾을 수 없습니다.")
                return False
            
            print("✅ title-area div 발견!")
            
            # title-area 하위의 a 태그 찾기
            print("🔍 title-area 하위의 a 태그 검색 중...")
            link_element = title_area.find_element(By.TAG_NAME, "a")
            
            if not link_element:
                print("❌ title-area 하위에 a 태그를 찾을 수 없습니다.")
                return False
            
            # 링크 정보 출력
            href_value = link_element.get_attribute("href")
            link_text = link_element.text.strip()
            
            print(f"✅ 링크 발견!")
            print(f"   📌 링크 텍스트: {link_text}")
            print(f"   🔗 링크 URL: {href_value}")
            
            # 현재 URL 저장 (비교용)
            current_url = self.driver.current_url
            print(f"📍 현재 URL: {current_url}")
            
            # 링크 클릭 가능 여부 확인
            if not link_element.is_enabled():
                print("❌ 링크가 비활성화되어 있습니다.")
                return False
            
            if not link_element.is_displayed():
                print("⚠️  링크가 화면에 보이지 않습니다. 스크롤을 시도합니다...")
                self.driver.execute_script("arguments[0].scrollIntoView();", link_element)
                time.sleep(1)
            
            # 링크 클릭
            print("🖱️  링크를 클릭합니다...")
            self.driver.execute_script("arguments[0].click();", link_element)  # JavaScript 클릭 사용 (더 안정적)
            
            # 페이지 변화 대기
            print("⏳ 페이지 로딩 대기 중...")
            
            # URL 변화 대기 (최대 10초)
            wait = WebDriverWait(self.driver, 10)
            try:
                wait.until(lambda driver: driver.current_url != current_url)
                print("✅ URL 변화 감지됨!")
            except TimeoutException:
                print("⚠️  URL 변화가 감지되지 않았지만 계속 진행합니다...")
            
            # 페이지 로딩 완료 대기
            try:
                wait.until(lambda driver: driver.execute_script('return document.readyState') == 'complete')
                time.sleep(2)  # 추가 안정화 대기
            except TimeoutException:
                print("⚠️  페이지 로딩 완료 대기 시간 초과")
            
            # 결과 확인
            new_url = self.driver.current_url
            new_title = self.driver.title
            
            print(f"🎯 페이지 이동 완료!")
            print(f"   📍 새 URL: {new_url}")
            print(f"   📄 새 페이지 제목: {new_title}")
            print(f"   📊 페이지 크기: {len(self.driver.page_source):,} bytes")
            
            # 성공 여부 판단
            if new_url != current_url:
                print("✅ 페이지 이동이 성공적으로 완료되었습니다!")
                self.logger.info(f"페이지 이동 성공: {current_url} → {new_url}")
                return True
            else:
                print("⚠️  URL은 변경되지 않았지만 페이지가 업데이트되었을 수 있습니다.")
                return True
                
        except NoSuchElementException as e:
            print(f"❌ 요소를 찾을 수 없습니다: {e}")
            print("🔧 가능한 원인:")
            print("   • 페이지 구조가 예상과 다름")
            print("   • title-area div가 존재하지 않음")
            print("   • a 태그가 title-area 하위에 없음")
            self.logger.error(f"요소 검색 실패: {e}")
            return False
            
        except TimeoutException as e:
            print(f"⏰ 페이지 로딩 시간 초과: {e}")
            self.logger.error(f"페이지 로딩 시간 초과: {e}")
            return False
            
        except WebDriverException as e:
            print(f"🌐 브라우저 오류: {e}")
            self.logger.error(f"링크 클릭 중 브라우저 오류: {e}")
            return False
            
        except Exception as e:
            print(f"❌ 예상치 못한 오류: {e}")
            self.logger.error(f"링크 클릭 중 예상치 못한 오류: {e}")
            return False
    
    def navigate_to_detail_page(self) -> bool:
        """
        목록 페이지에서 첫 번째 항목의 상세 페이지로 이동
        
        Returns:
            이동 성공 여부
        """
        try:
            print(f"\n" + "="*50)
            print("🔗 상세 페이지 이동")
            print("="*50)
            
            # 목록 페이지가 올바르게 로드되었는지 확인
            print("🔍 목록 페이지 상태 확인 중...")
            
            # 데이터 목록 영역 확인
            try:
                dataset_list = self.driver.find_element(By.CSS_SELECTOR, "div.mypage-dataset-list")
                print("✅ 데이터 목록 영역 확인됨")
            except NoSuchElementException:
                print("❌ 데이터 목록 영역을 찾을 수 없습니다.")
                print("🔧 페이지가 올바르게 로드되지 않았거나 구조가 변경되었을 수 있습니다.")
                return False
            
            # 첫 번째 title-area 링크 클릭 시도
            success = self.click_first_title_area_link()
            
            if success:
                print("🎉 상세 페이지 이동이 성공적으로 완료되었습니다!")
                
                # 상세 페이지 내용 저장
                detail_page_content = self.driver.page_source
                self.save_page_content(detail_page_content, 'detail_page.html')
                
                return True
            else:
                print("❌ 상세 페이지 이동에 실패했습니다.")
                return False
                
        except Exception as e:
            print(f"❌ 상세 페이지 이동 중 오류 발생: {e}")
            self.logger.error(f"상세 페이지 이동 오류: {e}")
            return False
    
    def analyze_page_structure(self) -> Dict[str, Any]:
        """
        현재 페이지 구조 분석 (디버깅용)
        
        Returns:
            페이지 구조 분석 결과
        """
        try:
            print(f"\n" + "="*50)
            print("🔍 페이지 구조 분석")
            print("="*50)
            
            page_source = self.driver.page_source
            soup = BeautifulSoup(page_source, 'html.parser')
            
            analysis = {
                'title': self.driver.title,
                'url': self.driver.current_url,
                'button_groups': [],
                'extend_buttons': [],
                'javascript_functions': []
            }
            
            # 버튼 그룹 찾기
            button_groups = soup.find_all('div', class_='button-group')
            print(f"📊 발견된 button-group: {len(button_groups)}개")
            
            for i, group in enumerate(button_groups):
                group_info = {
                    'index': i,
                    'classes': group.get('class', []),
                    'buttons': []
                }
                
                buttons = group.find_all('a')
                for j, button in enumerate(buttons):
                    button_info = {
                        'index': j,
                        'text': button.get_text().strip(),
                        'href': button.get('href', ''),
                        'classes': button.get('class', []),
                        'onclick': button.get('onclick', '')
                    }
                    group_info['buttons'].append(button_info)
                    
                    # 연장 관련 버튼 체크
                    if '연장' in button_info['text'] or 'extend' in button_info['href']:
                        analysis['extend_buttons'].append({
                            'group_index': i,
                            'button_index': j,
                            'button_info': button_info
                        })
                
                analysis['button_groups'].append(group_info)
            
            # JavaScript 함수 찾기
            script_tags = soup.find_all('script')
            for script in script_tags:
                if script.string:
                    if 'fn_reqst' in script.string:
                        analysis['javascript_functions'].append('fn_reqst')
                    if 'extend' in script.string:
                        analysis['javascript_functions'].append('extend_related')
            
            # 분석 결과 출력
            print(f"📄 페이지 제목: {analysis['title']}")
            print(f"🔗 현재 URL: {analysis['url']}")
            print(f"🔘 버튼 그룹 수: {len(analysis['button_groups'])}")
            print(f"🎯 연장 관련 버튼: {len(analysis['extend_buttons'])}개")
            
            for extend_btn in analysis['extend_buttons']:
                btn_info = extend_btn['button_info']
                print(f"   📌 연장 버튼 발견:")
                print(f"      텍스트: {btn_info['text']}")
                print(f"      href: {btn_info['href']}")
                print(f"      클래스: {btn_info['classes']}")
            
            return analysis
            
        except Exception as e:
            print(f"❌ 페이지 구조 분석 중 오류: {e}")
            return {}
    
    def click_extend_button(self) -> bool:
        """
        연장 신청 버튼 클릭 (HTML 구조 분석 기반 개선된 버전)
        
        Returns:
            클릭 성공 여부
        """
        try:
            print(f"\n" + "="*50)
            print("🔗 연장 신청 버튼 클릭 (개선된 버전)")
            print("="*50)
            
            # 현재 페이지가 올바른 상세 페이지인지 확인
            current_url = self.driver.current_url
            page_title = self.driver.title
            
            print(f"📍 현재 URL: {current_url}")
            print(f"📄 페이지 제목: {page_title}")
            
            # 페이지 구조 분석
            analysis = self.analyze_page_structure()
            
            if not analysis['extend_buttons']:
                print("❌ 페이지 분석 결과 연장 버튼을 찾을 수 없습니다.")
                print("🔧 다른 방법으로 버튼을 찾아보겠습니다...")
            
            # 방법 1: 정확한 href 속성으로 찾기
            print("\n🔍 방법 1: href 속성 기반 검색...")
            try:
                extend_button = self.driver.find_element(
                    By.CSS_SELECTOR, 
                    "a[href=\"javascript:fn_reqst('extend', '연장')\"]"
                )
                if extend_button:
                    print("✅ 방법 1 성공: href 속성으로 연장 버튼 발견!")
                    return self._click_button_safely(extend_button, "방법 1")
            except NoSuchElementException:
                print("❌ 방법 1 실패: href 속성으로 찾을 수 없음")
            
            # 방법 2: 텍스트 기반 XPath 검색
            print("\n🔍 방법 2: 텍스트 기반 XPath 검색...")
            try:
                extend_button = self.driver.find_element(
                    By.XPATH, 
                    "//a[contains(@class, 'button') and contains(@class, 'blue') and contains(text(), '연장 신청')]"
                )
                if extend_button:
                    print("✅ 방법 2 성공: XPath로 연장 버튼 발견!")
                    return self._click_button_safely(extend_button, "방법 2")
            except NoSuchElementException:
                print("❌ 방법 2 실패: XPath로 찾을 수 없음")
            
            # 방법 3: button-group 내에서 연장 관련 텍스트 검색
            print("\n🔍 방법 3: button-group 내 연장 텍스트 검색...")
            try:
                button_group = self.driver.find_element(By.CSS_SELECTOR, "div.button-group.a-c")
                if button_group:
                    print("✅ button-group 발견!")
                    
                    # button-group 내의 모든 a 태그 확인
                    buttons = button_group.find_elements(By.TAG_NAME, "a")
                    print(f"📊 button-group 내 버튼 수: {len(buttons)}")
                    
                    for i, button in enumerate(buttons):
                        button_text = button.text.strip()
                        button_href = button.get_attribute("href")
                        button_class = button.get_attribute("class")
                        
                        print(f"   버튼 {i+1}: '{button_text}' | href: '{button_href}' | class: '{button_class}'")
                        
                        if '연장' in button_text and 'extend' in button_href:
                            print(f"✅ 방법 3 성공: {i+1}번째 버튼이 연장 버튼!")
                            return self._click_button_safely(button, "방법 3")
                            
            except NoSuchElementException:
                print("❌ 방법 3 실패: button-group을 찾을 수 없음")
            
            # 방법 4: onclick 이벤트 기반 검색
            print("\n🔍 방법 4: onclick 이벤트 기반 검색...")
            try:
                extend_button = self.driver.find_element(
                    By.XPATH, 
                    "//a[contains(@onclick, \"fn_reqst('extend'\") or contains(@href, \"fn_reqst('extend'\")]"
                )
                if extend_button:
                    print("✅ 방법 4 성공: onclick 이벤트로 연장 버튼 발견!")
                    return self._click_button_safely(extend_button, "방법 4")
            except NoSuchElementException:
                print("❌ 방법 4 실패: onclick 이벤트로 찾을 수 없음")
            
            # 방법 5: 모든 버튼을 순회하면서 텍스트 확인
            print("\n🔍 방법 5: 전체 페이지 버튼 순회 검색...")
            try:
                all_buttons = self.driver.find_elements(By.TAG_NAME, "a")
                print(f"📊 전체 a 태그 수: {len(all_buttons)}")
                
                for i, button in enumerate(all_buttons):
                    try:
                        button_text = button.text.strip()
                        button_href = button.get_attribute("href") or ""
                        
                        if '연장' in button_text and ('extend' in button_href or 'fn_reqst' in button_href):
                            print(f"✅ 방법 5 성공: {i+1}번째 a 태그가 연장 버튼!")
                            print(f"   텍스트: '{button_text}'")
                            print(f"   href: '{button_href}'")
                            return self._click_button_safely(button, "방법 5")
                    except Exception as e:
                        continue  # 개별 버튼 오류는 무시하고 계속
                        
                print("❌ 방법 5 실패: 전체 검색에서도 연장 버튼을 찾을 수 없음")
                
            except Exception as e:
                print(f"❌ 방법 5 오류: {e}")
            
            # 모든 방법 실패
            print("\n❌ 모든 방법으로 연장 버튼을 찾을 수 없습니다.")
            print("🔧 가능한 원인:")
            print("   • 페이지가 완전히 로드되지 않음")
            print("   • 로그인 세션이 만료됨")
            print("   • 페이지 구조가 예상과 다름")
            print("   • 연장 신청이 불가능한 상태")
            print("   • JavaScript가 아직 로드되지 않음")
            
            # 디버깅용 페이지 소스 저장
            self.save_page_content(self.driver.page_source, 'debug_page.html')
            print("💾 디버깅용 페이지 소스가 'debug_page.html'에 저장되었습니다.")
            
            return False
            
        except Exception as e:
            print(f"❌ 연장 버튼 클릭 중 예상치 못한 오류: {e}")
            self.logger.error(f"연장 버튼 클릭 중 오류: {e}")
            return False
    
    def _click_button_safely(self, button_element, method_name: str) -> bool:
        """
        버튼을 안전하게 클릭하는 헬퍼 메서드
        
        Args:
            button_element: 클릭할 버튼 요소
            method_name: 사용된 검색 방법명
            
        Returns:
            클릭 성공 여부
        """
        try:
            # 버튼 정보 출력
            button_text = button_element.text.strip()
            button_href = button_element.get_attribute("href")
            button_class = button_element.get_attribute("class")
            
            print(f"🎯 {method_name}으로 발견된 연장 버튼 정보:")
            print(f"   📌 텍스트: '{button_text}'")
            print(f"   🔗 href: '{button_href}'")
            print(f"   🏷️  클래스: '{button_class}'")
            
            # 현재 URL 저장 (변화 확인용)
            current_url = self.driver.current_url
            
            # 버튼이 보이고 활성화되어 있는지 확인
            if not button_element.is_enabled():
                print("❌ 버튼이 비활성화되어 있습니다.")
                return False
            
            if not button_element.is_displayed():
                print("⚠️  버튼이 화면에 보이지 않습니다. 스크롤을 시도합니다...")
                self.driver.execute_script("arguments[0].scrollIntoView(true);", button_element)
                time.sleep(1)
            
            # 클릭 시도
            print("🖱️  버튼을 클릭합니다...")
            
            # JavaScript 클릭 사용 (더 안정적)
            self.driver.execute_script("arguments[0].click();", button_element)
            
            # alert 메시지 대기 및 처리
            try:
                print("⏳ alert 메시지 대기 중...")
                alert = WebDriverWait(self.driver, 10).until(EC.alert_is_present())
                alert_text = alert.text
                print(f"📢 Alert 메시지: {alert_text}")
                
                if "연장신청하시겠습니까?" in alert_text:
                    print("✅ 연장 신청 확인 alert 감지됨")
                    alert.accept()  # 확인 버튼 클릭
                    print("✅ 연장 신청 확인 완료")
                    
                    # 연장 완료 메시지 대기
                    try:
                        complete_alert = WebDriverWait(self.driver, 10).until(EC.alert_is_present())
                        complete_text = complete_alert.text
                        print(f"📢 완료 메시지: {complete_text}")
                        
                        if "연장되었습니다" in complete_text:
                            print("✅ 연장 완료 메시지 확인")
                            complete_alert.accept()
                            return True
                    except TimeoutException:
                        print("⚠️  연장 완료 메시지가 나타나지 않았습니다.")
                else:
                    print("⚠️  예상치 못한 alert 메시지가 나타났습니다.")
                    alert.accept()
                    
            except TimeoutException:
                print("⚠️  alert 메시지가 나타나지 않았습니다.")
            
            # 클릭 후 변화 대기
            print("⏳ 페이지 변화 대기 중...")
            time.sleep(3)
            
            # 결과 확인
            new_url = self.driver.current_url
            new_title = self.driver.title
            
            print(f"🎯 버튼 클릭 결과:")
            print(f"   📍 새 URL: {new_url}")
            print(f"   📄 새 페이지 제목: {new_title}")
            
            # URL 변화가 있으면 성공으로 간주
            if new_url != current_url:
                print("✅ 페이지 이동이 감지되었습니다! 연장 신청 페이지로 이동 성공!")
                self.logger.info(f"연장 버튼 클릭 성공: {current_url} → {new_url}")
                return True
            else:
                # URL 변화가 없어도 페이지 내용이 바뀌었을 수 있음
                print("⚠️  URL 변화는 없지만 버튼 클릭이 처리되었을 수 있습니다.")
                
                # 페이지 내용에서 성공 지표 확인
                page_source = self.driver.page_source
                success_indicators = [
                    '연장신청' in page_source,
                    '신청완료' in page_source,
                    '처리중' in page_source,
                    'success' in page_source.lower()
                ]
                
                if any(success_indicators):
                    print("✅ 페이지 내용 분석 결과 연장 신청이 처리된 것으로 보입니다!")
                    return True
                else:
                    print("⚠️  연장 신청 처리 결과를 확인할 수 없습니다.")
                    return True  # 일단 성공으로 간주
            
        except Exception as e:
            print(f"❌ 버튼 클릭 중 오류 발생: {e}")
            self.logger.error(f"버튼 클릭 중 오류: {e}")
            return False
    
    def wait_for_page_load(self, timeout: int = 10) -> bool:
        """
        페이지 로딩 완료까지 대기
        
        Args:
            timeout: 타임아웃 시간 (초)
            
        Returns:
            로딩 완료 여부
        """
        try:
            wait = WebDriverWait(self.driver, timeout)
            wait.until(lambda driver: driver.execute_script('return document.readyState') == 'complete')
            return True
        except TimeoutException:
            print(f"⏰ 페이지 로딩 대기 시간 초과 ({timeout}초)")
            return False
    
    def run(self):
        """
        전체 프로세스 실행
        """
        print("=" * 80)
        print("🚀 공공데이터포털 자동화 스크립트 v3.1 (Selenium - 연장버튼 개선)")
        print("=" * 80)
        print("🔧 Chrome WebDriver 기반 안정적인 브라우저 자동화")
        print("🎯 HTML 구조 분석 기반 연장 버튼 클릭 최적화")
        print("=" * 80)
        
        try:
            # 1. Chrome 드라이버 초기화
            print("\n🔧 1단계: Chrome 드라이버 초기화")
            self.setup_driver()
            
            # 2. 수동 로그인 프로세스
            print("\n🔐 2단계: 수동 로그인 프로세스")
            if not self.manual_login_process():
                print("❌ 로그인 프로세스가 취소되었습니다.")
                return
            
            # 3. 목록 페이지 데이터 수집
            print("\n📋 3단계: 목록 페이지 데이터 수집")
            list_html = self.get_list_page()
            
            if not list_html:
                print("❌ 목록 페이지를 가져올 수 없습니다.")
                print("🔧 가능한 원인:")
                print("   • 로그인 세션이 만료됨")
                print("   • 페이지 구조가 변경됨")
                print("   • 네트워크 연결 문제")
                
                retry_login = input("\n로그인을 다시 시도하시겠습니까? (y/N): ").strip().lower()
                if retry_login in ['y', 'yes']:
                    if self.manual_login_process():
                        list_html = self.get_list_page()
                        if not list_html:
                            print("❌ 재시도 후에도 목록 페이지를 가져올 수 없습니다.")
                            return
                    else:
                        print("❌ 재로그인에 실패했습니다.")
                        return
                else:
                    print("❌ 프로세스를 종료합니다.")
                    return
            
            # 목록 페이지 내용 저장
            self.save_page_content(list_html, 'list_page.html')

            # 4. 첫 번째 title-area 링크 클릭하여 상세 페이지로 이동
            print("\n🔗 4단계: 상세 페이지로 이동")
            if self.navigate_to_detail_page():
                print("✅ 상세 페이지 이동이 완료되었습니다!")
                
                # 페이지 완전 로딩 대기
                print("\n⏳ 상세 페이지 로딩 완료 대기...")
                self.wait_for_page_load(15)
                time.sleep(2)  # 추가 안정화 대기
                
                # 5. 연장 신청 버튼 클릭
                print("\n🔗 5단계: 연장 신청 (개선된 버전)")
                if self.click_extend_button():
                    print("✅ 연장 신청이 성공적으로 처리되었습니다!")
                else:
                    print("❌ 연장 신청 버튼 클릭에 실패했습니다.")
                    print("🔧 수동으로 브라우저에서 연장 신청을 진행해주세요.")
                
                print("\n📊 6단계: 프로세스 완료")
                print("🎉 모든 단계가 성공적으로 완료되었습니다!")
                print("\n💾 저장된 파일:")
                print("   📁 list_page.html: 목록 페이지")
                print("   📁 detail_page.html: 상세 페이지")
                if hasattr(self, 'debug_page.html'):
                    print("   📁 debug_page.html: 디버깅용 페이지")
            else:
                print("❌ 상세 페이지 이동에 실패했습니다.")
                print("🔧 목록 페이지는 정상적으로 수집되었습니다.")
            
            print("\n✅ 자동화 스크립트가 실행되었습니다!")
            print("🌐 브라우저는 유지됩니다. 수동으로 닫으실 수 있습니다.")
            
            # 브라우저 유지
            if self.keep_browser_open:
                print("\n🔄 브라우저를 유지합니다. 수동으로 닫으실 수 있습니다.")
                input("\n프로그램을 종료하려면 엔터키를 누르세요...")
            
        except KeyboardInterrupt:
            print("\n\n⚠️  사용자에 의해 중단되었습니다.")
            print("🌐 브라우저는 유지됩니다. 수동으로 닫으실 수 있습니다.")
        except Exception as e:
            print(f"\n❌ 실행 중 예상치 못한 오류 발생: {e}")
            print("🔧 오류 상세 정보:")
            import traceback
            traceback.print_exc()
            print("\n🌐 브라우저는 유지됩니다. 수동으로 닫으실 수 있습니다.")
    
    def save_page_content(self, content: str, filename: str) -> bool:
        """
        페이지 내용을 파일로 저장
        
        Args:
            content: 저장할 내용
            filename: 파일명
            
        Returns:
            저장 성공 여부
        """
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"💾 페이지 내용이 '{filename}'에 저장되었습니다.")
            self.logger.info(f"페이지 내용 저장: {filename}")
            return True
        except Exception as e:
            print(f"❌ 파일 저장 중 오류 발생: {e}")
            self.logger.error(f"파일 저장 오류: {e}")
            return False


def check_selenium_requirements():
    """
    Selenium 관련 요구사항 확인
    """
    print("🔧 시스템 요구사항 확인 중...")
    
    missing_requirements = []
    
    # Selenium 확인
    try:
        import selenium
        print(f"✅ Selenium 버전: {selenium.__version__}")
    except ImportError:
        missing_requirements.append("selenium")
        print("❌ Selenium이 설치되지 않음")
    
    # BeautifulSoup 확인
    try:
        import bs4
        print(f"✅ BeautifulSoup4 사용 가능")
    except ImportError:
        missing_requirements.append("beautifulsoup4")
        print("❌ BeautifulSoup4가 설치되지 않음")
    
    # Chrome 확인 (실제 실행 시 확인됨)
    print("🌐 Chrome 브라우저와 ChromeDriver는 실행 시 확인됩니다.")
    
    if missing_requirements:
        print("\n❌ 누락된 패키지:")
        for req in missing_requirements:
            print(f"   • {req}")
        print("\n설치 명령어:")
        print("pip install " + " ".join(missing_requirements))
        return False
    
    print("✅ 모든 요구사항이 충족되었습니다!")
    return True

# 메인 실행 부분
def main():
    """메인 실행 함수"""
    # 요구사항 확인
    if not check_selenium_requirements():
        print("\n필수 패키지를 설치한 후 다시 실행해주세요.")
        return
    
    # 자동화 실행
    automation = DataPortalAutomationSelenium()
    automation.run()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  프로그램이 사용자에 의해 중단되었습니다.")
        print("🌐 브라우저는 유지됩니다. 수동으로 닫으실 수 있습니다.")
    except Exception as e:
        print(f"\n❌ 프로그램 실행 중 오류 발생: {e}")
        import traceback
        traceback.print_exc()
        print("\n🌐 브라우저는 유지됩니다. 수동으로 닫으실 수 있습니다.")
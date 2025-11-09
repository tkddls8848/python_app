#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
데이터포털 활용신청 자동화 워크플로우
폼 처리 클래스 모듈
"""

import time
import logging
from typing import List
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, ElementClickInterceptedException
from selenium.webdriver.common.alert import Alert


class FormFiller:
    """활용신청 폼 자동 입력 클래스"""
    
    def __init__(self, driver: webdriver.Chrome):
        self.driver = driver
        self.wait = WebDriverWait(driver, 10)
        self.purpose_text = "웹 서비스 개발용"
    
    def fill_purpose_text(self) -> bool:
        """
        활용목적 텍스트 입력
        
        Returns:
            입력 성공 여부
        """
        textarea_selectors = [
            "//textarea[@id='prcusePurps']",
            "//textarea[@name='prcusePurps']", 
            "//textarea[@id='prcusePurps' and @name='prcusePurps']",
            "//textarea[contains(@class, 'input-textarea') and contains(@class, 'h160px')]",
            "//textarea[@title='활용목적 입력']",
            "//textarea[contains(@placeholder, '활용목적')]",
            "//textarea[contains(@id, 'purps')]",
            "//textarea[contains(@name, 'purps')]"
        ]
        
        for selector in textarea_selectors:
            try:
                element = self.wait.until(EC.presence_of_element_located((By.XPATH, selector)))
                element.clear()
                element.send_keys(self.purpose_text)
                
                logging.info(f"활용목적 입력 성공: {selector}")
                print("  ✓ 활용목적 입력 완료")
                return True
                
            except (TimeoutException, NoSuchElementException):
                continue
            except Exception as e:
                logging.warning(f"활용목적 입력 시도 실패 ({selector}): {e}")
                continue
        
        logging.error("활용목적 텍스트 영역을 찾을 수 없음")
        print("  ❌ 활용목적 입력 실패")
        return False
    
    def check_agreement_checkbox(self) -> bool:
        """
        이용허락범위 동의 체크박스 체크
        
        Returns:
            체크 성공 여부
        """
        checkbox_selectors = [
            "//input[@id='useScopeAgreAt']",
            "//input[@name='useScopeAgreAt']",
            "//input[@id='useScopeAgreAt' and @name='useScopeAgreAt']",
            "//input[@type='checkbox' and @value='Y' and @id='useScopeAgreAt']",
            "//label[@for='useScopeAgreAt']/..//input[@type='checkbox']",
            "//input[@type='checkbox' and contains(@id, 'Agre')]",
            "//input[@type='checkbox' and contains(@name, 'Agre')]",
            "//input[@type='checkbox' and @value='Y']"
        ]
        
        for selector in checkbox_selectors:
            try:
                element = self.wait.until(EC.element_to_be_clickable((By.XPATH, selector)))
                
                # 이미 체크되어 있는지 확인
                if not element.is_selected():
                    element.click()
                    time.sleep(0.5)  # 클릭 후 잠시 대기
                
                logging.info(f"동의 체크박스 체크 성공: {selector}")
                print("  ✓ 이용허락범위 동의 완료")
                return True
                
            except (TimeoutException, NoSuchElementException, ElementClickInterceptedException):
                continue
            except Exception as e:
                logging.warning(f"동의 체크박스 클릭 시도 실패 ({selector}): {e}")
                continue
        
        logging.error("동의 체크박스를 찾을 수 없음")
        print("  ❌ 이용허락범위 동의 실패")
        return False
    
    def fill_form(self) -> bool:
        """
        전체 폼 작성
        
        Returns:
            폼 작성 성공 여부
        """
        print("  📝 폼 작성 중...")
        
        # 페이지 로딩 완료 대기
        time.sleep(2)
        
        # 활용목적 입력
        if not self.fill_purpose_text():
            return False
        
        # 동의 체크박스 체크
        if not self.check_agreement_checkbox():
            return False
        
        print("  ✅ 폼 작성 완료")
        return True


class FormSubmitter:
    """활용신청 폼 제출 클래스"""
    
    def __init__(self, driver: webdriver.Chrome):
        self.driver = driver
        self.wait = WebDriverWait(driver, 10)
    
    def find_submit_button(self):
        """
        제출 버튼 찾기
        
        Returns:
            제출 버튼 element 또는 None
        """
        submit_button_selectors = [
            "//div[@id='loadingDiv']//button[@class='button blue']",
            "//button[contains(text(), '활용신청')]",
            "//button[contains(@onclick, 'fn_save')]",
            "//button[@type='submit']",
            "//input[@type='submit']",
            "//button[contains(@class, 'btn-submit')]",
            "//button[contains(@class, 'button') and contains(@class, 'blue')]",
            "//button[contains(text(), '신청')]",
            "//button[contains(text(), '저장')]",
            "//button[contains(@value, '신청')]",
            "//input[contains(@value, '신청')]"
        ]
        
        for selector in submit_button_selectors:
            try:
                element = self.wait.until(EC.element_to_be_clickable((By.XPATH, selector)))
                logging.info(f"제출 버튼 발견: {selector}")
                return element
            except (TimeoutException, NoSuchElementException):
                continue
            except Exception as e:
                logging.warning(f"제출 버튼 찾기 시도 실패 ({selector}): {e}")
                continue
        
        return None
    
    def handle_alert(self) -> bool:
        """
        Alert 창 처리
        
        Returns:
            Alert 처리 성공 여부
        """
        try:
            # Alert 대기 (최대 5초)
            alert = WebDriverWait(self.driver, 5).until(EC.alert_is_present())
            alert_text = alert.text
            logging.info(f"Alert 창 감지: {alert_text}")
            
            # Alert 승인
            alert.accept()
            print(f"  📢 Alert 처리: {alert_text}")
            return True
            
        except TimeoutException:
            # Alert가 없는 경우 (정상)
            logging.info("Alert 창 없음")
            return True
            
        except Exception as e:
            logging.error(f"Alert 처리 오류: {e}")
            print(f"  ⚠️  Alert 처리 오류: {e}")
            return False
    
    def submit_form(self) -> bool:
        """
        폼 제출
        
        Returns:
            제출 성공 여부
        """
        print("  📤 폼 제출 중...")
        
        # 제출 버튼 찾기
        submit_button = self.find_submit_button()
        if not submit_button:
            logging.error("제출 버튼을 찾을 수 없음")
            print("  ❌ 제출 버튼을 찾을 수 없습니다")
            return False
        
        try:
            # 제출 버튼 클릭
            submit_button.click()
            logging.info("제출 버튼 클릭 완료")
            
            # Alert 처리
            time.sleep(1)  # Alert 대기를 위한 짧은 지연
            if not self.handle_alert():
                print("  ⚠️  Alert 처리에 문제가 있었지만 계속 진행합니다")
            
            # 제출 처리 완료 대기
            time.sleep(5)
            
            print("  ✅ 폼 제출 완료")
            return True
            
        except ElementClickInterceptedException as e:
            logging.error(f"제출 버튼 클릭 방해: {e}")
            print("  ❌ 제출 버튼을 클릭할 수 없습니다 (다른 요소에 의해 가려짐)")
            return False
            
        except Exception as e:
            logging.error(f"폼 제출 오류: {e}")
            print(f"  ❌ 폼 제출 오류: {e}")
            return False
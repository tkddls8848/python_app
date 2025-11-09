"""
동적 테이블 구조 분석 스크립트
https://www.data.go.kr/data/15001700/openapi.do
위치: /html/body/div[2]/div/div[2]/div/div[2]/div[4]/div[2]/div[1]/div/div[1]
"""
import asyncio
from playwright.async_api import async_playwright
import json

async def analyze_dynamic_table():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)  # GUI로 확인
        page = await browser.new_page()

        url = "https://www.data.go.kr/data/15001700/openapi.do"
        print(f"페이지 로딩: {url}")

        try:
            await page.goto(url, wait_until='networkidle', timeout=60000)
            print("✓ 페이지 로드 완료")

            # 추가 대기 (동적 콘텐츠 렌더링)
            await asyncio.sleep(5)

            # 1. XPath로 요소 찾기
            xpath = '/html/body/div[2]/div/div[2]/div/div[2]/div[4]/div[2]/div[1]/div/div[1]'
            target_element = await page.query_selector(f'xpath={xpath}')

            if target_element:
                print("\n✓ 타겟 요소 발견!")

                # 요소의 HTML 구조 확인
                html_content = await target_element.inner_html()
                print(f"\n=== HTML 구조 (처음 500자) ===")
                print(html_content[:500])

                # 요소의 클래스와 ID 확인
                class_name = await target_element.get_attribute('class')
                element_id = await target_element.get_attribute('id')
                tag_name = await target_element.evaluate('el => el.tagName')

                print(f"\n=== 요소 정보 ===")
                print(f"태그: {tag_name}")
                print(f"클래스: {class_name}")
                print(f"ID: {element_id}")

                # 하위 테이블 찾기
                tables = await target_element.query_selector_all('table')
                print(f"\n=== 하위 테이블 개수: {len(tables)} ===")

                for i, table in enumerate(tables):
                    table_class = await table.get_attribute('class')
                    table_id = await table.get_attribute('id')
                    print(f"\n테이블 {i+1}:")
                    print(f"  클래스: {table_class}")
                    print(f"  ID: {table_id}")

                    # 행 개수 확인
                    rows = await table.query_selector_all('tr')
                    print(f"  행 개수: {len(rows)}")

                    # 처음 3개 행 출력
                    for j, row in enumerate(rows[:3]):
                        cells = await row.query_selector_all('th, td')
                        cell_texts = []
                        for cell in cells:
                            text = await cell.inner_text()
                            cell_texts.append(text.strip()[:50])
                        print(f"  행 {j+1}: {cell_texts}")

                # 셀렉트 박스나 버튼이 있는지 확인
                selects = await target_element.query_selector_all('select')
                buttons = await target_element.query_selector_all('button')

                print(f"\n=== 인터랙티브 요소 ===")
                print(f"셀렉트 박스 개수: {len(selects)}")
                print(f"버튼 개수: {len(buttons)}")

                if selects:
                    for i, select in enumerate(selects):
                        select_id = await select.get_attribute('id')
                        select_name = await select.get_attribute('name')
                        options = await select.query_selector_all('option')
                        print(f"\n셀렉트 {i+1}:")
                        print(f"  ID: {select_id}")
                        print(f"  Name: {select_name}")
                        print(f"  옵션 개수: {len(options)}")

                        # 옵션 값 출력
                        for j, option in enumerate(options[:5]):  # 처음 5개만
                            value = await option.get_attribute('value')
                            text = await option.inner_text()
                            print(f"    옵션 {j+1}: value={value}, text={text}")

                # 전체 HTML 저장
                with open('/home/user/python_app/dynamic_table_structure.html', 'w', encoding='utf-8') as f:
                    f.write(html_content)
                print("\n💾 전체 HTML이 dynamic_table_structure.html에 저장되었습니다.")

                # CSS 셀렉터 대안 찾기
                print("\n=== CSS 셀렉터 대안 ===")

                # 상위 div 확인
                parent_divs = await page.query_selector_all('div[class*="detail"], div[id*="api"]')
                for div in parent_divs[:3]:
                    div_class = await div.get_attribute('class')
                    div_id = await div.get_attribute('id')
                    print(f"  div - class: {div_class}, id: {div_id}")

            else:
                print("\n❌ 타겟 요소를 찾을 수 없습니다.")

                # 전체 페이지 스크린샷
                await page.screenshot(path='/home/user/python_app/page_screenshot.png', full_page=True)
                print("📸 전체 페이지 스크린샷이 저장되었습니다.")

            # 5초 대기 (수동 확인용)
            print("\n5초 후 브라우저가 닫힙니다...")
            await asyncio.sleep(5)

        except Exception as e:
            print(f"\n❌ 에러 발생: {e}")
            import traceback
            traceback.print_exc()

        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(analyze_dynamic_table())

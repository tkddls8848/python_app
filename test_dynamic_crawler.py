"""
동적 테이블 크롤러 테스트 스크립트
https://www.data.go.kr/data/15001700/openapi.do 페이지 크롤링
"""
import asyncio
import json
import sys
import os

# 경로 설정
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from nara_crawler.hybrid.dynamic_table_crawler import DynamicTableCrawler


async def test_specific_location():
    """특정 위치 테이블 분석"""
    print("=" * 60)
    print("동적 테이블 크롤링 테스트")
    print("=" * 60)

    crawler = DynamicTableCrawler()

    url = "https://www.data.go.kr/data/15001700/openapi.do"
    xpath = '/html/body/div[2]/div/div[2]/div/div[2]/div[4]/div[2]/div[1]/div/div[1]'

    print(f"\nURL: {url}")
    print(f"XPath: {xpath}")
    print("\n페이지 분석 중...")

    try:
        result = await crawler.crawl_specific_location(url, xpath)

        if result['success']:
            print("\n✅ 분석 성공!")

            data = result['data']

            # 요소 정보
            print(f"\n📍 요소 정보:")
            print(f"  태그: {data['element_info']['tag']}")
            print(f"  클래스: {data['element_info']['class']}")
            print(f"  ID: {data['element_info']['id']}")

            # 셀렉트 박스 정보
            if data.get('select_count', 0) > 0:
                print(f"\n🎛️ 셀렉트 박스: {data['select_count']}개")

                for select_info in data['selects']:
                    print(f"\n  셀렉트 {select_info['index'] + 1}:")
                    print(f"    ID: {select_info['id']}")
                    print(f"    Name: {select_info['name']}")
                    print(f"    옵션: {len(select_info['options'])}개")

                    if select_info['options']:
                        print(f"\n    옵션 목록 (처음 5개):")
                        for i, option in enumerate(select_info['options'][:5]):
                            print(f"      {i+1}. {option['text']} (value: {option['value']})")

                        if len(select_info['options']) > 5:
                            print(f"      ... 외 {len(select_info['options']) - 5}개")

                # 셀렉터 기반 크롤링 제안
                if data['selects']:
                    select_id = data['selects'][0]['id']
                    print(f"\n💡 다음 단계: 셀렉터별 크롤링")
                    print(f"   python test_dynamic_crawler_full.py --select-id {select_id}")

            # 테이블 정보
            if data.get('table_count', 0) > 0:
                print(f"\n📊 테이블: {data['table_count']}개")

                for table_info in data['tables']:
                    table_data = table_info['data']
                    print(f"\n  테이블 {table_info['index'] + 1}:")
                    print(f"    헤더: {table_data['headers']}")
                    print(f"    행 개수: {len(table_data['rows'])}")

                    if table_data['rows']:
                        print(f"    첫 행: {table_data['rows'][0]}")

            # 결과 저장
            output_file = '/home/user/python_app/dynamic_table_analysis.json'
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(result, f, ensure_ascii=False, indent=2)

            print(f"\n💾 전체 결과가 저장되었습니다:")
            print(f"   {output_file}")

        else:
            print("\n❌ 분석 실패")
            print(f"에러: {result['errors']}")

    except Exception as e:
        print(f"\n❌ 에러 발생: {e}")
        import traceback
        traceback.print_exc()


async def test_selector_based_crawling(selector_css=None, selector_id=None):
    """셀렉터 기반 전체 크롤링"""
    print("=" * 60)
    print("셀렉터 기반 동적 테이블 크롤링")
    print("=" * 60)

    crawler = DynamicTableCrawler()

    url = "https://www.data.go.kr/data/15001700/openapi.do"
    xpath = '/html/body/div[2]/div/div[2]/div/div[2]/div[4]/div[2]/div[1]/div/div[1]'

    if selector_id:
        selector_css = f"select#{selector_id}"

    if not selector_css:
        print("⚠️ 셀렉터 CSS가 필요합니다.")
        print("먼저 test_specific_location()을 실행하여 셀렉트 ID를 확인하세요.")
        return

    print(f"\nURL: {url}")
    print(f"셀렉터: {selector_css}")
    print(f"테이블 위치: {xpath}")
    print("\n크롤링 중...")

    try:
        result = await crawler.crawl_dynamic_selector_table(
            url=url,
            selector_css=selector_css,
            table_container_xpath=xpath,
            wait_after_select=2.0
        )

        if result['success']:
            print("\n✅ 크롤링 성공!")
            print(f"수집된 옵션: {len(result['data'])}개")

            for option_key, option_data in result['data'].items():
                print(f"\n📌 {option_data['option_text']} (value: {option_key})")
                print(f"   테이블: {len(option_data['tables'])}개")

                for table in option_data['tables']:
                    table_data = table['data']
                    print(f"   - 테이블 {table['table_index'] + 1}: {len(table_data['rows'])}행")

            # 결과 저장
            output_file = '/home/user/python_app/dynamic_table_full_result.json'
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(result, f, ensure_ascii=False, indent=2)

            print(f"\n💾 전체 결과가 저장되었습니다:")
            print(f"   {output_file}")

        else:
            print("\n❌ 크롤링 실패")
            print(f"에러: {result['errors']}")

    except Exception as e:
        print(f"\n❌ 에러 발생: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='동적 테이블 크롤러 테스트')
    parser.add_argument('--mode', choices=['analyze', 'crawl'], default='analyze',
                       help='실행 모드: analyze (분석) 또는 crawl (전체 크롤링)')
    parser.add_argument('--select-id', help='셀렉트 박스 ID (crawl 모드에서 필요)')
    parser.add_argument('--select-css', help='셀렉트 박스 CSS 셀렉터')

    args = parser.parse_args()

    if args.mode == 'analyze':
        asyncio.run(test_specific_location())
    elif args.mode == 'crawl':
        asyncio.run(test_selector_based_crawling(
            selector_css=args.select_css,
            selector_id=args.select_id
        ))

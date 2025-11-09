# 조달청 입찰공고 조회 MCP 서버

## 설치
```bash
pip install fastmcp
```

## 설정

서비스키 설정 (2가지 방법 중 선택):

**방법 1: 환경변수**
```bash
export SERVICE_KEY=your_actual_service_key
```

**방법 2: server.py 직접 수정**
```python
SERVICE_KEY = "your_actual_service_key"
```

## 실행
```bash
python server.py
```

## Claude Desktop 연동

`claude_desktop_config.json`:
```json
{
  "mcpServers": {
    "procurement": {
      "command": "python",
      "args": ["server.py"],
      "cwd": "/절대/경로/to/simple-procurement-mcp",
      "env": {
        "SERVICE_KEY": "your_service_key_here"
      }
    }
  }
}
```

## 사용 예시

Claude에서:
```
25년 4월 조달청 입찰공고 조회 URL 만들어줘
```

또는
```
2025년 4월 입찰공고
```

## 응답 예시
```json
{
  "url": "https://apis.data.go.kr/1230000/ao/PubDataOpnStdService/getDataSetOpnStdBidPblancInfo?serviceKey=...&bidNtceBgnDt=202504010000&bidNtceEndDt=202504302359",
  "description": "조달청 나라장터 입찰공고정보 조회",
  "parameters": {
    "입찰공고일시_시작": "202504010000",
    "입찰공고일시_종료": "202504302359",
    "페이지번호": 1,
    "결과수": 10
  },
  "usage": {
    "curl": "curl 'https://apis.data.go.kr/...'",
    "note": "실제 사용시 serviceKey를 본인의 키로 교체하세요"
  }
}
```

## 서비스키 발급

1. https://www.data.go.kr 접속
2. 회원가입/로그인
3. "조달청_나라장터 공공데이터개방표준서비스" 검색
4. 활용신청 → 서비스키 발급

## 제한사항

- 입찰공고일시 범위는 1개월로 제한
- 날짜 형식: "25년 4월" 또는 "2025년 4월"만 지원
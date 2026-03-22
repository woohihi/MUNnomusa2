# MUNnomusa2 - Claude Code 작업 내역

## 프로젝트 개요
공공기관 노무고문/자문위원 모집 공고 자동 모니터링 CRM 시스템
- Python 3.11 / Streamlit 대시보드
- 네이버 검색 API + Gemini AI 적합성 판별
- Google Sheets 영속 저장소
- GitHub Actions 주간 자동 검색

## 2026-03-22 작업 내역

### 문제: GitHub Actions 워크플로우 파일 누락
- README에는 GitHub Actions 자동화가 있다고 명시되어 있었지만
- `.github/workflows/` 폴더 및 워크플로우 파일이 존재하지 않아
- 자동 검색이 처음부터 한 번도 실행되지 않았음

### 수정 내용

#### 1. `.github/workflows/search.yml` 생성 (신규)
- 매주 월요일 오전 9시 KST (UTC 00:00) 자동 실행
- `workflow_dispatch`로 수동 실행도 가능 (`--limit`, `--orgs` 파라미터 지원)
- 필요한 모든 환경변수를 GitHub Secrets에서 주입

#### 2. `src/telegram_sender.py` 추가 (신규)
- NomuBlog 프로젝트(Next.js 블로그)와 **동일한 텔레그램 봇 토큰 재사용**
- `urllib` 표준 라이브러리만 사용 (추가 의존성 없음)
- `send_search_summary()`: 검색 완료 후 결과 요약 전송
- `send_error_alert()`: 파이프라인 치명적 오류 시 경고 전송
- 환경변수 `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`로 설정

#### 3. `src/main.py` 수정
- `telegram_sender` import 추가
- Step 7 추가: 이메일 발송(Step 6) 완료 후 텔레그램 알림 전송
- 치명적 오류 발생 시 `tg_error()` 호출

### GitHub Secrets 등록 목록 (woohihi/MUNnomusa2)
| Secret | 설명 |
|--------|------|
| `NAVER_CLIENT_ID` | 네이버 검색 API Client ID |
| `NAVER_CLIENT_SECRET` | 네이버 검색 API Client Secret |
| `GEMINI_API_KEY` | Google Gemini API 키 |
| `GOOGLE_SHEETS_ID` | Google Sheets 스프레드시트 ID |
| `GOOGLE_SHEETS_CREDS` | GCP Service Account JSON (전체 문자열) |
| `TELEGRAM_BOT_TOKEN` | 텔레그램 봇 토큰 (NomuBlog와 공유) |
| `TELEGRAM_CHAT_ID` | 텔레그램 채팅 ID (NomuBlog와 공유) |
| `SENDER_EMAIL` | Gmail 발신 주소 |
| `SENDER_PASSWORD` | Gmail 앱 비밀번호 |
| `RECIPIENT_EMAIL` | 이메일 수신 주소 |

## 아키텍처 메모

### 텔레그램 봇 공유 구조
```
NomuBlog (Next.js/Vercel)
  └─ 뉴스 알림, 칼럼 선택 → 텔레그램 봇 ──┐
                                              ├── 동일 봇 토큰/채팅 ID
MUNnomusa2 (Python/GitHub Actions)           │
  └─ 신규 공고 발견 알림 → 텔레그램 봇 ──────┘
```

### 자동 실행 스케줄
- 매주 월요일 09:00 KST
- Vercel 크론과 별개로 GitHub Actions에서 독립 실행
- 실행 실패 시 텔레그램으로 오류 알림

## 환경변수 위치
- 로컬: `.streamlit/secrets.toml` (gitignore 대상)
- GitHub Actions: Repository Secrets
- Streamlit Cloud: Streamlit Secrets

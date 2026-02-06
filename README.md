# AI 노무고문 공고 모니터링 웹 서비스

> 공공기관의 노무고문/자문위원 모집 공고를 24시간 감시하고, 과거 데이터 기반으로 다음 위촉 시기를 예측하는 올인원 CRM 시스템

[![Streamlit](https://img.shields.io/badge/Streamlit-FF4B4B?style=flat&logo=streamlit&logoColor=white)](https://streamlit.io/)
[![Python](https://img.shields.io/badge/Python-3.11-blue)](https://www.python.org/)
[![Google Sheets](https://img.shields.io/badge/Google%20Sheets-34A853?style=flat&logo=googlesheets&logoColor=white)](https://www.google.com/sheets/about/)

## 🎯 주요 기능

- **Two-Track 검색**: VIP 기관 정밀 감시 + 광역 키워드 발굴
- **비용 최적화**: Python 전처리로 AI API 호출 최소화
- **빈 본문 대응**: 첨부파일만 있는 공고도 제목 기반 포착
- **예측 시스템**: 과거 임기 데이터로 다음 공고 시기 예측
- **클라우드 데이터베이스**: Google Sheets 기반 영속성
- **자동화**: GitHub Actions 주간 스케줄링

## 🏗️ 시스템 아키텍처

```mermaid
graph TB
    A[GitHub Actions<br/>매주 월요일 09:00] -->|Trigger| B[검색 파이프라인]
    B --> C[네이버 검색 API<br/>Track A + B]
    C --> D[전처리<br/>중복 제거 + 키워드 필터]
    D --> E[Gemini 1.5 Flash<br/>적합성 판별]
    E --> F[Google Sheets<br/>Results 저장]
    F --> G[이메일 알림]
    
    H[Streamlit 웹 대시보드] -->|Read| F
    H --> I[현재 공고 조회]
    H --> J[수동 검색 실행]
    H --> K[예측 알림]
    
    F -->|마감일 지남| L[Archive Sheet]
    L --> M[예측 알고리즘<br/>D-day 계산]
    M --> K
```

## 🚀 빠른 시작

### 1. 사전 준비

#### 필수 API 키 발급

1. **네이버 검색 API**
   - [네이버 개발자 센터](https://developers.naver.com/apps/#/register) 접속
   - 애플리케이션 등록 → 검색 API 활성화
   - Client ID, Client Secret 저장

2. **Google Gemini API**
   - [Google AI Studio](https://aistudio.google.com/app/apikey) 접속
   - API 키 생성

3. **Google Cloud Service Account**
   ```bash
   # Google Cloud Console에서
   1. 새 프로젝트 생성
   2. Google Sheets API 활성화
   3. 서비스 계정 생성
   4. JSON 키 다운로드
   ```

4. **Google Sheets 생성**
   - [새 스프레드시트 생성](https://sheets.new)
   - 스프레드시트 ID 복사 (URL에서 추출)
   - Service Account 이메일과 공유 (편집자 권한)

### 2. 프로젝트 설치

```bash
# 레포지토리 클론
git clone https://github.com/your-username/MUNnomusa2.git
cd MUNnomusa2

# 의존성 설치
pip install -r requirements.txt
```

### 3. Secrets 설정

`.streamlit/secrets.toml` 파일 생성:

```toml
NAVER_CLIENT_ID = "your_client_id"
NAVER_CLIENT_SECRET = "your_client_secret"
GEMINI_API_KEY = "your_gemini_api_key"
GOOGLE_SHEETS_ID = "your_spreadsheet_id"

[gcp_service_account]
type = "service_account"
project_id = "your-project-id"
private_key_id = "key_id"
private_key = "-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n"
client_email = "service-account@project.iam.gserviceaccount.com"
# ... (Service Account JSON의 나머지 필드)

[email]
smtp_server = "smtp.gmail.com"
smtp_port = 587
sender_email = "your_email@gmail.com"
sender_password = "your_gmail_app_password"
recipient_email = "recipient@example.com"
```

### 4. Google Sheets 초기화

```python
# Python 인터프리터에서 실행
from src.sheets_manager import GoogleSheetManager

manager = GoogleSheetManager()
manager.init_all_sheets()  # Config, Results, Archive 시트 생성
```

### 5. 로컬 실행

```bash
streamlit run streamlit_app.py
```

브라우저에서 `http://localhost:8501` 접속

## 📦 배포 (Streamlit Community Cloud)

### 1. GitHub에 푸시

```bash
git add .
git commit -m "Initial commit"
git push origin main
```

### 2. Streamlit Cloud 설정

1. [Streamlit Community Cloud](https://streamlit.io/cloud) 로그인
2. **New app** → GitHub 레포지토리 선택
3. Main file path: `streamlit_app.py`
4. **Advanced settings** → Secrets 추가 (위의 secrets.toml 내용 복사)
5. **Deploy** 클릭

### 3. GitHub Actions Secrets 설정

레포지토리 Settings → Secrets and variables → Actions → New repository secret:

| Secret 이름 | 값 |
|------------|---|
| `NAVER_CLIENT_ID` | 네이버 Client ID |
| `NAVER_CLIENT_SECRET` | 네이버 Client Secret |
| `GEMINI_API_KEY` | Gemini API Key |
| `GOOGLE_SHEETS_ID` | 스프레드시트 ID |
| `GOOGLE_SHEETS_CREDS` | Service Account JSON (전체 문자열) |
| `SENDER_EMAIL` | Gmail 주소 |
| `SENDER_PASSWORD` | Gmail 앱 비밀번호 |
| `RECIPIENT_EMAIL` | 수신 이메일 |

## 📖 사용 방법

### 웹 대시보드

#### 🏠 현재 공고
- 진행 중인 공고 목록 조회
- 기관별 필터링, 마감일 정렬
- Obsidian 마크다운 / Excel 다운로드

#### 🔍 검색 실행
- 수동 검색 트리거
- 실시간 진행률 표시
- 신규 공고 발견 시 이메일 발송

#### 📈 예측 알림
- D-30 이내 임기 만료 예상 기관 표시
- 카드 스타일 UI로 직관적 확인

#### ⚙️ 설정
- Google Sheets 직접 편집 링크
- API 연결 상태 테스트
- 마감 공고 수동 아카이빙

### 기관 추가 방법

1. Google Sheets의 **Config** 탭 열기
2. 새 행에 정보 입력:
   - `organization`: 기관명 (예: "한국환경공단")
   - `keywords`: 키워드 (예: "노무고문,자문위원")
   - `active`: TRUE
3. 저장 후 다음 검색부터 자동 반영

## 🔧 트러블슈팅

### Google Sheets 연결 실패

**증상**: "Google Sheets 연결 실패" 오류

**해결**:
1. Service Account JSON이 올바른지 확인
2. 스프레드시트를 Service Account 이메일과 공유했는지 확인
3. Google Sheets API가 활성화되었는지 확인

### Gemini 429 오류 (Quota 초과)

**증상**: "You exceeded your current quota" 오류

**해결**:
1. 무료 티어 제한 확인 (분당 15 RPM, 일일 1,500 RPM)
2. `config.py`의 `GEMINI_RATE_LIMIT_DELAY` 증가 (0.5 → 1.0초)
3. 검색 빈도 줄이기 (주 1회 → 월 2회)

### 이메일 발송 실패

**증상**: "이메일 발송 실패" 메시지

**해결**:
1. Gmail 2단계 인증 활성화 확인
2. 앱 비밀번호 재발급 ([링크](https://myaccount.google.com/apppasswords))
3. SMTP 설정 확인 (포트 587, TLS)

## 📊 데이터 구조

### Config Sheet
| organization | keywords | active |
|-------------|----------|--------|
| 한국환경공단 | 노무고문,자문위원 | TRUE |

### Results Sheet
| url | title | organization | deadline | summary | collected_date |
|-----|-------|--------------|----------|---------|----------------|

### Archive Sheet
| ... (Results 컬럼) | term_months | start_date | next_expected_date |
|-------------------|-------------|------------|-------------------|

## 🛠️ 기술 스택

- **Frontend/Backend**: Python 3.11, Streamlit
- **AI**: Google Gemini 1.5 Flash
- **Database**: Google Sheets API (gspread)
- **Search**: 네이버 검색 API
- **Automation**: GitHub Actions
- **Email**: SMTP (Gmail)

## 📝 라이선스

MIT License

## 🤝 기여

이슈 및 Pull Request 환영합니다!

## 📧 문의

프로젝트 관련 문의: [your-email@example.com]

---

**Powered by Gemini 1.5 Flash** 🤖

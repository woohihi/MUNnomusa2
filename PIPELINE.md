# 노무고문 공고 모니터링 - 검색·분류 파이프라인 상세 문서

> 최종 업데이트: 2026-03-05
> 실행 진입점: `src/main.py`

---

## 전체 흐름 요약

```
Config Sheet (기관 목록)
        │
        ▼
[Step 1] Google Sheets 연결 및 기관 로드
        │
        ▼
[Step 2] 네이버 검색 (Track A + B 병렬, Track C 선택)
        │
        ├─ Track A: 기관 정밀 감시 (webkr + blog)
        ├─ Track B: 광역 키워드 검색 (webkr + blog + news)
        └─ Track C: 나라장터 API (G2B_API_KEY 없으면 자동 Skip)
        │
        ▼
[Step 3] 전처리 (4단계 파이프라인)
        │
        ├─ Step 1: 중복 URL 제거 (DB + Excluded 대조)
        ├─ Step 2: 키워드 검증 (Track A만 적용)
        ├─ Step 3: 네거티브 필터 (제목 기준)
        └─ Step 4: 점수 기반 필터 (score < 30 스킵)
        │
        ▼
[Step 3.5] 본문 크롤링 (description 짧은 항목 보강)
        │
        ▼
[Step 4] Gemini AI 분석 (4단계 판단)
        │
        ├─ Quick Reject 1: 과거 연도 공고 → Archive 자동 분류
        ├─ 키워드 자동통과: 핵심 키워드 매칭 → Gemini 생략
        ├─ Quick Reject 2: 명백한 무관 직종 → 거부
        └─ Gemini 분석: 공인노무사 Agent 판단
        │
        ▼
[Step 5] 결과 저장 (suggested_target 기준 분리)
        │
        ├─ suggested_target='Archive' → Archive 시트 직접 저장 (검토 불필요)
        └─ suggested_target='Results' → Pending 시트 저장 (관리자 검토 대기)
        │
        ▼
[Step 6] 이메일 발송 (요약 리포트)
```

---

## Step 2: 네이버 검색 (`src/naver_search.py`)

### Track A — 기관 정밀 감시

| 항목 | 내용 |
|------|------|
| 대상 | Config 시트에 등록된 기관 전체 |
| 검색 유형 | `webkr` + `blog` (2가지) |
| 쿼리 형식 | `"{기관명} {키워드}"` (예: "한국환경공단 노무고문") |
| Grade별 결과 수 | A등급: 20건 / B등급: 10건 / C등급: 5건 |
| 날짜 필터 | 최근 14일 이내 (pubDate 없으면 통과) |
| 태그 | `source='track_a'`, `organization_hint=기관명` |

**Grade 설정 방법:** Config 시트의 `grade` 컬럼에 A/B/C 입력. 없으면 자동으로 B 적용.

### Track B — 광역 키워드 검색

| 항목 | 내용 |
|------|------|
| 대상 | 고정 키워드 리스트 (config.py `DEFAULT_JOB_KEYWORDS`) |
| 검색 유형 | `webkr` + `blog` + `news` (3가지) |
| 키워드 목록 | 노무고문, 고문노무사, 자문노무사, 노무자문, 인사노무 자문위원, 노무 자문위원, 노무 전문위원, 인사위원회 위원 |
| 결과 수 | 키워드당 15건 |
| 날짜 필터 | 최근 14일 이내 |
| 태그 | `source='track_b'` |

### Track C — 나라장터 API (선택)

| 항목 | 내용 |
|------|------|
| 활성화 조건 | `G2B_API_KEY` 환경변수 또는 secrets에 설정된 경우만 |
| 검색 키워드 | 노무자문, 고문노무사, 자문노무사 |
| 결과 수 | 키워드당 20건 |
| 태그 | `source='track_c'` |
| API 없으면 | 자동 비활성화, 파이프라인 영향 없음 |

### 병렬 실행

Track A와 Track B는 `ThreadPoolExecutor(max_workers=2)`로 동시 실행.
Track C는 A/B 완료 후 순차 실행.

---

## Step 3: 전처리 (`src/preprocessor.py`)

### Step 1 — 중복 URL 제거

- **DB 중복**: Results + Archive 시트에 이미 있는 URL 제거
- **Excluded 중복**: 이전에 거절 처리된 URL 제거
- 기준: `item['link']` 완전 일치

### Step 2 — 키워드 검증 (Track A만 적용)

Track A 결과는 기관명으로 검색했기 때문에 노무 관련 내용이 없는 것도 포함될 수 있음.
제목 + 설명에 아래 키워드 중 1개 이상 있어야 통과:

```
노무, 법률, 고문, 자문, 위원, 평가, 인사, 심의, 위촉
```

Track B, C는 이미 키워드로 검색했으므로 이 단계 무조건 통과.

### Step 3 — 네거티브 필터

제목에 아래 키워드가 포함되면 제거:

| 카테고리 | 키워드 |
|----------|--------|
| 비관련 용역 | 입찰, 구매, 청소, 경비, 시스템 구축, 건설, 시공, 납품, 물품, 설비, 철거, 폐기물, 운송 |
| 주거/생활 | 아파트 |
| 취업 콘텐츠 | 자기소개서, 자소서, 합격후기, 면접후기, 수강, 강의, 설명회, 이벤트, 교육생 |
| 언론/홍보 | 기자, 보도자료, 뉴스, 신문, 속보, 홍보, 광고, 무료상담, 법률상담, 무료진단 |
| 학습 | 학원, 과외, 스터디, 동아리 |
| 단기 고용 | 아르바이트, 알바, 단기, 계약직, 파견 |

### Step 4 — 점수 기반 필터

각 항목에 0~100점 부여, 30점 미만은 Gemini 전송 없이 스킵.

| 점수 항목 | 조건 | 점수 |
|----------|------|------|
| 출처 (max 30) | URL이 .go.kr 또는 .or.kr | +30 |
| | Track A 항목 (기관 직접 검색) | +15 |
| 핵심 키워드 (max 40) | 노무고문, 고문노무사, 자문노무사, 노무자문, 노무사위촉, 노무사선정, 노무사모집, 인사노무자문 | +40 |
| | 노무, 고문, 자문, 위촉 | +20 |
| 공고 신호 (max 20) | 제목에 모집, 위촉, 공고, 선정, 안내 포함 | +20 |
| 출처 보정 (max 10) | Track B 또는 C 항목 | +10 |

| 점수 범위 | 분류 | 처리 |
|----------|------|------|
| 60점 이상 | HIGH priority | Gemini 전송 |
| 30~59점 | NORMAL priority | Gemini 전송 |
| 30점 미만 | SKIP | 탈락 (비용 절감) |

---

## Step 3.5: 본문 크롤링 (`src/web_scraper.py`)

`description` 길이가 **80자 미만**인 항목에 대해 원본 URL에서 본문 직접 수집.

- 타임아웃: 8초
- 최대 수집 길이: 2500자
- 한국어 인코딩 자동 감지 (EUC-KR 포함)
- 본문 영역 탐색 우선순위: `<article>` → `<main>` → id/class 패턴 → `<body>`
- 첨부파일만 있는 페이지 감지 시: `[첨부파일 확인 필요]` 접두어 추가

---

## Step 4: Gemini AI 분석 (`src/gemini_analyzer.py`)

### 사용 모델

| 우선순위 | 모델 |
|----------|------|
| 1순위 | `gemini-2.5-flash` |
| 2순위 (fallback) | `gemini-2.0-flash` |

404 오류 시 자동으로 다음 모델로 교체하여 재시도.

### 시스템 인스트럭션: 공인노무사 Agent

Gemini 호출 시 **15년 경력 공인노무사** 페르소나 적용:

- 판단 가능 직무: 노무고문, 고문/자문노무사, 법률자문위원(노동 분야), 인사위원회 자문위원, 산업안전 자문, 노무관리 위탁, 노사협력 자문, 위촉 전문위원
- 반드시 제외: 뉴스 기사, 홍보/마케팅, 합격 수기, 일반 직원 채용, 비관련 용역
- **판단 원칙: 애매한 경우 적합으로 판정** (누락이 거부보다 비용이 큼)

### 분석 전 판단 순서 (Gemini 호출 최소화)

```
항목 수신
    │
    ├─ [Quick Reject 1] 제목에 과거 연도(20XX, XX년) 포함?
    │       └─ Yes + 예외 키워드(평가/성과/결산/실적/감사) 없음
    │               → is_past_announcement=True, Archive 자동 분류
    │
    ├─ [키워드 자동통과] 제목(공백 제거)에 핵심 키워드?
    │       대상: 노무법인, 노무고문, 노무자문, 고문노무사, 자문노무사,
    │             노무사위촉, 노무사선정, 노무사모집, 인사노무
    │       └─ Yes → Gemini 생략, 즉시 통과
    │               - 제목에서 연도 추출 → 과거이면 is_past_announcement=True
    │               - 연도 없으면 description에서 날짜 패턴 추출 (NEW)
    │
    ├─ [Quick Reject 2] 제목에 명백 제외 직종 포함?
    │       대상: 경비원, 미화원, 운전원, 조리원, 영양사, 간호사,
    │             시설관리, 요양보호사, 사회복지사, 물리치료사,
    │             기간제근로자, 공무직, 사무원, 행정원, 연구원, 상담원,
    │             대학생, 청년인턴, 체험형, 아르바이트, 단기알바,
    │             용역, 입찰, 구매, 공사, 설계, 감리
    │       └─ Yes → 거부 (rejected_items에 추가)
    │
    └─ Gemini 분석 (위 3가지 모두 해당 없을 때)
            → JSON 반환: is_relevant, summary, deadline, term_months, start_date
```

### 과거 날짜 탐지 로직 (키워드 자동통과 보완, NEW)

제목에 연도가 없는 키워드 자동통과 항목의 경우, description 본문에서 날짜 추출:

1. `YYYY-MM-DD`, `YYYY.MM.DD`, `YYYY/MM/DD` 패턴 탐색
2. `YYYY년 MM월 DD일` 패턴 탐색
3. 미래 날짜 존재 시 → 가장 가까운 미래 날짜를 마감일로 채택
4. 모두 과거 날짜 → 가장 최근 과거 날짜를 마감일로 채택, `is_past_announcement=True`

### Gemini 응답 형식

```json
{
  "is_relevant": true,
  "summary": "공고 요약 1-2문장",
  "deadline": "YYYY-MM-DD",
  "term_months": 24,
  "start_date": "YYYY-MM-DD"
}
```

### 오류 처리

| 오류 | 처리 |
|------|------|
| 429 Quota Exceeded | 지수 백오프 재시도 (10s → 20s → 40s, 최대 3회) |
| 404 모델 없음 | 다음 모델로 자동 교체 후 재시도 |
| 403 API 키 차단 | 즉시 중단, 남은 항목 전부 "분석 실패" 상태로 Pending 저장 |

---

## Step 5: 결과 분류 및 저장 (`src/result_processor.py` + `src/main.py`)

### Priority 산정 (`_calculate_priority`)

| Priority | 조건 |
|----------|------|
| `긴급` | 마감일까지 D-7 이내 |
| `일반` | 마감일 여유 있음, Gemini 분석 통과 |
| `자동통과` | 키워드 매칭으로 통과 (Gemini 미거침) → **직접 확인 권장** |
| `기한미정` | 마감일 정보 없음 |
| `과거참고` | 마감 완료 공고 (`is_expired=True`) |
| `분석실패` | API 오류로 분석 불가 |

### 과거 공고 판단 (`is_expired`) 로직

```python
# 경로 1: is_past_announcement 플래그 (Quick Reject 1 또는 키워드 자동통과가 설정)
if item.get('is_past_announcement', False):
    is_expired = True

# 경로 2: Gemini가 추출한 deadline 날짜 비교
elif deadline_str:
    if datetime.strptime(deadline_str, '%Y-%m-%d').date() < date.today():
        is_expired = True
```

### suggested_target 결정

| 조건 | suggested_target |
|------|-----------------|
| `is_expired=True` | `'Archive'` |
| `is_expired=False` | `'Results'` |

### 저장 분기 (main.py)

```
all_records = ResultProcessor.process_results(analyzed_results)
    │
    ├─ suggested_target='Archive'
    │       → manager.append_archive_batch()  ← Archive 시트 직접 저장
    │         (관리자 검토 불필요, 과거 공고 참고용)
    │
    └─ suggested_target='Results'
            → manager.append_pending_batch()  ← Pending 시트 저장
              (관리자가 status 컬럼에 적합/거절/보류 입력 후 --approve 실행)
```

---

## Pending 시트 컬럼 구조

| 컬럼 | 내용 | 비고 |
|------|------|------|
| url | 공고 URL | |
| title | 공고 제목 | |
| organization | 기관명 | search_keyword → URL 도메인 순으로 fallback |
| deadline | 마감일 (YYYY-MM-DD) | |
| summary | AI 요약 또는 자동 분류 사유 | |
| suggested_target | 권장 저장 위치 (Results/Archive) | 시스템 자동 산정 |
| collected_date | 수집일 | |
| source | track_a / track_b / track_c | |
| status | **검토중** / 적합 / 거절 / 보류 | **관리자 직접 입력** |
| priority | 긴급 / 일반 / 자동통과 / 기한미정 / 과거참고 / 분석실패 | 시스템 자동 산정 |

---

## 관리자 검토 워크플로우

```
Pending 시트 확인
    │
    ├─ 적합한 공고 → status 셀에 "적합" 입력
    ├─ 불필요한 공고 → status 셀에 "거절" 입력
    └─ 나중에 판단 → status 셀에 "보류" 입력 (기본값: "검토중")
    │
    ▼
python -m src.main --approve 실행
    │
    ├─ status=적합 → Results 시트로 이동
    ├─ status=거절 → Excluded 시트로 이동 (이후 재수집 방지)
    └─ status=검토중/보류 → Pending 유지
```

---

## CLI 실행 옵션

| 옵션 | 설명 |
|------|------|
| `python -m src.main` | 전체 파이프라인 실행 |
| `--orgs N` | 검색 기관 수 제한 (테스트용) |
| `--limit N` | Gemini 분석 건수 제한 (테스트용) |
| `--approve` | Pending 검토 결과 처리 (적합→Results, 거절→Excluded) |
| `--reset` | 모든 데이터 시트 초기화 (Config 유지) |

---

## SearchLog 스테이지 흐름

각 항목은 파이프라인을 거치면서 SearchLog에 단계별로 기록됨:

| stage | 의미 |
|-------|------|
| `collected` | 네이버/G2B 검색 수집됨 |
| `filtered` | 전처리에서 탈락 (중복/키워드/네거티브/점수) |
| `analyzing` | 전처리 통과, Gemini 분석 대기 (Safety Net) |
| `rejected` | Gemini AI 또는 Quick Reject에서 거부 |
| `saved` | Pending 저장 완료 |

# 🚀 AI 노무고문 공고 모니터링 시스템 (MUNnomusa2) - 제품 요구사항 정의서 (PRD)

## 1. 프로젝트 개요 (Overview)

*   **프로젝트명**: MUNnomusa2 (AI Legal Advisor Job Monitor)
*   **목표**: 공공기관의 '노무고문/자문위원' 모집 공고를 반자동으로 수집, 분석하여 **적기에 지원**할 수 있도록 돕는 올인원 CRM.
*   **핵심 가치**:
    1.  **놓침 방지**: VIP 기관(Track A)과 광역 검색(Track B)의 이중 감시.
    2.  **시간 절약**: AI가 "단순 입찰/채용"을 걸러내고 "진짜 자문위원 공고"만 필터링.
    3.  **예측**: 과거 데이터를 기반으로 다음 위촉 시기를 예측하여 사전 영업 가능.

---

## 2. 시스템 아키텍처 (Current Architecture)

```mermaid
graph TD
    User[사용자 (노무사)] -->|Dashboard| Web[Streamlit 웹 앱]
    Auto[GitHub Actions (매주 월요일)] -->|CLI 실행| Pipeline[검색 파이프라인]

    subgraph "검색 파이프라인 (Core)"
        Naver[네이버 검색 API] -->|Raw Data| Filter[전처리 모듈]
        Filter -->|중복/키워드 필터링| AI_Check{AI 적합성 판단}
        AI_Check -->|Cost Save: 연도매칭| FastPass[자동 통과]
        AI_Check -->|Gemini 2.0 Flash| Analyze[상세 분석]
    end

    subgraph "데이터베이스 (Google Sheets)"
        Config[Config (기관/키워드)]
        Pending[Pending (검토 대기)]
        Results[Results (진행중 공고)]
        Archive[Archive (마감/CRM)]
        Log[SearchLog (모니터링)]
    end

    Pipeline -->|저장| Pending
    Web -->|Review| Pending
    Web -->|Approve/Reject| Results
    Web -->|이관| Archive
    Archive -->|D-day 계산| Web
```

---

## 3. 상세 기능 명세 (Detailed Specifications)

### 3.1 검색 모듈 (Search Engine)
*   **Two-Track 전략**:
    *   **Track A (VIP 기관)**: `Config` 시트에 등록된 기관명 + "개별 키워드" 조합으로 정밀 검색.
    *   **Track B (광역 검색)**: "노무고문", "자문위원" 등 포괄적 키워드로 모든 공공기관 검색.
*   **필터링 (Preprocessor)**:
    *   **URL 중복 제거**: `Results`, `Archive`, `Excluded` 시트에 이미 존재하는 URL은 즉시 제외.
    *   **Negative 필터**: "입찰", "청소", "경비", "합격후기" 등 불필요 키워드 제목 포함 시 1차 기각.

### 3.2 AI 분석 모듈 (Intelligence)
*   **Gemini 2.0/1.5 Flash 통합**:
    *   비용 절감을 위해 무료 티어(RPM 15) 제한 준수 (`config.py`: 4초 딜레이).
    *   **Fallback 로직**: Gemini 2.0 오류 시 1.5 버전으로 자동 재시도.
*   **하이브리드 분석**:
    *   **Rule-based**: 제목에 2026년, '26년 등이 포함되고 "노무고문"이 명확하면 AI 호출 없이 **즉시 통과** (속도/비용 최적화).
    *   **AI-based**: 본문을 분석하여 `is_relevant`(적합성), `deadline`(마감일), `summary`(요약) 추출.

### 3.3 검토 프로세스 (Human-in-the-Loop) - **핵심 기능**
*   **Pending (검토 대기소)**:
    *   자동 검색이나 수동 검색의 결과는 **절대 바로 `Results`에 들어가지 않음**.
    *   `Pending` 시트에 임시 저장된 후, 사용자가 Streamlit 웹의 **"검토 및 검색"** 탭에서 [저장] 버튼을 눌러야 `Results`로 이동.
    *   이유: AI의 오판(False Positive)으로 데이터베이스가 오염되는 것을 방지.

### 3.4 데이터 관리 & CRM
*   **영속성 보장**:
    *   모든 데이터는 Google Sheets에 저장되어 서버가 꺼져도 유지됨.
    *   **SearchLog**: 검색 시도, 수집 개수, 필터링 사유 등을 상세 기록 (디버깅용).
*   **예측 시스템**:
    *   `Archive` 시트의 `term_months`(임기) 정보를 활용.
    *   `start_date` + `term_months` - 30일 = **영업 예상 시점** 알림.

---

## 4. 데이터베이스 스키마 (Google Sheets)

현재 7개의 시트를 유기적으로 사용 중입니다.

| 시트명 | 역할 | 주요 컬럼 |
| :--- | :--- | :--- |
| **Config** | 검색 대상 관리 | `organization`, `keywords`, `active` |
| **Results** | **현재 진행 중 공고** | `url`, `title`, `deadline`, `D-day`, `summary` |
| **Pending** | **검토 대기소** | `suggested_target` (AI 추천 분류), `url`, `title`... |
| **Archive** | 마감된 공고 + CRM | `term_months`, `start_date`, `next_expected_date` |
| **Excluded** | 영구 제외 URL | `url`, `reason` (재수집 방지용) |
| **SearchLog** | 검색 이력/디버깅 | `timestamp`, `stage`, `reason` (실패 원인 추적) |
| **Keywords** | 광역 검색어 관리 | `keyword`, `active` |

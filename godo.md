

# 🏗️ 공공기관 노무자문 모집공고 모니터링 자동화 시스템

## 전체 시스템 아키텍처

```
┌─────────────────────────────────────────────────────────────────────┐
│                        🕐 시간 기반 트리거 (매일 09:00 / 14:00)           │
└──────────────────────────────┬──────────────────────────────────────┘
                               ▼
┌──────────────────────────────────────────────────────────────────────┐
│  PHASE 1: 데이터 수집                                                  │
│  ┌──────────────┐    ┌───────────────┐    ┌───────────────────────┐  │
│  │ 구글시트       │    │ 네이버 API     │    │ (선택) 나라장터 API   │  │
│  │ 기관목록(860) │───▶│ Blog/Web/News │    │ 용역 입찰공고         │  │
│  │ + 키워드 조합  │    │ 검색           │    │ 검색                  │  │
│  └──────────────┘    └──────┬────────┘    └──────────┬────────────┘  │
│                             │ 원시 결과                │              │
│                             ▼                         ▼              │
│                    ┌────────────────────────────────────┐             │
│                    │      결과 병합 & 중복제거           │             │
│                    └──────────────┬─────────────────────┘             │
└───────────────────────────────────┼──────────────────────────────────┘
                                    ▼
┌───────────────────────────────────────────────────────────────────────┐
│  PHASE 2: 규칙 기반 자동 분류                                          │
│                                                                       │
│  원시결과 ──▶ ┌─────────────┐                                         │
│              │ 출처 분석     │──▶ .go.kr / 블로그 / 뉴스 / 기타        │
│              │ 키워드 탐지   │──▶ 모집공고 신호 / 광고 신호 / 뉴스 신호 │
│              │ 날짜 필터     │──▶ 최근(30일) / 과거 / 판단불가          │
│              │ 점수 산정     │──▶ 실제공고 가능성 Score (0~100)        │
│              └──────┬──────┘                                         │
│                     ▼                                                │
│         ┌──────────────────────────────────┐                         │
│         │  자동분류 결과                     │                         │
│         │  ✅ 실제공고 후보 (Score ≥ 60)     │──────┐                  │
│         │  📢 광고/홍보    (광고 신호 탐지)   │      │                  │
│         │  📰 뉴스        (뉴스 출처)        │      │                  │
│         │  📁 과거공고     (날짜 초과)        │──▶ 추적시트 기록       │
│         │  ❓ 판단보류     (Score 40~59)     │──────┤                  │
│         │  ❌ 무관         (Score < 40)      │      │                  │
│         └──────────────────────────────────┘      │                  │
└───────────────────────────────────────────────────┼──────────────────┘
                                                    ▼
┌───────────────────────────────────────────────────────────────────────┐
│  PHASE 3: Gemini AI 정밀 판단                                          │
│                                                                       │
│  실제공고 후보 + 판단보류 ──▶ ┌─────────────────────────┐              │
│                              │ Gemini 2.0 Flash         │              │
│                              │                          │              │
│                              │ • 공고 진위 판별          │              │
│                              │ • 핵심정보 추출           │              │
│                              │   (마감일, 자격요건 등)   │              │
│                              │ • 기관명/공고유형 확인     │              │
│                              │ • 확신도 스코어           │              │
│                              └────────────┬────────────┘              │
│                                           ▼                           │
│                              ┌─────────────────────────┐              │
│                              │ 최종 판정 결과            │              │
│                              │ 🔴 긴급: 마감 임박 공고   │              │
│                              │ 🟢 신규: 확인된 실제 공고  │              │
│                              │ 🟡 주의: 추가 확인 필요    │              │
│                              │ ⚪ 해제: 공고 아님 확정    │              │
│                              └────────────┬────────────┘              │
└───────────────────────────────────────────┼───────────────────────────┘
                                            ▼
┌───────────────────────────────────────────────────────────────────────┐
│  PHASE 4: 리포팅 & 대시보드                                            │
│                                                                       │
│  ┌─────────────────┐    ┌──────────────────┐   ┌──────────────────┐  │
│  │ 📧 이메일 리포트  │    │ 📊 구글시트 대시보드│   │ 📁 과거공고 추적  │  │
│  │                  │    │                   │   │                  │  │
│  │ • 긴급공고 알림   │    │ • 일별 검색 현황   │   │ • 기관별 주기    │  │
│  │ • 신규공고 목록   │    │ • 분류별 통계      │   │ • 다음 예상 시기  │  │
│  │ • 과거공고 알림   │    │ • 기관별 히스토리   │   │ • 자동 알림      │  │
│  │ • 실행 로그      │    │ • 필터/정렬 뷰     │   │                  │  │
│  └─────────────────┘    └──────────────────┘   └──────────────────┘  │
└───────────────────────────────────────────────────────────────────────┘
```

---

## 💡 추가 제안: 더 나은 검색 전략

### 기존 계획의 문제점과 개선안

```
❌ 기존: 860개 기관 × 3개 키워드 × 2개 검색유형 = 5,160 API 호출/회
   → Google Apps Script 6분 제한 초과
   → 비효율적 (대부분 결과 없음)

✅ 개선: 하이브리드 2단계 검색 전략
```

```
┌─────────────────────────────────────────────────────────────────┐
│  1단계: 광역 검색 (매일, ~30 API 호출)                            │
│                                                                  │
│  일반 키워드로 검색 → 결과에서 기관목록과 매칭                      │
│  "노무자문 모집 공고", "자문노무사 모집", "노무사 위촉 공고" 등     │
│  × blog/web/news 3유형 × 상위 100건 = ~30 호출                   │
│                                                                  │
│  + 나라장터 API "노무" 키워드 용역입찰 검색 = ~5 호출              │
└─────────────────────────┬───────────────────────────────────────┘
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│  2단계: 정밀 검색 (주 1회, ~200 API 호출)                          │
│                                                                  │
│  과거 공고 이력이 있는 기관 (약 100개) 개별 검색                    │
│  특히 "다음 예상 공고 시기"에 해당하는 기관 집중 모니터링            │
│  100기관 × 2키워드 = ~200 호출                                    │
└─────────────────────────────────────────────────────────────────┘
```

### 추가 데이터 소스 제안

| 소스 | 장점 | API | 비용 |
|------|------|-----|------|
| **나라장터 (g2b.go.kr)** | 공공기관 용역입찰 공식 채널 | 공공데이터포털 API 제공 | 무료 |
| **정부24** | 정부 공고 통합 | 일부 API 제공 | 무료 |
| **각 기관 RSS** | 새 공고 실시간 감지 | RSS 피드 파싱 | 무료 |
| **네이버 검색** | 블로그/웹/뉴스 포괄 검색 | Naver Open API | 무료 |

---

## 📋 구글 시트 설계

### Sheet 1: `기관목록`

| 열 | 필드명 | 예시 | 설명 |
|----|--------|------|------|
| A | 기관코드 | PUB001 | 고유 식별자 |
| B | 기관명 | 한국토지주택공사 | 검색 키워드로 사용 |
| C | 기관약칭 | LH | 추가 검색 키워드 |
| D | 카테고리 | 공기업/준정부/기타 | 기관 분류 |
| E | 홈페이지 | www.lh.or.kr | 공고 확인용 |
| F | 과거공고횟수 | 3 | 자동 집계 |
| G | 마지막공고일 | 2024-06-15 | 자동 업데이트 |
| H | 선발주기(월) | 24 | 수동 입력/AI 추정 |
| I | 다음예상시기 | 2026-06 | 자동 계산 |
| J | 모니터링등급 | A/B/C | A:매일, B:주간, C:월간 |
| K | 마지막검색일 | 2025-07-11 | 자동 업데이트 |
| L | 비고 | | 수동 메모 |

### Sheet 2: `검색결과_원본`

| 열 | 필드명 | 설명 |
|----|--------|------|
| A | 검색ID | 자동생성 UUID |
| B | 검색일시 | 타임스탬프 |
| C | 검색어 | 사용된 검색 쿼리 |
| D | 검색유형 | blog/web/news/g2b |
| E | 제목 | 검색결과 제목 (HTML 태그 제거) |
| F | 링크 | URL |
| G | 설명 | 요약/스니펫 |
| H | 출처명 | 블로거명/사이트명 |
| I | 게시일 | YYYY-MM-DD |
| J | 매칭기관 | 기관목록과 매칭된 기관명 |
| K | 1차분류 | 규칙기반 분류 결과 |
| L | 분류점수 | 0~100 |
| M | AI분류 | Gemini 분류 결과 |
| N | AI확신도 | 0.0~1.0 |
| O | AI요약 | 핵심정보 요약 |
| P | 최종상태 | 긴급/신규/주의/해제/무관 |
| Q | 중복여부 | TRUE/FALSE |
| R | 처리완료 | TRUE/FALSE |

### Sheet 3: `과거공고_추적`

| 열 | 필드명 | 설명 |
|----|--------|------|
| A | 기관명 | |
| B | 공고제목 | |
| C | 공고연도 | |
| D | 공고월 | |
| E | 마감일 | |
| F | 계약기간 | 예: 2년 |
| G | 다음예상시기 | 자동계산 |
| H | 알림설정 | 예상시기 1개월 전 알림 |
| I | 링크 | |
| J | 비고 | |

### Sheet 4: `설정`

| 키 | 값 | 설명 |
|----|---|------|
| 광역검색_키워드 | 노무자문 모집,자문노무사 모집,... | 쉼표 구분 |
| 정밀검색_키워드 | 노무자문,자문노무사 | 기관명과 조합 |
| 검색결과수 | 20 | API당 가져올 결과 수 |
| 최근기준_일수 | 30 | 이 이내를 최근으로 판단 |
| 리포트_이메일 | user@gmail.com | |
| 배치_크기 | 100 | 1회 실행당 처리 기관수 |

### Sheet 5: `실행로그`

| 열 | 필드명 |
|----|--------|
| A | 실행일시 |
| B | 실행유형 (광역/정밀/AI분석/리포트) |
| C | 처리건수 |
| D | 신규발견 |
| E | 소요시간(초) |
| F | 오류내용 |
| G | 상세로그 |

---

## 🔧 핵심 구현 코드 (Google Apps Script)

### 파일 구조

```
📁 Google Apps Script Project
├── 00_Config.gs          ← 설정 및 상수
├── 01_NaverSearch.gs     ← 네이버 API 검색
├── 02_G2BSearch.gs       ← 나라장터 API (선택)
├── 03_Classifier.gs      ← 규칙 기반 분류
├── 04_GeminiAI.gs        ← Gemini AI 판단
├── 05_SheetManager.gs    ← 구글시트 CRUD
├── 06_Reporter.gs        ← 이메일 리포트
├── 07_Main.gs            ← 메인 오케스트레이터
└── 08_Setup.gs           ← 초기 설정/트리거
```

---

### `00_Config.gs` — 설정 및 상수

```javascript
/**
 * ============================================================
 * 00_Config.gs - 전역 설정
 * ============================================================
 */

function getConfig() {
  const props = PropertiesService.getScriptProperties();
  return {
    // === API Keys ===
    NAVER_CLIENT_ID: props.getProperty('NAVER_CLIENT_ID'),
    NAVER_CLIENT_SECRET: props.getProperty('NAVER_CLIENT_SECRET'),
    GEMINI_API_KEY: props.getProperty('GEMINI_API_KEY'),
    
    // === 스프레드시트 ===
    SPREADSHEET_ID: props.getProperty('SPREADSHEET_ID'),
    
    // === 시트명 ===
    SHEET: {
      INSTITUTIONS: '기관목록',
      RAW_RESULTS:  '검색결과_원본',
      PAST_TRACK:   '과거공고_추적',
      SETTINGS:     '설정',
      LOG:          '실행로그',
      DASHBOARD:    '대시보드'
    },
    
    // === 검색 설정 ===
    BROAD_KEYWORDS: [
      '노무자문 모집',
      '자문노무사 모집',
      '노무자문 공고',
      '노무사 위촉 공고',
      '노무자문 용역',
      '노무자문 제안요청',
      '노무관리 자문 모집',
      '공인노무사 모집'
    ],
    TARGETED_KEYWORDS: ['노무자문', '자문노무사 모집'],
    SEARCH_DISPLAY: 20,      // API 호출당 결과 수 (최대 100)
    BATCH_SIZE: 100,          // 정밀검색 시 1회 처리 기관 수
    
    // === 분류 설정 ===
    DAYS_RECENT: 30,          // 최근 공고 기준 (일)
    SCORE_REAL_THRESHOLD: 60, // 이 이상이면 실제공고 후보
    SCORE_MAYBE_THRESHOLD: 40,// 이 이상이면 판단보류
    
    // === Gemini 설정 ===
    GEMINI_MODEL: 'gemini-2.0-flash',
    GEMINI_ENDPOINT: 'https://generativelanguage.googleapis.com/v1beta/models/',
    
    // === 리포트 ===
    REPORT_EMAIL: props.getProperty('REPORT_EMAIL'),
    
    // === 네이버 API 엔드포인트 ===
    NAVER_API: {
      BLOG: 'https://openapi.naver.com/v1/search/blog.json',
      WEB:  'https://openapi.naver.com/v1/search/webkr.json',
      NEWS: 'https://openapi.naver.com/v1/search/news.json'
    }
  };
}

// 분류 라벨 상수
const CATEGORY = {
  REAL_POSTING:  '🟢 실제공고후보',
  ADVERTISEMENT: '📢 광고/홍보',
  NEWS:          '📰 뉴스기사',
  PAST_POSTING:  '📁 과거공고',
  MAYBE:         '❓ 판단보류',
  IRRELEVANT:    '❌ 무관',
};

const STATUS = {
  URGENT:   '🔴 긴급(마감임박)',
  NEW:      '🟢 신규공고',
  CAUTION:  '🟡 추가확인필요',
  CLEARED:  '⚪ 공고아님',
  PENDING:  '⏳ AI판단대기',
};
```

---

### `01_NaverSearch.gs` — 네이버 API 검색

```javascript
/**
 * ============================================================
 * 01_NaverSearch.gs - 네이버 검색 API 연동
 * ============================================================
 */

/**
 * 네이버 검색 API 호출 (단일)
 * @param {string} query - 검색어
 * @param {string} type - 'blog', 'web', 'news'
 * @param {number} display - 결과 수
 * @param {string} sort - 'sim'(정확도) or 'date'(최신)
 * @returns {Array} 검색결과 배열
 */
function naverSearch(query, type, display, sort) {
  const config = getConfig();
  const endpoints = {
    'blog': config.NAVER_API.BLOG,
    'web':  config.NAVER_API.WEB,
    'news': config.NAVER_API.NEWS
  };
  
  const url = endpoints[type] 
    + '?query=' + encodeURIComponent(query)
    + '&display=' + (display || config.SEARCH_DISPLAY)
    + '&start=1'
    + '&sort=' + (sort || 'date');
  
  const options = {
    method: 'get',
    headers: {
      'X-Naver-Client-Id': config.NAVER_CLIENT_ID,
      'X-Naver-Client-Secret': config.NAVER_CLIENT_SECRET
    },
    muteHttpExceptions: true
  };
  
  try {
    const response = UrlFetchApp.fetch(url, options);
    const code = response.getResponseCode();
    
    if (code !== 200) {
      Logger.log(`[NaverSearch] API 오류 (${code}): ${response.getContentText()}`);
      return [];
    }
    
    const json = JSON.parse(response.getContentText());
    return (json.items || []).map(item => ({
      title:       stripHtml(item.title),
      link:        item.link,
      description: stripHtml(item.description),
      source:      item.bloggername || item.originallink || '',
      postdate:    formatNaverDate(item.postdate || item.pubDate),
      searchType:  type,
      searchQuery: query
    }));
    
  } catch (e) {
    Logger.log(`[NaverSearch] 예외 발생: ${e.message}`);
    return [];
  }
}

/**
 * 광역 검색 실행 - 일반 키워드로 전체 검색
 * @returns {Array} 모든 검색 결과
 */
function executeBroadSearch() {
  const config = getConfig();
  const allResults = [];
  const searchTypes = ['blog', 'web', 'news'];
  
  Logger.log(`[BroadSearch] 시작: ${config.BROAD_KEYWORDS.length}개 키워드 × ${searchTypes.length}개 유형`);
  
  for (const keyword of config.BROAD_KEYWORDS) {
    for (const type of searchTypes) {
      const results = naverSearch(keyword, type, config.SEARCH_DISPLAY, 'date');
      allResults.push(...results);
      
      // API Rate Limit 방지 (100ms 대기)
      Utilities.sleep(100);
    }
  }
  
  Logger.log(`[BroadSearch] 완료: 총 ${allResults.length}건 수집`);
  return deduplicateResults(allResults);
}

/**
 * 정밀 검색 실행 - 특정 기관명 + 키워드 조합
 * @param {Array} institutions - 검색할 기관 목록 [{name, alias}]
 * @returns {Array} 검색 결과
 */
function executeTargetedSearch(institutions) {
  const config = getConfig();
  const allResults = [];
  
  Logger.log(`[TargetedSearch] 시작: ${institutions.length}개 기관`);
  
  for (const inst of institutions) {
    for (const keyword of config.TARGETED_KEYWORDS) {
      // 기관명 + 키워드 조합
      const query = `${inst.name} ${keyword}`;
      const results = naverSearch(query, 'web', 10, 'date');
      
      // 결과에 기관명 태깅
      results.forEach(r => r.matchedInstitution = inst.name);
      allResults.push(...results);
      
      // 약칭이 있으면 약칭으로도 검색
      if (inst.alias && inst.alias.trim()) {
        const aliasQuery = `${inst.alias} ${keyword}`;
        const aliasResults = naverSearch(aliasQuery, 'web', 5, 'date');
        aliasResults.forEach(r => r.matchedInstitution = inst.name);
        allResults.push(...aliasResults);
      }
      
      Utilities.sleep(100);
    }
  }
  
  Logger.log(`[TargetedSearch] 완료: 총 ${allResults.length}건 수집`);
  return deduplicateResults(allResults);
}

/**
 * 검색결과 중복 제거 (URL 기준)
 */
function deduplicateResults(results) {
  const seen = new Set();
  const unique = [];
  
  for (const item of results) {
    // URL 정규화
    const normalizedUrl = normalizeUrl(item.link);
    if (!seen.has(normalizedUrl)) {
      seen.add(normalizedUrl);
      unique.push(item);
    }
  }
  
  Logger.log(`[Dedup] ${results.length}건 → ${unique.length}건 (${results.length - unique.length}건 중복 제거)`);
  return unique;
}

/**
 * 이전에 수집된 결과와 비교하여 신규 결과만 필터링
 */
function filterNewResults(results) {
  const ss = SpreadsheetApp.openById(getConfig().SPREADSHEET_ID);
  const sheet = ss.getSheetByName(getConfig().SHEET.RAW_RESULTS);
  
  // 기존 URL 목록 로드
  const existingUrls = new Set();
  if (sheet.getLastRow() > 1) {
    const urlColumn = sheet.getRange(2, 6, sheet.getLastRow() - 1, 1).getValues(); // F열 = 링크
    urlColumn.forEach(row => existingUrls.add(normalizeUrl(row[0])));
  }
  
  const newResults = results.filter(r => !existingUrls.has(normalizeUrl(r.link)));
  Logger.log(`[FilterNew] ${results.length}건 중 ${newResults.length}건 신규`);
  return newResults;
}

// ===== 유틸리티 =====

function stripHtml(str) {
  if (!str) return '';
  return str.replace(/<[^>]*>/g, '').replace(/&amp;/g, '&').replace(/&lt;/g, '<')
            .replace(/&gt;/g, '>').replace(/&quot;/g, '"').replace(/&apos;/g, "'")
            .replace(/&#39;/g, "'").trim();
}

function formatNaverDate(dateStr) {
  if (!dateStr) return '';
  // 블로그: "20250101" 형식
  if (/^\d{8}$/.test(dateStr)) {
    return dateStr.substring(0,4) + '-' + dateStr.substring(4,6) + '-' + dateStr.substring(6,8);
  }
  // 뉴스: "Mon, 01 Jan 2025 09:00:00 +0900" 형식
  try {
    const d = new Date(dateStr);
    return Utilities.formatDate(d, 'Asia/Seoul', 'yyyy-MM-dd');
  } catch(e) {
    return dateStr;
  }
}

function normalizeUrl(url) {
  if (!url) return '';
  return url.replace(/^https?:\/\//, '').replace(/\/+$/, '').toLowerCase();
}
```

---

### `02_G2BSearch.gs` — 나라장터 API (추가 데이터 소스)

```javascript
/**
 * ============================================================
 * 02_G2BSearch.gs - 나라장터 (공공데이터포털) API 연동
 * 
 * 공공데이터포털에서 "조달청_나라장터 용역 입찰공고 조회" API 키 필요
 * https://www.data.go.kr/data/15000848/openapi.do
 * ============================================================
 */

/**
 * 나라장터 용역 입찰공고 검색
 * @returns {Array} 노무자문 관련 입찰공고
 */
function searchG2B() {
  const config = getConfig();
  const apiKey = PropertiesService.getScriptProperties().getProperty('DATA_GO_KR_API_KEY');
  
  if (!apiKey) {
    Logger.log('[G2B] API 키 미설정 - 나라장터 검색 건너뜀');
    return [];
  }
  
  const today = new Date();
  const thirtyDaysAgo = new Date(today.getTime() - 30 * 24 * 60 * 60 * 1000);
  
  const fromDate = Utilities.formatDate(thirtyDaysAgo, 'Asia/Seoul', 'yyyyMMdd') + '0000';
  const toDate = Utilities.formatDate(today, 'Asia/Seoul', 'yyyyMMdd') + '2359';
  
  const keywords = ['노무', '노무사', '노무자문', '노무관리'];
  const allResults = [];
  
  for (const keyword of keywords) {
    const url = 'https://apis.data.go.kr/1230000/BidPublicInfoService04/getList'
      + '?serviceKey=' + encodeURIComponent(apiKey)
      + '&pageNo=1'
      + '&numOfRows=100'
      + '&type=json'
      + '&bidNtceNm=' + encodeURIComponent(keyword)  // 공고명에 키워드 포함
      + '&inqryBgnDt=' + fromDate
      + '&inqryEndDt=' + toDate
      + '&bidClseDt=' + toDate;   // 마감일이 아직 안 지난 것
    
    try {
      const response = UrlFetchApp.fetch(url, { muteHttpExceptions: true });
      const json = JSON.parse(response.getContentText());
      
      const items = json?.response?.body?.items || [];
      
      for (const item of items) {
        allResults.push({
          title:       item.bidNtceNm || '',                    // 공고명
          link:        item.bidNtceDtlUrl || '',                // 상세 URL
          description: `발주기관: ${item.dminsttNm || ''} | 마감: ${item.bidClseDt || ''}`,
          source:      item.dminsttNm || '나라장터',             // 발주기관명
          postdate:    formatG2BDate(item.bidNtceDt),           // 공고일
          searchType:  'g2b',
          searchQuery: keyword,
          matchedInstitution: item.dminsttNm || '',
          deadline:    formatG2BDate(item.bidClseDt),           // 마감일
          g2bNumber:   item.bidNtceNo || ''                     // 공고번호
        });
      }
      
      Utilities.sleep(200);
    } catch (e) {
      Logger.log(`[G2B] 검색 오류 (${keyword}): ${e.message}`);
    }
  }
  
  Logger.log(`[G2B] 완료: ${allResults.length}건 수집`);
  return deduplicateResults(allResults);
}

function formatG2BDate(dateStr) {
  if (!dateStr || dateStr.length < 8) return '';
  return dateStr.substring(0,4) + '-' + dateStr.substring(4,6) + '-' + dateStr.substring(6,8);
}
```

---

### `03_Classifier.gs` — 규칙 기반 자동 분류

```javascript
/**
 * ============================================================
 * 03_Classifier.gs - 규칙 기반 자동 분류 엔진
 * ============================================================
 * 
 * 분류 로직:
 * 1. 출처(URL) 분석 → 공공기관/.go.kr / 블로그 / 뉴스 구분
 * 2. 제목+설명 키워드 분석 → 모집 신호 / 광고 신호 점수 산정
 * 3. 날짜 분석 → 최근/과거 구분
 * 4. 종합 점수 → 분류 결정
 */

/**
 * 단일 검색결과 분류
 * @param {Object} item - 검색결과 아이템
 * @param {Array} institutionNames - 기관명 목록 (매칭용)
 * @returns {Object} 분류 결과가 추가된 아이템
 */
function classifyItem(item, institutionNames) {
  const config = getConfig();
  const text = (item.title + ' ' + item.description).toLowerCase();
  const url = (item.link || '').toLowerCase();
  
  let score = 50; // 기본 점수
  let signals = [];
  let category = CATEGORY.MAYBE;
  
  // ===== 1단계: 출처(URL) 분석 =====
  const sourceAnalysis = analyzeSource(url);
  score += sourceAnalysis.score;
  signals.push(...sourceAnalysis.signals);
  
  // ===== 2단계: 모집공고 신호 탐지 =====
  const recruitSignals = detectRecruitmentSignals(text);
  score += recruitSignals.score;
  signals.push(...recruitSignals.signals);
  
  // ===== 3단계: 광고/홍보 신호 탐지 =====
  const adSignals = detectAdvertisementSignals(text, url);
  score -= adSignals.penalty;
  signals.push(...adSignals.signals);
  
  // ===== 4단계: 뉴스 신호 탐지 =====
  const newsSignals = detectNewsSignals(text, url, item.searchType);
  if (newsSignals.isNews) {
    category = CATEGORY.NEWS;
    score -= 20;
    signals.push('뉴스기사 감지');
  }
  
  // ===== 5단계: 날짜 분석 =====
  const dateAnalysis = analyzeDate(item.postdate, text);
  if (dateAnalysis.isPast) {
    score -= 15;
    signals.push(`과거 게시물 (${item.postdate})`);
  }
  if (dateAnalysis.hasPastYearRef) {
    signals.push(`과거연도 언급: ${dateAnalysis.yearRef}`);
  }
  
  // ===== 6단계: 기관명 매칭 =====
  const matchedInst = item.matchedInstitution || matchInstitution(text, institutionNames);
  if (matchedInst) {
    score += 10;
    signals.push(`기관 매칭: ${matchedInst}`);
  }
  
  // ===== 7단계: 최종 분류 결정 =====
  score = Math.max(0, Math.min(100, score)); // 0~100 클램핑
  
  if (newsSignals.isNews) {
    category = CATEGORY.NEWS;
  } else if (adSignals.penalty >= 25) {
    category = CATEGORY.ADVERTISEMENT;
  } else if (dateAnalysis.isPast && !recruitSignals.hasStrongSignal) {
    category = CATEGORY.PAST_POSTING;
  } else if (score >= config.SCORE_REAL_THRESHOLD) {
    category = CATEGORY.REAL_POSTING;
  } else if (score >= config.SCORE_MAYBE_THRESHOLD) {
    category = CATEGORY.MAYBE;
  } else {
    category = CATEGORY.IRRELEVANT;
  }
  
  return {
    ...item,
    matchedInstitution: matchedInst,
    category: category,
    score: score,
    signals: signals.join(' | '),
    needsAIReview: (category === CATEGORY.REAL_POSTING || category === CATEGORY.MAYBE)
  };
}

// ===== 분석 서브 함수들 =====

function analyzeSource(url) {
  const result = { score: 0, signals: [] };
  
  // 공공기관 도메인 패턴
  const govPatterns = [
    /\.go\.kr/,
    /\.or\.kr/,
    /\.re\.kr/,
    /g2b\.go\.kr/,
    /나라장터/
  ];
  
  // 블로그/카페 패턴
  const blogPatterns = [
    /blog\.naver\.com/,
    /m\.blog\.naver\.com/,
    /cafe\.naver\.com/,
    /tistory\.com/,
    /brunch\.co\.kr/,
    /velog\.io/
  ];
  
  // 뉴스 패턴
  const newsPatterns = [
    /news\.naver\.com/,
    /n\.news\.naver\.com/,
    /newsis\.com/,
    /yna\.co\.kr/,
    /yonhapnews/,
    /chosun\.com/,
    /donga\.com/,
    /hani\.co\.kr/,
    /khan\.co\.kr/,
    /hankyung\.com/,
    /mk\.co\.kr/,
    /edaily/,
    /newspim/,
    /etnews/
  ];
  
  // 노무법인 블로그 패턴 (광고 가능성 높음)
  const laborFirmPatterns = [
    /노무법인/,
    /노무사사무소/,
    /노무사사무실/,
    /labor/
  ];
  
  if (govPatterns.some(p => p.test(url))) {
    result.score += 20;
    result.signals.push('공공기관 도메인');
  }
  
  if (blogPatterns.some(p => p.test(url))) {
    result.score -= 10;
    result.signals.push('블로그 출처');
  }
  
  if (newsPatterns.some(p => p.test(url))) {
    result.score -= 5;
    result.signals.push('뉴스 출처');
  }
  
  return result;
}

function detectRecruitmentSignals(text) {
  const result = { score: 0, signals: [], hasStrongSignal: false };
  
  // 강한 모집 신호
  const strongSignals = [
    { pattern: /모집\s*공고/, label: '모집공고', score: 25 },
    { pattern: /제안\s*요청/, label: '제안요청', score: 25 },
    { pattern: /입찰\s*공고/, label: '입찰공고', score: 20 },
    { pattern: /용역\s*(입찰|공고|모집)/, label: '용역입찰/공고', score: 20 },
    { pattern: /자문\s*노무사.*모집/, label: '자문노무사모집', score: 30 },
    { pattern: /노무\s*자문.*모집/, label: '노무자문모집', score: 30 },
    { pattern: /노무사\s*위촉.*공고/, label: '노무사위촉공고', score: 25 },
  ];
  
  // 보통 모집 신호
  const normalSignals = [
    { pattern: /접수\s*기간/, label: '접수기간', score: 15 },
    { pattern: /제출\s*기한/, label: '제출기한', score: 15 },
    { pattern: /마감\s*일/, label: '마감일', score: 10 },
    { pattern: /지원\s*자격/, label: '지원자격', score: 10 },
    { pattern: /선정\s*공고/, label: '선정공고', score: 10 },
    { pattern: /위탁.*공고/, label: '위탁공고', score: 10 },
    { pattern: /공고\s*기간/, label: '공고기간', score: 10 },
    { pattern: /참가\s*신청/, label: '참가신청', score: 15 },
  ];
  
  for (const sig of strongSignals) {
    if (sig.pattern.test(text)) {
      result.score += sig.score;
      result.signals.push(`✓ ${sig.label}`);
      result.hasStrongSignal = true;
    }
  }
  
  for (const sig of normalSignals) {
    if (sig.pattern.test(text)) {
      result.score += sig.score;
      result.signals.push(`+ ${sig.label}`);
    }
  }
  
  return result;
}

function detectAdvertisementSignals(text, url) {
  const result = { penalty: 0, signals: [] };
  
  const adSignals = [
    { pattern: /선정\s*되었/, label: '선정결과 보고', penalty: 20 },
    { pattern: /계약\s*체결/, label: '계약체결 보고', penalty: 15 },
    { pattern: /자문.*맡게/, label: '수임 보고', penalty: 20 },
    { pattern: /위촉\s*되었/, label: '위촉결과 보고', penalty: 15 },
    { pattern: /수행\s*하고\s*있/, label: '수행중 홍보', penalty: 15 },
    { pattern: /업무\s*협약/, label: '협약 보도', penalty: 10 },
    { pattern: /보도\s*자료/, label: '보도자료', penalty: 10 },
    { pattern: /노무법인\s*[가-힣]+\s*(이|가|에서|은|는)/, label: '노무법인 홍보', penalty: 25 },
    { pattern: /자문.*수행.*실적/, label: '실적 홍보', penalty: 20 },
    { pattern: /전문\s*노무사.*상담/, label: '상담 광고', penalty: 15 },
  ];
  
  for (const sig of adSignals) {
    if (sig.pattern.test(text)) {
      result.penalty += sig.penalty;
      result.signals.push(`⚠ ${sig.label}`);
    }
  }
  
  // 블로그 출처 + 노무법인 관련 = 광고 확률 높음
  if (/blog|tistory|brunch/.test(url) && /노무(법인|사사무)/.test(text)) {
    result.penalty += 20;
    result.signals.push('⚠ 노무법인 블로그 홍보글');
  }
  
  return result;
}

function detectNewsSignals(text, url, searchType) {
  if (searchType === 'news') return { isNews: true };
  
  const newsPatterns = [
    /기자\s*[=|]/, /\[.*기자\]/, /특파원/, /앵커/,
    /뉴스/, /신문/, /일보/, /매일/
  ];
  
  const newsUrlPatterns = [
    /news/, /press/, /media/, /journal/
  ];
  
  const isNews = newsPatterns.some(p => p.test(text)) || 
                 newsUrlPatterns.some(p => p.test(url));
  
  return { isNews };
}

function analyzeDate(postdate, text) {
  const result = { isPast: false, hasPastYearRef: false, yearRef: '' };
  const config = getConfig();
  
  if (postdate) {
    const postDate = new Date(postdate);
    const today = new Date();
    const diffDays = (today - postDate) / (1000 * 60 * 60 * 24);
    
    if (diffDays > config.DAYS_RECENT) {
      result.isPast = true;
    }
  }
  
  // 과거 연도 참조 탐지
  const currentYear = new Date().getFullYear();
  const yearPattern = /20(1\d|2[0-5])년/g;
  let match;
  while ((match = yearPattern.exec(text)) !== null) {
    const year = parseInt('20' + match[1]);
    if (year < currentYear) {
      result.hasPastYearRef = true;
      result.yearRef = year + '년';
    }
  }
  
  return result;
}

function matchInstitution(text, institutionNames) {
  for (const name of institutionNames) {
    if (text.includes(name.toLowerCase())) {
      return name;
    }
  }
  return '';
}

/**
 * 전체 검색결과 일괄 분류
 * @param {Array} results - 검색결과 배열
 * @returns {Object} 분류된 결과 { realCandidates, ads, news, past, maybe, irrelevant }
 */
function classifyAllResults(results) {
  // 기관명 목록 로드
  const institutionNames = loadInstitutionNames();
  
  const classified = {
    realCandidates: [],
    advertisements: [],
    news: [],
    pastPostings: [],
    maybe: [],
    irrelevant: [],
    all: []
  };
  
  for (const item of results) {
    const result = classifyItem(item, institutionNames);
    classified.all.push(result);
    
    switch (result.category) {
      case CATEGORY.REAL_POSTING:  classified.realCandidates.push(result); break;
      case CATEGORY.ADVERTISEMENT: classified.advertisements.push(result); break;
      case CATEGORY.NEWS:          classified.news.push(result); break;
      case CATEGORY.PAST_POSTING:  classified.pastPostings.push(result); break;
      case CATEGORY.MAYBE:         classified.maybe.push(result); break;
      case CATEGORY.IRRELEVANT:    classified.irrelevant.push(result); break;
    }
  }
  
  Logger.log(`[Classifier] 분류 완료:
    실제공고후보: ${classified.realCandidates.length}
    광고/홍보: ${classified.advertisements.length}
    뉴스: ${classified.news.length}
    과거공고: ${classified.pastPostings.length}
    판단보류: ${classified.maybe.length}
    무관: ${classified.irrelevant.length}`
  );
  
  return classified;
}

function loadInstitutionNames() {
  const config = getConfig();
  const ss = SpreadsheetApp.openById(config.SPREADSHEET_ID);
  const sheet = ss.getSheetByName(config.SHEET.INSTITUTIONS);
  
  if (!sheet || sheet.getLastRow() < 2) return [];
  
  const data = sheet.getRange(2, 2, sheet.getLastRow() - 1, 2).getValues(); // B:기관명, C:약칭
  const names = [];
  data.forEach(row => {
    if (row[0]) names.push(row[0].toString().trim());
    if (row[1]) names.push(row[1].toString().trim());
  });
  
  return names;
}
```

---

### `04_GeminiAI.gs` — Gemini AI 정밀 판단

```javascript
/**
 * ============================================================
 * 04_GeminiAI.gs - Gemini AI 기반 정밀 분석
 * ============================================================
 */

/**
 * Gemini API 호출
 * @param {string} prompt - 프롬프트
 * @returns {string} AI 응답
 */
function callGemini(prompt) {
  const config = getConfig();
  const url = config.GEMINI_ENDPOINT + config.GEMINI_MODEL + ':generateContent'
    + '?key=' + config.GEMINI_API_KEY;
  
  const payload = {
    contents: [{
      parts: [{ text: prompt }]
    }],
    generationConfig: {
      temperature: 0.1,     // 낮은 온도 = 일관된 판단
      topP: 0.8,
      maxOutputTokens: 1024,
      responseMimeType: "application/json"  // JSON 응답 강제
    }
  };
  
  const options = {
    method: 'post',
    contentType: 'application/json',
    payload: JSON.stringify(payload),
    muteHttpExceptions: true
  };
  
  try {
    const response = UrlFetchApp.fetch(url, options);
    const json = JSON.parse(response.getContentText());
    
    if (json.error) {
      Logger.log(`[Gemini] API 오류: ${json.error.message}`);
      return null;
    }
    
    const text = json.candidates?.[0]?.content?.parts?.[0]?.text;
    return text;
  } catch (e) {
    Logger.log(`[Gemini] 예외: ${e.message}`);
    return null;
  }
}

/**
 * 검색결과 AI 분석
 * @param {Object} item - 분류된 검색결과 아이템
 * @returns {Object} AI 분석 결과
 */
function analyzeWithAI(item) {
  const prompt = buildAnalysisPrompt(item);
  const response = callGemini(prompt);
  
  if (!response) {
    return {
      aiCategory: '분석실패',
      aiConfidence: 0,
      aiSummary: 'AI 분석 실패',
      deadline: null,
      institutionName: item.matchedInstitution || '',
      finalStatus: STATUS.CAUTION
    };
  }
  
  try {
    const result = JSON.parse(response);
    
    // 최종 상태 결정
    let finalStatus = STATUS.PENDING;
    if (result.분류 === '실제공고' && result.확신도 >= 0.7) {
      // 마감일 확인
      if (result.마감일) {
        const deadline = new Date(result.마감일);
        const today = new Date();
        const daysLeft = (deadline - today) / (1000 * 60 * 60 * 24);
        finalStatus = daysLeft <= 7 ? STATUS.URGENT : STATUS.NEW;
      } else {
        finalStatus = STATUS.NEW;
      }
    } else if (result.분류 === '실제공고' && result.확신도 >= 0.4) {
      finalStatus = STATUS.CAUTION;
    } else {
      finalStatus = STATUS.CLEARED;
    }
    
    return {
      aiCategory: result.분류 || '',
      aiConfidence: result.확신도 || 0,
      aiSummary: result.핵심정보 || '',
      aiReason: result.판단근거 || '',
      deadline: result.마감일 || '',
      institutionName: result.기관명 || item.matchedInstitution || '',
      qualifications: result.자격요건 || '',
      contractPeriod: result.계약기간 || '',
      finalStatus: finalStatus
    };
  } catch (e) {
    Logger.log(`[Gemini] JSON 파싱 실패: ${e.message}`);
    return {
      aiCategory: '파싱실패',
      aiConfidence: 0,
      aiSummary: response.substring(0, 200),
      finalStatus: STATUS.CAUTION
    };
  }
}

/**
 * AI 분석 프롬프트 생성
 */
function buildAnalysisPrompt(item) {
  return `당신은 공공기관 노무자문 모집공고를 판별하는 전문 분석가입니다.

## 배경 정보
- 공공기관은 외부 공인노무사에게 노무자문을 위탁하기 위해 모집공고를 게시합니다.
- 실제 모집공고에는 접수기간, 자격요건, 제출서류 등의 정보가 포함됩니다.
- 광고성 콘텐츠는 노무법인이 수임 실적을 홍보하거나, 선정 결과를 보도하는 내용입니다.
- 과거공고는 이미 마감된 공고이지만, 향후 재공고 시기를 예측하는 데 유용합니다.

## 분석 대상
- 제목: ${item.title}
- 설명: ${item.description}
- 출처 URL: ${item.link}
- 출처명: ${item.source}
- 게시일: ${item.postdate}
- 검색 유형: ${item.searchType}
- 규칙기반 분류: ${item.category}
- 규칙기반 점수: ${item.score}
- 탐지된 신호: ${item.signals}

## 분류 기준
1. **실제공고**: 현재 접수 가능한(또는 곧 시작되는) 노무자문/자문노무사 모집 공고
2. **광고**: 노무법인/노무사의 홍보, 수임 보고, 선정 결과 자랑
3. **뉴스**: 언론 보도 기사
4. **과거공고**: 이미 마감되었거나 과거 연도의 공고
5. **무관**: 노무자문 모집과 전혀 관련 없는 내용

## 응답 형식 (반드시 아래 JSON 구조를 준수)
{
  "분류": "실제공고|광고|뉴스|과거공고|무관",
  "확신도": 0.0에서 1.0 사이의 숫자,
  "판단근거": "이렇게 판단한 구체적인 이유를 2~3문장으로 설명",
  "기관명": "공고를 낸 기관명 (추출 가능한 경우) 또는 빈 문자열",
  "마감일": "YYYY-MM-DD 형식의 마감일 (추출 가능한 경우) 또는 빈 문자열",
  "자격요건": "자격요건 요약 (추출 가능한 경우) 또는 빈 문자열",
  "계약기간": "계약기간 (예: 1년, 2년) 또는 빈 문자열",
  "핵심정보": "이 공고의 핵심 내용을 3문장 이내로 요약"
}`;
}

/**
 * 실제공고 후보 + 판단보류 건 일괄 AI 분석
 * @param {Array} items - AI 분석이 필요한 아이템들
 * @returns {Array} AI 분석 결과가 추가된 아이템들
 */
function batchAIAnalysis(items) {
  Logger.log(`[AI] ${items.length}건 AI 분석 시작`);
  const results = [];
  
  for (let i = 0; i < items.length; i++) {
    const item = items[i];
    Logger.log(`[AI] ${i + 1}/${items.length}: ${item.title.substring(0, 50)}...`);
    
    const aiResult = analyzeWithAI(item);
    results.push({ ...item, ...aiResult });
    
    // Rate limit 방지 (Gemini Free: 15 RPM)
    if (i < items.length - 1) {
      Utilities.sleep(4500); // 4.5초 대기 → ~13 RPM
    }
  }
  
  Logger.log(`[AI] 분석 완료`);
  return results;
}

/**
 * 과거공고에서 선발 주기를 AI로 분석
 */
function analyzePastPostingCycle(pastItems) {
  if (pastItems.length === 0) return [];
  
  // 같은 기관의 과거 공고를 모아서 주기 분석
  const byInstitution = {};
  for (const item of pastItems) {
    const inst = item.matchedInstitution || '미상';
    if (!byInstitution[inst]) byInstitution[inst] = [];
    byInstitution[inst].push(item);
  }
  
  const cycleResults = [];
  
  for (const [inst, items] of Object.entries(byInstitution)) {
    if (inst === '미상') continue;
    
    const prompt = `다음은 "${inst}" 기관의 과거 노무자문 관련 공고 목록입니다.
이 기관의 노무자문 선발 주기를 분석해주세요.

공고 목록:
${items.map(i => `- ${i.postdate}: ${i.title}`).join('\n')}

응답 형식 (JSON):
{
  "기관명": "${inst}",
  "추정주기_월": 숫자(개월 단위),
  "마지막공고일": "YYYY-MM-DD",
  "다음예상시기": "YYYY-MM",
  "확신도": 0.0~1.0,
  "분석근거": "분석 근거 설명"
}`;
    
    const response = callGemini(prompt);
    if (response) {
      try {
        cycleResults.push(JSON.parse(response));
      } catch (e) {}
    }
    Utilities.sleep(4500);
  }
  
  return cycleResults;
}
```

---

### `05_SheetManager.gs` — 구글시트 CRUD

```javascript
/**
 * ============================================================
 * 05_SheetManager.gs - 구글 시트 데이터 관리
 * ============================================================
 */

/**
 * 검색 결과를 원본 시트에 저장
 */
function saveRawResults(classifiedResults) {
  const config = getConfig();
  const ss = SpreadsheetApp.openById(config.SPREADSHEET_ID);
  let sheet = ss.getSheetByName(config.SHEET.RAW_RESULTS);
  
  if (!sheet) {
    sheet = createRawResultsSheet(ss);
  }
  
  const timestamp = new Date();
  const rows = classifiedResults.all.map(item => [
    Utilities.getUuid(),                          // A: 검색ID
    timestamp,                                     // B: 검색일시
    item.searchQuery || '',                        // C: 검색어
    item.searchType || '',                         // D: 검색유형
    item.title || '',                              // E: 제목
    item.link || '',                               // F: 링크
    item.description || '',                        // G: 설명
    item.source || '',                             // H: 출처명
    item.postdate || '',                           // I: 게시일
    item.matchedInstitution || '',                 // J: 매칭기관
    item.category || '',                           // K: 1차분류
    item.score || 0,                               // L: 분류점수
    '',                                            // M: AI분류 (나중에 업데이트)
    '',                                            // N: AI확신도
    '',                                            // O: AI요약
    item.needsAIReview ? STATUS.PENDING : '',      // P: 최종상태
    false,                                         // Q: 중복여부
    false                                          // R: 처리완료
  ]);
  
  if (rows.length > 0) {
    sheet.getRange(sheet.getLastRow() + 1, 1, rows.length, rows[0].length)
         .setValues(rows);
  }
  
  Logger.log(`[SheetManager] ${rows.length}건 저장 완료`);
  return rows.length;
}

/**
 * AI 분석 결과 업데이트
 */
function updateAIResults(aiResults) {
  const config = getConfig();
  const ss = SpreadsheetApp.openById(config.SPREADSHEET_ID);
  const sheet = ss.getSheetByName(config.SHEET.RAW_RESULTS);
  
  if (!sheet || sheet.getLastRow() < 2) return;
  
  // URL을 키로 행 번호 매핑
  const data = sheet.getDataRange().getValues();
  const urlToRow = {};
  for (let i = 1; i < data.length; i++) {
    urlToRow[normalizeUrl(data[i][5])] = i + 1; // F열(인덱스5) = 링크
  }
  
  for (const item of aiResults) {
    const rowNum = urlToRow[normalizeUrl(item.link)];
    if (rowNum) {
      sheet.getRange(rowNum, 13).setValue(item.aiCategory || '');     // M: AI분류
      sheet.getRange(rowNum, 14).setValue(item.aiConfidence || 0);    // N: AI확신도
      sheet.getRange(rowNum, 15).setValue(item.aiSummary || '');      // O: AI요약
      sheet.getRange(rowNum, 16).setValue(item.finalStatus || '');    // P: 최종상태
    }
  }
  
  Logger.log(`[SheetManager] ${aiResults.length}건 AI 결과 업데이트 완료`);
}

/**
 * 과거공고 추적 시트 업데이트
 */
function updatePastPostingTracker(pastItems, cycleAnalysis) {
  const config = getConfig();
  const ss = SpreadsheetApp.openById(config.SPREADSHEET_ID);
  let sheet = ss.getSheetByName(config.SHEET.PAST_TRACK);
  
  if (!sheet) {
    sheet = ss.insertSheet(config.SHEET.PAST_TRACK);
    sheet.getRange(1, 1, 1, 10).setValues([
      ['기관명', '공고제목', '공고연도', '공고월', '마감일', 
       '계약기간', '다음예상시기', '알림설정', '링크', '비고']
    ]);
    sheet.getRange(1, 1, 1, 10).setFontWeight('bold');
  }
  
  // 기존 데이터의 기관-링크 조합으로 중복 체크
  const existing = new Set();
  if (sheet.getLastRow() > 1) {
    const data = sheet.getRange(2, 1, sheet.getLastRow() - 1, 9).getValues();
    data.forEach(row => existing.add(row[0] + '|' + row[8]));
  }
  
  // 주기 분석 결과를 기관별로 매핑
  const cycleMap = {};
  if (cycleAnalysis) {
    cycleAnalysis.forEach(c => { cycleMap[c.기관명] = c; });
  }
  
  const newRows = [];
  for (const item of pastItems) {
    const key = (item.matchedInstitution || '') + '|' + item.link;
    if (existing.has(key)) continue;
    
    const cycle = cycleMap[item.matchedInstitution] || {};
    const postYear = item.postdate ? item.postdate.substring(0, 4) : '';
    const postMonth = item.postdate ? item.postdate.substring(5, 7) : '';
    
    newRows.push([
      item.matchedInstitution || '',
      item.title,
      postYear,
      postMonth,
      item.deadline || '',
      cycle.추정주기_월 ? cycle.추정주기_월 + '개월' : '',
      cycle.다음예상시기 || '',
      '',  // 알림설정 (수동)
      item.link,
      item.signals || ''
    ]);
  }
  
  if (newRows.length > 0) {
    sheet.getRange(sheet.getLastRow() + 1, 1, newRows.length, newRows[0].length)
         .setValues(newRows);
    Logger.log(`[SheetManager] 과거공고 ${newRows.length}건 추가`);
  }
}

/**
 * 실행 로그 기록
 */
function writeLog(logEntry) {
  const config = getConfig();
  const ss = SpreadsheetApp.openById(config.SPREADSHEET_ID);
  let sheet = ss.getSheetByName(config.SHEET.LOG);
  
  if (!sheet) {
    sheet = ss.insertSheet(config.SHEET.LOG);
    sheet.getRange(1, 1, 1, 7).setValues([
      ['실행일시', '실행유형', '처리건수', '신규발견', '소요시간(초)', '오류내용', '상세로그']
    ]);
    sheet.getRange(1, 1, 1, 7).setFontWeight('bold');
  }
  
  sheet.appendRow([
    new Date(),
    logEntry.type || '',
    logEntry.processed || 0,
    logEntry.newFound || 0,
    logEntry.duration || 0,
    logEntry.error || '',
    logEntry.detail || ''
  ]);
}

/**
 * 검색결과 원본 시트 생성
 */
function createRawResultsSheet(ss) {
  const config = getConfig();
  const sheet = ss.insertSheet(config.SHEET.RAW_RESULTS);
  
  const headers = [
    '검색ID', '검색일시', '검색어', '검색유형', '제목', '링크', 
    '설명', '출처명', '게시일', '매칭기관', '1차분류', '분류점수',
    'AI분류', 'AI확신도', 'AI요약', '최종상태', '중복여부', '처리완료'
  ];
  
  sheet.getRange(1, 1, 1, headers.length).setValues([headers]);
  sheet.getRange(1, 1, 1, headers.length).setFontWeight('bold');
  sheet.setFrozenRows(1);
  
  // 조건부 서식: 최종상태에 따른 색상
  const statusRange = sheet.getRange('P:P');
  
  // 긴급 = 빨간 배경
  const urgentRule = SpreadsheetApp.newConditionalFormatRule()
    .whenTextContains('긴급')
    .setBackground('#ffcdd2')
    .setRanges([statusRange])
    .build();
  
  // 신규 = 초록 배경
  const newRule = SpreadsheetApp.newConditionalFormatRule()
    .whenTextContains('신규')
    .setBackground('#c8e6c9')
    .setRanges([statusRange])
    .build();
  
  sheet.setConditionalFormatRules([urgentRule, newRule]);
  
  return sheet;
}

/**
 * 모니터링 등급에 따른 기관 목록 로드
 * @param {string} grade - 'A', 'B', 'C' 또는 'ALL'
 */
function loadInstitutionsByGrade(grade) {
  const config = getConfig();
  const ss = SpreadsheetApp.openById(config.SPREADSHEET_ID);
  const sheet = ss.getSheetByName(config.SHEET.INSTITUTIONS);
  
  if (!sheet || sheet.getLastRow() < 2) return [];
  
  const data = sheet.getRange(2, 1, sheet.getLastRow() - 1, 12).getValues();
  const institutions = [];
  
  for (const row of data) {
    const instGrade = (row[9] || 'C').toString().toUpperCase(); // J열: 모니터링등급
    
    if (grade === 'ALL' || instGrade === grade) {
      institutions.push({
        code:      row[0],
        name:      row[1] ? row[1].toString().trim() : '',
        alias:     row[2] ? row[2].toString().trim() : '',
        category:  row[3],
        homepage:  row[4],
        pastCount: row[5] || 0,
        lastPost:  row[6],
        cycle:     row[7],
        nextExpected: row[8],
        grade:     instGrade,
        lastSearch: row[10]
      });
    }
  }
  
  return institutions.filter(i => i.name); // 기관명이 있는 것만
}
```

---

### `06_Reporter.gs` — 이메일 리포트

```javascript
/**
 * ============================================================
 * 06_Reporter.gs - 이메일 리포트 생성 및 발송
 * ============================================================
 */

/**
 * 일일 리포트 이메일 발송
 */
function sendDailyReport(reportData) {
  const config = getConfig();
  const email = config.REPORT_EMAIL;
  
  if (!email) {
    Logger.log('[Reporter] 이메일 주소 미설정');
    return;
  }
  
  const today = Utilities.formatDate(new Date(), 'Asia/Seoul', 'yyyy-MM-dd (EEE)');
  const subject = `📋 노무자문 모집공고 모니터링 리포트 [${today}]`;
  
  const html = buildReportHtml(reportData, today);
  
  MailApp.sendEmail({
    to: email,
    subject: subject,
    htmlBody: html
  });
  
  Logger.log(`[Reporter] 리포트 발송 완료: ${email}`);
}

/**
 * HTML 리포트 생성
 */
function buildReportHtml(data, dateStr) {
  const { urgent, newPostings, caution, pastPostings, 
          upcomingAlerts, stats, errors } = data;
  
  let html = `
  <!DOCTYPE html>
  <html>
  <head>
    <meta charset="utf-8">
    <style>
      body { font-family: 'Malgun Gothic', Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; color: #333; }
      h1 { color: #1a73e8; border-bottom: 3px solid #1a73e8; padding-bottom: 10px; }
      h2 { color: #555; margin-top: 30px; }
      .summary-box { display: flex; gap: 15px; flex-wrap: wrap; margin: 20px 0; }
      .stat-card { background: #f8f9fa; border-radius: 12px; padding: 15px 20px; min-width: 120px; text-align: center; border: 1px solid #e0e0e0; }
      .stat-number { font-size: 28px; font-weight: bold; }
      .stat-label { font-size: 12px; color: #666; margin-top: 4px; }
      .urgent { border-left: 4px solid #d32f2f; background: #ffebee; }
      .new { border-left: 4px solid #388e3c; background: #e8f5e9; }
      .caution { border-left: 4px solid #f57c00; background: #fff3e0; }
      .past { border-left: 4px solid #1565c0; background: #e3f2fd; }
      .card { border-radius: 8px; padding: 15px; margin: 10px 0; }
      .card h3 { margin: 0 0 8px 0; }
      .card p { margin: 4px 0; font-size: 14px; }
      .card a { color: #1a73e8; }
      .badge { display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: bold; }
      .badge-urgent { background: #d32f2f; color: white; }
      .badge-new { background: #388e3c; color: white; }
      .badge-caution { background: #f57c00; color: white; }
      .confidence { color: #666; font-size: 12px; }
      .meta { color: #888; font-size: 12px; }
      .alert-box { background: #fff8e1; border: 1px solid #ffcc02; border-radius: 8px; padding: 15px; margin: 15px 0; }
      .footer { margin-top: 40px; padding-top: 20px; border-top: 1px solid #ddd; color: #888; font-size: 12px; }
      table { width: 100%; border-collapse: collapse; margin: 10px 0; }
      th, td { padding: 8px 12px; text-align: left; border-bottom: 1px solid #eee; font-size: 13px; }
      th { background: #f5f5f5; font-weight: bold; }
    </style>
  </head>
  <body>
    <h1>📋 노무자문 모집공고 모니터링 리포트</h1>
    <p style="color: #666;">${dateStr} 기준</p>

    <!-- 요약 통계 -->
    <div class="summary-box">
      <div class="stat-card">
        <div class="stat-number" style="color:#d32f2f;">${(urgent || []).length}</div>
        <div class="stat-label">🔴 긴급 (마감임박)</div>
      </div>
      <div class="stat-card">
        <div class="stat-number" style="color:#388e3c;">${(newPostings || []).length}</div>
        <div class="stat-label">🟢 신규 공고</div>
      </div>
      <div class="stat-card">
        <div class="stat-number" style="color:#f57c00;">${(caution || []).length}</div>
        <div class="stat-label">🟡 확인 필요</div>
      </div>
      <div class="stat-card">
        <div class="stat-number" style="color:#1565c0;">${stats?.totalSearched || 0}</div>
        <div class="stat-label">📊 총 검색 결과</div>
      </div>
    </div>`;
  
  // === 긴급 공고 ===
  if (urgent && urgent.length > 0) {
    html += `
    <h2>🔴 긴급 — 마감 임박 공고</h2>`;
    for (const item of urgent) {
      html += buildPostingCard(item, 'urgent');
    }
  }
  
  // === 신규 공고 ===
  if (newPostings && newPostings.length > 0) {
    html += `
    <h2>🟢 신규 확인된 공고</h2>`;
    for (const item of newPostings) {
      html += buildPostingCard(item, 'new');
    }
  }
  
  // === 추가 확인 필요 ===
  if (caution && caution.length > 0) {
    html += `
    <h2>🟡 추가 확인 필요</h2>`;
    for (const item of caution) {
      html += buildPostingCard(item, 'caution');
    }
  }
  
  // === 다음 공고 예상 알림 ===
  if (upcomingAlerts && upcomingAlerts.length > 0) {
    html += `
    <h2>⏰ 공고 예상 시기 도래 알림</h2>
    <div class="alert-box">
      <p>과거 공고 패턴을 기반으로, 다음 기관들이 곧 새 공고를 게시할 것으로 예상됩니다:</p>
      <table>
        <tr><th>기관명</th><th>마지막 공고</th><th>추정 주기</th><th>예상 시기</th></tr>`;
    for (const alert of upcomingAlerts) {
      html += `
        <tr>
          <td><strong>${alert.institution}</strong></td>
          <td>${alert.lastPosting}</td>
          <td>${alert.cycle}</td>
          <td style="color:#d32f2f;font-weight:bold;">${alert.expectedDate}</td>
        </tr>`;
    }
    html += `
      </table>
    </div>`;
  }
  
  // === 과거 공고 (새로 발견된) ===
  if (pastPostings && pastPostings.length > 0) {
    html += `
    <h2>📁 새로 발견된 과거 공고 (${pastPostings.length}건)</h2>
    <p style="color:#666;font-size:13px;">향후 공고 모니터링에 참고할 수 있는 과거 공고입니다.</p>
    <table>
      <tr><th>기관</th><th>제목</th><th>게시일</th><th>링크</th></tr>`;
    for (const item of pastPostings.slice(0, 20)) { // 최대 20건
      html += `
      <tr>
        <td>${item.matchedInstitution || '-'}</td>
        <td>${item.title ? item.title.substring(0, 60) : '-'}</td>
        <td>${item.postdate || '-'}</td>
        <td><a href="${item.link}">보기</a></td>
      </tr>`;
    }
    html += `</table>`;
  }
  
  // === 실행 통계 ===
  html += `
    <h2>📊 실행 통계</h2>
    <table>
      <tr><td>총 검색 결과</td><td><strong>${stats?.totalSearched || 0}건</strong></td></tr>
      <tr><td>신규 결과 (중복 제외)</td><td><strong>${stats?.newResults || 0}건</strong></td></tr>
      <tr><td>실제공고 후보</td><td><strong>${stats?.realCandidates || 0}건</strong></td></tr>
      <tr><td>광고/홍보 필터링</td><td>${stats?.ads || 0}건</td></tr>
      <tr><td>뉴스 필터링</td><td>${stats?.news || 0}건</td></tr>
      <tr><td>과거공고 분류</td><td>${stats?.past || 0}건</td></tr>
      <tr><td>AI 분석 수행</td><td>${stats?.aiAnalyzed || 0}건</td></tr>
      <tr><td>소요 시간</td><td>${stats?.duration || '-'}</td></tr>
    </table>`;
  
  // === 오류 ===
  if (errors && errors.length > 0) {
    html += `
    <h2>⚠️ 오류 로그</h2>
    <ul style="font-size:13px;color:#d32f2f;">`;
    for (const err of errors) {
      html += `<li>${err}</li>`;
    }
    html += `</ul>`;
  }
  
  html += `
    <div class="footer">
      <p>이 리포트는 자동 생성되었습니다. | 
         <a href="https://docs.google.com/spreadsheets/d/${getConfig().SPREADSHEET_ID}">구글 시트에서 전체 결과 보기</a></p>
      <p>문의: 모니터링 시스템 관리자</p>
    </div>
  </body>
  </html>`;
  
  return html;
}

function buildPostingCard(item, type) {
  const badgeClass = `badge-${type}`;
  const badgeText = type === 'urgent' ? '마감임박' : type === 'new' ? '신규' : '확인필요';
  const cardClass = type;
  
  return `
    <div class="card ${cardClass}">
      <h3>
        <span class="badge ${badgeClass}">${badgeText}</span>
        ${item.title || '제목 없음'}
      </h3>
      <p><strong>기관:</strong> ${item.institutionName || item.matchedInstitution || '확인 필요'}</p>
      ${item.deadline ? `<p><strong>마감일:</strong> <span style="color:#d32f2f;font-weight:bold;">${item.deadline}</span></p>` : ''}
      ${item.aiSummary ? `<p><strong>AI 요약:</strong> ${item.aiSummary}</p>` : ''}
      ${item.qualifications ? `<p><strong>자격요건:</strong> ${item.qualifications}</p>` : ''}
      <p class="meta">
        게시일: ${item.postdate || '?'} | 
        출처: ${item.source || '?'} | 
        AI 확신도: ${item.aiConfidence ? (item.aiConfidence * 100).toFixed(0) + '%' : '?'}
      </p>
      <p><a href="${item.link}" target="_blank">🔗 원본 보기</a></p>
    </div>`;
}
```

---

### `07_Main.gs` — 메인 오케스트레이터

```javascript
/**
 * ============================================================
 * 07_Main.gs - 메인 실행 오케스트레이터
 * ============================================================
 */

/**
 * 메인 실행 함수 - 광역 검색 (매일 실행)
 */
function runDailyBroadSearch() {
  const startTime = new Date();
  const errors = [];
  
  Logger.log('========== 일일 광역 검색 시작 ==========');
  
  try {
    // 1단계: 광역 검색 수행
    Logger.log('[STEP 1] 광역 검색 수행 중...');
    let allResults = executeBroadSearch();
    
    // 나라장터 검색 (설정된 경우)
    try {
      const g2bResults = searchG2B();
      allResults = allResults.concat(g2bResults);
    } catch (e) {
      errors.push(`나라장터 검색 오류: ${e.message}`);
    }
    
    // 2단계: 신규 결과 필터링
    Logger.log('[STEP 2] 신규 결과 필터링...');
    const newResults = filterNewResults(allResults);
    
    if (newResults.length === 0) {
      Logger.log('[INFO] 신규 결과 없음');
      writeLog({
        type: '광역검색',
        processed: allResults.length,
        newFound: 0,
        duration: (new Date() - startTime) / 1000,
        detail: '신규 결과 없음'
      });
      
      // 신규 결과 없어도 간단한 리포트 발송
      sendDailyReport({
        stats: { totalSearched: allResults.length, newResults: 0 },
        upcomingAlerts: checkUpcomingAlerts()
      });
      return;
    }
    
    // 3단계: 규칙 기반 분류
    Logger.log('[STEP 3] 규칙 기반 분류...');
    const classified = classifyAllResults(newResults);
    
    // 4단계: 결과 저장
    Logger.log('[STEP 4] 결과 저장...');
    saveRawResults(classified);
    
    // 5단계: AI 분석 (실제공고 후보 + 판단보류)
    Logger.log('[STEP 5] AI 분석...');
    const itemsForAI = [...classified.realCandidates, ...classified.maybe];
    let aiResults = [];
    
    if (itemsForAI.length > 0) {
      // Google Apps Script 6분 제한 고려
      const maxAIItems = 10; // 안전하게 10건까지만 (4.5초 × 10 = 45초)
      const toAnalyze = itemsForAI.slice(0, maxAIItems);
      
      aiResults = batchAIAnalysis(toAnalyze);
      updateAIResults(aiResults);
      
      // 나머지가 있으면 다음 배치에서 처리하도록 기록
      if (itemsForAI.length > maxAIItems) {
        Logger.log(`[INFO] AI 분석 대기: ${itemsForAI.length - maxAIItems}건 남음`);
        scheduleRemainingAIAnalysis();
      }
    }
    
    // 6단계: 과거공고 추적 업데이트
    Logger.log('[STEP 6] 과거공고 추적...');
    if (classified.pastPostings.length > 0) {
      updatePastPostingTracker(classified.pastPostings, null);
    }
    
    // 7단계: 리포트 구성 및 발송
    Logger.log('[STEP 7] 리포트 발송...');
    const urgent = aiResults.filter(r => r.finalStatus === STATUS.URGENT);
    const newPostings = aiResults.filter(r => r.finalStatus === STATUS.NEW);
    const caution = aiResults.filter(r => r.finalStatus === STATUS.CAUTION);
    
    const reportData = {
      urgent: urgent,
      newPostings: newPostings,
      caution: caution,
      pastPostings: classified.pastPostings,
      upcomingAlerts: checkUpcomingAlerts(),
      stats: {
        totalSearched: allResults.length,
        newResults: newResults.length,
        realCandidates: classified.realCandidates.length,
        ads: classified.advertisements.length,
        news: classified.news.length,
        past: classified.pastPostings.length,
        aiAnalyzed: aiResults.length,
        duration: ((new Date() - startTime) / 1000).toFixed(1) + '초'
      },
      errors: errors
    };
    
    sendDailyReport(reportData);
    
    // 8단계: 실행 로그
    writeLog({
      type: '광역검색',
      processed: allResults.length,
      newFound: newResults.length,
      duration: (new Date() - startTime) / 1000,
      detail: `실제후보:${classified.realCandidates.length} 광고:${classified.advertisements.length} 뉴스:${classified.news.length} 과거:${classified.pastPostings.length}`
    });
    
    Logger.log('========== 일일 광역 검색 완료 ==========');
    
  } catch (e) {
    Logger.log(`[ERROR] 메인 실행 오류: ${e.message}\n${e.stack}`);
    errors.push(e.message);
    
    writeLog({
      type: '광역검색',
      error: e.message,
      duration: (new Date() - startTime) / 1000
    });
    
    // 오류 알림 이메일
    try {
      MailApp.sendEmail(
        getConfig().REPORT_EMAIL,
        '⚠️ 노무자문 모니터링 오류 발생',
        `오류: ${e.message}\n\n스택: ${e.stack}`
      );
    } catch (mailError) {}
  }
}

/**
 * 정밀 검색 실행 (주 1회)
 * 모니터링 등급 A 기관 대상
 */
function runWeeklyTargetedSearch() {
  const startTime = new Date();
  
  Logger.log('========== 주간 정밀 검색 시작 ==========');
  
  try {
    // 등급 A/B 기관 로드
    const institutions = [
      ...loadInstitutionsByGrade('A'),
      ...loadInstitutionsByGrade('B')
    ];
    
    if (institutions.length === 0) {
      Logger.log('[INFO] 정밀 검색 대상 기관 없음');
      return;
    }
    
    // 배치 처리
    const batchKey = 'TARGETED_BATCH_INDEX';
    const props = PropertiesService.getScriptProperties();
    let batchIndex = parseInt(props.getProperty(batchKey) || '0');
    
    const config = getConfig();
    const batch = institutions.slice(
      batchIndex * config.BATCH_SIZE, 
      (batchIndex + 1) * config.BATCH_SIZE
    );
    
    if (batch.length === 0) {
      // 모든 배치 완료 → 리셋
      props.setProperty(batchKey, '0');
      Logger.log('[INFO] 모든 배치 완료, 리셋');
      return;
    }
    
    Logger.log(`[INFO] 배치 ${batchIndex + 1}: ${batch.length}개 기관 검색`);
    
    // 정밀 검색
    const results = executeTargetedSearch(batch);
    const newResults = filterNewResults(results);
    
    if (newResults.length > 0) {
      const classified = classifyAllResults(newResults);
      saveRawResults(classified);
      
      // AI 분석
      const itemsForAI = [...classified.realCandidates, ...classified.maybe];
      if (itemsForAI.length > 0) {
        const aiResults = batchAIAnalysis(itemsForAI.slice(0, 10));
        updateAIResults(aiResults);
      }
    }
    
    // 다음 배치 인덱스 저장
    props.setProperty(batchKey, (batchIndex + 1).toString());
    
    writeLog({
      type: '정밀검색',
      processed: batch.length,
      newFound: newResults.length,
      duration: (new Date() - startTime) / 1000,
      detail: `배치 ${batchIndex + 1}, 기관: ${batch.map(i => i.name).join(', ').substring(0, 200)}`
    });
    
  } catch (e) {
    Logger.log(`[ERROR] 정밀 검색 오류: ${e.message}`);
    writeLog({
      type: '정밀검색',
      error: e.message,
      duration: (new Date() - startTime) / 1000
    });
  }
}

/**
 * 남은 AI 분석 처리 (배치)
 */
function processRemainingAIAnalysis() {
  const config = getConfig();
  const ss = SpreadsheetApp.openById(config.SPREADSHEET_ID);
  const sheet = ss.getSheetByName(config.SHEET.RAW_RESULTS);
  
  if (!sheet || sheet.getLastRow() < 2) return;
  
  const data = sheet.getDataRange().getValues();
  const headers = data[0];
  const pendingItems = [];
  
  // AI판단 대기 중인 항목 찾기
  for (let i = 1; i < data.length; i++) {
    const status = data[i][15]; // P열: 최종상태
    const aiCategory = data[i][12]; // M열: AI분류
    
    if (status === STATUS.PENDING && !aiCategory) {
      pendingItems.push({
        rowIndex: i + 1,
        title: data[i][4],
        link: data[i][5],
        description: data[i][6],
        source: data[i][7],
        postdate: data[i][8],
        matchedInstitution: data[i][9],
        category: data[i][10],
        score: data[i][11],
        signals: '',
        searchType: data[i][3]
      });
    }
  }
  
  if (pendingItems.length === 0) {
    Logger.log('[AI Batch] 대기 중인 항목 없음');
    return;
  }
  
  Logger.log(`[AI Batch] ${Math.min(pendingItems.length, 10)}건 처리`);
  const toProcess = pendingItems.slice(0, 10);
  const aiResults = batchAIAnalysis(toProcess);
  updateAIResults(aiResults);
}

/**
 * 예상 공고 시기 도래 알림 확인
 */
function checkUpcomingAlerts() {
  const config = getConfig();
  const ss = SpreadsheetApp.openById(config.SPREADSHEET_ID);
  const sheet = ss.getSheetByName(config.SHEET.PAST_TRACK);
  
  if (!sheet || sheet.getLastRow() < 2) return [];
  
  const data = sheet.getRange(2, 1, sheet.getLastRow() - 1, 10).getValues();
  const alerts = [];
  const now = new Date();
  const currentYM = Utilities.formatDate(now, 'Asia/Seoul', 'yyyy-MM');
  
  // 1개월 후까지 확인
  const nextMonth = new Date(now.getTime() + 30 * 24 * 60 * 60 * 1000);
  const nextYM = Utilities.formatDate(nextMonth, 'Asia/Seoul', 'yyyy-MM');
  
  for (const row of data) {
    const expectedDate = row[6] ? row[6].toString().trim() : ''; // G열: 다음예상시기
    if (expectedDate && (expectedDate <= nextYM)) {
      alerts.push({
        institution: row[0],
        lastPosting: row[2] + '-' + row[3], // 연도-월
        cycle: row[5] || '미상',
        expectedDate: expectedDate
      });
    }
  }
  
  // 중복 기관 제거
  const seen = new Set();
  return alerts.filter(a => {
    if (seen.has(a.institution)) return false;
    seen.add(a.institution);
    return true;
  });
}

function scheduleRemainingAIAnalysis() {
  // 5분 후에 남은 AI 분석 실행
  ScriptApp.newTrigger('processRemainingAIAnalysis')
    .timeBased()
    .after(5 * 60 * 1000)
    .create();
}
```

---

### `08_Setup.gs` — 초기 설정 및 트리거

```javascript
/**
 * ============================================================
 * 08_Setup.gs - 초기 설정, 트리거, 유틸리티
 * ============================================================
 */

/**
 * 🔧 최초 1회 실행: 시스템 초기 설정
 * 
 * 실행 전 준비사항:
 * 1. 네이버 개발자센터 (https://developers.naver.com/) 에서 앱 등록
 *    → 검색 API 사용 신청 → Client ID / Secret 획득
 * 2. Google AI Studio (https://aistudio.google.com/) 에서 API 키 발급
 * 3. 구글 시트 생성 → ID 복사 (URL의 /d/ 와 /edit 사이 문자열)
 */
function initialSetup() {
  // ===== 1. API 키 설정 (아래 값을 실제 값으로 변경 후 실행) =====
  const props = PropertiesService.getScriptProperties();
  
  props.setProperties({
    'NAVER_CLIENT_ID':      '여기에_네이버_클라이언트ID_입력',
    'NAVER_CLIENT_SECRET':  '여기에_네이버_클라이언트_시크릿_입력',
    'GEMINI_API_KEY':       '여기에_제미나이_API키_입력',
    'SPREADSHEET_ID':       '여기에_구글시트_ID_입력',
    'REPORT_EMAIL':         '여기에_리포트_받을_이메일_입력',
    // (선택) 나라장터 API
    'DATA_GO_KR_API_KEY':   ''  // 공공데이터포털 API 키 (선택사항)
  });
  
  Logger.log('✅ API 키 설정 완료');
  
  // ===== 2. 시트 구조 초기화 =====
  initializeSheets();
  
  // ===== 3. 트리거 설정 =====
  setupTriggers();
  
  Logger.log('🎉 초기 설정 완료!');
  Logger.log('📌 다음 단계: "기관목록" 시트에 공공기관 데이터를 입력하세요.');
}

/**
 * 시트 구조 초기화
 */
function initializeSheets() {
  const config = getConfig();
  const ss = SpreadsheetApp.openById(config.SPREADSHEET_ID);
  
  // 기관목록 시트
  let instSheet = ss.getSheetByName(config.SHEET.INSTITUTIONS);
  if (!instSheet) {
    instSheet = ss.insertSheet(config.SHEET.INSTITUTIONS);
    instSheet.getRange(1, 1, 1, 12).setValues([
      ['기관코드', '기관명', '기관약칭', '카테고리', '홈페이지', 
       '과거공고횟수', '마지막공고일', '선발주기(월)', '다음예상시기', 
       '모니터링등급', '마지막검색일', '비고']
    ]);
    instSheet.getRange(1, 1, 1, 12).setFontWeight('bold').setBackground('#e8eaf6');
    instSheet.setFrozenRows(1);
    
    // 샘플 데이터
    instSheet.getRange(2, 1, 5, 12).setValues([
      ['PUB001', '한국토지주택공사', 'LH', '공기업', 'www.lh.or.kr', 0, '', '', '', 'A', '', ''],
      ['PUB002', '한국전력공사', '한전', '공기업', 'www.kepco.co.kr', 0, '', '', '', 'A', '', ''],
      ['PUB003', '국민건강보험공단', '건보공단', '준정부', 'www.nhis.or.kr', 0, '', '', '', 'A', '', ''],
      ['PUB004', '한국도로공사', '도로공사', '공기업', 'www.ex.co.kr', 0, '', '', '', 'B', '', ''],
      ['PUB005', '한국수자원공사', 'K-water', '공기업', 'www.kwater.or.kr', 0, '', '', '', 'B', '', ''],
    ]);
    
    Logger.log('✅ 기관목록 시트 생성 (샘플 5개 포함)');
  }
  
  // 설정 시트
  let settSheet = ss.getSheetByName(config.SHEET.SETTINGS);
  if (!settSheet) {
    settSheet = ss.insertSheet(config.SHEET.SETTINGS);
    settSheet.getRange(1, 1, 1, 3).setValues([['설정키', '설정값', '설명']]);
    settSheet.getRange(1, 1, 1, 3).setFontWeight('bold').setBackground('#e8eaf6');
    
    settSheet.getRange(2, 1, 7, 3).setValues([
      ['광역검색_키워드', '노무자문 모집,자문노무사 모집,노무자문 공고,노무사 위촉 공고,노무자문 용역,노무자문 제안요청', '쉼표 구분'],
      ['정밀검색_키워드', '노무자문,자문노무사 모집', '기관명과 조합하여 검색'],
      ['검색결과수', '20', 'API당 가져올 결과 수 (최대 100)'],
      ['최근기준_일수', '30', '이 이내를 최근 공고로 판단'],
      ['배치_크기', '100', '정밀검색 시 1회 처리 기관 수'],
      ['AI_최대_분석수', '10', '1회 실행당 AI 분석 최대 건수'],
      ['리포트_이메일', '', '빈칸이면 스크립트 속성 값 사용']
    ]);
    
    Logger.log('✅ 설정 시트 생성');
  }
  
  // 나머지 시트들 (없으면 자동 생성됨)
  Logger.log('✅ 시트 구조 초기화 완료');
}

/**
 * 자동 실행 트리거 설정
 */
function setupTriggers() {
  // 기존 트리거 제거
  const triggers = ScriptApp.getProjectTriggers();
  triggers.forEach(trigger => ScriptApp.deleteTrigger(trigger));
  
  // 1. 일일 광역 검색 (매일 오전 9시)
  ScriptApp.newTrigger('runDailyBroadSearch')
    .timeBased()
    .everyDays(1)
    .atHour(9)
    .create();
  
  // 2. 일일 광역 검색 2차 (매일 오후 2시) - 오전에 놓친 것 catch
  ScriptApp.newTrigger('runDailyBroadSearch')
    .timeBased()
    .everyDays(1)
    .atHour(14)
    .create();
  
  // 3. 주간 정밀 검색 (매주 월요일 오전 10시부터 배치 실행)
  ScriptApp.newTrigger('runWeeklyTargetedSearch')
    .timeBased()
    .onWeekDay(ScriptApp.WeekDay.MONDAY)
    .atHour(10)
    .create();
  
  // 4. 정밀 검색 배치 연속 실행 (월~금 매시간) - 큰 기관목록 처리용
  ScriptApp.newTrigger('runWeeklyTargetedSearch')
    .timeBased()
    .onWeekDay(ScriptApp.WeekDay.MONDAY)
    .atHour(11)
    .create();
  
  ScriptApp.newTrigger('runWeeklyTargetedSearch')
    .timeBased()
    .onWeekDay(ScriptApp.WeekDay.MONDAY)
    .atHour(12)
    .create();
  
  Logger.log('✅ 트리거 설정 완료');
  Logger.log('  - 광역검색: 매일 09:00, 14:00');
  Logger.log('  - 정밀검색: 매주 월요일 10:00~12:00 (3배치)');
}

/**
 * 수동 테스트 실행 함수
 * 전체 파이프라인을 소규모로 테스트
 */
function testRun() {
  Logger.log('===== 테스트 실행 시작 =====');
  
  // 1. 검색 테스트 (키워드 1개만)
  Logger.log('[TEST] 네이버 검색 테스트...');
  const testResults = naverSearch('노무자문 모집 공고', 'web', 5, 'date');
  Logger.log(`[TEST] 검색 결과: ${testResults.length}건`);
  
  if (testResults.length > 0) {
    Logger.log(`[TEST] 첫 번째 결과: ${JSON.stringify(testResults[0], null, 2)}`);
    
    // 2. 분류 테스트
    Logger.log('[TEST] 분류 테스트...');
    const classified = classifyAllResults(testResults);
    Logger.log(`[TEST] 분류 결과: ${JSON.stringify({
      실제후보: classified.realCandidates.length,
      광고: classified.advertisements.length,
      뉴스: classified.news.length,
      과거: classified.pastPostings.length,
      보류: classified.maybe.length,
      무관: classified.irrelevant.length
    })}`);
    
    // 3. AI 테스트 (1건만)
    const aiTestItem = classified.realCandidates[0] || classified.maybe[0] || testResults[0];
    if (aiTestItem) {
      Logger.log('[TEST] AI 분석 테스트...');
      const aiResult = analyzeWithAI(classifyItem(aiTestItem, []));
      Logger.log(`[TEST] AI 결과: ${JSON.stringify(aiResult, null, 2)}`);
    }
  }
  
  Logger.log('===== 테스트 실행 완료 =====');
}

/**
 * 구글 시트 메뉴 추가
 */
function onOpen() {
  const ui = SpreadsheetApp.getUi();
  ui.createMenu('🔍 노무자문 모니터링')
    .addItem('▶ 지금 광역검색 실행', 'runDailyBroadSearch')
    .addItem('▶ 지금 정밀검색 실행', 'runWeeklyTargetedSearch')
    .addItem('▶ AI 분석 재실행', 'processRemainingAIAnalysis')
    .addSeparator()
    .addItem('🧪 테스트 실행', 'testRun')
    .addSeparator()
    .addItem('⚙️ 초기 설정', 'initialSetup')
    .addItem('⏰ 트리거 재설정', 'setupTriggers')
    .addToUi();
}
```

---

## 🚀 배포 및 설정 가이드

### Step 1: 사전 준비

```
┌─ 준비물 체크리스트 ───────────────────────────────────────┐
│                                                           │
│  □ 1. 네이버 개발자센터 계정 + 애플리케이션 등록            │
│     → https://developers.naver.com/apps/#/register        │
│     → "검색" API 선택                                     │
│     → Client ID / Client Secret 획득                      │
│                                                           │
│  □ 2. Google AI Studio API 키                             │
│     → https://aistudio.google.com/apikey                  │
│     → API 키 생성                                         │
│                                                           │
│  □ 3. (선택) 공공데이터포털 API 키                          │
│     → https://www.data.go.kr 회원가입                     │
│     → "조달청 나라장터 입찰공고" API 활용 신청              │
│                                                           │
│  □ 4. 구글 스프레드시트 생성                                │
│     → 새 시트 만들기                                       │
│     → URL에서 스프레드시트 ID 복사                          │
│     예: docs.google.com/spreadsheets/d/{이_부분}/edit      │
│                                                           │
│  □ 5. 공공기관 목록 확보                                    │
│     → 공공기관 경영정보 공개시스템(ALIO) 활용               │
│       https://www.alio.go.kr                              │
│     → 또는 기획재정부 공공기관 지정 목록 활용               │
│                                                           │
└───────────────────────────────────────────────────────────┘
```

### Step 2: 스크립트 배포

```
1. 구글 시트 열기 → [확장 프로그램] → [Apps Script]

2. 기본 파일(코드.gs) 내용 삭제

3. 8개 파일 생성:
   좌측 [+] 버튼 → "스크립트" 선택
   
   파일명:          내용:
   00_Config      → 위 Config.gs 코드 붙여넣기
   01_NaverSearch → 위 NaverSearch.gs 코드 붙여넣기
   02_G2BSearch   → 위 G2BSearch.gs 코드 붙여넣기
   03_Classifier  → 위 Classifier.gs 코드 붙여넣기
   04_GeminiAI    → 위 GeminiAI.gs 코드 붙여넣기
   05_SheetManager→ 위 SheetManager.gs 코드 붙여넣기
   06_Reporter    → 위 Reporter.gs 코드 붙여넣기
   07_Main        → 위 Main.gs 코드 붙여넣기
   08_Setup       → 위 Setup.gs 코드 붙여넣기

4. 08_Setup.gs 열기
   → initialSetup() 함수에서 API 키 값 수정
   → 함수 선택 드롭다운에서 "initialSetup" 선택
   → ▶ 실행 버튼 클릭
   → 권한 승인 (최초 1회)

5. 테스트:
   → 함수 선택: "testRun"
   → ▶ 실행
   → 로그 확인 (Ctrl+Enter 또는 [실행 로그] 메뉴)
```

### Step 3: 기관 목록 입력

```
방법 1: 직접 입력
  → "기관목록" 시트에 기관명 수동 입력
  → 860개 기관 데이터 (ALIO에서 다운로드 가능)

방법 2: ALIO 데이터 활용
  → alio.go.kr → 공공기관 목록 다운로드
  → 구글 시트에 붙여넣기
  → 열 순서 맞추기

방법 3: AI 활용
  → Gemini에게 "한국 공공기관 목록 860개를 구글시트 형식으로"
  → 결과를 시트에 붙여넣기
  → 정확성 확인 필요
```

### Step 4: 모니터링 등급 설정

```
모니터링등급 기준 (J열):

A등급 (매일 검색): 
  → 과거에 노무자문 공고를 냈던 기관
  → 대규모 공기업/준정부기관
  → 다음 공고 예상 시기가 임박한 기관

B등급 (주간 검색):
  → 중견 공공기관
  → 노무자문 수요가 있을 것으로 추정되는 기관

C등급 (월간 검색 또는 광역검색만):
  → 소규모 기관
  → 노무자문 수요 불확실
```

---

## 🔮 Phase 2: 지원서 작성 도우미 (향후 개발)

```
┌─────────────────────────────────────────────────────────────────┐
│                    지원서 작성 도우미 개요                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  트리거: 모니터링 시스템에서 "실제공고" 확인 시 자동 활성화         │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │ Step 1: 공고 상세 분석                                    │    │
│  │  • 공고 페이지 전문 크롤링                                │    │
│  │  • HWP 파일 다운로드 및 파싱 (Cloud Function 활용)        │    │
│  │  • 자격요건, 제출서류, 평가기준 추출                       │    │
│  └──────────────────┬──────────────────────────────────────┘    │
│                     ▼                                           │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │ Step 2: 지원서 초안 생성                                  │    │
│  │  • 기존 지원서 템플릿 DB 참조                             │    │
│  │  • 공고 맞춤 자기소개서/사업계획서 초안                    │    │
│  │  • 평가기준에 맞는 강점 포인트 제안                        │    │
│  └──────────────────┬──────────────────────────────────────┘    │
│                     ▼                                           │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │ Step 3: 체크리스트 생성                                    │    │
│  │  • 필수 제출서류 목록                                     │    │
│  │  • 서류별 준비 상태 체크                                   │    │
│  │  • 마감일 기준 일정표                                     │    │
│  │  • 제출 방법 안내 (우편/방문/이메일)                       │    │
│  └──────────────────┬──────────────────────────────────────┘    │
│                     ▼                                           │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │ Step 4: 알림 및 후속 관리                                  │    │
│  │  • 마감 D-7, D-3, D-1 알림                               │    │
│  │  • 제출 완료 기록                                         │    │
│  │  • 선정 결과 모니터링                                     │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                 │
│  기술 스택 추가:                                                │
│  • Google Cloud Functions (HWP 파싱용 Python 함수)              │
│  • python-hwp 또는 olefile 라이브러리                           │
│  • Google Docs API (지원서 문서 자동 생성)                       │
│  • Google Calendar API (마감일 일정 등록)                        │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 📌 비용 및 제한 요약

| 항목 | 무료 한도 | 예상 사용량 | 비용 |
|------|-----------|-------------|------|
| **네이버 검색 API** | 25,000회/일 | ~100회/일 | **무료** |
| **Gemini API** | 15 RPM, 1,500 RPD | ~20회/일 | **무료** |
| **Google Apps Script** | 6분/실행, 90분/일 | ~10분/일 | **무료** |
| **Google Sheets** | 무제한 (개인) | 1개 파일 | **무료** |
| **공공데이터포털** | 1,000회/일 | ~10회/일 | **무료** |
| | | **총 비용** | **$0** |

> **주의사항**: Google Apps Script는 무료 계정 기준 1회 실행 최대 **6분**입니다. 위 코드는 이 제한을 고려하여 배치 처리와 트리거 체인으로 설계되어 있습니다. Google Workspace 계정이면 30분까지 가능합니다.

---

## ✅ 실행 순서 체크리스트

```
□ 1. API 키 3개 발급 (네이버, Gemini, 공공데이터포털)
□ 2. 구글 시트 생성 + ID 확인
□ 3. Apps Script에 8개 파일 코드 입력
□ 4. initialSetup() 에서 API 키 입력 후 실행
□ 5. "기관목록" 시트에 공공기관 데이터 입력
□ 6. testRun() 으로 동작 확인
□ 7. 모니터링 등급(A/B/C) 설정
□ 8. setupTriggers() 로 자동 실행 활성화
□ 9. 첫 번째 리포트 이메일 수신 확인
□ 10. 2~3일 운영 후 분류 규칙 튜닝 (Classifier.gs 키워드 조정)
```
# 확장하기: 새 관점(Lens) 추가와 기준 조정

이 프로젝트는 "하나의 완성된 화면"이 아니라, 경영진이 "이 관점으로도 보고 싶다"고 할 때 **한 파일을 추가하는 것**으로 대응하도록 설계되어 있다. 기준을 바꾸는 주체와 방법은 세 가지다.

| 누가 | 무엇을 | 어떻게 | 반영 시점 |
|---|---|---|---|
| 경영진/방문자 | 이슈 판정 임계값(예: ROAS가 몇 % 떨어져야 이슈로 볼지) | 앱 사이드바 "이슈 기준 조정" 슬라이더. 바뀐 항목은 상단 배너에 표시되고 "기본값으로 되돌리기"로 복구 | 즉시, 그 방문자의 세션에만 |
| 운영자 | 사용할 관점 목록, 임계값 기본값, 판매 속도 산정 기간 같은 계산 옵션 | `config/lab.toml` 수정 | 다음 리프레시 |
| 개발자 | 새 관점(새 KPI, 새 규칙, 새 탭, 새 데이터 소스) | `src/commerce_lab/lenses/<이름>.py` 추가 | 재배포 + 다음 리프레시 |

## 구조: 관점 하나 = 파일 하나

관점(`Lens`, [`lenses/base.py`](../src/commerce_lab/lenses/base.py))은 다음을 한 모듈에 담는다.

| 필드 | 역할 |
|---|---|
| `compute(datasets, window, params)` | 이 관점의 KPI를 계산해 스냅샷의 한 섹션(dict)으로 반환 |
| `detect(section, params)` | 그 **섹션만** 읽어 `DecisionItem` 목록 반환 (결정적, AI 없음) |
| `params` | 조정 가능한 임계값. `label`은 ko/en 모두 채운다(방향까지 드러나게: "ROAS 변화율 ≤ 이 값이면 high"). `runtime=True`면 앱에 슬라이더가 생기고(`min`/`max`/`step` 필수), `False`면 `compute`가 쓰는 값이라 설정 파일로만 바꾼다 |
| `data_sources` | (선택) 새 원천 데이터셋: 컬럼 정의 + 합성 데이터 생성 함수 |
| `render(section, lang, params)` | (선택) 앱 탭. Streamlit은 함수 안에서 import |
| `localizers` | (선택) `issue_type` → 한/영 문장 |
| `kpi_lookup`, `headline_metrics` | (선택) 이슈 추세선 값, Overview KPI 타일 |
| `title` | 탭 이름. ko/en 둘 다 지정(예: 성과 / Performance) |
| `strings` | (선택) 이 관점이 쓰는 UI 문구(ko/en). 접히는 영역(`st.expander`)을 만든다면 제목에 "클릭하여 펼치기"와 내용 요약(개수 등)을 넣어, 접힌 것이 무엇인지 보이게 한다 |

`detect`가 원천 데이터가 아니라 **스냅샷 섹션만** 읽는다는 점이 핵심이다. 그래서 앱이 저장된 지표만으로 임계값을 바꿔 이슈를 다시 판정할 수 있고(BigQuery/Gemini 호출 없음), "KPI는 결정적으로 계산하고 Gemini는 해석만 한다"는 원칙도 그대로 유지된다. 각 이슈에는 어느 관점이 만들었는지(`lens`)가 기록된다.

기본 4개 관점([`sales`](../src/commerce_lab/lenses/sales.py), [`marketing`](../src/commerce_lab/lenses/marketing.py), [`customer`](../src/commerce_lab/lenses/customer.py), [`inventory`](../src/commerce_lab/lenses/inventory.py))이 그대로 예제다.

## 새 관점 추가 절차

예: 반품률 관점(새 데이터 소스 `returns` 필요).

1. **파일 만들기** `src/commerce_lab/lenses/returns.py`에 모듈 수준 `LENS = Lens(...)`를 정의한다.
   - 새 테이블이 필요하면 `DataSource(name="returns", columns={"order_id": "STRING", "returned": "BOOL"}, generate=...)`를 `data_sources=`에 넣는다. `generate(rng, datasets)`는 이미 생성된 데이터셋(주문 등)을 받아 DataFrame을 돌려준다. 이 소스는 자기 전용 난수열을 쓰므로 **기존 데이터는 한 바이트도 바뀌지 않는다.**
   - `compute`는 `datasets["returns"]`를 읽어 섹션을 만들고, `detect`는 그 섹션과 `params`로 `DecisionItem`을 만든다.
2. **켜기** `config/lab.toml`의 `enabled`에 `"returns"`를 추가한다(순서 = 탭 순서). 패키지 밖 모듈이면 `"my_package.returns"`처럼 점이 있는 경로를 쓴다.
3. **리프레시** `python -m commerce_lab.pipeline.refresh` — 새 CSV 생성, 스냅샷에 섹션/이슈 반영. 클라우드에서는 `--upload`가 GCS 업로드와 함께 `raw.returns` 테이블을 `CREATE TABLE IF NOT EXISTS`로 만들고 적재한다.
4. **테스트** [`tests/test_lenses/test_extensibility.py`](../tests/test_lenses/test_extensibility.py)가 같은 절차(새 데이터 소스 → 스냅샷 → 이슈 → 설정 덮어쓰기 → 앱 재판정)를 임시 관점으로 검증하는 템플릿이다.

## 설정 파일 `config/lab.toml`

```toml
[lenses]
enabled = ["sales", "marketing", "customer", "inventory"]

[params.marketing]
decline_high_pct = -35

[params.inventory]
stockout_days = 10
velocity_window_days = 21   # runtime=False 계산 옵션: 설정 파일로만 변경
```

- 적어 두지 않은 값은 각 관점의 기본값을 쓴다. 오타 난 키는 조용히 무시되지 않고 리프레시가 즉시 실패한다.
- 리프레시 Job 이미지에 `config/`가 함께 복사된다(`Dockerfile.job`). 설정을 바꾸면 Job 이미지를 다시 빌드/배포해야 클라우드에 반영된다.
- 앱은 설정 파일을 읽지 않는다. 스냅샷에 기록된 `lenses`/`params`를 그대로 따른다.

## 한계 (의도적)

- 앱의 임계값 조정은 **이슈 판정**에만 영향을 준다. 지표 자체를 바꾸는 옵션(예: 판매 속도 산정 기간, 비교 기간 길이)은 다시 계산이 필요하므로 설정 파일 + 리프레시로만 바꾼다.
- 조정한 값은 세션에만 남는다(저장·공유 기능 없음).
- BigQuery 메트릭 SQL(`sql/metrics/*.sql`)은 관점 추가와 자동 연동되지 않는다. 새 관점의 권위 있는 계산은 Python(`compute`)이며, BigQuery에서도 계산하고 싶다면 SQL을 `sql/metrics/`에 추가하면 `provision_gcp.sh`가 함께 적용한다.
- 앱 UI 문구는 ko/en 두 언어만 지원한다.

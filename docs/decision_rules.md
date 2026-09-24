# 의사결정/이슈 탐지 규칙

구현: 각 관점 모듈의 `detect`(`src/commerce_lab/lenses/{sales,marketing,customer,inventory}.py`). 임계값은 각 모듈의 `params`가 기본값이며 `config/lab.toml`이나 앱에서 조정할 수 있다([`extending.md`](extending.md)). 순수하고 결정적인, 임계값 기반 로직이다 -- AI는 관여하지 않는다(`CLAUDE.md`: "Gemini는 근거가 있는 구조화된 결과를 해석해야 하며, 계산의 권위 있는 주체가 되어서는 안 된다"). 각 규칙은 M3 메트릭이 담긴 스냅샷 섹션을 입력으로 받아 0개 이상의 `DecisionItem`(`src/commerce_lab/decisions/models.py`)을 반환한다: 이슈, 근거 KPI, 유력한 원인, 영향받는 브랜드/채널/SKU, 심각도, 가능한 조치, 이후 모니터링할 KPI(`PROJECT.md` §7).

## 규칙과 임계값

| 규칙 | 입력 | 트리거 | 심각도 |
|---|---|---|---|
| 마케팅 효율 악화 | `metrics.marketing_by_segment` | `roas_change_pct <= -20%`, `previous_spend >= 1000`(무의미한 세그먼트 제외) | `<= -40%`면 high, 아니면 medium |
| 품절 위험 | `metrics.inventory_risk` | `stockout_risk = True`(즉 `days_of_cover < 7`) | `days_of_cover < 3`면 high, 아니면 medium |
| 과잉재고 위험 | `metrics.inventory_risk` | `excess_risk = True`(`days_of_cover > 60` 또는 재고는 있는데 velocity가 0) | low |
| 매출 하락 | `metrics.sales_by_segment` | `pct_change <= -20%`, `previous_net_revenue >= 500`(무의미한 세그먼트 제외) | `<= -35%`면 high, 아니면 medium |
| 고객 구성 변화 | `metrics.customer_mix` | `new_share_pct_change <= -25%` | `<= -50%`면 high, 아니면 medium |

모든 임계값은 `docs/synthetic_data.md`에 심어놓은 4개 시나리오를 탐지 가능하게 하면서 무의미한 세그먼트의 잡음은 걸러내기 위한 데모용 기본값이며, 실제 리테일 벤치마크에 맞춰 튜닝된 것은 아니다. README의 한계 섹션에 명시되어 있다.

## 예상 매출 영향 (`estimated_revenue_impact`)

모든 `DecisionItem`의 `supporting_kpi`에는 `estimated_revenue_impact` 필드가 있다(값이 없으면 `None`) -- 이슈의 심각도를 %가 아니라 달러 규모로도 가늠할 수 있게 한다. 오직 이미 계산된 KPI만으로 직접 유도 가능한 경우에만 채워진다:

| 규칙 | 계산식 |
|---|---|
| 마케팅 효율 악화 | `current_attributed_revenue - (current_spend × previous_roas)` -- 이전 효율을 유지했다면 이 지출로 벌었을 매출 대비, 실제로 번 매출의 차이 |
| 매출 하락 | `current_net_revenue - previous_net_revenue` |
| 품절 위험 / 과잉재고 위험 / 고객 구성 변화 | `None` -- SKU 단위 원가·판매가나 주문당 매출 귀속 정보가 이 규칙의 입력에는 없어, 방어 가능한 달러 계산을 할 수 없다 |

앱은 이 필드를 카드에 표시하고, 같은 심각도 등급 안에서 정렬할 때 2차 기준으로 사용한다(`commerce_lab.app.view_helpers.top_issues`) -- 심각도 자체를 이 값으로 뒤집지는 않는다. 심각도는 여전히 결정적 규칙이 정하는 1차 신호다.

## 이 레이어가 하는 것과 하지 않는 것

- 한다: 사실을 계산하고, 고정 임계값을 적용하고, 심각도로 정렬하고, (서술문이 아닌) 구조화된 이슈 목록을 만든다. `tests/test_decisions/`로 전부 단위 테스트되어 있으며, 심어놓은 4개 시나리오 각각이 정확히 기대한 이슈를 만들고 무관한 세그먼트는 만들지 않음을 포함한다.
- 하지 않는다: 자연어 설명을 쓰거나, 한 줄짜리 사실 기반 원인 설명 이상으로 인과관계를 추론하거나, 외부 서비스를 호출하지 않는다. 서술형 해석은 이 구조에 근거해 Gemini(M6)가 담당한다 -- Gemini는 `DecisionItem`을 받을 뿐 원본 데이터를 받지 않으며, 주어진 사실이나 심각도를 바꿀 수 없다.

## 사후 조치 검증 (PROJECT.md §3 질문 7)

별도의 "검증" 기능은 없다 -- 이슈를 탐지한 것과 동일한 규칙 엔진이 그 해소 여부도 판정한다. 각 `DecisionItem`은 정확히 어떤 `kpi_to_monitor`를 봐야 하는지 명시한다. 조치가 취해지고 다음 예약 리프레시(M7)가 새 데이터로 실행되면, 이슈를 발생시켰던 규칙이 같은 임계값으로 그 KPI를 다시 평가한다: 회복되었다면 규칙이 더 이상 발동하지 않고 해당 이슈는 `run_detection`의 출력에서 그냥 사라진다 -- 따로 맞춰볼 것이 없다. 같은 결정적 함수를 더 최신 데이터에 대해 다시 실행하는 것뿐이기 때문이다.
`tests/test_decisions/test_post_action_verification.py`가 이를 직접 보여준다: `stockout_risk`/`marketing_efficiency_decline`을 발생시키는 "이전" 상태를 만들고, 같은 KPI가 임계값을 넘어 회복된 "이후" 상태를 만들어, 이슈가 더 이상 나타나지 않음을 확인한다 -- 즉 시스템이 하락뿐 아니라 회복도 올바르게 인식한다.

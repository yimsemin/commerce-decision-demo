# KPI 정의

`CLAUDE.md`("메트릭 정의를 명시적으로 유지")와 `PROJECT.md` §6("정확한 공식은 한 곳에 문서화")에 따른, 모든 KPI 공식의 단일 출처. 다음 두 구현체가 존재하며 반드시 이 문서와 정확히 일치해야 한다:

- `sql/metrics/*.sql` — `staging.*` 위의 BigQuery SQL. 리프레시 파이프라인이 사용하는, 클라우드에 배포된 권위 있는 경로.
- `src/commerce_lab/metrics/*.py` — 로컬 개발(`PROJECT.md` §10)과 자동화 테스트용 pandas 미러.

## 기간 비교

"현재 기간" = 데이터에 존재하는 가장 최근 `window_days`(기본 30)일. "이전 기간" = 그 직전 `window_days`일. 하드코딩된 달력 날짜가 아니라 데이터의 `MAX(date)`로부터 계산하므로, 어떤 리프레시에도 동일한 로직이 적용된다(`metrics/periods.py`).

## 매출(Sales)

| KPI | 공식 |
|---|---|
| net_revenue | `SUM(net_sales)` |
| orders | `COUNT(DISTINCT order_id)` |
| units_sold | `SUM(quantity)` |
| aov(평균 주문 금액) | `net_revenue / orders` |

브랜드/채널/SKU 기여도 분석 지원: 세그먼트별 현재 vs 이전 순매출을 절대 변화량 기준으로 정렬(`sales_by_segment`).

## 마케팅(Marketing)

| KPI | 공식 |
|---|---|
| spend | `SUM(spend)` |
| attributed_revenue | `SUM(attributed_revenue)` |
| roas | `attributed_revenue / spend` |
| cac(마케팅 채널별) | `spend(채널) / new_customers_acquired(채널)` |

CAC는 마케팅 채널 단위로만 계산한다. 합성 고객 모델은 `acquisition_channel`을 브랜드와 무관하게 배정하므로, 브랜드 x 채널로 CAC를 쪼개는 것은 이 데이터로는 방어 가능한 계산이 아니다(`PROJECT.md` §6이 모델이 지원하는 범위로 CAC를 명시적으로 제한함).

## 고객(Customer)

| KPI | 공식 |
|---|---|
| new_customer_share(기간) | 해당 기간 주문에 대한 `AVG(is_new_customer)` |
| returning_customer_share(기간) | `1 - new_customer_share(기간)` |
| repeat_purchase_rate | `COUNT(total_orders > 1인 고객) / COUNT(전체 고객)`, 최신 데이터 기준(기간 한정 아닌 전체 기간 지표) |

## 재고(Inventory)

| KPI | 공식 |
|---|---|
| on_hand | 가장 최근 날짜의 `closing_stock` |
| velocity | 가장 최근 날짜로부터 최근 14일간 `AVG(units_sold)` |
| days_of_cover | `on_hand / velocity` (velocity가 0이면 정의되지 않음/null) |
| stockout_risk | `days_of_cover < 7` |
| excess_risk | `on_hand > 0 AND (velocity = 0 OR days_of_cover > 60)` |

임계값(품절 7일, 과잉 60일, velocity 창 14일)은 `docs/synthetic_data.md`에 심어놓은 시나리오를 관측 가능하게 만들기 위한 데모용 기본값이며, 실제 리테일 벤치마크에 맞춰 튜닝된 것은 아니다. README의 한계 섹션에 명시되어 있다.

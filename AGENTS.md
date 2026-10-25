# AGENTS.md

## 프로젝트

- **의도**: 파편화된 합성 커머스 데이터를 경영 의사결정의 근거로 바꾸는 Google Cloud 포트폴리오 데모. 위에 얹힌 AI가 아니라 그 아래의 결정적 계산(BigQuery KPI, 규칙 기반 이슈 탐지)이 중심이고, Gemini는 이미 계산된 결과를 해석만 한다. 제품 스펙은 [docs/PROJECT.md](docs/PROJECT.md).
- **사용자**: 포트폴리오를 읽는 리뷰어(기획·전략 직무 채용 담당)와 오너. 발표자 없이 저장소와 랜딩페이지만으로 이해할 수 있어야 한다.
- **성공 기준**: [docs/PROJECT.md](docs/PROJECT.md)의 Definition of Done. 앱의 모든 숫자가 그것을 계산한 SQL/Python까지 추적되고, 매일 자동 갱신된다.
- **하지 않을 것**: 프로덕션 SaaS 기능. 마이크로서비스, Kubernetes, 스트리밍, 커스텀 ML 학습, 인증, 별도 데이터베이스, 메시지 버스, 범용 추상화 계층, 디자인 시스템, 대용량 데이터셋. 명시된 의사결정 질문이나 Definition of Done를 뒷받침하지 않는 메트릭·필드·서비스·기능.

## 실행과 검증

```sh
uv sync --extra dev --extra pipeline          # 환경 (프로젝트 .venv, Python 3.14)
uv run pytest -q                              # 테스트
uv run python -m commerce_lab.pipeline.refresh              # 로컬 데이터 생성 + 스냅샷 (GCP 불필요)
uv run streamlit run src/commerce_lab/app/main.py           # 로컬 앱
uv run python -m commerce_lab.pipeline.parity --seed N      # BigQuery와 pandas KPI 대조 (GCP 필요, 오늘 raw 테이블을 교체함)
```

클라우드 배포·해체 절차는 [README.md](README.md)의 "배포"와 `scripts/`. 리소스 구성과 결정 기록은 [docs/operations.md](docs/operations.md).

## 구조

- 흐름: 합성 데이터 → Cloud Storage → BigQuery(raw/staging/metrics) → 규칙 → Gemini 해석 → `app_snapshot.json` → Cloud Run 앱. Cloud Scheduler가 매일 Cloud Run Job을 실행한다. 공개 트래픽은 스냅샷 파일만 읽고 BigQuery·Gemini를 직접 호출하지 않는다.
- KPI 공식은 `sql/metrics/*.sql`(권위 있는 구현)과 `src/commerce_lab/metrics/`(pandas 기준 구현)가 [docs/kpi_definitions.md](docs/kpi_definitions.md)와 일치해야 한다. 한쪽을 고치면 `pipeline.parity`로 대조한다.
- 확장은 관점(lens) 모듈 단위다([docs/extending.md](docs/extending.md)).

## 프로젝트 규칙

- KPI 계산과 이슈 탐지 규칙은 결정적이고 테스트 가능해야 한다. Gemini는 근거가 있는 구조화된 결과를 해석할 뿐 계산의 주체가 되지 않는다. 메트릭 정의는 명시적으로 유지한다.
- 수동 콘솔 조작보다 재현 가능한 CLI 스크립트를 우선한다. 저비용·서버리스 구성을 쓰고, 생성한 리소스와 해체 절차를 문서화한다.
- 자격 증명·시크릿을 커밋하지 않는다. 필요하면 환경변수를 쓴다.
- 오너에게 묻는 것: 포트폴리오 스토리나 비즈니스 해석에 영향, 프로젝트 범위 변경, 지속 비용 발생, 보안·계정 접근, 되돌릴 수 없는 클라우드 작업(리소스 삭제·해체, IAM·org policy, 결제 연결). 라이브러리·내부 구조·네이밍·SQL 구성 같은 일상적 기술 선택은 묻지 않는다.
- README는 비즈니스 문제, 각 GCP 컴포넌트의 존재 이유, 데이터/메트릭 흐름, 의사결정 로직, Gemini의 제한된 역할, 셋업/배포, 비용·안전 가정, 한계를 설명하고 프로덕션 준비도나 AI 역량을 과장하지 않는다.
- 합성 데이터는 실행마다 새 랜덤 시드로 만든다([docs/synthetic_data.md](docs/synthetic_data.md)). 랜딩페이지의 수치와 스크린샷은 캡처 시점의 예시다.
- 커밋 제목은 영어로 쓴다.

<!-- ysm-baseline:start -->
## 공통 작업 규칙 (ysm baseline)

이 구역은 ysm-skills 베이스라인이 관리한다. 프로젝트 고유 규칙은 이 구역 밖에 쓰고, 충돌하면 프로젝트 규칙이 우선한다. 소통·판단·검증 같은 공통 진행 규칙은 전역 지침(ysm-global)이 맡는다.

### 문서

- 루트에는 `README.md`·`AGENTS.md`·`CLAUDE.md`·`LICENSE`·`CHANGELOG.md`처럼 관례상 필요한 파일만 두고, 기획·인수인계·결정 기록·가이드 같은 나머지 문서는 `docs/`에 둔다. 사용자가 폴더에 넣어 둔 입력 문서도 `docs/`로 옮긴다.
- 같은 규칙·사실은 한 문서에만 쓰고 나머지는 링크한다. 문서 종류마다 자리를 하나로 정한다(README는 개요·사용법, 로드맵은 앞으로 할 일만이며 끝난 항목은 지운다). 문서를 늘리기보다 합친다. 날짜를 박은 "현재 수준" 표를 두지 않는다.
- 방향이 바뀌거나 큰 변경이 끝나면 문서 간 모순·중복·낡은 내용을 점검한다.

### UI가 있는 프로젝트

- 첫 방문자 기준으로 설계한다. 지금 무엇이 진행 중인지(진행도·완료·결과 없음 안내)가 보여야 하고, 용어와 단위가 화면 전체에서 같아야 하며, 내부 용어를 노출하지 않는다.
- 영역 구분은 박스를 남발하지 말고 글자 크기·굵기와 일관된 간격으로 한다. 글자는 12pt 이상, 한국어는 어절 단위로 줄바꿈하고, 외부 폰트·CDN 없이 로컬 자산을 쓴다.

### Git

- stage·commit·push·PR·merge는 사용자가 요청할 때만 한다. 승인은 그 요청에만 유효하고 다음 작업으로 이어지지 않는다. 이 파일의 프로젝트 구역이 명시한 상시 승인만 예외다.
- force push, 푸시한 이력의 수정, 브랜치·태그 강제 삭제, 공유 브랜치의 `reset --hard`는 사용자가 그 대화에서 직접 요청했을 때만 한다. 푸시 전 로컬 커밋의 amend·fixup 정리는 이력 재작성이 아니다. `--no-verify`로 훅을 우회하지 않는다.
- 첫 커밋 이후의 작업은 `main`이 아닌 작업 브랜치(`feat/` `fix/` `docs/` `chore/` + kebab-case)에서 한다. 프로젝트가 `main` 직행을 명시하면 예외다. 병렬 작업은 브랜치마다 `git worktree`로 분리한다.
- 커밋은 의미·작업 단위 하나씩 만든다. 같은 목적의 후속 수정(오타·누락·리뷰 반영)은 새 커밋으로 쌓지 말고 푸시 전에 amend·fixup으로 합쳐 원격 이력을 깔끔하게 유지한다.
- 커밋 제목은 `<type>(<선택 scope>): <요약>`이다. type은 `feat` `fix` `perf` `refactor` `docs` `test` `build` `ci` `chore` `style` `revert`, 72자 이내, 끝에 마침표 없음. 형식은 `.githooks/commit-msg`가 검사한다. 이유가 필요하면 본문에 쓴다. 제목 언어는 프로젝트가 정한다.
- 커밋 이메일은 GitHub noreply 주소를 쓴다(프로젝트에 설정되어 있으면 `.githooks/pre-commit`이 검사한다).
- PR 본문은 요약(무엇을·왜), 확인한 방법(실제 실행한 것만), 남은 결정 순서로 짧게 쓴다(`.github/pull_request_template.md`).
- 커밋 메시지와 PR 본문에 AI 생성 표식이나 co-author 트레일러(`Co-Authored-By: Claude …`, `🤖 Generated with …` 등)를 넣지 않는다. 커밋은 훅이 제거하지만 PR 본문은 직접 지킨다.
- 병합이 끝난 브랜치는 로컬·원격 모두 지운다. 푸시·병합까지 요청받은 작업은 로컬과 원격이 일치하고 미커밋 변경이 없는 상태로 마친다.
- 새 클론에서는 한 번 `git config core.hooksPath .githooks`를 실행한다(Claude Code는 세션 시작 때 자동 실행).

### 의존성과 환경

- 의존성·가상환경·캐시·데이터·설정·로그는 프로젝트 폴더 안에만 두어, 폴더를 지우면 함께 사라지게 한다. 설치물과 결과물을 프로젝트 밖(스크래치패드, 전역, 에이전트 메모리)에 두지 않는다. 폴더 하나만 받아도 다른 컴퓨터에서 이어갈 수 있어야 한다. 폴더 밖 저장은 사용자가 명시적으로 고른 경우만 허용한다.
  - Node: `package.json`의 `devDependencies`와 `npx`.
  - Python: `uv`로 프로젝트 `.venv`만 쓴다(`uv sync`, `uv add`).
  - 런타임 버전은 `.node-version`, `.python-version`에만 고정한다. `mise.toml`은 두지 않는다.
- macOS와 Windows에서 같은 동작을 하도록 플랫폼 중립 경로와 LF 줄바꿈을 쓴다.

### 안전

- 저장소는 언제 공개되어도 문제가 없는 상태로 유지한다. `.env`, 키, 토큰, 개인정보, 개인 절대경로, 개인 취향·운영 데이터, 실제 업무 문서를 저장소에 넣거나 읽어 출력하지 않는다. 환경변수 예시는 값이 없는 `.env.example`만 둔다.
- 비밀값으로 보이는 파일·문자열이 staged에 있으면 `.githooks/pre-commit`이 커밋을 막는다.
<!-- ysm-baseline:end -->

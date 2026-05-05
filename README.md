# Academy Private MVP

광영여고/광영고 전담 강의 운영을 위한 비공개 자동화 MVP입니다.

현재 저장소의 1차 목표는 본문 원문을 입력해 광영여고식 변형문항 후보를 만들고, 문제은행에 저장한 뒤, 출력 가능한 동형 세트 제작까지 이어지는 로컬 웹 도구를 만드는 것입니다.

## Current Modules

- `site/engine.html`: 브라우저 기반 변형문항 생성 MVP
- `site/engine-core.js`: 지문 분석, 문항 생성, 검수 점수화, 문제은행 직렬화 엔진
- `site/engine-ui.js`: 로컬 저장, CSV/JSON export, 동형 모의 조립 UI
- `site/engine.css`: 엔진 전용 화면 스타일
- `tools/`: PDF/DOCX 렌더링, 레이아웃 감사, 패키지 검수, 학생 배포본 생성 자동화

## Local Run

```powershell
cd site
python quiet_server.py
```

Then open:

```text
http://127.0.0.1:4177/engine.html
```

## Data Policy

Generated exams, answer keys, PDF/DOCX packages, extracted school materials, and local analysis files are intentionally ignored by Git.

Keep those files on the local machine and use the repository for source code, automation scripts, and reproducible tooling.

## MVP Roadmap

1. 본문 변형문제 생성기
2. 문제은행 관리와 태그/난도/출처 필터
3. 족보닷컴식 세트 선택 및 출력
4. 교사용 정답/해설 분리 출력
5. 시험 분석 리포트 자동화
6. 블로그 초안 자동 작성

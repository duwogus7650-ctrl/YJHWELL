# LiteMaxwell — 작업 추적

영상(Ansys Maxwell 2D PM모터 워크플로우)의 기능만 구현하는 경량 클론.
스택: Python 3.12 + PyQt6 + numpy/scipy + shapely + triangle + pyqtgraph.

## ⚠ 방향 전환 (영상 정밀 재분석 후)
기존 클론(단순 메뉴+툴바)은 실제 Maxwell과 구조가 달라 사용자가 반려.
0.2초 추출+phash dedup으로 308장 정밀 분석 → 실제 UI는 **리본 기반 + 이중 트리 + 히스토리 모델링 + 파라메트릭 변수**.
청사진: `docs/maxwell_ui_spec.md`. 이걸 기준으로 UI 셸부터 충실하게 재구축 예정.

## 리본 셸 재구축 (완료)
- [x] RibbonBar(탭+그룹+캡션) — Desktop/View/Draw/Model/Simulation/Results/Automation
- [x] 메뉴바 File…Help (Draw/Modeler/View/Maxwell 2D 실동작)
- [x] 좌측 이중 트리: Project Manager(디자인 구조) + Model(Sheets>재질>객체>CreateX/CoverLines)
- [x] Properties 패널: Name/Value/Unit/Evaluated/Type 그리드 + 탭(Attribute/Command/Variables), 재질콤보·색·이름 편집
- [x] 다크/라이트 테마 토글(캔버스 포함) — 라이트는 실제 AEDT 느낌
- [x] 기존 엔진 연결: 샘플모터 25객체, 메시 28,960요소, 작도/불리언/복제/미러/재질·BH편집 전부 동작
- [x] 검증 캡처: shell_1_dark / shell_2_mesh / shell_3_light / shell_4_simtab
- 남음: 솔버 이하(2~5단계)는 Project Manager의 Boundaries/Excitations/Analysis/Results 노드에 채워나갈 예정.

## 1:1 재구축 진행 (사용자: "영상 순서대로 전부 동일하게")
- [x] 리본 아이콘화 + 패널 비율 + 우클릭 메뉴 + 더블클릭 Properties 모달(uniq_v1/u_0031 근거)
- [x] 원 작도: 드래그+2클릭 둘 다, 세그먼트 기본 0, 좌표 입력바(Abs/Rel·Cart/Polar)
- [x] CreateCircle Properties 모달(Command 탭, Center/Radius 편집)
- [x] **파라메트릭 변수 시스템**: Variables 모델+식 평가(D_ro/2-T_m, sin(15deg) 등), Project Variables 대화상자, Variables 탭, 치수에 식 입력 가능
- [x] 원 작도를 사각형과 동일(press-drag, 두 점 지름) + Fit All/Fit Sel 버튼(Draw 탭)
- [x] 재질 **Select Definition 브라우저**(검색·라이브러리·결과 그리드·View/Edit/Add 버튼, uniq_v1/u_0150 근거) + 시스템 재질 라이브러리(Copper(Pure)_80C·N45UH·20PNX1200F + Granta 동·강판)
- [x] **View/Edit Material** 그리드(Name·Type·Value·Units): Relative Permeability(B-H Curve…), Bulk Conductivity, Magnetic Coercivity(Magnitude/X/Y/Z), Core Loss(Kh/Kc/Ke/Y/Kdc), Mass Density, Composition, Young/Poisson, Magnetostriction + 우측 패널(View/Edit for·Physics·Validate). BH Curve 편집기(표+그래프+Import/Export) 연결. (uniq_v1/u_0167 근거)
- [x] **폴리라인 = 파라메트릭 세그먼트**(선:길이·방향, 호:center-point arc 중심·각도). 작도 후 **CreatePolyline 더블클릭 → Segment 편집**(길이/각도 수정→형상 갱신)
- [x] 도구 토글: Polyline/Spline 다시 누르면 꺼짐 + 작도 후 Select 자동 복귀(one-shot)
- [x] **Spline 도구**(Catmull-Rom 닫힌 곡선)
- [x] **객체 스냅(Osnap)**: 기존 꼭짓점에 자동 스냅 + 호박색 사각 마커(영상의 스냅 표시)
- [x] 작도 중 **우클릭 컨텍스트 메뉴**: Done / Close Polyline / Line·Center Point Arc(세그먼트 종류) / Undo Previous Segment (Maxwell 방식). Arc는 도구 변경 안 함.
- [x] 단일클릭 선택(RubberBandDrag) + **Delete 키 삭제** + Esc=Select
- [x] SegmentDialog Qt import 크래시 수정(이게 "세그먼트 수정 안 됨"의 진짜 원인)
- [x] **세그먼트 속성 종류별 분리**(영상 u_0044/u_0089 근거): Model 트리에 CreateLine/CreateAngularArc 노드, 더블클릭 시 Line=`Segment Type/Point1/Point2`, Center Point Arc=`Segment Type/Start Point/Center Point/Angle/Plane/Number of segments` 그리드. 좌표/각도 편집→형상 갱신.
- [x] **열린 폴리라인 지원**(녹화 분석으로 발견한 핵심 버그 수정): 폴리라인/호/스플라인은 기본 **열린 곡선(LineString, 채움 없음)**. 우클릭 **Done=열림 / Close Polyline=닫힘(채움)**, **Cover Lines**(Modeler/우클릭)로 열린 선을 시트로 변환. 메시는 닫힌 형상만.
- [x] CenterPointArc 각도추적(마우스 따라 휨, >180° 가능)
- [x] 작도 미리보기 채움 제거(열린 곡선이 채워져 보이던 버그)
- [x] **우클릭 메뉴 Maxwell 일치**(실제 영상 040148/040931 근거): Escape Draw Mode / Done / Close Polyline / Undo Previous Segment / **Set Edge Type▸**(Straight·Spline·3 Point Arc·Center Point Arc). edge type 일반화(straight/cpa/3pa), 3 Point Arc 구현.
- [x] **그리드 스냅 + 스냅 마커**(닫힘=초록 삼각형 / 꼭짓점=사각형 / 그리드=십자), 시작점 클릭 시 자동 닫힘. 그리드에 점·선 맞춰 깔끔 작도(Osnap 기본 ON).
- [x] **Undo/Redo**(Ctrl+Z / Ctrl+Y, Ctrl+Shift+Z): 생성·삭제·불리언·복제·미러·Cover·세그먼트편집·치수입력 스냅샷. 삭제 복원 포함.
- [x] 열림=라인(LineString)/닫힘=형상 재확인.
- [ ] v1 잔여: Fillet(모서리 라운딩)
- [ ] BP(철손) 곡선 편집 연결
- [x] v2 해석조건: Assign Excitation(Current)/Boundary(Vector Potential)/Band(Motion)/Mesh Operation/Solve Setup → Project Manager 트리 채움 (uniq_v2/u_0043)
- [x] 솔버: 2D 자기 magnetostatic FEM(B) → 코깅토크 + Field Overlay (eafc/e6df/d4e 커밋)
- [x] **솔버 #1 Back-EMF**: 권선함수(cos 투영) 자속쇄교 λ(θ) → e=-dλ/dt 3상. feedback-runner 검증(자기일관성 0.995/평형/영합)
- [x] **솔버 #3 부하토크**: 3상 전류 회전동기 주입 + Maxwell 응력. dq 교차일치 0.89 + 전류 선형성 2.04로 검증
- [x] **솔버 #2 비선형 BH**: fixed-point ν(B) (relax 0.3, RMS 수렴, 8/10/14극 강건) + 선형 폴백 항등. 포화비 0.79
- [x] **UI**: Results 탭에 Back-EMF/Load Torque 버튼 + 3상 멀티트레이스 플롯(InducedVoltage A/B/C)
- [x] **검증 하니스**: feedback/ (solve_case.py + oracle + config). 설계무관 물리 oracle vs 회귀 베이스라인 분리. 8/10/14극·속도가변 전부 통과, 열화설계는 게이트가 차단
- [ ] v3: Transient(시간스텝)/Optimetrics에 Back-EMF·부하토크 연동, CSV 확장

## (구) 전체 로드맵 (단계적 MVP)
- [ ] **1단계 (현재): 형상편집 + 재질 + 메시** ← 진행 중
- [ ] 2단계: 경계/여자 조건 + 2D 자기 FEM(magnetostatic) 솔버
- [ ] 3단계: 회전 모션 + transient, 토크/Back-EMF
- [ ] 4단계: 결과 플롯(필드 오버레이, 토크/전압 vs 시간) + CSV 내보내기
- [ ] 5단계: 파라메트릭 스윕(설계변수, pk2pk)

## 1단계 세부 (완료)
- [x] 데이터 모델: Project/Design, Shape(Circle/Rect/Polygon, shapely 기반), Material(BH curve)
- [x] 재질 라이브러리 기본값(공기/구리/전기강판/NdFeB 자석)
- [x] 메시: triangle 기반 삼각 FE 메시 + 삼각형별 재질 판정
- [x] UI: AEDT 유사 레이아웃(좌 트리 / 중앙 2D 캔버스 / 우 속성 / 하단 로그)
- [x] 2D 모델러 캔버스: 격자·좌표축·단위(mm), 팬/줌, 그리기(원/사각/폴리곤)·선택·삭제, 불리언(합/차)
- [x] 재질 편집 다이얼로그: BH 곡선 표+그래프, CSV import/export
- [x] 메시 생성·표시 토글
- [x] 엔지니어링 팔레트 QSS(blueprint steel/cool gray/amber)
- [x] 실행 검증(스크린샷): geometry / mesh / BH editor 3종 그랩 확인

## 1단계 보완 (완료)
- [x] 다크 엔지니어링 테마(QSS + 캔버스/그래프 다크)
- [x] 격자 스냅 토글
- [x] 치수 입력 작도(Circle/Rectangle by dimensions)
- [x] Duplicate Around Axis(축 기준 회전복제) — 모터 슬롯/자석 배열용
- [x] Duplicate Along Line(이동복제), Mirror(미러/복제)
- [x] 재검증: dup-around-axis 7/8 copies, 메시 28,960 tris, 다크 캡처 3종 확인

## 1단계 리뷰
- 동작 확인: 샘플 PM모터(25 객체) 삽입 → 메시 14,529 노드 / 28,960 삼각형 → BH 편집기(표+그래프) 정상.
- 검증 방법: `verify_shots.py`가 QWidget.grab()으로 결정적 캡처(포그라운드 불필요).
- 남은 메모: 다크 테마 옵션 미정(사용자 확인 대기). 솔버는 2단계.
- 실행: `.venv\Scripts\python.exe run.py` (또는 verify_shots.py로 캡처).

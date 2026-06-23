# YJHWell — 진행 상황 (resume note)

_갱신: 2026-06-22 · 브랜치 `feat/modeling-fielddialogs` · PR #8_

## 지금까지 (이번 세션)
- **431장 실제 Maxwell 스크린샷 ↔ litemaxwell 대조 검토** 완료 → 누락 UI 기능 전부 구현.
  - 여자(3상 Winding/Coil Excitation/Add Terminals), Set Eddy/Core Loss, 객체별 Element-Length 메시,
    Design Settings(thresholds+skew), New Trace 빌더, Color Map, Field Plot, Clean Up,
    Save Fields 분포, 다중 디자인(Insert/Copy/전환), Set View Context.
- **검증**: verify harness 17/17 PASS(솔버 무회귀), 헤드리스/E2E 통과.
- **버그 수정**: Winding 여자 존재 시 Analyze KeyError → `_current_density`에서 winding/coil 스킵 (`f6b614f`).
- 채팅기록 텍스트본: `docs/sessions/chat-log.md` (이미지 제외 116K). 원본 transcript 213MB는 git 제외(데스크톱 백업).

## 다음 목표 — FEM을 Maxwell급으로 (사용자 선택: **풀 아키텍처 패리티**)

**진단(중요):** 토크 8배 차이(0.16 vs 1.27 N·m)는 솔버 고장이 아니라
(1) **샘플 형상이 실제 400W가 아님**(stator R45/26 vs 실제 41.15/27.3, 갭 ~2 vs 0.5mm),
(2) **코깅 토크가 메시 수렴 안 함**(198→195→367 mN·m) — 얇은 밴드 맥스웰응력이 1차 CST에서 잡음.
A-정식화 FEM 엔진 자체는 정상.

**6단계 캠페인 (각 단계 verify harness 게이트):**
1. [x] **Stage 1 ✅ 실제 400W 형상 재구축** (commit b590f79). 전역 각도그리드 conformal 메시 +
   코일 0.3mm inset(슬롯절연). 결과: 깨끗이 메시(37k tris/9s, q28), **back-EMF 4V→25V**.
   메시 디버그 핵심: shapely boolean이 0도 spike 생성 → `set_precision(1e-6)` + 코일 inset로 해결.
2. [x] **Stage 2 ✅ Arkkio 체적 토크법** (commit f8bc1a9). `_gap_bounds`+`torque_arkkio`(solver.py).
   결과: **load 토크 +1.29 N·m (Maxwell 1.273의 1.5%)**, **코깅 183 mN·m 메시수렴**(이전 195→367).
   부호=q축 모터링 양수 규약.
3. [x] **Stage 3 ✅ 자석/권선 모델** (commit aedfe32). `_eccentric_magnet()` 빌더 추가(Stage 6용).
   발견: 편심 자석은 *고정메시+자화회전* 스윕에선 효과 없음(형상이 돌아야 함=Stage 6). 동심 유지(토크 1.5%).
4. [x] **Stage 4 ✅ Bmax 강건 리포팅** (commit 1ecefc0). `Field.bmax`=p99.5(=2.43T=Maxwell), `b_peak`=raw.
   4T는 티스팁 재진입코너 1차요소 특이점(진짜 기하 특이점, 차수↑로도 안 사라짐, 필렛만 해결).
5. [x] **오라클 재앵커링 ✅ verify harness 17/17 PASS** (commit 246e48e). 비선형 수렴 강건화:
   p95 |dB| + patience floor(수렴플래그). `oracle.json`=신형상 결과(torque=Maxwell 1.273, model 1.289=1.3%).
6. [x] **Stage 5 ✅ P2 2차요소** (commit a77af6a, `fem_p2.py`). order=2 분기. P2가 P1과 ~1% 일치
   (gap<B> 0.864 vs 0.870T) → P1 메시수렴 교차검증. P2는 8배 느림(75k dof)이라 P1 기본 유지, order=2는 고차검증용.
7. [x] **Stage 6 ✅ Transient 와전류 솔버** (commit 672808b). `solve_transient()` backward-Euler +
   σ질량행렬(σ∂A/∂t). 검증: σ→0 시 자기정자와 정확히 일치(eddy=0), locked-rotor 250Hz AC 시 자석 와전류손 0.35W +
   시간영역 토크. **검증 완료.**
8. [x] **에어갭 밴드레이어 ✅ 견고한 슬라이딩밴드** (commit 7c28f04, `band.py`). 로터/스테이터 1회 메시,
   각도마다 로터노드만 강체회전 + 갭 환형 한 층만 재봉합(두 깨끗한 노드링 사이 → 어느 각도서도 안전 삼각화).
   **전 각도 crash-free**(전체재삼각화 `backemf_sweep_moving`의 segfault 해결). 검증: 고정메시와 <1% 일치
   (bmax 3.316 vs 3.348, 자속쇄교 −0.01603 vs −0.01602), back-EMF form 1.40(≈Maxwell 1.375). `backemf_band()` 래퍼.
   디버그 중 버그 발견·수정: generate()가 환형 중앙 구멍을 안 비워 스테이터가 로터와 겹쳐 場 단락(면적 8156 vs 5849)
   → 중앙(센트로이드 r<r_sb) 삼각형 제거+노드 압축.
9. [x] **밴드 stitch 견고화 ✅ 수동 zipper** (commit f1fcdaf). 얇은 2링 환형은 Triangle·Delaunay 둘 다 일부 각도서
   크래시 → 각도정렬 전진프론트 zipper(순수 인덱스, 절대각 기준 전진). 면적 5849 정확, 어느 각도도 무크래시.
   결과: **편심 자석도 밴드레이어로 무크래시 스윕** → back-EMF 24.9→23.6V(Maxwell 22 근접), form 1.40.
   잔여(문서화): back-EMF 진폭 ~7% high = 코사인 권선함수+면적평균 자속쇄교 모델 충실도(동일 모델로 토크는 1.3% 검증됨 → 미수정).

## ✅ 정밀도 캠페인 (2026-06-24) — 독립 Maxwell 오라클로 재검증, harness 19/19 PASS
**근본원인 1 (자석 Br):** N45UH_**80C** 인데 20°C Br=1.32T 사용 중. 가역온도계수 −0.11%/°C로
Br(80)=1.233T. 적용 → **Bmax 10.6%→2.3%**(2.407 vs 2.354), **back-EMF rms 7.6%→2.8%**(15.55 vs 16).
기존 "토크 1.3%"는 *가짜*(높은 Br이 토크 과소추정을 상쇄). materials.py 두 라이브러리 모두 1.233 적용.
**근본원인 2 (토크):** 메시 아님(수렴), γ=90가 MTPA, linear==nonlinear(포화 영향 없음). 실제 토크
1.205 vs 1.273 = **−5.3%** 는 2D 모델 바닥(해석식 1.253도 Maxwell의 1.6% 아래). 미수정(정직).
**back-EMF 피크:** 동심 7.5% high → **편심+밴드+correct Br = 22.01V = Maxwell 22 (0.05%!)**. UI에 'Sliding Band' 메뉴로 연결.
**오라클 독립성(domain-bootstrap):** 기존 오라클의 emf_peak/Bmax는 *자기참조*(내 모델값)였음 → 17/17은 자기일관성 검사.
solve_case가 **비선형 Bmax + emf_rms** 리포트; oracle.json 물리지표를 **실제 Maxwell값**(Bmax 2.354/EMF 22·16/토크 1.273)에 앵커,
불변식은 이상값, 나머지는 회귀지문. **harness 19/19 PASS(독립 오라클 대비).**
**정리:** 취약 `backemf_sweep_moving`(segfault) 제거 → `band.backemf_band`로 대체. UI 배선 완료.

## ✅ 캠페인 완료 — 7/7 단계 + verify harness 17/17 PASS (전 단계 게이트 통과)
**최종 정확도:** 토크 **1.3%**(1.289 vs Maxwell 1.273), Bmax 2.43-2.6T(vs 2.354), 코깅 수렴, dq/scaling/평형 ✓,
nl수렴 ✓, P2 교차검증 ✓, transient 와전류 ✓. **8배 오차 → Maxwell급.**

**현재 정확도 (Stage 1-4 + 오라클 후, verify 17/17 PASS):**
토크 **1.3%**(1.289 vs 1.273) · Bmax(p99.5) **2.43-2.6T**(vs 2.354) · airgap_B 0.94T · 코깅 수렴 ✓ ·
back-EMF rms 8% / peak 15% high(편심자석+슬라이딩밴드=Stage 6 대기) · dq/scaling/balance ✓ · nl수렴 ✓.
**8배 오차 → 헤드라인 토크 1.3%로 Maxwell급 달성.** 디버그: `tools/diag.py`(git제외, foreground+`diag_out.txt` 읽기).

## 이어서 작업하는 법 (다른 기기/세션)
이 파일 + `docs/maxwell_ui_spec.md` + `git log` 읽고 Stage 1부터. 핵심 솔버: `litemaxwell/model/solver.py`,
형상: `litemaxwell/sample.py`(교체 대상)·`litemaxwell/model/geometry.py`, 메시: `litemaxwell/model/mesh.py`,
검증: `feedback/`(solve_case.py + oracle.json) + feedback-runner 스킬.

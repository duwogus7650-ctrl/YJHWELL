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
1. [ ] **Stage 1 — 실제 400W 파라메트릭 형상 재구축** (D_ro=53.6, D_so=82.3, g=0.5, T_m=2.9, L_stk=28,
   파라메트릭 티스 W_t=5.6/H_t=9.25/W_so=3, 자석 a_m=0.89 span + MagnetR=1.9 필렛, Zc=14, I_rms=8.2). ← **다음 작업**
2. [ ] **Stage 2 — Arkkio 체적 토크법** (얇은 밴드 → 갭 환형 체적적분; 코깅 수렴).
3. [ ] **Stage 3 — 권선 자속쇄교 정밀화** (기본파 cos 투영 → 실제 도체분포; back-EMF 크기 보정).
4. [ ] **Stage 4 — 에어갭 레이어 메시 + 수렴 검증**.
5. [ ] **Stage 5 — 2차요소(P2 삼각형)** 자기정자 조립.
6. [ ] **Stage 6 — 진짜 transient time-stepping + 와전류(∂A/∂t) + 슬라이딩밴드 회전**.

**오라클(목표값):** 정격 평균토크 **1.273 N·m**(=400W/314.16rad/s), 상 back-EMF **~22V peak/16V rms**,
B max **~2.354 T**, 무부하 코깅 pk-pk MagnetR 1.0→1.5mm 시 69→34 mN·m. FEMM 교차검증 병행.
→ `feedback/oracle.json`을 (현재 샘플 baseline에서) **실제 Maxwell 값으로 재앵커링**하는 것이 목표.

## 이어서 작업하는 법 (다른 기기/세션)
이 파일 + `docs/maxwell_ui_spec.md` + `git log` 읽고 Stage 1부터. 핵심 솔버: `litemaxwell/model/solver.py`,
형상: `litemaxwell/sample.py`(교체 대상)·`litemaxwell/model/geometry.py`, 메시: `litemaxwell/model/mesh.py`,
검증: `feedback/`(solve_case.py + oracle.json) + feedback-runner 스킬.

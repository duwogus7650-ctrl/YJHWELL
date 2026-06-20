# Maxwell 2D UI 사양 (영상 정밀 분석 결과)

출처: 영상 3개를 0.2초 간격 추출 + perceptual-hash 중복제거 → 308장(v1 191/v2 83/v3 34)을 8개 에이전트로 정밀 분석.
대상: **Ansys Electronics Desktop 2024 R1 + Maxwell 2D**. 프로젝트 `400W_10P12S_AMR_1` (400W, 10극 12슬롯 PM모터).
디자인: `BasicModel_RatedLoad (Transient, XY)`, `BasicModel_NoLoad (Transient, XY)`, `4. 400W_NoLoad_BasicModel_10P12S_Optimized`.

## 1. 윈도우 전체 구조 (← 기존 클론이 가장 크게 틀렸던 부분)

```
┌ Title bar: Ansys Electronics Desktop 2024 R1 - <proj> - <design> - 3D Modeler - [<proj> - <design> - Modeler]
├ Menu bar: File  Edit  View  Project  Draw  Modeler  Maxwell 2D  Tools  Window  Help
│           (플롯 활성 시 Draw/Modeler → Report2D 로 교체)
├ RIBBON (탭): Desktop | View | Draw | Model | Simulation | Results | Automation | Ansys Minerva | Learning and Support
├──────────────┬─────────────────────────────────────────────┬──────────────┐
│ Project      │                                             │ Properties   │
│ Manager      │            3D Modeler (2D view)             │ (Name|Value| │
│ (tree)       │   - 흰 배경 격자, X(빨강)/Y(초록)/Z 축 트라이어드   │  Unit|Eval|  │
│ ────────     │   - 우상단 "Ansys 2024 R1" 워터마크            │  Type)       │
│ Model        │   - 하단 mm 스케일바, "Time=..." 오버레이        │ 탭: Attribute│
│ history tree │                                             │ /Command/    │
│              │                                             │ Coord/Vars   │
├──────────────┴─────────────────────────────────────────────┴──────────────┤
│ Progress | Message Manager (탭)                                            │
├ Status bar: (좌)"Nothing is selected"/"N objects selected"  (우)"Hide N Messages" "Hide Progress"
```

### 리본 Draw 탭 그룹 (좌→우)
- Clipboard: Save, Cut, Copy, Paste, Delete, Undo, Redo
- Select: `Select: Object▼`, `Select by Name`
- View: Zoom, Pan, Rotate▼, Orient▼, Fit All, Fit Selected
- Draw primitives (아이콘): point/line/arc/spline/rectangle/circle/ellipse/polyline/polygon
- Modeler ops: Move, Along Line, Rotate, Around Axis, Mirror, Thru Mirror
- Boolean: Unite, Subtract, Split, Imprint, Intersect
- Surface: Fillet, Chamfer, Surface▼, Sheet▼, Edge▼
- CS: Relative CS▼, Face CS, Object CS▼
- Measure: Measure▼, Ruler, Units
- Grid, In Plane▼
- Material: Model▼, `<material>▼`(예 vacuum), Material

### 좌측 트리 1 — Project Manager
```
400W_10P12S_AMR_1*               (프로젝트)
  BasicModel_NoLoad (Transient, XY)
  BasicModel_RatedLoad (Transient, XY)*   (활성=굵게)
    3D Components
    Model
      MotionSetup1
        Moving1
    Boundaries
      VectorPotential1
    Excitations
      Current_1 … Current_10
      PhaseA  PhaseB  PhaseC
    Parameters
    Mesh
      Band  Coil  Core  Magnet  Region
    Analysis
      Setup1
    Optimetrics
      ParametricSetup1
    Results
      Torque Plot 1
        Moving1.Torque
      Winding Plot 1
        InducedVoltage(PhaseA) / (PhaseB) / (PhaseC)
    Field Overlays
      B > Mag_B1 (Setup1 : Transient, Time=0s)
  Definitions
```

### 좌측 트리 2 — Model(작도 히스토리)
```
Model
  Sheets
    20PNX1200F_20C            (재질별 그룹)
    Arnold_Magnetics_N45UH_80C
    Copper (Pure)_80C
    vacuum
      <Body>                  (예: Rotor, Stator, Magnet, Coil, Band, Region)
        CreateCircle / CreatePolyline / CreateRectangle
        CoverLines
        Subtract / Unite / DuplicateAroundAxis / Fillet / CreateFaceCS …
  Coordinate Systems
    Global, RelativeCS1/2, FaceCS1…FaceCS10
  Planes
  Lists
```

## 2. 핵심 대화상자 (필드까지)
- **Properties**(모달, 탭 Attribute/Command/Segment/Coord System): Name, Material("vacuum"), Solve Inside☑, Orientation Global, Model☑, Group Model, Display Wireframe, Material Appearance, Color(스와치), Transparent 0 · 버튼 확인/취소/적용(A)
- **Color**(Windows 표준 색 선택기)
- **Add Variable**: Name, Unit Type, Unit, Value, Type=Local Variable
- **Duplicate Around Axis**: Axis(X/Y/Z), Angle(예 720deg/N_pole), Total number, Attach To Original Object☐
- **Subtract**: Blank Parts / Tool Parts, Clone tool objects before operation☐
- **Split**
- **Select Definition**(재질 브라우저): Search by Name, by Name/by Property, Libraries([sys]ArnoldMagnetics/Benchmark/ChinaSteel), 결과 그리드(Name|Location|Origin), 버튼 View/Edit Materials/Add/Clone/Remove/Export
- **View / Edit Material**: Material Name, 속성 그리드(Name|Type|Value|Units) — Relative Permeability(Simple 또는 Nonlinear=B-H Curve), Bulk Conductivity, Magnetic Coercivity(Vector: Magnitude+X/Y/Z), Core Loss Model(None / Electrical Steel: Kh/Kc/Ke/Y/Kdc/Equiv.Cut Depth), Mass Density, Composition(Solid / Lamination: Stacking Factor/Direction), Young/Poisson, Magnetostriction · Physics 체크(Electromagnetic/Thermal/Structural)
- **BH Curve**: Temperature, Normal/Intrinsic, Swap X-Y/Import/Export Dataset, H[A/m]|B[T] 표, 그래프, Intercepts
- **BP Curve(철손)**: B[T]|P 표, Core Loss Unit(w/m^3), Mass Density, Frequency(60Hz), Thickness, Conductivity, Kh/Kc/Ke/Y
- **Motion Setup**: 탭 Type/Data/Mechanical/Post Processing — Motion Type(Translation/Rotation/Periodic/Non-Cylindrical), Moving Vector(Global::Z), Positive/Negative, Initial Position(init_pos=-15deg)
- **Winding**: Name, Type=Current, Solid/Stranded, Current/Resistance/Inductance/Voltage(+단위), Number of parallel branches
- **Add Terminals**: Coil Terminal|Conductor Number|Currently Assigned To
- **Element Length Based Refinement**(메시): Name, Apply to Initial Mesh, Enable, Set maximum element length(+mm), Max additional elements
- **Solve Setup**: 탭 General/Save Fields/Advanced/Solver/… — Name=Setup1, Enabled, Adaptive Time Step, Stop time, Time step
- **Set Eddy Effect**: 객체별 체크 그리드
- **2D Design Settings**: Material Thresholds 등 탭
- **Create Field Plot**: Name/Folder, Quantity(Mag_B/B_Vector/Flux_Lines/Mag_H/…), In Volume 목록 → 자속밀도 컬러 컨투어
- **Report / New Trace(s)**: Solution/Domain, 탭 Trace/Families, Primary Sweep=Time, X/Y, Category(Torque/Speed/Position/Winding/Loss/…), Quantity(Moving1.Torque/LoadTorque, InducedVoltage/FluxLinkage/InputCurrent(PhaseA/B/C)), Function
- **Setup Sweep Analysis**(Optimetrics 파라메트릭): 변수 MagnetR 1.0–1.5mm 스윕
- **Clean Up Solutions**, **Analysis Configuration**(머신/코어)

### 우클릭 컨텍스트 메뉴 (핵심)
- 객체: Assign Material…, Assign Band▸, Assign Boundary▸, Assign Excitation▸(Coil/Current/Current Density/Permanent Magnet Field/Add Winding/Set Eddy Effects/Set Core Loss…), Assign Mesh Operation▸, Fields▸, Plot Mesh…
- Analysis/Setup1: Analyze, Generate Mesh, Revert to Time Zero, Profile…
- Results: Create Transient Report▸(Rectangular Plot/Data Table/…), Create Fields Report▸

## 3. 워크플로우 (영상 1→2→3)
1. **V1 형상+재질**: AEDT 실행 → 새 프로젝트 → Insert Maxwell 2D → 파라메트릭 변수(D_ro, T_m, N_pole=10, N_slot=12, g, …)로 region/rotor/shaft/magnet/stator/teeth/coil 작도(primitive + DuplicateAroundAxis + Subtract/Unite + Fillet) → Select Definition으로 재질 할당(vacuum/Copper(Pure)_80C/N45UH/20PNX1200F) → BH·BP 곡선 편집
2. **V2 조건+메시+솔브**: Band에 Motion(Rotation, Z, init_pos=-15deg) → 경계 VectorPotential1 → 권선 PhaseA/B/C(Winding+Add Terminals) → 메시(Element Length Based Refinement: Band/Coil/Core/Magnet/Region) → Solve Setup(Transient) → Set Eddy Effects → Analyze → 리포트(Torque, Winding Back-EMF) → 메시 표시 → Field Overlay(Mag_B 컬러플롯)
3. **V3 파라메트릭+결과**: Clean Up Solutions → Optimetrics Parametric(MagnetR 1.0–1.5mm) → 실행 → 변동별 Torque(pk2pk) → CSV 내보내기 → Excel에서 pk2pk vs MagnetR 분석 → xlsx 저장

## 4. 재구축 시사점 (기존 클론 대비 변경점)
- **단순 메뉴+툴바 → 리본(탭) UI**로 교체
- 좌측 **이중 트리**(Project Manager + Model 히스토리) 도입
- Properties를 **Name/Value/Unit/Evaluated/Type 그리드 + 탭(Attribute/Command/…)** 로
- 작도를 **히스토리 기반**(각 객체가 CreateX→CoverLines→Boolean… 노드)으로
- **파라메트릭 변수 시스템**(D_ro 등 식 평가) — Maxwell 핵심
- 메뉴/대화상자 한글 혼용(확인/취소/적용)도 실제와 동일

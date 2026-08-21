"""파라미터 추출 설정. GUI의 Extraction Config 페이지가 이 값을 채운다."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Optional, Tuple

VthMethod = Literal["constant_current", "linear_extrapolation"]


@dataclass
class ExtractionConfig:
    """추출 알고리즘 설정. 극성은 여기 두지 않는다 — curve마다 이미 device.polarity로
    갖고 있으므로(같은 설정을 NMOS/PMOS curve에 그대로 재사용 가능하도록) 중복을 피한다.
    """

    # Vth - Constant Current
    vth_method: VthMethod = "constant_current"
    cc_current_ref: float = 1e-7  # A, 기본 100nA
    cc_normalize_by_wl: bool = True  # True면 기준전류 = cc_current_ref * (W/L)

    # Vth - Linear Extrapolation
    le_vd_target: Optional[float] = None
    le_fit_vg_range: Optional[Tuple[float, float]] = None
    le_apply_vd_half_correction: bool = True

    # SS
    ss_vg_range: Optional[Tuple[float, float]] = None
    ss_min_r2: float = 0.98

    # Ion / Ioff (None이면 극성에 따라 곡선의 최대/최소 Vg를 사용)
    ion_vg: Optional[float] = None
    ioff_vg: Optional[float] = None

    # Id-Vd 지표 (Ron: 선형영역, gds: 포화영역)
    ron_vd_range: Optional[Tuple[float, float]] = None
    gds_vd_range: Optional[Tuple[float, float]] = None

    # DIBL: 비교에 쓸 두 Vd 조건 (없으면 split 내 관측된 최소/최대 Vd 사용)
    dibl_vd_pair: Optional[Tuple[float, float]] = None

    # 공통: 분석에 사용할 Vg 범위 제한
    curve_vg_analysis_range: Optional[Tuple[float, float]] = None

    # 필드효과 이동도(μFE, 포화영역: sqrt(Id)-Vg 기울기 방식). Cox는 데이터에 없어 둘 중
    # 하나로 입력받는다 — mobility_cox_F_cm2가 있으면 그걸 우선 쓰고, 없으면 두께+비유전율로
    # 계산한다. 둘 다 없으면 이동도 계산은 (에러 없이) 그냥 건너뛴다 — 선택적 지표이므로.
    mobility_cox_F_cm2: Optional[float] = None
    mobility_oxide_thickness_nm: Optional[float] = None
    mobility_oxide_rel_permittivity: Optional[float] = None
    mobility_fit_vg_range: Optional[Tuple[float, float]] = None

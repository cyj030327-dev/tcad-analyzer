"""분석 결과 요약 보고서(HTML) 자동 생성.

CSV/Excel 내보내기(exporters.py)는 표 하나만 담는 반면, 여기서는 실행 결과 표 + Id-Vg
비교 그래프 + 최적 소자 추천 결과를 한 파일로 묶는다. 새 외부 패키지(reportlab 등) 없이
matplotlib + 표준 라이브러리만으로, 브라우저에서 바로 열어보거나 인쇄해서 PDF로 저장할 수
있는 자체완결 HTML 파일을 만든다(이미지도 base64로 파일 안에 그대로 담아, 파일 하나만
전달하면 그래프도 함께 보인다).
"""

from __future__ import annotations

import base64
import html
import io
from datetime import datetime
from typing import List, Optional

import matplotlib
import numpy as np
import pandas as pd

from ..analysis import (
    DEFAULT_METRIC_DIRECTIONS,
    OptimizationProfile,
    build_split_metric_table,
    recommend_optimal,
    to_dataframe,
)
from ..models import Curve, CurveType, ExtractedParameter

# gui/mpl_canvas.py와 동일하게 지정 — io_export는 GUI 없이도(예: 스크립트, 테스트) 이 모듈
# 하나만으로 그래프가 있는 보고서를 만들 수 있어야 하므로, GUI가 이미 떠 있어 이 설정이
# 됐을 거라고 가정하지 않고 여기서도 한 번 더 지정한다.
matplotlib.rcParams["font.family"] = ["Malgun Gothic", "DejaVu Sans"]
matplotlib.rcParams["axes.unicode_minus"] = False

PROFILE_LABELS = {
    OptimizationProfile.LOW_POWER: "저전력",
    OptimizationProfile.HIGH_PERFORMANCE: "고성능",
    OptimizationProfile.BALANCED: "밸런스",
}

_CSS = """
body{font-family:'Segoe UI','Malgun Gothic',sans-serif;margin:0;background:#f4f6f9;color:#1f2933;}
.wrap{max-width:980px;margin:0 auto;padding:40px 28px 80px;}
h1{font-size:22px;margin:0 0 4px;}
.meta{color:#6b7684;font-size:13px;margin:0 0 32px;}
h2{font-size:16px;color:#00789e;border-bottom:2px solid #dfe4ea;padding-bottom:8px;margin:36px 0 16px;}
.cards{display:flex;flex-wrap:wrap;gap:14px;margin:0 0 8px;}
.card{background:#fff;border:1px solid #dfe4ea;border-radius:8px;padding:14px 18px;min-width:130px;}
.card .v{font-size:22px;font-weight:700;color:#0099cc;}
.card .l{font-size:12px;color:#6b7684;}
.callout{background:#e5f5fa;border:1px solid #d8eef4;border-radius:8px;padding:14px 18px;margin:0 0 16px;font-size:13.5px;}
.callout b{color:#00789e;}
table{border-collapse:collapse;width:100%;font-size:12.5px;background:#fff;margin:0 0 8px;}
th,td{border:1px solid #dfe4ea;padding:6px 9px;text-align:left;white-space:nowrap;}
th{background:#e5f5fa;color:#00789e;}
tr:nth-child(even) td{background:#fafbfc;}
.muted{color:#6b7684;font-size:12.5px;}
.tbl-scroll{overflow-x:auto;border:1px solid #dfe4ea;border-radius:8px;margin:0 0 20px;}
img.chart{max-width:100%;border:1px solid #dfe4ea;border-radius:8px;margin:0 0 20px;background:#fff;}
footer{color:#6b7684;font-size:11.5px;margin-top:48px;border-top:1px solid #dfe4ea;padding-top:14px;}
"""


def _fig_to_base64_png(fig, dpi: int = 130) -> str:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=dpi, bbox_inches="tight")
    buf.seek(0)
    return base64.b64encode(buf.read()).decode("ascii")


def _build_idvg_overview_chart(curves: List[Curve], max_curves: int = 40) -> Optional[str]:
    """저장된 curve들의 Id-Vg를 로그 스케일로 겹쳐 그린 PNG를 base64 문자열로 반환.
    Id-Vg curve가 하나도 없으면 None(그 절 자체를 생략하기 위해)."""
    import matplotlib.pyplot as plt

    id_vg_curves = [c for c in curves if c.curve_type == CurveType.ID_VG]
    if not id_vg_curves:
        return None

    fig, ax = plt.subplots(figsize=(8, 4))
    for c in id_vg_curves[:max_curves]:
        with np.errstate(invalid="ignore"):
            y = np.abs(c.id_)
        ax.plot(c.vg, y, linewidth=0.9, alpha=0.75)
    ax.set_yscale("log")
    ax.set_xlabel("Vg (V)")
    ax.set_ylabel("|Id| (A)")
    shown = min(len(id_vg_curves), max_curves)
    ax.set_title(f"Id-Vg 비교 (전체 {len(id_vg_curves)}개 중 {shown}개 표시)")
    fig.tight_layout()
    img = _fig_to_base64_png(fig)
    plt.close(fig)
    return img


def _fmt(v) -> str:
    if isinstance(v, float):
        if np.isinf(v):
            return "∞" if v > 0 else "-∞"
        if np.isnan(v):
            return "-"
        return f"{v:.4g}"
    return html.escape(str(v))


def _df_to_html_table(df: pd.DataFrame, max_rows: int = 400) -> str:
    if df is None or df.empty:
        return '<p class="muted">표시할 데이터가 없습니다.</p>'
    shown = df.head(max_rows)
    header = "".join(f"<th>{html.escape(str(c))}</th>" for c in shown.columns)
    body_rows = []
    for _, row in shown.iterrows():
        cells = "".join(f"<td>{_fmt(v)}</td>" for v in row)
        body_rows.append(f"<tr>{cells}</tr>")
    note = ""
    if len(df) > max_rows:
        note = f'<p class="muted">…외 {len(df) - max_rows}행은 생략했습니다(전체 표는 CSV/Excel 내보내기를 이용하세요).</p>'
    return (
        f'<div class="tbl-scroll"><table><thead><tr>{header}</tr></thead>'
        f"<tbody>{''.join(body_rows)}</tbody></table></div>{note}"
    )


def generate_html_report(
    params: List[ExtractedParameter],
    curves: List[Curve],
    profile: OptimizationProfile = OptimizationProfile.BALANCED,
    metric_names: Optional[List[str]] = None,
    title: str = "TCAD 소자 분석 결과 보고서",
) -> str:
    """추출된 파라미터 + curve로부터 자체완결 HTML 보고서 문자열을 만든다.

    metric_names를 지정하지 않으면, 프로그램이 알고 있는 대표 지표(DEFAULT_METRIC_DIRECTIONS)
    중 실제로 이 데이터에 존재하는 것만 자동으로 골라 "최적 소자 추천"에 쓴다 — 버튼 하나로
    바로 만들 수 있게 하기 위해서다(세부 조정은 Comparison 탭의 "최적 소자 추천"을 쓰면 된다).
    """
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M")
    df = to_dataframe(params)
    present_metrics = sorted(df["param_name"].unique()) if not df.empty else []
    if metric_names is None:
        metric_names = [m for m in DEFAULT_METRIC_DIRECTIONS if m in present_metrics]

    n_splits = df["split_label"].nunique() if not df.empty else 0
    n_devices = df["device_id"].nunique() if not df.empty else 0
    id_vg_curves = [c for c in curves if c.curve_type == CurveType.ID_VG]
    id_vd_curves = [c for c in curves if c.curve_type == CurveType.ID_VD]

    sections = []

    # ------------------------------------------------------------- 요약
    sections.append(
        "<h2>요약</h2>"
        '<div class="cards">'
        f'<div class="card"><div class="v">{len(curves)}</div><div class="l">전체 curve</div></div>'
        f'<div class="card"><div class="v">{n_devices}</div><div class="l">소자 종류</div></div>'
        f'<div class="card"><div class="v">{n_splits}</div><div class="l">공정 조건(split)</div></div>'
        f'<div class="card"><div class="v">{len(params)}</div><div class="l">추출된 지표 값</div></div>'
        "</div>"
    )

    # ------------------------------------------------------------- 추천
    if metric_names and not df.empty:
        result = recommend_optimal(params, metric_names=metric_names, profile=profile)
        if result.top_recommendation is not None:
            weight_txt = ", ".join(
                f"{name} {w * 100:.0f}%" for name, w in sorted(result.weights_used.items(), key=lambda kv: -kv[1]) if w > 0
            )
            sections.append(
                "<h2>최적 소자 추천</h2>"
                f'<div class="callout">프로파일 <b>{PROFILE_LABELS.get(profile, profile.value)}</b> 기준, '
                f"사용된 지표: {html.escape(', '.join(metric_names))}<br>"
                f"가중치: {html.escape(weight_txt) if weight_txt else '(없음)'}<br>"
                f"Pareto 후보군({len(result.pareto_candidates)}개): {html.escape(', '.join(result.pareto_candidates))}<br>"
                f"<b>추천 split: {html.escape(result.top_recommendation)}</b></div>"
            )
            sections.append(_df_to_html_table(result.scored_table.reset_index().rename(columns={"index": "split_label"})))
        else:
            sections.append(
                "<h2>최적 소자 추천</h2><p class=\"muted\">추천할 split이 없습니다(데이터가 부족합니다).</p>"
            )

    # ------------------------------------------------------------- Id-Vg 그래프
    chart_b64 = _build_idvg_overview_chart(curves)
    if chart_b64:
        sections.append(
            "<h2>Id-Vg 비교</h2>"
            f'<img class="chart" src="data:image/png;base64,{chart_b64}" alt="Id-Vg 비교 그래프">'
        )

    # ------------------------------------------------------------- 지표별 split 요약
    if metric_names and not df.empty:
        wide = build_split_metric_table(params, metric_names).reset_index().rename(columns={"index": "split_label"})
        sections.append("<h2>지표별 split 요약</h2>")
        sections.append(_df_to_html_table(wide))

    # ------------------------------------------------------------- 전체 파라미터 원자료
    sections.append("<h2>전체 파라미터 표</h2>")
    sections.append(_df_to_html_table(df.drop(columns=["curve_id"], errors="ignore")))

    if id_vd_curves:
        sections.append(
            f'<p class="muted">Id-Vd curve {len(id_vd_curves)}개도 함께 임포트되어 있습니다 '
            "(Ron/gds 등에 반영됨, 그래프는 위 표만 참고하세요).</p>"
        )

    body = "\n".join(sections)
    return f"""<!doctype html>
<html lang="ko"><head><meta charset="utf-8"><title>{html.escape(title)}</title>
<style>{_CSS}</style></head>
<body><div class="wrap">
<h1>{html.escape(title)}</h1>
<p class="meta">생성 일시: {generated_at} · TCAD 소자 특성 분석기 자동 생성</p>
{body}
<footer>이 파일은 TCAD 소자 특성 분석기에서 자동 생성되었습니다. 브라우저에서 열어 인쇄(Ctrl+P) → PDF로 저장하면 제출용 문서로도 쓸 수 있습니다.</footer>
</div></body></html>"""

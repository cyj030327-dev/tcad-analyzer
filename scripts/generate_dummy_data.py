"""실제 Sentaurus 출력 파일을 받기 전, 개발/테스트용 더미 데이터를 생성하는 스크립트.

생성물 (기본 출력 위치: sample_data/):
  plt/n<N>_des.plt         : NMOS/PMOS × 온도 split × repeat별 Id-Vg(저Vd/고Vd) + Id-Vd 곡선
  plt/gtree.dat             : 위 노드들의 split(Temperature, Repeat) 매핑 (Tcl 스타일)
  plt/n<N>_des.cmd          : 일부 노드에 대한 sdevice 명령 파일 예시(Electrode/Solve/Physics)
  plt/edge_cases/*.plt      : 파서 견고성 확인용(컬럼 수 불일치, 멀티라인 VARIABLES, CRLF 등)
  tables/summary.csv        : 이미 추출됐다고 가정한 파라미터 테이블(Lot/Split/Device/Vth/SS)

물리식은 정밀한 TCAD 시뮬레이션이 아니라 "그럴듯한 모양 + 재현 가능한 noise"가 목적이다.

사용법: python scripts/generate_dummy_data.py --out sample_data --n-splits 3 --repeats 1
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Dict, List, Sequence

import numpy as np

RNG = np.random.default_rng(42)

VG_STEP = 0.02
VD_LIN = 0.05
VD_SAT = 1.0
K_COEF = 2.0e-4  # A/V^2 급 계수
I0_LEAK = 1.0e-13  # A, subthreshold 전류 스케일
LAMBDA_CLM = 0.05  # 채널 길이 변조 계수(gds에 영향)


def _sign(polarity: str) -> int:
    return 1 if polarity == "NMOS" else -1


def _vg_sweep(polarity: str) -> np.ndarray:
    if polarity == "NMOS":
        return np.arange(-0.2, 1.2 + 1e-9, VG_STEP)
    return np.arange(-1.2, 0.2 + 1e-9, VG_STEP)


def _add_noise(id_array: np.ndarray, rel: float = 0.01, floor: float = 1e-17) -> np.ndarray:
    noise = RNG.normal(0.0, rel * np.abs(id_array) + floor, size=id_array.shape)
    return id_array + noise


def id_vg_curve(vg: np.ndarray, vth: float, ss_mv: float, polarity: str) -> np.ndarray:
    """subthreshold(지수) + above-threshold(제곱법칙) 근사로 그럴듯한 Id-Vg 곡선 생성.

    above-threshold 항에 순수 max(x,0)^2를 쓰면, k(제곱법칙 계수)가 I0(subthreshold 스케일)보다
    훨씬 커서 문턱 바로 위에서 전류가 수 decade씩 순간적으로 튀는 인위적인 불연속이 생긴다.
    대신 softplus 기반의 smooth-max(= s*log1p(exp(x/s)))를 써서 문턱 부근을 S_thermal 폭으로
    부드럽게 이어준다(x가 클 때는 max(x,0)과 동일하게 수렴).
    """
    s = _sign(polarity)
    overdrive = s * (vg - vth)
    s_thermal = (ss_mv / 1000.0) / np.log(10)
    id_sub = I0_LEAK * np.exp(np.clip(overdrive / s_thermal, -50, 50))
    smooth_relu = s_thermal * np.log1p(np.exp(np.clip(overdrive / s_thermal, -50, 50)))
    id_above = K_COEF * smooth_relu**2
    id_mag = id_sub + id_above
    return s * id_mag


def id_vd_curve(vd_mag: np.ndarray, vg_bias: float, vth: float, polarity: str) -> np.ndarray:
    """선형+포화 영역을 근사한 Id-Vd 곡선(고정 Vg bias)."""
    s = _sign(polarity)
    overdrive = max(s * (vg_bias - vth), 1e-6)
    id_lin = K_COEF * (2 * overdrive * vd_mag - vd_mag**2)
    id_sat = K_COEF * overdrive**2 * (1 + LAMBDA_CLM * vd_mag)
    id_mag = np.where(vd_mag < overdrive, np.clip(id_lin, 0, None), id_sat)
    return s * id_mag


def write_tecplot_file(
    path: Path,
    title: str,
    variables: Sequence[str],
    zones: List[Dict],
    newline: str = "\n",
) -> None:
    lines = [f'TITLE = "{title}"']
    lines.append("VARIABLES = " + " ".join(f'"{v}"' for v in variables))
    for zone in zones:
        lines.append(f'ZONE T="{zone["title"]}" I={len(zone["rows"])} F=POINT')
        for row in zone["rows"]:
            lines.append(" ".join(f"{v:.6e}" for v in row))
    content = newline.join(lines) + newline
    path.write_text(content, encoding="utf-8")


def write_gtree(path: Path, node_attrs: Dict[str, Dict[str, str]]) -> None:
    lines = []
    for node_id, attrs in node_attrs.items():
        for var, value in attrs.items():
            lines.append(f"set gtree({node_id},{var}) {value}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_cmd_file(path: Path, on_electrode_voltage: float) -> None:
    content = f"""Electrode {{
  {{ Name="gate" Voltage=0.0 }}
  {{ Name="drain" Voltage=0.0 }}
  {{ Name="source" Voltage=0.0 }}
  {{ Name="substrate" Voltage=0.0 }}
}}

Physics {{
  Mobility( DopingDep HighFieldSaturation Enormal )
  EffectiveIntrinsicDensity( OldSlotboom )
  Recombination( SRH(DopingDep) )
}}

Solve {{
  Poisson
  Coupled {{ Poisson Electron Hole }}
  Quasistationary (
    InitialStep=0.01 MaxStep=0.05 MinStep=1e-5
    Goal {{ Name="gate" Voltage={on_electrode_voltage} }}
  ) {{ Coupled {{ Poisson Electron Hole }} }}
}}
"""
    path.write_text(content, encoding="utf-8")


def generate(out_dir: Path, n_splits: int, repeats: int) -> None:
    plt_dir = out_dir / "plt"
    edge_dir = plt_dir / "edge_cases"
    tables_dir = out_dir / "tables"
    for d in (plt_dir, edge_dir, tables_dir):
        d.mkdir(parents=True, exist_ok=True)

    temps = [900, 950, 1000][:n_splits]

    node_attrs: Dict[str, Dict[str, str]] = {}
    summary_rows: List[str] = ["Lot,Split,Device,Vth,SS"]
    node_id = 1
    cmd_written = 0

    for polarity, base_vth in (("NMOS", 0.40), ("PMOS", -0.40)):
        vg = _vg_sweep(polarity)
        for temp in temps:
            temp_factor = (temp - 950) / 50.0
            vth_lin = base_vth - 0.02 * temp_factor if polarity == "NMOS" else base_vth + 0.02 * temp_factor
            ss_mv = 80 + 5 * temp_factor
            dibl_mv = 40 + 5 * temp_factor
            vth_sat = vth_lin - np.sign(vth_lin) * (dibl_mv / 1000.0) * (VD_SAT - VD_LIN)

            for rep in range(1, repeats + 1):
                split_label = f"{polarity}_T{temp}_R{rep}"
                vd_lin_signed = VD_LIN if polarity == "NMOS" else -VD_LIN
                vd_sat_signed = VD_SAT if polarity == "NMOS" else -VD_SAT

                # 1) 저Vd Id-Vg (Vth_CC/SS/Ion/Ioff/gm 추출용)
                lin_id = _add_noise(id_vg_curve(vg, vth_lin, ss_mv, polarity))
                lin_node = str(node_id)
                node_id += 1
                write_tecplot_file(
                    plt_dir / f"n{lin_node}_des.plt",
                    title=f"{split_label}_lin",
                    variables=["Gate Voltage (V)", "Drain Current (A)", "Drain Voltage (V)"],
                    zones=[
                        {
                            "title": split_label,
                            "rows": [(v, i, vd_lin_signed) for v, i in zip(vg, lin_id)],
                        }
                    ],
                )
                node_attrs[lin_node] = {"Temperature": str(temp), "Repeat": str(rep)}

                # 2) 고Vd Id-Vg (DIBL 계산용)
                sat_id = _add_noise(id_vg_curve(vg, vth_sat, ss_mv, polarity))
                sat_node = str(node_id)
                node_id += 1
                write_tecplot_file(
                    plt_dir / f"n{sat_node}_des.plt",
                    title=f"{split_label}_sat",
                    variables=["Gate Voltage (V)", "Drain Current (A)", "Drain Voltage (V)"],
                    zones=[
                        {
                            "title": split_label,
                            "rows": [(v, i, vd_sat_signed) for v, i in zip(vg, sat_id)],
                        }
                    ],
                )
                node_attrs[sat_node] = {"Temperature": str(temp), "Repeat": str(rep)}

                # 3) Id-Vd (Ron/gds 추출용, on-state 2개 Vg bias를 별도 ZONE으로)
                vd_mag = np.linspace(0.0, 1.2, 25)
                overdrive_targets = [0.4, 0.8]
                zones = []
                for ov in overdrive_targets:
                    vg_bias = vth_lin + _sign(polarity) * ov
                    id_vals = _add_noise(id_vd_curve(vd_mag, vg_bias, vth_lin, polarity), rel=0.01)
                    vd_signed = vd_mag if polarity == "NMOS" else -vd_mag
                    vg_bias_col = np.full_like(vd_mag, vg_bias)
                    zones.append(
                        {
                            "title": f"{split_label}_Vg={vg_bias:.2f}",
                            "rows": list(zip(vg_bias_col, id_vals, vd_signed)),
                        }
                    )
                idvd_node = str(node_id)
                node_id += 1
                write_tecplot_file(
                    plt_dir / f"n{idvd_node}_des.plt",
                    title=f"{split_label}_idvd",
                    variables=["Gate Voltage (V)", "Drain Current (A)", "Drain Voltage (V)"],
                    zones=zones,
                )
                node_attrs[idvd_node] = {"Temperature": str(temp), "Repeat": str(rep)}

                summary_rows.append(f"LOT1,{split_label},{polarity},{vth_lin:.4f},{ss_mv:.2f}")

                if cmd_written < 2:
                    on_v = 1.2 if polarity == "NMOS" else -1.2
                    write_cmd_file(plt_dir / f"n{lin_node}_des.cmd", on_v)
                    cmd_written += 1

    write_gtree(plt_dir / "gtree.dat", node_attrs)
    (tables_dir / "summary.csv").write_text("\n".join(summary_rows) + "\n", encoding="utf-8")

    _write_edge_cases(edge_dir)

    print(f"생성 완료: {plt_dir} 에 {node_id - 1}개 노드(.plt), gtree.dat, cmd 파일 {cmd_written}개")
    print(f"요약 테이블: {tables_dir / 'summary.csv'}")
    print(f"edge-case 파일: {edge_dir}")


def _write_edge_cases(edge_dir: Path) -> None:
    # 1) 컬럼 수 불일치 (파서가 라인 번호와 함께 에러를 내야 함)
    (edge_dir / "malformed_column_mismatch.plt").write_text(
        'TITLE = "bad"\n'
        'VARIABLES = "Gate Voltage (V)" "Drain Current (A)" "Drain Voltage (V)"\n'
        'ZONE T="bad" I=3 F=POINT\n'
        "0.0 1.0e-12 0.05\n"
        "0.1 2.0e-12\n"  # 컬럼 하나 누락
        "0.2 3.0e-12 0.05\n",
        encoding="utf-8",
    )

    # 2) VARIABLES가 여러 줄에 걸침
    (edge_dir / "multiline_variables.plt").write_text(
        'TITLE = "multiline"\n'
        "VARIABLES = \n"
        '"Gate Voltage (V)"\n'
        '"Drain Current (A)"\n'
        '"Drain Voltage (V)"\n'
        'ZONE T="ml" I=2 F=POINT\n'
        "0.0 1.0e-12 0.05\n"
        "0.1 2.0e-12 0.05\n",
        encoding="utf-8",
    )

    # 3) 여러 ZONE
    (edge_dir / "multi_zone.plt").write_text(
        'TITLE = "multizone"\n'
        'VARIABLES = "Gate Voltage (V)" "Drain Current (A)" "Drain Voltage (V)"\n'
        'ZONE T="zoneA" I=2 F=POINT\n'
        "0.0 1.0e-12 0.05\n"
        "0.1 2.0e-12 0.05\n"
        'ZONE T="zoneB" I=2 F=POINT\n'
        "0.0 3.0e-12 0.05\n"
        "0.1 4.0e-12 0.05\n",
        encoding="utf-8",
    )

    # 4) Windows CRLF 줄바꿈
    write_tecplot_file(
        edge_dir / "crlf_lineendings.plt",
        title="crlf",
        variables=["Gate Voltage (V)", "Drain Current (A)", "Drain Voltage (V)"],
        zones=[{"title": "crlf", "rows": [(0.0, 1.0e-12, 0.05), (0.1, 2.0e-12, 0.05)]}],
        newline="\r\n",
    )

    # 5) I= 선언값과 실제 라인 수가 다른 경우 (경고 후 실제 라인 수 사용)
    (edge_dir / "mismatched_i_count.plt").write_text(
        'TITLE = "mismatch"\n'
        'VARIABLES = "Gate Voltage (V)" "Drain Current (A)" "Drain Voltage (V)"\n'
        'ZONE T="mismatch" I=5 F=POINT\n'
        "0.0 1.0e-12 0.05\n"
        "0.1 2.0e-12 0.05\n"
        "0.2 3.0e-12 0.05\n",
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default="sample_data")
    parser.add_argument("--n-splits", type=int, default=3, help="온도 split 개수(최대 3)")
    parser.add_argument("--repeats", type=int, default=1, help="split당 반복 횟수")
    args = parser.parse_args()

    generate(Path(args.out), args.n_splits, args.repeats)


if __name__ == "__main__":
    main()

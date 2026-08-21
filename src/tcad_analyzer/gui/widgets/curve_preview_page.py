"""4) Curve Preview 페이지: curve 시각화 + 추출 지점 오버레이 + 시뮬레이션 조건 요약.

목록에서 하나만 고르면 Vth/SS/Ion/Ioff 등 추출 지점을 자세히 오버레이해서 보여주고,
Ctrl(또는 Shift)로 여러 개를 동시에 고르면 원본 곡선끼리 겹쳐 그려 모양을 비교할 수 있다
(이 경우 세부 추출 마커는 화면이 복잡해지므로 생략).
"""

from __future__ import annotations

import numpy as np
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPlainTextEdit,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtCore import Qt

from ...models import Curve, CurveType
from ..controllers.project_controller import ProjectController
from ..mpl_canvas import MplCanvas


class CurvePreviewPage(QWidget):
    def __init__(self, controller: ProjectController, parent=None):
        super().__init__(parent)
        self.controller = controller

        layout = QHBoxLayout(self)

        left = QVBoxLayout()
        left_widget = QWidget()
        left_widget.setLayout(left)
        left_widget.setMaximumWidth(300)
        left.addWidget(QLabel("Curve 목록 (Ctrl/Shift+클릭으로 여러 개 선택 시 겹쳐보기)"))
        self.curve_list = QListWidget()
        self.curve_list.setSelectionMode(QAbstractItemView.ExtendedSelection)
        left.addWidget(self.curve_list)
        self.log_check = QCheckBox("로그 축 (|Id|)")
        self.log_check.setChecked(True)
        left.addWidget(self.log_check)
        left.addWidget(QLabel("시뮬레이션 조건 요약 (.cmd, 있는 경우만 / 1개 선택 시만 표시)"))
        self.cmd_text = QPlainTextEdit()
        self.cmd_text.setReadOnly(True)
        self.cmd_text.setMaximumHeight(160)
        left.addWidget(self.cmd_text)
        layout.addWidget(left_widget)

        self.canvas = MplCanvas(figsize=(7, 5))
        layout.addWidget(self.canvas, 1)

        self.curve_list.itemSelectionChanged.connect(self._on_selection_changed)
        self.log_check.stateChanged.connect(self._replot)
        self.controller.curvesBuilt.connect(self._refresh_list)
        self.controller.extractionCompleted.connect(self._replot)

    def _refresh_list(self) -> None:
        self.curve_list.clear()
        for curve in self.controller.curves:
            label = f"{curve.curve_id} [{curve.device.device_id}] {curve.split.label()}"
            item = QListWidgetItem(label)
            item.setData(Qt.UserRole, curve.curve_id)
            self.curve_list.addItem(item)
        if self.curve_list.count() > 0:
            self.curve_list.setCurrentRow(0)

    def _selected_curves(self) -> list[Curve]:
        curve_ids = {item.data(Qt.UserRole) for item in self.curve_list.selectedItems()}
        return [c for c in self.controller.curves if c.curve_id in curve_ids]

    def _on_selection_changed(self) -> None:
        self._replot()
        self._update_cmd_summary()

    def _update_cmd_summary(self) -> None:
        curves = self._selected_curves()
        if len(curves) != 1:
            self.cmd_text.setPlainText("" if not curves else "(여러 curve 선택됨 — 1개만 선택하면 표시)")
            return
        summary = self.controller.cmd_summary_for_curve(curves[0])
        if summary is None or summary.is_empty():
            self.cmd_text.setPlainText("(참고 정보 없음)")
            return
        lines = []
        if summary.electrodes:
            lines.append("Electrodes: " + ", ".join(summary.electrodes))
        if summary.voltage_sweeps:
            lines.append("Voltage sweep: " + ", ".join(summary.voltage_sweeps))
        if summary.physics_models:
            lines.append("Physics: " + ", ".join(summary.physics_models))
        if summary.partially_recognized:
            lines.append("(일부 정보를 인식하지 못했습니다)")
        self.cmd_text.setPlainText("\n".join(lines))

    def _params_for_curve(self, curve_id: str):
        return [p for p in self.controller.extracted_params if p.curve_id == curve_id]

    def _replot(self) -> None:
        curves = self._selected_curves()
        self.canvas.figure.clear()
        if not curves:
            self.canvas.draw()
            return

        ax = self.canvas.figure.add_subplot(111)
        if len(curves) == 1:
            curve = curves[0]
            params = self._params_for_curve(curve.curve_id)
            by_name = {p.param_name: p for p in params}
            if curve.curve_type == CurveType.ID_VG:
                self._plot_id_vg(ax, curve, by_name)
            else:
                self._plot_id_vd(ax, curve, by_name)
        else:
            self._plot_overlay(ax, curves)

        ax.legend(fontsize=8, loc="best")
        self.canvas.figure.tight_layout()
        self.canvas.draw()

    def _curve_label(self, curve: Curve) -> str:
        return f"{curve.device.device_id} {curve.split.label()}"

    def _plot_overlay(self, ax, curves: list[Curve]) -> None:
        vg_curves = [c for c in curves if c.curve_type == CurveType.ID_VG]
        vd_curves = [c for c in curves if c.curve_type == CurveType.ID_VD]

        if vg_curves and vd_curves:
            ax.text(
                0.5,
                0.5,
                "Id-Vg와 Id-Vd curve를 동시에 겹쳐 그릴 수 없습니다.\n같은 종류끼리만 선택하세요.",
                ha="center",
                va="center",
                transform=ax.transAxes,
                wrap=True,
            )
            return

        if vg_curves:
            log_scale = self.log_check.isChecked()
            for curve in vg_curves:
                abs_id = np.abs(curve.id_)
                y = np.where(abs_id > 0, abs_id, np.nan) if log_scale else abs_id
                ax.plot(curve.vg, y, lw=1.3, label=self._curve_label(curve))
            if log_scale:
                ax.set_yscale("log")
            ax.set_xlabel("Vg (V)")
            ax.set_ylabel("|Id| (A)")
            ax.set_title(f"Id-Vg 비교 ({len(vg_curves)}개)")
        else:
            for curve in vd_curves:
                ax.plot(curve.vd_array, curve.id_, lw=1.3, label=self._curve_label(curve))
            ax.set_xlabel("Vd (V)")
            ax.set_ylabel("Id (A)")
            ax.set_title(f"Id-Vd 비교 ({len(vd_curves)}개)")

    def _plot_id_vg(self, ax, curve, by_name) -> None:
        vg = curve.vg
        abs_id = np.abs(curve.id_)
        if self.log_check.isChecked():
            plot_id = np.where(abs_id > 0, abs_id, np.nan)
            ax.set_yscale("log")
        else:
            plot_id = abs_id
        ax.plot(vg, plot_id, "o-", ms=3, lw=1, label="|Id|")
        ax.set_xlabel("Vg (V)")
        ax.set_ylabel("|Id| (A)")
        ax.set_title(f"Id-Vg: {curve.curve_id}")

        vth_param = by_name.get("Vth_CC") or by_name.get("Vth_SD")
        if vth_param is not None:
            ax.axvline(vth_param.value, color="red", ls="--", lw=1, label=f"{vth_param.param_name}={vth_param.value:.3f}V")

        ss_param = by_name.get("SS")
        if ss_param is not None and "vg_range" in ss_param.method_params:
            lo, hi = ss_param.method_params["vg_range"]
            ax.axvspan(lo, hi, color="orange", alpha=0.2, label=f"SS fit ({ss_param.value:.1f}mV/dec)")

        for name, marker in (("Ion", "^"), ("Ioff", "v")):
            p = by_name.get(name)
            if p is not None:
                ax.scatter([], [], marker=marker, color="green", label=f"{name}={p.value:.2e}A")

    def _plot_id_vd(self, ax, curve, by_name) -> None:
        vd = curve.vd_array
        ax.plot(vd, curve.id_, "o-", ms=3, lw=1, label="Id")
        ax.set_xlabel("Vd (V)")
        ax.set_ylabel("Id (A)")
        ax.set_title(f"Id-Vd: {curve.curve_id}")

        ron_param = by_name.get("Ron")
        if ron_param is not None:
            ax.text(0.02, 0.95, f"Ron={ron_param.value:.2e} ohm", transform=ax.transAxes, va="top")
        gds_param = by_name.get("gds")
        if gds_param is not None:
            ax.text(0.02, 0.88, f"gds={gds_param.value:.2e} S", transform=ax.transAxes, va="top")

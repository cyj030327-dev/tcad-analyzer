"""5) Comparison 페이지: split별 비교(박스플롯/바차트/산점도) + '최적 소자 추천'."""

from __future__ import annotations

from typing import List, Optional

import numpy as np
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtCore import Qt

from ...analysis import (
    DEFAULT_METRIC_DIRECTIONS,
    MetricDirection,
    OptimizationProfile,
    build_sensitivity_table,
    compute_correlation,
    compute_sensitivity_summary,
    describe_relationship,
    filter_by_ranges,
    numeric_attribute_names,
    recommend_optimal,
    summarize_by_split,
    to_dataframe,
)
from ..controllers.project_controller import ProjectController
from ..mpl_canvas import MplCanvas


class ComparisonPage(QWidget):
    def __init__(self, controller: ProjectController, parent=None):
        super().__init__(parent)
        self.controller = controller

        layout = QVBoxLayout(self)

        top = QHBoxLayout()
        top.addWidget(QLabel("Device:"))
        self.device_combo = QComboBox()
        top.addWidget(self.device_combo)
        self.btn_refresh_comparison = QPushButton("새로고침")
        self.btn_refresh_comparison.clicked.connect(self._refresh_all)
        top.addWidget(self.btn_refresh_comparison)
        top.addStretch(1)
        layout.addLayout(top)

        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)

        self.tabs.addTab(self._build_distribution_tab(), "박스플롯/바차트")
        self.tabs.addTab(self._build_correlation_tab(), "상관관계")
        self.tabs.addTab(self._build_sensitivity_tab(), "민감도 분석")
        self.tabs.addTab(self._build_recommend_tab(), "최적 소자 추천")
        self.tabs.addTab(self._build_filter_tab(), "조건 필터")

        self.controller.extractionCompleted.connect(self._refresh_all)
        self.controller.curvesBuilt.connect(self._refresh_all)

    # ---------------------------------------------------------------- data
    def _params_df(self):
        df = to_dataframe(self.controller.all_params)
        device = self.device_combo.currentText()
        if device and device != "전체" and not df.empty:
            df = df[df["device_id"] == device]
        return df

    def _filtered_params(self) -> List:
        """device 필터가 적용된 원본 ExtractedParameter 리스트(DataFrame이 아닌 형태가
        필요한 sensitivity 분석 등에서 사용)."""
        device = self.device_combo.currentText()
        params = self.controller.all_params
        if device and device != "전체":
            params = [p for p in params if p.device.device_id == device]
        return params

    def _param_names(self) -> List[str]:
        df = to_dataframe(self.controller.all_params)
        if df.empty:
            return []
        return sorted(df["param_name"].unique().tolist())

    def _device_names(self) -> List[str]:
        df = to_dataframe(self.controller.all_params)
        if df.empty:
            return []
        return sorted(df["device_id"].unique().tolist())

    def _refresh_all(self) -> None:
        current_device = self.device_combo.currentText()
        self.device_combo.blockSignals(True)
        self.device_combo.clear()
        self.device_combo.addItem("전체")
        self.device_combo.addItems(self._device_names())
        idx = self.device_combo.findText(current_device)
        self.device_combo.setCurrentIndex(idx if idx >= 0 else 0)
        self.device_combo.blockSignals(False)

        names = self._param_names()
        for combo in (self.dist_param_combo, self.corr_x_combo, self.corr_y_combo, self.sens_metric_combo):
            current = combo.currentText()
            combo.blockSignals(True)
            combo.clear()
            combo.addItems(names)
            idx = combo.findText(current)
            combo.setCurrentIndex(idx if idx >= 0 else 0)
            combo.blockSignals(False)

        self.metric_list.clear()
        for name in names:
            item = QListWidgetItem(name)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Unchecked)
            self.metric_list.addItem(item)

        self._refresh_dist_split_list()
        self._refresh_filter_criteria_combos()
        self._replot_distribution()
        self._replot_correlation()
        self._replot_sensitivity()
        self._refresh_sensitivity_summary()

    # --------------------------------------------------------- distribution
    def _build_distribution_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)

        row = QHBoxLayout()
        row.addWidget(QLabel("파라미터:"))
        self.dist_param_combo = QComboBox()
        row.addWidget(self.dist_param_combo)
        row.addWidget(QLabel("차트:"))
        self.dist_kind_combo = QComboBox()
        self.dist_kind_combo.addItems(["박스플롯", "바차트(평균±표준편차)"])
        row.addWidget(self.dist_kind_combo)
        row.addStretch(1)
        layout.addLayout(row)

        layout.addWidget(QLabel("비교할 split 선택 (기본: 전체):"))
        split_row = QHBoxLayout()
        self.dist_split_list = QListWidget()
        self.dist_split_list.setMinimumHeight(220)
        self.dist_split_list.setMaximumHeight(320)
        split_row.addWidget(self.dist_split_list)
        split_btn_col = QVBoxLayout()
        self.btn_dist_select_all = QPushButton("전체 선택")
        self.btn_dist_select_none = QPushButton("전체 해제")
        split_btn_col.addWidget(self.btn_dist_select_all)
        split_btn_col.addWidget(self.btn_dist_select_none)
        split_btn_col.addStretch(1)
        split_row.addLayout(split_btn_col)
        layout.addLayout(split_row)

        self.dist_status_label = QLabel("")
        layout.addWidget(self.dist_status_label)

        self.dist_canvas = MplCanvas(figsize=(7, 4))
        self.dist_canvas.canvas.mpl_connect("motion_notify_event", self._on_dist_hover)
        self.dist_canvas.setMinimumHeight(380)
        layout.addWidget(self.dist_canvas)

        self.dist_table = QTableWidget(0, 5)
        self.dist_table.setHorizontalHeaderLabels(["split", "mean", "std", "min", "max"])
        self.dist_table.setMinimumHeight(150)
        layout.addWidget(self.dist_table)

        self._dist_bars: list = []
        self._dist_ax = None
        self._dist_annotation = None

        self.dist_param_combo.currentIndexChanged.connect(self._replot_distribution)
        self.dist_kind_combo.currentIndexChanged.connect(self._replot_distribution)
        self.dist_split_list.itemChanged.connect(self._replot_distribution)
        self.btn_dist_select_all.clicked.connect(lambda: self._check_all_dist_splits(True))
        self.btn_dist_select_none.clicked.connect(lambda: self._check_all_dist_splits(False))

        # 탭 안 내용(파라미터/차트 선택 + split 체크리스트 + 캔버스 + 표)이 넓은 split 목록
        # 때문에 한 화면에 다 안 들어갈 수 있어, 각 구성요소는 원래 크기를 유지하고
        # 탭 전체를 스크롤 가능하게 감싼다(캔버스/표가 억지로 눌려 찌그러지는 것을 방지).
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(w)
        return scroll

    def _selected_dist_splits(self) -> List[str]:
        return [
            self.dist_split_list.item(i).text()
            for i in range(self.dist_split_list.count())
            if self.dist_split_list.item(i).checkState() == Qt.Checked
        ]

    def _check_all_dist_splits(self, checked: bool) -> None:
        state = Qt.Checked if checked else Qt.Unchecked
        self.dist_split_list.blockSignals(True)
        for i in range(self.dist_split_list.count()):
            self.dist_split_list.item(i).setCheckState(state)
        self.dist_split_list.blockSignals(False)
        self._replot_distribution()

    def _refresh_dist_split_list(self) -> None:
        """device 필터가 적용된 상태에서 나오는 모든 split을 목록에 채운다.
        이미 있던 항목의 체크 상태는 보존하고, 새로 생긴 항목은 기본 체크(=전체 비교 유지)."""
        df = self._params_df()
        labels = sorted(df["split_label"].unique().tolist()) if not df.empty else []
        previous = {
            self.dist_split_list.item(i).text(): self.dist_split_list.item(i).checkState()
            for i in range(self.dist_split_list.count())
        }
        self.dist_split_list.blockSignals(True)
        self.dist_split_list.clear()
        for label in labels:
            item = QListWidgetItem(label)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(previous.get(label, Qt.Checked))
            self.dist_split_list.addItem(item)
        self.dist_split_list.blockSignals(False)

    def _replot_distribution(self) -> None:
        param = self.dist_param_combo.currentText()
        df = self._params_df()
        self.dist_canvas.figure.clear()
        self._dist_bars = []
        self._dist_ax = None
        self._dist_annotation = None
        if not param or df.empty:
            self.dist_status_label.setText("데이터가 없습니다.")
            self.dist_canvas.draw()
            self.dist_table.setRowCount(0)
            return

        selected_splits = set(self._selected_dist_splits())
        if not selected_splits:
            self.dist_status_label.setText("비교할 split을 하나 이상 선택하세요.")
            self.dist_canvas.draw()
            self.dist_table.setRowCount(0)
            return

        subset = df[(df["param_name"] == param) & (df["split_label"].isin(selected_splits))]
        if subset.empty:
            self.dist_status_label.setText("선택한 split에 해당하는 데이터가 없습니다.")
            self.dist_canvas.draw()
            self.dist_table.setRowCount(0)
            return

        self.dist_status_label.setText("")
        ax = self.dist_canvas.figure.add_subplot(111)
        groups = subset.groupby("split_label")["value"]
        labels = list(groups.groups.keys())

        if self.dist_kind_combo.currentIndex() == 0:
            ax.boxplot([groups.get_group(l).values for l in labels], tick_labels=labels)
        else:
            means = [groups.get_group(l).mean() for l in labels]
            stds = [groups.get_group(l).std() for l in labels]
            bars = ax.bar(range(len(labels)), means, yerr=stds, capsize=4)
            ax.set_xticks(range(len(labels)))
            ax.set_xticklabels(labels)

            self._dist_annotation = ax.annotate(
                "",
                xy=(0, 0),
                xytext=(0, 12),
                textcoords="offset points",
                ha="center",
                bbox=dict(boxstyle="round", fc="lightyellow", ec="gray"),
                visible=False,
            )
            self._dist_ax = ax
            self._dist_bars = list(zip(bars.patches, labels, means))

        ax.set_ylabel(param)
        self.dist_canvas.figure.autofmt_xdate(rotation=30)
        self.dist_canvas.figure.tight_layout()
        self.dist_canvas.draw()

        summary = summarize_by_split(self.controller.all_params, param)
        summary = summary[summary["split_label"].isin(labels)]
        self.dist_table.setRowCount(len(summary))
        for i, row in enumerate(summary.itertuples(index=False)):
            for j, val in enumerate(row):
                self.dist_table.setItem(i, j, QTableWidgetItem(str(val)))

    def _on_dist_hover(self, event) -> None:
        ann = self._dist_annotation
        if ann is None or self._dist_ax is None or event.inaxes != self._dist_ax:
            if ann is not None and ann.get_visible():
                ann.set_visible(False)
                self.dist_canvas.canvas.draw_idle()
            return
        for patch, label, value in self._dist_bars:
            contains, _ = patch.contains(event)
            if contains:
                ann.xy = (patch.get_x() + patch.get_width() / 2, patch.get_height())
                ann.set_text(f"{label}\n{value:.4g}")
                ann.set_visible(True)
                self.dist_canvas.canvas.draw_idle()
                return
        if ann.get_visible():
            ann.set_visible(False)
            self.dist_canvas.canvas.draw_idle()

    # ---------------------------------------------------------- correlation
    def _build_correlation_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        row = QHBoxLayout()
        row.addWidget(QLabel("X:"))
        self.corr_x_combo = QComboBox()
        row.addWidget(self.corr_x_combo)
        row.addWidget(QLabel("Y:"))
        self.corr_y_combo = QComboBox()
        row.addWidget(self.corr_y_combo)
        row.addStretch(1)
        layout.addLayout(row)

        self.corr_canvas = MplCanvas(figsize=(6, 5))
        layout.addWidget(self.corr_canvas)
        self.corr_r_label = QLabel("")
        layout.addWidget(self.corr_r_label)

        self.corr_x_combo.currentIndexChanged.connect(self._replot_correlation)
        self.corr_y_combo.currentIndexChanged.connect(self._replot_correlation)
        return w

    def _replot_correlation(self) -> None:
        x, y = self.corr_x_combo.currentText(), self.corr_y_combo.currentText()
        self.corr_canvas.figure.clear()
        if not x or not y:
            self.corr_canvas.draw()
            return

        device = self.device_combo.currentText()
        params = self.controller.all_params
        if device and device != "전체":
            params = [p for p in params if p.device.device_id == device]
        merged = compute_correlation(params, x, y)

        ax = self.corr_canvas.figure.add_subplot(111)
        if not merged.empty:
            ax.scatter(merged[x], merged[y])
        ax.set_xlabel(x)
        ax.set_ylabel(y)
        self.corr_canvas.figure.tight_layout()
        self.corr_canvas.draw()

        r = merged.attrs.get("pearson_r")
        self.corr_r_label.setText(f"Pearson r = {r:.3f} (n={len(merged)})" if r is not None else f"n={len(merged)}")

    # ---------------------------------------------------------- sensitivity
    def _build_sensitivity_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.addWidget(
            QLabel(
                "지표를 하나 고르면, gtree.dat에서 읽은 공정변수(숫자로 해석되는 것) 전부를 한 번에 "
                "나란히 보여줍니다 — 점이 오른쪽 위로 갈수록(빨간 추세선이 우상향) '그 변수가 커질수록 "
                "지표도 커진다'는 뜻이에요. split 하나에 curve가 여러 개면 지표는 평균값을 씁니다."
            )
        )

        row = QHBoxLayout()
        row.addWidget(QLabel("지표:"))
        self.sens_metric_combo = QComboBox()
        row.addWidget(self.sens_metric_combo)
        row.addStretch(1)
        layout.addLayout(row)

        self.sens_canvas = MplCanvas(figsize=(9, 3.5))
        layout.addWidget(self.sens_canvas)

        self.sens_caption_label = QLabel("")
        self.sens_caption_label.setWordWrap(True)
        layout.addWidget(self.sens_caption_label)

        layout.addWidget(
            QLabel("지표별로 묶어서, 그 지표에 영향이 큰 공정변수 순으로 정리한 전체 요약:")
        )
        self.sens_summary_table = QTableWidget(0, 5)
        self.sens_summary_table.setHorizontalHeaderLabels(["지표", "공정변수", "r", "n", "설명"])
        self.sens_summary_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.Stretch)
        layout.addWidget(self.sens_summary_table)

        self.sens_metric_combo.currentIndexChanged.connect(self._replot_sensitivity)
        return w

    def _replot_sensitivity(self) -> None:
        metric = self.sens_metric_combo.currentText()
        self.sens_canvas.figure.clear()
        params = self._filtered_params()
        attr_names = numeric_attribute_names(params)

        if not metric or not attr_names:
            self.sens_canvas.draw()
            self.sens_caption_label.setText("")
            return

        table = build_sensitivity_table(params, [metric])
        if table.empty or metric not in table.columns:
            self.sens_canvas.draw()
            self.sens_caption_label.setText("데이터가 부족합니다.")
            return

        captions = []
        for i, attr in enumerate(attr_names):
            ax = self.sens_canvas.figure.add_subplot(1, len(attr_names), i + 1)
            if attr not in table.columns:
                ax.set_title(attr)
                captions.append(f"• {attr}: 데이터가 없습니다.")
                continue

            sub = table[[attr, metric]].dropna()
            r: Optional[float] = None
            if not sub.empty:
                ax.scatter(sub[attr], sub[metric])
                if len(sub) >= 3 and sub[attr].nunique() >= 2 and sub[metric].nunique() >= 2:
                    r = float(np.corrcoef(sub[attr], sub[metric])[0, 1])
                    # 추세선(1차 직선 피팅) — 방향을 숫자(r)보다 눈으로 바로 보이게
                    slope, intercept = np.polyfit(sub[attr], sub[metric], 1)
                    x_line = np.array([sub[attr].min(), sub[attr].max()])
                    ax.plot(x_line, slope * x_line + intercept, color="red", linewidth=1.5)
            ax.set_xlabel(attr)
            if i == 0:
                ax.set_ylabel(metric)
            captions.append(f"• {describe_relationship(attr, metric, r)}")

        self.sens_canvas.figure.tight_layout()
        self.sens_canvas.draw()
        self.sens_caption_label.setText("\n".join(captions))

    def _refresh_sensitivity_summary(self) -> None:
        summary = compute_sensitivity_summary(self._filtered_params(), self._param_names())
        self.sens_summary_table.setRowCount(len(summary))
        for i, row in enumerate(summary.itertuples(index=False)):
            for j, val in enumerate(row):
                text = f"{val:.4g}" if isinstance(val, float) else str(val)
                self.sens_summary_table.setItem(i, j, QTableWidgetItem(text))

    # ----------------------------------------------------------- recommend
    def _build_recommend_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)

        layout.addWidget(QLabel("비교/추천에 사용할 지표를 선택하세요:"))
        self.metric_list = QListWidget()
        self.metric_list.setMaximumHeight(120)
        layout.addWidget(self.metric_list)

        form = QFormLayout()
        self.profile_combo = QComboBox()
        self.profile_combo.addItems(["저전력", "고성능", "밸런스", "사용자 지정"])
        form.addRow("최적화 프로파일", self.profile_combo)
        self.custom_weight_edit = QPlainTextEdit()
        self.custom_weight_edit.setPlaceholderText("사용자 지정일 때만 사용, 한 줄에 하나: 지표명=가중치\n예) Ioff=0.5\nSS=0.5")
        self.custom_weight_edit.setMaximumHeight(70)
        form.addRow("사용자 지정 가중치", self.custom_weight_edit)
        self.target_edit = QPlainTextEdit()
        self.target_edit.setPlaceholderText("선택: 목표값. 한 줄에 하나: 지표명=목표값\n예) Vth_CC=0.4")
        self.target_edit.setMaximumHeight(70)
        form.addRow("목표값 (선택)", self.target_edit)
        layout.addLayout(form)

        self.btn_recommend = QPushButton("추천 계산")
        layout.addWidget(self.btn_recommend)

        self.recommend_summary_label = QLabel("")
        self.recommend_summary_label.setWordWrap(True)
        layout.addWidget(self.recommend_summary_label)

        self.recommend_table = QTableWidget(0, 0)
        layout.addWidget(self.recommend_table)

        self.btn_recommend.clicked.connect(self._on_recommend)
        return w

    def _selected_metrics(self) -> List[str]:
        return [
            self.metric_list.item(i).text()
            for i in range(self.metric_list.count())
            if self.metric_list.item(i).checkState() == Qt.Checked
        ]

    def _on_recommend(self) -> None:
        metrics = self._selected_metrics()
        if not metrics:
            self.recommend_summary_label.setText("지표를 하나 이상 선택하세요.")
            return

        device = self.device_combo.currentText()
        params = self.controller.all_params
        if device and device != "전체":
            params = [p for p in params if p.device.device_id == device]

        directions = {m: DEFAULT_METRIC_DIRECTIONS.get(m, MetricDirection.HIGHER_BETTER) for m in metrics}
        profile_map = {
            0: OptimizationProfile.LOW_POWER,
            1: OptimizationProfile.HIGH_PERFORMANCE,
            2: OptimizationProfile.BALANCED,
            3: OptimizationProfile.CUSTOM,
        }
        profile = profile_map[self.profile_combo.currentIndex()]
        custom_weights = _parse_kv_float(self.custom_weight_edit.toPlainText()) if profile == OptimizationProfile.CUSTOM else None
        targets = _parse_kv_float(self.target_edit.toPlainText())

        result = recommend_optimal(
            params,
            metric_names=metrics,
            directions=directions,
            profile=profile,
            custom_weights=custom_weights,
            targets=targets or None,
        )

        if result.top_recommendation is None:
            self.recommend_summary_label.setText("추천할 split이 없습니다(데이터가 부족합니다).")
            self.recommend_table.setRowCount(0)
            return

        weight_items = sorted(result.weights_used.items(), key=lambda kv: kv[1], reverse=True)
        weight_txt = ", ".join(f"{name} {w * 100:.0f}%" for name, w in weight_items if w > 0)

        self.recommend_summary_label.setText(
            f"Pareto 후보군: {', '.join(result.pareto_candidates)}\n"
            f"추천 split: {result.top_recommendation}\n"
            f"사용된 가중치({self.profile_combo.currentText()}): {weight_txt or '(없음)'}"
        )

        table = result.scored_table.reset_index().rename(columns={"index": "split_label"})
        self.recommend_table.setColumnCount(len(table.columns))
        self.recommend_table.setHorizontalHeaderLabels([str(c) for c in table.columns])
        self.recommend_table.setRowCount(len(table))
        for i, row in enumerate(table.itertuples(index=False)):
            for j, val in enumerate(row):
                text = f"{val:.4g}" if isinstance(val, float) else str(val)
                self.recommend_table.setItem(i, j, QTableWidgetItem(text))

    # -------------------------------------------------------------- filter
    def _build_filter_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)

        layout.addWidget(
            QLabel(
                "지표를 고르고 최소/최대 범위를 입력하세요. 조건을 여러 개 추가하면 전부 만족하는 "
                "split만 걸러서 보여줍니다."
            )
        )

        self.filter_criteria_table = QTableWidget(0, 4)
        self.filter_criteria_table.setHorizontalHeaderLabels(["지표", "관측된 범위(참고)", "최소", "최대"])
        self.filter_criteria_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.filter_criteria_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.filter_criteria_table.setMaximumHeight(140)
        layout.addWidget(self.filter_criteria_table)

        row_btns = QHBoxLayout()
        self.btn_add_criterion = QPushButton("조건 추가")
        self.btn_remove_criterion = QPushButton("선택 조건 삭제")
        row_btns.addWidget(self.btn_add_criterion)
        row_btns.addWidget(self.btn_remove_criterion)
        row_btns.addStretch(1)
        layout.addLayout(row_btns)

        self.btn_filter = QPushButton("필터 적용")
        layout.addWidget(self.btn_filter)

        self.filter_summary_label = QLabel("")
        self.filter_summary_label.setWordWrap(True)
        layout.addWidget(self.filter_summary_label)

        self.filter_table = QTableWidget(0, 0)
        layout.addWidget(self.filter_table)

        self.btn_add_criterion.clicked.connect(self._add_filter_criterion_row)
        self.btn_remove_criterion.clicked.connect(self._remove_filter_criterion_row)
        self.btn_filter.clicked.connect(self._on_filter)
        return w

    def _add_filter_criterion_row(self) -> None:
        row = self.filter_criteria_table.rowCount()
        self.filter_criteria_table.insertRow(row)
        combo = QComboBox()
        combo.addItems(self._param_names())
        combo.currentIndexChanged.connect(self._on_filter_criterion_metric_changed)
        self.filter_criteria_table.setCellWidget(row, 0, combo)

        range_item = QTableWidgetItem("")
        range_item.setFlags(range_item.flags() & ~Qt.ItemIsEditable)
        self.filter_criteria_table.setItem(row, 1, range_item)
        self.filter_criteria_table.setItem(row, 2, QTableWidgetItem(""))
        self.filter_criteria_table.setItem(row, 3, QTableWidgetItem(""))

        self._update_observed_range(row)

    def _remove_filter_criterion_row(self) -> None:
        row = self.filter_criteria_table.currentRow()
        if row >= 0:
            self.filter_criteria_table.removeRow(row)

    def _on_filter_criterion_metric_changed(self) -> None:
        combo = self.sender()
        for row in range(self.filter_criteria_table.rowCount()):
            if self.filter_criteria_table.cellWidget(row, 0) is combo:
                self._update_observed_range(row)
                break

    def _observed_range(self, param_name: str):
        """현재 device 필터가 적용된 상태에서, 그 지표의 실제 관측 최소/최대값(모든 split 통틀어)."""
        df = self._params_df()
        subset = df[df["param_name"] == param_name] if not df.empty else df
        if subset.empty:
            return None
        return float(subset["value"].min()), float(subset["value"].max())

    def _update_observed_range(self, row: int) -> None:
        combo = self.filter_criteria_table.cellWidget(row, 0)
        item = self.filter_criteria_table.item(row, 1)
        if combo is None or item is None:
            return
        rng = self._observed_range(combo.currentText()) if combo.currentText() else None
        item.setText(f"{rng[0]:.4g} ~ {rng[1]:.4g}" if rng else "(데이터 없음)")

    def _refresh_filter_criteria_combos(self) -> None:
        """데이터가 새로 로드되면 이미 추가된 조건 행들의 지표 목록/관측범위도 최신화(선택값 유지)."""
        names = self._param_names()
        for row in range(self.filter_criteria_table.rowCount()):
            combo = self.filter_criteria_table.cellWidget(row, 0)
            if combo is None:
                continue
            current = combo.currentText()
            combo.blockSignals(True)
            combo.clear()
            combo.addItems(names)
            idx = combo.findText(current)
            if idx >= 0:
                combo.setCurrentIndex(idx)
            combo.blockSignals(False)
            self._update_observed_range(row)

    def _on_filter(self) -> None:
        criteria = {}
        for row in range(self.filter_criteria_table.rowCount()):
            combo = self.filter_criteria_table.cellWidget(row, 0)
            if combo is None or not combo.currentText():
                continue
            lo_item = self.filter_criteria_table.item(row, 2)
            hi_item = self.filter_criteria_table.item(row, 3)
            lo_text = lo_item.text().strip() if lo_item else ""
            hi_text = hi_item.text().strip() if hi_item else ""
            if not lo_text or not hi_text:
                continue
            try:
                lo, hi = float(lo_text), float(hi_text)
            except ValueError:
                continue
            criteria[combo.currentText()] = (lo, hi)

        if not criteria:
            self.filter_summary_label.setText(
                "'조건 추가'로 행을 만들고, 지표를 고른 뒤 최소/최대 값을 숫자로 입력하세요."
            )
            self.filter_table.setRowCount(0)
            return

        device = self.device_combo.currentText()
        params = self.controller.all_params
        if device and device != "전체":
            params = [p for p in params if p.device.device_id == device]

        result = filter_by_ranges(params, criteria)

        if result.empty:
            self.filter_summary_label.setText("조건을 만족하는 split이 없습니다.")
            self.filter_table.setRowCount(0)
            return

        self.filter_summary_label.setText(f"{len(result)}개 split이 조건을 만족합니다: {', '.join(result.index)}")

        table = result.reset_index().rename(columns={"index": "split_label"})
        self.filter_table.setColumnCount(len(table.columns))
        self.filter_table.setHorizontalHeaderLabels([str(c) for c in table.columns])
        self.filter_table.setRowCount(len(table))
        for i, row in enumerate(table.itertuples(index=False)):
            for j, val in enumerate(row):
                text = f"{val:.4g}" if isinstance(val, float) else str(val)
                self.filter_table.setItem(i, j, QTableWidgetItem(text))


def _parse_kv_float(text: str) -> dict:
    result = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or "=" not in line:
            continue
        k, v = line.split("=", 1)
        try:
            result[k.strip()] = float(v.strip())
        except ValueError:
            continue
    return result

"""1) Import 페이지: 파일/폴더 임포트, gtree.dat 자동 감지, 새로고침."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QAbstractItemView,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..controllers.project_controller import ProjectController
from ..project_file import load_project, save_project


class ImportPage(QWidget):
    def __init__(self, controller: ProjectController, parent=None):
        super().__init__(parent)
        self.controller = controller

        layout = QVBoxLayout(self)

        top_row = QHBoxLayout()
        info = QLabel(
            "Sentaurus TCAD의 .plt 곡선 파일, gtree.dat, sdevice .cmd 파일, 또는 이미 추출된 "
            "파라미터 CSV/Excel을 불러오세요. 폴더를 선택하면 그 안의 관련 파일을 한 번에 인식합니다."
        )
        info.setWordWrap(True)
        top_row.addWidget(info, 1)

        self.btn_save_project = QPushButton("현재 데이터 저장")
        self.btn_save_project.setToolTip(
            "지금까지 임포트한 파일 구성 + Column Mapping에서 고친 값 + 추출 설정을\n"
            "파일 하나로 저장합니다."
        )
        self.btn_load_project = QPushButton("이전 데이터 불러오기")
        self.btn_load_project.setToolTip(
            "저장해둔 파일을 불러와 그대로 이어서 작업합니다.\n"
            "(원본 .plt/.cmd/gtree.dat 파일이 저장 당시와 같은 경로에 있어야 합니다)"
        )
        top_row.addWidget(self.btn_save_project)
        top_row.addWidget(self.btn_load_project)
        layout.addLayout(top_row)

        btn_row = QHBoxLayout()
        self.btn_files = QPushButton("파일 선택...")
        self.btn_folder = QPushButton("폴더 선택...")
        self.btn_refresh = QPushButton("새로고침")
        self.btn_refresh.setEnabled(False)
        btn_row.addWidget(self.btn_files)
        btn_row.addWidget(self.btn_folder)
        btn_row.addWidget(self.btn_refresh)
        btn_row.addStretch(1)
        layout.addLayout(btn_row)

        self.gtree_label = QLabel("gtree.dat: 아직 없음")
        layout.addWidget(self.gtree_label)

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["파일", "종류", "상태", "메시지"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        layout.addWidget(self.table)

        remove_row = QHBoxLayout()
        self.btn_remove = QPushButton("선택 항목 빼기")
        self.btn_clear = QPushButton("전체 지우기")
        remove_row.addWidget(self.btn_remove)
        remove_row.addWidget(self.btn_clear)
        remove_row.addStretch(1)
        layout.addLayout(remove_row)

        self.btn_files.clicked.connect(self._on_select_files)
        self.btn_folder.clicked.connect(self._on_select_folder)
        self.btn_refresh.clicked.connect(self._on_refresh)
        self.btn_remove.clicked.connect(self._on_remove_selected)
        self.btn_clear.clicked.connect(self._on_clear_all)
        self.btn_save_project.clicked.connect(self._on_save_project)
        self.btn_load_project.clicked.connect(self._on_load_project)
        self.controller.importChanged.connect(self._refresh_table)

    def _on_select_files(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(
            self,
            "파일 선택",
            "",
            "지원 파일 (*.plt *.csv *.xlsx *.xls *.cmd *.dat);;모든 파일 (*)",
        )
        if paths:
            self.controller.import_paths([Path(p) for p in paths])

    def _on_select_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "폴더 선택")
        if folder:
            self.controller.import_folder(Path(folder))
            self.btn_refresh.setEnabled(True)

    def _on_refresh(self) -> None:
        self.controller.refresh()

    def _on_remove_selected(self) -> None:
        rows = sorted({idx.row() for idx in self.table.selectedIndexes()})
        if not rows:
            return
        statuses = self.controller.import_status
        paths = [statuses[row].path for row in rows if row < len(statuses)]
        if not paths:
            return
        self.controller.remove_paths(paths)

    def _on_clear_all(self) -> None:
        if not self.controller.import_status:
            return
        answer = QMessageBox.question(
            self,
            "전체 지우기",
            "임포트된 파일을 전부 목록에서 뺄까요? (원본 파일은 지워지지 않습니다)",
        )
        if answer == QMessageBox.Yes:
            self.controller.clear_all_imports()

    def _on_save_project(self) -> None:
        if not self.controller.import_status:
            QMessageBox.information(self, "저장할 내용 없음", "먼저 파일을 임포트하세요.")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "현재 데이터 저장", "project.tcadproj", "TCAD 데이터 (*.tcadproj);;모든 파일 (*)"
        )
        if not path:
            return
        try:
            save_project(self.controller, Path(path))
        except OSError as exc:
            QMessageBox.warning(self, "저장 실패", f"데이터를 저장하지 못했습니다: {exc}")
            return
        QMessageBox.information(self, "저장 완료", f"데이터를 저장했습니다:\n{path}")

    def _on_load_project(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "이전 데이터 불러오기", "", "TCAD 데이터 (*.tcadproj);;모든 파일 (*)"
        )
        if not path:
            return
        try:
            result = load_project(self.controller, Path(path))
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, "불러오기 실패", f"데이터를 불러오지 못했습니다: {exc}")
            return

        msg = (
            f"파일 {result.restored_plt_count + result.restored_table_count}개, "
            f"curve {len(self.controller.curves)}개, "
            f"파라미터 {len(self.controller.extracted_params)}개를 복원했습니다."
        )
        if result.missing_files:
            missing_list = "\n".join(result.missing_files)
            msg += f"\n\n⚠ 다음 파일을 찾을 수 없어 건너뛰었습니다:\n{missing_list}"
        QMessageBox.information(self, "불러오기 완료", msg)

    def _refresh_table(self) -> None:
        statuses = self.controller.import_status
        self.table.setRowCount(len(statuses))
        for row, status in enumerate(statuses):
            self.table.setItem(row, 0, QTableWidgetItem(status.path.name))
            self.table.setItem(row, 1, QTableWidgetItem(status.kind))
            self.table.setItem(row, 2, QTableWidgetItem("성공" if status.ok else "실패"))
            self.table.setItem(row, 3, QTableWidgetItem(status.message))

        if self.controller.gtree_project:
            n = len(self.controller.gtree_project.nodes)
            self.gtree_label.setText(f"gtree.dat: {n}개 노드 인식됨 (파일 매핑 시 자동으로 split에 반영됩니다)")
        else:
            self.gtree_label.setText("gtree.dat: 아직 없음 (split 조건은 다음 단계에서 수동 입력할 수 있습니다)")

from PyQt6.QtWidgets import (QTreeView, QAbstractItemView, QMessageBox, QMenu, QProgressDialog, QApplication, QHeaderView)
from PyQt6.QtCore import Qt, QMimeData, QUrl, QSettings, QDir, QSortFilterProxyModel
from PyQt6.QtGui import QAction, QMouseEvent, QDrag, QIcon, QStandardItemModel, QStandardItem, QBrush, QColor
import os
import shutil
from datetime import datetime
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class CustomSortFilterProxyModel(QSortFilterProxyModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_sort_order = Qt.SortOrder.AscendingOrder

    def lessThan(self, left, right):
        left_row = left.row()
        right_row = right.row()
        source_model = self.sourceModel()
        left_name = source_model.item(left_row, 0).text()
        right_name = source_model.item(right_row, 0).text()

        left_is_file = source_model.item(left_row, 0).data(Qt.ItemDataRole.UserRole + 1)
        right_is_file = source_model.item(right_row, 0).data(Qt.ItemDataRole.UserRole + 1)

        if left_is_file is None or right_is_file is None:
            left_is_file = 0 if source_model.item(left_row, 2).text().lower() == "folder" else 1
            right_is_file = 0 if source_model.item(right_row, 2).text().lower() == "folder" else 1
            logging.warning(f"lessThan: Invalid UserRole + 1 for {left_name} or {right_name}")

        logging.debug(f"lessThan: Comparing {left_name} (is_file: {left_is_file}) with {right_name} (is_file: {right_is_file})")

        if left_is_file != right_is_file:
            result = left_is_file < right_is_file
            logging.debug(f"lessThan: {left_name} vs {right_name} -> folder/file ordering, result: {result}")
            return result

        column = left.column()
        left_value = self._get_sort_value(left_row, column, source_model)
        right_value = self._get_sort_value(right_row, column, source_model)

        logging.debug(f"lessThan: Values for column {column}: {left_value} vs {right_value}")

        if column == 1:
            if left_value == -1 and right_value == -1:
                left_value = self._get_sort_value(left_row, 0, source_model)
                right_value = self._get_sort_value(right_row, 0, source_model)
                logging.debug(f"lessThan: Both folders, sorting by name: {left_value} vs {right_value}")
        elif column == 2:
            if left_value == right_value:
                left_value = self._get_sort_value(left_row, 0, source_model)
                right_value = self._get_sort_value(right_row, 0, source_model)
                logging.debug(f"lessThan: Same type, sorting by name: {left_value} vs {right_value}")
        elif column == 3:
            if left_value == right_value:
                left_value = self._get_sort_value(left_row, 0, source_model)
                right_value = self._get_sort_value(right_row, 0, source_model)
                logging.debug(f"lessThan: Same date, sorting by name: {left_value} vs {right_value}")

        result = left_value < right_value if self._current_sort_order == Qt.SortOrder.AscendingOrder else left_value > right_value
        logging.debug(f"lessThan: {left_name} vs {right_name} -> {'less' if result else 'greater'} (column: {column}, order: {'Ascending' if self._current_sort_order == Qt.SortOrder.AscendingOrder else 'Descending'})")
        return result

    def _get_sort_value(self, row, column, source_model):
        item = source_model.item(row, column)
        if column == 0:
            value = item.data(Qt.ItemDataRole.UserRole + 2)
            if value is None:
                logging.warning(f"_get_sort_value: UserRole + 2 (name) not set for row {row}, using text")
                value = item.text().lower()
            return value
        elif column == 1:
            value = item.data(Qt.ItemDataRole.UserRole + 1)
            if value is None:
                logging.warning(f"_get_sort_value: UserRole + 1 (size) not set for row {row}, using 0")
                value = 0
            return value
        elif column == 2:
            value = item.data(Qt.ItemDataRole.UserRole + 1)
            if value is None:
                logging.warning(f"_get_sort_value: UserRole + 1 (type) not set for row {row}, using text")
                value = item.text().lower()
            return value
        else:
            value = item.data(Qt.ItemDataRole.UserRole + 1)
            if value is None:
                logging.warning(f"_get_sort_value: UserRole + 1 (date) not set for row {row}, using 0")
                value = 0
            return value

    def setSortOrder(self, order):
        self._current_sort_order = order
        logging.debug(f"Set sort order to {'Ascending' if order == Qt.SortOrder.AscendingOrder else 'Descending'}")

class CustomTreeView(QTreeView):
    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.BackButton:
            self.file_manager.go_back(self)
            logging.info("Back button pressed")
        elif event.button() == Qt.MouseButton.ForwardButton:
            self.file_manager.go_forward(self)
            logging.info("Forward button pressed")
        super().mousePressEvent(event)

class CustomTreeViewWithDrag(CustomTreeView):
    def __init__(self, file_manager, parent=None):
        super().__init__(parent)
        self.file_manager = file_manager
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDragDropMode(QAbstractItemView.DragDropMode.DragDrop)
        self.setDefaultDropAction(Qt.DropAction.CopyAction)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)
        self.setEditTriggers(QAbstractItemView.EditTrigger.DoubleClicked | QAbstractItemView.EditTrigger.SelectedClicked | QAbstractItemView.EditTrigger.EditKeyPressed)

        self.setSortingEnabled(False)
        self.header().setSectionsClickable(True)
        self.header().sectionClicked.connect(self.on_header_clicked)
        self.header().setSortIndicator(0, Qt.SortOrder.AscendingOrder)

        self._current_sort_column = 0
        self._current_sort_order = Qt.SortOrder.AscendingOrder

        self.header().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.header().setMinimumSectionSize(50)
        self.header().setStretchLastSection(False)

        self.drag_start_position = None
        self._sorting_in_progress = False

        self.proxy_model = CustomSortFilterProxyModel(self)
        self.proxy_model.setDynamicSortFilter(True)

        self.update_style()
        logging.info("Initialized CustomTreeViewWithDrag")

    def focusInEvent(self, event):
        super().focusInEvent(event)
        self.file_manager.update_active_zone(self)
        logging.debug("Tree view gained focus")

    def update_style(self):
        settings = QSettings("MyFileManager", "Settings")
        tree_font_size = settings.value("treeview_font_size", "10", type=str)
        tree_row_height = settings.value("treeview_row_height", "24", type=str)
        tree_bg_color = settings.value("treeview_bg_color", "#2E2E2E", type=str)
        tree_alt_bg_color = settings.value("treeview_alt_bg_color", "#353535", type=str)

        self.setStyleSheet(f"""
            QTreeView {{
                background: {tree_bg_color};
                color: #FFFFFF;
                border: none;
                font-size: {tree_font_size}pt;
            }}
            QTreeView::item {{
                padding: 2px;
                min-height: {tree_row_height}px;
            }}
            QTreeView::item:selected {{
                background-color: #4A4A4A;
            }}
            QHeaderView::section {{
                background-color: #3A3A3A;
                color: #FFFFFF;
                padding: 2px;
                border: none;
                height: 20px;
                font-size: 9pt;
            }}
        """)
        self.apply_alternating_colors()
        logging.debug("Updated tree view style")

    def apply_alternating_colors(self):
        settings = QSettings("MyFileManager", "Settings")
        tree_bg_color = settings.value("treeview_bg_color", "#2E2E2E", type=str)
        tree_alt_bg_color = settings.value("treeview_alt_bg_color", "#353535", type=str)

        source_model = self.proxy_model.sourceModel()
        if not source_model:
            return

        for row in range(source_model.rowCount()):
            for col in range(source_model.columnCount()):
                item = source_model.item(row, col)
                if item:
                    if row % 2 == 0:
                        item.setBackground(QBrush(QColor(tree_bg_color)))
                    else:
                        item.setBackground(QBrush(QColor(tree_alt_bg_color)))
        logging.debug("Applied alternating colors")

    def setModel(self, model):
        self.proxy_model.setSourceModel(model)
        super().setModel(self.proxy_model)
        self.apply_alternating_colors()
        logging.info(f"Set model and sorted by column {self._current_sort_column}, order: {'Ascending' if self._current_sort_order == Qt.SortOrder.AscendingOrder else 'Descending'}")
        self.proxy_model.setSortOrder(self._current_sort_order)
        self.proxy_model.sort(self._current_sort_column, self._current_sort_order)

    def on_header_clicked(self, column):
        if self._sorting_in_progress:
            return

        if not self.proxy_model:
            logging.error("Proxy model not defined")
            return

        if column == self._current_sort_column:
            new_order = Qt.SortOrder.DescendingOrder if self._current_sort_order == Qt.SortOrder.AscendingOrder else Qt.SortOrder.AscendingOrder
        else:
            new_order = Qt.SortOrder.AscendingOrder

        logging.info(f"Sorting by column {column}, order: {'Ascending' if new_order == Qt.SortOrder.AscendingOrder else 'Descending'}")

        self._sorting_in_progress = True
        try:
            self.proxy_model.setSortOrder(new_order)
            self.proxy_model.sort(column, new_order)

            self._current_sort_column = column
            self._current_sort_order = new_order

            self.header().setSortIndicator(column, new_order)

            self.apply_alternating_colors()
            self.viewport().update()
            self.update()
            self.file_manager.save_state()
        finally:
            self._sorting_in_progress = False

    def format_size(self, size):
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size < 1024:
                return f"{size:.2f} {unit}"
            size /= 1024
        return f"{size:.2f} PB"

    def dataChanged(self, topLeft, bottomRight, roles=None):
        super().dataChanged(topLeft, bottomRight, roles)
        if roles and Qt.ItemDataRole.EditRole in roles and topLeft.column() == 0:
            logging.info(f"Data changed due to editing at index: {topLeft.row()},{topLeft.column()}")
            self.file_manager.on_data_changed(self, topLeft)
        self.apply_alternating_colors()
        logging.debug("Data changed, reapplied alternating colors")

    def rowsInserted(self, parent, start, end):
        super().rowsInserted(parent, start, end)
        self.apply_alternating_colors()
        logging.debug(f"Rows inserted from {start} to {end}")

    def rowsRemoved(self, parent, start, end):
        super().rowsRemoved(parent, start, end)
        self.apply_alternating_colors()
        logging.debug(f"Rows removed from {start} to {end}")

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_start_position = event.pos()
        super().mousePressEvent(event)
        self.file_manager.update_active_zone(self)
        logging.debug("Mouse pressed in tree view")

    def mouseMoveEvent(self, event):
        if not (event.buttons() & Qt.MouseButton.LeftButton):
            return
        if not self.drag_start_position or (event.pos() - self.drag_start_position).manhattanLength() < QApplication.startDragDistance():
            return
        selected_indexes = self.selectedIndexes()
        if not selected_indexes:
            return
        drag = QDrag(self)
        mime_data = QMimeData()
        urls = []
        processed_rows = set()
        for index in selected_indexes:
            if index.column() == 0 and index.row() not in processed_rows:
                source_index = self.proxy_model.mapToSource(index)
                path = self.proxy_model.sourceModel().item(source_index.row(), 0).data(Qt.ItemDataRole.UserRole)
                urls.append(QUrl.fromLocalFile(path))
                processed_rows.add(index.row())
        mime_data.setUrls(urls)
        drag.setMimeData(mime_data)
        pixmap = self.viewport().grab()
        drag.setPixmap(pixmap.scaled(100, 100, Qt.AspectRatioMode.KeepAspectRatio))
        drag.setHotSpot(event.pos() - self.drag_start_position)
        drag.exec(Qt.DropAction.CopyAction | Qt.DropAction.MoveAction)
        logging.debug(f"Started drag with {len(urls)} items")

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        if event.mimeData().hasUrls():
            index = self.indexAt(event.position().toPoint())
            source_index = self.proxy_model.mapToSource(index) if index.isValid() else None
            dest_path = self.proxy_model.sourceModel().item(source_index.row(), 0).data(Qt.ItemDataRole.UserRole) if source_index else self.file_manager.current_path(self)
            if not os.path.isdir(dest_path):
                dest_path = os.path.dirname(dest_path)
            src_paths = [url.toLocalFile() for url in event.mimeData().urls()]
            if not src_paths:
                return
            menu = QMenu(self)
            copy_action = QAction("Скопировать", self)
            move_action = QAction("Переместить", self)
            cancel_action = QAction("Отмена", self)
            copy_action.triggered.connect(lambda: self.file_manager.perform_file_operation(src_paths, dest_path, "copy"))
            move_action.triggered.connect(lambda: self.file_manager.perform_file_operation(src_paths, dest_path, "move"))
            menu.addAction(copy_action)
            menu.addAction(move_action)
            menu.addAction(cancel_action)
            menu.exec(self.mapToGlobal(event.position().toPoint()))
            event.acceptProposedAction()
            self.file_manager.refresh_view(self)
            logging.info(f"Dropped {len(src_paths)} items to {dest_path}")

    def show_context_menu(self, position):
        menu = QMenu()
        refresh_action = QAction("Обновить", self)
        copy_action = QAction("Копировать", self)
        cut_action = QAction("Вырезать", self)
        paste_action = QAction("Вставить", self)
        delete_action = QAction("Переместить в корзину", self)
        new_folder_action = QAction("Создать папку", self)
        new_text_file_action = QAction("Создать текстовый документ", self)
        refresh_action.triggered.connect(lambda: self.file_manager.refresh_view(self))
        copy_action.triggered.connect(lambda: self.file_manager.hotkey_manager.copy_files())
        cut_action.triggered.connect(lambda: self.file_manager.hotkey_manager.cut_files())
        paste_action.triggered.connect(lambda: self.file_manager.hotkey_manager.paste_files())
        delete_action.triggered.connect(self.delete_selected)
        new_folder_action.triggered.connect(self.create_new_folder)
        new_text_file_action.triggered.connect(self.create_new_text_file)
        menu.addAction(refresh_action)
        menu.addSeparator()
        menu.addAction(copy_action)
        menu.addAction(cut_action)
        if self.file_manager.clipboard:
            menu.addAction(paste_action)
        menu.addSeparator()
        menu.addAction(delete_action)
        menu.addAction(new_folder_action)
        menu.addAction(new_text_file_action)
        menu.exec(self.mapToGlobal(position))
        logging.debug("Showed context menu")

    def delete_selected(self):
        selected = self.selectedIndexes()
        if not selected:
            logging.info("No items selected for deletion")
            QMessageBox.warning(self.file_manager, "Ошибка", "Выберите файлы или папки для удаления")
            return
        total_items = len(set(index.row() for index in selected))
        reply = QMessageBox.question(self.file_manager, "Удаление", "Переместить выбранные элементы в корзину?",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply != QMessageBox.StandardButton.Yes:
            return
        progress = QProgressDialog("Перемещение в корзину...", "Отмена", 0, total_items, self.file_manager)
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setAutoClose(True)
        deleted_paths = set()
        for i, index in enumerate(selected):
            if index.column() != 0 or index.row() in deleted_paths:
                continue
            source_index = self.proxy_model.mapToSource(index)
            path = self.proxy_model.sourceModel().item(source_index.row(), 0).data(Qt.ItemDataRole.UserRole)
            progress.setValue(i)
            progress.setLabelText(f"Перемещение: {os.path.basename(path)}")
            if not os.path.exists(path):
                logging.warning(f"Path does not exist for deletion: {path}")
                continue
            try:
                if not os.access(path, os.W_OK):
                    logging.error(f"No write permission for {path}")
                    QMessageBox.warning(self.file_manager, "Ошибка", f"Нет прав на удаление: {path}")
                    continue
                if self.file_manager.undo_manager.move_to_trash(path):
                    self.file_manager.undo_manager.add_action('DELETE', path=path)
                    deleted_paths.add(index.row())
                    logging.info(f"Moved to trash: {path}")
                else:
                    logging.error(f"Failed to move {path} to trash")
                    QMessageBox.warning(self.file_manager, "Ошибка", f"Не удалось переместить {path} в корзину")
            except Exception as e:
                logging.error(f"Error moving {path} to trash: {e}")
                QMessageBox.warning(self.file_manager, "Ошибка", f"Не удалось переместить {path} в корзину: {e}")
            if progress.wasCanceled():
                break
        progress.setValue(total_items)
        self.file_manager.refresh_view(self)

    def create_new_folder(self):
        current_path = self.file_manager.current_path(self)
        base_name = "Новая папка"
        new_path = os.path.join(current_path, base_name)
        counter = 1
        while os.path.exists(new_path):
            new_path = os.path.join(current_path, f"{base_name} ({counter})")
            counter += 1
        try:
            os.makedirs(new_path)
            self.file_manager.undo_manager.add_action('CREATE_FOLDER', path=new_path)
            self.file_manager.refresh_view(self)
            logging.info(f"Created new folder: {new_path}")
        except PermissionError as e:
            logging.error(f"No permission to create folder: {e}")
            QMessageBox.warning(self.file_manager, "Ошибка", f"Нет прав на создание папки: {e}")
        except OSError as e:
            logging.error(f"Failed to create folder: {e}")
            QMessageBox.warning(self.file_manager, "Ошибка", f"Не удалось создать папку: {e}")

    def create_new_text_file(self):
        current_path = self.file_manager.current_path(self)
        base_name = "Новый текстовый документ.txt"
        new_path = os.path.join(current_path, base_name)
        counter = 1
        while os.path.exists(new_path):
            new_path = os.path.join(current_path, f"Новый текстовый документ ({counter}).txt")
            counter += 1
        try:
            with open(new_path, 'w') as f:
                pass
            self.file_manager.undo_manager.add_action('CREATE_FILE', path=new_path)
            self.file_manager.refresh_view(self)
            logging.info(f"Created new text file: {new_path}")
        except PermissionError as e:
            logging.error(f"No permission to create file: {e}")
            QMessageBox.warning(self.file_manager, "Ошибка", f"Нет прав на создание файла: {e}")
        except OSError as e:
            logging.error(f"Failed to create file: {e}")
            QMessageBox.warning(self.file_manager, "Ошибка", f"Не удалось создать текстовый документ: {e}")

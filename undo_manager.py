import os
import shutil
import time
import logging
from PyQt6.QtWidgets import QMessageBox
from datetime import datetime
import urllib.parse

# Configure logging for undo operations
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class UndoAction:
    def __init__(self, action_type, **kwargs):
        self.action_type = action_type
        self.kwargs = kwargs
        self.timestamp = time.time()  # Store timestamp for unique action tracking

class UndoManager:
    def __init__(self):
        self.undo_stack = []
        self.max_stack_size = 100  # Limit stack size to prevent memory issues

    def add_action(self, action_type, **kwargs):
        """Add an action to the undo stack with validation."""
        required_params = {
            'COPY': ['dest_path'],
            'MOVE': ['src_path', 'dest_path'],
            'DELETE': ['path'],
            'CREATE_FOLDER': ['path'],
            'CREATE_FILE': ['path'],
            'RENAME': ['old_path', 'new_path']
        }
        if action_type in required_params:
            for param in required_params[action_type]:
                if param not in kwargs:
                    logging.error(f"Missing parameter {param} for action {action_type}")
                    return
        action = UndoAction(action_type, **kwargs)
        self.undo_stack.append(action)
        logging.info(f"Added action: {action_type}, params: {kwargs}")
        # Trim stack if it exceeds max size
        if len(self.undo_stack) > self.max_stack_size:
            self.undo_stack.pop(0)
            logging.debug("Trimmed undo stack to maintain max size")

    def undo(self):
        """Undo the last action in the stack."""
        if not self.undo_stack:
            logging.info("Undo stack is empty")
            return
        action = self.undo_stack.pop()
        logging.info(f"Undoing action: {action.action_type}, params: {action.kwargs}")
        try:
            if action.action_type == 'COPY':
                self._undo_copy(action.kwargs['dest_path'])
            elif action.action_type == 'MOVE':
                self._undo_move(action.kwargs['src_path'], action.kwargs['dest_path'])
            elif action.action_type == 'DELETE':
                self._undo_delete(action.kwargs['path'])
            elif action.action_type == 'CREATE_FOLDER':
                self._undo_create_folder(action.kwargs['path'])
            elif action.action_type == 'CREATE_FILE':
                self._undo_create_file(action.kwargs['path'])
            elif action.action_type == 'RENAME':
                self._undo_rename(action.kwargs['old_path'], action.kwargs['new_path'])
        except Exception as e:
            logging.error(f"Failed to undo {action.action_type}: {e}")
            # Re-add action to stack if undo fails
            self.undo_stack.append(action)
            raise

    def _undo_copy(self, dest_path):
        """Undo a copy operation by removing the copied file."""
        if not os.path.exists(dest_path):
            logging.warning(f"Cannot undo copy: {dest_path} does not exist")
            return
        try:
            if os.path.isdir(dest_path):
                shutil.rmtree(dest_path)
            else:
                os.remove(dest_path)
            logging.info(f"Undid copy: Removed {dest_path}")
        except PermissionError as e:
            logging.error(f"No permission to remove {dest_path}: {e}")
            raise
        except OSError as e:
            logging.error(f"Failed to remove {dest_path}: {e}")
            raise

    def _undo_move(self, src_path, dest_path):
        """Undo a move operation by moving the file back."""
        if not os.path.exists(dest_path):
            logging.warning(f"Cannot undo move: {dest_path} does not exist")
            return
        if os.path.exists(src_path):
            logging.warning(f"Cannot undo move: {src_path} already exists")
            return
        try:
            shutil.move(dest_path, src_path)
            logging.info(f"Undid move: {dest_path} -> {src_path}")
        except PermissionError as e:
            logging.error(f"No permission to move {dest_path} to {src_path}: {e}")
            raise
        except OSError as e:
            logging.error(f"Failed to move {dest_path} to {src_path}: {e}")
            raise

    def _undo_delete(self, path):
        """Undo a delete operation by restoring from trash."""
        trash_files_dir = os.path.expanduser("~/.local/share/Trash/files")
        trash_info_dir = os.path.expanduser("~/.local/share/Trash/info")
        base_name = os.path.basename(path)
        trash_file_path = os.path.join(trash_files_dir, base_name)
        trash_info_path = os.path.join(trash_info_dir, f"{base_name}.trashinfo")

        if not os.path.exists(trash_file_path):
            logging.warning(f"Cannot restore {path}: not found in trash at {trash_file_path}")
            QMessageBox.warning(None, "Предупреждение", f"Файл {path} не найден в корзине.")
            return

        try:
            # Ensure parent directory exists
            os.makedirs(os.path.dirname(path), exist_ok=True)
            # Restore the file
            shutil.move(trash_file_path, path)
            # Remove the trashinfo file
            if os.path.exists(trash_info_path):
                os.remove(trash_info_path)
            logging.info(f"Restored {path} from trash")
        except PermissionError as e:
            logging.error(f"No permission to restore {path}: {e}")
            raise
        except OSError as e:
            logging.error(f"Failed to restore {path}: {e}")
            raise

    def _undo_create_folder(self, path):
        """Undo a folder creation by removing the folder."""
        if not os.path.exists(path):
            logging.warning(f"Cannot undo folder creation: {path} does not exist")
            return
        try:
            os.rmdir(path)
            logging.info(f"Undid folder creation: Removed {path}")
        except PermissionError as e:
            logging.error(f"No permission to remove {path}: {e}")
            raise
        except OSError as e:
            logging.error(f"Failed to remove {path}: {e}")
            raise

    def _undo_create_file(self, path):
        """Undo a file creation by removing the file."""
        if not os.path.exists(path):
            logging.warning(f"Cannot undo file creation: {path} does not exist")
            return
        try:
            os.remove(path)
            logging.info(f"Undid file creation: Removed {path}")
        except PermissionError as e:
            logging.error(f"No permission to remove {path}: {e}")
            raise
        except OSError as e:
            logging.error(f"Failed to remove {path}: {e}")
            raise

    def _undo_rename(self, old_path, new_path):
        """Undo a rename operation by reverting to the old name."""
        if not os.path.exists(new_path):
            logging.warning(f"Cannot undo rename: {new_path} does not exist")
            return
        if os.path.exists(old_path):
            logging.warning(f"Cannot undo rename: {old_path} already exists")
            return
        logging.info(f"Attempting to undo rename: {new_path} -> {old_path}")
        try:
            os.rename(new_path, old_path)
            logging.info(f"Undid rename: {new_path} -> {old_path}")
        except PermissionError as e:
            logging.error(f"No permission to rename {new_path} to {old_path}: {e}")
            raise
        except OSError as e:
            logging.error(f"Failed to rename {new_path} to {old_path}: {e}")
            raise

    def move_to_trash(self, path):
        """Move a file or folder to the Linux trash directory."""
        if not os.path.exists(path):
            logging.warning(f"Cannot move to trash: {path} does not exist")
            return False

        trash_files_dir = os.path.expanduser("~/.local/share/Trash/files")
        trash_info_dir = os.path.expanduser("~/.local/share/Trash/info")
        base_name = os.path.basename(path)
        trash_file_path = os.path.join(trash_files_dir, base_name)
        trash_info_path = os.path.join(trash_info_dir, f"{base_name}.trashinfo")

        # Handle name conflicts
        counter = 1
        while os.path.exists(trash_file_path) or os.path.exists(trash_info_path):
            base_name = f"{os.path.splitext(os.path.basename(path))[0]}_{counter}{os.path.splitext(path)[1]}"
            trash_file_path = os.path.join(trash_files_dir, base_name)
            trash_info_path = os.path.join(trash_info_dir, f"{base_name}.trashinfo")
            counter += 1

        try:
            # Create trash directories if they don't exist
            os.makedirs(trash_files_dir, exist_ok=True)
            os.makedirs(trash_info_dir, exist_ok=True)

            # Move the file to trash
            shutil.move(path, trash_file_path)

            # Create .trashinfo file
            deletion_time = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
            trash_info_content = (
                "[Trash Info]\n"
                f"Path={urllib.parse.quote(path)}\n"
                f"DeletionDate={deletion_time}\n"
            )
            with open(trash_info_path, 'w', encoding='utf-8') as f:
                f.write(trash_info_content)

            logging.info(f"Moved to trash: {path} -> {trash_file_path}")
            return True
        except PermissionError as e:
            logging.error(f"No permission to move {path} to trash: {e}")
            return False
        except OSError as e:
            logging.error(f"Error moving {path} to trash: {e}")
            return False

    def clear_trash(self):
        """Permanently delete all files in the trash."""
        trash_files_dir = os.path.expanduser("~/.local/share/Trash/files")
        trash_info_dir = os.path.expanduser("~/.local/share/Trash/info")

        try:
            if os.path.exists(trash_files_dir):
                shutil.rmtree(trash_files_dir)
                os.makedirs(trash_files_dir, exist_ok=True)
            if os.path.exists(trash_info_dir):
                shutil.rmtree(trash_info_dir)
                os.makedirs(trash_info_dir, exist_ok=True)
            logging.info("Cleared trash directory")
            return True
        except PermissionError as e:
            logging.error(f"No permission to clear trash: {e}")
            return False
        except OSError as e:
            logging.error(f"Failed to clear trash: {e}")
            return False

    def clear_stack(self):
        """Clear the undo stack."""
        self.undo_stack = []
        logging.info("Cleared undo stack")

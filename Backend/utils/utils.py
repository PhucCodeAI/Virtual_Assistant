import os

from dtos.utils import CodeBase


def _generate_codebase_tree(
    path: str,
    extensions: list[str] | str | None = None,
    folders: list[str] | str | None = None,
    files: list[str] | str | None = None,
    return_json: bool = False,
) -> str | CodeBase:
    """
    Quét toàn bộ thư mục và tạo ra một sơ đồ cây văn bản trực quan hoặc đối tượng CodeBase JSON.

    - Input: path (str, Thư mục gốc cần quét)
    - Input: extensions (Đuôi file hoặc chuỗi kết thúc cần bỏ qua)
    - Input: folders (Tên thư mục cần bỏ qua)
    - Input: files (Tên file cụ thể cần bỏ qua)
    - Input: return_json (bool, True nếu muốn trả về cấu trúc CodeBase Model)
    - Output: str (nếu return_json=False) hoặc CodeBase (nếu return_json=True)
    """
    if isinstance(extensions, str):
        extensions = [extensions]
    extensions = [
        ext if ext.startswith(".") else f".{ext}" for ext in (extensions or [])
    ]

    if isinstance(folders, str):
        folders = [folders]
    folders = [os.path.basename(os.path.normpath(f)) for f in (folders or [])]

    if isinstance(files, str):
        files = [files]
    files = [os.path.basename(f) for f in (files or [])]

    root_abs_path = os.path.abspath(path)

    if return_json:

        def _build_json_tree(current_dir: str) -> CodeBase:
            dir_name = os.path.basename(os.path.normpath(current_dir))
            rel_path = os.path.relpath(current_dir, root_abs_path)
            if rel_path == ".":
                rel_path = dir_name

            node = CodeBase(name=dir_name, path=rel_path, type="folder", children=[])

            try:
                items = sorted(
                    os.listdir(current_dir),
                    key=lambda x: (
                        not os.path.isdir(os.path.join(current_dir, x)),
                        x.lower(),
                    ),
                )
            except PermissionError:
                return node

            for item in items:
                full_path = os.path.join(current_dir, item)
                item_rel_path = os.path.relpath(full_path, root_abs_path)

                if os.path.isdir(full_path):
                    if item in folders:
                        continue
                    child_folder_node = _build_json_tree(full_path)
                    if child_folder_node:
                        node.children.append(child_folder_node)
                else:
                    if item in files:
                        continue
                    if any(item.endswith(ext) for ext in extensions):
                        continue

                    # Ép kiểu dữ liệu phần tử file về cấu trúc CodeBase chuẩn
                    node.children.append(
                        CodeBase(name=item, path=item_rel_path, type="file")
                    )
            return node

        return _build_json_tree(root_abs_path)

    output_lines = [f"Root: {os.path.basename(os.path.normpath(path))}/"]

    def _build_text_tree(current_dir: str, prefix: str = ""):
        try:
            items = sorted(
                os.listdir(current_dir),
                key=lambda x: (
                    not os.path.isdir(os.path.join(current_dir, x)),
                    x.lower(),
                ),
            )
        except PermissionError:
            return

        filtered_items = []
        for item in items:
            full_path = os.path.join(current_dir, item)
            if os.path.isdir(full_path):
                if item in folders:
                    continue
            else:
                if item in files:
                    continue
                if any(item.endswith(ext) for ext in extensions):
                    continue
            filtered_items.append(item)

        count = len(filtered_items)
        for index, item in enumerate(filtered_items):
            full_path = os.path.join(current_dir, item)
            is_last = index == count - 1

            pointer = "└── " if is_last else "├── "

            if os.path.isdir(full_path):
                output_lines.append(f"{prefix}{pointer}folder: {item}/")
                new_prefix = prefix + ("    " if is_last else "│   ")
                _build_text_tree(full_path, new_prefix)
            else:
                output_lines.append(f"{prefix}{pointer}file: {item}")

    _build_text_tree(root_abs_path)
    return "\n".join(output_lines)


def format_message(
    system_prompt: str = "", prompt: str = "", assistance: str = ""
) -> list[dict[str, str]]:
    message = []

    if system_prompt.strip():
        message.append({"role": "system", "content": system_prompt.strip()})
    if prompt.strip():
        message.append({"role": "user", "content": prompt.strip()})
    if assistance.strip():
        message.append({"role": "assistant", "content": assistance.strip()})

    return message


def override_system_prompt(
    agent_system_prompt: str, messages: list[dict[str, str]]
) -> list[dict[str, str]]:
    """
    Ghi đè hoàn toàn System Prompt cũ bằng System Prompt chuyên biệt của Agent.
    Loại bỏ triệt để nguy cơ Prompt Collision (xung đột chỉ thị).
    Đảm bảo duy nhất 1 System Message nằm ở Index 0 cho llama-cpp-python.

    -Input: agent_system_prompt (str), messages (list[dict[str, str]])
    -Output: list[dict[str, str]] (Mảng messages sạch chỉ chứa 1 system prompt + history user/assistant)
    """
    clean_history = [msg for msg in messages if msg.get("role") != "system"]

    agent_system_msg = {"role": "system", "content": agent_system_prompt}

    return [agent_system_msg] + clean_history


if __name__ == "__main__":
    path = r"../UI"

    folders_to_ignore = [
        ".git",
        ".venv",
        "__pycache__",
        "logs",
        "static",
        "node_modules",
        "assets",
        ".pytest_cache",
        ".vscode",
    ]
    extensions_to_ignore = [".pyc", ".log", ".DS_Store", ".lock"]
    files_to_ignore = [
        "test.py",
        ".env",
        ".python-version",
        "test.json",
    ]

    tree_result = _generate_codebase_tree(
        path=path,
        extensions=extensions_to_ignore,
        folders=folders_to_ignore,
        files=files_to_ignore,
        return_json=False,
    )

    print(tree_result)

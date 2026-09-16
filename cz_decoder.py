import os
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from czdecoder.pipeline import build_page_rows, recognize_row
from czdecoder.excel import save_excel
from czdecoder.shortcuts import classify_shortcut
from czdecoder.bindings import SHEET_BINDINGS
from czdecoder.paths import (
    can_save_next_to_pdf,
    get_common_pdf_directory,
    result_filename_from_directory,
)
from czdecoder.version import APP_VERSION
from tksheet import Sheet

# --- Drag'n'Drop: tkinterdnd2 ---
DND_FILES = "DND_Files"
TkinterDnD = None
HAS_DND = False
try:
    from tkinterdnd2 import DND_FILES as _DND, TkinterDnD as _TD
    DND_FILES = _DND
    TkinterDnD = _TD
    HAS_DND = True
except ImportError:
    pass


APP_TITLE = f"Честный знак PDF → Excel v{APP_VERSION}"


# --- Состояние ---
app_state = {"rows": [], "recognized": False}
# Ссылка на кнопку «Сохранить рядом с PDF» (создаётся ниже в GUI-блоке).
save_next_btn = None


def set_status(text: str):
    status_var.set(text)
    root.update_idletasks()


def _install_layout_independent_shortcuts(sheet):
    """Делает Ctrl+C и Ctrl+A независимыми от раскладки клавиатуры.

    Штатные tksheet copy/select_all привязаны к keysym 'c'/'C'/'a'/'A', поэтому
    при русской раскладке (физическая C → 'Cyrillic_es', физическая A →
    'Cyrillic_ef') они не срабатывают. Здесь добавляем fallback на физическую
    клавишу: ловим <Control-KeyPress> и, если это не латиница (т.е. штатный bind
    гарантированно не сработал), вызываем ШТАТНЫЙ метод tksheet ctrl_c()/select_all().
    """
    mt = sheet.MT

    def handler(event):
        action = classify_shortcut(
            bool(event.state & 0x0004),  # state бит 0x0004 = Ctrl зажат
            event.keysym,
            event.keycode or 0,
        )
        if action == "copy":
            try:
                mt.ctrl_c()
            except Exception:
                pass
            return "break"
        if action == "select_all":
            try:
                mt.select_all()
            except Exception:
                pass
            return "break"
        return None

    # Вешаем на body-таблицу (там фокус при выделении ячеек) и на сам Sheet
    # (покрывает фокус на RI/CH при выделении строки/столбца).
    for w in (sheet.MT, sheet.RI, sheet.CH, sheet.TL, sheet):
        try:
            w.bind("<Control-KeyPress>", handler, add="+")
        except Exception:
            pass


def refresh_sheet():
    data = []
    for r in app_state["rows"]:
        data.append([
            r.get("full_dm", ""),
            r.get("gtin", ""),
            r.get("pn", ""),
            r.get("qty", ""),
            r["file_name"],
            r["page_num"],
        ])
    sheet.set_sheet_data(data)
    try:
        sheet.column_width(column=0, width=380)
        sheet.column_width(column=1, width=130)
        sheet.column_width(column=2, width=280)
        sheet.column_width(column=3, width=70)
        sheet.column_width(column=4, width=180)
        sheet.column_width(column=5, width=70)
    except Exception:
        pass


def _add_files(files):
    new_rows = build_page_rows(list(files))
    app_state["rows"].extend(new_rows)
    app_state["recognized"] = False
    refresh_sheet()
    update_save_buttons_state()
    set_status(f"Загружено страниц: {len(new_rows)}")


def load_pdfs():
    filenames = filedialog.askopenfilenames(
        title="Выберите PDF файлы",
        filetypes=[("PDF files", "*.pdf")]
    )
    if filenames:
        _add_files(list(filenames))


def load_folder():
    from czdecoder.pipeline import list_pdf_paths
    folder = filedialog.askdirectory(title="Выберите папку с PDF файлами")
    if not folder:
        return
    pdfs = list_pdf_paths(folder)
    if pdfs:
        _add_files(pdfs)
    else:
        messagebox.showinfo("Пусто", "PDF файлы в папке не найдены.")


def on_drop(event):
    raw = event.data.strip()
    if not raw:
        return
    # На Windows tkinterdnd2 может выдавать путь в фигурных скобках
    paths = root.tk.splitlist(raw)
    pdfs = []
    for p in paths:
        p = p.strip().strip("{}").strip('"')
        if p.lower().endswith(".pdf") and os.path.isfile(p):
            pdfs.append(p)
    if pdfs:
        _add_files(pdfs)


def recognize():
    if not app_state["rows"]:
        messagebox.showwarning("Нет данных", "Сначала загрузите PDF файлы.")
        return

    total_pages = len(app_state["rows"])
    progress_bar["maximum"] = max(total_pages, 1)
    progress_bar["value"] = 0
    done = 0

    try:
        for r in app_state["rows"]:
            recognize_row(r)
            done += 1
            progress_bar["value"] = done
            root.update_idletasks()

        app_state["recognized"] = True
        refresh_sheet()
        update_save_buttons_state()
        set_status(f"Распознано страниц: {done}")

    except Exception as e:
        messagebox.showerror("Ошибка", f"Ошибка распознавания:\n{e}")
        set_status("Ошибка распознавания")


def _save_excel_to(excel_path: str):
    """Общая реализация сохранения Excel (без диалога выбора папки).

    Вызывает save_excel(), обновляет статус, показывает info/error box.
    """
    try:
        save_excel(app_state["rows"], excel_path)
        set_status(f"Сохранено: {excel_path}")
        messagebox.showinfo("Готово", f"Excel сохранён:\n{excel_path}")
    except Exception as e:
        messagebox.showerror("Ошибка", f"Ошибка сохранения:\n{e}")
        set_status("Ошибка сохранения")


def save_excel_gui():
    if not app_state["rows"]:
        messagebox.showwarning("Нет данных", "Сначала загрузите PDF файлы.")
        return
    if not app_state["recognized"]:
        messagebox.showwarning("Не распознано", "Сначала нажмите «Распознать».")
        return

    out_dir = filedialog.askdirectory(title="Выберите папку для сохранения Excel")
    if not out_dir:
        return

    _save_excel_to(os.path.join(out_dir, "result.xlsx"))


def _save_buttons_can_save():
    """Можно ли сохранить «рядом с PDF»: есть rows, распознано, одна общая папка."""
    return can_save_next_to_pdf(app_state["rows"], app_state["recognized"])


def update_save_buttons_state():
    state = "normal" if _save_buttons_can_save() else "disabled"
    if save_next_btn is not None:
        save_next_btn.config(state=state)  # noqa: save_next_btn — ttk.Button


def save_excel_next_to_pdf():
    if not app_state["rows"]:
        messagebox.showwarning("Нет данных", "Сначала загрузите PDF файлы.")
        return
    if not app_state["recognized"]:
        messagebox.showwarning("Не распознано", "Сначала нажмите «Распознать».")
        return

    directory = get_common_pdf_directory(app_state["rows"])
    if directory is None:
        messagebox.showwarning(
            "Разные папки", "PDF находятся в разных папках — сохраните Excel вручную.")
        return

    _save_excel_to(os.path.join(directory, result_filename_from_directory(directory)))


def clear_table():
    app_state["rows"] = []
    app_state["recognized"] = False
    sheet.set_sheet_data([])
    update_save_buttons_state()
    set_status("Таблица очищена")


# --- GUI ---
if HAS_DND:
    root = TkinterDnD.Tk()
else:
    root = tk.Tk()

root.title(APP_TITLE)
root.geometry("1280x720")
root.minsize(1120, 650)

status_var = tk.StringVar(value="Готово к работе")

main = ttk.Frame(root, padding=10)
main.pack(fill="both", expand=True)

ttk.Label(main, text=f"Декодер DataMatrix из PDF → Excel  v{APP_VERSION}",
          font=("Segoe UI", 14, "bold")).pack(anchor="w", pady=(0, 10))

toolbar = ttk.Frame(main)
toolbar.pack(fill="x", pady=(0, 10))

ttk.Button(toolbar, text="Загрузить PDF", command=load_pdfs).pack(side="left")
ttk.Button(toolbar, text="Загрузить папку", command=load_folder).pack(side="left", padx=(8, 0))
ttk.Button(toolbar, text="Распознать", command=recognize).pack(side="left", padx=(8, 0))
ttk.Button(toolbar, text="Сохранить Excel", command=save_excel_gui).pack(side="left", padx=(8, 0))
save_next_btn = ttk.Button(toolbar, text="Сохранить рядом с PDF",
                           command=save_excel_next_to_pdf, state="disabled")
save_next_btn.pack(side="left", padx=(8, 0))
ttk.Button(toolbar, text="Очистить", command=clear_table).pack(side="left", padx=(8, 0))

drop_text = "Перетащите PDF файлы сюда"
drop_label = tk.Label(main, text=drop_text,
                      relief="groove", bd=2, bg="#f2f2f2",
                      height=3, font=("Segoe UI", 10))
drop_label.pack(fill="x", pady=(0, 10))

if HAS_DND:
    try:
        drop_label.drop_target_register(DND_FILES)
        drop_label.dnd_bind("<<Drop>>", on_drop)
    except Exception:
        drop_label.config(text="Drag'n'Drop недоступен. Используйте кнопки.")

sheet = Sheet(main, headers=["Полный DM", "GTIN", "PN", "Кол-во", "Файл", "Страница"])
sheet.pack(fill="both", expand=True)

# Excel-like selection & copy (tksheet >= 7.6 штатно это поддерживает).
# Таблица остаётся read-only по содержимому: мы НЕ включаем edit_cell /
# paste / delete / cut / undo / redo / edit_header / edit_index — поэтому
# пользователь может выделять, копировать, менять ширину колонок и
# скроллить, но не редактировать распознанные значения.
sheet.enable_bindings(SHEET_BINDINGS)

# Ctrl+C / Ctrl+A должны работать независимо от раскладки клавиатуры (EN/RU).
_install_layout_independent_shortcuts(sheet)

bottom = ttk.Frame(main)
bottom.pack(fill="x", pady=(10, 0))

progress_bar = ttk.Progressbar(bottom, orient="horizontal", mode="determinate", length=280)
progress_bar.pack(side="right")

ttk.Label(main, textvariable=status_var, relief="sunken", anchor="w").pack(fill="x", pady=(8, 0))

root.mainloop()
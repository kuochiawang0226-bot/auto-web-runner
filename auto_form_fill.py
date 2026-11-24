# -*- coding: utf-8 -*-
"""GitHub Actions 單列執行版。請配合 .github/workflows/run-row.yml 與 README 使用。
每次工作只查一次 IP；重複時由下一個獨立工作重試，不使用 Tor。
原有網頁定位及操作邏輯保留。操作完成不等同網站已確認受理。
"""
import os
import time

_raw_url = os.environ.get("TARGET_URL", "")
TARGET_URL = _raw_url.strip()

print("網址設定檢查：", {
    "有讀到內容": bool(_raw_url),
    "前後有空白或換行": _raw_url != TARGET_URL,
    "以https開頭": TARGET_URL.startswith("https://"),
    "包含預設提示文字": "請填入" in TARGET_URL,
})
EXCEL_PATH = os.environ.get("EXCEL_PATH", "data.xlsx")
SHEET_NAME = os.environ.get("SHEET_NAME") or None
DROPDOWN1_OPTION = "中部汽車"
SUBMIT_TEXT = "送出"
WAIT_AFTER_SUBMIT = 5
DROPDOWN1_SELECTOR = ""
DROPDOWN2_SELECTOR = ""
FIELD_SELECTOR = ""
FIELD_PLACEHOLDER = "請填入文字"

CUSTOM_DROPDOWN_CSS = (
    '[role="listbox"][aria-expanded], '
    "[role=combobox], [aria-haspopup=listbox], .el-select, .ant-select, "
    ".select2-selection, .v-select, .dropdown-toggle"
)


def _select_native(sel, label, wait=15):
    """一般下拉選單：只接受完整名稱一致的選項。"""
    label = str(label).strip()
    deadline = time.monotonic() + wait

    while time.monotonic() < deadline:
        texts = [
            t.strip()
            for t in sel.locator("option").all_inner_texts()
        ]
        matches = [
            index for index, text in enumerate(texts)
            if text == label
        ]

        if len(matches) > 1:
            raise RuntimeError(f"選單中有多個同名選項「{label}」")

        if len(matches) == 1:
            sel.select_option(index=matches[0], force=True)
            return True

        time.sleep(0.5)

    return False


def _select_custom(page, nth, label):
    """自製選單：只點擊完整名稱一致且可見的唯一選項。"""
    label = str(label).strip()
    page.locator(CUSTOM_DROPDOWN_CSS).nth(nth).click()
    deadline = time.monotonic() + 15

    while time.monotonic() < deadline:
        options = page.get_by_role("option", name=label, exact=True)
        visible = [
            options.nth(i)
            for i in range(options.count())
            if options.nth(i).is_visible()
        ]

        if not visible:
            texts = page.get_by_text(label, exact=True)
            visible = [
                texts.nth(i)
                for i in range(texts.count())
                if texts.nth(i).is_visible()
            ]

        if len(visible) > 1:
            raise RuntimeError(f"找到多個可見的同名項目「{label}」，不自動選取")

        if len(visible) == 1:
            visible[0].click()
            return

        time.sleep(0.5)

    raise RuntimeError(f"找不到完整名稱一致的選項「{label}」")
    
def choose(page, nth, label, selector=""):
    """選第 nth 個下拉選單（0＝第一個、1＝第二個）的指定項目。"""

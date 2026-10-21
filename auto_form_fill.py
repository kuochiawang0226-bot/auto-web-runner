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
    "[role=combobox], [aria-haspopup=listbox], .el-select, .ant-select, "
    ".select2-selection, .v-select, .dropdown-toggle"
)


def _select_native(sel, label, wait=15):
    """一般下拉選單：等選項出現（第二個選單常要等第一個選完才載入），再選取。"""
    deadline = time.time() + wait
    while time.time() < deadline:
        texts = [t.strip() for t in sel.locator("option").all_inner_texts()]
        if label in texts:
            sel.select_option(index=texts.index(label), force=True)
            return True
        partial = [k for k, t in enumerate(texts) if label in t]
        if partial:
            sel.select_option(index=partial[0], force=True)
            return True
        time.sleep(0.5)
    return False


def _select_custom(page, nth, label):
    """網站自製選單：點開第 nth 個選單，再點選項文字。"""
    page.locator(CUSTOM_DROPDOWN_CSS).nth(nth).click()
    time.sleep(0.8)
    opt = page.get_by_role("option", name=label)
    if opt.count() == 0:
        opt = page.get_by_text(label, exact=True)
    opt.last.click()


def choose(page, nth, label, selector=""):
    """選第 nth 個下拉選單（0＝第一個、1＝第二個）的指定項目。"""
    if selector:
        if not _select_native(page.locator(selector).first, label):
            raise RuntimeError(f"選單 {selector} 裡找不到「{label}」")
        return
    selects = page.locator("select")
    if selects.count() > nth and _select_native(selects.nth(nth), label):
        time.sleep(1)   # 讓網站有時間載入下一個選單的選項
        return
    _select_custom(page, nth, label)
    time.sleep(1)


TEXT_INPUT_CSS = (
    "input:not([type]), input[type=text], input[type=tel], input[type=email], "
    "input[type=number], input[type=search], textarea, [contenteditable=true]"
)


def _find_text_box(page, wait=15):
    """找出真正要打字的欄位：排除唯讀、停用、以及下拉選單內部的輸入框。"""
    deadline = time.time() + wait
    while time.time() < deadline:
        boxes = page.locator(TEXT_INPUT_CSS)
        for k in range(boxes.count()):
            box = boxes.nth(k)
            try:
                if not box.is_visible() or not box.is_editable():
                    continue
                inside_dropdown = box.evaluate(
                    """(el, css) => !!el.closest(css) || el.getAttribute('role') === 'combobox'
                         || el.hasAttribute('aria-autocomplete')
                         || el.getAttribute('aria-hidden') === 'true'
                         || el.getAttribute('tabindex') === '-1'
                         || /nativeInput/i.test(el.className)""",
                    CUSTOM_DROPDOWN_CSS + ", .select2-container, [role=listbox]",
                )
                if not inside_dropdown:
                    return box
            except Exception:
                continue
        time.sleep(0.5)
    raise RuntimeError("找不到可以輸入文字的欄位")


def fill_field(page, value):
    """模擬真人點欄位、清空、逐字輸入，讓網站確實收到內容。"""
    if FIELD_SELECTOR:
        box = page.locator(FIELD_SELECTOR).first
    elif FIELD_PLACEHOLDER and page.get_by_placeholder(FIELD_PLACEHOLDER).count() > 0:
        box = page.get_by_placeholder(FIELD_PLACEHOLDER).first
    else:
        box = _find_text_box(page)
    box.scroll_into_view_if_needed()
    box.click()
    box.press("Control+A")
    box.press("Delete")
    box.press_sequentially(value, delay=60)
    box.dispatch_event("change")
    box.press("Tab")          # 離開欄位，觸發網站的檢查
    time.sleep(0.5)
    try:
        got = box.input_value()
    except Exception:
        got = box.inner_text()
    if got.strip() != value.strip():
        raise RuntimeError(f"輸入欄位內容不符（預期「{value}」，實際「{got}」）")


def report_page(page, row_no):
    """失敗時印出網頁上的選單資訊並截圖，方便判斷原因。"""
    try:
        page.screenshot(path=f"錯誤畫面_第{row_no}列.png", full_page=True)
        selects = page.locator("select")
        print(f"  網頁上找到 {selects.count()} 個標準下拉選單：")
        for k in range(selects.count()):
            opts = [t.strip() for t in selects.nth(k).locator("option").all_inner_texts()][:8]
            print(f"   第 {k + 1} 個選項：{opts}")
        print(f"  自製選單數量：{page.locator(CUSTOM_DROPDOWN_CSS).count()}")
        boxes = page.locator(TEXT_INPUT_CSS)
        print(f"  找到 {boxes.count()} 個文字欄位：")
        for k in range(boxes.count()):
            b = boxes.nth(k)
            info = b.evaluate("e => [e.tagName, e.id, e.name, e.placeholder, e.readOnly, e.className].join(' | ')")
            print(f"   第 {k + 1} 個：{info}，看得到={b.is_visible()}")
        print(f"  已存截圖：錯誤畫面_第{row_no}列.png")
    except Exception:
        pass


def click_submit(page):
    """按下送出按鈕。"""
    btn = page.get_by_role("button", name=SUBMIT_TEXT)
    if btn.count() > 0:
        btn.first.click()
    else:
        page.locator(f"input[type=submit][value='{SUBMIT_TEXT}'], text={SUBMIT_TEXT}").first.click()


# ---------------- GitHub 工作排程與跨次紀錄 ----------------
import base64
import csv
import hashlib
import ipaddress
import json
import re
import urllib.request
import urllib.error
from pathlib import Path
from datetime import datetime, timezone

STATE_PATH = '.automation/state.json'
WORKFLOW_FILE = 'run-row.yml'


def now():
    return datetime.now(timezone.utc).isoformat()


def valid_ip(value):
    ip = ipaddress.ip_address(value.strip())
    if not ip.is_global:
        raise ValueError('查詢結果不是公開 IP')
    return str(ip)


def legacy_ips(path):
    """匯入舊 CSV 所有有效 IPv4/IPv6，包含失敗列與附註。"""
    result = set()
    if Path(path).exists():
        with open(path, encoding='utf-8-sig', newline='') as f:
            for row in csv.reader(f):
                if len(row) < 5:
                    continue
                value = re.split(r'[（(\s]', row[4].strip(), maxsplit=1)[0]
                try:
                    result.add(valid_ip(value))
                except ValueError:
                    pass
    return result


class GitHubStore:
    def __init__(self):
        self.repo = os.environ['GITHUB_REPOSITORY']
        self.branch = os.environ['DEFAULT_BRANCH']
        self.token = os.environ['GH_TOKEN']
        self.api = os.environ.get('GITHUB_API_URL', 'https://api.github.com')
        self.sha = None

    def request(self, method, path, body=None):
        data = None if body is None else json.dumps(body).encode()
        req = urllib.request.Request(self.api + '/repos/' + self.repo + path,
            data=data, method=method, headers={
                'Authorization': 'Bearer ' + self.token,
                'Accept': 'application/vnd.github+json',
                'Content-Type': 'application/json',
                'User-Agent': 'single-row-automation'})
        with urllib.request.urlopen(req, timeout=45) as response:
            raw = response.read()
            return json.loads(raw) if raw else None

    def load(self):
        from urllib.parse import quote
        try:
            response = self.request('GET', '/contents/' + STATE_PATH + '?ref=' + quote(self.branch, safe=''))
        except urllib.error.HTTPError as e:
            if e.code != 404:
                raise
            return {'version': 1, 'used_ips': [], 'batches': {}}
        self.sha = response['sha']
        state = json.loads(base64.b64decode(response['content']))
        if state.get('version') != 1:
            raise RuntimeError('不支援的狀態檔版本')
        return state

    def save(self, state):
        raw = json.dumps(state, ensure_ascii=False, indent=2).encode()
        body = {'message': 'Save automation progress', 'branch': self.branch,
                'content': base64.b64encode(raw).decode()}
        if self.sha:
            body['sha'] = self.sha
        # 使用 SHA 防止覆蓋其他工作的更新；失敗就停止，不自動覆寫。
        response = self.request('PUT', '/contents/' + STATE_PATH, body)
        self.sha = response['content']['sha']

    def dispatch(self, inputs):
        self.request('POST', '/actions/workflows/' + WORKFLOW_FILE + '/dispatches',
                     {'ref': self.branch, 'inputs': inputs})


def read_data(start, end):
    from openpyxl import load_workbook
    wb = load_workbook(EXCEL_PATH, data_only=True, read_only=True)
    try:
        ws = wb[SHEET_NAME] if SHEET_NAME else wb.worksheets[0]
        result = []
        for r, (a, b) in enumerate(ws.iter_rows(min_row=start, max_row=end or ws.max_row,
                                               max_col=2, values_only=True), start):
            if a is None or not str(a).strip():
                break
            result.append((r, str(a).strip(), '' if b is None else str(b).strip()))
        return result
    finally:
        wb.close()


def lookup_ip(page):
    response = page.goto('https://api.ipify.org', timeout=60000)
    if response is None or not response.ok:
        raise RuntimeError('IP 查詢服務回應失敗')
    return valid_ip(page.inner_text('body'))


def apply_row(page, row):
    row_no, a, b = row
    page.goto(TARGET_URL, timeout=90000)
    page.wait_for_load_state('networkidle', timeout=60000)
    choose(page, 0, DROPDOWN1_OPTION, DROPDOWN1_SELECTOR)
    choose(page, 1, a, DROPDOWN2_SELECTOR)
    fill_field(page, b)
    click_submit(page)
    time.sleep(WAIT_AFTER_SUBMIT)


def process_attempt(state, batch, rows, get_ip, operate, save):
    """一次只嘗試一個 IP；回傳 True 才接續新工作。可離線測試。"""
    if batch['status'] != 'ready':
        return False
    if batch['index'] >= len(rows):
        batch['status'] = 'complete'
        save(state)
        return False
    if batch['runs'] >= batch['max_runs']:
        batch['status'] = 'limit_reached'
        save(state)
        return False
    batch['runs'] += 1
    batch['step'] += 1
    row = rows[batch['index']]
    event = {'time': now(), 'row': row[0], 'run_id': os.environ.get('GITHUB_RUN_ID', ''),
             'result': 'checking', 'ip': ''}
    batch['events'].append(event)
    try:
        ip = valid_ip(get_ip())
    except Exception as exc:
        event['result'] = 'ip_lookup_failed'
        event['error'] = str(exc)
        batch['status'] = 'ip_lookup_failed'
        save(state)
        return False
    event['ip'] = ip
    if ip in state['used_ips']:
        event['result'] = 'duplicate_ip'
        batch['retries'] += 1
        # max_retries=5：首次重複後最多另外啟動 5 次。
        if batch['retries'] > batch['max_retries']:
            batch['status'] = 'retry_limit'
        elif batch['runs'] >= batch['max_runs']:
            batch['status'] = 'limit_reached'
        save(state)
        return batch['status'] == 'ready'
    # 操作網站前先保留 IP 及 in_flight，當機後不會默默重送。
    state['used_ips'].append(ip)
    batch['status'] = 'in_flight'
    event['result'] = 'in_flight'
    save(state)
    try:
        operate(row)
    except Exception as exc:
        event['result'] = 'operation_uncertain'
        event['error'] = str(exc)
        batch['status'] = 'operation_uncertain'
        save(state)
        return False
    event['result'] = '操作完成（沿用原程式判定）'
    batch['index'] += 1
    batch['retries'] = 0
    batch['status'] = 'complete' if batch['index'] == len(rows) else 'ready'
    if batch['status'] == 'ready' and batch['runs'] >= batch['max_runs']:
        batch['status'] = 'limit_reached'
    save(state)
    return batch['status'] == 'ready'


def main():
    if os.environ.get('GITHUB_ACTIONS') != 'true':
        raise RuntimeError('此版本請透過附帶的 GitHub Actions 工作流程執行。')
    mode = os.environ.get('MODE', 'check_ip')
    if mode not in ('check_ip', 'execute'):
        raise ValueError('未知模式')
    if mode == 'execute' and ('請填入' in TARGET_URL or not TARGET_URL.startswith('https://')):
        raise ValueError('請先設定 TARGET_URL Secret（HTTPS 網址）。')
    store = GitHubStore()
    state = store.load()
    state['used_ips'] = sorted(set(state['used_ips']) | legacy_ips('送出紀錄.csv'))
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            page = browser.new_page()
            if mode == 'check_ip':
                ip = lookup_ip(page)
                print('查詢到的出口 IP：', ip)
                print('歷史紀錄中是否出現：', ip in state['used_ips'])
                print('只查 IP：不操作目標網站、不接續下一次工作、不登記為已使用。')
                return
            start = int(os.environ.get('START_ROW', '2'))
            end = int(os.environ.get('END_ROW', '0'))
            retries = int(os.environ.get('MAX_RETRIES', '5'))
            max_runs = int(os.environ.get('MAX_RUNS', '100'))
            batch_id = os.environ.get('BATCH_ID', '').strip()
            if not re.fullmatch(r'[A-Za-z0-9_-]{1,64}', batch_id):
                raise ValueError('批次名稱只能含英數字、底線、連字號，1–64 字。')
            if start < 2 or (end and end < start) or not 0 <= retries <= 20 or not 1 <= max_runs <= 500:
                raise ValueError('列號／重試次數／總工作數設定不正確。')
            rows = read_data(start, end)
            fingerprint = hashlib.sha256(json.dumps([TARGET_URL, SHEET_NAME, rows],
                                       ensure_ascii=False).encode()).hexdigest()
            config = {'fingerprint': fingerprint, 'start': start, 'end': end,
                      'max_retries': retries, 'max_runs': max_runs}
            batch = state['batches'].get(batch_id)
            if batch is None:
                batch = dict(config, index=0, runs=0, retries=0, step=0, status='ready', events=[])
                state['batches'][batch_id] = batch
            elif any(batch.get(k) != v for k, v in config.items()):
                raise RuntimeError('同批次設定或資料已改變，請還原設定；新資料請使用新批次名稱。')
            expected = os.environ.get('EXPECTED_STEP', '').strip()
            if expected and int(expected) != batch['step']:
                print('過期的接續工作，略過。')
                return
            def operate(row):
                try:
                    apply_row(page, row)
                except Exception:
                    report_page(page, row[0])
                    raise
            more = process_attempt(state, batch, rows, lambda: lookup_ip(page), operate, store.save)
            print('批次：', batch_id, '狀態：', batch['status'], '已處理筆數：', batch['index'])
            Path('本次結果.json').write_text(json.dumps(batch, ensure_ascii=False, indent=2), encoding='utf-8')
            if more:
                time.sleep(15)
                store.dispatch({'mode': 'execute', 'batch_id': batch_id,
                    'start_row': str(start), 'end_row': str(end), 'max_retries': str(retries),
                    'max_runs': str(max_runs), 'expected_step': str(batch['step'])})
                print('已要求下一個獨立工作接續；請在 Actions 查看。')
            elif batch['status'] != 'complete':
                raise RuntimeError('批次已暫停：' + batch['status'] + '；請參閱 README。')
        finally:
            browser.close()


if __name__ == '__main__':
    main()

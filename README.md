# Windows IP 懸浮視窗

這是一個簡單的 Windows 懸浮視窗工具，會顯示：
- `Local IP`（區網 IP）
- `Public IP`（對外網路 IP）

功能：
- 視窗固定在最上層（可切換）
- 每 30 秒自動刷新
- 可按 `立即更新` 手動刷新

## 需求

- Windows
- Python 3.9+（建議 3.10 以上）

## 執行

在此資料夾開啟終端機後執行：

```bash
python ip_floating_window.py
```

## 打包成 EXE（可選）

1. 安裝 PyInstaller

```bash
pip install pyinstaller
```

2. 打包

```bash
pyinstaller --noconfirm --onefile --windowed --name IPFloatingWindow ip_floating_window.py
```

3. 執行檔位置

```text
dist/IPFloatingWindow.exe
```

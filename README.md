# Piermux 離線 Linux 桌面套件

目標：Rocky Linux 8 x86_64，已安裝 Singularity CE 3.11，具有可用的 X11 桌面。
以 Ubuntu 22.04 容器提供 WebKitGTK 4.1，不修改主機套件，不需要 Windows 管理員權限。
此為第三方離線封裝，非 Piermux 官方 Linux 發行版。固定上游 commit：
`fbad099633383a8544dc34576dc4ae220188b3f2`（v0.1.27 pre-release）。

## 下載與傳入

在 repository 的 Actions → Build offline bundle，開啟成功的執行紀錄，
下載 Artifacts 中的 `piermux-offline-linux-x86_64` ZIP。
解開 ZIP，將其中的 tar.gz 與 SHA256SUMS 一次傳到 Linux。
Actions 若失敗則不會產生可用成品；請查看失敗步驟。

## Linux 啟動

在包含下載檔案的目錄執行：

```bash
sha256sum -c SHA256SUMS
tar --no-same-owner -xzf piermux-offline-linux-x86_64.tar.gz
bash piermux-offline/start-piermux.sh
```

先確認校驗結果是 OK，再解壓。需要數 GB 可用空間，實際大小以 Actions 產物為準。
解壓後的 rootfs 是 Singularity 支援的 sandbox 目錄格式，不是 .sif；
不要只傳啟動指令，必須完整保留 rootfs 的檔案、權限與符號連結。
啟動與編譯都不會在 目標主機 下載相依套件。

## 本機 tmux：只填顯示名稱

先關閉舊版 GUI，再用新版 start-piermux.sh 啟動。不要只替換啟動指令，必須完整解壓新版套件。
新增連線預設「本機 tmux」，只需填顯示名稱並儲存，不需要 SSH host、帳號、密碼或私鑰。
既有錯選 SSH 的項目可點鉛筆，將連線方式改為「本機 tmux」後儲存。
左側展開本機項目即可看到目前使用者的 tmux sessions；主機列的 + 可新增 session。
每個 session 可作為專案，上方 window 按鈕可切換 agent 終端機。

啟動指令會在主機執行 Python 標準函式庫 bridge，使用私人 Unix socket，不開 TCP 或 SSH。
指令與 PTY 在主機執行，保留原本 PATH、shell、tmux server 和 bsub 等環境。
主機需要既有 tmux 與 Python 3；Rocky 若沒有 python3 指令，會自動使用 /usr/libexec/platform-python。
關閉 GUI 會清理 bridge 與 attach client，保留 tmux session 與既有 agent 工作。
從 tmux 裡啟動也可用，新 PTY 會清除外層 TMUX／TMUX_PANE 避免巢狀連線錯誤。

遠端 SSH 功能保留，只有選「SSH 遠端主機」才需要提供認證資訊。
本機模式不會存取 keyring，也不會繞過排程系統的 5-agent 限制。

## 驗證與限制

Actions 在 Ubuntu runner 上檢查動態函式庫，並以 Xvfb 啟動 GUI，
確認程式仍在執行且建立標題包含 piermux 的視窗後，才打包。
這不代表已在 Rocky 8、公司 Singularity 設定、中文輸入法或 tmux 2.7 驗收。
首次在目標機仍需確認視窗顯示、SSH、session 清單與 attach。

若出現 Can't open display：確認仍在相同桌面 session，DISPLAY 與 XAUTHORITY 正確；
不要使用 xhost + 放寬所有人的存取權。
若 Singularity 回報權限、user namespace 或 sandbox 禁止，
保留錯誤訊息；需調整封裝方式或由系統管理員確認政策。
若執行目錄掛載為 noexec，將完整套件移至允許執行的使用者目錄。

## 此版本的 GUI 擴充

專案沿用 tmux session；每個 session 的 attach 畫面新增可點選的 window 列。
先在左側選專案 session，再點上方 window 編號／名稱切換 agent 終端機。
每 10 秒同步一次清單；也可按更新按鈕立即同步。
可用原本 tmux 的 rename-window 指令替 agent 終端機命名。
切換 window 不會提交、重啟或終止 agent，分頁數不等於排程系統的工作名額。
本次不實作自動派工，也不會繞過既有的 5-agent 限制。
window 切換會改變 session 的目前 window，其他連到同一 session 的 client 可能跟著切換。

擴充 patch 隨映像保留在 /opt/piermux/WINDOW_TABS.patch。
CI 執行 React 顯示狀態測試、Rust 解析／參數測試、TypeScript 編譯與 GUI 啟動測試。
這些檢查不取代目標主機上的真實 SSH 點選切換驗收。

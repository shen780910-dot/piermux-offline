# 離線封裝計畫

目標：外網 GitHub Actions 建置，使用者一次傳入 Rocky Linux 8，
透過既有 Singularity CE 3.11 開啟 Piermux GUI，不安裝主機套件。

採用 Ubuntu 22.04 sandbox rootfs tar.gz；相較 .sif，不需額外安裝 SIF 建置工具。
相較直接 RPM 封裝，此方式可一併提供 WebKitGTK 4.1 與其相依套件。
固定上游 commit，npm ci / Cargo --locked，保留上游 MIT LICENSE。

1. Docker 多階段編譯 Piermux，執行環境不含建置工具。
2. 檢查 ldd，以 Xvfb 啟動 GUI 並確認視窗存在。
3. docker export 取出 rootfs，排除虛擬檔案系統內容，打包啟動指令與說明。
4. 產生 SHA-256 並上傳 Actions artifact。
5. 目標機驗收 X11、SSH、keyring、中文輸入與 tmux 2.7；這些無法由 CI 取代。

公開 repository 不包含公司資料、內部網址、帳密或私鑰。

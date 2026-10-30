# 本機 tmux 連線

使用者要求新增時只填顯示名稱，不需要 SSH 設定。新增連線預設本機，原有 SSH 連線保留。

1. 在主機執行 Python 標準函式庫 bridge，使用私人 0700 目錄與 0600 Unix socket，驗證 peer UID；不開 TCP 或 SSH。
2. 容器 GUI 經本機 socket 執行主機指令及 PTY。保留主機 PATH、shell、tmux server、工作目錄與排程工具，避免新 session 跑進容器環境。
3. 加入 transport abstraction，保留原 SSH backend；本機模式略過 keyring、私鑰與 SSH 驗證。表單預設本機且只要求顯示名稱。
4. 測試協定驗證、二進位／中文 PTY、resize、關閉 client 不終止 tmux session、本機表單、實際列出／建立／切換 session。
5. 編譯、GUI smoke test、產生新版離線封裝。原版及既有 window 分頁須繼續可用。

由啟動指令管理 bridge 生命週期；關閉 GUI 結束 bridge 與 attach client，保留主機 tmux server／agent 工作。
